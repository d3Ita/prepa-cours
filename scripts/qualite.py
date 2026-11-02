#!/usr/bin/env python3
"""Calcule le score qualité d'un chapitre, décide de la suite de la boucle et trace les validations humaines.

Usage : qualite.py rapport [chapitre] --etape decoupage|scenarios|livrables [--json]
        qualite.py decider [chapitre] --etape ... --max-cycles 2
        qualite.py valider [chapitre] --etape ... --decision valider|modifier|relancer
        qualite.py quality-report [chapitre] --etape ...

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
from matrice import ETAPES, NOMS_LIENS, construire, couverture, lire_phases, parcourir
from modele import construire_modele, ecrire_modele, id_objectif
from redaction import lire_etat as lire_redaction

CATEGORIES = ("factual", "pedagogical", "timing", "coherence", "evaluation", "hallucination")
SEVERITES = ("critical", "warning", "info")
PROVENANCES = ("source", "deduite", "externe", "incertaine")
DIMENSIONS = {"exactitude": "Exactitude", "objectifs": "Objectifs", "coherence": "Cohérence",
              "progression": "Progression", "timing": "Timing", "evaluation": "Évaluation", "completude": "Complétude"}
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
            # Une ligne de dessin contient des coordonnées : seul le texte d'une étiquette vient du cours.
            ligne = re.sub(r"^@dessin\s*:\s*etiquette(?:\s+\S+){3}\s+", "Étiquette : ", ligne)
            if ligne.startswith("@"):
                continue
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


def mesurer_completude(chapitre, etape):
    """Calcule la part de ce qui est attendu et bien présent : fichiers, notions et sections du cours.

    Renvoie (score, constats). Un mot retrouvé ne prouve pas que la notion est bien traitée.
    """
    if etape == "decoupage":
        return None, []
    dossier = Path(chapitre) / ".travail"
    donnees = parcourir(chapitre)
    attendus = [dossier / f"seance-{s['numero']}" / f for s in donnees["seances"] for f in FICHIERS_ETAPE[etape]]
    presents = sum(f.is_file() for f in attendus)
    total = len(attendus)
    produit = "\n".join(f.read_text(encoding="utf-8") for f in fichiers_produits(chapitre, etape)
                        if f.name != "objectifs.md").casefold()
    constats = []
    for o in donnees["objectifs"]:
        for notion in o["notions"]:
            total += 1
            if notion.casefold() in produit:
                presents += 1
            else:
                constats.append(constat("warning", "coherence", o["id"], f"La notion « {notion} » n'apparaît dans aucun document produit.",
                                        dimension="completude", suggestion="Traiter cette notion ou la retirer de l'objectif."))
    for ligne in (lire_source(chapitre) or "").splitlines():
        titre = re.match(r"#{1,6}\s+(.+)", ligne.strip())
        mots = re.findall(r"\w{4,}", titre.group(1).casefold()) if titre else []
        if not mots or titre.group(1).strip().casefold() == "sources utilisées":
            continue
        total += 1
        if 2 * sum(m in produit for m in mots) >= len(mots):
            presents += 1
        else:
            constats.append(constat("warning", "coherence", "Cours/", f"La section « {titre.group(1).strip()} » du cours n'apparaît pas dans les documents produits.",
                                    dimension="completude", suggestion="Vérifier si cette section a été oubliée."))
    return (round(100 * presents / total) if total else None), constats


def expliquer(c):
    lieu = "" if c["location"] in c["problem"] else f" ({c['location']})"
    preuve = f" : {c['evidence']}" if c.get("evidence") else ""
    return f"{c['problem']}{lieu}{preuve}"


def calculer_scores(constats, couvertures, etat_critique, etape, completude=None):
    scores = {}
    for dimension, libelle in DIMENSIONS.items():
        concernes = [c for c in constats if c.get("dimension", DIMENSION_DE[c["category"]]) == dimension]
        if dimension in DIMENSIONS_CRITIQUE and etat_critique != "ok":
            scores[dimension] = {"libelle": libelle, "score": None, "details": [f"Non évaluée : critique {etat_critique}."]
                                 + [expliquer(c) for c in concernes]}
            continue
        if (dimension == "evaluation" and etape != "livrables") or (dimension == "completude" and completude is None):
            scores[dimension] = {"libelle": libelle, "score": None, "details": ["Pas encore produite à cette étape."]}
            continue
        if dimension == "objectifs":
            valeurs = [c["pourcentage"] for c in couvertures.values()]
            score = round(sum(valeurs) / len(valeurs)) if valeurs else 0
        elif dimension == "completude":
            score = completude
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


def interventions_humaines(chapitre):
    """Rassemble chaque décision du prof : validation d'étape, validation du cours, modification appliquée."""
    actions = {"valider": "approve", "modifier": "modify", "relancer": "rerun"}
    liste = [{"stage": v["etape"], "action": actions[v["decision"]], "date": v["date"]} for v in validations(chapitre)]
    redaction = lire_redaction(chapitre) or {}
    liste += [{"stage": "redaction", "action": "approve", "date": v["date"]} for v in redaction.get("validations", [])]
    journal = Path(chapitre) / ".travail" / "revue" / "modifications.json"
    if journal.is_file():
        liste += [{"stage": "modification", "action": "apply", "date": m["date"]}
                  for m in json.loads(journal.read_text(encoding="utf-8"))]
    return sorted(liste, key=lambda i: i["date"])


def historique_revisions(chapitre):
    return lire_etat(chapitre).get("historique", [])


def compter_revisions(chapitre):
    return sum(h["decision"].startswith("REVISION ") for h in historique_revisions(chapitre))


def metriques(rapport, chapitre):
    """Les mesures communes à la comparaison agent unique / multi-agent décrite dans docs/methodology.md."""
    scores = rapport["scores"]
    valeurs = lambda *noms: [scores[n]["score"] for n in noms if scores[n]["score"] is not None]
    moyenne = lambda v: round(sum(v) / len(v)) if v else None
    fichiers = max(1, len(fichiers_produits(chapitre, rapport["etape"])))
    non_marquees = [c for c in rapport["constats"] if c["category"] == "hallucination" and c["severity"] != "info"]
    return {"accuracy": scores["exactitude"]["score"], "pedagogical_coherence": moyenne(valeurs("coherence", "progression")),
            "objective_coverage": scores["objectifs"]["score"], "timing_validity": scores["timing"]["score"],
            "evaluation_quality": scores["evaluation"]["score"], "content_completeness": scores["completude"]["score"],
            "hallucination_rate": round(len(non_marquees) / fichiers, 2), "hallucination_count": len(non_marquees),
            "critical_error_count": rapport["critiques"], "warning_count": rapport["avertissements"],
            "human_interventions": len(interventions_humaines(chapitre)), "revision_count": compter_revisions(chapitre),
            "generation_time": None}


METHODE_CODE = "deterministic"
METHODE_MIXTE = "deterministic+llm_critic"
METHODE_ABSENTE = "not_evaluated"


def score_explique(rapport, *dimensions, methode):
    """Le score, sa méthode de calcul et ses explications : un chiffre seul n'est jamais rendu."""
    disponibles = [rapport["scores"][d] for d in dimensions if rapport["scores"][d]["score"] is not None]
    valeur = round(sum(s["score"] for s in disponibles) / len(disponibles)) if disponibles else None
    return {"value": valeur, "method": methode if valeur is not None else METHODE_ABSENTE,
            "explanation": [ligne for d in dimensions for ligne in rapport["scores"][d]["details"]]}


def construire_quality_report(chapitre, rapport):
    critique_ok = rapport["critique"] == "ok"
    mixte = METHODE_MIXTE if critique_ok else METHODE_CODE
    details = {
        "accuracy_score": score_explique(rapport, "exactitude", methode=METHODE_MIXTE),
        "objective_coverage_score": score_explique(rapport, "objectifs", methode=METHODE_CODE),
        "pedagogical_coherence_score": score_explique(rapport, "coherence", "progression", methode=mixte),
        "timing_score": score_explique(rapport, "timing", methode=mixte),
        "evaluation_score": score_explique(rapport, "evaluation", methode=mixte),
        "content_completeness_score": score_explique(rapport, "completude", methode=METHODE_CODE),
    }
    trace = construire_modele(chapitre)["traceability"]
    couverture_objectifs = []
    for source, c in rapport["couverture"].items():
        oid = id_objectif(source)
        couverture_objectifs.append({"id": oid, "source_id": source, "percentage": c["pourcentage"],
                                     "missing": c["manquants"], "status": trace[oid]["status"], "explanation": trace[oid]["explanation"]})
    tries = {s: [c for c in rapport["constats"] if c["severity"] == s] for s in SEVERITES}
    interventions = interventions_humaines(chapitre)
    return {"schema_version": 1, "stage": rapport["etape"], "status": rapport["statut"], "overall_score": rapport["global"],
            "partial": rapport["partiel"], "critic": rapport["critique"], **{k: v["value"] for k, v in details.items()}, "score_details": details,
            "critical_issues": tries["critical"], "warnings": tries["warning"], "infos": tries["info"], "objective_coverage": couverture_objectifs,
            "human_interventions": {"count": len(interventions), "events": interventions},
            "revisions": {"count": compter_revisions(chapitre), "history": historique_revisions(chapitre)}}


def afficher_quality_report(q):
    libelles = (("accuracy_score", "Accuracy"), ("objective_coverage_score", "Objective coverage"),
                ("pedagogical_coherence_score", "Pedagogical coherence"), ("timing_score", "Timing"),
                ("evaluation_score", "Evaluation"), ("content_completeness_score", "Content completeness"))
    print(f"QUALITY REPORT\n\nOverall: {q['overall_score']}/100" + (" (partial)" if q["partial"] else "") + "\n")
    for cle, libelle in libelles:
        detail = q["score_details"][cle]
        print(f"{libelle}: {detail['value'] if detail['value'] is not None else 'not evaluated'} [{detail['method']}]")
    print(f"\nCritical issues: {len(q['critical_issues'])}\nWarnings: {len(q['warnings'])}\nInfos: {len(q['infos'])}")
    print(f"Revisions: {q['revisions']['count']}\nHuman interventions: {q['human_interventions']['count']}\n\nSTATUS: {q['status']}")


def construire_rapport(chapitre, etape, avec_critique=True, ecrire=True):
    """Sans la critique, le rapport repose sur le code seul : c'est la mesure comparable entre deux architectures."""
    matrice = construire(chapitre)
    couvertures = couverture(matrice, etape)
    critique, etat_critique = lire_critique(chapitre, etape) if avec_critique else ([], "non utilisée")
    completude, constats_completude = mesurer_completude(chapitre, etape)
    constats = controler_etape(chapitre, etape) + controler_couverture(matrice, etape) \
        + constats_completude + verifier_sources(chapitre, etape) + critique
    scores = calculer_scores(constats, couvertures, etat_critique, etape, completude)
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
    if not ecrire:
        return rapport
    revue = Path(chapitre) / ".travail" / "revue"
    revue.mkdir(parents=True, exist_ok=True)
    (revue / "qualite.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    (revue / "quality_report.json").write_text(
        json.dumps(construire_quality_report(chapitre, rapport), ensure_ascii=False, indent=2), encoding="utf-8")
    ecrire_modele(chapitre)
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
    etat = lire_etat(chapitre)
    cycles = etat["cycles"].get(etape, 0)

    def tracer(decision):
        etat.setdefault("historique", []).append(
            {"stage": etape, "date": time.strftime("%Y-%m-%dT%H:%M:%S"), "decision": decision, "cycle": cycles,
             "issues": rapport["critiques"] + rapport["avertissements"], "critical": rapport["critiques"]})
        ecrire_etat(chapitre, etat)

    if not rapport["critiques"] and not rapport["avertissements"]:
        tracer("HUMAN_VALIDATION")
        return "DECISION: VALIDATION_HUMAINE"
    if cycles >= max_cycles:
        tracer("REVISION_LIMIT_REACHED")
        return "⚠ Révision maximale atteinte.\nUne validation humaine est requise.\nDECISION: VALIDATION_HUMAINE"
    cycles += 1
    etat["cycles"][etape] = cycles
    tracer(f"REVISION {cycles}/{max_cycles}")
    return f"DECISION: REVISION {cycles}/{max_cycles}"


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
    for nom in ("rapport", "decider", "valider", "quality-report"):
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
    if a.commande == "quality-report":
        afficher_quality_report(construire_quality_report(a.chapitre, construire_rapport(a.chapitre, a.etape)))
    elif a.commande == "decider":
        print(decider(a.chapitre, a.etape, lire_max_cycles(a.max_cycles)))
    else:
        valider(a.chapitre, a.etape, a.decision)


if __name__ == "__main__":
    main()
