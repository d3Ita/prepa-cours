#!/usr/bin/env python3
"""Historique Git d'un dossier de cours, à lancer depuis ce dossier.

Usage : versions.py sauver "message" | historique
        versions.py comparer <version> <fichier> | restaurer <version> <fichier>
"""
import difflib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from extraire_texte import extraire

IGNORES = "~$*\n.~lock.*#\n.DS_Store\nThumbs.db\n"
BUREAUTIQUE = (".pptx", ".docx", ".odp", ".odt")


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        sys.exit(f"Erreur : {r.stderr.strip()}")
    return r.stdout.strip()


def preparer():
    if not shutil.which("git"):
        sys.exit("Git n'est pas installé sur cet ordinateur : les sauvegardes sont impossibles.")
    dossier = Path.cwd().resolve()
    # Évite de versionner tout un disque ou tout un dossier personnel par erreur.
    if dossier in (Path.home().resolve(), Path(dossier.anchor)):
        sys.exit("Placez-vous dans le dossier du cours avant de sauvegarder.")
    racine = git("rev-parse", "--show-toplevel", check=False)
    if not racine:
        git("init")
    elif Path(racine).resolve() != dossier:
        sys.exit(f"Ce dossier fait déjà partie d'un autre historique : {racine}")
    ignores = Path(".gitignore")
    if not ignores.exists():
        ignores.write_text(IGNORES, encoding="utf-8")


def sauver(message):
    preparer()
    git("add", "-A")
    if not git("status", "--porcelain"):
        print("Rien de nouveau à sauvegarder.")
        return
    identite = []
    if not git("config", "user.name", check=False):
        identite += ["-c", "user.name=Prof Cours"]
    if not git("config", "user.email", check=False):
        identite += ["-c", "user.email=prof-cours@localhost"]
    git(*identite, "commit", "-m", message)
    print(f"Sauvegardé : {message}")


def historique():
    preparer()
    print(git("log", "--date=format:%d/%m/%Y %H:%M", "--format=%h  %ad  %s", check=False)
          or "Aucune sauvegarde pour l'instant.")


def verifier_version(version, fichier):
    if not re.fullmatch(r"[0-9a-f]{4,40}", version):
        sys.exit(f"Version invalide : {version}")
    if subprocess.run(["git", "cat-file", "-e", f"{version}:./{fichier}"],
                      capture_output=True).returncode:
        sys.exit(f"{fichier} n'existe pas dans la version {version}.")


def lignes(chemin):
    if chemin.suffix.lower() in BUREAUTIQUE:
        return extraire(chemin)
    return chemin.read_text(encoding="utf-8", errors="replace").splitlines()


def comparer(version, fichier):
    preparer()
    verifier_version(version, fichier)
    actuel = Path(fichier)
    if not actuel.is_file():
        sys.exit(f"{fichier} n'existe plus dans le dossier.")
    ancien = subprocess.run(["git", "show", f"{version}:./{fichier}"], capture_output=True).stdout
    with tempfile.TemporaryDirectory() as tmp:
        copie = Path(tmp) / f"ancien{actuel.suffix}"
        copie.write_bytes(ancien)
        avant = lignes(copie)
    apres = lignes(actuel)
    # Le texte seul est comparé : un changement d'image ou de mise en forme n'apparaît pas.
    changements = [l for l in difflib.ndiff(avant, apres) if l[0] in "+-"]
    if not changements:
        print("Aucune différence de texte.")
    for l in changements:
        print(("Ajouté : " if l[0] == "+" else "Retiré : ") + l[2:])


def restaurer(version, fichier):
    preparer()
    verifier_version(version, fichier)
    sauver(f"Avant le retour de {fichier} à la version {version}")
    git("checkout", version, "--", fichier)
    sauver(f"Retour de {fichier} à la version {version}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "sauver":
        sauver(args[1])
    elif args == ["historique"]:
        historique()
    elif len(args) == 3 and args[0] == "comparer":
        comparer(args[1], args[2])
    elif len(args) == 3 and args[0] == "restaurer":
        restaurer(args[1], args[2])
    else:
        sys.exit(__doc__)
