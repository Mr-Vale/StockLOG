#!/usr/bin/env bash
# Restore into a NEW isolated schema; optional explicit activation after full validation.
set -euo pipefail
umask 077
[[ ${EUID} -eq 0 ]] || { echo 'Administrative maintenance access is required.' >&2; exit 1; }
ARCHIVE=''; IDENTITY=''; TARGET=''; EXPECTED=''; ACTIVATE=0
while [[ $# -gt 0 ]]; do
 case "$1" in
  --archive) ARCHIVE=${2:?};shift 2;;
  --identity) IDENTITY=${2:?};shift 2;;
  --target) TARGET=${2:?};shift 2;;
  --sha256) EXPECTED=${2:?};shift 2;;
  --activate) ACTIVATE=1;shift;;
  *) echo "Unknown option $1" >&2;exit 2;;
 esac
done
[[ $TARGET =~ ^stocklog_restore_[A-Za-z0-9_]+$ && $EXPECTED =~ ^[0-9a-f]{64}$ && -f $ARCHIVE && -f $IDENTITY ]] || { echo 'Supply archive, protected key, expected SHA-256 and NEW target stocklog_restore_NAME.' >&2;exit 2; }
ACTUAL=$(sha256sum "$ARCHIVE" | cut -d' ' -f1)
[[ $ACTUAL == "$EXPECTED" ]] || { echo 'Ciphertext checksum mismatch; nothing restored.' >&2;exit 1; }
set -a;source /etc/stocklog/app.env;set +a
mariadb -e "CREATE DATABASE \`$TARGET\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
# No DROP/overwrite. On failure this new schema stays isolated for diagnosis.
STOCKLOG_DB_NAME=$TARGET STOCKLOG_DB_USER=root STOCKLOG_DB_PASSWORD='' /opt/stocklog/current/.venv/bin/python /opt/stocklog/current/manage.py restore "$ARCHIVE" --identity "$IDENTITY" --confirm-database "$TARGET"
mariadb -e "GRANT SELECT,INSERT,UPDATE,DELETE ON \`$TARGET\`.* TO 'stocklog'@'localhost'; GRANT SELECT,SHOW VIEW,TRIGGER ON \`$TARGET\`.* TO 'stocklog_backup'@'localhost';"
if [[ $ACTIVATE == 1 ]]; then
 systemctl stop stocklog
 cp -a /etc/stocklog/app.env /etc/stocklog/app.env.pre-restore
 STOCKLOG_RESTORE_TARGET=$TARGET python3 - <<'PY'
import os
from pathlib import Path
p=Path('/etc/stocklog/app.env');source=p.read_text().splitlines()
content='\n'.join('STOCKLOG_DB_NAME='+os.environ['STOCKLOG_RESTORE_TARGET'] if line.startswith('STOCKLOG_DB_NAME=') else line for line in source)+'\n'
tmp=p.with_suffix('.restore.tmp');tmp.write_text(content);tmp.chmod(0o640)
import grp
os.chown(tmp,0,grp.getgrnam('stocklog').gr_gid);os.replace(tmp,p)
PY
 systemctl start stocklog
 echo 'Restored target activated. Prior database retained; rollback uses app.env.pre-restore and a service restart.'
else
 echo 'Restore validated into an isolated schema; active application database was not changed.'
fi
