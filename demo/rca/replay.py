"""Pre-recorded explanations for the RCA service (the fallback when the live LLM is slow or down).

A replay file holds a REAL answer the same model gave to an earlier incident of the same family
(latency, traffic), together with the evidence that answer was based on. It is recorded with
`bash scripts/act3.sh record` and read here. Whoever shows it must always label it as pre-recorded.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

log = logging.getLogger("rca")

FAMILY_NAME = re.compile(r"[a-z_]+")  # the family becomes a file name: never trust it blindly


@dataclass(frozen=True)
class Replay:
    family: str
    explanation: str  # the readable text the model produced
    evidence: str  # the evidence of the ORIGINAL incident (its figures are the ones the text cites)
    model: str
    generated_at: str  # ISO 8601, UTC
    llm_seconds: float
    warnings: tuple[str, ...]  # grounding alarms the original answer had (empty = clean)

    def label(self) -> str:
        """The honest one-line description shown next to a replayed answer (page and Grafana)."""
        return f"Respuesta pregrabada — generada por {self.model} el {self.generated_date()} ante un incidente del mismo tipo"

    def generated_date(self) -> str:
        try:
            return datetime.fromisoformat(self.generated_at).strftime("%d/%m/%Y %H:%M UTC")
        except ValueError:
            return self.generated_at


def live_label(model: str) -> str:
    return f"Respuesta en vivo — generada por {model} durante este incidente"


def load_replay(directory: Path, family: str) -> Replay | None:
    """The recorded answer for this family, or None when there is none (or the file is unusable)."""
    if not FAMILY_NAME.fullmatch(family):
        return None
    path = directory / f"{family}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        replay = Replay(
            family=data["family"],
            explanation=data["explanation"],
            evidence=data["evidence"],
            model=data["model"],
            generated_at=data["generated_at"],
            llm_seconds=float(data["llm_seconds"]),
            warnings=tuple(data.get("warnings", [])),
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        log.warning("Ignoring unusable replay file %s: %s", path, error)
        return None
    # The page renders these with html.escape()/strftime: a wrong type would crash it, a wrong family would mislead.
    strings = (replay.explanation, replay.evidence, replay.model, replay.generated_at)
    if not all(isinstance(value, str) for value in strings) or not replay.explanation.strip():
        log.warning("Ignoring replay file %s: explanation, evidence, model and generated_at must be non-empty text", path)
        return None
    if replay.family != family:
        log.warning("Ignoring replay file %s: it holds family %r, expected %r", path, replay.family, family)
        return None
    if not all(isinstance(w, str) for w in replay.warnings):
        log.warning("Ignoring replay file %s: warnings must be a list of text", path)
        return None
    return replay
