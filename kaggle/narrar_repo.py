"""Narra lecciones sin interfaz (para Kaggle u otra GPU) y sube cada MP3 a un repositorio de GitHub.

Lee los textos de un repositorio (p. ej. el privado de APUNTY), narra las lecciones que falten con la voz
indicada y hace commit + push de cada MP3 en cuanto termina. Si se corta, al volver a lanzarlo sigue
por donde iba. Pensado para «Guardar versión → Guardar y ejecutar todo» en Kaggle: sigue aunque
cierres el navegador.

Variables de entorno:
  GH_TOKEN      clave de GitHub con permiso de escritura en el repositorio (obligatoria)
  REPO          dueño/nombre del repositorio, p. ej. jonragitt/apunty
  RAMA          rama donde están los textos y donde se suben los audios
  TEXTOS        JSON con {"lecciones": [{"id", "titulo", "texto"}]} dentro del repositorio
  SALIDA        carpeta del repositorio donde se guardan los MP3
  VOZ           carpeta del repositorio con los recortes WAV de la voz (si está vacía se crean desde VOZ_URL)
  VOZ_URL       página de LibriVox / archive.org / MP3 para crear la voz si no hay recortes
  VELOCIDAD, EXPRESIVIDAD, RITMO, PAUSAS   ajustes (por defecto, los de «Narrador pausado»)
  MAX_HORAS     para antes de este tiempo (Kaggle corta a las 12 h)
  SOLO          ids de lecciones separados por comas (repartir entre máquinas); SOLO_VOZ=1 solo crea la voz
  YA_CLONADO    el repositorio ya está en CARPETA (GitHub Actions)
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.normalizar import PRONUNCIACIONES_INICIALES, normalizar  # noqa: E402

E = os.environ.get
TOKEN = E("GH_TOKEN", "")
REPO = E("REPO", "jonragitt/apunty")
RAMA = E("RAMA", "claude/project-thread-v133ti")
TEXTOS = E("TEXTOS", "narracion/apunty-japon.json")
SALIDA = E("SALIDA", "narracion/audio")
VOZ = E("VOZ", "narracion/voz")
VOZ_URL = E("VOZ_URL", "https://archive.org/details/torquemadahoguera_2610_librivox")
AJUSTES = dict(speed=float(E("VELOCIDAD", "0.95")), exaggeration=float(E("EXPRESIVIDAD", "0.35")),
               cfg=float(E("RITMO", "0.3")), pausa=float(E("PAUSAS", "1.4")))
MAX_SEG = float(E("MAX_HORAS", "11")) * 3600
DESTINO = Path(E("CARPETA", "/kaggle/working/repo" if Path("/kaggle").exists() else str(ROOT / "datos" / "repo")))
T0 = time.time()


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", str(DESTINO), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[-400:]}")
    return r


def clonar() -> None:
    if E("YA_CLONADO"):  # GitHub Actions: el repositorio ya está descargado y con permiso para subir
        git("config", "user.name", "Estudio de voz")
        git("config", "user.email", "estudio-de-voz@users.noreply.github.com")
        return
    if not TOKEN:
        sys.exit("❌ Falta GH_TOKEN (la clave de GitHub). En Kaggle: Add-ons → Secrets → GH_TOKEN.")
    url = E("REPO_URL") or f"https://x-access-token:{TOKEN}@github.com/{REPO}.git"  # REPO_URL: solo para pruebas
    if (DESTINO / ".git").exists():
        git("pull", "-q", "--rebase", "origin", RAMA)
    else:
        DESTINO.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "clone", "-q", "--depth", "1", "-b", RAMA, url, str(DESTINO)], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("❌ No puedo abrir el repositorio: revisa la clave de GitHub. " + r.stderr.replace(TOKEN, "***")[-300:])
    git("config", "user.name", "Estudio de voz")
    git("config", "user.email", "estudio-de-voz@users.noreply.github.com")


def subir(rutas: list[Path], mensaje: str) -> None:
    git("add", *[str(p.relative_to(DESTINO)) for p in rutas])
    if not git("diff", "--cached", "--quiet", check=False).returncode:
        return
    git("commit", "-q", "-m", mensaje)
    import random
    for intento in range(12):  # varias máquinas pueden estar subiendo a la vez
        if git("push", "-q", "origin", f"HEAD:{RAMA}", check=False).returncode == 0:
            return
        git("pull", "-q", "--rebase", "origin", RAMA, check=False)
        time.sleep(min(60, 2 ** intento) * random.uniform(0.5, 1.5))
    raise RuntimeError("No he podido subir a GitHub.")


def preparar_voz() -> list[Path]:
    carpeta = DESTINO / VOZ
    refs = sorted(carpeta.glob("*.wav"))
    if refs:
        print(f"🎙️ Voz: {len(refs)} recortes de {VOZ}")
        return refs
    from server.audio_tools import descargar, guardar_wav, recortes
    print("🎙️ Creando la voz desde", VOZ_URL)
    tmp = Path("/tmp/voz-descargas")
    archivos = descargar(VOZ_URL, tmp)
    carpeta.mkdir(parents=True, exist_ok=True)
    por = max(1, 8 // len(archivos))
    for f in archivos:
        for clip in recortes(f, n=por):
            if len(refs) < 8:
                ruta = carpeta / f"ref_{len(refs)}.wav"
                guardar_wav(clip, ruta)
                refs.append(ruta)
    subir(refs, "Recortes de la voz para narrar")
    return refs


def a_mp3(wav: bytes, destino: Path) -> float:
    tmp = destino.with_suffix(".tmp.mp3")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "wav", "-i", "pipe:0", "-ac", "1", "-ar", "24000",
                    "-b:a", "64k", str(tmp)], input=wav, check=True)
    tmp.replace(destino)
    with wave.open(io.BytesIO(wav)) as w:
        return round(w.getnframes() / w.getframerate(), 1)


def main() -> None:
    clonar()
    lecciones = json.loads((DESTINO / TEXTOS).read_text("utf-8"))["lecciones"]
    salida = DESTINO / SALIDA
    salida.mkdir(parents=True, exist_ok=True)
    pendientes = [l for l in lecciones if not (salida / f"{l['id']}.mp3").exists()]
    if E("SOLO"):  # solo estas lecciones (para repartir el trabajo entre varias máquinas)
        solo = set(E("SOLO").split(","))
        pendientes = [l for l in pendientes if l["id"] in solo]
    if E("SOLO_VOZ"):  # solo preparar los recortes de la voz
        preparar_voz()
        return
    print(f"📚 {len(lecciones)} lecciones, faltan {len(pendientes)}")
    if not pendientes:
        print("✅ Ya está todo narrado.")
        return
    refs = preparar_voz()
    from server.engine import ChatterboxEngine
    motor = ChatterboxEngine()  # sin GPU falla (salvo ESTUDIO_CPU=1): mejor parar que grabar pitidos
    pron_extra = DESTINO / "narracion" / "pronunciaciones.json"
    diccionario = PRONUNCIACIONES_INICIALES + (json.loads(pron_extra.read_text("utf-8")) if pron_extra.exists() else [])
    for n, l in enumerate(pendientes, 1):
        if time.time() - T0 > MAX_SEG:
            print("⏸️ Se acaba el tiempo de la sesión: paro aquí. Vuelve a lanzarlo y seguirá.")
            break
        t = time.time()
        leido = normalizar(l["texto"], "es", diccionario)
        wav = motor.synthesize(leido, refs, AJUSTES["speed"], AJUSTES["exaggeration"], AJUSTES["cfg"], "es", AJUSTES["pausa"])
        mp3 = salida / f"{l['id']}.mp3"
        dur = a_mp3(wav, mp3)
        subir([mp3], f"Narración: {l.get('titulo') or l['id']}")
        print(f"✅ {n}/{len(pendientes)} {l['id']} · {dur:.0f} s de audio en {time.time() - t:.0f} s", flush=True)
    print("🏁 Fin.")


if __name__ == "__main__":
    main()
