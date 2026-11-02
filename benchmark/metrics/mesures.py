"""Calcule les métriques du benchmark à partir du rapport qualité, et vérifie le résultat attendu d'un cas.

Une valeur à None veut dire « non mesuré », jamais zéro. Ces indicateurs sont techniques et structurels :
ils ne mesurent pas directement la qualité pédagogique.
"""
import csv
import json
from pathlib import Path

from modele import construire_modele
from qualite import construire_rapport

ETAPE = "livrables"
# La méthode de chaque métrique : aucun résultat ne doit pouvoir passer pour plus solide qu'il n'est.
METHODES = {
    "objective_coverage": "deterministic", "timing_validity": "deterministic", "evaluation_quality": "deterministic+llm_critic",
    "content_completeness": "deterministic", "hallucination_count": "deterministic_heuristic+llm_critic",
    "critical_error_count": "deterministic+llm_critic", "warning_count": "deterministic+llm_critic", "human_interventions": "recorded",
    "revision_count": "recorded", "generation_time": "measured_by_runner", "accuracy": "llm_critic",
}
COLONNES = list(METHODES)


def mesurer(chapitre, execution=None):
    """Renvoie les métriques d'un chapitre. `execution` apporte ce que seul l'exécuteur connaît."""
    execution = execution or {}
    rapport = construire_rapport(chapitre, ETAPE)
    m = rapport["metriques"]
    temps = [c for c in rapport["constats"] if c["category"] == "timing" and c["severity"] != "info"]
    interventions = m["human_interventions"] if execution.get("human_interventions_recorded") else None
    return {"objective_coverage": m["objective_coverage"], "timing_validity": not temps, "evaluation_quality": m["evaluation_quality"],
            "content_completeness": m["content_completeness"], "hallucination_count": m["hallucination_count"],
            "critical_error_count": m["critical_error_count"], "warning_count": m["warning_count"], "human_interventions": interventions,
            "revision_count": m["revision_count"], "generation_time": execution.get("generation_time"), "accuracy": m["accuracy"],
            "critic": rapport["critique"], "status": rapport["statut"]}


def verifier_cas(cas, chapitre):
    """Compare le chapitre au résultat attendu du cas. Renvoie la liste des écarts."""
    a = cas.attendu
    rapport = construire_rapport(chapitre, ETAPE)
    modele = construire_modele(chapitre)
    m = mesurer(chapitre)
    textes = " ".join(c["problem"] for c in rapport["constats"])
    ecarts = []

    def egal(nom, obtenu, attendu):
        if obtenu != attendu:
            ecarts.append(f"{nom} : {obtenu} au lieu de {attendu}")

    def au_moins(nom, obtenu, minimum):
        if obtenu < minimum:
            ecarts.append(f"{nom} : {obtenu} au lieu d'au moins {minimum}")

    if "critiques" in a:
        egal("problèmes critiques", rapport["critiques"], a["critiques"])
    if "avertissements" in a:
        egal("avertissements", rapport["avertissements"], a["avertissements"])
    if "critiques_min" in a:
        au_moins("problèmes critiques", rapport["critiques"], a["critiques_min"])
    if "couverture" in a:
        egal("couverture", m["objective_coverage"], a["couverture"])
    if "timing_valide" in a:
        egal("temps valide", m["timing_validity"], a["timing_valide"])
    if "completude" in a:
        egal("complétude", m["content_completeness"], a["completude"])
    if "completude_max" in a and (m["content_completeness"] is None or m["content_completeness"] > a["completude_max"]):
        ecarts.append(f"complétude : {m['content_completeness']} au lieu d'au plus {a['completude_max']}")
    if "hallucinations_min" in a:
        au_moins("hallucinations", m["hallucination_count"], a["hallucinations_min"])
    if "seances" in a:
        egal("séances", len(modele["sessions"]), a["seances"])
    if "evaluations_min" in a:
        au_moins("évaluations", len(modele["evaluations"]), a["evaluations_min"])
    for objectif, statut in a.get("statuts", {}).items():
        egal(objectif, modele["traceability"][objectif]["status"], statut)
    ecarts += [f"constat attendu absent : {t}" for t in a.get("contient", []) if t not in textes]
    return ecarts


def agreger(lignes):
    """Résume les lignes d'un mode. Une métrique sans aucune valeur reste « non mesurée »."""
    resume = {"courses": len({l["case"] for l in lignes}), "runs": len(lignes),
              "failed_runs": sum(l["run_status"] != "completed" for l in lignes)}
    valides = [l for l in lignes if l["run_status"] == "completed"]
    for colonne in COLONNES:
        valeurs = [l[colonne] for l in valides if l[colonne] is not None]
        if colonne == "timing_validity":
            valeurs = [100 * v for v in valeurs]
        resume[colonne] = {"mean": round(sum(valeurs) / len(valeurs), 2) if valeurs else None, "n": len(valeurs)}
    return resume


def exporter(lignes, dossier):
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "benchmark_results.json").write_text(json.dumps(lignes, ensure_ascii=False, indent=2), encoding="utf-8")
    colonnes = ["run_id", "runner", "simulated", "mode", "case", "repetition", "run_status", *COLONNES, "critic", "status"]
    with (dossier / "benchmark_results.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
