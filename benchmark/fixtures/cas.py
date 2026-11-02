"""Les dix cas du benchmark : des sorties synthétiques écrites à la main, chacune avec un résultat attendu.

Ces fixtures testent les contrôles du système. Elles ne sont pas des sorties d'un modèle de langage et
ne disent rien de la qualité d'une architecture.
"""
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from generer import vers_docx, vers_pptx

COURS = Path(__file__).resolve().parent.parent / "courses"
ETAPE_REFERENCE = "livrables"


def objectifs(titre, niveau, matiere, duree, objectifs_texte, decoupage):
    return f"# Objectifs : {titre}\n\nNiveau : {niveau}\nMatière : {matiere}\nDurée totale : {duree}\n\n{objectifs_texte}\n\n## Découpage\n\n{decoupage}\n"


def scenario(titre, objectif, notions, duree=60):
    decouverte, pratique = duree // 3, duree - 10
    return (f"# {titre}\n- Notions : {notions}\n\n## 0-{decouverte} min — Découverte\n- Objectif visé : {objectif}\n\n"
            f"## {decouverte}-{pratique} min — Activité : observer un schéma\n- Objectif visé : {objectif}\n\n"
            f"## {pratique}-{duree} min — QCM\n- Objectif visé : {objectif}\n")


def diapos(phrase, objectif):
    return f"# {phrase}\n- {phrase}\n> Objectif : {objectif}\n"


def qcm(question, bonne):
    fausses = ["Il voit", "Il respire", "Il court"]
    return "# QCM\n\n" + "".join(
        f"## Question {i}\n{question}\nA. {bonne}\nB. {fausses[0]}\nC. {fausses[1]}\nD. {fausses[2]}\n\n" for i in range(1, 6))


def corrige(objectif, lettres="ABCDA"):
    return "".join(f"Question {i} : {l} ({objectif}) — D'après le cours.\n" for i, l in enumerate(lettres, 1))


OBJECTIFS_DIGESTION = objectifs(
    "la digestion", "Cinquième", "SVT", "2 h",
    "- OBJ1 : Décrire le rôle de l'estomac.\n  - Notions : estomac, sucs digestifs\n"
    "- OBJ2 : Expliquer l'absorption des nutriments.\n  - Notions : intestin grêle, nutriments",
    "Séance 1 : 1 h — OBJ1\nSéance 2 : 1 h — OBJ2")
NOTIONS_DIGESTION = "estomac, sucs digestifs, intestin grêle, nutriments"


def digestion(**remplacements):
    fichiers = {
        "objectifs.md": OBJECTIFS_DIGESTION,
        "seance-1/scenario.md": scenario("La digestion : l'estomac", "OBJ1", NOTIONS_DIGESTION),
        "seance-1/diapos.md": diapos("L'estomac brasse les aliments", "OBJ1"),
        "seance-1/qcm.md": qcm("Que fait l'estomac ?", "Il brasse les aliments"),
        "seance-1/qcm-corrige.md": corrige("OBJ1"),
        "seance-2/scenario.md": scenario("La digestion : l'intestin grêle", "OBJ2", NOTIONS_DIGESTION),
        "seance-2/diapos.md": diapos("L'intestin grêle absorbe les nutriments", "OBJ2"),
        "seance-2/qcm.md": qcm("Que fait l'intestin grêle ?", "Il absorbe les nutriments"),
        "seance-2/qcm-corrige.md": corrige("OBJ2"),
    }
    fichiers.update(remplacements)
    return {k: v for k, v in fichiers.items() if v is not None}


def electricite():
    themes = [("le circuit", "OBJ1", "Un circuit fermé permet le passage du courant"), ("la tension", "OBJ2", "La tension se mesure en volts"),
              ("l'intensité", "OBJ3", "L'intensité se mesure en ampères"), ("la puissance", "OBJ4", "La puissance dépend de la tension et de l'intensité")]
    fichiers = {"objectifs.md": objectifs(
        "l'électricité", "Seconde", "Physique-chimie", "6 h",
        "\n".join(f"- {o} : Expliquer {t}.\n  - Notions : {t.split(' ', 1)[-1] if t.startswith('le ') or t.startswith('la ') else 'intensité'}" for t, o, _ in themes),
        "Séance 1 : 1 h 30 — OBJ1\nSéance 2 : 1 h 30 — OBJ2\nSéance 3 : 1 h 30 — OBJ3\nSéance 4 : 1 h 30 — OBJ4")}
    for n, (theme, objectif, phrase) in enumerate(themes, 1):
        fichiers |= {f"seance-{n}/scenario.md": scenario(f"L'électricité : {theme}", objectif, theme, 90),
                     f"seance-{n}/diapos.md": diapos(phrase, objectif), f"seance-{n}/qcm.md": qcm("Quelle est la bonne réponse ?", phrase),
                     f"seance-{n}/qcm-corrige.md": corrige(objectif)}
    fichiers["evaluation.md"] = ("# Évaluation\nTotal : 12 points.\n\n## Question 1 (3 points)\nQuelle est la bonne réponse ?\nA. Un circuit fermé\nB. Il voit\nC. Il court\n\n"
                                 "## Question 2 (3 points)\nType : vrai-faux\nLa tension se mesure en volts.\n\n"
                                 "## Question 3 (3 points)\nType : etude-de-cas\nAnalysez un circuit.\n[réponse: 3]\n\n"
                                 "## Question 4 (3 points)\nType : reflexion\nDe quoi dépend la puissance ?\n[réponse: 3]\n")
    fichiers["evaluation.md"] = fichiers["evaluation.md"].replace("## Question 1 (3 points)\n", "## Question 1 (3 points)\nType : qcm\n")
    fichiers["corrige.md"] = "Question 1 : A (OBJ1)\nQuestion 2 : Vrai (OBJ2)\nQuestion 3 : Une analyse du circuit (OBJ3)\nQuestion 4 : Elle dépend de la tension et de l'intensité (OBJ4)\n"
    return fichiers


@dataclass
class Cas:
    id: str
    description: str
    cours: str
    consignes: str
    fichiers: dict
    attendu: dict = field(default_factory=dict)


CAS = [
    Cas("01_coherent", "Cours parfaitement cohérent.", "digestion.txt", "Cinquième, SVT, 2 h en 2 séances d'1 h", digestion(),
        {"critiques": 0, "avertissements": 0, "couverture": 100, "timing_valide": True, "completude": 100}),
    Cas("02_objectif_non_couvert", "Un objectif n'est relié à aucune activité ni évaluation.", "digestion.txt", "Cinquième, SVT, 2 h en 2 séances d'1 h",
        digestion(**{"objectifs.md": OBJECTIFS_DIGESTION.replace("\n\n## Découpage", "\n- OBJ3 : Citer un organe.\n\n## Découpage")
                     .replace("Séance 1 : 1 h — OBJ1", "Séance 1 : 1 h — OBJ1, OBJ3")}),
        {"critiques_min": 1, "statuts": {"OBJ-003": "MISSING", "OBJ-001": "COMPLETE"}, "contient": ["OBJ3 : manque"]}),
    Cas("03_temps_impossible", "Le scénario dure plus longtemps que la séance.", "digestion.txt", "Cinquième, SVT, 2 h en 2 séances d'1 h",
        digestion(**{"seance-1/scenario.md": scenario("La digestion : l'estomac", "OBJ1", NOTIONS_DIGESTION, 107)}),
        {"timing_valide": False, "contient": ["le scénario dure 107 min pour une séance de 60 min"]}),
    Cas("04_plusieurs_bonnes_reponses", "Une question de QCM a deux bonnes réponses.", "digestion.txt", "Cinquième, SVT, 2 h en 2 séances d'1 h",
        digestion(**{"seance-1/qcm-corrige.md": corrige("OBJ1").replace("Question 1 : A", "Question 1 : A, C")}),
        {"critiques_min": 1, "contient": ["la question 1 du QCM a plusieurs bonnes réponses : A, C"]}),
    Cas("05_corrige_incorrect", "Le corrigé donne une réponse qui n'existe pas dans le QCM.", "digestion.txt", "Cinquième, SVT, 2 h en 2 séances d'1 h",
        digestion(**{"seance-2/qcm-corrige.md": corrige("OBJ2").replace("Question 3 : C", "Question 3 : Z")}),
        {"critiques_min": 1, "contient": ["la réponse Z de la question 3 n'existe pas dans le QCM"]}),
    Cas("06_hallucination", "Les diapos citent un nom et une date absents du cours.", "digestion.txt", "Cinquième, SVT, 2 h en 2 séances d'1 h",
        digestion(**{"seance-1/diapos.md": "# L'estomac\n- Le chercheur Beaumont a décrit l'estomac en 1833\n> Objectif : OBJ1\n"}),
        {"hallucinations_min": 2, "contient": ["« 1833 » n'apparaît pas", "« Beaumont » n'apparaît pas"]}),
    Cas("07_cours_incomplet", "Une section du cours, une notion et des documents manquent.", "digestion-longue.txt", "Cinquième, SVT, 2 h en 2 séances d'1 h",
        digestion(**{"objectifs.md": OBJECTIFS_DIGESTION.replace("sucs digestifs", "bile"), "seance-2/qcm.md": None, "seance-2/diapos.md": None}),
        {"critiques_min": 2, "completude_max": 90, "contient": ["La section « Le foie et la vésicule biliaire »", "La notion « bile »", "seance-2 : qcm.md est absent"]}),
    Cas("08_contradictions", "La durée annoncée et un corrigé se contredisent.", "digestion.txt", "Cinquième, SVT, 2 h en 2 séances d'1 h",
        digestion(**{"objectifs.md": OBJECTIFS_DIGESTION.replace("Durée totale : 2 h", "Durée totale : 3 h"),
                     "seance-1/qcm-corrige.md": corrige("OBJ1") + "Question 1 : C (OBJ1)\n"}),
        {"critiques_min": 1, "contient": ["Les séances totalisent 120 min", "le corrigé se contredit sur la question 1"]}),
    Cas("09_tres_court", "Une seule séance très courte, sans défaut.", "court.txt", "Sixième, SVT, 30 min en 1 séance",
        {"objectifs.md": objectifs("le cycle de l'eau", "Sixième", "SVT", "30 min", "- OBJ1 : Décrire le cycle de l'eau.\n  - Notions : nuages, pluie",
                                   "Séance 1 : 30 min — OBJ1"),
         "seance-1/scenario.md": scenario("Le cycle de l'eau", "OBJ1", "nuages, pluie", 30),
         "seance-1/diapos.md": diapos("L'eau forme des nuages, puis de la pluie", "OBJ1"),
         "seance-1/qcm.md": qcm("Que forme l'eau ?", "Des nuages"), "seance-1/qcm-corrige.md": corrige("OBJ1")},
        {"critiques": 0, "avertissements": 0, "couverture": 100, "seances": 1}),
    Cas("10_complexe", "Quatre séances et une évaluation finale avec plusieurs types de questions.", "electricite.txt", "Seconde, physique-chimie, 6 h en 4 séances d'1 h 30",
        electricite(), {"critiques": 0, "avertissements": 0, "couverture": 100, "seances": 4, "evaluations_min": 24}),
]


def trouver(identifiant):
    for cas in CAS:
        if cas.id == identifiant:
            return cas
    raise KeyError(identifiant)


def ecrire_source(cas, chapitre):
    dossier = Path(chapitre) / "Cours"
    dossier.mkdir(parents=True, exist_ok=True)
    shutil.copy2(COURS / cas.cours, dossier / cas.cours)


LIVRABLES = {"scenario.md": "Cours/seance-{n}-scenario.docx", "qcm.md": "QCM/seance-{n}-qcm.docx",
             "qcm-corrige.md": "Corrections/seance-{n}-qcm-corrige.docx"}


def materialiser(cas, chapitre):
    """Écrit les textes de .travail et génère les vrais .docx et .pptx du cas."""
    chapitre = Path(chapitre)
    ecrire_source(cas, chapitre)
    for categorie in ("Diapos", "QCM", "Evaluations", "Corrections"):
        (chapitre / categorie).mkdir(exist_ok=True)
    for relatif, texte in cas.fichiers.items():
        chemin = chapitre / ".travail" / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
        seance, _, nom = relatif.rpartition("/")
        if not seance:
            sorties = {"evaluation.md": "Evaluations/evaluation.docx", "corrige.md": "Corrections/evaluation-corrige.docx"}
            if nom in sorties:
                vers_docx(texte, chapitre / sorties[nom])
            continue
        numero = seance.split("-")[1]
        if nom == "diapos.md":
            vers_pptx(texte, chapitre / f"Diapos/seance-{numero}-diapos.pptx", None, chemin.parent)
        else:
            vers_docx(texte, chapitre / LIVRABLES[nom].format(n=numero))
