#!/usr/bin/env python3

"""
Convierte el JSON fuente a la estructura usada por el proyecto Rust principal:

.cache/
  bibles/
    <bible>/
      manifest.json
      books/
      <BOOK_USFM>.json

Uso:
    python convert.py /ruta/a/biblia
"""

import json
import unicodedata
import os
import sys
from pathlib import Path

# ============================================================
# MAPA DE ABREVIACIONES (ID → Nombre largo)
# ============================================================

BOOK_MAP = {
"1ch":{"normal":"1 Crónicas","long":"1 Crónicas","abbrev":"1 Crón"},"1co":{"normal":"1 Corintios","long":"1 Corintios","abbrev":"1 Cori"},"1jn":{"normal":"1 Juan","long":"1 Juan","abbrev":"1 Juan"},"1ki":{"normal":"1 Reyes","long":"1 Reyes","abbrev":"1 Reye"},"1pe":{"normal":"1 Pedro","long":"1 Pedro","abbrev":"1 Pedr"},"1sa":{"normal":"1 Samuel","long":"1 Samuel","abbrev":"1 Samu"},"1th":{"normal":"1 Tesalonicenses","long":"1 Tesalonicenses","abbrev":"1 Tesa"},"1ti":{"normal":"1 Timoteo","long":"1 Timoteo","abbrev":"1 Timo"},"2ch":{"normal":"2 Crónicas","long":"2 Crónicas","abbrev":"2 Crón"},"2co":{"normal":"2 Corintios","long":"2 Corintios","abbrev":"2 Cori"},"2jn":{"normal":"2 Juan","long":"2 Juan","abbrev":"2 Juan"},"2ki":{"normal":"2 Reyes","long":"2 Reyes","abbrev":"2 Reye"},"2pe":{"normal":"2 Pedro","long":"2 Pedro","abbrev":"2 Pedr"},"2sa":{"normal":"2 Samuel","long":"2 Samuel","abbrev":"2 Samu"},"2th":{"normal":"2 Tesalonicenses","long":"2 Tesalonicenses","abbrev":"2 Tesa"},"2ti":{"normal":"2 Timoteo","long":"2 Timoteo","abbrev":"2 Timo"},"3jn":{"normal":"3 Juan","long":"3 Juan","abbrev":"3 Juan"},"act":{"normal":"Hechos","long":"Hechos","abbrev":"Hechos"},"amo":{"normal":"Amós","long":"Amós","abbrev":"Amós"},"col":{"normal":"Colosenses","long":"Colosenses","abbrev":"Colose"},"dan":{"normal":"Daniel","long":"Daniel","abbrev":"Daniel"},"deu":{"normal":"Deuteronomio","long":"Deuteronomio","abbrev":"Deuter"},"ecc":{"normal":"Eclesiastés","long":"Eclesiastés","abbrev":"Eclesi"},"eph":{"normal":"Efesios","long":"Efesios","abbrev":"Efesio"},"est":{"normal":"Ester","long":"Ester","abbrev":"Ester"},"exo":{"normal":"Éxodo","long":"Éxodo","abbrev":"Éxodo"},"ezk":{"normal":"Ezequiel","long":"Ezequiel","abbrev":"Ezequi"},"ezr":{"normal":"Esdras","long":"Esdras","abbrev":"Esdras"},"gal":{"normal":"Gálatas","long":"Gálatas","abbrev":"Gálata"},"gen":{"normal":"Génesis","long":"Génesis","abbrev":"Génesi"},"hab":{"normal":"Habacuc","long":"Habacuc","abbrev":"Habacu"},"hag":{"normal":"Hageo","long":"Hageo","abbrev":"Hageo"},"heb":{"normal":"Hebreos","long":"Hebreos","abbrev":"Hebreo"},"hos":{"normal":"Oseas","long":"Oseas","abbrev":"Oseas"},"isa":{"normal":"Isaías","long":"Isaías","abbrev":"Isaías"},"jas":{"normal":"Santiago","long":"Santiago","abbrev":"Santia"},"jdg":{"normal":"Jueces","long":"Jueces","abbrev":"Jueces"},"jer":{"normal":"Jeremías","long":"Jeremías","abbrev":"Jeremí"},"jhn":{"normal":"Juan","long":"Juan","abbrev":"Juan"},"job":{"normal":"Job","long":"Job","abbrev":"Job"},"jol":{"normal":"Joel","long":"Joel","abbrev":"Joel"},"jon":{"normal":"Jonás","long":"Jonás","abbrev":"Jonás"},"jos":{"normal":"Josué","long":"Josué","abbrev":"Josué"},"jud":{"normal":"Judas","long":"Judas","abbrev":"Judas"},"lam":{"normal":"Lamentaciones","long":"Lamentaciones","abbrev":"Lament"},"lev":{"normal":"Levítico","long":"Levítico","abbrev":"Levíti"},"luk":{"normal":"Lucas","long":"Lucas","abbrev":"Lucas"},"mal":{"normal":"Malaquías","long":"Malaquías","abbrev":"Malaqu"},"mat":{"normal":"Mateo","long":"Mateo","abbrev":"Mateo"},"mic":{"normal":"Miqueas","long":"Miqueas","abbrev":"Miquea"},"mrk":{"normal":"Marcos","long":"Marcos","abbrev":"Marcos"},"nam":{"normal":"Nahum","long":"Nahum","abbrev":"Nahum"},"neh":{"normal":"Nehemías","long":"Nehemías","abbrev":"Nehemí"},"num":{"normal":"Números","long":"Números","abbrev":"Número"},"oba":{"normal":"Abdías","long":"Abdías","abbrev":"Abdías"},"phm":{"normal":"Filemón","long":"Filemón","abbrev":"Filemó"},"php":{"normal":"Filipenses","long":"Filipenses","abbrev":"Filipe"},"pro":{"normal":"Proverbios","long":"Proverbios","abbrev":"Prover"},"psa":{"normal":"Salmos","long":"Salmos","abbrev":"Salmos"},"rev":{"normal":"Apocalipsis","long":"Apocalipsis","abbrev":"Apocal"},"rom":{"normal":"Romanos","long":"Romanos","abbrev":"Romano"},"rut":{"normal":"Rut","long":"Rut","abbrev":"Rut"},"sng":{"normal":"Cantares","long":"Cantares","abbrev":"Cantar"},"tit":{"normal":"Tito","long":"Tito","abbrev":"Tito"},"zec":{"normal":"Zacarías","long":"Zacarías","abbrev":"Zacarí"},"zep":{"normal":"Sofonías","long":"Sofonías","abbrev":"Sofoní"}
}

def normalize(texto):
    if texto.count(' '):
        s = texto.split()
        if not s[0].isdigit():
            texto = "".join(s[1:])
    return ''.join(c for c in unicodedata.normalize('NFD', texto) 
                  if unicodedata.category(c) != 'Mn')

# ============================================================
# FUNCIÓN PARA MAPEAR LOS USFM A NUESTRAS ABREVIACIONES
# ============================================================

def find_book_id_from_name(name):
    """
    Busca una abreviación por nombre largo.
    La RVR1960 trae "name": "Génesis", "Juan", etc.
    """
    for abbr, item in BOOK_MAP.items():
        if normalize(name.lower()) in normalize(item["long"].lower()):
            return {"id": abbr, "item": {"long": item["long"], "normal": item["normal"], "abbrev": item["abbrev"]}}
    raise ValueError(f"No se encontró abreviación para: {item.long}")


# ============================================================
# CONVERTIR UN ITEM DEL CAPÍTULO → ESQUEMA Content (Rust)
# ============================================================

def convert_chapter_item(item):
    t = item["type"]
    lines = item["lines"]

    if t == "verse":
        # unir las líneas del versículo
        return [" ".join(lines)]

    # headings
    if t in ["heading1", "heading2", "section1", "section2", "label"]:
        level = {
            "heading1": 1,
            "heading2": 2,
            "section1": 1,
            "section2": 2,
            "label": 1,
        }.get(t, 1)

        text = " ".join(lines)
        return [{
            "Heading": {
                "type": "heading",
                "contents": text,
                "level": level
            }
        }]

    # fallback
    return [" ".join(lines)]


# ============================================================
# PROCESA UN LIBRO COMPLETO
# ============================================================

def convert_book(book):
    book_name = book["name"]
    book_mapped = find_book_id_from_name(book_name)
    book_id = book_mapped["id"]
    book_item = book_mapped["item"]

    rust_book = {
        "book": book_id,
        "name": {
            "normal": book_item["normal"],
            "long": book_item["long"],
            "abbrev": book_item["abbrev"]
        },
        "contents": []
    }

    for chapter in book["chapters"]:
        chapter_contents = []

        for item in chapter["items"]:
            converted = convert_chapter_item(item)
            chapter_contents.append(converted)

        rust_book["contents"].append(chapter_contents)

    return book_id, rust_book


# ============================================================
# PROCESA TODA LA BIBLIA
# ============================================================

def build_manifest(books):
    """
    Construye el BibleVariant estándar.
    Usamos solo book_names (normal, long, abbrev)
    Las secciones y headings se dejan vacías por ahora.
    """

    manifest = {
        "book_names": {},
        "chapter_headings": {},
        "sections": {}
    }

    for book_id, book_data in books.items():
        manifest["book_names"][book_id] = book_data["name"]

    return manifest


# ============================================================
# MAIN
# ============================================================

def main(source_file: Path, output_root: Path):
    with open(source_file, "r", encoding="utf-8") as f:
        source = json.load(f)

    books_dir = output_root / "books"
    books_dir.mkdir(parents=True, exist_ok=True)

    converted_books = {}

    for book in source["books"]:
        book_id, converted = convert_book(book)
        converted_books[book_id] = converted

        # guardar el libro
        with open(books_dir / f"{book_id}.json", "w", encoding="utf-8") as f:
            json.dump(converted, f, ensure_ascii=False, indent=2)

    # crear manifesto
    manifest = build_manifest(converted_books)

    with open(output_root / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("Conversión completa.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python convert.py /ruta/a/biblia")
        sys.exit(1)
    infile = Path(sys.argv[1])
    output_root = Path(sys.argv[2])
    if not infile.exists():
        print(f"Archivo no encontrado: {infile}")
        sys.exit(2)
    main(infile, output_root)
