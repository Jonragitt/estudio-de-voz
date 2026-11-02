"""Genera una sola página HTML con la web en modo vista previa (sin servidor).

Uso:  python tools/build_preview.py   ->  dist/vista-previa.html
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
web = ROOT / "web"
html = (web / "index.html").read_text("utf-8")
css = (web / "style.css").read_text("utf-8")
demo = (web / "demo.js").read_text("utf-8")
app = (web / "app.js").read_text("utf-8")

body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
body = body.replace('<script src="app.js"></script>', "")
banner = ('<div class="preview-note" role="note">Vista previa: la voz es la del navegador. '
          'Las voces de verdad llegan con Chatterbox en el paso 2.</div>')
body = body.replace('<main class="main">', '<main class="main">' + banner, 1)
extra = (".hist .acts a,#pl-dl{display:none!important}"
         ".preview-note{margin:0 0 14px;padding:10px 14px;border-radius:14px;font-size:14px;"
         "background:color-mix(in srgb,var(--tint) 12%,transparent);color:var(--fg2)}")

out = (f"<title>Estudio de voz</title>\n<style>\n{css}\n{extra}\n</style>\n{body}\n"
       f"<script>\n{demo}\n</script>\n<script>\n{app}\n</script>\n")
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
(dist / "vista-previa.html").write_text(out, "utf-8")
print("dist/vista-previa.html")
