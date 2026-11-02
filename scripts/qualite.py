#!/usr/bin/env python3
"""Calcule le score qualité d'un chapitre, décide de la suite de la boucle et trace les validations humaines.

Usage : qualite.py rapport [chapitre] --etape decoupage|scenarios|livrables [--json]
        qualite.py decider [chapitre] --etape ... --max-cycles 2
        qualite.py valider [chapitre] --etape ... --decision valider|modifier|relancer

Seule la commande « valider », lancée après la réponse du prof, peut marquer une étape comme validée.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from controler import controler, lire
from evaluations import verifier
from extraire_texte import extraire
from matrice import ETAPES, NOMS_LIENS, construire, couverture, lire_phases

CATEGORIES = ("factual", "pedagogical", "timing", "coherence", "evaluation", "hallucination")
SEVERITES = ("critical", "warning", "info")
PROVENANCES = ("source", "deduite", "externe", "incertaine")
DIMENSIONS = {"exactitude": "Exactitude", "objectifs": "Objectifs", "coherence": "Cohérence",
              "progression": "Progression", "timing": "Timing", "evaluation": "Évaluation"}
DIMENSION_DE = {"factual": "exactitude", "hallucination": "exactitude", "pedagogical": "progression",
                "timing": "timing", "coherence": "coherence", "evaluation": "evaluation"}
# Seule la critique peut juger le fond : sans elle, ces dimensions restent « non évaluées ».
DIMENSIONS_CRITIQUE = ("exactitude", "progression")
PENALITES = {"critical": 40, "warning": 12, "info": 3}
PLAFOND_CRITIQUE = 69
MAX_CYCLES_DEFAUT = 2
MAX_CYCLES_LIMITE = 5
TITRES_ETAPES = {"decoupage": "Découpage terminé.", "scenarios": "Scénarios terminés.",
                 "livrables": "Diapos et évaluations terminées."}
FICHIERS_ETAPE = {"scenarios": ("scenario.md",), "livrables": ("scenario.md", "diapos.md", "qcm.md", "qcm-corrige.md")}
A_VERIFIER = "[À VÉRIFIER]"
# Ce vocabulaire de mise en forme ne vient pas du cours, et ce n'est pas une information à vérifier.
MOTS_DE_STRUCTURE = {"qcm", "obj", "nom", "date", "total", "durée", "question", "séance", "objectif", "objectifs",
                     "support", "corrigé", "évaluation", "bilan", "rappel", "activité", "diapo", "diapos"}


def constat(severity, category, location, problem, evidence="", suggestion="", **autres):
    return {"severity": severity, "category": category, "location": location, "problem": problem,
            "evidence": evidence, "suggestion": suggestion, **autres}


def fichiers_produits(chapitre, etape):
    dossier = Path(chapitre) / ".travail"
    fichiers = [dossier / "objectifs.md"]
    for seance in sorted(dossier.glob("seance-*")):
        fichiers += [seance / f for f in FICHIERS_ETAPE.get(etape, ())]
    if etape == "livrables":
        fichiers += [dossier / "evaluation.md", dossier / "corrige.md"]
    return [f for f in fichiers if f.is_file()]


def lire_source(chapitre):
    """Renvoie le texte du cours d'origine, ou None si aucun document n'a pu être lu (un PDF par exemple)."""
    textes = []
    for chemin in sorted((Path(chapitre) / "Cours").glob("*")):
        if chemin.is_file() and not chemin.name.startswith(("seance-", ".")):
            try:
                textes += extraire(chemin)
            except (OSError, SystemExit, KeyError, ValueError):
                continue
    return "\n".join(textes) if textes else None


def termes_suspects(ligne, source):
    """Repère les nombres et les noms propres absents du cours : une piste pour la critique, pas une preuve."""
    propre = re.sub(r"^[-*#>\s]+|^[A-Z][.)]\s+|^Question\s+\d+\s*:\s*\S+", "", ligne)
    propre = re.sub(r"\bOBJ\d+\b|\[.*?\]|\(.*?\)\s*$", " ", propre).replace("*", "")
    propre = re.sub(r"\d+\s*(?:min\w*|h\b|heures?|points?|séances?|diapos?|lignes?)", " ", propre, flags=re.IGNORECASE)
    suspects = [n for n in re.findall(r"\d[\d.,]*\d", propre) if n not in source]
    for phrase in re.split(r"[.!?:;—|]\s+", propre):
        suspects += [m for m in re.findall(r"(?<=\s)[A-ZÀ-Ý][\w'’-]{2,}", phrase)
                     if m.casefold() not in source and m.casefold() not in MOTS_DE_STRUCTURE]
    return suspects


def verifier_sources(chapitre, etape):
    """Trace ce qui est marqué [À VÉRIFIER] et ce qui ne vient pas visiblement du cours."""
    dossier = Path(chapitre) / ".travail"
    source = lire_source(chapitre)
    constats = []
    if source is None:
        constats.append(constat("info", "hallucination", "Cours/", "Le cours d'origine n'a pas pu être lu par le contrôle.",
                                suggestion="La critique doit le comparer elle-même aux documents produits."))
    source_min = (source or "").casefold()
    for chemin in fichiers_produits(chapitre, etape):
        lieu = chemin.relative_to(dossier).as_posix()
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if A_VERIFIER in ligne:
                constats.append(constat("info", "hallucination", lieu, "Information marquée à vérifier par le prof.",
                                        ligne.strip(), provenance="incertaine"))
            elif source is not None and not ligne.startswith("##") and chemin.name != "objectifs.md":
                for terme in termes_suspects(ligne, source_min):
                    constats.append(constat("warning", "hallucination", lieu, f"« {terme} » n'apparaît pas dans le cours d'origine.",
                                            ligne.strip(), f"Vérifier ce terme, puis le marquer {A_VERIFIER} s'il ne vient pas du cours.",
                                            provenance="externe"))
    return constats


def lire_critique(chapitre, etape):
    """Renvoie (constats, état). L'état vaut « ok » seulement pour une critique complète et à jour."""
    dossier = Path(chapitre) / ".travail"
    chemin = dossier / "revue" / "critique.json"
    if not chemin.is_file():
        return [], "absente"
    # La critique lue doit porter sur la dernière version : une révision la rend obsolète.
    if any(f.stat().st_mtime > chemin.stat().st_mtime for f in dossier.rglob("*.md")):
        return [], "obsolète"
    try:
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        constats = contenu["constats"]
        controlees = {v["category"] for v in contenu["verifications"] if v.get("control")}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return [], "invalide"
    if contenu.get("etape") != etape:
        return [], "d'une autre étape"
    # Une critique qui dirait seulement « OK » ne compte pas : chaque catégorie doit avoir été contrôlée.
    if set(CATEGORIES) - controlees or not isinstance(constats, list):
        return [], "incomplète"
    for c in constats:
        if (not isinstance(c, dict) or c.get("severity") not in SEVERITES or c.get("category") not in CATEGORIES
                or not c.get("location") or not c.get("problem") or c.get("provenance", "source") not in PROVENANCES
                or (c["severity"] == "critical" and not c.get("evidence"))):
            return [], "invalide"
    return constats, "ok"


def rang(etape):
    return ETAPES.index(etape)


def controler_etape(chapitre, etape):
    constats = []
    problemes, _ = controler(Path(chapitre))
    for p in problemes:
        if rang(getattr(p, "etape", "livrables")) <= rang(etape):
            constats.append(constat(getattr(p, "severite", "warning"), getattr(p, "categorie", "coherence"),
                                    p.split(" : ")[0] if " : " in p else "chapitre", str(p)))
    if etape != "decoupage":
        for seance in sorted((Path(chapitre) / ".travail").glob("seance-*")):
            for titre, _, minutee in lire_phases(lire(seance / "scenario.md") or ""):
                if not minutee:
                    constats.append(constat("warning", "timing", seance.name, f"La phase « {titre} » n'a pas de temps défini."))
    dossier = Path(chapitre) / ".travail"
    sujet, corrige = lire(dossier / "evaluation.md"), lire(dossier / "corrige.md")
    if etape == "livrables" and sujet and corrige:
        constats += [constat("warning", "evaluation", "evaluation.md", p) for p in verifier(sujet, corrige, "question-ouverte")]
    return constats


def controler_couverture(matrice, etape):
    constats = []
    for objectif, c in couverture(matrice, etape).items():
        if not c["manquants"]:
            continue
        manque = set(c["manquants"])
        # Sans activité ni évaluation, rien ne permet de vérifier la maîtrise de l'objectif.
        severite = "critical" if c["pourcentage"] == 0 else "info" if manque == {"exercices"} else "warning"
        constats.append(constat(severite, "coherence", objectif,
                                f"{objectif} : manque {', '.join(NOMS_LIENS[l] for l in c['manquants'])}.",
                                dimension="objectifs", suggestion="Ajouter le lien manquant ou revoir cet objectif."))
    return constats


def expliquer(c):
    lieu = "" if c["location"] in c["problem"] else f" ({c['location']})"
    preuve = f" : {c['evidence']}" if c.get("evidence") else ""
    return f"{c['problem']}{lieu}{preuve}"


def calculer_scores(constats, couvertures, etat_critique, etape):
    scores = {}
    for dimension, libelle in DIMENSIONS.items():
        concernes = [c for c in constats if c.get("dimension", DIMENSION_DE[c["category"]]) == dimension]
        if dimension in DIMENSIONS_CRITIQUE and etat_critique != "ok":
            scores[dimension] = {"libelle": libelle, "score": None, "details": [f"Non évaluée : critique {etat_critique}."]
                                 + [expliquer(c) for c in concernes]}
            continue
        if dimension == "evaluation" and etape != "livrables":
            scores[dimension] = {"libelle": libelle, "score": None, "details": ["Pas encore produite à cette étape."]}
            continue
        if dimension == "objectifs":
            valeurs = [c["pourcentage"] for c in couvertures.values()]
            score = round(sum(valeurs) / len(valeurs)) if valeurs else 0
        else:
            score = max(0, 100 - sum(PENALITES[c["severity"]] for c in concernes))
        scores[dimension] = {"libelle": libelle, "score": score,
                             "details": [expliquer(c) for c in concernes] or ["Aucun problème détecté."]}
    return scores


def validations(chapitre):
    chemin = Path(chapitre) / ".travail" / "revue" / "validations.json"
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else []


def validee_par_le_prof(chapitre, etape):
    dossier = Path(chapitre) / ".travail"
    chemin = dossier / "revue" / "validations.json"
    derniere = next((v for v in reversed(validations(chapitre)) if v["etape"] == etape), None)
    if derniere is None or derniere["decision"] != "valider":
        return False
    return not any(f.stat().st_mtime > chemin.stat().st_mtime for f in dossier.rglob("*.md"))


def metriques(rapport, chapitre):
    """Les mesures communes à la comparaison agent unique / multi-agent décrite dans experiences/protocole.md."""
    scores = rapport["scores"]
    valeurs = lambda *noms: [scores[n]["score"] for n in noms if scores[n]["score"] is not None]
    moyenne = lambda v: round(sum(v) / len(v)) if v else None
    fichiers = max(1, len(fichiers_produits(chapitre, rapport["etape"])))
    non_marquees = [c for c in rapport["constats"] if c["category"] == "hallucination" and c["severity"] != "info"]
    return {"accuracy": scores["exactitude"]["score"], "pedagogical_coherence": moyenne(valeurs("coherence", "progression")),
            "objective_coverage": scores["objectifs"]["score"], "timing_validity": scores["timing"]["score"],
            "evaluation_quality": scores["evaluation"]["score"], "hallucination_rate": round(len(non_marquees) / fichiers, 2),
            "human_interventions": len(validations(chapitre)), "generation_time": None}


def construire_rapport(chapitre, etape):
    matrice = construire(chapitre)
    couvertures = couverture(matrice, etape)
    critique, etat_critique = lire_critique(chapitre, etape)
    constats = controler_etape(chapitre, etape) + controler_couverture(matrice, etape) \
        + verifier_sources(chapitre, etape) + critique
    scores = calculer_scores(constats, couvertures, etat_critique, etape)
    evalues = [s["score"] for s in scores.values() if s["score"] is not None]
    critiques = sum(c["severity"] == "critical" for c in constats)
    avertissements = sum(c["severity"] == "warning" for c in constats)
    score = round(sum(evalues) / len(evalues)) if evalues else 0
    if critiques:
        score = min(score, PLAFOND_CRITIQUE)
    if validee_par_le_prof(chapitre, etape):
        statut = "HUMAN_VALIDATED"
    elif critiques or etat_critique != "ok":
        statut = "HUMAN_REVIEW_REQUIRED"
    else:
        statut = "READY_FOR_HUMAN_VALIDATION"
    rapport = {"etape": etape, "date": time.strftime("%Y-%m-%dT%H:%M:%S"), "global": score, "partiel": etat_critique != "ok",
               "critique": etat_critique, "critiques": critiques, "avertissements": avertissements, "statut": statut,
               "scores": scores, "couverture": couvertures, "constats": constats}
    rapport["metriques"] = metriques(rapport, chapitre)
    revue = Path(chapitre) / ".travail" / "revue"
    revue.mkdir(parents=True, exist_ok=True)
    (revue / "qualite.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    return rapport


def afficher(rapport):
    print("QUALITY SCORE\n")
    print(f"{'Global':<16}{rapport['global']}/100" + (" (partiel)" if rapport["partiel"] else ""))
    for s in rapport["scores"].values():
        print(f"{s['libelle']:<16}" + (f"{s['score']}/100" if s["score"] is not None else "non évalué"))
    for s in rapport["scores"].values():
        print(f"\n{s['libelle']} : " + (f"{s['score']}/100" if s["score"] is not None else "non évalué"))
        for ligne in s["details"]:
            print(f"- {ligne}")
    print("\nOBJECTIVE COVERAGE\n")
    for objectif, c in rapport["couverture"].items():
        signe = "✓" if c["pourcentage"] == 100 else "✗" if c["pourcentage"] == 0 else "⚠"
        print(f"{objectif} {signe} {c['pourcentage']}%")
    print(f"\nCRITICAL ISSUES: {rapport['critiques']}\nWARNINGS: {rapport['avertissements']}\n\nSTATUS: {rapport['statut']}")
    partiel = f" (partiel : critique {rapport['critique']})" if rapport["partiel"] else ""
    print(f"\n{TITRES_ETAPES[rapport['etape']]}\n\nQuality score: {rapport['global']}/100{partiel}\n")
    if rapport["critiques"]:
        print(f"✗ {rapport['critiques']} problème(s) bloquant(s)")
    if rapport["avertissements"]:
        print(f"⚠ {rapport['avertissements']} warning(s)")
    print("\n[1] Valider\n[2] Modifier\n[3] Relancer l'analyse")


def lire_max_cycles(valeur):
    """La valeur vient du réglage du plugin : hors limites ou absente, on garde le défaut."""
    try:
        cycles = int(valeur)
    except (TypeError, ValueError):
        return MAX_CYCLES_DEFAUT
    return cycles if 0 <= cycles <= MAX_CYCLES_LIMITE else MAX_CYCLES_DEFAUT


def lire_etat(chapitre):
    chemin = Path(chapitre) / ".travail" / "revue" / "etat.json"
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else {"cycles": {}}


def ecrire_etat(chapitre, etat):
    revue = Path(chapitre) / ".travail" / "revue"
    revue.mkdir(parents=True, exist_ok=True)
    (revue / "etat.json").write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")


def decider(chapitre, etape, max_cycles):
    """Renvoie la suite : critique, révision ou validation humaine. Jamais une validation automatique."""
    rapport = construire_rapport(chapitre, etape)
    if rapport["critique"] != "ok":
        return f"DECISION: CRITIQUE_REQUISE (critique {rapport['critique']})"
    if not rapport["critiques"] and not rapport["avertissements"]:
        return "DECISION: VALIDATION_HUMAINE"
    etat = lire_etat(chapitre)
    cycles = etat["cycles"].get(etape, 0)
    if cycles >= max_cycles:
        return "⚠ Révision maximale atteinte.\nUne validation humaine est requise.\nDECISION: VALIDATION_HUMAINE"
    etat["cycles"][etape] = cycles + 1
    ecrire_etat(chapitre, etat)
    return f"DECISION: REVISION {cycles + 1}/{max_cycles}"


def valider(chapitre, etape, decision):
    """Trace la réponse du prof. « Modifier » et « Relancer » rouvrent la boucle de révision."""
    rapport = construire_rapport(chapitre, etape)
    historique = validations(chapitre)
    historique.append({"etape": etape, "decision": decision, "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "score": rapport["global"], "critiques": rapport["critiques"],
                       "avertissements": rapport["avertissements"]})
    (Path(chapitre) / ".travail" / "revue" / "validations.json").write_text(
        json.dumps(historique, ensure_ascii=False, indent=2), encoding="utf-8")
    if decision != "valider":
        etat = lire_etat(chapitre)
        etat["cycles"].pop(etape, None)
        ecrire_etat(chapitre, etat)
    print(f"Décision du prof enregistrée : {decision}.")


def main():
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    sous = p.add_subparsers(dest="commande", required=True)
    for nom in ("rapport", "decider", "valider"):
        c = sous.add_parser(nom)
        c.add_argument("chapitre", nargs="?", default=".")
        c.add_argument("--etape", choices=ETAPES, default="livrables")
        if nom == "rapport":
            c.add_argument("--json", action="store_true")
        if nom == "decider":
            c.add_argument("--max-cycles", default=MAX_CYCLES_DEFAUT)
        if nom == "valider":
            c.add_argument("--decision", choices=("valider", "modifier", "relancer"), required=True)
    a = p.parse_args()
    if not (Path(a.chapitre) / ".travail" / "objectifs.md").is_file():
        sys.exit("Ce dossier n'est pas un chapitre préparé : .travail/objectifs.md est absent.")
    if a.commande == "rapport":
        rapport = construire_rapport(a.chapitre, a.etape)
        if a.json:
            print(json.dumps(rapport, ensure_ascii=False, indent=2))
        else:
            afficher(rapport)
        sys.exit(1 if rapport["critiques"] else 0)
    if a.commande == "decider":
        print(decider(a.chapitre, a.etape, lire_max_cycles(a.max_cycles)))
    else:
        valider(a.chapitre, a.etape, a.decision)


if __name__ == "__main__":
    main()
