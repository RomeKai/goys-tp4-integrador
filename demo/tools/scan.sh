#!/bin/sh
# Slow, repeated SYN scan of the demo network (the "attacker" behaviour of Act 2).
#   -sS      SYN ("half-open") scan: never completes the TCP handshake
#   -T2      "polite" timing template: waits 0.4 s between probes to the same host
#   -Pn -n   skip host discovery and DNS: probe the given IPs directly
#   -p 1-1024  the well-known ports
# A threshold-based IDS counts "ports per second" or "connections per second"; a scan this slow
# stays under such thresholds, but it still changes the traffic pattern a model has learned.
set -eu

TARGETS="${SCAN_TARGETS:-172.28.0.10 172.28.0.11 172.28.0.20 172.28.0.21 172.28.0.22 172.28.0.30 172.28.0.31}"
PORTS="${SCAN_PORTS:-1-1024}"
TIMING="${SCAN_TIMING:-T2}"

while true; do
  # shellcheck disable=SC2086  # TARGETS must be word-split into several IPs
  nmap -sS "-$TIMING" -Pn -n -p "$PORTS" $TARGETS >/dev/null 2>&1 || true
  sleep 5
done
