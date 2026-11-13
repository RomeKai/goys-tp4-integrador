#!/bin/sh
# Shared helpers for the Act 3 senders: build an OTLP/JSON payload and POST it with curl.
# OTLP/HTTP accepts JSON on /v1/metrics, so plain curl is enough to speak to the Collector.

COLLECTOR="${COLLECTOR_HOST:-otel-collector}"
ENDPOINT_PATH="/v1/metrics"

# Random integer in [0, $1) from the kernel's random source (busybox sh has no $RANDOM).
rand() {
  n="$(od -An -N2 -tu2 /dev/urandom | tr -d ' ')"
  echo $((n % $1))
}

# One resource (= one sender) with two gauges. Arguments: instance_id error_ratio requests_per_second
#   service.name       -> which application the telemetry claims to come from
#   service.instance.id -> which replica of it
resource_block() {
  now="$(($(date +%s) * 1000000000))"
  printf '{"resource":{"attributes":[{"key":"service.name","value":{"stringValue":"api-agent"}},'
  printf '{"key":"service.instance.id","value":{"stringValue":"%s"}}]},' "$1"
  printf '"scopeMetrics":[{"metrics":['
  printf '{"name":"demo_api_error_ratio","gauge":{"dataPoints":[{"timeUnixNano":"%s","asDouble":%s}]}},' "$now" "$2"
  printf '{"name":"demo_api_requests_per_second","gauge":{"dataPoints":[{"timeUnixNano":"%s","asDouble":%s}]}}' "$now" "$3"
  printf ']}]}'
}

# POST the payload in $PAYLOAD. Prints "<http status>|<curl error text>"; the status is 000 if no HTTP
# answer arrived (for example a TLS handshake failure). Extra arguments go straight to curl.
post() {
  url="$1"
  shift
  err_file="$(mktemp)"
  code="$(curl -sS -m 5 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' \
    -d "$PAYLOAD" "$@" "$url" 2>"$err_file")" || true
  printf '%s|%s' "$code" "$(tr '\n' ' ' <"$err_file")"
  rm -f "$err_file"
}
