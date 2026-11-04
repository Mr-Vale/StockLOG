#!/usr/bin/env bash
# Disposable Debian image only. No VPS, host services, public DNS or certificate changes.
set -euo pipefail
INSTALLER_SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
INSTALLER_CONTAINER=stocklog-installer-test-$RANDOM-$RANDOM
trap 'docker rm -f "$INSTALLER_CONTAINER" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$INSTALLER_CONTAINER" --memory=2g --cpus=2 -v "$INSTALLER_SOURCE:/src:ro" -v "${STOCKLOG_TEST_CA_BUNDLE:-/etc/ssl/certs/ca-certificates.crt}:/tmp/test-ca.pem:ro" -e PIP_CERT=/tmp/test-ca.pem debian:13 sleep infinity >/dev/null
docker exec "$INSTALLER_CONTAINER" bash -c 'apt-get update && apt-get install -y --no-install-recommends python3 python3-pexpect'
# A synthetic tagged-source identity tests the installer without publishing a release.
docker exec "$INSTALLER_CONTAINER" bash -c 'mkdir /test-source; tar -C /src --exclude=.git --exclude=work --exclude=__pycache__ -cf - . | tar -C /test-source -xf -'
docker exec -i "$INSTALLER_CONTAINER" python3 - <<'IDENTITY'
import json
from pathlib import Path
p=Path('/test-source')
v=json.loads((p/'stocklog/version.json').read_text())['version']
(p/'release.json').write_text(json.dumps(dict(version=v,tag='v'+v,commit='a'*40,health='prepared')))
IDENTITY
docker exec -i "$INSTALLER_CONTAINER" python3 - <<'PY'
import pexpect, sys
child=pexpect.spawn('bash', ['/test-source/ops/install-debian13.sh', '--no-start'], encoding='utf-8', timeout=900)
child.logfile_read=sys.stdout
child.expect('Public domain name .*: ', timeout=20)
child.sendline('stocklog.example.test')
child.expect('Initial administrator username: ', timeout=300)
child.sendline('installer-test-admin')
child.expect('Initial administrator password: ', timeout=30)
child.sendline('Disposable-Installer-Check-2026')
child.expect('Repeat password: ', timeout=30)
child.sendline('Disposable-Installer-Check-2026')
# Background Debian service helpers can inherit the PTY even after bash exits.
# Match completion, then give bash a short exit window instead of waiting 15 minutes for PTY closure.
child.expect('Verify DNS/HTTPS, first sign-in, backup and isolated restore before operational use.', timeout=60)
child.expect(pexpect.EOF, timeout=5)
child.close()
assert child.exitstatus == 0, f'Installer exited {child.exitstatus}'
PY
# Regression: root validation misses unreadable imports. Exercise the service identity.
docker exec "$INSTALLER_CONTAINER" runuser -u caddy -- caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker exec "$INSTALLER_CONTAINER" bash -c 'test "$(stat -c "%U:%G:%a" /etc/caddy/sites-enabled/stocklog.caddy)" = "root:caddy:640" && test "$(stat -c "%U:%G:%a" /etc/caddy/Caddyfile)" = "root:caddy:640"'
docker exec "$INSTALLER_CONTAINER" runuser -u caddy -- test ! -r /etc/stocklog/app.env
docker exec "$INSTALLER_CONTAINER" stocklog-manage check --deploy --fail-level ERROR
docker exec "$INSTALLER_CONTAINER" stocklog-manage shell -c "from herd.models import Account, Property; a=Account.objects.get(username='installer-test-admin'); assert a.administrator and a.check_password('Disposable-Installer-Check-2026'); assert not Property.objects.exists(); print('Initial administrator and empty property setup verified')"
# Re-running must stop rather than replace the activated installation or reset credentials.
if docker exec "$INSTALLER_CONTAINER" bash /test-source/ops/install-debian13.sh --no-start --domain stocklog.example.test; then
  echo 'Installer unexpectedly accepted an existing installation.' >&2; exit 1
fi
docker exec "$INSTALLER_CONTAINER" bash -c 'set -a; source /etc/stocklog/app.env; set +a; python3 /src/ops/test-updates.py'
echo 'Debian 13 package/schema/configuration and terminal prompts passed. PID-1 service boot, reboot and public ACME remain unverified.'
