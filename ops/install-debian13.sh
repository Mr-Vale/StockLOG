#!/usr/bin/env bash
# Native Debian installer. Run only on an explicitly authorised target.
set -euo pipefail
umask 027
if [[ ${EUID} -ne 0 ]]; then echo 'Run this installer as root.' >&2; exit 1; fi
source /etc/os-release
if [[ ${ID} != debian || ${VERSION_ID} != 13 ]]; then echo 'This release supports Debian 13 only.' >&2; exit 1; fi
DOMAIN=''; NO_START=0; SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN=${2:?}; shift 2 ;;
    --no-start) NO_START=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
if [[ ! $DOMAIN =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ || $DOMAIN != *.* ]]; then echo 'Supply --domain stocklog.your-domain.example (real public DNS required for HTTPS).' >&2; exit 2; fi
exec 9>/var/lock/stocklog-install.lock
flock -n 9 || { echo 'Another installation is running.' >&2; exit 1; }
trap 'flock -u 8 2>/dev/null || true; flock -u 9' EXIT
BACKUP_LOCKED=0
if [[ -d /var/lib/stocklog/backups ]]; then
  exec 8>/var/lib/stocklog/backups/.operations.lock
  flock 8
  BACKUP_LOCKED=1
fi
# Do not install SSH/firewall rules, create swap, alter root logins, or change OS release.
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3 python3-venv python3-dev build-essential pkg-config default-libmysqlclient-dev mariadb-server mariadb-client ca-certificates curl gnupg debian-archive-keyring caddy fonts-dejavu-core age logrotate systemd openssh-client openssh-server tar gzip
python3 -c 'import sys; assert sys.version_info[:2] == (3,13), "Debian Python 3.13 is required"'
if [[ $(df --output=avail -B1 /var/lib | tail -n1) -lt 1073741824 ]]; then echo 'Need at least 1 GiB free before installation.' >&2; exit 1; fi
getent group stocklog >/dev/null || groupadd --system stocklog
id stocklog >/dev/null 2>&1 || useradd --system --gid stocklog --home-dir /var/lib/stocklog --shell /usr/sbin/nologin stocklog
getent group stocklog-backup >/dev/null || groupadd --system stocklog-backup
id stocklog-backup >/dev/null 2>&1 || useradd --system --gid stocklog-backup --create-home --home-dir /var/lib/stocklog-backup --shell /bin/sh stocklog-backup
install -d -m 0750 /etc/stocklog /opt/stocklog/releases
install -d -o stocklog -g stocklog -m 0751 /var/lib/stocklog
install -d -o stocklog -g stocklog -m 0755 /var/lib/stocklog/static
install -d -o stocklog -g stocklog-backup -m 2750 /var/lib/stocklog/backups
if [[ $BACKUP_LOCKED == 0 ]]; then exec 8>/var/lib/stocklog/backups/.operations.lock; flock 8; fi
chown stocklog:stocklog-backup /var/lib/stocklog/backups/.operations.lock
chmod 0640 /var/lib/stocklog/backups/.operations.lock
install -d -o stocklog -g stocklog -m 0750 /var/log/stocklog
# Preserve an existing valid config/key. Never rotate secrets on a routine rerun.
if [[ ! -e /etc/stocklog/recovery.key ]]; then
  age-keygen -o /etc/stocklog/recovery.key 2>/dev/null
  chmod 0600 /etc/stocklog/recovery.key
fi
RECIPIENT=$(age-keygen -y /etc/stocklog/recovery.key)
if [[ ! -e /etc/stocklog/app.env ]]; then
  STOCKLOG_INSTALL_DOMAIN=$DOMAIN STOCKLOG_INSTALL_RECIPIENT=$RECIPIENT python3 - <<'PY'
import os,secrets,shlex
from pathlib import Path
values={'STOCKLOG_SECRET_KEY':secrets.token_urlsafe(64),'STOCKLOG_HOSTS':os.environ['STOCKLOG_INSTALL_DOMAIN'],'STOCKLOG_ORIGINS':'https://'+os.environ['STOCKLOG_INSTALL_DOMAIN'],'STOCKLOG_HTTPS':'1','STOCKLOG_STATE':'/var/lib/stocklog','STOCKLOG_BACKUPS':'/var/lib/stocklog/backups','STOCKLOG_AGE_RECIPIENT':os.environ['STOCKLOG_INSTALL_RECIPIENT'],'STOCKLOG_DB_NAME':'stocklog','STOCKLOG_DB_USER':'stocklog','STOCKLOG_DB_PASSWORD':secrets.token_hex(32),'STOCKLOG_DB_HOST':'localhost','STOCKLOG_BACKUP_DB_USER':'stocklog_backup','STOCKLOG_BACKUP_DB_PASSWORD':secrets.token_hex(32)}
path=Path('/etc/stocklog/app.env')
with path.open('x') as f:
    for key,value in values.items():f.write(key+'='+shlex.quote(value)+'\n')
PY
fi
chown root:stocklog /etc/stocklog/app.env;chmod 0640 /etc/stocklog/app.env;chown root:stocklog /etc/stocklog;chmod 0750 /etc/stocklog
set -a; source /etc/stocklog/app.env; set +a
if [[ $STOCKLOG_HOSTS != "$DOMAIN" ]]; then echo 'Existing hostname configuration differs; refusing to replace it automatically.' >&2; exit 1; fi
# This managed fragment is independent of other database/site configuration.
cat > /etc/mysql/mariadb.conf.d/70-stocklog.cnf <<'CONF'
[mariadb]
bind-address = 127.0.0.1
innodb_buffer_pool_size = 384M
max_connections = 20
performance_schema = OFF
CONF
if [[ $NO_START == 0 ]]; then systemctl enable --now mariadb; else service mariadb start 8>&- 9>&-; fi
# Random hex passwords are created only above. Validate identifiers before SQL use.
[[ $STOCKLOG_DB_NAME =~ ^[A-Za-z][A-Za-z0-9_]*$ && $STOCKLOG_DB_USER =~ ^[A-Za-z][A-Za-z0-9_]*$ && $STOCKLOG_DB_PASSWORD =~ ^[0-9a-f]{64}$ && $STOCKLOG_BACKUP_DB_PASSWORD =~ ^[0-9a-f]{64}$ ]] || { echo 'Unsupported existing database credential format; review configuration.' >&2; exit 1; }
# Never pass a password in process argv or print generated SQL/credentials.
python3 - <<'PY' | mariadb
import os
n=os.environ['STOCKLOG_DB_NAME'];u=os.environ['STOCKLOG_DB_USER'];p=os.environ['STOCKLOG_DB_PASSWORD'];b=os.environ['STOCKLOG_BACKUP_DB_PASSWORD']
print(f"CREATE DATABASE IF NOT EXISTS `{n}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
print(f"CREATE USER IF NOT EXISTS '{u}'@'localhost' IDENTIFIED BY '{p}';")
print(f"GRANT SELECT,INSERT,UPDATE,DELETE ON `{n}`.* TO '{u}'@'localhost';")
print(f"CREATE USER IF NOT EXISTS 'stocklog_backup'@'localhost' IDENTIFIED BY '{b}';")
print(f"GRANT SELECT,SHOW VIEW,TRIGGER ON `{n}`.* TO 'stocklog_backup'@'localhost';")
PY
RELEASE=$(sha256sum "$SOURCE/requirements.lock" | cut -c1-12)-$(find "$SOURCE/stocklog" "$SOURCE/herd" "$SOURCE/ops" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-12)
DEST=/opt/stocklog/releases/$RELEASE
if [[ ! -d $DEST ]]; then
  install -d -m 0755 "$DEST"
  tar -C "$SOURCE" --exclude='.git' --exclude='.venv' --exclude='.env' --exclude='.env.*' --exclude='__pycache__' --exclude='*.pyc' --exclude='var' --exclude='test-results' --exclude='docs/testing/generated' --exclude='App' --exclude='Config' -cf - . | tar -C "$DEST" -xf -
fi
chown -R root:root "$DEST";chmod 0755 /opt/stocklog /opt/stocklog/releases
python3 -m venv "$DEST/.venv"
# PIP_CERT is respected for isolated corporate-proxy tests; TLS verification remains enabled.
"$DEST/.venv/bin/pip" install --require-hashes -r "$DEST/requirements-build.lock"
"$DEST/.venv/bin/pip" install --no-build-isolation --require-hashes -r "$DEST/requirements.lock"
chmod -R a+rX "$DEST"
if [[ $NO_START == 0 ]] && systemctl is-active --quiet stocklog; then systemctl stop stocklog; fi
STOCKLOG_DB_USER=root STOCKLOG_DB_PASSWORD='' "$DEST/.venv/bin/python" "$DEST/manage.py" migrate --noinput
runuser -u stocklog -- "$DEST/.venv/bin/python" "$DEST/manage.py" collectstatic --noinput
find /var/lib/stocklog/static -type d -exec chmod 0755 {} +
find /var/lib/stocklog/static -type f -exec chmod 0644 {} +
"$DEST/.venv/bin/python" "$DEST/manage.py" check --deploy --fail-level ERROR
# No Django public registration/default password; first-admin setup is a separate terminal command.
ln -sfn "$DEST" /opt/stocklog/current
cat > /usr/local/bin/stocklog-manage <<'MANAGE'
#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then echo 'Run with administrative privileges.' >&2; exit 1; fi
set -a; source /etc/stocklog/app.env; set +a
exec runuser -u stocklog -- /opt/stocklog/current/.venv/bin/python /opt/stocklog/current/manage.py "$@"
MANAGE
chmod 0750 /usr/local/bin/stocklog-manage
install -m 0755 "$DEST/ops/backup_read.py" /usr/local/bin/stocklog-backup-read
cat > /etc/systemd/system/stocklog.service <<'UNIT'
[Unit]
Description=StockLOG Gunicorn application
After=network.target mariadb.service
Requires=mariadb.service
[Service]
User=stocklog
Group=stocklog
WorkingDirectory=/opt/stocklog/current
EnvironmentFile=/etc/stocklog/app.env
ExecStart=/opt/stocklog/current/.venv/bin/gunicorn stocklog.wsgi:application --bind 127.0.0.1:8001 --workers 1 --threads 2 --timeout 90 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile -
Restart=on-failure
RestartSec=5
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
MemoryHigh=512M
MemoryMax=768M
ReadWritePaths=/var/lib/stocklog /var/log/stocklog
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/stocklog-backup.service <<'UNIT'
[Unit]
Description=StockLOG consistent encrypted daily backup
After=mariadb.service
[Service]
Type=oneshot
User=stocklog
Group=stocklog-backup
WorkingDirectory=/opt/stocklog/current
EnvironmentFile=/etc/stocklog/app.env
ExecStart=/opt/stocklog/current/.venv/bin/python manage.py backup
UMask=0027
Nice=10
IOSchedulingClass=idle
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/stocklog
UNIT
cat > /etc/systemd/system/stocklog-backup.timer <<'UNIT'
[Unit]
Description=Daily StockLOG backup at 16:15 UTC
[Timer]
OnCalendar=*-*-* 16:15:00 UTC
Persistent=true
RandomizedDelaySec=300
[Install]
WantedBy=timers.target
UNIT
install -d -m 0755 /etc/caddy/sites-enabled
if [[ ! -f /etc/caddy/Caddyfile.stocklog-original ]]; then cp -a /etc/caddy/Caddyfile /etc/caddy/Caddyfile.stocklog-original; fi
# Only bootstrap the default fresh Debian Caddyfile; refuse to overwrite unrelated sites.
if ! grep -qF 'import /etc/caddy/sites-enabled/*' /etc/caddy/Caddyfile; then
  if grep -Eq '^:80[[:space:]]*\{' /etc/caddy/Caddyfile; then
    printf 'import /etc/caddy/sites-enabled/*\n' > /etc/caddy/Caddyfile
  else
    echo 'Existing Caddyfile is not the fresh package default. Add the sites-enabled import after review.' >&2; exit 1
  fi
fi
cat > /etc/caddy/sites-enabled/stocklog.caddy <<SITE
$DOMAIN {
    encode gzip
    request_body {
        max_size 8MB
    }
    handle_path /static/* {
        root * /var/lib/stocklog/static
        file_server
    }
    handle {
        reverse_proxy 127.0.0.1:8001
    }
}
SITE
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
cat > /etc/logrotate.d/stocklog <<'LOGROTATE'
/var/log/stocklog/*.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
LOGROTATE
# App output goes to journald; cap disk there without changing SSH/firewall state.
install -d /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=128M\nRuntimeMaxUse=32M\n' > /etc/systemd/journald.conf.d/stocklog.conf
systemctl enable stocklog stocklog-backup.timer caddy
if [[ $NO_START == 0 ]]; then
  systemctl daemon-reload
  systemctl restart mariadb stocklog caddy
  systemctl start stocklog-backup.timer
fi
printf 'Installed release %s. No account password was generated or printed.\n' "$RELEASE"
printf 'Next: stocklog-manage initial_admin --username YOUR_ADMIN --pic YOUR_PIC --property-name "YOUR PROPERTY"\n'
printf 'Copy /etc/stocklog/recovery.key to protected OFF-SERVER storage before relying on encrypted backups.\n'
printf 'Verify DNS/HTTPS, first sign-in, backup and isolated restore before operational use.\n'
