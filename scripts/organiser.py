#!/usr/bin/env python3
"""Organise le dossier de cours : niveau, classe, chapitre, puis Cours, Diapos, QCM, Evaluations, Corrections.

Usage : organiser.py creer <dossier de cours> <niveau> <classe> <chapitre>
        organiser.py arbre <dossier de cours>
        organiser.py ranger <fichier> <dossier du chapitre> <catégorie> [--deplacer]
        organiser.py dupliquer <dossier du chapitre> <dossier de l'autre classe>
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

CATEGORIES = ("Cours", "Diapos", "QCM", "Evaluations", "Corrections")
MARQUEUR = ".prof-cours"
INTERDITS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
CHAPITRE = re.compile(r"Chapitre (\d+) - (.+)", re.IGNORECASE)


def nom_sur(texte, quoi):
    """Empêche de sortir du dossier de cours et retire les caractères refusés sous Windows."""
    nom = re.sub(r"\s+", " ", INTERDITS.sub(" ", texte)).strip().rstrip(".")
    if not nom or nom.startswith("."):
        sys.exit(f"Nom invalide pour {quoi} : « {texte} ».")
    return nom


def dossier_chapitre(classe, titre):
    """Numérote un nouveau chapitre, et retrouve celui qui porte déjà ce titre."""
    titre = nom_sur(titre, "le chapitre")
    if re.match(r"chapitre\s+\d+", titre, re.IGNORECASE):
        return classe / titre
    existants = [CHAPITRE.fullmatch(p.name) for p in classe.iterdir() if p.is_dir()] if classe.is_dir() else []
    existants = [m for m in existants if m]
    for m in existants:
        if m.group(2).casefold() == titre.casefold():
            return classe / m.group(0)
    suivant = max((int(m.group(1)) for m in existants), default=0) + 1
    return classe / f"Chapitre {suivant:02d} - {titre}"


def creer(racine, niveau, classe, chapitre):
    racine = Path(racine).expanduser().resolve()
    # Le dossier de cours reçoit tout l'historique : il ne doit pas englober un disque ou un dossier personnel.
    if racine in (Path.home().resolve(), Path(racine.anchor)):
        sys.exit("Choisissez un dossier dédié aux cours, pas votre dossier personnel ou tout un disque.")
    dossier_classe = racine / nom_sur(niveau, "le niveau") / nom_sur(classe, "la classe")
    dossier = dossier_chapitre(dossier_classe, chapitre)
    for categorie in CATEGORIES:
        (dossier / categorie).mkdir(parents=True, exist_ok=True)
    travail = dossier / ".travail"
    travail.mkdir(exist_ok=True)
    # Le point ne masque le dossier que sur macOS et Linux.
    if sys.platform == "win32":
        subprocess.run(["attrib", "+h", str(travail)], capture_output=True)
    (racine / MARQUEUR).touch()
    print(dossier)


def visibles(dossier):
    return sorted(p for p in dossier.iterdir() if p.is_dir() and not p.name.startswith("."))


def arbre(racine):
    racine = Path(racine).expanduser()
    if not racine.is_dir():
        sys.exit(f"Dossier introuvable : {racine}")
    trouve = False
    for niveau in visibles(racine):
        print(niveau.name)
        for classe in visibles(niveau):
            print(f"  {classe.name}")
            for chapitre in visibles(classe):
                trouve = True
                contenu = []
                for categorie in CATEGORIES:
                    dossier = chapitre / categorie
                    nombre = sum(1 for p in dossier.iterdir() if p.is_file() and not p.name.startswith(".")) \
                        if dossier.is_dir() else 0
                    contenu.append(f"{categorie} : {nombre}")
                print(f"    {chapitre.name} ({', '.join(contenu)})")
    if not trouve:
        print("Aucun chapitre pour l'instant.")


def ranger(fichier, chapitre, categorie, deplacer):
    source = Path(fichier)
    if not source.is_file():
        sys.exit(f"Fichier introuvable : {fichier}")
    nom = next((c for c in CATEGORIES if c.casefold() == categorie.casefold()), None)
    if nom is None:
        sys.exit(f"Catégorie inconnue : {categorie}. Choisissez parmi : {', '.join(CATEGORIES)}.")
    if not Path(chapitre).is_dir():
        sys.exit(f"Chapitre introuvable : {chapitre}")
    cible = Path(chapitre) / nom / source.name
    # Deux fichiers peuvent porter le même nom : ne jamais perdre celui qui est déjà rangé.
    if cible.exists():
        sys.exit(f"{cible} existe déjà : renommez l'un des deux fichiers.")
    cible.parent.mkdir(exist_ok=True)
    (shutil.move if deplacer else shutil.copy2)(str(source), str(cible))
    print(f"{'Déplacé' if deplacer else 'Copié'} : {cible}")


def dupliquer(chapitre, classe):
    source = Path(chapitre)
    if not source.is_dir():
        sys.exit(f"Chapitre introuvable : {chapitre}")
    cible = Path(classe) / source.name
    if cible.exists():
        sys.exit(f"{cible} existe déjà : rien n'a été copié.")
    shutil.copytree(source, cible)
    print(cible)


def main():
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    sous = p.add_subparsers(dest="commande", required=True)
    c = sous.add_parser("creer")
    for champ in ("racine", "niveau", "classe", "chapitre"):
        c.add_argument(champ)
    sous.add_parser("arbre").add_argument("racine")
    r = sous.add_parser("ranger")
    for champ in ("fichier", "chapitre", "categorie"):
        r.add_argument(champ)
    r.add_argument("--deplacer", action="store_true")
    d = sous.add_parser("dupliquer")
    d.add_argument("chapitre")
    d.add_argument("classe")
    a = p.parse_args()
    if a.commande == "creer":
        creer(a.racine, a.niveau, a.classe, a.chapitre)
    elif a.commande == "arbre":
        arbre(a.racine)
    elif a.commande == "dupliquer":
        dupliquer(a.chapitre, a.classe)
    else:
        ranger(a.fichier, a.chapitre, a.categorie, a.deplacer)


if __name__ == "__main__":
    main()
