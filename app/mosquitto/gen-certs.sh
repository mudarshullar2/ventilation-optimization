#!/usr/bin/env bash
# Generate a local CA and a broker server certificate for TLS (port 8883).
# For local use: the server cert is valid for localhost and 127.0.0.1.
set -euo pipefail
cd "$(dirname "$0")/certs"

# CA
openssl req -new -x509 -days 3650 -nodes \
  -keyout ca.key -out ca.crt -subj "/CN=home-climate-control-CA"

# Server key + CSR
openssl req -new -nodes -keyout server.key -out server.csr -subj "/CN=localhost"

# Sign with SANs so clients can verify localhost / 127.0.0.1
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 3650 \
  -extfile <(printf "subjectAltName=DNS:localhost,IP:127.0.0.1")

rm -f server.csr
echo "wrote mosquitto/certs/{ca.crt,server.crt,server.key}"
