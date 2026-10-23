#!/usr/bin/env bash
# Developer infrastructure only: never run against a VPS, NAS or existing database.
set -euo pipefail
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
NAME=stocklog-test-$RANDOM-$RANDOM
cleanup() { docker exec "$NAME" chown -R "$(id -u):$(id -g)" /src/docs/testing/generated >/dev/null 2>&1 || true; docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
# --memory/--cpus reproduce the intended small host class; Docker is not production infrastructure.
docker run -d --name "$NAME" --memory=2g --cpus=2 -v "$SOURCE:/src" debian:13 sleep infinity >/dev/null
CERT_ENV=()
if [[ -n ${STOCKLOG_TEST_CA_BUNDLE:-} ]]; then
 docker cp "$STOCKLOG_TEST_CA_BUNDLE" "$NAME:/tmp/test-ca.pem"
 CERT_ENV=(-e PIP_CERT=/tmp/test-ca.pem)
fi
docker exec "$NAME" bash -c 'export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get install -y --no-install-recommends python3 python3-venv python3-dev build-essential pkg-config default-libmysqlclient-dev mariadb-server mariadb-client ca-certificates age fonts-dejavu-core chromium && python3 -m venv /opt/test-venv'
docker exec "${CERT_ENV[@]}" "$NAME" bash -c 'cd /src && /opt/test-venv/bin/pip install --require-hashes -r requirements-build.lock && /opt/test-venv/bin/pip install --no-build-isolation --require-hashes -r requirements-dev.lock'
docker exec "$NAME" bash -c 'service mariadb start && mariadb -e "CREATE DATABASE stocklog CHARACTER SET utf8mb4; CREATE USER '\''stocklog'\''@'\''localhost'\''; GRANT ALL ON stocklog.* TO '\''stocklog'\''@'\''localhost'\''; GRANT ALL ON test_stocklog.* TO '\''stocklog'\''@'\''localhost'\'';"'
docker exec -e STOCKLOG_SECRET_KEY=isolated-test-key-not-a-production-secret -e STOCKLOG_DEBUG=1 -e STOCKLOG_HTTPS=0 "$NAME" bash -c 'cd /src && /opt/test-venv/bin/python manage.py migrate --noinput && /opt/test-venv/bin/pytest -v --junitxml=docs/testing/generated/junit.xml'
