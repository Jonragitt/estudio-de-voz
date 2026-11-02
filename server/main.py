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
from .normalizar import PRONUNCIACIONES_INICIALES, normalizar

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("ESTUDIO_DATOS", ROOT / "datos"))  # en Colab: una carpeta de Google Drive
AUDIO = DATA / "audios"
VOICES = DATA / "voces"
for d in (AUDIO, VOICES):
    d.mkdir(parents=True, exist_ok=True)
HISTORY = DATA / "historial.json"
VOICES_DB = DATA / "voces.json"
PRON_DB = DATA / "pronunciaciones.json"

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


PERMISO = "Marca la casilla confirmando que tienes derecho a usar esta voz."


def crear_voz(nombre: str, archivos: list[Path], kind: str, descripcion: str, tags: list[str]) -> dict:
    """Saca recortes limpios de las grabaciones y guarda la voz. Varias grabaciones = voz más fiel."""
    vid = uuid.uuid4().hex[:10]
    refs: list[str] = []
    try:
        from .audio_tools import guardar_wav, recortes
        por_archivo = max(1, 8 // max(1, len(archivos)))
        for f in archivos:
            for clip in recortes(f, n=por_archivo):
                if len(refs) >= 8:
                    break
                ruta = VOICES / f"{vid}_{len(refs)}.wav"
                guardar_wav(clip, ruta)
                refs.append(ruta.name)
    except ImportError:  # sin librosa (modo demo en el portátil): se guarda la grabación tal cual
        ruta = VOICES / f"{vid}{archivos[0].suffix or '.wav'}"
        ruta.write_bytes(archivos[0].read_bytes())
        refs.append(ruta.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        for f in archivos:
            f.unlink(missing_ok=True)
    if not refs:
        raise HTTPException(400, "No he podido sacar voz limpia de esas grabaciones.")
    voice = {"id": vid, "name": nombre.strip()[:60] or "Voz sin nombre", "kind": kind, "tags": tags,
             "description": descripcion, "ref": refs[0], "refs": refs, "created": int(time.time())}
    write_json(VOICES_DB, read_json(VOICES_DB, []) + [voice])
    return voice


@app.post("/api/voces/clonar")
async def clonar(nombre: str = Form(...), permiso: bool = Form(False), audio: list[UploadFile] = File(...)):
    """Crea una voz a partir de una o varias grabaciones subidas."""
    if not permiso:
        raise HTTPException(400, PERMISO)
    tmp = DATA / "tmp"
    tmp.mkdir(exist_ok=True)
    archivos = []
    for a in audio[:10]:
        f = tmp / f"{uuid.uuid4().hex[:8]}{Path(a.filename or 'a.wav').suffix or '.wav'}"
        f.write_bytes(await a.read())
        archivos.append(f)
    n = len(archivos)
    desc = "Creada con una grabación." if n == 1 else f"Creada con {n} grabaciones."
    return crear_voz(nombre, archivos, "clon", desc, ["clonada"])


class ImportRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    enlaces: list[str] = Field(min_length=1, max_length=5)
    permiso: bool = False


@app.post("/api/voces/importar")
def importar(req: ImportRequest):
    """Crea una voz desde enlaces: MP3 directos, páginas de LibriVox/archive.org o vídeos."""
    if not req.permiso:
        raise HTTPException(400, PERMISO)
    from .audio_tools import descargar
    tmp = DATA / "tmp"
    archivos: list[Path] = []
    for url in req.enlaces:
        if not url.strip().startswith(("http://", "https://")):
            raise HTTPException(400, f"Esto no parece un enlace: {url[:60]}")
        try:
            archivos += descargar(url, tmp)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(400, f"No he podido descargar {url[:60]} ({e.__class__.__name__}).")
    origen = "LibriVox" if any("librivox" in u or "archive.org" in u for u in req.enlaces) else "enlace"
    return crear_voz(req.nombre, archivos, "importada", f"Creada desde {origen} ({len(archivos)} audios).",
                     ["importada", origen.lower()])


@app.delete("/api/voces/{vid}")
def borrar_voz(vid: str):
    db = read_json(VOICES_DB, [])
    keep = [v for v in db if v["id"] != vid]
    if len(keep) == len(db):
        raise HTTPException(404, "Esa voz no existe o no se puede borrar.")
    for v in db:
        if v["id"] == vid:
            for r in set(v.get("refs", []) + ([v["ref"]] if v.get("ref") else [])):
                (VOICES / r).unlink(missing_ok=True)
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
    refs = [VOICES / r for r in voice.get("refs", [voice["ref"]] if voice.get("ref") else [])]
    if req.language not in LANGUAGES:
        raise HTTPException(400, "Ese idioma no está disponible.")
    leido = normalizar(req.text, req.language, pronunciaciones_actuales())
    t0 = time.time()
    with gen_lock:
        wav = get_engine().synthesize(leido, refs or None, req.speed, req.exaggeration, req.cfg, req.language)
    aid = uuid.uuid4().hex[:12]
    (AUDIO / f"{aid}.wav").write_bytes(wav)
    item = {"id": aid, "text": req.text, "voice_id": voice["id"], "voice_name": voice["name"],
            "created": int(time.time()), "seconds": round(time.time() - t0, 2), "motor": get_engine().name,
            "language": req.language, "leido": leido}
    hist = read_json(HISTORY, [])
    hist.insert(0, item)
    write_json(HISTORY, hist[:500])
    return item


def pronunciaciones_actuales() -> list[dict]:
    return read_json(PRON_DB, PRONUNCIACIONES_INICIALES)


class Pronunciacion(BaseModel):
    palabra: str = Field(min_length=1, max_length=60)
    lectura: str = Field(min_length=1, max_length=120)


@app.get("/api/pronunciaciones")
def ver_pronunciaciones():
    return pronunciaciones_actuales()


@app.put("/api/pronunciaciones")
def guardar_pronunciaciones(lista: list[Pronunciacion]):
    datos = [p.model_dump() for p in lista[:500]]
    write_json(PRON_DB, datos)
    return datos


class TextoRequest(BaseModel):
    text: str = Field(max_length=5000)
    language: str = "es"


@app.post("/api/normalizar")
def ver_normalizado(req: TextoRequest):
    return {"texto": normalizar(req.text, req.language, pronunciaciones_actuales())}


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
