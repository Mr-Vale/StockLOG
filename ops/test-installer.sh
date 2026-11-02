#!/usr/bin/env bash
# Disposable Debian image only. No VPS, host services, public DNS or certificate changes.
set -euo pipefail
INSTALLER_SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
INSTALLER_CONTAINER=stocklog-installer-test-$RANDOM-$RANDOM
trap 'docker rm -f "$INSTALLER_CONTAINER" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$INSTALLER_CONTAINER" --memory=2g --cpus=2 -v "$INSTALLER_SOURCE:/src:ro" debian:13 sleep infinity >/dev/null
docker exec "$INSTALLER_CONTAINER" bash -c 'apt-get update && apt-get install -y --no-install-recommends python3 python3-pexpect'
docker exec -i "$INSTALLER_CONTAINER" python3 - <<'PY'
import pexpect, sys
child=pexpect.spawn('bash', ['/src/ops/install-debian13.sh', '--no-start'], encoding='utf-8', timeout=900)
child.logfile_read=sys.stdout
child.expect('Public domain name .*: ')
child.sendline('stocklog.example.test')
child.expect('Initial administrator username: ')
child.sendline('installer-test-admin')
child.expect('Initial administrator password: ')
child.sendline('Disposable-Installer-Check-2026')
child.expect('Repeat password: ')
child.sendline('Disposable-Installer-Check-2026')
child.expect(pexpect.EOF)
child.close()
assert child.exitstatus == 0, f'Installer exited {child.exitstatus}'
PY
docker exec "$INSTALLER_CONTAINER" stocklog-manage check --deploy --fail-level ERROR
docker exec "$INSTALLER_CONTAINER" stocklog-manage shell -c "from herd.models import Account, Property; a=Account.objects.get(username='installer-test-admin'); assert a.administrator and a.check_password('Disposable-Installer-Check-2026'); assert not Property.objects.exists(); print('Initial administrator and empty property setup verified')"
# Re-running must stop rather than replace the activated installation or reset credentials.
if docker exec "$INSTALLER_CONTAINER" bash /src/ops/install-debian13.sh --no-start --domain stocklog.example.test; then
  echo 'Installer unexpectedly accepted an existing installation.' >&2; exit 1
fi
echo 'Debian 13 package/schema/configuration and terminal prompts passed. PID-1 service boot, reboot and public ACME remain unverified.'
