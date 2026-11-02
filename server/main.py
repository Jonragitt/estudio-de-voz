"""Servidor del Estudio de voz: sirve la web y la API.

Arranque:  uvicorn server.main:app --reload   (desde la carpeta del proyecto)
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine import LANGUAGES, load_engine

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("ESTUDIO_DATOS", ROOT / "datos"))  # en Colab: una carpeta de Google Drive
AUDIO = DATA / "audios"
VOICES = DATA / "voces"
for d in (AUDIO, VOICES):
    d.mkdir(parents=True, exist_ok=True)
HISTORY = DATA / "historial.json"
VOICES_DB = DATA / "voces.json"

DEFAULT_VOICES = [
    {"id": "base", "name": "Narrador base", "kind": "base", "tags": ["neutra", "español"],
     "description": "La voz por defecto del modelo."},
]

app = FastAPI(title="Estudio de voz")
engine = None
gen_lock = threading.Lock()  # la GPU genera un audio cada vez


def get_engine():
    global engine
    if engine is None:
        engine = load_engine()
    return engine


def read_json(p: Path, default):
    return json.loads(p.read_text("utf-8")) if p.exists() else default


def write_json(p: Path, data) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def all_voices() -> list[dict]:
    return DEFAULT_VOICES + read_json(VOICES_DB, [])


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice_id: str = "base"
    speed: float = Field(1.0, ge=0.5, le=2.0)
    exaggeration: float = Field(0.5, ge=0.0, le=1.0)
    cfg: float = Field(0.5, ge=0.0, le=1.0)
    language: str = "es"


@app.get("/api/estado")
def estado():
    e = get_engine()
    return {"motor": e.name, "listo": e.ready}


@app.get("/api/idiomas")
def idiomas():
    return LANGUAGES


@app.get("/api/voces")
def voces():
    return all_voices()


@app.post("/api/voces/clonar")
async def clonar(nombre: str = Form(...), audio: UploadFile = File(...)):
    """Clon rápido: guarda una grabación de referencia. El entrenamiento completo llega en el paso 3."""
    vid = uuid.uuid4().hex[:10]
    ext = Path(audio.filename or "ref.wav").suffix or ".wav"
    ref = VOICES / f"{vid}{ext}"
    ref.write_bytes(await audio.read())
    voice = {"id": vid, "name": nombre.strip()[:60] or "Voz sin nombre", "kind": "clon",
             "tags": ["clonada"], "description": "Clon rápido a partir de una grabación.", "ref": ref.name}
    write_json(VOICES_DB, read_json(VOICES_DB, []) + [voice])
    return voice


@app.delete("/api/voces/{vid}")
def borrar_voz(vid: str):
    db = read_json(VOICES_DB, [])
    keep = [v for v in db if v["id"] != vid]
    if len(keep) == len(db):
        raise HTTPException(404, "Esa voz no existe o no se puede borrar.")
    for v in db:
        if v["id"] == vid and v.get("ref"):
            (VOICES / v["ref"]).unlink(missing_ok=True)
    write_json(VOICES_DB, keep)
    return {"ok": True}


@app.post("/api/voces/disenar")
def disenar():
    raise HTTPException(501, "Diseñar voces desde cero llega en el paso 4.")


@app.post("/api/tts")
def tts(req: TTSRequest):
    voice = next((v for v in all_voices() if v["id"] == req.voice_id), None)
    if not voice:
        raise HTTPException(404, "No encuentro esa voz.")
    ref = VOICES / voice["ref"] if voice.get("ref") else None
    if req.language not in LANGUAGES:
        raise HTTPException(400, "Ese idioma no está disponible.")
    t0 = time.time()
    with gen_lock:
        wav = get_engine().synthesize(req.text, ref, req.speed, req.exaggeration, req.cfg, req.language)
    aid = uuid.uuid4().hex[:12]
    (AUDIO / f"{aid}.wav").write_bytes(wav)
    item = {"id": aid, "text": req.text, "voice_id": voice["id"], "voice_name": voice["name"],
            "created": int(time.time()), "seconds": round(time.time() - t0, 2), "motor": get_engine().name,
            "language": req.language}
    hist = read_json(HISTORY, [])
    hist.insert(0, item)
    write_json(HISTORY, hist[:500])
    return item


@app.get("/api/historial")
def historial():
    return read_json(HISTORY, [])


@app.delete("/api/historial/{aid}")
def borrar_historial(aid: str):
    hist = read_json(HISTORY, [])
    write_json(HISTORY, [h for h in hist if h["id"] != aid])
    (AUDIO / f"{aid}.wav").unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/audio/{aid}")
def audio(aid: str):
    p = AUDIO / f"{Path(aid).name}.wav"
    if not p.exists():
        raise HTTPException(404, "Audio no encontrado.")
    return FileResponse(p, media_type="audio/wav", filename=f"estudio-{aid}.wav")


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
