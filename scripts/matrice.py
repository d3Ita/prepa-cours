#!/usr/bin/env python3
"""Construit la matrice pédagogique d'un chapitre : objectif, notions, séance, activité, diapos, exercice, évaluation.

La matrice se lit dans les fichiers existants de .travail, sans format supplémentaire.

Usage : matrice.py [dossier du chapitre] [--etape decoupage|scenarios|livrables] [--json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

from controler import SEANCE, lire
from evaluations import OBJECTIF, lire_corrige
from generer import lire_diapos

ETAPES = ("decoupage", "scenarios", "livrables")
LIENS = {
    "decoupage": ("seances",),
    "scenarios": ("activites", "exercices"),
    "livrables": ("activites", "diapos", "exercices", "evaluations"),
}
NOMS_LIENS = {"seances": "séance", "activites": "activité", "diapos": "diapo",
              "exercices": "exercice", "evaluations": "évaluation"}
PRATIQUE = re.compile(r"activité|exercice|atelier|\btp\b|\btd\b|manipulation|problème|étude de cas|mise en pratique",
                      re.IGNORECASE)
MINUTAGE = re.compile(r"\d+\s*[-–]\s*\d+\s*min")


def lire_phases(scenario):
    """Renvoie (titre, corps, minutée) pour chaque section « ## » d'un scénario."""
    parties = re.split(r"^##\s+(.+)$", scenario, flags=re.MULTILINE)
    return [(titre.strip(), corps, bool(MINUTAGE.match(titre)))
            for titre, corps in zip(parties[1::2], parties[2::2])]


def construire(chapitre):
    """Renvoie {objectif : {texte, notions, seances, activites, diapos, exercices, evaluations}}."""
    dossier = Path(chapitre) / ".travail"
    objectifs_md = lire(dossier / "objectifs.md") or ""
    matrice = {}
    for objectif, texte, notions in re.findall(
            r"^[-*\s]*(OBJ\d+)\s*:\s*(.*)$(?:\n[-*\s]*Notions\s*:\s*(.*)$)?", objectifs_md, re.MULTILINE):
        matrice[objectif] = {"texte": texte.strip(), "notions": [n.strip() for n in notions.split(",") if n.strip()],
                             "seances": [], "activites": [], "diapos": [], "exercices": [], "evaluations": []}

    def ajouter(objectifs, lien, valeur):
        for objectif in set(objectifs):
            if objectif in matrice and valeur not in matrice[objectif][lien]:
                matrice[objectif][lien].append(valeur)

    activite = exercice = 0
    for numero, _, objectifs_texte in SEANCE.findall(objectifs_md):
        ajouter(OBJECTIF.findall(objectifs_texte), "seances", int(numero))
        seance = dossier / f"seance-{numero}"
        for titre, corps, _ in lire_phases(lire(seance / "scenario.md") or ""):
            activite += 1
            cites = OBJECTIF.findall(corps)
            ajouter(cites, "activites", f"ACT-{activite:02d}")
            if PRATIQUE.search(titre):
                exercice += 1
                ajouter(cites, "exercices", f"EX-{exercice:02d}")
        diapos = lire(seance / "diapos.md")
        for i, contenu in enumerate(lire_diapos(diapos) if diapos else [], 1):
            ajouter(OBJECTIF.findall(" ".join(contenu["notes"])), "diapos", f"S{numero}:{i}")
        for reponse in lire_corrige(lire(seance / "qcm-corrige.md") or ""):
            ajouter(reponse.objectifs, "evaluations", f"S{numero}-QCM-{reponse.numero}")
    for reponse in lire_corrige(lire(dossier / "corrige.md") or ""):
        ajouter(reponse.objectifs, "evaluations", f"EVAL-{reponse.numero}")
    return dict(sorted(matrice.items(), key=lambda e: int(e[0][3:])))


def couverture(matrice, etape="livrables"):
    """Renvoie {objectif : {pourcentage, manquants}} : la part des liens attendus à cette étape."""
    liens = LIENS[etape]
    resultat = {}
    for objectif, entree in matrice.items():
        manquants = [l for l in liens if not entree[l]]
        resultat[objectif] = {"pourcentage": round(100 * (len(liens) - len(manquants)) / len(liens)),
                              "manquants": manquants}
    return resultat


def afficher(matrice, etape):
    for objectif, e in matrice.items():
        print(f"{objectif} : {e['texte']}")
        for libelle, valeurs in (("notions", e["notions"]), ("séances", e["seances"]), ("activités", e["activites"]),
                                 ("diapos", e["diapos"]), ("exercices", e["exercices"]), ("évaluations", e["evaluations"])):
            print(f" ├── {libelle} : {', '.join(map(str, valeurs)) or '—'}")
    print("\nOBJECTIVE COVERAGE\n")
    for objectif, c in couverture(matrice, etape).items():
        signe = "✓" if c["pourcentage"] == 100 else "✗" if c["pourcentage"] == 0 else "⚠"
        print(f"{objectif} {signe} {c['pourcentage']}%")
    for objectif, c in couverture(matrice, etape).items():
        if c["manquants"]:
            print(f"{objectif} : manque {', '.join(NOMS_LIENS[l] for l in c['manquants'])}.")


if __name__ == "__main__":
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("chapitre", nargs="?", default=".")
    p.add_argument("--etape", choices=ETAPES, default="livrables")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    m = construire(a.chapitre)
    if a.json:
        print(json.dumps({"matrice": m, "couverture": couverture(m, a.etape)}, ensure_ascii=False, indent=2))
    else:
        afficher(m, a.etape)
