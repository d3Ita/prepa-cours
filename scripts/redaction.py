#!/usr/bin/env python3
"""Suit la rédaction d'un cours à partir de documents, jusqu'à sa validation par le prof.

Usage : redaction.py demarrer [chapitre] --sources <fichier> [<fichier>…]
        redaction.py produire [chapitre] [--outils dossier]
        redaction.py etat [chapitre]
        redaction.py valider [chapitre] [--malgre-a-verifier]
        redaction.py rouvrir [chapitre]

Tant que le cours n'est pas validé, ou s'il a changé depuis, le contrôle de cohérence bloque la suite.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from extraire_texte import extraire

COURS = Path("Cours") / "cours.docx"
COURS_ODT = Path("Cours") / "cours.odt"
SOURCES = Path("Cours") / "Sources"
BROUILLON = Path(".travail") / "revue" / "cours-brouillon.md"
ETAT = Path(".travail") / "revue" / "redaction.json"
A_VERIFIER = "[À VÉRIFIER]"


def lire_etat(chapitre):
    chemin = Path(chapitre) / ETAT
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else None


def ecrire_etat(chapitre, etat):
    chemin = Path(chapitre) / ETAT
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")


def chemin_cours(chapitre):
    """Le cours peut être un .docx ou un .odt selon le réglage du prof. Renvoie None s'il n'existe pas."""
    for chemin in (Path(chapitre) / COURS, Path(chapitre) / COURS_ODT):
        if chemin.is_file():
            return chemin
    return None


def empreinte(chapitre):
    chemin = chemin_cours(chapitre)
    return hashlib.sha256(chemin.read_bytes()).hexdigest() if chemin else None


def statut(chapitre):
    """Renvoie None sans rédaction suivie, sinon en_cours, validee ou modifie_apres_validation."""
    etat = lire_etat(chapitre)
    if etat is None:
        return None
    if etat["statut"] != "validee":
        return "en_cours"
    return "validee" if etat["empreinte"] == empreinte(chapitre) else "modifie_apres_validation"


def blocage(chapitre):
    """Renvoie le message qui arrête le pipeline, ou None si le cours peut passer à la suite."""
    return {"en_cours": "Le cours est encore en rédaction : le prof ne l'a pas validé.",
            "modifie_apres_validation": "Le cours a changé depuis sa validation : le prof doit le revalider."}.get(statut(chapitre))


def sauvegarder(chapitre, message):
    versions = Path(__file__).resolve().parent / "versions.py"
    r = subprocess.run([sys.executable, str(versions), "sauver", message], cwd=chapitre,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(f"Sauvegarde impossible : {r.stderr.strip()}")


def demarrer(chapitre, sources):
    """Copie les documents sans jamais toucher aux originaux ni écraser une source déjà présente."""
    dossier = Path(chapitre) / SOURCES
    fichiers = [Path(s) for s in sources]
    for f in fichiers:
        if not f.is_file():
            sys.exit(f"Fichier introuvable : {f}. Rien n'a été copié.")
        if (dossier / f.name).exists():
            sys.exit(f"{dossier / f.name} existe déjà : renommez l'un des deux fichiers. Rien n'a été copié.")
    if len({f.name for f in fichiers}) != len(fichiers):
        sys.exit("Deux documents portent le même nom : renommez-en un. Rien n'a été copié.")
    dossier.mkdir(parents=True, exist_ok=True)
    for f in fichiers:
        shutil.copy2(f, dossier / f.name)
    etat = lire_etat(chapitre) or {"statut": "en_cours", "debut": time.strftime("%Y-%m-%dT%H:%M:%S"), "validations": []}
    etat["statut"] = "en_cours"
    ecrire_etat(chapitre, etat)
    print(f"{len(fichiers)} document(s) copié(s) dans {SOURCES.as_posix()}.")


def produire(chapitre, outils, format_sortie=None):
    """Crée le document du cours depuis le brouillon de l'agent, puis retire ce brouillon :
    le document devient l'unique référence, que le prof peut retoucher librement."""
    brouillon = Path(chapitre) / BROUILLON
    cours = Path(chapitre) / COURS
    if not brouillon.is_file():
        sys.exit(f"Aucun brouillon : {BROUILLON.as_posix()} est absent.")
    existant = chemin_cours(chapitre)
    if existant:
        sys.exit(f"{existant.relative_to(chapitre).as_posix()} existe déjà : modifiez-le sans le recréer, pour garder les retouches du prof.")
    generer = Path(__file__).resolve().parent / "generer.py"
    commande = [sys.executable, str(generer), "docx", str(brouillon), str(cours)]
    if outils:
        commande += ["--outils", outils]
    # Le cours se révise longuement : il reste toujours modifiable, et un PDF n'en serait qu'une copie à part.
    if format_sortie and format_sortie.strip().lstrip(".").casefold() == "odt":
        commande += ["--sortie-format", "odt"]
    r = subprocess.run(commande, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(f"Création impossible : {r.stderr.strip()}")
    if "⚠" in r.stdout:
        print(r.stdout.strip())
    brouillon.unlink()
    etat = lire_etat(chapitre) or {"statut": "en_cours", "debut": time.strftime("%Y-%m-%dT%H:%M:%S"), "validations": []}
    etat["statut"] = "en_cours"
    ecrire_etat(chapitre, etat)
    sauvegarder(chapitre, "Première version du cours")
    print(f"Créé : {chemin_cours(chapitre).relative_to(chapitre).as_posix()}")


def lire_sources(chapitre):
    """Renvoie (texte des sources lisibles, noms des documents impossibles à comparer)."""
    textes, non_lus = [], []
    for chemin in sorted((Path(chapitre) / SOURCES).glob("*")):
        if not chemin.is_file():
            continue
        textes.append(chemin.stem)
        try:
            textes += extraire(chemin)
        except (OSError, SystemExit, KeyError, ValueError):
            non_lus.append(chemin.name)
    return "\n".join(textes).casefold(), non_lus


def analyser(chapitre):
    from qualite import termes_suspects

    lignes = extraire(chemin_cours(chapitre))
    source, non_lus = lire_sources(chapitre)
    a_verifier = [l for l in lignes if A_VERIFIER in l]
    suspects = {}
    # Une source illisible, comme un PDF, peut contenir ces termes : ne rien affirmer dans ce cas.
    if not non_lus:
        for ligne in lignes:
            if A_VERIFIER not in ligne:
                for terme in termes_suspects(ligne, source):
                    suspects.setdefault(terme, ligne)
    return {"mots": sum(len(l.split()) for l in lignes), "a_verifier": a_verifier, "suspects": suspects, "non_lus": non_lus}


def etat(chapitre):
    etat_actuel = statut(chapitre)
    if etat_actuel is None:
        print("STATUS: AUCUNE_REDACTION")
        return
    if empreinte(chapitre) is None:
        print("STATUS: EN_ATTENTE_DU_PREMIER_DOCUMENT")
        return
    a = analyser(chapitre)
    print(f"Cours : {chemin_cours(chapitre).relative_to(chapitre).as_posix()} ({a['mots']} mots)")
    if a["a_verifier"]:
        print(f"\n{len(a['a_verifier'])} point(s) à vérifier :")
        for ligne in a["a_verifier"]:
            print(f"  {ligne}")
    if a["suspects"]:
        print("\nAbsents des documents fournis (pistes à vérifier, pas des preuves) :")
        for terme, ligne in a["suspects"].items():
            print(f"  « {terme} » : {ligne}")
    if a["non_lus"]:
        print(f"\nDocuments non comparés automatiquement : {', '.join(a['non_lus'])}")
    print(f"\nSTATUS: {etat_actuel.upper()}")
    if etat_actuel != "validee":
        print("\n[1] Continuer à modifier\n[2] Valider et passer à la suite")


def valider(chapitre, malgre_a_verifier):
    """À lancer seulement après la réponse explicite du prof."""
    if empreinte(chapitre) is None:
        sys.exit(f"{COURS.as_posix()} est absent, comme {COURS_ODT.as_posix()} : rien à valider.")
    etat_actuel = lire_etat(chapitre)
    if etat_actuel is None:
        sys.exit("Aucune rédaction suivie dans ce chapitre.")
    restants = analyser(chapitre)["a_verifier"]
    if restants and not malgre_a_verifier:
        sys.exit(f"{len(restants)} point(s) [À VÉRIFIER] restent dans le cours. Montrez-les au prof : "
                 "seul son accord explicite permet de valider malgré tout.")
    sauvegarder(chapitre, "Avant validation du cours")
    trace = empreinte(chapitre)
    etat_actuel.update(statut="validee", empreinte=trace)
    etat_actuel["validations"].append({"date": time.strftime("%Y-%m-%dT%H:%M:%S"), "empreinte": trace,
                                       "a_verifier_restants": len(restants)})
    ecrire_etat(chapitre, etat_actuel)
    sauvegarder(chapitre, "Cours validé par le prof")
    print("Cours validé : la suite du pipeline peut commencer.")


def rouvrir(chapitre):
    etat_actuel = lire_etat(chapitre)
    if etat_actuel is None:
        sys.exit("Aucune rédaction suivie dans ce chapitre.")
    etat_actuel["statut"] = "en_cours"
    etat_actuel.pop("empreinte", None)
    ecrire_etat(chapitre, etat_actuel)
    print("Le cours est de nouveau en révision.")


def main():
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    sous = p.add_subparsers(dest="commande", required=True)
    for nom in ("demarrer", "produire", "etat", "valider", "rouvrir"):
        c = sous.add_parser(nom)
        c.add_argument("chapitre", nargs="?", default=".")
        if nom == "demarrer":
            c.add_argument("--sources", nargs="+", required=True)
        if nom == "produire":
            c.add_argument("--outils")
            c.add_argument("--sortie-format")
        if nom == "valider":
            c.add_argument("--malgre-a-verifier", action="store_true")
    a = p.parse_args()
    if not Path(a.chapitre).is_dir():
        sys.exit(f"Chapitre introuvable : {a.chapitre}")
    if a.commande == "demarrer":
        demarrer(a.chapitre, a.sources)
    elif a.commande == "produire":
        produire(a.chapitre, a.outils, a.sortie_format)
    elif a.commande == "etat":
        etat(a.chapitre)
    elif a.commande == "valider":
        valider(a.chapitre, a.malgre_a_verifier)
    else:
        rouvrir(a.chapitre)


if __name__ == "__main__":
    main()
