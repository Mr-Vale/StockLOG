#!/usr/bin/env bash
# Download bootstrap tooling, which resolves the published release before installation.
set -euo pipefail
umask 077
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
SOURCE=$(mktemp -d /tmp/stocklog-bootstrap.XXXXXXXX)
trap 'rm -rf -- "$SOURCE"' EXIT
for name in bootstrap-debian13.sh release.py; do
  curl --fail --show-error --location "https://raw.githubusercontent.com/Mr-Vale/StockLOG/main/ops/$name" --output "$SOURCE/$name"
done
bash "$SOURCE/bootstrap-debian13.sh"
