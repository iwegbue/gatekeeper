#!/usr/bin/env bash
set -euo pipefail

REPO="${GATEKEEPER_REPO:-iwegbue/gatekeeper}"
REF="${GATEKEEPER_REF:-main}"
BASE="https://raw.githubusercontent.com/${REPO}/${REF}/deploy"

echo "Gatekeeper: downloading compose files from ${REPO} @ ${REF}"
curl -fsSL "${BASE}/docker-compose.yml" -o docker-compose.yml
curl -fsSL "${BASE}/nginx.conf" -o nginx.conf

if [[ -n "${GATEKEEPER_IMAGE:-}" ]]; then
  export GATEKEEPER_IMAGE
fi

echo "Pulling images (this may take a minute the first time)..."
docker compose pull

echo "Starting services..."
docker compose up -d

echo ""
echo "Gatekeeper is starting. Open http://localhost in your browser to finish setup."
echo "To pin a version later, set GATEKEEPER_IMAGE in a .env file (see deploy/README.md)."
