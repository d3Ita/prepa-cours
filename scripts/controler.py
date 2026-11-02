#!/usr/bin/env python3
"""Contrôle la cohérence d'un dossier de cours : découpage, objectifs, minutage, QCM, diapos, barème.

Usage : controler.py [dossier]
Code de sortie 1 s'il y a au moins un problème.
"""
import re
import sys
from pathlib import Path

from generer import lire_diapos

FICHIERS_SEANCE = ("scenario.md", "diapos.md", "qcm.md", "qcm-corrige.md")
FICHIERS_OBJECTIFS = ("scenario.md", "diapos.md", "qcm-corrige.md")
MAX_PUCES = 6
QUESTIONS_QCM = 5
CHOIX_MINIMUM = 3
SEANCE = re.compile(r"^[-*\s]*S[ée]ance\s+(\d+)\s*:\s*(.+?)\s*[—–]\s*(.*)$", re.MULTILINE | re.IGNORECASE)
OBJECTIF = re.compile(r"\bO\d+\b")


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
    blocs = re.split(r"^##\s*Question\s+\d+.*$", qcm, flags=re.MULTILINE | re.IGNORECASE)[1:]
    problemes = []
    if len(blocs) != QUESTIONS_QCM:
        problemes.append(f"{seance} : le QCM a {len(blocs)} question(s) au lieu de {QUESTIONS_QCM}.")
    if OBJECTIF.search(qcm):
        problemes.append(f"{seance} : le sujet du QCM ne doit pas citer les objectifs.")
    choix = [re.findall(r"^([A-Z])[.)]\s+\S", bloc, re.MULTILINE) for bloc in blocs]
    for i, lettres in enumerate(choix, 1):
        if len(lettres) < CHOIX_MINIMUM:
            problemes.append(f"{seance} : la question {i} du QCM a moins de {CHOIX_MINIMUM} choix.")
    reponses = dict(re.findall(r"^[-*\s]*Question\s+(\d+)\s*:\s*\**([A-Z])\b", corrige,
                               re.MULTILINE | re.IGNORECASE))
    for i, lettres in enumerate(choix, 1):
        reponse = reponses.get(str(i))
        if reponse is None:
            problemes.append(f"{seance} : le corrigé ne donne pas la réponse à la question {i}.")
        elif reponse not in lettres:
            problemes.append(f"{seance} : la réponse {reponse} de la question {i} n'existe pas dans le QCM.")
    if len(reponses) == QUESTIONS_QCM and len(set(reponses.values())) == 1:
        problemes.append(f"{seance} : toutes les bonnes réponses du QCM sont la {next(iter(reponses.values()))}.")
    return problemes


def controler_seance(dossier, numero, duree, attendus, definis):
    nom = f"seance-{numero}"
    if not (dossier / nom).is_dir():
        return [f"Le dossier {nom} est absent."]
    problemes = []
    textes = {f: lire(dossier / nom / f) for f in FICHIERS_SEANCE}
    for fichier, texte in textes.items():
        if texte is None:
            problemes.append(f"{nom} : {fichier} est absent.")
    for fichier in FICHIERS_OBJECTIFS:
        if textes[fichier] is None:
            continue
        cites = set(OBJECTIF.findall(textes[fichier]))
        problemes += [f"{nom} : {o} n'est pas couvert dans {fichier}." for o in sorted(attendus - cites)]
        problemes += [f"{nom} : {fichier} cite {o}, absent de objectifs.md." for o in sorted(cites - definis)]
    if textes["scenario.md"] is not None:
        problemes += controler_minutage(textes["scenario.md"], duree, nom)
    if textes["qcm.md"] is not None and textes["qcm-corrige.md"] is not None:
        problemes += controler_qcm(textes["qcm.md"], textes["qcm-corrige.md"], nom)
    if textes["diapos.md"] is not None:
        for contenu in lire_diapos(textes["diapos.md"]):
            if len(contenu["puces"]) > MAX_PUCES:
                problemes.append(f"{nom} : diapo « {contenu['titre']} » avec {len(contenu['puces'])} puces "
                                 f"(maximum {MAX_PUCES}).")
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
    return problemes, infos


def controler(dossier):
    """Renvoie (problèmes, informations)."""
    objectifs_md = lire(dossier / "objectifs.md")
    if objectifs_md is None:
        return ["objectifs.md est absent."], []
    problemes, infos = [], []
    definis = set(re.findall(r"^[-*\s]*(O\d+)\s*:", objectifs_md, re.MULTILINE))
    if not definis:
        problemes.append("objectifs.md ne définit aucun objectif (« - O1 : … »).")

    seances = SEANCE.findall(objectifs_md)
    if not seances:
        problemes.append("objectifs.md ne contient aucune séance (« Séance 1 : 2 h — O1, O2 »).")
    numeros = [int(s[0]) for s in seances]
    if numeros != list(range(1, len(numeros) + 1)):
        problemes.append(f"Les séances doivent être numérotées à partir de 1 et sans trou : {numeros}.")

    total, couverts = 0, set()
    for numero, duree_texte, objectifs_texte in seances:
        duree = minutes(duree_texte)
        attendus = set(OBJECTIF.findall(objectifs_texte))
        couverts |= attendus
        if duree is None or duree == 0:
            problemes.append(f"Séance {numero} : durée illisible « {duree_texte} » (ex. : 2 h, 1 h 30, 55 min).")
            continue
        total += duree
        if not attendus:
            problemes.append(f"Séance {numero} : aucun objectif attribué.")
        problemes += [f"Séance {numero} : {o} n'est pas défini dans objectifs.md." for o in sorted(attendus - definis)]
        problemes += controler_seance(dossier, numero, duree, attendus, definis)
    problemes += [f"{o} n'est attribué à aucune séance." for o in sorted(definis - couverts)]

    annonce = re.search(r"^[-*\s]*Durée totale\s*:\s*(.+)$", objectifs_md, re.MULTILINE | re.IGNORECASE)
    if annonce and minutes(annonce.group(1)) != total:
        problemes.append(f"Les séances totalisent {total} min, mais objectifs.md annonce « {annonce.group(1).strip()} ».")

    # Après un nouveau découpage, un ancien dossier pourrait être distribué par erreur.
    for extra in sorted(p.name for p in dossier.glob("seance-*") if p.is_dir()):
        if extra not in {f"seance-{n}" for n in numeros}:
            problemes.append(f"Le dossier {extra} ne correspond à aucune séance du découpage.")

    autres_problemes, autres_infos = controler_evaluation(dossier, definis)
    problemes += autres_problemes
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
