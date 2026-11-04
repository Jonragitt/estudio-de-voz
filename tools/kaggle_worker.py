"""Trabajador de Kaggle: genera la voz en la GPU para el estudio del portátil.

No se ejecuta a mano: tools/arrancar.py rellena TOKEN y TEMA y lo sube a Kaggle con la API.
Abre un enlace de Cloudflare, lo anuncia en el tema secreto de ntfy.sh y atiende solo a quien traiga la
clave. Se apaga solo si el portátil deja de dar latidos unos minutos (el estudio se cerró).
"""
import os
import re
import subprocess
import sys
import threading
import time
import uuid

TOKEN = "__TOKEN__"
TEMA = "__TEMA__"
REPO = "https://github.com/Jonragitt/estudio-de-voz"
CARPETA = "/kaggle/working/estudio-de-voz"
REFS = "/kaggle/working/voces"
APAGAR_TRAS = 300  # segundos sin noticias del portátil


def sh(cmd: str) -> None:
    print("$", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


sh(f"git clone -q --depth 1 {REPO} {CARPETA}")
sh("pip install -q chatterbox-tts fastapi uvicorn")
# Kaggle trae un torchvision hecho para otra versión de torch, y eso rompe el modelo (igual que en Colab)
sh("pip uninstall -y -q torchvision")
sys.path.insert(0, CARPETA)
os.makedirs(REFS, exist_ok=True)

import queue  # noqa: E402

import requests  # noqa: E402
import torch  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, Header, HTTPException, Request  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402
from server.engine import ChatterboxEngine  # noqa: E402

# Kaggle da dos GPU T4: un modelo en cada una, y cada una genera un trozo a la vez.
# El motor usa «cuda», que es la GPU actual del hilo; por eso se elige con torch.cuda.device.
libres: queue.Queue = queue.Queue()
for gpu in range(max(1, torch.cuda.device_count())):
    with torch.cuda.device(gpu):
        libres.put((gpu, ChatterboxEngine()))
print(f"✅ Motor cargado en {libres.qsize()} GPU", flush=True)

app = FastAPI()
trabajos: dict[str, dict] = {}
ultimo = time.time()


def comprobar(x_token):
    global ultimo
    if x_token != TOKEN:
        raise HTTPException(403, "No autorizado")
    ultimo = time.time()


@app.get("/salud")
def salud(x_token: str = Header(None)):
    comprobar(x_token)
    return {"ok": True}


@app.put("/ref/{nombre}")
async def subir_ref(nombre: str, request: Request, x_token: str = Header(None)):
    comprobar(x_token)
    with open(os.path.join(REFS, os.path.basename(nombre)), "wb") as f:
        f.write(await request.body())
    return {"ok": True}


def generar(tid: str, t: dict) -> None:
    try:
        t0 = time.time()
        refs = [os.path.join(REFS, n) for n in t["refs"]]
        gpu, motor = libres.get()
        try:
            with torch.cuda.device(gpu):
                wav = motor.synthesize(t["text"], refs or None, t["speed"], t["exaggeration"], t["cfg"], t["language"], t["pausa"])
        finally:
            libres.put((gpu, motor))
        trabajos[tid] = {"wav": wav}
        print(f"Audio {tid}: {len(t['text'])} letras en {time.time() - t0:.1f} s", flush=True)
    except Exception as e:
        print("Error:", repr(e), flush=True)
        trabajos[tid] = {"error": repr(e)}


@app.post("/sintetizar")
def sintetizar(t: dict, x_token: str = Header(None)):
    comprobar(x_token)
    faltan = [n for n in t["refs"] if not os.path.exists(os.path.join(REFS, os.path.basename(n)))]
    if faltan:
        return JSONResponse({"faltan": faltan}, status_code=409)
    tid = uuid.uuid4().hex[:12]
    trabajos[tid] = {}
    threading.Thread(target=generar, args=(tid, t), daemon=True).start()
    return {"id": tid}


@app.get("/resultado/{tid}")
def resultado(tid: str, x_token: str = Header(None)):
    comprobar(x_token)
    fin = time.time() + 60  # espera hasta 60 s antes de responder «aún no»
    while time.time() < fin:
        r = trabajos.get(tid)
        if r is None:
            raise HTTPException(404, "No existe ese trabajo")
        if "wav" in r:
            return Response(trabajos.pop(tid)["wav"], media_type="audio/wav")
        if "error" in r:
            raise HTTPException(500, trabajos.pop(tid)["error"])
        time.sleep(0.5)
    return Response(status_code=202)


threading.Thread(target=lambda: uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning"), daemon=True).start()
if not os.path.exists("/kaggle/working/cloudflared"):
    sh("wget -q -O /kaggle/working/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
       " && chmod +x /kaggle/working/cloudflared")
cf = subprocess.Popen(["/kaggle/working/cloudflared", "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"],
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for linea in cf.stdout:
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", linea)
    if m:
        url = m.group(0)
        break
threading.Thread(target=lambda: [None for _ in cf.stdout], daemon=True).start()  # vaciar el resto del registro
requests.post(f"https://ntfy.sh/{TEMA}", data=url, timeout=30)
print("🌍 Enlace anunciado al portátil", flush=True)
ultimo = time.time() + 120  # margen mientras el portátil lo descubre

while time.time() - ultimo < APAGAR_TRAS or any(not r for r in trabajos.values()):
    time.sleep(15)
print("Apagando: el estudio del portátil está cerrado.", flush=True)
cf.kill()
