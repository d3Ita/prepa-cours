#!/usr/bin/env python3
"""Affiche le texte d'un fichier txt, md, docx, odt, pptx ou odp (bibliothèque standard seulement).

Les titres des documents Word et LibreOffice sont préfixés par « ## » pour montrer le plan du cours.

Usage : extraire_texte.py fichier
"""
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

FORMATS = (".txt", ".md", ".docx", ".odt", ".pptx", ".odp")
STYLE_TITRE = re.compile(r"heading|titre|title", re.IGNORECASE)


def nom(el):
    return el.tag.rsplit("}", 1)[-1]


def est_titre(el, odf):
    if odf:
        return nom(el) == "h"
    return any(nom(s) == "pStyle" and any(STYLE_TITRE.match(v) for v in s.attrib.values())
               for s in el.iter())


def paragraphes(xml, odf):
    for el in ET.fromstring(xml).iter():
        if nom(el) in ("p", "h"):
            if odf:
                texte = "".join(el.itertext())
            else:
                texte = "".join(t.text or "" for t in el.iter() if nom(t) == "t")
            if texte.strip():
                yield f"## {texte}" if est_titre(el, odf) else texte


def numero(chemin):
    return int(re.search(r"(\d+)\.xml$", chemin).group(1))


def lire_texte(fichier):
    brut = Path(fichier).read_bytes()
    try:
        return brut.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        # Les fichiers texte enregistrés sous Windows sont souvent dans cet encodage.
        return brut.decode("cp1252", errors="replace").splitlines()


def extraire(fichier):
    ext = Path(fichier).suffix.lower()
    if ext not in FORMATS:
        sys.exit(f"Format non pris en charge : {ext or 'sans extension'}. "
                 "Enregistrez le fichier en docx, odt ou txt.")
    if ext in (".txt", ".md"):
        return lire_texte(fichier)
    with zipfile.ZipFile(fichier) as z:
        if ext == ".docx":
            return list(paragraphes(z.read("word/document.xml"), False))
        if ext in (".odt", ".odp"):
            return list(paragraphes(z.read("content.xml"), True))
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
