#!/usr/bin/env bash
# Act 3 helper: start the full stack and run the telemetry-poisoning / mTLS scenario.
# Every command is idempotent (safe to repeat).
#
#   act3.sh up                  start Acts 1+2+3 (keeps the current mTLS setting)
#   act3.sh down [-v]           stop everything (-v also deletes Prometheus/Grafana data; the model is kept)
#   act3.sh poison on           the attacker starts injecting FORGED telemetry into the Collector
#   act3.sh poison off
#   act3.sh poison logs         what the attacker sees (accepted / rejected, with the exact TLS error)
#   act3.sh mtls on             the Collector requires client certificates (mutual TLS)
#   act3.sh mtls off            back to plain, unauthenticated OTLP
#   act3.sh try attacker|legit  one attempt from the attacker / from the legitimate agent, result on screen
#   act3.sh status              mode, attack state, what Prometheus holds, LLM state
#
# The Act 1-2 stack is not affected: plain OTLP is the default and nothing here runs unless the
# Act 3 override is loaded.
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like Unix paths (e.g. /usr/local/bin/...).
export MSYS_NO_PATHCONV=1

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

STATE_FILE="$DEMO_DIR/.act3-mode" # "plain" or "mtls" (git-ignored)

usage() {
  sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 1
}

current_mode() {
  if [ -f "$STATE_FILE" ]; then cat "$STATE_FILE"; else echo plain; fi
}

# Run docker compose with the three files and the variables that select the Collector overlay.
compose() {
  local mode; mode="$(current_mode)"
  OTLP_MODE="$mode" OTEL_OVERLAY="overlay-$mode.yaml" \
    docker compose -f docker-compose.yml -f docker-compose.act2.yml -f docker-compose.act3.yml "$@"
}

require_running() {
  local service="$1"
  local running
  running="$(compose ps --status running --services)"
  if ! grep -qx "$service" <<<"$running"; then
    echo "Service '$service' is not running. Start the full stack first:  bash scripts/act3.sh up" >&2
    exit 1
  fi
}

wait_for_collector() {
  # The Collector image has no shell or wget: ask its health endpoint (plain HTTP, port 13133) from another container.
  local i
  for i in $(seq 1 30); do
    if compose exec -T poisoner curl -s -o /dev/null -m 2 http://otel-collector:13133/ 2>/dev/null; then return 0; fi
    sleep 1
  done
  echo "The Collector did not become healthy in 30 s. Look at: docker compose ... logs otel-collector" >&2
  return 1
}

attack_running() {
  compose exec -T poisoner pgrep -f /usr/local/bin/attack.sh >/dev/null 2>&1
}

poison_on() {
  require_running poisoner
  if attack_running; then
    echo "poison already ON"
    return
  fi
  # Run the loop detached, with its output sent to the container's stdout so `poison logs` can show it.
  compose exec -d poisoner sh -c 'exec /usr/local/bin/attack.sh >/proc/1/fd/1 2>&1'
  echo "poison ON: attacker injects forged telemetry (5 fake api replicas reporting 0 % errors) every 2 s"
}

poison_off() {
  require_running poisoner
  compose exec -T poisoner pkill -f /usr/local/bin/attack.sh >/dev/null 2>&1 || true
  echo "poison OFF (forged series expire from the Collector in ~30 s)"
}

mtls_set() {
  local target="$1"
  if [ "$target" = "mtls" ]; then
    bash "$DEMO_DIR/scripts/certs.sh" >/dev/null # no-op if the certificates already exist
  fi
  require_running otel-collector
  local previous; previous="$(current_mode)"
  echo "$target" >"$STATE_FILE" # compose() reads the mode from this file, so it must be written before `up`
  # Recreate the two services that depend on the mode: the Collector (new overlay) and the legitimate agent (new scheme).
  if ! compose up -d --force-recreate otel-collector otlp-agent >/dev/null; then
    echo "$previous" >"$STATE_FILE"
    echo "Could not switch the Collector to $target mode (see the error above)" >&2
    exit 1
  fi
  wait_for_collector
  if [ "$target" = "mtls" ]; then
    echo "mTLS ON: the Collector now requires a client certificate signed by the demo CA"
  else
    echo "mTLS OFF: the Collector accepts unauthenticated, unencrypted OTLP again"
  fi
}

try_sender() {
  case "$1" in
    attacker)
      require_running poisoner
      compose exec -T poisoner /usr/local/bin/attack.sh once || true
      ;;
    legit)
      require_running otlp-agent
      compose exec -T otlp-agent /usr/local/bin/legit.sh once || true
      ;;
    *) usage ;;
  esac
}

prom_value() {
  compose exec -T prometheus wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null \
    | sed -n 's/.*"value":\[[^,]*,"\([^"]*\)"\].*/\1/p' || true
}

show_status() {
  require_running poisoner
  echo "mTLS requested:    $(current_mode)"
  if attack_running; then echo "attacker loop:     ON"; else echo "attacker loop:     off"; fi
  local replicas points
  replicas="$(prom_value 'count(demo_api_error_ratio)%20or%20vector(0)')"
  points="$(prom_value 'sum(rate(otelcol_receiver_accepted_metric_points[30s]))%20or%20vector(0)')"
  printf 'api replicas reporting over OTLP (1 = only the real one): %s\n' "${replicas:-?}"
  printf 'metric points accepted by the Collector per second:       %.2f\n' "${points:-0}"
  # Rejected handshakes are not a Prometheus metric (they fail before any data reaches the pipeline),
  # but the Collector logs each one: this is the only server-side count of rejected attempts.
  local rejected
  rejected="$(compose logs --no-log-prefix otel-collector 2>/dev/null | grep -c 'TLS handshake error' || true)"
  printf 'TLS handshakes rejected by the Collector (its log, since the last restart): %s
' "${rejected:-0}"
  echo "Try it:  bash scripts/act3.sh try attacker | try legit"
  echo "RCA page: http://localhost:8085   Grafana: http://localhost:3000"
}

main() {
  case "${1:-}:${2:-}" in
    up:*)          compose up -d; echo "Grafana http://localhost:3000   RCA http://localhost:8085" ;;
    down:*)        compose down "${@:2}"; rm -f "$STATE_FILE" ;;
    poison:on)     poison_on ;;
    poison:off)    poison_off ;;
    poison:logs)   compose logs --tail 20 poisoner ;;
    mtls:on)       mtls_set mtls ;;
    mtls:off)      mtls_set plain ;;
    try:*)         try_sender "${2:-}" ;;
    status:*)      show_status ;;
    *)             usage ;;
  esac
}

main "$@"
