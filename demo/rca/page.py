"""HTML for the read-only RCA page (http://localhost:8085). Pure string building: no state, no network.

main.py passes in what to show (model name, LLM status, the incidents); this file only draws it.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  # only for type hints; importing main here would be circular
    from main import Incident

STATUS_LABEL = {
    "analizando": "analizando…",
    "listo": "explicación lista",
    "llm_no_disponible": "LLM no disponible: solo evidencia",
}

PAGE_STYLE = """
body{font-family:system-ui,sans-serif;background:#111827;color:#e5e7eb;margin:0;padding:1.5rem 2rem}
h1{font-size:1.4rem;margin:0 0 .3rem} .sub{color:#9ca3af;margin-bottom:1.2rem}
.card{background:#1f2937;border-radius:8px;padding:1rem 1.2rem;margin-bottom:1.2rem}
.head{display:flex;gap:1rem;align-items:center;margin-bottom:.8rem}
.badge{padding:.15rem .6rem;border-radius:999px;font-size:.85rem;font-weight:600}
.analizando{background:#b45309}.listo{background:#15803d}.llm_no_disponible{background:#b91c1c}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem}
@media(max-width:900px){.cols{grid-template-columns:1fr}}
h2{font-size:1.1rem;margin:0 0 .5rem;color:#93c5fd}
pre{white-space:pre-wrap;font-family:ui-monospace,Consolas,monospace;font-size:1rem;margin:0}
.llm pre{font-family:system-ui,sans-serif;font-size:1.15rem;line-height:1.45}
.warn{color:#fbbf24;margin-top:.6rem}.ok{color:#86efac;margin-top:.6rem}.err{color:#fca5a5}
details{margin-top:.8rem;color:#9ca3af}
"""

PAGE_SCRIPT = """document.querySelectorAll('time').forEach(function(t){
 var d=new Date(t.getAttribute('datetime'));t.textContent=d.toLocaleTimeString();});"""


def render_incident(model: str, incident: Incident, build_messages: Callable) -> str:
    when = datetime.fromtimestamp(incident.detected_at, timezone.utc)
    evidence = html.escape(incident.evidence.text) if incident.evidence else "Reuniendo evidencia…"
    if incident.status == "analizando":
        llm_box = "<pre>analizando…</pre>"
    elif incident.status == "listo":
        llm_box = f"<pre>{html.escape(incident.explanation.strip())}</pre>"
        if incident.warnings:
            llm_box += f'<div class="warn">Atención: {html.escape("; ".join(incident.warnings))}</div>'
        else:
            llm_box += ('<div class="ok">Control automático: las cifras citadas están en la evidencia, junto a la señal correcta, y no se copió el ejemplo. '
                        "Esto no prueba que la explicación sea correcta.</div>")
    else:
        llm_box = f'<div class="err">LLM no disponible. Se muestra solo la evidencia medida.<br>Motivo: {html.escape(incident.llm_error)}</div>'
        if incident.partial:
            llm_box += f"<details open><summary>Texto parcial recibido</summary><pre>{html.escape(incident.partial)}</pre></details>"
    prompt_box = ""
    if incident.evidence:
        prompt = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in build_messages(incident.evidence.text))
        prompt_box = f"<details><summary>Prompt exacto enviado al LLM</summary><pre>{html.escape(prompt)}</pre></details>"
    seconds = f" · LLM {incident.llm_seconds:.0f} s" if incident.status != "analizando" else ""
    return f"""
<div class="card">
  <div class="head"><b>Incidente #{incident.id}</b>
    <time datetime="{when.isoformat()}">{when:%H:%M:%S} UTC</time>
    <span class="badge {incident.status}">{STATUS_LABEL[incident.status]}</span>
    <span style="color:#9ca3af">{html.escape(incident.grafana_note)}{seconds}</span></div>
  <div class="cols">
    <div><h2>Evidencia medida (sin IA)</h2><pre>{evidence}</pre></div>
    <div class="llm"><h2>Explicación del LLM local ({html.escape(model)}), basada solo en esa evidencia</h2>{llm_box}</div>
  </div>
  {prompt_box}
</div>"""


def render_page(model: str, llm_status: str, incidents: list[Incident], build_messages: Callable) -> str:
    cards = "".join(render_incident(model, i, build_messages) for i in incidents[:10])
    if not cards:
        cards = '<div class="card">Sin anomalías detectadas por ahora. Esta página se actualiza sola.</div>'
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="3"><title>Explicación de causa raíz - Acto 3</title>
<style>{PAGE_STYLE}</style></head><body>
<h1>Explicación de causa raíz (Acto 3)</h1>
<div class="sub">LLM local: {html.escape(llm_status)}. Página de solo lectura; se actualiza cada 3 s.
El LLM recibe únicamente la evidencia de la izquierda. Si se equivoca, se nota al compararlas.</div>
{cards}<script>{PAGE_SCRIPT}</script></body></html>"""
