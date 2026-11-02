#!/usr/bin/env python3
"""Construit le modèle structuré d'un cours et sa traçabilité, sans appel à un modèle de langage.

Le modèle est calculé depuis les textes de .travail : ces textes restent la seule source à modifier.
Les identifiants sont déterminés par l'ordre de ces textes : les mêmes fichiers donnent le même modèle.

Usage : modele.py [dossier du chapitre] [--json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

from controler import minutes
from matrice import parcourir

VERSION_MODELE = 1
FICHIER = Path(".travail") / "revue" / "course_model.json"
SUFFIXES_SOURCE = (".docx", ".odt", ".txt", ".md", ".pptx", ".odp", ".pdf")
COMPLET, PARTIEL, MANQUANT = "COMPLETE", "PARTIAL", "MISSING"
LIENS_ATTENDUS = {"activities": "activité", "resources": "ressource ou diapo", "exercises": "exercice", "evaluations": "évaluation"}


def identifiant(prefixe, numero):
    return f"{prefixe}-{numero:03d}"


def id_objectif(source):
    return identifiant("OBJ", int(source[3:]))


def champ(texte, *noms):
    for nom in noms:
        m = re.search(rf"^[-*\s]*{nom}\s*:\s*(.+)$", texte, re.MULTILINE | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def lire_metadonnees(chapitre, objectifs_md, seances):
    titre = re.search(r"^#\s*(?:Objectifs\s*:\s*)?(.+)$", objectifs_md, re.MULTILINE)
    annonce = champ(objectifs_md, "Durée totale")
    dossier_cours = Path(chapitre) / "Cours"
    sources = sorted(p.relative_to(chapitre).as_posix() for p in dossier_cours.rglob("*") if p.is_file()
                     and p.suffix.lower() in SUFFIXES_SOURCE and not p.name.startswith(("seance-", ".", "~$"))) \
        if dossier_cours.is_dir() else []
    return {"title": titre.group(1).strip() if titre else None, "subject": champ(objectifs_md, "Matière", "Matiere"),
            "level": champ(objectifs_md, "Niveau"), "class": champ(objectifs_md, "Classe"),
            "duration_minutes": minutes(annonce) if annonce else sum(s["duree"] or 0 for s in seances), "source": sources}


def construire_modele(chapitre):
    """Renvoie le modèle du cours : un dictionnaire JSON, sans classe à connaître pour le réutiliser."""
    donnees = parcourir(chapitre)
    concepts = {}
    objectifs = []
    for o in donnees["objectifs"]:
        liens = []
        for notion in o["notions"]:
            concept = concepts.setdefault(notion.casefold(), {"id": identifiant("C", len(concepts) + 1), "label": notion, "objectives": []})
            concept["objectives"].append(id_objectif(o["id"]))
            liens.append(concept["id"])
        objectifs.append({"id": id_objectif(o["id"]), "source_id": o["id"], "text": o["texte"], "concepts": liens})

    sessions, evaluations = [], []
    ressource = 0

    def ajouter_evaluation(question, session, libelle):
        evaluations.append({"id": identifiant("EVAL", len(evaluations) + 1), "label": libelle, "type": question["type"], "session": session,
                            "question": question["numero"], "objectives": [id_objectif(o) for o in question["objectifs"]]})

    for s in donnees["seances"]:
        session_id = identifiant("SES", s["numero"])
        activites = [{"id": identifiant("ACT", a["numero"]), "title": a["titre"], "start_minute": a["debut"], "end_minute": a["fin"],
                      "duration_minutes": a["fin"] - a["debut"] if a["debut"] is not None else None,
                      "objectives": [id_objectif(o) for o in a["objectifs"]],
                      "exercise": identifiant("EX", a["exercice"]) if a["exercice"] else None} for a in s["activites"]]
        ressources = []
        for diapo in s["diapos"]:
            ressource += 1
            ressources.append({"id": identifiant("RES", ressource), "type": "slide", "slide": diapo["numero"], "title": diapo["titre"],
                               "objectives": [id_objectif(o) for o in diapo["objectifs"]]})
        sessions.append({"id": session_id, "number": s["numero"], "duration_minutes": s["duree"],
                         "objectives": [id_objectif(o) for o in s["objectifs"]], "activities": activites, "resources": ressources})
        for question in s["questions"]:
            ajouter_evaluation(question, session_id, f"S{s['numero']}-QCM-{question['numero']}")
    for question in donnees["evaluation"]:
        ajouter_evaluation(question, None, f"FINAL-{question['numero']}")

    return {"version": VERSION_MODELE, "metadata": lire_metadonnees(chapitre, donnees["objectifs_md"], donnees["seances"]),
            "objectives": objectifs, "concepts": list(concepts.values()), "sessions": sessions, "evaluations": evaluations,
            "traceability": tracer(objectifs, sessions, evaluations)}


def tracer(objectifs, sessions, evaluations):
    """Relie chaque objectif à ses éléments, et dit lesquels manquent. Rien n'est demandé à un modèle de langage."""
    trace = {}
    for o in objectifs:
        oid = o["id"]
        activites = [a for s in sessions for a in s["activities"] if oid in a["objectives"]]
        liens = {"concepts": o["concepts"], "sessions": [s["id"] for s in sessions if oid in s["objectives"]],
                 "activities": [a["id"] for a in activites], "resources": [r["id"] for s in sessions for r in s["resources"] if oid in r["objectives"]],
                 "exercises": [a["exercise"] for a in activites if a["exercise"]], "evaluations": [e["id"] for e in evaluations if oid in e["objectives"]]}
        manquants = [cle for cle in LIENS_ATTENDUS if not liens[cle]]
        if not manquants:
            statut, explication = COMPLET, f"{oid} est relié à une activité, une ressource, un exercice et une évaluation."
        elif len(manquants) == len(LIENS_ATTENDUS):
            statut, explication = MANQUANT, f"{oid} est défini, mais n'a aucune activité, ressource, exercice ni évaluation associés."
        else:
            statut = PARTIEL
            explication = f"{oid} n'a pas de lien vers : {', '.join(LIENS_ATTENDUS[c] for c in manquants)}."
        trace[oid] = {**liens, "status": statut, "missing": manquants, "explanation": explication}
    return trace


def verifier_modele(modele):
    """Contrôle la structure : identifiants uniques et références qui existent."""
    erreurs = []
    objectifs = {o["id"] for o in modele["objectives"]}
    concepts = {c["id"] for c in modele["concepts"]}
    identifiants = [o["id"] for o in modele["objectives"]] + [c["id"] for c in modele["concepts"]] + [e["id"] for e in modele["evaluations"]]
    for s in modele["sessions"]:
        identifiants += [s["id"]] + [a["id"] for a in s["activities"]] + [r["id"] for r in s["resources"]]
    for doublon in sorted({i for i in identifiants if identifiants.count(i) > 1}):
        erreurs.append(f"Identifiant en double : {doublon}.")

    def verifier_references(lieu, references, connus):
        erreurs.extend(f"{lieu} cite {r}, qui n'existe pas." for r in references if r not in connus)

    for o in modele["objectives"]:
        verifier_references(o["id"], o["concepts"], concepts)
    for s in modele["sessions"]:
        verifier_references(s["id"], s["objectives"], objectifs)
        for element in s["activities"] + s["resources"]:
            verifier_references(element["id"], element["objectives"], objectifs)
    sessions = {s["id"] for s in modele["sessions"]}
    for e in modele["evaluations"]:
        verifier_references(e["id"], e["objectives"], objectifs)
        if e["session"] is not None:
            verifier_references(e["id"], [e["session"]], sessions)
    return erreurs


def ecrire_modele(chapitre, modele=None):
    modele = modele or construire_modele(chapitre)
    chemin = Path(chapitre) / FICHIER
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(modele, ensure_ascii=False, indent=2), encoding="utf-8")
    return modele


def afficher(modele):
    print(f"COURSE MODEL : {modele['metadata']['title']}\n")
    for oid, t in modele["traceability"].items():
        print(oid)
        for cle in ("concepts", "sessions", "activities", "resources", "exercises"):
            print(f" ├── {cle} : {', '.join(t[cle]) or '—'}")
        print(f" └── evaluations : {', '.join(t['evaluations']) or '—'}")
    print("\nOBJECTIVE COVERAGE\n")
    signes = {COMPLET: "✓", PARTIEL: "⚠ PARTIAL", MANQUANT: "✗ MISSING"}
    for oid, t in modele["traceability"].items():
        print(f"{oid} {signes[t['status']]}")
    for t in modele["traceability"].values():
        if t["status"] != COMPLET:
            print(t["explanation"])
    for erreur in verifier_modele(modele):
        print(f"⚠ {erreur}")


if __name__ == "__main__":
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("chapitre", nargs="?", default=".")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    if not (Path(a.chapitre) / ".travail" / "objectifs.md").is_file():
        sys.exit("Ce dossier n'est pas un chapitre préparé : .travail/objectifs.md est absent.")
    resultat = ecrire_modele(a.chapitre)
    if a.json:
        print(json.dumps(resultat, ensure_ascii=False, indent=2))
    else:
        afficher(resultat)
