"""Arranca el estudio con la voz de verdad generada en Kaggle, sin tocar Kaggle a mano.

1. Sube tools/kaggle_worker.py a Kaggle como cuaderno con GPU, con una clave y un tema secreto nuevos.
2. Arranca el estudio y abre el navegador. En cuanto Kaggle está listo (unos 10 minutos), el estudio
   lo encuentra solo. Los audios se guardan en datos/, en el portátil.

Si falta la llave de Kaggle (kaggle.json) o algo falla, el estudio arranca igual en modo demo.
Uso: .venv\\Scripts\\python tools\\arrancar.py   (lo hace «Abrir estudio.bat»)
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KAGGLE_DIR = Path.home() / ".kaggle"
PUERTO = 8000


def llave_kaggle() -> dict | None:
    """Devuelve el contenido de kaggle.json; si está en Descargas, lo mueve a su sitio."""
    destino = KAGGLE_DIR / "kaggle.json"
    if not destino.exists():
        candidatos = sorted((Path.home() / "Downloads").glob("kaggle*.json"), key=lambda p: p.stat().st_mtime)
        if not candidatos:
            return None
        KAGGLE_DIR.mkdir(exist_ok=True)
        shutil.move(str(candidatos[-1]), destino)
        print("Llave de Kaggle guardada en", destino)
    return json.loads(destino.read_text("utf-8"))


def subir_trabajador(usuario: str, token: str, tema: str) -> None:
    carpeta = ROOT / "datos" / "kaggle"
    carpeta.mkdir(parents=True, exist_ok=True)
    codigo = (ROOT / "tools" / "kaggle_worker.py").read_text("utf-8")
    (carpeta / "worker.py").write_text(codigo.replace("__TOKEN__", token).replace("__TEMA__", tema), "utf-8")
    meta = {"id": f"{usuario}/estudio-de-voz-gpu", "title": "estudio-de-voz-gpu", "code_file": "worker.py",
            "language": "python", "kernel_type": "script", "is_private": True, "enable_gpu": True,
            "enable_tpu": False, "enable_internet": True,
            "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": []}
    (carpeta / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), "utf-8")
    kaggle = Path(sys.executable).with_name("kaggle.exe")
    r = subprocess.run([str(kaggle), "kernels", "push", "-p", str(carpeta), "--accelerator", "NvidiaTeslaT4"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    salida = (r.stdout + r.stderr).strip()
    print(salida)
    if r.returncode != 0 or "error" in salida.lower():
        raise RuntimeError("Kaggle no aceptó el cuaderno: " + salida[-400:])


def main() -> None:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))  # para que uvicorn encuentre server.main
    try:
        llave = llave_kaggle()
        if not llave:
            raise RuntimeError("no encuentro kaggle.json (créalo en kaggle.com → Settings → API → Create New Token)")
        token, tema = secrets.token_urlsafe(24), "estudio-voz-" + secrets.token_hex(12)
        subir_trabajador(llave["username"], token, tema)
        os.environ.update(ESTUDIO_MOTOR="kaggle", ESTUDIO_TOKEN=token, ESTUDIO_TEMA=tema)
        print("✅ GPU de Kaggle pedida. Tarda unos 10 minutos en estar lista; el estudio la encontrará solo.")
    except Exception as e:
        print("⚠️  Sin Kaggle:", e, "→ arranco en modo demo.")
        os.environ["ESTUDIO_MOTOR"] = "demo"
    threading.Timer(2, lambda: webbrowser.open(f"http://localhost:{PUERTO}")).start()
    import uvicorn
    uvicorn.run("server.main:app", host="127.0.0.1", port=PUERTO)


if __name__ == "__main__":
    main()
