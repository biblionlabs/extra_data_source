#!/usr/bin/env python3
"""
convert.py
Convierte los siguientes formatos a la estructura Rust del proyecto:

FORMATS SOPORTADOS:
- JSON (formato interno previo)
- USFM (.usfm, .txt)
- OSIS XML (.xml)
- BibliaLibre XML
- Zefania / BibleML XML
- SWORD imp-format (.imp)
- SWORD XML (osis-like)

Genera:
.cache/bibles/<bible_id>/manifest.json
.cache/bibles/<bible_id>/books/<BOOK_ID>.json
"""

import json
import unicodedata
import os
import sys
import xml.etree.ElementTree as ET
import re

from pathlib import Path
from maps import USFM_TO_NAME, BOOK_MAP

# ============================================================
# HELPERS
# ============================================================

def normalize(text):
    """Quitar acentos, minúsculas, sin espacios."""
    text = text.lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")
    text = text.replace(" ", "")
    return text

def find_book_id_from_name(name):
    """
    Nueva versión sólida:
      1. Coincidencia EXACTA por nombre largo
      2. Coincidencia EXACTA por normalización
      3. Coincidencia exacta por número + nombre
      4. Coincidencia flexible pero con prioridad correcta
    """
    name_norm = normalize(name)

    for abbr, item in BOOK_MAP.items():
        if item["long"].lower() == name.lower():
            return abbr, item

    for abbr, item in BOOK_MAP.items():
        if normalize(item["long"]) == name_norm:
            return abbr, item

    m = re.match(r"^([1-3])(.+)$", name_norm)
    if m:
        number = m.group(1)
        base = m.group(2)
        for abbr, item in BOOK_MAP.items():
            if abbr.startswith(number) and normalize(item["long"]).startswith(base):
                return abbr, item

    for abbr, item in BOOK_MAP.items():
        if name_norm in normalize(item["long"]):
            return abbr, item

    raise ValueError(f"Libro no reconocido: {name}")


# ============================================================
# LOADER DE FORMATO JSON
# ============================================================

def load_json_bible(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ============================================================
# USFM PARSER
# ============================================================

USFM_BOOK_RE = re.compile(r"^\\id\s+([A-Z1-3]{2,4})", re.IGNORECASE)
USFM_CH_RE = re.compile(r"^\\c\s+(\d+)")
USFM_VS_RE = re.compile(r"^\\v\s+(\d+)\s+(.*)")

def load_usfm(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()

    books = []
    current_book = None
    current_chapter = None

    for line in lines:
        line = line.strip()

        m = USFM_BOOK_RE.match(line)
        if m:
            book_code = m.group(1).upper()
            name = USFM_TO_NAME.get(book_code, book_code)

            if current_book:
                books.append(current_book)

            current_book = {"name": name, "chapters": []}
            current_chapter = None
            continue

        m = USFM_CH_RE.match(line)
        if m:
            n = int(m.group(1))
            current_chapter = {"number": n, "items": []}
            current_book["chapters"].append(current_chapter)
            continue

        m = USFM_VS_RE.match(line)
        if m and current_chapter:
            vn = int(m.group(1))
            text = m.group(2)
            current_chapter["items"].append({
                "type": "verse",
                "verse": vn,
                "lines": [text]
            })

    if current_book:
        books.append(current_book)

    return {"books": books}


# ============================================================
# OSIS XML LOADER
# ============================================================

def load_osis(path: Path):
    tree = ET.parse(path)
    root = tree.getroot()
    ns = {"osis": "http://www.bibletechnologies.net/2003/OSIS/namespace"}

    books = []

    for div in root.findall(".//osis:div[@type='book']", ns):
        osis_name = div.attrib.get("osisID", "Unknown")
        book = {"name": osis_name, "chapters": []}

        for chapter in div.findall("osis:chapter", ns):
            ch_num = int(chapter.attrib["osisID"].split(".")[-1])
            chapter_obj = {"number": ch_num, "items": []}

            for verse in chapter.findall("osis:verse", ns):
                v_num = int(verse.attrib["osisID"].split(".")[-1])
                text = "".join(verse.itertext()).strip()
                chapter_obj["items"].append({
                    "type": "verse",
                    "verse": v_num,
                    "lines": [text]
                })

            book["chapters"].append(chapter_obj)

        books.append(book)

    return {"books": books}


# ============================================================
# BibliaLibre / Simple XML LOADER
# ============================================================

def load_simple_bible_xml(path: Path):
    tree = ET.parse(path)
    root = tree.getroot()

    books = []

    for b in root.findall("b"):
        name = b.attrib.get("n", "")
        book = {"name": name, "chapters": []}

        for c in b.findall("c"):
            ch = int(c.attrib["n"])
            chapter = {"number": ch, "items": []}

            for v in c.findall("v"):
                vn = int(v.attrib["n"])
                text = (v.text or "").strip()
                chapter["items"].append({
                    "type": "verse",
                    "verse": vn,
                    "lines": [text]
                })

            book["chapters"].append(chapter)

        books.append(book)

    return {"books": books}


# ============================================================
# Zefania LOADER
# ============================================================

def load_zefania(path: Path):
    tree = ET.parse(path)
    root = tree.getroot()
    books = []

    for b in root.findall("BIBLEBOOK"):
        name = b.attrib.get("bname")
        book = {"name": name, "chapters": []}

        for c in b.findall("CHAPTER"):
            ch = int(c.attrib["cnumber"])
            chap = {"number": ch, "items": []}

            for v in c.findall("VERS"):
                vn = int(v.attrib["vnumber"])
                text = (v.text or "").strip()
                chap["items"].append({
                    "type": "verse",
                    "verse": vn,
                    "lines": [text]
                })

            book["chapters"].append(chap)

        books.append(book)

    return {"books": books}


# ============================================================
# SWORD imp-format
# ============================================================

IMP_RE = re.compile(r"^(\w+)\s+(\d+):(\d+)\s+(.*)$")

def load_imp(path: Path):
    books = {}
    lines = path.read_text(encoding="utf-8").splitlines()

    for line in lines:
        m = IMP_RE.match(line)
        if not m:
            continue
        code, ch, vn, text = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)

        name = USFM_TO_NAME.get(code.upper(), code)

        if name not in books:
            books[name] = {"name": name, "chapters": {}}

        if ch not in books[name]["chapters"]:
            books[name]["chapters"][ch] = {"number": ch, "items": []}

        books[name]["chapters"][ch]["items"].append({
            "type": "verse",
            "verse": vn,
            "lines": [text]
        })

    # convertir dict → lista
    final = []
    for name, data in books.items():
        final.append({
            "name": name,
            "chapters": list(data["chapters"].values())
        })

    return {"books": final}


# ============================================================
# DETECTOR AUTOMÁTICO DE FORMATO
# ============================================================

def detect_format(path: Path):
    ext = path.suffix.lower()
    if ext == ".json": return "json"
    if ext in (".usfm", ".txt"): return "usfm"
    if ext == ".imp": return "imp"
    if ext == ".xml":
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "<osis" in text: return "osis"
        if "<XMLBIBLE" in text: return "zefania"
        if "<bible" in text and "<b " in text: return "simplexml"
        return "simplexml"
    print(f"No se reconoce formato de: {path}")
    return None


def load_any(path: Path):
    fmt = detect_format(path)

    if fmt == "json":
        return load_json_bible(path)
    if fmt == "usfm":
        return load_usfm(path)
    if fmt == "osis":
        return load_osis(path)
    if fmt == "simplexml":
        return load_simple_bible_xml(path)
    if fmt == "zefania":
        return load_zefania(path)
    if fmt == "imp":
        return load_imp(path)

    return None


# ============================================================
# DIRECTORIO: unir resultados de múltiples archivos
# ============================================================

def load_from_directory(dirpath: Path):
    all_books = {}

    for file in dirpath.iterdir():
        if file.is_file():
            print("→ cargando:", file.name)
            data = load_any(file)

            if data is None:
                continue

            for book in data["books"]:
                name = book["name"]
                if name not in all_books:
                    all_books[name] = book
                else:
                    # fusionar capítulos sin sobrescribir
                    existing = all_books[name]
                    existing_chapters = {c["number"]: c for c in existing["chapters"]}
                    for ch in book["chapters"]:
                        if ch["number"] not in existing_chapters:
                            existing["chapters"].append(ch)

    return {"books": list(all_books.values())}


# ============================================================
# CONVERSION → RUST BOOK
# ============================================================

def convert_chapter_item(it):
    return [" ".join(it["lines"])]

def convert_book(book):
    book_id, item = find_book_id_from_name(book["name"])

    return book_id, {
        "book": book_id,
        "name": item,
        "contents": [
            [convert_chapter_item(v) for v in chap["items"]]
            for chap in book["chapters"]
        ]
    }


# ============================================================
# MANIFEST
# ============================================================

def build_manifest(books):
    return {
        "book_names": {bid: b["name"] for bid, b in books.items()},
        "chapter_headings": {},
        "sections": {}
    }


# ============================================================
# MAIN
# ============================================================

def main(input_path: Path, output_path: Path):
    if input_path.is_dir():
        print("→ Leyendo directorio completo…")
        source = load_from_directory(input_path)
    else:
        print("→ Leyendo archivo…")
        source = load_any(input_path)
        if source is None:
            return

    output_path.mkdir(parents=True, exist_ok=True)

    books_dir = output_path / "books"
    books_dir.mkdir(exist_ok=True)

    converted = {}

    for book in source["books"]:
        try:
            book_id, rust_book = convert_book(book)
            converted[book_id] = rust_book

            with open(books_dir / f"{book_id}.json", "w", encoding="utf-8") as f:
                json.dump(rust_book, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"⚠️  Error con libro '{book['name']}': {e}")

    manifest = build_manifest(converted)
    with open(output_path / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("✔ Conversión completa.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python convert.py <archivo|directorio> <salida>")
        sys.exit(1)

    main(Path(sys.argv[1]), Path(sys.argv[2]))
