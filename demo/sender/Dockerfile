# Small image for the Act 3 security scenario. Three roles share it:
#   - "otlp-agent": the LEGITIMATE telemetry sender (sends OTLP/HTTP, with a client certificate under mTLS)
#   - "poisoner":   the ATTACKER that injects forged telemetry (never has a certificate)
#   - scripts/certs.sh also uses it to run openssl when the host has none
# Built once (with internet) and saved in the offline tar, so nothing is installed at fair time.
FROM alpine:3.20.3

# curl = OTLP/HTTP client (JSON encoding, so no protobuf tooling is needed); openssl = certificate generation.
RUN apk add --no-cache curl openssl

COPY otlp.sh legit.sh attack.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/otlp.sh /usr/local/bin/legit.sh /usr/local/bin/attack.sh

# Containers using this image stay idle unless they set a command; act3.sh starts/stops the attack.
CMD ["sleep", "infinity"]
