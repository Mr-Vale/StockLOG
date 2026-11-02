#!/usr/bin/env bash
# Download a pinned revision, then run its installer with the terminal intact.
set -euo pipefail
umask 077
[[ $EUID == 0 ]] || { echo 'Run as root (sudo bash).' >&2; exit 1; }
source /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'Debian 13 is required.' >&2; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates git
REF=${1:-main}
INSTALL_SOURCE=$(mktemp -d /root/stocklog-source.XXXXXXXX)
trap 'rm -rf -- "$INSTALL_SOURCE"' EXIT
git clone --quiet https://github.com/Mr-Vale/StockLOG.git "$INSTALL_SOURCE"
INSTALL_REVISION=$(git -C "$INSTALL_SOURCE" rev-parse --verify "$REF^{commit}" 2>/dev/null || git -C "$INSTALL_SOURCE" rev-parse --verify "refs/remotes/origin/$REF^{commit}")
git -C "$INSTALL_SOURCE" checkout --quiet --detach "$INSTALL_REVISION"
printf 'Installing StockLOG revision %s\n' "$(git -C "$INSTALL_SOURCE" rev-parse HEAD)"
bash "$INSTALL_SOURCE/ops/install-debian13.sh" </dev/tty
