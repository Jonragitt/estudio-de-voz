"""Motores de voz del Estudio.

- ChatterboxEngine: el motor real, Chatterbox Multilingüe de Resemble AI (licencia MIT, permite uso
  comercial, 23 idiomas incluido el español). Se usa si está instalado y hay GPU (o ESTUDIO_CPU=1).
- DemoEngine: genera pitidos de prueba para poder usar la web sin GPU ni modelo instalado.
"""
from __future__ import annotations

import io
import math
import os
import re
import struct
import wave
from pathlib import Path

LANGUAGES = {
    "es": "Español", "en": "Inglés", "fr": "Francés", "it": "Italiano", "pt": "Portugués",
    "de": "Alemán", "ja": "Japonés", "zh": "Chino", "ko": "Coreano", "ru": "Ruso", "ar": "Árabe",
    "nl": "Neerlandés", "pl": "Polaco", "tr": "Turco", "sv": "Sueco", "da": "Danés", "no": "Noruego",
    "fi": "Finés", "el": "Griego", "he": "Hebreo", "hi": "Hindi", "ms": "Malayo", "sw": "Suajili",
}


def split_text(text: str, limit: int = 280) -> list[str]:
    """Trocea el texto en trozos de como mucho `limit` caracteres (se usa en el motor demo)."""
    return [f for f, _ in frases(text, limit)] or [text]


PAUSAS = {".": 0.55, "!": 0.55, "?": 0.6, "…": 0.7, ";": 0.4, ":": 0.4, ",": 0.22, "\n": 0.9}


def frases(text: str, limit: int = 220) -> list[tuple[str, float]]:
    """Divide el texto en frases y dice cuánto silencio va después de cada una.

    Generar frase a frase hace que el narrador vaya más pausado y respire entre frases, en lugar de
    leer de corrido un bloque largo.
    """
    out: list[tuple[str, float]] = []
    for parrafo in [p.strip() for p in re.split(r"\n\s*\n|\n", text.strip()) if p.strip()]:
        partes = [x.strip() for x in re.split(r"(?<=[.!?…;:])\s+", parrafo) if x.strip()]
        # frases muy cortas («¿Por qué?», «Clave.») se unen a la siguiente: sueltas, el modelo a veces falla
        juntas: list[str] = []
        for x in partes:
            if juntas and len(juntas[-1]) < 16 and len(juntas[-1]) + len(x) < limit:
                juntas[-1] = juntas[-1] + " " + x
            else:
                juntas.append(x)
        partes = juntas
        for i, frase in enumerate(partes):
            while len(frase) > limit:  # frase muy larga: cortar por la última coma (o espacio)
                cut = frase.rfind(",", 0, limit)
                cut = cut if cut > limit // 3 else frase.rfind(" ", 0, limit)
                cut = cut if cut > limit // 3 else limit
                out.append((frase[:cut + 1].strip(), PAUSAS[","]))
                frase = frase[cut + 1:].strip()
            if frase:
                fin = frase[-1]
                out.append((frase, PAUSAS.get(fin, 0.45)))
        if out:
            out[-1] = (out[-1][0], PAUSAS["\n"])
    return out


def recortar_silencio(audio, sr: int, umbral: float = 0.01, margen: float = 0.04):
    """Quita el silencio del principio y del final de un trozo para que las pausas sean las nuestras."""
    import numpy as np
    voz = np.where(np.abs(audio) > umbral)[0]
    if len(voz) == 0:
        return audio
    m = int(sr * margen)
    return audio[max(0, voz[0] - m): min(len(audio), voz[-1] + m)]


def cambiar_ritmo(audio, sr: int, velocidad: float):
    """Cambia la velocidad sin cambiar el tono. Usa ffmpeg (atempo, suena limpio en voz);
    si no está, usa librosa (puede sonar con eco)."""
    import numpy as np
    import shutil
    if abs(velocidad - 1.0) < 0.02:
        return audio
    velocidad = min(max(velocidad, 0.5), 2.0)
    if shutil.which("ffmpeg"):
        import subprocess
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0",
                            "-filter:a", f"atempo={velocidad:.3f}", "-f", "s16le", "-ar", str(sr), "-ac", "1", "pipe:1"],
                           input=pcm, capture_output=True)
        if r.returncode == 0 and r.stdout:
            return np.frombuffer(r.stdout, dtype="<i2").astype(np.float32) / 32767
    import librosa
    return librosa.effects.time_stretch(audio, rate=velocidad)


def wav_bytes(samples, rate: int) -> bytes:
    """Convierte muestras float (-1..1) a un WAV de 16 bits."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        if hasattr(samples, "astype"):  # numpy: rápido para audios largos
            import numpy as np
            w.writeframes((np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes())
        else:
            w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, float(x))) * 32767)) for x in samples))
    return buf.getvalue()


class DemoEngine:
    name = "demo"
    ready = True

    def synthesize(self, text: str, refs: list[Path] | None = None, speed: float = 1.0,
                   exaggeration: float = 0.5, cfg: float = 0.5, language: str = "es", pausa: float = 1.0) -> bytes:
        """Devuelve un WAV con un pitido por palabra, para probar la interfaz."""
        rate = 22050
        words = max(1, len(text.split()))
        base = 180 + 220 * exaggeration
        beat = int(rate * 0.18 / max(speed, 0.25))
        gap = int(rate * 0.06 / max(speed, 0.25))
        samples: list[float] = []
        for i in range(min(words, 200)):
            f = base * (1 + 0.12 * math.sin(i))
            samples += [0.27 * math.sin(math.pi * n / beat) * math.sin(2 * math.pi * f * n / rate) for n in range(beat)]
            samples += [0.0] * gap
        return wav_bytes(samples, rate)


class ChatterboxEngine:
    name = "chatterbox"

    def __init__(self) -> None:
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        if torch.cuda.is_available():
            device = "cuda"
        elif os.getenv("ESTUDIO_CPU") == "1":
            device = "cpu"  # funciona, pero muy despacio
        else:
            raise RuntimeError("No hay GPU NVIDIA (pon ESTUDIO_CPU=1 para forzar la CPU)")
        self.model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        self.sr = self.model.sr
        self.base_conds = self.model.conds
        self.cache: dict[str, object] = {}
        self.ready = True

    def _conds_for(self, refs: list[Path] | None, exaggeration: float):
        """Prepara la voz. Con varios recortes, la huella de la voz es la media de todos (más fiel)."""
        if not refs:
            return self.base_conds
        key = "|".join(map(str, refs))
        if key not in self.cache:
            self.model.prepare_conditionals(str(refs[0]), exaggeration=exaggeration)
            if len(refs) > 1:
                import librosa
                import torch
                wavs = [librosa.load(str(r), sr=16000)[0] for r in refs]
                emb = torch.from_numpy(self.model.ve.embeds_from_wavs(wavs, sample_rate=16000))
                self.model.conds.t3.speaker_emb = emb.mean(axis=0, keepdim=True).to(self.model.device)
            self.cache[key] = self.model.conds
        return self.cache[key]

    def synthesize(self, text: str, refs: list[Path] | None = None, speed: float = 1.0,
                   exaggeration: float = 0.5, cfg: float = 0.5, language: str = "es", pausa: float = 1.0) -> bytes:
        import numpy as np

        self.model.conds = self._conds_for(refs, exaggeration)
        parts = []
        for frase, silencio in frases(text):
            wav = None
            for intento in (frase, frase + " …", frase.rstrip(".!?…;:") + "."):
                try:  # el modelo falla a veces con alguna frase concreta (IndexError interno): se reintenta
                    wav = self.model.generate(intento, language_id=language, exaggeration=exaggeration, cfg_weight=cfg)
                    break
                except (IndexError, RuntimeError) as e:
                    print(f"[motor] reintento por {e.__class__.__name__} en: {frase[:60]!r}", flush=True)
            if wav is None:
                continue  # se salta la frase antes que perder toda la lección
            voz = recortar_silencio(wav.squeeze(0).cpu().numpy().astype(np.float32), self.sr)
            voz = cambiar_ritmo(voz, self.sr, speed)
            # las pausas se alargan cuando el narrador va más lento
            parts += [voz, np.zeros(int(self.sr * silencio * pausa / max(speed, 0.5)), dtype=np.float32)]
        audio = np.concatenate(parts[:-1]) if parts else np.zeros(self.sr // 4, dtype=np.float32)
        return wav_bytes(audio, self.sr)


def load_engine():
    if os.getenv("ESTUDIO_MOTOR") == "demo":
        return DemoEngine()
    try:
        return ChatterboxEngine()
    except Exception as e:  # sin GPU, sin modelo o sin dependencias: modo demo
        print(f"[motor] Chatterbox no disponible ({e.__class__.__name__}: {e}); uso el motor demo.")
        return DemoEngine()
