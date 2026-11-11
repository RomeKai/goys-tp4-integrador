#!/usr/bin/env bash
# Generate the demo PKI for the Act 3 mTLS scenario into demo/certs/ (git-ignored: NEVER commit keys).
#
#   certs/ca/ca.crt, ca.key              the demo Certificate Authority (ca.key never leaves this folder)
#   certs/server/ca.crt server.crt .key  mounted ONLY into the Collector
#   certs/client/ca.crt client.crt .key  mounted ONLY into the legitimate agent (otlp-agent)
#
# Usage:  scripts/certs.sh           create the certificates if they do not exist yet
#         scripts/certs.sh --force   delete and recreate them
# openssl comes from the host if available; otherwise it runs inside the goys-demo/sender image
# (force that with CERTS_USE_DOCKER=1). Everything is demo-only and valid for 365 days.
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like Unix paths (e.g. -subj "/CN=...").
export MSYS_NO_PATHCONV=1

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTS_DIR="$DEMO_DIR/certs"
SENDER_IMAGE="goys-demo/sender:1.0.0"

if [ "${1:-}" = "--force" ]; then
  rm -rf "$CERTS_DIR"
elif [ -f "$CERTS_DIR/server/server.crt" ] && [ -f "$CERTS_DIR/client/client.crt" ]; then
  echo "Certificates already exist in $CERTS_DIR (use --force to recreate)."
  exit 0
fi

# POSIX sh commands that build the whole PKI in the current directory. They run on the host or in
# the container, so only plain openssl is used here.
PKI_COMMANDS='
set -eu
mkdir -p ca server client

# 1. Certificate Authority: a self-signed certificate that is allowed to sign other certificates.
openssl ecparam -name prime256v1 -genkey -noout -out ca/ca.key
openssl req -x509 -new -key ca/ca.key -sha256 -days 365 -subj "/CN=TP4 Demo CA" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -out ca/ca.crt

# 2. Server certificate for the Collector. The SAN list is what a client checks the server name against.
openssl ecparam -name prime256v1 -genkey -noout -out server/server.key
openssl req -new -key server/server.key -subj "/CN=otel-collector" -out server/server.csr
printf "subjectAltName=DNS:otel-collector,DNS:localhost,IP:127.0.0.1,IP:172.28.0.22\nextendedKeyUsage=serverAuth\n" > server/server.ext
openssl x509 -req -in server/server.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
  -days 365 -sha256 -extfile server/server.ext -out server/server.crt

# 3. Client certificate for the legitimate sender: same idea, but usable for client authentication.
openssl ecparam -name prime256v1 -genkey -noout -out client/client.key
openssl req -new -key client/client.key -subj "/CN=legit-agent" -out client/client.csr
printf "extendedKeyUsage=clientAuth\n" > client/client.ext
openssl x509 -req -in client/client.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial \
  -days 365 -sha256 -extfile client/client.ext -out client/client.crt

# 4. Each side also gets the CA certificate (public) to verify the other one. Tidy up.
cp ca/ca.crt server/ca.crt
cp ca/ca.crt client/ca.crt
rm -f server/*.csr server/*.ext client/*.csr client/*.ext ca/*.srl
# Demo only: containers run as other users and must be able to read the key files.
chmod 644 server/server.key client/client.key
'

mkdir -p "$CERTS_DIR"
if [ "${CERTS_USE_DOCKER:-0}" != "1" ] && command -v openssl >/dev/null 2>&1; then
  echo "Generating certificates with the host openssl ($(openssl version)) ..."
  (cd "$CERTS_DIR" && sh -c "$PKI_COMMANDS")
else
  echo "Generating certificates inside $SENDER_IMAGE (CERTS_USE_DOCKER=1 or no openssl on the host) ..."
  if ! docker image inspect "$SENDER_IMAGE" >/dev/null 2>&1; then
    echo "Missing image $SENDER_IMAGE: run scripts/pull-images.sh (or load-images.sh) first." >&2
    exit 1
  fi
  # The container writes the PKI to /pki and streams it back as a tar: no host mounts, works on Windows.
  # openssl's progress messages go to stderr (>&2) so they cannot corrupt the tar on stdout.
  docker run --rm "$SENDER_IMAGE" sh -c "mkdir /pki && cd /pki && { $PKI_COMMANDS
  } >&2 && tar cf - ." | tar xf - -C "$CERTS_DIR"
fi

echo
echo "Done. Files in $CERTS_DIR:"
(cd "$CERTS_DIR" && find . -type f | sort)
echo
if command -v openssl >/dev/null 2>&1; then
  # Relative paths: a native-Windows openssl does not understand /c/... paths.
  (cd "$CERTS_DIR" && openssl verify -CAfile ca/ca.crt server/server.crt client/client.crt)
fi
