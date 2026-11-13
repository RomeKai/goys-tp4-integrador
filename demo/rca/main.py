"""Root-cause explanation (RCA) service for the Act 3 demo.

What it does, in four steps:
  1. Every POLL_SECONDS it asks Prometheus whether the Act 2 detector raised its anomaly flag.
  2. On a new anomaly it gathers EVIDENCE with plain code (no AI): which signal family scored,
     how far each feature is from the baseline the detector learned, recent values, what is healthy.
  3. It sends only that evidence to a small local LLM (Ollama) and asks, in Spanish, for the probable
     cause and 2-3 next checks. The prompt forbids inventing facts.
  4. It publishes evidence + explanation as a Grafana annotation and on a read-only web page (/).
If the LLM is down or too slow, step 4 falls back (RCA_MODE, see Config):
  - live:   evidence only, marked "LLM no disponible".
  - replay: never asks the LLM; shows a REAL answer recorded earlier for the same incident family.
  - auto:   asks the LLM with a time budget; past the budget (or on failure) shows the recorded answer
            and, if the live one still arrives, replaces it. A recorded answer is ALWAYS labelled as such.
With no recording for that family, the fallback is evidence only.
"""

from __future__ import annotations

import html
import json
import logging
import math
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
from page import render_page
from replay import Replay, live_label, load_replay

log = logging.getLogger("rca")


@dataclass(frozen=True)
class Config:
    """Settings read from environment variables (see docker-compose.act3.yml)."""

    prometheus_url: str = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://ollama:11434")
    model: str = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    grafana_url: str = os.getenv("GRAFANA_URL", "http://grafana:3000")
    grafana_user: str = os.getenv("GRAFANA_USER", "admin")
    grafana_password: str = os.getenv("GRAFANA_PASSWORD", "admin")
    dashboard_uid: str = os.getenv("DASHBOARD_UID", "act2-deteccion-anomalias")
    poll_seconds: float = float(os.getenv("POLL_SECONDS", "5"))
    # Wait after the flag rises so the 30 s windows of the detector are fuller when we measure.
    evidence_delay: float = float(os.getenv("EVIDENCE_DELAY_SECONDS", "5"))
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))  # hard cap for one explanation
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "220"))  # cap on generated tokens
    threads: int = int(os.getenv("LLM_THREADS", "4"))  # CPU threads for inference
    port: int = int(os.getenv("PORT", "8085"))
    # live = LLM only; replay = recorded answer only (the LLM is never called); auto = LLM with a budget, then recorded.
    mode: str = os.getenv("RCA_MODE", "auto")
    live_budget: float = float(os.getenv("RCA_LIVE_BUDGET_SECONDS", "30"))  # auto: wait this long for the LLM
    replay_dir: Path = Path(os.getenv("RCA_REPLAY_DIR", str(Path(__file__).parent / "replay")))


MODES = ("live", "replay", "auto")


# --- Domain knowledge fixed by us (not measured, not generated) ---------------------------------
# Which service each signal family describes. The detector measures api for latency, web for traffic.
FAMILY_TARGET = {"latency": "api", "traffic": "web"}
FAMILY_LABEL = {"latency": "latencia", "traffic": "tráfico"}
# What each feature means; it is shown with the evidence and sent to the LLM as a glossary.
GLOSSARY = {
    "api_http_ms": "tiempo de respuesta HTTP de api, promedio de 30 s, en ms",
    "api_http_jitter_ms": "variación de ese tiempo de respuesta, en ms",
    "api_tcp_connect_ms": "tiempo para abrir una conexión TCP a api, en ms",
    "api_icmp_rtt_ms": "tiempo de ida y vuelta de un ping a api, en ms",
    "rx_packets_per_conn": "paquetes TCP recibidos por web por cada conexión completada",
    "tx_packets_per_conn": "paquetes TCP enviados por web por cada conexión completada",
    "rx_bytes_per_conn": "bytes recibidos por web por cada conexión completada",
}

SYSTEM_PROMPT = """Eres un asistente de operaciones de red. Recibes una EVIDENCIA medida por un detector de anomalías.
Reglas:
- Usa SOLO la EVIDENCIA real (la última). El ejemplo es de otro caso: copia su formato, nunca su contenido.
- No inventes cifras, servicios, herramientas ni eventos. No cambies el sentido de una señal: si subió, no digas que bajó.
- "normal" es el promedio aprendido de esa señal, NO un límite ni un umbral: no digas que lo "excedió" ni que superó un "límite".
- Habla de causa PROBABLE, nunca de certeza. Si la evidencia no alcanza, escribe "causa no determinada".
- Responde en español con un JSON: "causa_probable" (dos frases; cada cifra va junto al nombre exacto de su señal) y "verificaciones" (tres acciones que una persona puede hacer)."""

# One worked example about a FICTITIOUS, abstract case. Small models ignore a described format but
# copy a demonstrated one; the abstract names keep them from borrowing real-sounding content (a first
# version with a "cache" example made the model talk about caches). Unrelated to api/web on purpose.
# Both signals RISE here: when the example had one falling, the model copied "bajó" onto the first
# signal of every real case, even when it rose.
EXAMPLE_EVIDENCE = """Servicio afectado: (ejemplo).
Señales que se desviaron:
  - senal_a (cantidad de elementos en espera): ahora 180, normal 12 (x15.0)
  - senal_b (tiempo de proceso de cada elemento, en ms): ahora 95, normal 20 (x4.8)
Observaciones:
  - 2 de 2 señales se desviaron a la vez.
  - Ninguna sonda cayó y ninguna alerta por umbral está activa."""
EXAMPLE_ANSWER = json.dumps(
    {
        "causa_probable": "senal_a subió a 180 (normal 12) y senal_b subió a 95 (normal 20). "
        "Eso sugiere un cambio de comportamiento, pero la evidencia no alcanza para nombrar el motivo.",
        "verificaciones": [
            "Comparar senal_a y senal_b con su historial reciente.",
            "Revisar si hubo un cambio en la carga o en la configuración del servicio afectado.",
            "Volver a medir ambas señales en unos minutos para ver si se normalizan.",
        ],
    },
    ensure_ascii=False,
)

# Ollama "structured output": the model can only produce JSON that fits this schema (the sampler is
# constrained), so the answer is always complete and bounded. Without it a 1B model often rambled
# and ran out of tokens before writing the checks.
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "causa_probable": {"type": "string", "maxLength": 380},
        "verificaciones": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "string", "maxLength": 130}},
    },
    "required": ["causa_probable", "verificaciones"],
}


def user_message(evidence_text: str) -> str:
    return f"EVIDENCIA:\n{evidence_text}\n\nExplica la causa probable."


def build_messages(evidence_text: str) -> list[dict[str, str]]:
    """Chat sent to the LLM: rules, one worked example, then the real evidence."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message(EXAMPLE_EVIDENCE)},
        {"role": "assistant", "content": EXAMPLE_ANSWER},
        {"role": "user", "content": user_message(evidence_text)},
    ]


# --- Prometheus access ---------------------------------------------------------------------------
def prom_query(cfg: Config, promql: str) -> list[tuple[dict[str, str], float]]:
    """Instant query -> list of (labels, value). NaN/Inf values are dropped."""
    response = requests.get(f"{cfg.prometheus_url}/api/v1/query", params={"query": promql}, timeout=3)
    response.raise_for_status()
    rows = []
    for item in response.json()["data"]["result"]:
        value = float(item["value"][1])
        if math.isfinite(value):
            rows.append((item["metric"], value))
    return rows


def prom_scalar(cfg: Config, promql: str, default: float = 0.0) -> float:
    rows = prom_query(cfg, promql)
    return rows[0][1] if rows else default


def prom_history(cfg: Config, promql: str, seconds: int = 120, step: int = 20) -> list[float]:
    """Range query for ONE series -> its last values, oldest first."""
    end = time.time()
    response = requests.get(
        f"{cfg.prometheus_url}/api/v1/query_range",
        params={"query": promql, "start": end - seconds, "end": end, "step": step},
        timeout=3,
    )
    response.raise_for_status()
    result = response.json()["data"]["result"]
    return [float(v) for _, v in result[0]["values"]] if result else []


# --- Step 2: evidence (deterministic) ---------------------------------------------------------------
@dataclass
class Deviation:
    family: str
    name: str
    now: float
    mean: float
    std: float

    @property
    def scale(self) -> float:
        """Size of one 'normal wobble'. It never drops below 5 % of the mean, otherwise a nearly
        constant feature would give absurd distances."""
        return max(self.std, 0.05 * abs(self.mean), 1e-6)

    @property
    def z(self) -> float:
        """Distance from the baseline, in normal wobbles."""
        return (self.now - self.mean) / self.scale


@dataclass
class Evidence:
    score: float
    threshold: float
    family_scores: dict[str, float]
    flagged: list[str]  # families above the alarm line (the worst first)
    deviations: list[Deviation]  # features of the flagged families, largest |z| first
    earlier: dict[str, float]  # value of the most deviating features ~40 s ago
    onset_seconds: int | None  # roughly how long ago the signals left their normal range
    classic_alerts: int
    probes_down: int
    probes_total: int
    observations: list[str] = field(default_factory=list)  # fixed rules applied to the numbers (no AI)
    text: str = ""  # the same evidence as readable Spanish text (what the LLM and the page get)


def fmt(value: float) -> str:
    return f"{value:.1f}" if abs(value) >= 10 else f"{value:.2f}"


def collect_evidence(cfg: Config) -> Evidence:
    """Read everything we know about the anomaly straight from Prometheus."""
    score = prom_scalar(cfg, "goys_anomaly_score")
    threshold = prom_scalar(cfg, "goys_anomaly_threshold", 0.6)
    family_scores = {m["family"]: v for m, v in prom_query(cfg, "goys_family_score")}
    ranked = sorted(family_scores, key=lambda f: family_scores[f], reverse=True)
    flagged = [f for f in ranked if family_scores[f] > threshold] or ranked[:1]

    now = {(m["family"], m["name"]): v for m, v in prom_query(cfg, "goys_detector_feature")}
    mean = {(m["family"], m["name"]): v for m, v in prom_query(cfg, "goys_detector_baseline_mean")}
    std = {(m["family"], m["name"]): v for m, v in prom_query(cfg, "goys_detector_baseline_std")}
    deviations = [
        Deviation(family, name, now[(family, name)], mean[(family, name)], std.get((family, name), 0.0))
        for (family, name) in now
        if family in flagged and (family, name) in mean
    ]
    deviations.sort(key=lambda d: abs(d.z), reverse=True)

    # One sample every 20 s over 2 minutes, oldest first, for the most deviating features.
    history = {d.name: prom_history(cfg, f'goys_detector_feature{{name="{d.name}"}}') for d in deviations[:3]}
    earlier = {name: values[-3] for name, values in history.items() if len(values) >= 3}
    onset_seconds = estimate_onset(deviations[0], history[deviations[0].name]) if deviations else None

    evidence = Evidence(
        score=score,
        threshold=threshold,
        family_scores=family_scores,
        flagged=flagged,
        deviations=deviations,
        earlier=earlier,
        onset_seconds=onset_seconds,
        classic_alerts=int(prom_scalar(cfg, 'count(ALERTS{alertstate="firing",source!="ml"}) or vector(0)')),
        probes_down=int(prom_scalar(cfg, "count(probe_success == 0) or vector(0)")),
        probes_total=int(prom_scalar(cfg, "count(probe_success)")),
    )
    evidence.observations = observe(evidence)
    evidence.text = format_evidence(evidence)
    return evidence


def observe(ev: Evidence) -> list[str]:
    """Plain if-rules over the measured numbers. They state what the data shows, not what caused it.
    Keeping them in code (not in the LLM) makes them testable and always correct."""
    moved = {d.name: d for d in ev.deviations if abs(d.z) > 3}  # outside the normal wobble
    notes = []
    if "latency" in ev.flagged:
        latency = [d for d in ev.deviations if d.family == "latency"]
        notes.append(f"{sum(d.name in moved for d in latency)} de {len(latency)} señales de latencia de api se desviaron a la vez.")
        if "api_icmp_rtt_ms" in moved:
            notes.append("El ping (ICMP) también subió: el retraso existe por debajo de HTTP, no solo en la aplicación web.")
        elif "api_http_ms" in moved:
            notes.append("HTTP subió pero el ping (ICMP) no: el retraso parece estar en la aplicación.")
        if "api_http_jitter_ms" in moved:
            notes.append("El jitter aumentó: los tiempos de respuesta son más irregulares, no solo más altos.")
    if "traffic" in ev.flagged:
        packets = moved.get("rx_packets_per_conn")
        if packets and packets.now > packets.mean:
            notes.append("web recibe más paquetes por cada conexión completada: "
                         "llegan paquetes que no terminan en una conexión completa (por ejemplo, intentos de conexión incompletos).")
        elif moved:
            notes.append("La forma del tráfico hacia web cambió respecto de lo aprendido.")
    if ev.classic_alerts == 0 and ev.probes_down == 0:
        notes.append("Ninguna sonda cayó y ninguna alerta por umbral está activa: los servicios siguen respondiendo.")
    return notes


def estimate_onset(top: Deviation, values: list[float]) -> int | None:
    """Seconds since the top feature left its normal range: 20 s per trailing sample beyond 3 wobbles."""
    outside = 0
    for value in reversed(values):
        if abs(value - top.mean) / top.scale <= 3:
            break
        outside += 1
    return outside * 20 if outside else None


def format_evidence(ev: Evidence) -> str:
    """Render the evidence as plain Spanish text. No interpretation here: only measured values."""
    scores = " | ".join(f"{FAMILY_LABEL.get(f, f)} {ev.family_scores[f]:.2f}" for f in ev.family_scores)
    targets = ", ".join(FAMILY_TARGET.get(f, "?") for f in ev.flagged)
    families = ", ".join(FAMILY_LABEL.get(f, f) for f in ev.flagged)
    lines = [
        f"Detector ML: puntaje {ev.score:.2f} (línea de alarma {ev.threshold:.2f}).",
        f"Puntaje por familia: {scores}. Familia que disparó: {families}.",
        f"Servicio afectado: {targets}.",
        "Señales que se desviaron (ahora frente a lo normal aprendido en el calentamiento):",
    ]
    for d in ev.deviations:
        ratio = d.now / d.mean if d.mean else float("inf")
        line = f"  - {d.name} ({GLOSSARY.get(d.name, 'sin descripción')}): ahora {fmt(d.now)}, normal {fmt(d.mean)} (x{ratio:.1f})"
        if d.name in ev.earlier:
            line += f", hace 40 s {fmt(ev.earlier[d.name])}"
        lines.append(line)
    if ev.onset_seconds:
        ago = "más de 2 minutos" if ev.onset_seconds >= 120 else f"unos {ev.onset_seconds} s"
        lines.append(f"Inicio: las señales estaban en su rango normal hasta hace {ago}.")
    if ev.observations:
        lines.append("Observaciones (reglas fijas sobre las cifras, sin IA):")
        lines.extend(f"  - {note}" for note in ev.observations)
    lines.append(f"Contexto: alertas por umbral activas: {ev.classic_alerts}; sondas caídas: {ev.probes_down} de {ev.probes_total}.")
    return "\n".join(lines)


# --- Step 3: ask the LLM -------------------------------------------------------------------------
class LlmError(Exception):
    """The LLM could not produce an explanation (down, model missing, too slow)."""


def format_answer(raw_json: str) -> str:
    """The constrained JSON from the LLM -> the text people read."""
    answer = json.loads(raw_json)
    cause = answer["causa_probable"].strip()
    if not cause.endswith("."):  # the length cap in the schema can cut mid-sentence: keep whole sentences
        cause = cause.rsplit(". ", 1)[0] + "." if ". " in cause else cause + "…"
    answer["causa_probable"] = cause
    checks = "\n".join(f"- {check}" for check in answer["verificaciones"])
    return f"Causa probable: {answer['causa_probable']}\nPróximas verificaciones:\n{checks}"


def ask_llm(cfg: Config, evidence_text: str, on_text, seed: int = 42) -> str:
    """Stream the explanation from Ollama. on_text(partial) is called as tokens arrive (so a failure
    still leaves the partial text visible). Raises LlmError on any failure."""
    body = {
        "model": cfg.model,
        "stream": True,
        "keep_alive": "30m",  # keep the model in RAM between incidents
        "format": ANSWER_SCHEMA,
        "messages": build_messages(evidence_text),
        # Low temperature: we want the same facts every time, not creativity.
        "options": {"temperature": 0.2, "seed": seed, "num_predict": cfg.max_tokens, "num_ctx": 2048, "num_thread": cfg.threads},
    }
    text = ""
    deadline = time.monotonic() + cfg.llm_timeout
    try:
        with requests.post(f"{cfg.ollama_url}/api/chat", json=body, stream=True, timeout=(3, cfg.llm_timeout)) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                text += chunk.get("message", {}).get("content", "")
                on_text(text)
                if chunk.get("done"):
                    return format_answer(text)
                if time.monotonic() > deadline:
                    raise TimeoutError(f"más de {cfg.llm_timeout:.0f} s")
    except requests.ConnectionError as error:
        raise LlmError("no se pudo conectar con Ollama (¿está apagado?)") from error
    except (requests.Timeout, TimeoutError) as error:
        raise LlmError(f"el LLM tardó más de {cfg.llm_timeout:.0f} s") from error
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as error:
        raise LlmError("el LLM devolvió una respuesta incompleta") from error
    except requests.RequestException as error:
        raise LlmError(f"{type(error).__name__}: {error}") from error
    raise LlmError("el LLM cortó la respuesta antes de terminar")


NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


# Words that only exist in the worked example of the prompt. If they show up in an explanation, the
# model copied the example instead of reading the evidence.
EXAMPLE_TERMS = ("senal_a", "senal_b", "(ejemplo)")

# The evidence never defines a per-signal limit; "normal" is the learned average. A small model likes
# to call it a "límite de tolerancia" and say the signal "exceeded" it, which is invented.
INVENTED_LIMIT_TERMS = ("límite", "limite", "tolerancia")


UP_WORDS = ("subi", "sube", "aument", "crec", "elev", "increment")
DOWN_WORDS = ("baj", "disminu", "descend", "redu", "cay")
SIGNAL_NAME = re.compile(r"[a-z]+(?:_[a-z]+)+")  # e.g. rx_packets_per_conn


def close(value: float, reference: float, tolerance: float = 0.06) -> bool:
    """Equal within rounding (the LLM may write 98 for 97.9)."""
    return abs(value - reference) <= max(tolerance * abs(reference), 0.06)


def to_number(token: str) -> float | None:
    """A figure worth checking, or None for list numbering and 'two or three checks'."""
    value = float(token.replace(",", "."))
    return None if value <= 3 and value == int(value) else value


def grounding_warnings(explanation: str, ev: Evidence) -> list[str]:
    """Cheap hallucination alarms, in Spanish. They catch (1) figures that are not in the evidence,
    (2) a figure written next to the wrong signal name, and (3) words copied from the prompt's example, (4) a signal family that did not fire.
    They do NOT prove the text is right: a sentence can use true figures and still claim something false."""
    warnings = []
    # The score line names every family, fired or not: leave it out when checking what the evidence says.
    facts = "\n".join(line for line in ev.text.splitlines() if not line.startswith("Puntaje por familia"))
    figures = {token: to_number(token) for token in NUMBER.findall(facts)}
    allowed = [v for v in figures.values() if v is not None]
    unsupported = []
    for token in NUMBER.findall(explanation):
        value = to_number(token)
        if value is not None and not any(close(value, a) for a in allowed):
            unsupported.append(token)
    if unsupported:
        warnings.append("cifras sin respaldo en la evidencia: " + ", ".join(unsupported))

    # (2) For each signal name the LLM mentions, the figures right after it must belong to that signal.
    values = {d.name: [d.now, d.mean, d.now / d.mean if d.mean else 0.0, ev.earlier.get(d.name)] for d in ev.deviations}
    mentions = [m for m in SIGNAL_NAME.finditer(explanation) if m.group() in values]
    wrong, reversed_direction = [], []
    by_name = {d.name: d for d in ev.deviations}
    for i, mention in enumerate(mentions):
        end = mentions[i + 1].start() if i + 1 < len(mentions) else len(explanation)
        sentence = re.split(r"\.\s", explanation[mention.end():end])[0]  # stop at the end of the sentence
        for token in NUMBER.findall(sentence):
            value = to_number(token)
            own = [v for v in values[mention.group()] if v is not None]
            if value is not None and not any(close(value, v, 0.03) for v in own):  # stricter: neighbours differ little
                wrong.append(f"{mention.group()} {token}")
        # Direction: "bajó" next to a signal that went up (or the other way round).
        near = explanation[mention.end() : min(mention.end() + 45, end)].lower()  # never read into the next signal's words
        rose = by_name[mention.group()].now > by_name[mention.group()].mean
        said_up, said_down = any(w in near for w in UP_WORDS), any(w in near for w in DOWN_WORDS)
        if (rose and said_down and not said_up) or (not rose and said_up and not said_down):
            reversed_direction.append(mention.group())
    if wrong:
        warnings.append("cifras junto a la señal equivocada: " + ", ".join(wrong))
    if reversed_direction:
        warnings.append("sentido invertido (dice que bajó lo que subió, o al revés): " + ", ".join(reversed_direction))

    lowered, evidence_lowered = explanation.lower(), facts.lower()
    limits = [t for t in INVENTED_LIMIT_TERMS if t in lowered and t not in evidence_lowered]
    if limits:
        warnings.append("habla de un límite que la evidencia no define (\"normal\" es el promedio aprendido, no un tope)")
    copied = [t for t in EXAMPLE_TERMS if t in lowered and t not in evidence_lowered]
    if copied:
        warnings.append("términos copiados del ejemplo del prompt, no de la evidencia: " + ", ".join(copied))
    # (4) A family that did not fire is only named in the score line, so naming it is not grounded.
    off_family = [FAMILY_LABEL.get(f, f) for f in ev.family_scores
                  if f not in ev.flagged and FAMILY_LABEL.get(f, f).lower() in lowered and FAMILY_LABEL.get(f, f).lower() not in evidence_lowered]
    if off_family:
        warnings.append("menciona " + ", ".join(off_family) + ", que no está en la evidencia")
    return warnings


# --- Shared state --------------------------------------------------------------------------------
@dataclass
class Incident:
    id: int
    detected_at: float
    status: str = "analizando"  # analizando | listo (live answer) | pregrabada (recorded answer) | llm_no_disponible
    family: str = ""  # signal family that fired first (latency, traffic): selects the recorded answer
    evidence: Evidence | None = None
    explanation: str = ""  # final readable text of the LIVE answer
    replay: Replay | None = None  # the recorded answer shown while status == "pregrabada"
    replay_reason: str = ""  # why the recorded answer is shown instead of a live one
    live_pending: bool = False  # recorded answer shown while the live attempt is still running
    partial: str = ""  # raw text received before a failure
    llm_error: str = ""
    llm_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)  # grounding alarms, see grounding_warnings()
    annotation_id: int | None = None
    grafana_note: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "detected_at": datetime.fromtimestamp(self.detected_at, timezone.utc).isoformat(),
            "status": self.status,
            "family": self.family,
            "evidence": self.evidence.text if self.evidence else "",
            "explanation": self.explanation,
            "replay": {**asdict(self.replay), "label": self.replay.label(), "reason": self.replay_reason} if self.replay else None,
            "llm_error": self.llm_error,
            "llm_seconds": round(self.llm_seconds, 1),
            "warnings": self.warnings,
            "grafana": self.grafana_note,
        }


class State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.incidents: list[Incident] = []  # newest first
        self.llm_status = "iniciando"  # shown in the page header

    def busy(self) -> bool:
        with self.lock:
            return any(i.status == "analizando" or i.live_pending for i in self.incidents)

    def open_incident(self) -> Incident:
        with self.lock:
            incident = Incident(id=len(self.incidents) + 1, detected_at=time.time())
            self.incidents.insert(0, incident)
            return incident


# --- Step 4a: Grafana annotation -------------------------------------------------------------------
def annotation_text(headline: str, detail: str = "") -> str:
    """Annotation body. Grafana renders a safe subset of HTML, so <br> gives line breaks."""
    parts = [f"<b>{html.escape(headline)}</b>"]
    if detail:
        parts.append(html.escape(detail).replace("\n", "<br>"))
    return "<br>".join(parts)


def grafana_annotate(cfg: Config, incident: Incident, text: str) -> None:
    """Create the annotation on first call, update it afterwards. Never raises: Grafana is optional."""
    auth = (cfg.grafana_user, cfg.grafana_password)
    try:
        if incident.annotation_id is None:
            payload = {"dashboardUID": cfg.dashboard_uid, "time": int(incident.detected_at * 1000), "tags": ["rca"], "text": text}
            response = requests.post(f"{cfg.grafana_url}/api/annotations", json=payload, auth=auth, timeout=5)
            response.raise_for_status()
            incident.annotation_id = response.json()["id"]
        else:
            payload = {"text": text, "tags": ["rca"]}
            response = requests.patch(
                f"{cfg.grafana_url}/api/annotations/{incident.annotation_id}", json=payload, auth=auth, timeout=5
            )
            response.raise_for_status()
        incident.grafana_note = "anotación publicada en Grafana"
    except requests.RequestException as error:
        incident.grafana_note = f"no se pudo anotar en Grafana ({type(error).__name__})"
        log.warning("Grafana annotation failed: %s", error)


# --- One incident, start to finish -----------------------------------------------------------------
@dataclass
class LiveResult:
    """Outcome of the live LLM attempt. The worker thread fills it; analyze() reads it after the thread ends."""

    text: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    seconds: float = 0.0


def run_live(cfg: Config, incident: Incident, evidence: Evidence, result: LiveResult) -> None:
    """Ask the LLM (with one retry) and store what came back. Never raises."""

    def keep_partial(raw: str) -> None:  # raw JSON so far; only shown if the LLM fails midway
        incident.partial = raw

    started = time.monotonic()
    try:
        # A 1B model sometimes flips a direction or misplaces a figure. The checks catch that, so
        # try once more with another seed and keep the cleaner answer (the warning stays if both fail).
        best = None
        for seed in (42, 7):
            try:
                text = ask_llm(cfg, evidence.text, keep_partial, seed=seed)
            except Exception as error:  # noqa: BLE001
                if best is None:
                    raise
                log.warning("Incident %d: retry with seed %d failed (%r), keeping the first answer", incident.id, seed, error)
                break
            found = grounding_warnings(text, evidence)
            if best is None or len(found) < len(best[1]):
                best = (text, found)
            if not found:
                break
            log.info("Incident %d: attempt with seed %d had warnings: %s", incident.id, seed, found)
        result.text, result.warnings = best
    except LlmError as error:
        result.error = str(error)
    except Exception as error:  # noqa: BLE001 (the worker must never die silently: analyze() reads result.error)
        log.exception("Incident %d: unexpected error in the live attempt", incident.id)
        result.error = repr(error)
    result.seconds = time.monotonic() - started


def annotation_for(cfg: Config, incident: Incident) -> str:
    """The Grafana text for the incident's current state. The label always says live or pre-recorded."""
    evidence = incident.evidence
    targets = ", ".join(FAMILY_TARGET.get(f, "?") for f in evidence.flagged)
    if incident.status == "listo":
        headline = f"Anomalía en {targets}: {live_label(cfg.model)} ({incident.llm_seconds:.0f} s)"
        detail = incident.explanation.strip()
        if incident.warnings:
            detail += "\nAtención: " + "; ".join(incident.warnings)
    elif incident.status == "pregrabada":
        replay = incident.replay
        headline = f"Anomalía en {targets}: {replay.label()} ({incident.replay_reason})"
        detail = replay.explanation.strip()
        if replay.warnings:
            detail += "\nAtención (en la respuesta original): " + "; ".join(replay.warnings)
        detail += "\n\nEvidencia de ESTE incidente (medida ahora; las cifras del texto pregrabado son las del incidente original):\n"
        detail += evidence.text
    else:
        headline = f"Anomalía en {targets}: LLM no disponible, solo evidencia"
        detail = evidence.text.split("Señales que se desviaron")[0].strip()
    return annotation_text(headline, detail)


def show_replay(incident: Incident, replay: Replay, reason: str) -> None:
    incident.replay, incident.replay_reason, incident.status = replay, reason, "pregrabada"


def analyze(cfg: Config, state: State, incident: Incident) -> None:
    grafana_annotate(cfg, incident, annotation_text("Anomalía detectada: analizando causa..."))
    time.sleep(cfg.evidence_delay)
    try:
        incident.evidence = collect_evidence(cfg)
    except (requests.RequestException, KeyError, ValueError) as error:
        incident.status = "llm_no_disponible"
        incident.llm_error = f"No se pudo reunir la evidencia: {error}"
        log.exception("Evidence collection failed")
        grafana_annotate(cfg, incident, annotation_text("Anomalía: no se pudo reunir la evidencia", str(error)))
        return
    evidence = incident.evidence
    incident.family = evidence.flagged[0] if evidence.flagged else ""
    replay = None if cfg.mode == "live" else load_replay(cfg.replay_dir, incident.family)

    if cfg.mode == "replay":
        log.info("Incident %d: replay mode, the LLM is not called (recorded answer: %s)", incident.id, "yes" if replay else "none")
        if replay:
            show_replay(incident, replay, "modo replay, no se consulta al LLM")
        else:
            incident.status, incident.llm_error = "llm_no_disponible", f"modo replay y no hay respuesta pregrabada para '{incident.family}'"
        grafana_annotate(cfg, incident, annotation_for(cfg, incident))
        return

    result = LiveResult()
    worker = threading.Thread(target=run_live, args=(cfg, incident, evidence, result), daemon=True)
    worker.start()
    # Auto with a recording at hand: wait only the budget. Otherwise wait for the LLM (bounded by llm_timeout).
    worker.join(cfg.live_budget if cfg.mode == "auto" and replay else None)
    if worker.is_alive():
        log.info("Incident %d: no live answer after %.0f s, showing the recorded one", incident.id, cfg.live_budget)
        incident.live_pending = True  # before show_replay: busy() must never be False while the worker runs
        show_replay(incident, replay, f"el LLM no respondió en {cfg.live_budget:.0f} s")
        grafana_annotate(cfg, incident, annotation_for(cfg, incident))
        worker.join()  # bounded: ask_llm gives up after llm_timeout
        incident.live_pending = False

    incident.llm_seconds = result.seconds
    if not result.error and not result.text:  # never publish "listo" with nothing to show
        result.error = "el LLM devolvió una respuesta vacía"
    if result.error:
        state.llm_status = f"con problemas: {result.error}"
        log.warning("LLM unavailable: %s", result.error)
        if incident.status != "pregrabada":  # nothing shown yet: the recording if there is one, else evidence only
            if replay:
                show_replay(incident, replay, f"el LLM falló: {result.error}")
            else:
                incident.status, incident.llm_error = "llm_no_disponible", result.error
    else:
        incident.explanation, incident.warnings = result.text, result.warnings
        incident.status, incident.replay, incident.replay_reason = "listo", None, ""  # live replaces the recording
        state.llm_status = f"listo ({cfg.model})"
    grafana_annotate(cfg, incident, annotation_for(cfg, incident))
    log.info("Incident %d finished: %s in %.1f s", incident.id, incident.status, incident.llm_seconds)


# --- Step 1: watch the detector ----------------------------------------------------------------------
def monitor(cfg: Config, state: State) -> None:
    """Open one incident per anomaly episode (the flag going from 0 to 1). A different family taking
    over inside the same episode is NOT a new incident: while an incident is being reverted the flag
    stays up for ~40 s and the top family flips, which would trigger a useless second explanation."""
    episode_open = False
    while True:
        try:
            flag = prom_scalar(cfg, "goys_anomaly_flag")
            if flag >= 1:
                scores = {m["family"]: v for m, v in prom_query(cfg, "goys_family_score")}
                family = max(scores, key=lambda f: scores[f]) if scores else ""
                if not episode_open and not state.busy():
                    episode_open = True
                    incident = state.open_incident()
                    log.info("Anomaly detected (family=%s), opening incident %d", family, incident.id)
                    threading.Thread(target=analyze, args=(cfg, state, incident), daemon=True).start()
            else:
                episode_open = False
        except (requests.RequestException, KeyError, ValueError) as error:
            log.warning("Cannot read the detector: %s", error)
        time.sleep(cfg.poll_seconds)


def warm_up_llm(cfg: Config, state: State) -> None:
    """Load the model into RAM at startup so the first explanation does not pay the loading time."""
    while True:
        try:
            response = requests.post(
                f"{cfg.ollama_url}/api/generate", json={"model": cfg.model, "prompt": "", "keep_alive": "30m"}, timeout=120
            )
            if response.status_code == 404:
                state.llm_status = f"modelo {cfg.model} no descargado (ejecutar scripts/pull-model.sh)"
            else:
                response.raise_for_status()
                state.llm_status = f"listo ({cfg.model})"
                return
        except requests.RequestException:
            state.llm_status = "no disponible (Ollama no responde)"
        time.sleep(10)


# --- Step 4b: read-only web page (HTML lives in page.py) ---------------------------------------------
def page_html(cfg: Config, state: State) -> str:
    with state.lock:
        incidents = list(state.incidents)
    return render_page(cfg.model, state.llm_status, cfg.mode, incidents, lambda text: build_messages(text))


def has_cut_check(explanation: str) -> bool:
    """True if a next-check line stops mid-sentence (the length cap in ANSWER_SCHEMA can cut it)."""
    return any(not line.rstrip().endswith((".", "!", "?")) for line in explanation.splitlines() if line.startswith("- "))


def off_family_mentions(explanation: str, ev: Evidence) -> int:
    """How often the text names a signal family that did NOT fire (e.g. "latencia" in a traffic incident).
    The grounding checks miss it because the family scores line is part of the evidence text."""
    lowered = explanation.lower()
    return sum(lowered.count(FAMILY_LABEL.get(f, f)) for f in ev.family_scores if f not in ev.flagged)


def record_rank(incident: Incident) -> tuple[int, bool, int]:
    """Lower is cleaner: grounding warnings, then a check cut mid-sentence, then mentions of a family that did not fire."""
    return (len(incident.warnings), has_cut_check(incident.explanation), off_family_mentions(incident.explanation, incident.evidence))


def replay_record(cfg: Config, state: State, family: str) -> dict | None:
    """The best LIVE answer so far for this family, in the replay file format (None if there is none).
    Best = lowest record_rank(), the newest among equals. `act3.sh record` saves it on the host:
    the container only mounts the replay folder read-only."""
    with state.lock:
        live = [i for i in state.incidents if i.family == family and i.status == "listo" and i.evidence]  # newest first
    if not live:
        return None
    best = min(live, key=record_rank)  # min() keeps the first (newest) of equals
    return {
        "family": family,
        "explanation": best.explanation.strip(),
        "evidence": best.evidence.text,
        "model": cfg.model,
        "generated_at": datetime.fromtimestamp(best.detected_at, timezone.utc).isoformat(timespec="seconds"),
        "llm_seconds": round(best.llm_seconds, 1),
        "warnings": best.warnings,
    }


def make_handler(cfg: Config, state: State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (name fixed by http.server)
            if self.path == "/":
                body, kind = page_html(cfg, state).encode(), "text/html; charset=utf-8"
            elif self.path == "/api/incidents":
                with state.lock:
                    body = json.dumps([i.as_dict() for i in state.incidents], ensure_ascii=False).encode()
                kind = "application/json; charset=utf-8"
            elif self.path.startswith("/api/replay/"):
                record = replay_record(cfg, state, self.path.removeprefix("/api/replay/"))
                if record is None:
                    self.send_error(404, "no live answer recorded for that family yet")
                    return
                body = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode()
                kind = "application/json; charset=utf-8"
            elif self.path == "/health":
                body, kind = b"ok", "text/plain"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # silence per-request logs
            pass

    return Handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = Config()
    if cfg.mode not in MODES:
        log.warning("RCA_MODE=%r is not one of %s: using 'auto'", cfg.mode, MODES)
        cfg = replace(cfg, mode="auto")
    state = State()
    if cfg.mode == "replay":
        state.llm_status = "no se usa (modo replay)"  # replay never touches Ollama, not even to warm it up
    else:
        threading.Thread(target=warm_up_llm, args=(cfg, state), daemon=True).start()
    threading.Thread(target=monitor, args=(cfg, state), daemon=True).start()
    log.info("Serving page on :%d, mode %s, model %s, LLM timeout %.0f s, live budget %.0f s, replay dir %s",
             cfg.port, cfg.mode, cfg.model, cfg.llm_timeout, cfg.live_budget, cfg.replay_dir)
    ThreadingHTTPServer(("0.0.0.0", cfg.port), make_handler(cfg, state)).serve_forever()


if __name__ == "__main__":
    main()
