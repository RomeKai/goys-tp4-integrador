#!/usr/bin/env bash
# Start and stop the two Act 2 incidents. Every command is idempotent (safe to repeat).
#
#   inject-incident.sh latency on [delay_ms] [jitter_ms]   gradual degradation of "api"
#   inject-incident.sh latency off
#   inject-incident.sh scan on                             slow port scan against demo-net
#   inject-incident.sh scan off
#   inject-incident.sh status                              what is active + what the detector says
#
# Requires the stack started with the Act 2 override:
#   docker compose -f docker-compose.yml -f docker-compose.act2.yml up -d
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like Unix paths (e.g. /usr/local/bin/...).
export MSYS_NO_PATHCONV=1

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.act2.yml)

# Defaults stay well below the Act 1 thresholds (HTTP 500 ms, ICMP RTT 100 ms):
# 50 ms +/- 25 ms of delay on api's replies gives an ICMP RTT of 25-75 ms and an HTTP probe of ~100 ms.
DEFAULT_DELAY_MS=50
DEFAULT_JITTER_MS=25

usage() {
  sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 1
}

require_running() {
  local service="$1"
  if ! "${COMPOSE[@]}" ps --status running --services | grep -qx "$service"; then
    echo "Service '$service' is not running. Start the Act 2 stack first:" >&2
    echo "  docker compose -f docker-compose.yml -f docker-compose.act2.yml up -d" >&2
    exit 1
  fi
}

# Run `tc` inside the netem sidecar (which shares api's network namespace).
# If api was restarted, the sidecar keeps the OLD namespace (no eth0 there) and must be recreated.
tc_in_api() {
  if ! "${COMPOSE[@]}" exec -T netem tc qdisc show dev eth0 >/dev/null 2>&1; then
    echo "netem sidecar lost api's network namespace, recreating it ..." >&2
    "${COMPOSE[@]}" up -d --force-recreate netem >/dev/null 2>&1
  fi
  "${COMPOSE[@]}" exec -T netem tc "$@"
}

latency_state() {
  # The qdisc line contains "delay ..." only while the netem rule is active.
  tc_in_api qdisc show dev eth0 | grep -o 'delay.*' || true
}

latency_on() {
  local delay="${1:-$DEFAULT_DELAY_MS}" jitter="${2:-$DEFAULT_JITTER_MS}"
  require_running netem
  # "replace" creates the qdisc if missing and updates it if present: idempotent.
  tc_in_api qdisc replace dev eth0 root netem delay "${delay}ms" "${jitter}ms"
  echo "latency ON: api replies delayed ${delay} ms +/- ${jitter} ms"
}

latency_off() {
  require_running netem
  # Deleting a qdisc that does not exist is an error: ignore it so "off" is idempotent.
  tc_in_api qdisc del dev eth0 root 2>/dev/null || true
  echo "latency OFF"
}

scan_running() {
  "${COMPOSE[@]}" exec -T attacker pgrep -f /usr/local/bin/scan.sh >/dev/null 2>&1
}

scan_on() {
  require_running attacker
  if scan_running; then
    echo "scan already ON"
    return
  fi
  "${COMPOSE[@]}" exec -d attacker /usr/local/bin/scan.sh
  echo "scan ON: slow nmap SYN scan (-T2) against 172.28.0.0/24 services"
}

scan_off() {
  require_running attacker
  # Kill the loop first so it does not start a new nmap, then the running nmap.
  "${COMPOSE[@]}" exec -T attacker pkill -f /usr/local/bin/scan.sh >/dev/null 2>&1 || true
  "${COMPOSE[@]}" exec -T attacker pkill nmap >/dev/null 2>&1 || true
  echo "scan OFF"
}

prom_value() {
  # Ask Prometheus (from inside its own container, no host tools needed) for one value.
  "${COMPOSE[@]}" exec -T prometheus wget -qO- "http://localhost:9090/api/v1/query?query=$1" 2>/dev/null \
    | sed -n 's/.*"value":\[[^,]*,"\([^"]*\)"\].*/\1/p' || true
}

show_status() {
  require_running netem
  require_running attacker

  local lat; lat="$(latency_state)"
  if [ -n "$lat" ]; then echo "latency: ON  ($lat)"; else echo "latency: off"; fi
  if scan_running; then echo "scan:    ON"; else echo "scan:    off"; fi

  local ready score flag firing
  ready="$(prom_value goys_detector_ready)"
  score="$(prom_value goys_anomaly_score)"
  flag="$(prom_value goys_anomaly_flag)"
  firing="$(prom_value 'count(ALERTS{alertstate="firing",source!="ml"})%20or%20vector(0)')"
  if [ "${ready:-0}" = "1" ]; then
    printf 'detector: score=%.3f flag=%s\n' "${score:-0}" "${flag:-0}"
  else
    echo "detector: warming up (baseline not trained yet)"
  fi
  echo "traditional alerts firing: ${firing:-?}"
}

main() {
  case "${1:-}:${2:-}" in
    latency:on)  latency_on "${3:-}" "${4:-}" ;;
    latency:off) latency_off ;;
    scan:on)     scan_on ;;
    scan:off)    scan_off ;;
    status:*)    show_status ;;
    *)           usage ;;
  esac
}

main "$@"
