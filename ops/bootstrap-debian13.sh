#!/usr/bin/env bash
# Download a pinned revision, then run its installer with the terminal intact.
set -euo pipefail
umask 077
[[ $EUID == 0 ]] || { echo 'Run as root (sudo bash).' >&2; exit 1; }
source /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'Debian 13 is required.' >&2; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates git python3
[[ $# == 0 ]] || { echo 'Only the latest published stable release can be installed.' >&2; exit 2; }
INSTALL_SOURCE=$(mktemp -d /tmp/stocklog-source.XXXXXXXX)
trap 'rm -rf -- "$INSTALL_SOURCE"' EXIT
# Bootstrap resolver comes from this script's reviewed checkout/download directory.
python3 "$(dirname -- "${BASH_SOURCE[0]}")/release.py" "$INSTALL_SOURCE/source"
bash "$INSTALL_SOURCE/source/ops/install-debian13.sh" </dev/tty
