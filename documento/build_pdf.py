#!/usr/bin/env python3
"""Convierte documento/articulo.md en HTML temporal (A4, estilo del template) y lo imprime a PDF con Edge.

Uso (desde cualquier carpeta):  python documento/build_pdf.py
Requisitos: Python 3 y Microsoft Edge instalado. No usa dependencias externas.
"""
import html
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "articulo.md"
OUT_PDF = HERE / "articulo.pdf"
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 2.5cm; @bottom-center { content: counter(page); font: 10pt 'Times New Roman', serif; } }
@page :first { @bottom-center { content: ''; } }
* { box-sizing: border-box; }
html { font-family: 'Times New Roman', Times, serif; font-size: 12pt; color: #000; }
body { margin: 0; line-height: 1.5; text-align: justify; hyphens: auto; -webkit-hyphens: auto; orphans: 2; widows: 2; }
/* Portada */
.portada { page-break-after: always; text-align: center; line-height: 1.35; min-height: 24.5cm; display: flex; flex-direction: column; justify-content: space-between; }
.portada h1 { font-size: 20pt; line-height: 1.25; margin: 0.6cm 0 0.8cm; text-align: center; }
.portada .logo { display: inline-block; border: 1pt dashed #666; padding: 18pt 28pt; margin: 8pt auto 0; font-size: 10pt; color: #555; }
.portada .top { margin-top: 0.2cm; }
.portada p { margin: 3pt 0; text-align: center; }
.portada ul { list-style: none; padding: 0; margin: 2pt 0 4pt; text-align: center; }
.portada li { margin: 1pt 0; }
.portada .datos { margin-bottom: 0.4cm; }
.pend { background: #fff2a8; padding: 0 2pt; }
/* Cuerpo */
h2 { font-size: 13pt; margin: 14pt 0 3pt; break-after: avoid; text-align: left; }
h3 { font-size: 12pt; font-style: italic; margin: 8pt 0 2pt; break-after: avoid; text-align: left; }
p { margin: 0 0 6pt; }
.cuerpo > h2:first-child { margin-top: 0; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 10pt; }
a { color: #000; text-decoration: none; }
/* Tablas y figuras */
.cap-tabla { font-size: 11pt; line-height: 1.3; margin: 8pt 0 3pt; break-after: avoid; text-align: left; }
.cap-fig { font-size: 11pt; line-height: 1.3; margin: 3pt 0 8pt; text-align: left; }
.nota { font-size: 9pt; line-height: 1.3; margin: 3pt 0 8pt; text-align: left; }
table { border-collapse: collapse; width: 100%; table-layout: fixed; font-size: 10pt; line-height: 1.15; text-align: left; hyphens: auto; }
th, td { border: 0.5pt solid #444; padding: 2pt 3pt; vertical-align: top; overflow-wrap: anywhere; }
th { background: #dcdcdc; font-weight: bold; }
tr { break-inside: avoid; }
figure { margin: 6pt 0 0; break-inside: avoid; text-align: center; }
figure .cap-fig { text-align: left; }
figure img { width: 90%; height: auto; }
/* Referencias */
p.ref { font-size: 12pt; line-height: 1.15; margin: 0 0 2pt; padding-left: 1.27cm; text-indent: -1.27cm; text-align: left; overflow-wrap: anywhere; hyphens: manual; }
"""


def inline(text: str, cover: bool = False) -> str:
    t = html.escape(text, quote=False)
    t = t.replace("s.f.-", "s.f.\u2011")  # guion no separable en (s.f.-a)
    t = re.sub(r"(\d) (\d{3})\b", "\\1\u00a0\\2", t)  # 40 000 sin corte de linea
    t = t.replace(" %", "\u00a0%")
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", t)
    t = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', t)
    if cover:
        t = re.sub(r"\[([^\]]+)\]", r'<span class="pend">[\1]</span>', t)
    return t


def table_html(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], cells[2:]
    n = len(head)
    widths = {6: [14, 18, 13, 16, 18, 21]}.get(n, [round(100 / n)] * n)
    out = ["<table>", "<colgroup>" + "".join(f'<col style="width:{w}%">' for w in widths) + "</colgroup>"]
    out.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def convert(md: str) -> str:
    cover_md, body_md = md.split("\n---\n", 1)
    # --- portada
    cover = ['<section class="portada">']
    lines = [l for l in cover_md.splitlines()]
    title = next(l[2:].strip() for l in lines if l.startswith("# "))
    top, datos, in_list = [], [], False
    for l in lines:
        s = l.strip()
        if not s or s.startswith("# "):
            continue
        if s == "![UTN Logo]":
            top.append('<div class="logo">[Logo de la UTN: insertar aquí]</div>')
        elif s.startswith("- "):
            if not in_list:
                datos.append("<ul>")
                in_list = True
            datos.append(f"<li>{inline(s[2:], True)}</li>")
        else:
            if in_list:
                datos.append("</ul>")
                in_list = False
            (top if s.startswith("**Universidad") else datos).append(
                f"<p>{inline(s, True)}</p>" if not s.startswith("<") else s
            )
    if in_list:
        datos.append("</ul>")
    # Reparte: universidad + logo arriba, título al centro, datos abajo
    uni = [x for x in top if "Universidad" in x or "logo" in x]
    cover += ['<div class="top">' + "".join(uni) + "</div>", f"<h1>{inline(title)}</h1>", '<div class="datos">' + "".join(datos) + "</div>", "</section>"]

    # --- cuerpo
    out = ['<main class="cuerpo">']
    blocks = re.split(r"\n\s*\n", body_md.strip())
    in_refs = False
    in_fig = False
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        lines = b.splitlines()
        if b.startswith("## "):
            name = b[3:].strip()
            if in_refs:
                out.append("</div>")
            in_refs = name == "Referencias"
            out.append(f"<h2>{inline(name)}</h2>")
            if in_refs:
                out.append('<div class="refs">')
        elif b.startswith("### "):
            out.append(f"<h3>{inline(b[4:].strip())}</h3>")
        elif b.startswith("!["):
            m = re.match(r"!\[(.*)\]\((.*)\)", b, re.S)
            src = (HERE / m.group(2)).resolve().as_uri()  # ruta absoluta: el HTML temporal vive en otra carpeta
            out.append(f'<figure><img src="{html.escape(src)}" alt="{html.escape(m.group(1), quote=True)}">')
            in_fig = True
        elif b.startswith("|"):
            out.append(table_html(lines))
        elif b.startswith("**Tabla"):
            out.append(f'<p class="cap-tabla">{inline(b)}</p>')
        elif b.startswith("**Figura"):
            # la leyenda va debajo de la figura y dentro del mismo bloque (no se separan al paginar)
            out.append(f'<p class="cap-fig">{inline(b)}</p>' + ("</figure>" if in_fig else ""))
            in_fig = False
        elif b.startswith("*Nota.*"):
            out.append(f'<p class="nota">{inline(b)}</p>')
        elif in_refs:
            out.append(f'<p class="ref">{inline(b)}</p>')
        else:
            out.append(f"<p>{inline(b)}</p>")
    if in_refs:
        out.append("</div>")
    out.append("</main>")

    return (
        '<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>\n"
        + "\n".join(cover)
        + "\n"
        + "\n".join(out)
        + "\n</body></html>\n"
    )


def main() -> int:
    edge = next((p for p in EDGE_CANDIDATES if Path(p).exists()), None)
    if not edge:
        print("No se encontró Microsoft Edge: instalarlo para generar el PDF.")
        return 1
    OUT_PDF.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:  # el HTML es intermedio: no se conserva
        out_html = Path(tmp) / "articulo.html"
        out_html.write_text(convert(SRC.read_text(encoding="utf-8")), encoding="utf-8")
        subprocess.run(
            [edge, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={OUT_PDF}", out_html.as_uri()],
            check=True,
            capture_output=True,
        )
        # Edge puede devolver el control antes de terminar de escribir: esperar a que el archivo se estabilice.
        last = -1
        for _ in range(60):
            time.sleep(0.5)
            size = OUT_PDF.stat().st_size if OUT_PDF.exists() else -1
            if size > 0 and size == last:
                break
            last = size
    print(f"PDF:  {OUT_PDF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
