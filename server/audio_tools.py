"""Herramientas para crear voces a partir de enlaces o de varias grabaciones.

- descargar(): baja el audio de un MP3 directo, de una página de LibriVox o de un vídeo (con yt-dlp).
- recortes(): limpia el audio y saca varios recortes de voz continua, que son los que usa el motor.
"""
from __future__ import annotations

import re
import subprocess
import urllib.request
import uuid
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (EstudioDeVoz)"}
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus", ".aac")
SR = 24000


def _get(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def librivox_mp3s(page_url: str) -> list[str]:
    """Busca los MP3 de capítulos en una página de libro de LibriVox o de archive.org."""
    html = _get(page_url).decode("utf-8", "ignore")
    links = re.findall(r'https?://(?:www\.)?archive\.org/download/[^"\'\s<>]+?_64kb\.mp3', html)
    if not links:
        links = re.findall(r'https?://(?:www\.)?archive\.org/download/[^"\'\s<>]+?\.mp3', html)
    seen, out = set(), []
    for link in links:
        if link not in seen:
            seen.add(link)
            out.append(link)
    return out


def descargar(url: str, carpeta: Path, max_archivos: int = 3) -> list[Path]:
    """Descarga el audio de `url`. Devuelve los archivos descargados."""
    carpeta.mkdir(parents=True, exist_ok=True)
    url = url.strip()
    low = url.lower().split("?")[0]
    if low.endswith(AUDIO_EXT):
        urls = [url]
    elif "librivox.org" in low or "archive.org/details" in low:
        urls = librivox_mp3s(url)[:max_archivos]
        if not urls:
            raise ValueError("No encuentro archivos de audio en esa página.")
    else:
        return [_ytdlp(url, carpeta)]
    out = []
    for u in urls:
        pref = "librivox_" if "librivox" in u.lower() or "archive.org" in u.lower() else ""
        dest = carpeta / f"{pref}{uuid.uuid4().hex[:8]}{Path(u.split('?')[0]).suffix or '.mp3'}"
        dest.write_bytes(_get(u, timeout=300))
        out.append(dest)
    return out


def _ytdlp(url: str, carpeta: Path) -> Path:
    """Vídeos (YouTube, TikTok, Instagram…): descarga solo el audio con yt-dlp."""
    base = carpeta / uuid.uuid4().hex[:8]
    r = subprocess.run(["yt-dlp", "-q", "--no-playlist", "-f", "bestaudio/best", "-x", "--audio-format", "mp3",
                        "-o", f"{base}.%(ext)s", url], capture_output=True, text=True, timeout=600)
    files = list(carpeta.glob(base.name + ".*"))
    if r.returncode != 0 or not files:
        raise ValueError("No he podido descargar el audio de ese enlace. " + (r.stderr.strip().splitlines() or [""])[-1])
    return files[0]


def recortes(archivo: Path, n: int = 4, dur: float = 12.0, saltar: float | None = None, max_min: float = 8.0):
    """Devuelve hasta `n` recortes de `dur` segundos de voz continua y limpia (arrays float32 a 24 kHz).

    `saltar`: segundos iniciales que se ignoran. Por defecto 25 s en LibriVox (la presentación del capítulo)
    y 0 en el resto.
    """
    import librosa
    import numpy as np

    if saltar is None:
        saltar = 25.0 if "librivox" in archivo.name.lower() else 0.0
    y, _ = librosa.load(str(archivo), sr=SR, mono=True, offset=saltar, duration=max_min * 60)
    if len(y) < SR * 3 and saltar:
        y, _ = librosa.load(str(archivo), sr=SR, mono=True, duration=max_min * 60)
    if len(y) < SR * 3:
        raise ValueError("El audio es demasiado corto: hacen falta al menos unos segundos de voz.")
    y = y - float(np.mean(y))
    # tramos con voz (quita silencios largos)
    tramos = librosa.effects.split(y, top_db=35, frame_length=2048, hop_length=512)
    voz = [y[a:b] for a, b in tramos if b - a > SR * 0.3]
    if not voz:
        raise ValueError("No he encontrado voz en ese audio.")
    pausa = np.zeros(int(SR * 0.2), dtype=np.float32)
    limpio = np.concatenate([np.concatenate([v, pausa]) for v in voz]).astype(np.float32)
    largo = int(SR * dur)
    if len(limpio) <= largo:
        candidatos = [limpio]
    else:
        paso = largo // 2
        ventanas = [limpio[i:i + largo] for i in range(0, len(limpio) - largo + 1, paso)]
        # preferir ventanas con volumen estable (sin golpes ni música)
        def puntuacion(w):
            rms = librosa.feature.rms(y=w, frame_length=2048, hop_length=1024)[0]
            return float(np.std(rms) / (np.mean(rms) + 1e-6))
        orden = sorted(range(len(ventanas)), key=lambda i: puntuacion(ventanas[i]))
        elegidas = []
        for i in orden:  # que no se solapen
            if all(abs(i - j) >= 2 for j in elegidas):
                elegidas.append(i)
            if len(elegidas) == n:
                break
        candidatos = [ventanas[i] for i in sorted(elegidas)]
    out = []
    for w in candidatos:
        pico = float(np.max(np.abs(w))) or 1.0
        out.append((w / pico * 0.9).astype(np.float32))
    return out


def guardar_wav(audio, ruta: Path) -> None:
    import soundfile as sf
    sf.write(str(ruta), audio, SR, subtype="PCM_16")
