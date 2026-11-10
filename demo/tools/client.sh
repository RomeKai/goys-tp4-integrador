#!/bin/sh
# Benign background traffic: a few "users" requesting web and api at random intervals.
# Without it the demo network would be perfectly regular (only probes), and a regular baseline
# gives a model nothing to learn from. Roughly 2-3 requests per second in total.
set -eu

# Random integer in [0, $1) from the kernel's random source (busybox sh has no $RANDOM).
rand() {
  n="$(od -An -N2 -tu2 /dev/urandom | tr -d ' ')"
  echo $((n % $1))
}

while true; do
  case "$(rand 2)" in
    0) url="http://web/" ;;
    *) url="http://api/" ;;
  esac
  wget -q -T 2 -O /dev/null "$url" || true
  # 100-899 ms between requests (always three digits, so "0.NNN" is a valid fraction of a second).
  sleep "0.$((100 + $(rand 800)))"
done
