#!/usr/bin/env python3
"""Exemple reproductible du parcours complet, sans modèle de langage ni compte.

Les étapes rédigées par des agents (planification, génération, critique, révision) et les réponses du prof sont
SIMULÉES par des textes écrits à l'avance. En revanche, les contrôles, le score, la boucle de révision, le modèle
de cours et les documents sont produits par le vrai code. Ce parcours montre comment les étapes communiquent :
il ne dit rien de la qualité d'une vraie génération.

Usage : python3 benchmark/parcours_mock.py [dossier de sortie]
"""
import json
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
for dossier in (ICI / "fixtures", ICI.parent / "scripts"):
    sys.path.insert(0, str(dossier))

import cas as cas_benchmark  # noqa: E402
import generer  # noqa: E402
import modele  # noqa: E402
import qualite  # noqa: E402
from extraire_texte import extraire  # noqa: E402

CATEGORIES = ("factual", "pedagogical", "timing", "coherence", "evaluation", "hallucination")
MAX_REVISIONS = 2


def critique_simulee(chapitre, etape, constats=()):
    """Écrit ce que l'agent critique rendrait, au format réel, toujours en dernier."""
    chemin = Path(chapitre) / ".travail" / "revue" / "critique.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({"etape": etape, "verifications": [{"category": c, "control": "Contrôle simulé pour cet exemple."} for c in CATEGORIES],
                                  "constats": list(constats)}, ensure_ascii=False, indent=2), encoding="utf-8")


def executer(chapitre, afficher=print):
    """Déroule le parcours et renvoie le rapport final : chaque étape lit ce que la précédente a écrit."""
    chapitre = Path(chapitre)
    cas = cas_benchmark.trouver("01_coherent")

    afficher("[1/8] Input course (réel)")
    cas_benchmark.ecrire_source(cas, chapitre)
    source = extraire(chapitre / "Cours" / cas.cours)
    afficher(f"      {cas.cours} : {len(source)} lignes")

    afficher("[2/8] Analysis (réel : lecture et plan du document)")
    sections = [l for l in source if l.startswith("#")]
    afficher(f"      {len(sections)} titres trouvés")

    afficher("[3/8] Planning (texte SIMULÉ, contrôles réels)")
    objectifs = chapitre / ".travail" / "objectifs.md"
    objectifs.parent.mkdir(parents=True, exist_ok=True)
    objectifs.write_text(cas.fichiers["objectifs.md"], encoding="utf-8")
    critique_simulee(chapitre, "decoupage")
    afficher(f"      {qualite.decider(chapitre, 'decoupage', MAX_REVISIONS)}")
    qualite.valider(chapitre, "decoupage", "valider")

    afficher("[4/8] Generation (textes SIMULÉS, documents réels)")
    cas_benchmark.materialiser(cas, chapitre)
    corrige = chapitre / ".travail" / "seance-1" / "qcm-corrige.md"
    juste = corrige.read_text(encoding="utf-8")
    corrige.write_text(juste.replace("Question 1 : A", "Question 1 : B"), encoding="utf-8")
    afficher("      Une erreur est glissée dans le corrigé : la question 1 donne B au lieu de A.")
    afficher(f"      Le code seul ne peut pas la voir : {qualite.construire_rapport(chapitre, 'livrables', avec_critique=False, ecrire=False)['critiques']} problème bloquant.")

    afficher("[5/8] Critic (constat SIMULÉ, décision réelle)")
    critique_simulee(chapitre, "livrables", [{
        "severity": "critical", "category": "evaluation", "location": "seance-1", "problem": "La réponse B de la question 1 est fausse.",
        "evidence": "Le cours dit que l'estomac brasse les aliments : c'est le choix A.", "suggestion": "Remplacer B par A.", "provenance": "source"}])
    decision = qualite.decider(chapitre, "livrables", MAX_REVISIONS)
    afficher(f"      {decision}")

    afficher("[6/8] Revision (correction SIMULÉE, décision réelle)")
    corrige.write_text(juste, encoding="utf-8")
    generer.vers_docx(juste, chapitre / "Corrections" / "seance-1-qcm-corrige.docx")
    afficher(f"      Après correction : {qualite.decider(chapitre, 'livrables', MAX_REVISIONS)}")
    critique_simulee(chapitre, "livrables")
    fin = qualite.decider(chapitre, "livrables", MAX_REVISIONS)
    afficher(f"      Après une nouvelle critique : {fin}")

    afficher("[7/8] Quality report (réel)")
    rapport = qualite.construire_rapport(chapitre, "livrables")
    qualite.afficher_quality_report(qualite.construire_quality_report(chapitre, rapport))

    afficher("\n[8/8] Human validation (réponse SIMULÉE) et final output (réel)")
    qualite.valider(chapitre, "livrables", "valider")
    rapport = qualite.construire_rapport(chapitre, "livrables")
    modele.ecrire_modele(chapitre)
    documents = sorted(p.relative_to(chapitre).as_posix() for p in chapitre.rglob("*") if p.suffix in (".docx", ".pptx"))
    afficher(f"      STATUS: {rapport['statut']}")
    afficher(f"      {len(documents)} documents, dans {chapitre}")
    return {"rapport": rapport, "documents": documents, "decisions": [decision, fin]}


if __name__ == "__main__":
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    print("EXEMPLE SIMULÉ : aucun modèle de langage n'est appelé.\n")
    if len(sys.argv) > 1:
        if Path(sys.argv[1]).exists() and any(Path(sys.argv[1]).iterdir()):
            sys.exit(f"{sys.argv[1]} n'est pas vide : choisissez un dossier neuf.")
        executer(sys.argv[1])
    else:
        with tempfile.TemporaryDirectory() as tmp:
            executer(tmp)
