"""Anomaly detector for the Act 2 demo.

What it does, in four steps:
  1. Every INTERVAL_SECONDS it asks Prometheus for a handful of numbers (the "features").
  2. During the warm-up it only collects them: that is what "normal" looks like.
  3. When the warm-up ends it trains one IsolationForest per signal family on that normal data.
  4. From then on it scores every new sample and publishes the result on /metrics:
       goys_anomaly_score  0..1, higher = more anomalous (0.5 = "cannot tell", above 0.6 = alarm)
       goys_anomaly_flag   1 when the score stays above the alarm line for a few samples in a row
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass

import numpy as np
import requests
from prometheus_client import Gauge, start_http_server
from sklearn.ensemble import IsolationForest

log = logging.getLogger("detector")

# Averages and rates look back 30 s (6 scrapes at 5 s): smooth enough to ignore a single odd
# probe, short enough to react within the demo.
WINDOW = "30s"


@dataclass(frozen=True)
class Family:
    """A group of features that move together during one kind of incident.

    tolerance: how much a feature may wobble for normal reasons, as a fraction of its usual value
    (0.5 = +-50 %). See blur() and ACTO-2-GUIA.md for why the model needs it."""

    tolerance: float
    features: dict[str, str]  # feature name -> PromQL returning exactly one number


def probe_ms(job: str, instance: str, stat: str = "avg") -> str:
    """PromQL: a blackbox probe duration over WINDOW, in milliseconds."""
    selector = f'probe_duration_seconds{{job="{job}",instance="{instance}"}}'
    return f"1000 * {stat}_over_time({selector}[{WINDOW}])"


def web_rate(metric: str, labels: str = "") -> str:
    """PromQL: per-second rate of a counter seen by the sensor that lives inside the web container."""
    return f'sum(rate({metric}{{instance="web:9100"{labels}}}[{WINDOW}]))'


CONNECTIONS = web_rate("node_netstat_Tcp_PassiveOpens")  # completed TCP handshakes per second
RX_BYTES = web_rate("node_network_receive_bytes_total", ',device="eth0"')

# One IsolationForest per family. A forest picks features at random, so unrelated features dilute
# each other; with one forest per family each incident moves most of that forest's features.
FAMILIES: dict[str, Family] = {
    # Incident 1 (latency + jitter on api): the same slowdown seen at four places.
    # Latencies here are ~1-2 ms and wobble a lot in relative terms, hence the wide tolerance.
    "latency": Family(
        tolerance=0.5,
        features={
            "api_http_ms": probe_ms("blackbox-http", "http://api/health"),
            "api_http_jitter_ms": probe_ms("blackbox-http", "http://api/health", "stddev"),
            "api_tcp_connect_ms": probe_ms("blackbox-tcp", "api:80"),
            "api_icmp_rtt_ms": (
                "1000 * avg_over_time("
                f'probe_icmp_duration_seconds{{job="blackbox-icmp",phase="rtt",instance="api"}}[{WINDOW}])'
            ),
        },
    ),
    # Incident 2 (slow port scan): the shape of the traffic web receives, per completed connection.
    # Normal clients send ~7 packets per connection and that ratio is very stable (tight tolerance).
    # A SYN scan sends packets that never become a connection, so the ratio rises even though the
    # total volume looks ordinary.
    "traffic": Family(
        tolerance=0.05,
        features={
            "rx_packets_per_conn": f'{web_rate("node_netstat_Tcp_InSegs")} / {CONNECTIONS}',
            "tx_packets_per_conn": f'{web_rate("node_netstat_Tcp_OutSegs")} / {CONNECTIONS}',
            "rx_bytes_per_conn": f"{RX_BYTES} / {CONNECTIONS}",
        },
    ),
}


@dataclass(frozen=True)
class Config:
    """Settings read from environment variables (see docker-compose.act2.yml)."""

    prometheus_url: str = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
    # Seconds since start after which the baseline is trained (settle time included).
    warmup_seconds: float = float(os.getenv("WARMUP_SECONDS", "180"))
    # Ignored at the start: the 30 s windows are not full yet, so the numbers are not representative.
    settle_seconds: float = float(os.getenv("SETTLE_SECONDS", "30"))
    interval_seconds: float = float(os.getenv("INTERVAL_SECONDS", "5"))
    min_samples: int = int(os.getenv("MIN_SAMPLES", "20"))  # refuse to train on less data
    alarm_threshold: float = float(os.getenv("ALARM_THRESHOLD", "0.6"))
    consecutive: int = int(os.getenv("CONSECUTIVE", "3"))  # samples above the line to raise the flag
    port: int = int(os.getenv("PORT", "8000"))


def query_prometheus(base_url: str, promql: str) -> float | None:
    """Run an instant query and return its single value, or None if there is no usable data."""
    response = requests.get(
        f"{base_url}/api/v1/query", params={"query": promql}, timeout=3
    )
    response.raise_for_status()
    result = response.json()["data"]["result"]
    if not result:
        return None
    value = float(result[0]["value"][1])
    return value if math.isfinite(value) else None


def read_sample(base_url: str) -> dict[str, float] | None:
    """Read every feature of every family once. None if any is missing (e.g. Prometheus just started)."""
    sample: dict[str, float] = {}
    for family in FAMILIES.values():
        for name, promql in family.features.items():
            value = query_prometheus(base_url, promql)
            if value is None:
                log.warning("No data yet for feature %s", name)
                return None
            sample[name] = value
    return sample


def blur(data: np.ndarray, tolerance: float, copies: int = 9) -> np.ndarray:
    """Add noisy copies of the training rows: every value is multiplied by 1 + N(0, tolerance).

    An IsolationForest only knows the *range* of what it saw. Without this, a reading that is a
    hair outside that range (say 1.9 ms when training only saw up to 1.7 ms) looks exactly as
    strange as one that is 50 times larger. Blurring teaches it that small wobbles are normal."""
    rng = np.random.default_rng(42)
    noisy = [np.maximum(data * (1 + tolerance * rng.standard_normal(data.shape)), 0) for _ in range(copies)]
    return np.vstack([data, *noisy])


class FamilyModel:
    """An IsolationForest trained on the (blurred) normal data of one family."""

    def __init__(self, family: Family, normal_rows: list[dict[str, float]]) -> None:
        self.features = list(family.features)
        data = np.array([[row[name] for name in self.features] for row in normal_rows])
        # n_estimators: how many random trees vote. random_state: same result on every run.
        self.forest = IsolationForest(n_estimators=200, random_state=42)
        self.forest.fit(blur(data, family.tolerance))
        training_scores = self.score_rows(data)
        log.info(
            "Family trained on %d samples: normal scores %.3f..%.3f (%s)",
            len(data),
            training_scores.min(),
            training_scores.max(),
            ", ".join(self.features),
        )

    def score_rows(self, data: np.ndarray) -> np.ndarray:
        """sklearn returns the negative of the paper's score, so flip the sign: higher = more anomalous."""
        return -self.forest.score_samples(data)

    def score(self, sample: dict[str, float]) -> float:
        return float(self.score_rows(np.array([[sample[name] for name in self.features]]))[0])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = Config()

    score_gauge = Gauge("goys_anomaly_score", "Anomaly score, 0..1 (worst family; alarm above the threshold)")
    flag_gauge = Gauge("goys_anomaly_flag", "1 if the score stayed above the alarm line")
    threshold_gauge = Gauge("goys_anomaly_threshold", "Alarm line for goys_anomaly_score")
    ready_gauge = Gauge("goys_detector_ready", "1 once the baseline is trained, 0 while warming up")
    progress_gauge = Gauge("goys_detector_warmup_progress", "Warm-up progress, 0..1")
    family_score_gauge = Gauge("goys_family_score", "IsolationForest score of one family", ["family"])
    feature_gauge = Gauge("goys_detector_feature", "Feature values the detector reads", ["name"])

    start_http_server(cfg.port)
    threshold_gauge.set(cfg.alarm_threshold)
    log.info("Serving /metrics on :%d, warm-up %.0f s", cfg.port, cfg.warmup_seconds)

    started = time.monotonic()
    normal_rows: list[dict[str, float]] = []
    models: dict[str, FamilyModel] = {}
    above_line = 0  # consecutive samples over the alarm line

    while True:
        loop_start = time.monotonic()
        try:
            sample = read_sample(cfg.prometheus_url)
        except requests.RequestException as error:
            log.warning("Prometheus not reachable: %s", error)
            sample = None

        if sample is not None:
            for name, value in sample.items():
                feature_gauge.labels(name=name).set(value)

            if not models:
                # Warm-up: everything we see is assumed normal (after the settle time).
                if time.monotonic() - started >= cfg.settle_seconds:
                    normal_rows.append(sample)
            else:
                family_scores = {family: model.score(sample) for family, model in models.items()}
                for family, value in family_scores.items():
                    family_score_gauge.labels(family=family).set(value)
                score = max(family_scores.values())  # the worst family decides
                above_line = above_line + 1 if score > cfg.alarm_threshold else 0
                score_gauge.set(score)
                flag_gauge.set(1 if above_line >= cfg.consecutive else 0)

        if not models:
            elapsed = time.monotonic() - started
            progress_gauge.set(min(elapsed / cfg.warmup_seconds, 1.0))
            if elapsed >= cfg.warmup_seconds and len(normal_rows) >= cfg.min_samples:
                models = {name: FamilyModel(family, normal_rows) for name, family in FAMILIES.items()}
                ready_gauge.set(1)

        time.sleep(max(0.0, cfg.interval_seconds - (time.monotonic() - loop_start)))


if __name__ == "__main__":
    main()
