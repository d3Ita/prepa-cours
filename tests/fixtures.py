"""Un cours synthétique complet et valide, à dégrader dans les tests pour produire chaque défaut."""
import json
import os
import time
from pathlib import Path

COURS = """# La digestion
Le système digestif transforme les aliments en nutriments.
L'estomac brasse les aliments et les mélange aux sucs digestifs.
L'intestin grêle absorbe les nutriments, qui passent dans le sang.
La digestion complète dure environ 24 heures.
"""
OBJECTIFS = """# Objectifs : la digestion

Niveau : Cinquième
Classe : 5e A
Matière : SVT
Durée totale : 2 h

- OBJ1 : Décrire le rôle de l'estomac.
  - Notions : estomac, sucs digestifs
- OBJ2 : Expliquer l'absorption des nutriments.
  - Notions : intestin grêle, nutriments

## Découpage

Séance 1 : 1 h — OBJ1
Séance 2 : 1 h — OBJ2
"""
CATEGORIES = ("factual", "pedagogical", "timing", "coherence", "evaluation", "hallucination")


def scenario(objectif):
    return (f"# Séance\n\n## 0-20 min — Découverte\n- Objectif visé : {objectif}\n"
            f"## 20-50 min — Activité : observer un schéma\n- Objectif visé : {objectif}\n"
            f"## 50-60 min — QCM\n- Objectif visé : {objectif}\n")


def diapos(objectif):
    return f"# Le système digestif\n- Les aliments deviennent des nutriments\n> Objectif : {objectif}\n"


def qcm(sujet="Que fait l'estomac ?"):
    return "# QCM\n\n" + "".join(f"## Question {i}\n{sujet}\nA. Il brasse les aliments\nB. Il voit\nC. Il respire\nD. Il court\n\n"
                                 for i in range(1, 6))


def corrige(objectif):
    return "".join(f"Question {i} : {l} ({objectif}) — D'après le cours.\n" for i, l in enumerate("ABCDA", 1))


def ecrire_chapitre(dossier, **remplacements):
    """Une clé remplace un fichier de .travail : seance_1__qcm_corrige remplace seance-1/qcm-corrige.md."""
    chapitre = Path(dossier)
    fichiers = {"objectifs.md": OBJECTIFS}
    for n, objectif in ((1, "OBJ1"), (2, "OBJ2")):
        fichiers |= {f"seance-{n}/scenario.md": scenario(objectif), f"seance-{n}/diapos.md": diapos(objectif),
                     f"seance-{n}/qcm.md": qcm(), f"seance-{n}/qcm-corrige.md": corrige(objectif)}
    for cle, texte in remplacements.items():
        fichiers[cle.replace("seance_", "seance-").replace("__", "/").replace("qcm_corrige", "qcm-corrige") + ".md"] = texte
    for relatif, texte in fichiers.items():
        chemin = chapitre / ".travail" / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
    (chapitre / "Cours").mkdir(exist_ok=True)
    (chapitre / "Cours" / "cours.txt").write_text(COURS, encoding="utf-8")
    for n in (1, 2):
        for livrable in (f"Cours/seance-{n}-scenario.docx", f"Diapos/seance-{n}-diapos.pptx",
                         f"QCM/seance-{n}-qcm.docx", f"Corrections/seance-{n}-qcm-corrige.docx"):
            (chapitre / livrable).parent.mkdir(exist_ok=True)
            (chapitre / livrable).touch()
    return chapitre


def verifications(categories=CATEGORIES):
    return [{"category": c, "control": f"Contrôle {c}."} for c in categories]


def ecrire_critique(chapitre, etape="livrables", constats=(), verifs=None):
    """Écrit la critique, plus récente que tous les textes : les dates ne dépendent pas de l'horloge du test."""
    revue = Path(chapitre) / ".travail" / "revue"
    revue.mkdir(parents=True, exist_ok=True)
    chemin = revue / "critique.json"
    chemin.write_text(json.dumps({"etape": etape, "verifications": verifications() if verifs is None else verifs,
                                  "constats": list(constats)}, ensure_ascii=False), encoding="utf-8")
    plus_recent = max(f.stat().st_mtime for f in (Path(chapitre) / ".travail").rglob("*.md"))
    os.utime(chemin, (plus_recent + 10, plus_recent + 10))


def vieillir_revue(chapitre):
    """Rend les textes plus récents que la critique et que les validations, comme après une révision."""
    futur = time.time() + 1000
    chemin = Path(chapitre) / ".travail" / "objectifs.md"
    os.utime(chemin, (futur, futur))


def constat(severity="warning", category="factual", location="seance-1", problem="Un problème", evidence="Une preuve",
            suggestion="Une suggestion", **autres):
    return {"severity": severity, "category": category, "location": location, "problem": problem,
            "evidence": evidence, "suggestion": suggestion, **autres}
