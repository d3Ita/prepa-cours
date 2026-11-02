#!/usr/bin/env python3
"""Affiche le texte d'un fichier pptx, docx, odp ou odt (bibliothèque standard seulement).

Usage : extraire_texte.py fichier
"""
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def nom(el):
    return el.tag.rsplit("}", 1)[-1]


def paragraphes(xml, odf):
    for el in ET.fromstring(xml).iter():
        if nom(el) in ("p", "h"):
            if odf:
                texte = "".join(el.itertext())
            else:
                texte = "".join(t.text or "" for t in el.iter() if nom(t) == "t")
            if texte.strip():
                yield texte


def numero(chemin):
    return int(re.search(r"(\d+)\.xml$", chemin).group(1))


def extraire(fichier):
    ext = Path(fichier).suffix.lower()
    with zipfile.ZipFile(fichier) as z:
        if ext == ".docx":
            return list(paragraphes(z.read("word/document.xml"), False))
        if ext in (".odt", ".odp"):
            return list(paragraphes(z.read("content.xml"), True))
        if ext == ".pptx":
            sortie = []
            noms = set(z.namelist())
            diapos = [n for n in noms if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
            for chemin in sorted(diapos, key=numero):
                sortie.append(f"--- Diapo {numero(chemin)} ---")
                sortie += paragraphes(z.read(chemin), False)
            for chemin in sorted((n for n in noms if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)),
                                 key=numero):
                sortie.append(f"--- Notes {numero(chemin)} ---")
                sortie += paragraphes(z.read(chemin), False)
            return sortie
    sys.exit(f"Format non pris en charge : {ext}. Enregistrez le fichier en pptx, docx, odp, odt ou PDF.")


if __name__ == "__main__":
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        print("\n".join(extraire(sys.argv[1])))
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
        sys.exit(f"Lecture impossible de {sys.argv[1]} : {e}")
