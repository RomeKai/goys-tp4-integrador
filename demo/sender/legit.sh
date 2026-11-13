#!/bin/sh
# The LEGITIMATE agent: reports the error ratio and request rate of api every 5 s.
# The story is that api really has about 11 % errors (an application problem). That is the truth
# the forged telemetry of the attacker tries to hide.
#   OTLP_MODE=plain  -> http://otel-collector:4318         (Acts 1-2 behaviour, no TLS)
#   OTLP_MODE=mtls   -> https://otel-collector:4318 with the client certificate
#   legit.sh once    -> send one batch, print the result and exit (0 = accepted)
set -eu
. /usr/local/bin/otlp.sh

MODE="${OTLP_MODE:-plain}"
INSTANCE="api-agent-1"
LAST_RESULT=""

# Send one batch. Succeeds only if the Collector answers HTTP 200.
send_once() {
  ratio="$(printf '0.%02d' $((9 + $(rand 5))))" # 0.09 .. 0.13
  rps="$((8 + $(rand 5)))"                       # 8 .. 12
  PAYLOAD="{\"resourceMetrics\":[$(resource_block "$INSTANCE" "$ratio" "$rps")]}"
  if [ "$MODE" = "mtls" ]; then
    LAST_RESULT="$(post "https://$COLLECTOR:4318$ENDPOINT_PATH" --cacert /certs/ca.crt --cert /certs/client.crt --key /certs/client.key)"
  else
    LAST_RESULT="$(post "http://$COLLECTOR:4318$ENDPOINT_PATH")"
  fi
  [ "${LAST_RESULT%%|*}" = "200" ]
}

if [ "${1:-}" = "once" ]; then
  if send_once; then
    echo "[legítimo, $MODE] ACEPTADO por el Collector (HTTP 200)"
    exit 0
  fi
  echo "[legítimo, $MODE] RECHAZADO: ${LAST_RESULT#*|}"
  exit 1
fi

previous=""
while true; do
  if send_once; then state="ACEPTADO"; else state="RECHAZADO: ${LAST_RESULT#*|}"; fi
  # Only log changes, so `docker compose logs otlp-agent` stays readable.
  if [ "$state" != "$previous" ]; then
    echo "[$(date +%H:%M:%S)] legítimo ($MODE): $state"
    previous="$state"
  fi
  sleep 5
done
