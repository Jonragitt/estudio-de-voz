"""Motor remoto: la web y los audios se quedan en el portátil y la voz se genera en una GPU de Kaggle.

El cuaderno de Kaggle (tools/kaggle_worker.py) abre su propio enlace de Cloudflare y lo anuncia en un
tema secreto de ntfy.sh. El portátil lee ese enlace y le manda los trabajos con una clave; nada del
portátil queda abierto a internet. Mientras el estudio esté abierto, el portátil le da un «latido» cada
30 s; si deja de llegar, Kaggle se apaga solo y no gasta horas de GPU.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import HTTPException

LATIDO = 30


class RemoteEngine:
    name = "kaggle"

    def __init__(self, voices: Path, token: str, tema: str) -> None:
        self.voices, self.token, self.tema = voices, token, tema
        self.url: str | None = None
        self.vivo = 0.0  # última vez que Kaggle respondió
        self.arranque = time.time()
        threading.Thread(target=self._vigilar, daemon=True).start()

    @property
    def ready(self) -> bool:
        return self.url is not None and time.time() - self.vivo < LATIDO * 3

    def _pedir(self, metodo: str, ruta: str, datos: bytes | None = None, tipo: str = "application/json",
               espera: int = 60) -> tuple[int, bytes]:
        req = urllib.request.Request(self.url + ruta, data=datos, method=metodo,
                                     headers={"X-Token": self.token, "Content-Type": tipo})
        try:
            with urllib.request.urlopen(req, timeout=espera) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def _vigilar(self) -> None:
        """Busca el enlace que anuncia Kaggle y luego le da un latido cada 30 s."""
        while True:
            try:
                if self.url is None:
                    with urllib.request.urlopen(f"https://ntfy.sh/{self.tema}/json?poll=1&since=all",  # el tema es nuevo en cada arranque
                                                timeout=30) as r:
                        for linea in r.read().decode().splitlines():
                            msg = json.loads(linea).get("message", "")
                            if msg.startswith("https://") and msg.endswith(".trycloudflare.com"):
                                self.url = msg
                if self.url and self._pedir("GET", "/salud")[0] == 200:
                    self.vivo = time.time()
            except Exception as e:  # sin red o Kaggle aún arrancando: se vuelve a probar
                print("[kaggle]", e.__class__.__name__, e)
            time.sleep(LATIDO if self.url else 15)

    def synthesize(self, text: str, refs: list[Path] | None = None, speed: float = 1.0,
                   exaggeration: float = 0.5, cfg: float = 0.5, language: str = "es", pausa: float = 1.0) -> bytes:
        """Las lecciones largas se parten en trozos que Kaggle genera de dos en dos (tiene dos GPU T4) y
        luego se unen con la pausa que tocaba entre ellos."""
        if not self.ready:
            minutos = int((time.time() - self.arranque) // 60)
            raise HTTPException(503, "La GPU de Kaggle aún se está encendiendo (tarda unos 10 minutos; "
                                     f"lleva {minutos}). Prueba de nuevo en un rato.")
        trozos = trocear(text)
        if len(trozos) == 1:
            return self._generar(text, refs, speed, exaggeration, cfg, language, pausa)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(2) as ex:
            wavs = list(ex.map(lambda t: self._generar(t[0], refs, speed, exaggeration, cfg, language, pausa), trozos))
        return unir_wavs(wavs, [p * pausa / max(speed, 0.5) for _, p in trozos])

    def _generar(self, text: str, refs: list[Path] | None, speed: float, exaggeration: float, cfg: float,
                 language: str, pausa: float) -> bytes:
        trabajo = json.dumps({"text": text, "refs": [r.name for r in refs or []], "speed": speed,
                              "exaggeration": exaggeration, "cfg": cfg, "language": language, "pausa": pausa}).encode()
        estado, cuerpo = self._pedir("POST", "/sintetizar", trabajo)
        if estado == 409:  # a Kaggle le faltan grabaciones de la voz: se las mando y repito
            for nombre in json.loads(cuerpo)["faltan"]:
                self._pedir("PUT", f"/ref/{nombre}", (self.voices / nombre).read_bytes(), "application/octet-stream", 120)
            estado, cuerpo = self._pedir("POST", "/sintetizar", trabajo)
        if estado != 200:
            raise HTTPException(502, f"Kaggle no aceptó el trabajo ({estado}): {cuerpo[:200].decode(errors='replace')}")
        tid = json.loads(cuerpo)["id"]
        # el audio se recoge a trozos de espera: Cloudflare corta las peticiones de más de 100 s
        # una lección larga puede tardar más de media hora: se espera mientras Kaggle siga vivo
        fin = time.time() + 4 * 3600
        while time.time() < fin and time.time() - self.vivo < LATIDO * 6:
            try:
                estado, cuerpo = self._pedir("GET", f"/resultado/{tid}", espera=90)
            except OSError:  # un corte de red momentáneo no tira el trabajo
                time.sleep(10)
                continue
            if estado == 200:
                self.vivo = time.time()
                return cuerpo
            if estado != 202:
                raise HTTPException(500, f"Error en Kaggle: {cuerpo[:300].decode(errors='replace')}")
            self.vivo = time.time()  # «aún no» también es señal de que Kaggle sigue trabajando
            time.sleep(1)
        raise HTTPException(504, "Kaggle dejó de responder antes de terminar el audio.")


TROZO = 1500  # letras por trozo (unos 2 minutos de audio)


def trocear(text: str) -> list[tuple[str, float]]:
    """Agrupa párrafos enteros en trozos de unas TROZO letras; devuelve cada trozo y la pausa que va detrás.

    Solo se corta al final de un párrafo, para que al unir los trozos suene la pausa larga de cambio de
    párrafo. Si un párrafo es enorme, se corta al final de una frase."""
    from .engine import PAUSAS, frases
    if len(text) <= TROZO * 1.5:
        return [(text, 0.0)]
    trozos: list[tuple[str, float]] = []
    actual, largo = "", 0
    for frase, pausa in frases(text):
        actual += frase + ("\n" if pausa == PAUSAS["\n"] else " ")
        largo += len(frase)
        if (largo >= TROZO and pausa == PAUSAS["\n"]) or largo >= TROZO * 2.5:
            trozos.append((actual.strip(), pausa))
            actual, largo = "", 0
    if actual.strip():
        if trozos and largo < TROZO // 3:  # un final muy corto va con el trozo anterior
            trozos[-1] = (trozos[-1][0] + "\n" + actual.strip(), 0.0)
        else:
            trozos.append((actual.strip(), 0.0))
    return trozos


def unir_wavs(wavs: list[bytes], silencios: list[float]) -> bytes:
    """Une WAV de 16 bits con el mismo formato, con `silencios[i]` segundos detrás del trozo i."""
    import io
    import wave
    salida = io.BytesIO()
    with wave.open(salida, "wb") as out:
        for i, w in enumerate(wavs):
            with wave.open(io.BytesIO(w)) as trozo:
                if i == 0:
                    out.setparams(trozo.getparams())
                out.writeframes(trozo.readframes(trozo.getnframes()))
                if i < len(wavs) - 1:
                    out.writeframes(b"\0" * (int(trozo.getframerate() * silencios[i]) * trozo.getsampwidth()))
    return salida.getvalue()


def activar(voices: Path) -> RemoteEngine | None:
    """Si el estudio se arrancó con ESTUDIO_MOTOR=kaggle, crea el motor remoto."""
    if os.getenv("ESTUDIO_MOTOR") != "kaggle":
        return None
    return RemoteEngine(voices, os.environ["ESTUDIO_TOKEN"], os.environ["ESTUDIO_TEMA"])
