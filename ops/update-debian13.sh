#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $EUID == 0 ]] || { echo 'Run from a root terminal.' >&2; exit 1; }
source /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'Debian 13 required.' >&2; exit 1; }
[[ -L /opt/stocklog/current && -f /etc/stocklog/app.env ]] || { echo 'No StockLOG installation detected. See docs/operations/INSTALL.md.' >&2; exit 1; }
[[ -f /opt/stocklog/current/release.json && -f /opt/stocklog/current/ops/update.py ]] || {
  echo 'Unversioned installation: compatibility and commit cannot be inferred safely. See https://github.com/Mr-Vale/StockLOG/blob/main/docs/operations/UPDATES.md#major-version-reinstall' >&2
  exit 1
}
set -a; source /etc/stocklog/app.env; set +a
exec python3 /opt/stocklog/current/ops/update.py
