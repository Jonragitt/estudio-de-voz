"""Prepara el texto para que el modelo lo lea bien en español.

Convierte en palabras lo que los modelos de voz suelen leer mal: números (también con separador de miles),
porcentajes, símbolos, unidades, siglos en números romanos y abreviaturas. Quita las rayas y los
paréntesis (los cambia por pausas) y las vocales largas de las palabras japonesas (Honshū → Honshu).
"""
from __future__ import annotations

import re

_UNI = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
        "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve",
        "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis",
        "veintisiete", "veintiocho", "veintinueve"]
_DEC = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
_CEN = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos",
        "setecientos", "ochocientos", "novecientos"]


def _menor_mil(n: int) -> str:
    if n == 100:
        return "cien"
    c, r = divmod(n, 100)
    partes = [_CEN[c]] if c else []
    if r < 30:
        if r or not c:
            partes.append(_UNI[r])
    else:
        d, u = divmod(r, 10)
        partes.append(_DEC[d] + (f" y {_UNI[u]}" if u else ""))
    return " ".join(p for p in partes if p)


def numero(n: int) -> str:
    """Número entero en palabras: 6852 → «seis mil ochocientos cincuenta y dos»."""
    if n < 0:
        return "menos " + numero(-n)
    if n < 1000:
        return _menor_mil(n)
    for valor, sing, plur in ((10**12, "un billón", "billones"), (10**6, "un millón", "millones")):
        if n >= valor:
            q, r = divmod(n, valor)
            cab = sing if q == 1 else f"{_apocope(numero(q))} {plur}"
            return cab + (f" {numero(r)}" if r else "")
    q, r = divmod(n, 1000)
    cab = "mil" if q == 1 else f"{_apocope(numero(q))} mil"
    return cab + (f" {numero(r)}" if r else "")


def _apocope(s: str) -> str:
    """«veintiuno mil» → «veintiún mil», «uno millones» → «un millones»."""
    s = re.sub(r"veintiuno$", "veintiún", s)
    return re.sub(r"\buno$", "un", s)


def _decimal(entero: str, dec: str) -> str:
    dec_txt = " ".join(_UNI[int(d)] for d in dec) if dec.startswith("0") else numero(int(dec))
    return f"{numero(int(entero))} coma {dec_txt}"


_ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _romano(s: str) -> int | None:
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMANOS.get(ch)
        if v is None:
            return None
        total += -v if v < prev else v
        prev = max(prev, v)
    return total or None


UNIDADES = {
    "km²": ("kilómetro cuadrado", "kilómetros cuadrados"), "km2": ("kilómetro cuadrado", "kilómetros cuadrados"),
    "m²": ("metro cuadrado", "metros cuadrados"), "km/h": ("kilómetro por hora", "kilómetros por hora"),
    "km": ("kilómetro", "kilómetros"), "cm": ("centímetro", "centímetros"), "mm": ("milímetro", "milímetros"),
    "kg": ("kilo", "kilos"), "°C": ("grado", "grados"), "ºC": ("grado", "grados"), "°": ("grado", "grados"),
    "m": ("metro", "metros"), "g": ("gramo", "gramos"), "t": ("tonelada", "toneladas"), "h": ("hora", "horas"),
    "€": ("euro", "euros"), "$": ("dólar", "dólares"), "¥": ("yen", "yenes"),
}
_UNI_RE = "|".join(re.escape(u) for u in sorted(UNIDADES, key=len, reverse=True))

ABREVIATURAS = [
    (r"\ba\.\s?C\.", "antes de Cristo"), (r"\bd\.\s?C\.", "después de Cristo"),
    (r"\bs\.\s?(?=[IVXLC]+\b)", "siglo "), (r"\bss\.\s?(?=[IVXLC]+\b)", "siglos "),
    (r"\bp\.\s?ej\.", "por ejemplo"), (r"\betc\.", "etcétera"), (r"\bEE\.\s?UU\.", "Estados Unidos"),
    (r"\bn\.º\s?", "número "), (r"\bnº\s?", "número "),
    (r"\bapr?ox\.", "aproximadamente"), (r"\bh\.\s?(?=\d)", "hacia el "), (r"\bc\.\s?(?=\d)", "hacia el "),
]

SIMBOLOS = [("≈", " aproximadamente "), ("~", " aproximadamente "), ("±", " más o menos "),
            ("≥", " mayor o igual que "), ("≤", " menor o igual que "), ("→", ", "), ("&", " y "),
            ("+", " más "), ("×", " por "), ("·", ", "), ("…", "..."), ("«", ""), ("»", ""),
            ("“", ""), ("”", ""), ('"', "")]

VOCALES_LARGAS = str.maketrans({"ā": "a", "ē": "e", "ī": "i", "ō": "o", "ū": "u", "Ā": "A", "Ē": "E",
                                "Ī": "I", "Ō": "O", "Ū": "U", "ô": "o", "û": "u", "â": "a", "ê": "e", "î": "i"})


PRONUNCIACIONES_INICIALES = [
    # nombres japoneses: en español la h suena como j y la j japonesa como «y»
    {"palabra": "Hokkaido", "lectura": "Jokaido"}, {"palabra": "Honshu", "lectura": "Jonshu"},
    {"palabra": "Kyushu", "lectura": "Kiushu"}, {"palabra": "Heian", "lectura": "Jeián"},
    {"palabra": "Heian-kyo", "lectura": "Jeián Kio"}, {"palabra": "Hiroshima", "lectura": "Jiroshima"},
    {"palabra": "Meiji", "lectura": "Meiyi"}, {"palabra": "Fujiwara", "lectura": "Fuyiwara"},
    {"palabra": "Fuji", "lectura": "Fuyi"}, {"palabra": "Jomon", "lectura": "Yomon"},
    {"palabra": "Kyoto", "lectura": "Kioto"}, {"palabra": "Tokyo", "lectura": "Tokio"},
    {"palabra": "Heisei", "lectura": "Jeisei"}, {"palabra": "Shogun", "lectura": "Sogún"},
]


def aplicar_pronunciaciones(t: str, diccionario: list[dict] | None) -> str:
    """Cambia palabras por cómo deben sonar. Las más largas primero (Heian-kyo antes que Heian)."""
    for e in sorted(diccionario or [], key=lambda e: -len(e.get("palabra", ""))):
        palabra = (e.get("palabra") or "").strip().translate(VOCALES_LARGAS)
        lectura = (e.get("lectura") or "").strip()
        if palabra and lectura:
            t = re.sub(rf"(?<![\wáéíóúñü]){re.escape(palabra)}(?![\wáéíóúñü])", lectura, t, flags=re.IGNORECASE)
    return t


def normalizar(texto: str, idioma: str = "es", diccionario: list[dict] | None = None) -> str:
    """Devuelve el texto listo para leer en voz alta."""
    t = aplicar_pronunciaciones(texto.translate(VOCALES_LARGAS), diccionario)
    if idioma != "es":
        return re.sub(r"\s+", " ", t).strip()

    # intervalos: «794–1185» → «794 a 1185»
    t = re.sub(r"(\d)\s*[–—-]\s*(\d)", r"\1 a \2", t)
    # rayas y paréntesis → pausas
    t = re.sub(r"\s*[—–]\s*", ", ", t)
    t = re.sub(r"\s*\(\s*", ", ", t)
    t = re.sub(r"\s*\)\s*", ", ", t)
    t = re.sub(r"\s*\[\s*|\s*\]\s*", ", ", t)

    for patron, rep in ABREVIATURAS:
        t = re.sub(patron, rep, t)

    # siglos y reyes en números romanos: «siglo XII» → «siglo doce»
    def _sig(m):
        n = _romano(m.group(2))
        return f"{m.group(1)} {numero(n)}" if n else m.group(0)
    t = re.sub(r"\b(siglos?|Siglos?|milenio|era|periodo)\s+([IVXLCDM]+)\b", _sig, t)

    # separador de miles: «14 000», «14.000», «14 000» → 14000 (solo si van en grupos de tres)
    t = re.sub(r"(?<![\d,])(\d{1,3})((?:[    .]\d{3})+)(?!\d|,\d)",
               lambda m: m.group(1) + re.sub(r"\D", "", m.group(2)), t)

    # porcentajes
    t = re.sub(r"(\d+(?:,\d+)?)\s*%", r"\1 por ciento", t)

    for s, rep in SIMBOLOS:
        t = t.replace(s, rep)

    # números con unidad: «3000 km» → «tres mil kilómetros»
    def _unidad(m):
        n_txt, u = m.group(1), m.group(2)
        sing, plur = UNIDADES[u]
        palabra = sing if n_txt in ("1", "1,0") else plur
        return f"{n_txt} {palabra}"
    t = re.sub(rf"(\d+(?:,\d+)?)\s*({_UNI_RE})(?![\wáéíóú])", _unidad, t)

    t = re.sub(r"\bkm[²2](?!\w)", "kilómetros cuadrados", t)
    t = re.sub(r"\bkm\b", "kilómetros", t)
    # decimales y enteros
    t = re.sub(r"\b(\d+),(\d+)\b", lambda m: _decimal(m.group(1), m.group(2)), t)
    t = re.sub(r"\b\d+\b", lambda m: numero(int(m.group(0))) if len(m.group(0)) <= 15 else m.group(0), t)
    t = re.sub(r"\buno (?=(kilómetro|metro|kilo|euro|grado|hora|gramo|tonelada|dólar|yen|centímetro|milímetro|millón|por ciento))", "un ", t)
    t = re.sub(r"\bveintiuno (kilómetros|metros|kilos|euros|grados|horas)", r"veintiún \1", t)

    # limpieza de puntuación
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r",\s*([,.;:])", r"\1", t)
    t = re.sub(r"([.;:!?]),", r"\1", t)
    t = re.sub(r"^,\s*", "", t.strip())
    return t
