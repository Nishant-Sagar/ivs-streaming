#!/bin/bash
# Start the server with local HTTPS so phones can use the camera.
# Requires mkcert: brew install mkcert
set -e
cd "$(dirname "$0")"

if ! command -v mkcert &>/dev/null; then
  echo "mkcert not found. Install it first:"
  echo "  brew install mkcert"
  exit 1
fi

mkdir -p .certs

# Get the machine's LAN IP
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")

mkcert -install 2>/dev/null || true

if [ -n "$LAN_IP" ]; then
  mkcert -cert-file .certs/cert.pem -key-file .certs/key.pem localhost 127.0.0.1 "$LAN_IP"
  echo ""
  echo "Open on your phone: https://$LAN_IP:8000/app/stream.html"
else
  mkcert -cert-file .certs/cert.pem -key-file .certs/key.pem localhost 127.0.0.1
fi

echo ""
cd backend
venv/bin/uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --ssl-certfile ../.certs/cert.pem \
  --ssl-keyfile ../.certs/key.pem \
  --env-file ../.env \
  --reload
