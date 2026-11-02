#!/usr/bin/env python3
"""Contrôle la cohérence d'un dossier de cours : objectifs, minutage, barème, diapos.

Usage : controler.py [dossier]
Code de sortie 1 s'il y a au moins un problème.
"""
import re
import sys
from pathlib import Path

from generer import lire_diapos

FICHIERS = ("scenario.md", "diapos.md", "corrige.md")
MAX_PUCES = 6


def lire(dossier, nom):
    chemin = dossier / nom
    return chemin.read_text(encoding="utf-8") if chemin.is_file() else None


def controler(dossier):
    """Renvoie (problèmes, informations)."""
    problemes, infos = [], []
    objectifs_md = lire(dossier, "objectifs.md")
    if objectifs_md is None:
        return ["objectifs.md est absent."], infos
    objectifs = sorted(set(re.findall(r"\bO\d+\b", objectifs_md)), key=lambda o: int(o[1:]))
    if not objectifs:
        problemes.append("objectifs.md ne contient aucun objectif numéroté (O1, O2…).")

    for nom in FICHIERS:
        texte = lire(dossier, nom)
        if texte is None:
            problemes.append(f"{nom} est absent.")
            continue
        cites = set(re.findall(r"\bO\d+\b", texte))
        for o in objectifs:
            if o not in cites:
                problemes.append(f"{o} n'est pas couvert dans {nom}.")
        for o in sorted(cites - set(objectifs)):
            problemes.append(f"{nom} cite {o}, absent de objectifs.md.")

    scenario = lire(dossier, "scenario.md")
    if scenario is not None:
        phases = [(int(a), int(b)) for a, b in
                  re.findall(r"^##\s*(\d+)\s*[-–]\s*(\d+)\s*min", scenario, re.MULTILINE)]
        if not phases:
            problemes.append("scenario.md n'a aucune phase minutée (« ## 0-10 min — … »).")
        else:
            fin = 0
            for debut, arrivee in phases:
                if debut != fin or arrivee <= debut:
                    problemes.append(f"Minutage incohérent : phase {debut}-{arrivee} min, attendu un début à {fin}.")
                fin = arrivee
            duree = re.search(r"Durée\s*:\s*(\d+)", objectifs_md, re.IGNORECASE)
            if duree and int(duree.group(1)) != fin:
                problemes.append(f"Le scénario dure {fin} min, mais objectifs.md annonce {duree.group(1)} min.")
            infos.append(f"Durée du scénario : {fin} min.")

    evaluation = lire(dossier, "evaluation.md")
    if evaluation is None:
        problemes.append("evaluation.md est absent.")
    else:
        points = [float(p.replace(",", ".")) for p in
                  re.findall(r"\((\d+(?:[.,]\d+)?)\s*points?\)", evaluation, re.IGNORECASE)]
        total = sum(points)
        annonce = re.search(r"Total\s*:\s*(\d+(?:[.,]\d+)?)\s*points?", evaluation, re.IGNORECASE)
        if not points:
            problemes.append("evaluation.md n'indique aucun barème (« (5 points) »).")
        elif annonce and float(annonce.group(1).replace(",", ".")) != total:
            problemes.append(f"Les questions totalisent {total:g} points, mais le sujet annonce {annonce.group(1)}.")
        if points:
            infos.append(f"Barème : {total:g} points.")

    diapos = lire(dossier, "diapos.md")
    if diapos is not None:
        for contenu in lire_diapos(diapos):
            if len(contenu["puces"]) > MAX_PUCES:
                problemes.append(f"Diapo « {contenu['titre']} » : {len(contenu['puces'])} puces (maximum {MAX_PUCES}).")

    a_verifier = {nom: texte.count("[À VÉRIFIER]") for nom in
                  ("objectifs.md", *FICHIERS, "evaluation.md")
                  if (texte := lire(dossier, nom)) is not None}
    for nom, nombre in a_verifier.items():
        if nombre:
            infos.append(f"{nom} : {nombre} point(s) à vérifier par le prof.")
    return problemes, infos


if __name__ == "__main__":
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    problemes, infos = controler(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    for ligne in infos:
        print(f"Info : {ligne}")
    for ligne in problemes:
        print(f"Problème : {ligne}")
    if not problemes:
        print("Cours cohérent : aucun problème détecté.")
    sys.exit(1 if problemes else 0)
