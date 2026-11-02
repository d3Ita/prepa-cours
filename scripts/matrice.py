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

from controler import SEANCE, lire, minutes
from evaluations import OBJECTIF, lire_corrige, lire_sujet
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
MINUTAGE = re.compile(r"(\d+)\s*[-–]\s*(\d+)\s*min")


def lire_phases(scenario):
    """Renvoie (titre, corps, minutée) pour chaque section « ## » d'un scénario."""
    parties = re.split(r"^##\s+(.+)$", scenario, flags=re.MULTILINE)
    return [(titre.strip(), corps, bool(MINUTAGE.match(titre)))
            for titre, corps in zip(parties[1::2], parties[2::2])]


def lire_questions(sujet, corrige, type_defaut):
    """Fusionne le sujet et le corrigé en une entrée par numéro de question."""
    types = {q.numero: q.type for q in lire_sujet(sujet or "", type_defaut)}
    questions = {}
    for reponse in lire_corrige(corrige or ""):
        entree = questions.setdefault(reponse.numero, {"numero": reponse.numero, "objectifs": [],
                                                       "type": types.get(reponse.numero, type_defaut)})
        entree["objectifs"] += [o for o in reponse.objectifs if o not in entree["objectifs"]]
    for numero, type_question in types.items():
        questions.setdefault(numero, {"numero": numero, "objectifs": [], "type": type_question})
    return [questions[n] for n in sorted(questions)]


def parcourir(chapitre):
    """Lit les textes de .travail une seule fois : la matrice et le modèle de cours en sont deux vues."""
    dossier = Path(chapitre) / ".travail"
    objectifs_md = lire(dossier / "objectifs.md") or ""
    objectifs = [{"id": objectif, "texte": texte.strip(), "notions": [n.strip() for n in notions.split(",") if n.strip()]}
                 for objectif, texte, notions in re.findall(
                     r"^[-*\s]*(OBJ\d+)\s*:\s*(.*)$(?:\n[-*\s]*Notions\s*:\s*(.*)$)?", objectifs_md, re.MULTILINE)]
    seances = []
    activite = exercice = 0
    for numero, duree, objectifs_texte in SEANCE.findall(objectifs_md):
        dossier_seance = dossier / f"seance-{numero}"
        activites = []
        for titre, corps, _ in lire_phases(lire(dossier_seance / "scenario.md") or ""):
            activite += 1
            pratique = bool(PRATIQUE.search(titre))
            exercice += pratique
            temps = MINUTAGE.match(titre)
            activites.append({"numero": activite, "exercice": exercice if pratique else None, "titre": titre,
                              "debut": int(temps.group(1)) if temps else None, "fin": int(temps.group(2)) if temps else None,
                              "objectifs": sorted(set(OBJECTIF.findall(corps)), key=lambda o: int(o[3:]))})
        diapos = lire(dossier_seance / "diapos.md")
        seances.append({
            "numero": int(numero), "duree": minutes(duree), "objectifs": OBJECTIF.findall(objectifs_texte), "activites": activites,
            "diapos": [{"numero": i, "titre": c["titre"], "objectifs": sorted(set(OBJECTIF.findall(" ".join(c["notes"]))))}
                       for i, c in enumerate(lire_diapos(diapos) if diapos else [], 1)],
            "questions": lire_questions(lire(dossier_seance / "qcm.md"), lire(dossier_seance / "qcm-corrige.md"), "qcm"),
        })
    return {"objectifs_md": objectifs_md, "objectifs": objectifs, "seances": seances,
            "evaluation": lire_questions(lire(dossier / "evaluation.md"), lire(dossier / "corrige.md"), "question-ouverte")}


def construire(chapitre):
    """Renvoie {objectif : {texte, notions, seances, activites, diapos, exercices, evaluations}}."""
    donnees = parcourir(chapitre)
    matrice = {o["id"]: {"texte": o["texte"], "notions": o["notions"], "seances": [], "activites": [], "diapos": [],
                         "exercices": [], "evaluations": []} for o in donnees["objectifs"]}

    def ajouter(objectifs, lien, valeur):
        for objectif in set(objectifs):
            if objectif in matrice and valeur not in matrice[objectif][lien]:
                matrice[objectif][lien].append(valeur)

    for seance in donnees["seances"]:
        numero = seance["numero"]
        ajouter(seance["objectifs"], "seances", numero)
        for activite in seance["activites"]:
            ajouter(activite["objectifs"], "activites", f"ACT-{activite['numero']:02d}")
            if activite["exercice"]:
                ajouter(activite["objectifs"], "exercices", f"EX-{activite['exercice']:02d}")
        for diapo in seance["diapos"]:
            ajouter(diapo["objectifs"], "diapos", f"S{numero}:{diapo['numero']}")
        for question in seance["questions"]:
            ajouter(question["objectifs"], "evaluations", f"S{numero}-QCM-{question['numero']}")
    for question in donnees["evaluation"]:
        ajouter(question["objectifs"], "evaluations", f"EVAL-{question['numero']}")
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
