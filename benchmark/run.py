#!/usr/bin/env python3
"""Lance le benchmark de Prépa Cours et produit ses rapports.

Usage : python3 benchmark/run.py verify
        python3 benchmark/run.py run --runner fixture
        python3 benchmark/run.py run --runner claude --i-accept-llm-costs [--cases 01_coherent] [--repetitions 3] [--model NOM]
        python3 benchmark/run.py report [identifiant de l'exécution]

Ce benchmark mesure des indicateurs techniques et structurels, pas directement la qualité pédagogique.
"""
import argparse
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
for dossier in (ICI, ICI / "fixtures", ICI / "metrics", ICI.parent / "scripts"):
    sys.path.insert(0, str(dossier))

import cas as cas_benchmark  # noqa: E402
import mesures  # noqa: E402
from runners import ECHEC, MODES, TERMINE, ClaudeRunner, FixtureRunner  # noqa: E402

SORTIES = ICI / "outputs"
RAPPORTS = ICI / "reports"
AVERTISSEMENT = "Ce benchmark mesure des indicateurs techniques et structurels, pas directement la qualité pédagogique."
AVERTISSEMENT_SIMULE = ("⚠ DONNÉES SIMULÉES : ces sorties sont des fixtures écrites à la main, identiques dans les deux modes.\n"
                        "   Elles testent le banc d'essai. Aucune conclusion sur les architectures ne peut en être tirée.")
LIBELLES = (("objective_coverage", "Objective coverage", "%"), ("timing_validity", "Timing validity", "%"),
            ("evaluation_quality", "Evaluation quality", "/100"), ("content_completeness", "Content completeness", "%"),
            ("hallucination_count", "Hallucinations (average)", ""), ("critical_error_count", "Critical errors (average)", ""),
            ("warning_count", "Warnings (average)", ""), ("human_interventions", "Human interventions (average)", ""),
            ("revision_count", "Revisions (average)", ""), ("generation_time", "Generation time (average)", " s"),
            ("accuracy", "Accuracy (critic)", "/100"), ("critic_critical_count", "Critical issues found by critic (average)", ""))


def verifier():
    """Vérifie les contrôles : chaque cas doit donner exactement son résultat attendu."""
    echecs = 0
    for cas in cas_benchmark.CAS:
        with tempfile.TemporaryDirectory() as tmp:
            cas_benchmark.materialiser(cas, tmp)
            ecarts = mesures.verifier_cas(cas, tmp)
        print(f"{'✓' if not ecarts else '✗'} {cas.id} : {cas.description}")
        for ecart in ecarts:
            print(f"    {ecart}")
        echecs += bool(ecarts)
    print(f"\nComportements attendus vérifiés : {len(cas_benchmark.CAS) - echecs}/{len(cas_benchmark.CAS)}")
    print("Ce résultat teste les contrôles du système sur des données synthétiques, pas la qualité d'une génération.")
    return echecs


def commit_git():
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ICI, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def lancer(runner, modes, cas_choisis, repetitions, identifiant=None, sorties=SORTIES):
    """Exécute chaque cas dans chaque mode. Un échec est enregistré, jamais remplacé par une valeur inventée."""
    identifiant = identifiant or time.strftime("%Y%m%d-%H%M%S")
    dossier = Path(sorties) / identifiant
    if dossier.exists():
        sys.exit(f"Cette exécution existe déjà : {dossier}")
    dossier.mkdir(parents=True)
    (dossier / "manifest.json").write_text(json.dumps(
        {"run_id": identifiant, "date": time.strftime("%Y-%m-%dT%H:%M:%S"), "runner": runner.nom, "simulated": runner.simulated, "model": runner.modele,
         "modes": list(modes), "cases": [c.id for c in cas_choisis], "repetitions": repetitions, "git_commit": commit_git(),
         "python": platform.python_version()}, ensure_ascii=False, indent=2), encoding="utf-8")
    for mode in modes:
        for cas in cas_choisis:
            for repetition in range(1, repetitions + 1):
                base = dossier / mode / cas.id / f"repetition-{repetition}"
                chapitre = base / "output"
                chapitre.mkdir(parents=True)
                print(f"{mode} / {cas.id} / {repetition}", flush=True)
                execution = runner.executer(cas, mode, chapitre, base / "run.log")
                ligne = {"run_id": identifiant, "runner": runner.nom, "simulated": runner.simulated, "mode": mode, "case": cas.id,
                         "repetition": repetition, "run_status": execution["run_status"], "error": execution.get("error")}
                produit = (chapitre / ".travail" / "objectifs.md").is_file()
                if execution["run_status"] == TERMINE and not produit:
                    ligne.update(run_status=ECHEC, error="Aucune sortie exploitable : .travail/objectifs.md est absent.")
                vides = {c: None for c in mesures.COLONNES}
                ligne.update(mesures.mesurer(chapitre, execution) if ligne["run_status"] == TERMINE else {**vides, "generation_time": execution.get("generation_time")})
                (base / "metrics.json").write_text(json.dumps(ligne, ensure_ascii=False, indent=2), encoding="utf-8")
    return identifiant


def lire_lignes(dossier):
    return [json.loads(c.read_text(encoding="utf-8")) for c in sorted(dossier.rglob("metrics.json"))]


def formater(metrique, unite):
    if metrique["mean"] is None:
        return "non mesuré"
    return f"{metrique['mean']:g}{unite} (n={metrique['n']})"


def rapporter(identifiant=None, sorties=SORTIES, rapports=RAPPORTS):
    sorties = Path(sorties)
    if identifiant is None:
        executions = sorted(p.name for p in sorties.iterdir() if p.is_dir()) if sorties.is_dir() else []
        if not executions:
            sys.exit("Aucune exécution : lancez d'abord « run.py run ».")
        identifiant = executions[-1]
    dossier = sorties / identifiant
    if not dossier.is_dir():
        sys.exit(f"Exécution introuvable : {identifiant}")
    manifeste = json.loads((dossier / "manifest.json").read_text(encoding="utf-8"))
    lignes = lire_lignes(dossier)
    lignes_texte = ["=" * 36, "PREPA-COURS BENCHMARK", "=" * 36, ""]
    if manifeste["simulated"]:
        lignes_texte += [AVERTISSEMENT_SIMULE, ""]
    lignes_texte += [f"Run: {identifiant}", f"Runner: {manifeste['runner']}", f"Model: {manifeste['model'] or 'non indiqué'}",
                     f"Courses: {len(manifeste['cases'])}", f"Repetitions: {manifeste['repetitions']}", ""]
    for mode in manifeste["modes"]:
        titre = {"single_agent": "Single Agent", "multi_agent": "Multi-Agent"}[mode]
        resume = mesures.agreger([l for l in lignes if l["mode"] == mode])
        lignes_texte += [titre, "-" * len(titre), f"Runs: {resume['runs']}, failed: {resume['failed_runs']}"]
        lignes_texte += [f"{libelle}: {formater(resume[cle], unite)}" for cle, libelle, unite in LIBELLES]
        lignes_texte.append("")
    lignes_texte += [AVERTISSEMENT, "Aucune différence affichée n'est testée statistiquement par cet outil."]
    texte = "\n".join(lignes_texte) + "\n"
    cible = Path(rapports) / identifiant
    mesures.exporter(lignes, cible)
    (cible / "report.txt").write_text(texte, encoding="utf-8")
    print(texte)
    print(f"Rapport : {cible}")
    return texte


def main():
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    sous = p.add_subparsers(dest="commande", required=True)
    sous.add_parser("verify")
    r = sous.add_parser("run")
    r.add_argument("--runner", choices=("fixture", "claude"), required=True)
    r.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    r.add_argument("--cases", nargs="+")
    r.add_argument("--repetitions", type=int, default=1)
    r.add_argument("--run-id")
    r.add_argument("--claude", default="claude", help="Commande qui lance Claude Code.")
    r.add_argument("--model")
    r.add_argument("--timeout", type=int, default=1800)
    r.add_argument("--max-revisions", type=int, default=2)
    r.add_argument("--i-accept-llm-costs", action="store_true")
    r.add_argument("--output-dir", default=str(SORTIES))
    r.add_argument("--reports-dir", default=str(RAPPORTS))
    c = sous.add_parser("report")
    c.add_argument("run_id", nargs="?")
    c.add_argument("--output-dir", default=str(SORTIES))
    c.add_argument("--reports-dir", default=str(RAPPORTS))
    a = p.parse_args()
    if a.commande == "verify":
        sys.exit(1 if verifier() else 0)
    if a.commande == "report":
        rapporter(a.run_id, a.output_dir, a.reports_dir)
        return
    if a.repetitions < 1:
        sys.exit("--repetitions doit valoir au moins 1.")
    try:
        choisis = [cas_benchmark.trouver(i) for i in a.cases] if a.cases else cas_benchmark.CAS
    except KeyError as e:
        sys.exit(f"Cas inconnu : {e}. Cas disponibles : {', '.join(c.id for c in cas_benchmark.CAS)}")
    if a.runner == "claude":
        if not a.i_accept_llm_costs:
            sys.exit("Ce mode lance de vraies générations, payantes et longues : relancez avec --i-accept-llm-costs.")
        runner = ClaudeRunner(a.claude, a.model, a.timeout, a.max_revisions)
    else:
        runner = FixtureRunner()
    rapporter(lancer(runner, a.modes, choisis, a.repetitions, a.run_id, a.output_dir), a.output_dir, a.reports_dir)


if __name__ == "__main__":
    main()
