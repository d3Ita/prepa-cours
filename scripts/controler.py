#!/usr/bin/env python3
"""Contrôle la cohérence d'un chapitre : découpage, objectifs, minutage, QCM, diapos, barème, fichiers rangés.

Usage : controler.py [dossier du chapitre]
Code de sortie 1 s'il y a au moins un problème.
"""
import re
import sys
from pathlib import Path

from evaluations import CHOIX_MINIMUM, OBJECTIF, lire_corrige, lire_sujet, verifier
from generer import lire_diapos
from redaction import blocage

FICHIERS_SEANCE = ("scenario.md", "diapos.md", "qcm.md", "qcm-corrige.md")
FICHIERS_OBJECTIFS = ("scenario.md", "diapos.md", "qcm-corrige.md")
LIVRABLES_SEANCE = ("Cours/seance-{n}-scenario.docx", "Diapos/seance-{n}-diapos.pptx",
                    "QCM/seance-{n}-qcm.docx", "Corrections/seance-{n}-qcm-corrige.docx")
LIVRABLES_EVALUATION = ("Evaluations/evaluation.docx", "Corrections/evaluation-corrige.docx")
CATEGORIES = ("Cours", "Diapos", "QCM", "Evaluations", "Corrections")
MAX_PUCES = 6
QUESTIONS_QCM = 5
SEANCE = re.compile(r"^[-*\s]*S[ée]ance\s+(\d+)\s*:\s*(.+?)\s*[—–]\s*(.*)$", re.MULTILINE | re.IGNORECASE)
CHAMPS_OBLIGATOIRES = {"niveau de la classe": r"Niveau", "matière": r"Mati[èe]re"}


class Probleme(str):
    """Un message affiché tel quel, qui garde ce que le score qualité doit savoir de lui."""

    def __new__(cls, texte, categorie="coherence", severite="warning", etape="livrables"):
        probleme = super().__new__(cls, texte)
        probleme.categorie, probleme.severite, probleme.etape = categorie, severite, etape
        return probleme


def etiqueter(messages, **details):
    return [Probleme(m, **details) for m in messages]


def minutes(texte):
    """Convertit « 2 h », « 1h30 », « 1 h 30 min » ou « 90 min » en minutes, sinon None."""
    m = re.fullmatch(r"(?:(\d+)\s*h(?:eures?)?\s*(?:(\d+)\s*(?:min(?:utes?)?)?)?|(\d+)\s*min(?:utes?)?)",
                     texte.strip(), re.IGNORECASE)
    if not m:
        return None
    return int(m.group(3)) if m.group(3) else int(m.group(1)) * 60 + int(m.group(2) or 0)


def lire(chemin):
    return chemin.read_text(encoding="utf-8") if chemin.is_file() else None


def controler_minutage(scenario, duree, seance):
    phases = [(int(a), int(b)) for a, b in
              re.findall(r"^##\s*(\d+)\s*[-–]\s*(\d+)\s*min", scenario, re.MULTILINE)]
    if not phases:
        return [f"{seance} : scenario.md n'a aucune phase minutée (« ## 0-10 min — … »)."]
    problemes, fin = [], 0
    for debut, arrivee in phases:
        if debut != fin or arrivee <= debut:
            problemes.append(f"{seance} : phase {debut}-{arrivee} min incohérente, début attendu à {fin}.")
        fin = arrivee
    if fin != duree:
        problemes.append(f"{seance} : le scénario dure {fin} min pour une séance de {duree} min.")
    return problemes


def controler_qcm(qcm, corrige, seance):
    questions = lire_sujet(qcm, "qcm")
    problemes = []
    if len(questions) != QUESTIONS_QCM:
        problemes.append(f"{seance} : le QCM a {len(questions)} question(s) au lieu de {QUESTIONS_QCM}.")
    if OBJECTIF.search(qcm):
        problemes.append(f"{seance} : le sujet du QCM ne doit pas citer les objectifs.")
    for question in questions:
        if question.type == "qcm" and len(question.choix) < CHOIX_MINIMUM:
            problemes.append(f"{seance} : la question {question.numero} du QCM a moins de {CHOIX_MINIMUM} choix.")
    problemes += [f"{seance} : {p}" for p in verifier(qcm, corrige, "qcm")]
    lettres = [r.lettres[0] for r in lire_corrige(corrige) if r.lettres]
    if len(lettres) == QUESTIONS_QCM and len(set(lettres)) == 1:
        problemes.append(f"{seance} : toutes les bonnes réponses du QCM sont la {lettres[0]}.")
    return problemes


def controler_seance(dossier, numero, duree, attendus, definis):
    nom = f"seance-{numero}"
    if not (dossier / nom).is_dir():
        return [Probleme(f"Le dossier {nom} est absent.", severite="critical", etape="scenarios")]
    problemes = []
    textes = {f: lire(dossier / nom / f) for f in FICHIERS_SEANCE}
    etape = {"scenario.md": "scenarios"}
    for fichier, texte in textes.items():
        if texte is None:
            problemes.append(Probleme(f"{nom} : {fichier} est absent.", severite="critical",
                                      etape=etape.get(fichier, "livrables")))
    for fichier in FICHIERS_OBJECTIFS:
        if textes[fichier] is None:
            continue
        cites = set(OBJECTIF.findall(textes[fichier]))
        problemes += etiqueter([f"{nom} : {o} n'est pas couvert dans {fichier}." for o in sorted(attendus - cites)]
                               + [f"{nom} : {fichier} cite {o}, absent de objectifs.md." for o in sorted(cites - definis)],
                               etape=etape.get(fichier, "livrables"))
    if textes["scenario.md"] is not None:
        problemes += etiqueter(controler_minutage(textes["scenario.md"], duree, nom), categorie="timing", etape="scenarios")
    if textes["qcm.md"] is not None and textes["qcm-corrige.md"] is not None:
        problemes += etiqueter(controler_qcm(textes["qcm.md"], textes["qcm-corrige.md"], nom),
                               categorie="evaluation", severite="critical")
    if textes["diapos.md"] is not None:
        for contenu in lire_diapos(textes["diapos.md"]):
            if len(contenu["puces"]) > MAX_PUCES:
                problemes.append(Probleme(f"{nom} : diapo « {contenu['titre']} » avec {len(contenu['puces'])} puces "
                                          f"(maximum {MAX_PUCES}).", categorie="pedagogical"))
    return problemes


def controler_evaluation(dossier, definis):
    """L'évaluation finale est facultative : elle n'est contrôlée que si elle existe."""
    evaluation = lire(dossier / "evaluation.md")
    if evaluation is None:
        return [], []
    problemes, infos = [], []
    corrige = lire(dossier / "corrige.md")
    if corrige is None:
        problemes.append("evaluation.md existe, mais corrige.md est absent.")
    else:
        for o in sorted(set(OBJECTIF.findall(corrige)) - definis):
            problemes.append(f"corrige.md cite {o}, absent de objectifs.md.")
    points = [float(p.replace(",", ".")) for p in
              re.findall(r"\((\d+(?:[.,]\d+)?)\s*points?\)", evaluation, re.IGNORECASE)]
    total = sum(points)
    annonce = re.search(r"Total\s*:\s*(\d+(?:[.,]\d+)?)\s*points?", evaluation, re.IGNORECASE)
    if not points:
        problemes.append("evaluation.md n'indique aucun barème (« (5 points) »).")
    else:
        infos.append(f"Évaluation finale : {total:g} points.")
    if points and annonce and float(annonce.group(1).replace(",", ".")) != total:
        problemes.append(f"Les questions totalisent {total:g} points, mais le sujet annonce {annonce.group(1)}.")
    return etiqueter(problemes, categorie="evaluation"), infos


def controler_livrables(chapitre, numeros, avec_evaluation):
    attendus = [m.format(n=n) for n in numeros for m in LIVRABLES_SEANCE]
    if avec_evaluation:
        attendus += LIVRABLES_EVALUATION
    problemes = [Probleme(f"Le fichier {f} est absent.", severite="critical",
                          etape="scenarios" if "scenario" in f else "livrables")
                 for f in attendus if not (chapitre / f).is_file()]
    # Après un nouveau découpage, un ancien fichier pourrait être distribué par erreur.
    for categorie in CATEGORIES:
        for chemin in sorted((chapitre / categorie).glob("seance-*")):
            m = re.match(r"seance-(\d+)-", chemin.name)
            if m and int(m.group(1)) not in numeros:
                problemes.append(Probleme(
                    f"Le fichier {categorie}/{chemin.name} ne correspond à aucune séance du découpage."))
    return problemes


def controler(chapitre):
    """Renvoie (problèmes, informations)."""
    dossier = chapitre / ".travail"
    objectifs_md = lire(dossier / "objectifs.md")
    if objectifs_md is None:
        return [Probleme(".travail/objectifs.md est absent : lancez le contrôle depuis le dossier du chapitre.",
                         severite="critical", etape="decoupage")], []
    problemes, infos = [], []
    if blocage(chapitre):
        problemes.append(Probleme(blocage(chapitre), severite="critical", etape="decoupage"))
    for nom, motif in CHAMPS_OBLIGATOIRES.items():
        if not re.search(rf"^[-*\s]*{motif}\s*:\s*\S", objectifs_md, re.MULTILINE | re.IGNORECASE):
            problemes.append(Probleme(f"objectifs.md n'indique pas : {nom}.", etape="decoupage"))
    definis = set(re.findall(r"^[-*\s]*(OBJ\d+)\s*:", objectifs_md, re.MULTILINE))
    if not definis:
        problemes.append(Probleme("objectifs.md ne définit aucun objectif (« - OBJ1 : … »).",
                                  severite="critical", etape="decoupage"))

    seances = SEANCE.findall(objectifs_md)
    if not seances:
        problemes.append(Probleme("objectifs.md ne contient aucune séance (« Séance 1 : 2 h — OBJ1, OBJ2 »).",
                                  severite="critical", etape="decoupage"))
    numeros = [int(s[0]) for s in seances]
    if numeros != list(range(1, len(numeros) + 1)):
        problemes.append(Probleme(f"Les séances doivent être numérotées à partir de 1 et sans trou : {numeros}.",
                                  etape="decoupage"))

    total, couverts = 0, set()
    for numero, duree_texte, objectifs_texte in seances:
        duree = minutes(duree_texte)
        attendus = set(OBJECTIF.findall(objectifs_texte))
        couverts |= attendus
        if duree is None or duree == 0:
            problemes.append(Probleme(f"Séance {numero} : durée illisible « {duree_texte} » (ex. : 2 h, 1 h 30, 55 min).",
                                      categorie="timing", severite="critical", etape="decoupage"))
            continue
        total += duree
        if not attendus:
            problemes.append(Probleme(f"Séance {numero} : aucun objectif attribué.", etape="decoupage"))
        problemes += etiqueter([f"Séance {numero} : {o} n'est pas défini dans objectifs.md."
                                for o in sorted(attendus - definis)], etape="decoupage")
        problemes += controler_seance(dossier, numero, duree, attendus, definis)
    problemes += etiqueter([f"{o} n'est attribué à aucune séance." for o in sorted(definis - couverts)], etape="decoupage")

    annonce = re.search(r"^[-*\s]*Durée totale\s*:\s*(.+)$", objectifs_md, re.MULTILINE | re.IGNORECASE)
    if annonce and minutes(annonce.group(1)) != total:
        problemes.append(Probleme(f"Les séances totalisent {total} min, mais objectifs.md annonce « {annonce.group(1).strip()} ».",
                                  categorie="timing", etape="decoupage"))

    # Après un nouveau découpage, un ancien dossier pourrait être distribué par erreur.
    for extra in sorted(p.name for p in dossier.glob("seance-*") if p.is_dir()):
        if extra not in {f"seance-{n}" for n in numeros}:
            problemes.append(Probleme(f"Le dossier {extra} ne correspond à aucune séance du découpage.", etape="scenarios"))

    autres_problemes, autres_infos = controler_evaluation(dossier, definis)
    problemes += autres_problemes
    problemes += controler_livrables(chapitre, numeros, (dossier / "evaluation.md").is_file())
    infos = [f"{len(seances)} séance(s), {total} min au total.", *autres_infos]
    for chemin in sorted(dossier.rglob("*.md")):
        nombre = chemin.read_text(encoding="utf-8").count("[À VÉRIFIER]")
        if nombre:
            infos.append(f"{chemin.relative_to(dossier).as_posix()} : {nombre} point(s) à vérifier par le prof.")
    return problemes, infos


if __name__ == "__main__":
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    problemes, infos = controler(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    for ligne in infos:
        print(f"Info : {ligne}")
    for ligne in problemes:
        print(f"Problème : {ligne}")
    if not problemes:
        print("Cours cohérent : aucun problème détecté.")
    sys.exit(1 if problemes else 0)
