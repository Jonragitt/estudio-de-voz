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
    """Trocea el texto en frases de como mucho `limit` caracteres (el modelo genera unos 40 s por trozo)."""
    sentences = re.split(r"(?<=[.!?…;:])\s+|\n+", text.strip())
    chunks, cur = [], ""
    for s in filter(None, (x.strip() for x in sentences)):
        while len(s) > limit:  # frase muy larga: cortar por la última coma o espacio
            cut = max(s.rfind(",", 0, limit), s.rfind(" ", 0, limit))
            cut = cut if cut > limit // 3 else limit
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(s[:cut + 1].strip())
            s = s[cut + 1:].strip()
        if cur and len(cur) + 1 + len(s) > limit:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks or [text]


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
                   exaggeration: float = 0.5, cfg: float = 0.5, language: str = "es") -> bytes:
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
                   exaggeration: float = 0.5, cfg: float = 0.5, language: str = "es") -> bytes:
        import numpy as np

        self.model.conds = self._conds_for(refs, exaggeration)
        pause = np.zeros(int(self.sr * 0.25), dtype=np.float32)
        parts = []
        for chunk in split_text(text):
            wav = self.model.generate(chunk, language_id=language, exaggeration=exaggeration, cfg_weight=cfg)
            parts += [wav.squeeze(0).cpu().numpy().astype(np.float32), pause]
        audio = np.concatenate(parts[:-1]) if parts else pause
        if abs(speed - 1.0) > 0.01:
            import librosa
            audio = librosa.effects.time_stretch(audio, rate=speed)  # cambia el ritmo sin cambiar el tono
        return wav_bytes(audio, self.sr)


def load_engine():
    if os.getenv("ESTUDIO_MOTOR") == "demo":
        return DemoEngine()
    try:
        return ChatterboxEngine()
    except Exception as e:  # sin GPU, sin modelo o sin dependencias: modo demo
        print(f"[motor] Chatterbox no disponible ({e.__class__.__name__}: {e}); uso el motor demo.")
        return DemoEngine()
