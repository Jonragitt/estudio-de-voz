"""Saca el texto narrable de cada capítulo de APUNTY (la página publicada) a un JSON para el estudio.

Uso: python tools/apunty_textos.py apunty.html salida.json
Lee la constante COUNTRIES de la página y, por capítulo, se queda con título, entradilla, apartados,
párrafos, listas, cuadros (¿Por qué?, Clave…), cronologías y glosarios. Quita pies de foto, escritura
japonesa, etiquetas de interfaz y créditos.
"""
import json
import re
import sys

from bs4 import BeautifulSoup


def _fin(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace("→", " lleva a ")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\(\s*[,;]?\s*", "(", t)
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s+([,.;:)])", r"\1", t)
    t = t.strip()
    if t and t[-1] not in ".!?…:;»\"":
        t += "."
    return t


def _texto(el) -> str:
    return el.get_text(" ", strip=True)


def capitulo(html: str) -> str:
    s = BeautifulSoup(html, "html.parser")
    for x in s.select("figure, button, .jp, .credits, p.eyebrow, p.meta"):
        x.decompose()
    guia = s.select_one('section[data-k="guia"]')
    if guia and guia.find("aside"):  # instrucciones de uso de la página: no se narran
        for x in list(guia.find("aside").find_next_siblings()):
            x.decompose()
    out: list[str] = []
    h = s.select_one("header.chap-h")
    if h:
        out += [_fin(_texto(h.h1)), _fin(_texto(h.select_one(".lede"))) if h.select_one(".lede") else ""]
        h.decompose()
    for el in s.find_all(["h2", "h3", "p", "li", "aside", "dl", "blockquote"]):
        if any(p.name in ("aside", "dl", "li", "blockquote") for p in el.parents if p is not el):
            continue
        if el.name == "aside":
            tg = el.select_one(".tg")
            etiqueta = tg.get_text(strip=True).lower() if tg else ""
            i = next((k for k, ch in enumerate(etiqueta) if ch.isalpha()), 0)
            etiqueta = etiqueta[:i] + etiqueta[i:i + 1].upper() + etiqueta[i + 1:]
            if tg:
                tg.decompose()
            cuerpo = " ".join(_fin(_texto(p)) for p in el.find_all(["p", "li"]))
            out.append(((_fin(etiqueta) + " ") if etiqueta else "") + cuerpo)
        elif el.name == "dl":
            for d in el.find_all("div", recursive=False) or [el]:
                dt, dd = d.find("dt"), d.find("dd")
                if dt and dd:
                    out.append(_fin(_texto(dt).rstrip(":") + ": " + _texto(dd)))
        elif el.name == "li":
            dt, ev = el.select_one(".dt"), el.select_one(".ev")
            out.append(_fin(f"{_texto(dt)}: {_texto(ev)}") if dt and ev else _fin(_texto(el)))
        elif el.get("data-ns") is None:
            out.append(_fin(_texto(el)))
    texto = "\n\n".join(t for t in out if t and t != ".")
    return re.sub(r"\n{3,}", "\n\n", texto)


def main(entrada: str, salida: str) -> None:
    linea = next(l for l in open(entrada, encoding="utf-8") if l.startswith("const COUNTRIES = "))
    paises = json.loads(linea[len("const COUNTRIES = "):].rstrip().rstrip(";"))
    lecciones = []
    for p in paises:
        for c in p.get("chapters", []):
            m = re.match(r"t(\d+)c(\d+)$", c["id"])
            temporada, num = (int(m[1]), int(m[2])) if m else (1, int(re.sub(r"\D", "", c["id"]) or 0))
            lecciones.append({"id": f"{p['id']}-{c['id']}", "pais": p["id"], "capitulo": c["id"],
                              "temporada": temporada, "numero": num, "titulo": c["t"], "texto": capitulo(c["html"])})
    json.dump({"lecciones": lecciones}, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(lecciones)} lecciones, {sum(len(l['texto'].split()) for l in lecciones)} palabras -> {salida}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
