"""HTML for the read-only RCA page (http://localhost:8085). Pure string building: no state, no network.

main.py passes in what to show (model name, LLM status, mode, the incidents); this file only draws it.
A pre-recorded answer is never drawn like a live one: it always carries its own banner.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from replay import live_label

if TYPE_CHECKING:  # only for type hints; importing main here would be circular
    from main import Incident

STATUS_LABEL = {
    "analizando": "analizando…",
    "listo": "respuesta en vivo",
    "pregrabada": "respuesta PREGRABADA (no es en vivo)",
    "llm_no_disponible": "LLM no disponible: solo evidencia",
}

PAGE_STYLE = """
body{font-family:system-ui,sans-serif;background:#111827;color:#e5e7eb;margin:0;padding:1.5rem 2rem}
h1{font-size:1.4rem;margin:0 0 .3rem} .sub{color:#9ca3af;margin-bottom:1.2rem}
.card{background:#1f2937;border-radius:8px;padding:1rem 1.2rem;margin-bottom:1.2rem}
.head{display:flex;gap:1rem;align-items:center;margin-bottom:.8rem}
.badge{padding:.15rem .6rem;border-radius:999px;font-size:.85rem;font-weight:600}
.analizando{background:#b45309}.listo{background:#15803d}.pregrabada{background:#7c3aed}.llm_no_disponible{background:#b91c1c}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem}
@media(max-width:900px){.cols{grid-template-columns:1fr}}
h2{font-size:1.1rem;margin:0 0 .5rem;color:#93c5fd}
pre{white-space:pre-wrap;font-family:ui-monospace,Consolas,monospace;font-size:1rem;margin:0}
.llm pre{font-family:system-ui,sans-serif;font-size:1.15rem;line-height:1.45}
.warn{color:#fbbf24;margin-top:.6rem}.ok{color:#86efac;margin-top:.6rem}.err{color:#fca5a5}
.src{border-radius:6px;padding:.4rem .7rem;margin-bottom:.7rem;font-weight:600}
.src.live{background:#14532d;color:#bbf7d0}.src.replay{background:#4c1d95;color:#ede9fe}
.src small{display:block;font-weight:400;margin-top:.2rem}
details{margin-top:.8rem;color:#9ca3af}
"""

PAGE_SCRIPT = """document.querySelectorAll('time').forEach(function(t){
 var d=new Date(t.getAttribute('datetime'));t.textContent=d.toLocaleTimeString();});"""


def render_llm_box(model: str, incident: Incident) -> tuple[str, str]:
    """(heading, body) of the right-hand column, according to where the explanation comes from."""
    if incident.status == "analizando":
        return f"Explicación del LLM local ({html.escape(model)})", "<pre>analizando…</pre>"
    if incident.status == "listo":
        body = f'<div class="src live">{html.escape(live_label(model))}</div>'
        body += f"<pre>{html.escape(incident.explanation.strip())}</pre>"
        if incident.warnings:
            body += f'<div class="warn">Atención: {html.escape("; ".join(incident.warnings))}</div>'
        else:
            body += ('<div class="ok">Control automático: las cifras citadas están en la evidencia, junto a la señal correcta, y no se copió el ejemplo. '
                     "Esto no prueba que la explicación sea correcta.</div>")
        return f"Explicación del LLM local ({html.escape(model)}), basada solo en esa evidencia", body
    if incident.status == "pregrabada" and incident.replay:
        replay = incident.replay
        body = (f'<div class="src replay">{html.escape(replay.label())}'
                f"<small>Motivo: {html.escape(incident.replay_reason)}.</small></div>")
        body += f"<pre>{html.escape(replay.explanation.strip())}</pre>"
        notice = "Las cifras de este texto son las del incidente original, no las de la evidencia actual de la izquierda."
        if incident.live_pending:  # only while the live attempt is still running
            notice += " Si el LLM en vivo responde, esta respuesta se reemplaza."
        body += f'<div class="warn">{notice}</div>'
        if replay.warnings:
            body += f'<div class="warn">Atención (en la respuesta original): {html.escape("; ".join(replay.warnings))}</div>'
        body += (f"<details><summary>Evidencia en la que se basó la respuesta pregrabada (incidente original)</summary>"
                 f"<pre>{html.escape(replay.evidence)}</pre></details>")
        return f"Explicación pregrabada de {html.escape(replay.model)} (incidente del mismo tipo)", body
    body = f'<div class="err">LLM no disponible. Se muestra solo la evidencia medida.<br>Motivo: {html.escape(incident.llm_error)}</div>'
    if incident.partial:
        body += f"<details open><summary>Texto parcial recibido</summary><pre>{html.escape(incident.partial)}</pre></details>"
    return f"Explicación del LLM local ({html.escape(model)})", body


def render_incident(model: str, incident: Incident, build_messages: Callable) -> str:
    when = datetime.fromtimestamp(incident.detected_at, timezone.utc)
    evidence = html.escape(incident.evidence.text) if incident.evidence else "Reuniendo evidencia…"
    heading, llm_box = render_llm_box(model, incident)
    prompt_box = ""
    if incident.evidence and incident.status in ("listo", "llm_no_disponible"):  # a recorded answer used no prompt now
        prompt = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in build_messages(incident.evidence.text))
        prompt_box = f"<details><summary>Prompt exacto enviado al LLM</summary><pre>{html.escape(prompt)}</pre></details>"
    seconds = f" · LLM {incident.llm_seconds:.0f} s" if incident.status in ("listo", "llm_no_disponible") else ""
    return f"""
<div class="card">
  <div class="head"><b>Incidente #{incident.id}</b>
    <time datetime="{when.isoformat()}">{when:%H:%M:%S} UTC</time>
    <span class="badge {incident.status}">{STATUS_LABEL[incident.status]}</span>
    <span style="color:#9ca3af">{html.escape(incident.grafana_note)}{seconds}</span></div>
  <div class="cols">
    <div><h2>Evidencia medida ahora (sin IA)</h2><pre>{evidence}</pre></div>
    <div class="llm"><h2>{heading}</h2>{llm_box}</div>
  </div>
  {prompt_box}
</div>"""


def render_page(model: str, llm_status: str, mode: str, incidents: list[Incident], build_messages: Callable) -> str:
    cards = "".join(render_incident(model, i, build_messages) for i in incidents[:10])
    if not cards:
        cards = '<div class="card">Sin anomalías detectadas por ahora. Esta página se actualiza sola.</div>'
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="3"><title>Explicación de causa raíz - Acto 3</title>
<style>{PAGE_STYLE}</style></head><body>
<h1>Explicación de causa raíz (Acto 3)</h1>
<div class="sub">Modo: {html.escape(mode)}. LLM local: {html.escape(llm_status)}. Página de solo lectura; se actualiza cada 3 s.
El LLM recibe únicamente la evidencia de la izquierda. Si se equivoca, se nota al compararlas.
Una respuesta pregrabada siempre se marca como tal.</div>
{cards}<script>{PAGE_SCRIPT}</script></body></html>"""
