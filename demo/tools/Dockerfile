# Small utility image shared by two Act 2 containers:
#   - "attacker": runs a slow nmap scan (needs NET_RAW)
#   - "netem":    injects latency with `tc netem` inside api's network namespace (needs NET_ADMIN)
# It is built once (with internet) and saved in the offline tar, so nothing is installed at fair time.
FROM alpine:3.20.3

# nmap = port scanner, iproute2-tc = the `tc` command (traffic control / netem).
RUN apk add --no-cache nmap iproute2-tc

COPY scan.sh client.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/scan.sh /usr/local/bin/client.sh

# Containers using this image stay idle; inject-incident.sh starts/stops the actual work.
CMD ["sleep", "infinity"]
