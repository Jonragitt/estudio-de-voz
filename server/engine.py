"""Motores de voz del Estudio.

- ChatterboxEngine: el motor real (licencia MIT, permite uso comercial). Se usa si está instalado.
- DemoEngine: genera un tono de prueba para poder usar la web sin GPU ni modelo instalado.
"""
from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path


class DemoEngine:
    name = "demo"
    ready = True

    def synthesize(self, text: str, ref_audio: Path | None = None, speed: float = 1.0,
                   exaggeration: float = 0.5, cfg: float = 0.5) -> bytes:
        """Devuelve un WAV con un pitido por palabra, para probar la interfaz."""
        rate = 22050
        words = max(1, len(text.split()))
        base = 180 + 220 * exaggeration
        frames = bytearray()
        beat = int(rate * 0.18 / max(speed, 0.25))
        gap = int(rate * 0.06 / max(speed, 0.25))
        for i in range(min(words, 200)):
            f = base * (1 + 0.12 * math.sin(i))
            for n in range(beat):
                env = math.sin(math.pi * n / beat)
                frames += struct.pack("<h", int(9000 * env * math.sin(2 * math.pi * f * n / rate)))
            frames += b"\x00\x00" * gap
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(frames))
        return buf.getvalue()


class ChatterboxEngine:
    name = "chatterbox"

    def __init__(self) -> None:
        import torch  # noqa: F401
        from chatterbox.tts import ChatterboxTTS

        import torch as _t
        device = "cuda" if _t.cuda.is_available() else "cpu"
        self.model = ChatterboxTTS.from_pretrained(device=device)
        self.ready = True

    def synthesize(self, text: str, ref_audio: Path | None = None, speed: float = 1.0,
                   exaggeration: float = 0.5, cfg: float = 0.5) -> bytes:
        import torchaudio

        wav = self.model.generate(
            text,
            audio_prompt_path=str(ref_audio) if ref_audio else None,
            exaggeration=exaggeration,
            cfg_weight=cfg,
        )
        if speed != 1.0:
            import torchaudio.functional as F
            wav = F.resample(wav, int(self.model.sr * speed), self.model.sr)
        buf = io.BytesIO()
        torchaudio.save(buf, wav, self.model.sr, format="wav")
        return buf.getvalue()


def load_engine():
    try:
        return ChatterboxEngine()
    except Exception as e:  # sin GPU, sin modelo o sin dependencias: modo demo
        print(f"[motor] Chatterbox no disponible ({e.__class__.__name__}); uso el motor demo.")
        return DemoEngine()
