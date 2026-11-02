#!/usr/bin/env python3
"""Modifie un endroit précis d'un chapitre et toutes ses références, seulement après validation.

Usage : modifier.py rechercher "<terme>" [dossier]
        modifier.py apercu [chapitre]
        modifier.py appliquer [chapitre] --jeton <jeton donné par l'aperçu>

Le plan vient de .travail/revue/modification.json. Les documents sont modifiés sur place, sans être
régénérés : les retouches du prof, les images et la mise en forme restent intactes.
"""
import argparse
import hashlib
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from controler import controler

SUFFIXES_TEXTE = (".md", ".txt")
SUFFIXES_OOXML = (".docx", ".pptx")
SUFFIXES_ODF = (".odt", ".odp")
SUFFIXES = SUFFIXES_TEXTE + SUFFIXES_OOXML + SUFFIXES_ODF
# Ces formats peuvent contenir une référence, mais le script ne sait ni les lire ni les modifier.
SUFFIXES_NON_LUS = (".pdf", ".doc", ".ppt", ".rtf", ".xlsx", ".ods")
# Sources : les documents d'origine fournis par le prof ne doivent jamais être modifiés.
DOSSIERS_IGNORES = {".git", "revue", "Sources"}
PARTIES_OOXML = re.compile(r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml"
                           r"|ppt/(slides/slide|notesSlides/notesSlide)\d+\.xml")
PARAGRAPHE = re.compile(r"<(w|a):p(?:\s[^>]*)?>.*?</\1:p>", re.DOTALL)
RUN = re.compile(r"<(w|a):t(\s[^>]*)?>(.*?)</\1:t>", re.DOTALL)
PARAGRAPHE_ODF = re.compile(r"<text:(p|h)(?:\s[^>]*)?>.*?</text:\1>", re.DOTALL)
PLAN = Path(".travail") / "revue" / "modification.json"
JOURNAL = Path(".travail") / "revue" / "modifications.json"


def decoder(donnees):
    try:
        return donnees.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        # Les fichiers texte enregistrés sous Windows sont souvent dans cet encodage.
        return donnees.decode("cp1252", errors="replace"), "cp1252"


def lieu_partie(partie):
    m = re.search(r"(slide|notesSlide)(\d+)\.xml$", partie)
    if m:
        return f"{'diapo' if m.group(1) == 'slide' else 'notes de la diapo'} {m.group(2)}"
    return None


def parties_ooxml(archive):
    noms = [n for n in archive.namelist() if PARTIES_OOXML.fullmatch(n)]
    return sorted(noms, key=lambda n: (re.sub(r"\d+\.xml$", "", n), int((re.search(r"(\d+)\.xml$", n) or [0, 0])[1])))


def paragraphes(donnees, suffixe):
    """Renvoie (lieu, texte) pour chaque ligne ou paragraphe d'un document."""
    if suffixe in SUFFIXES_TEXTE:
        return [(f"ligne {i}", l) for i, l in enumerate(decoder(donnees)[0].splitlines(), 1) if l.strip()]
    resultat = []
    with zipfile.ZipFile(io.BytesIO(donnees)) as archive:
        if suffixe in SUFFIXES_ODF:
            xml = archive.read("content.xml").decode("utf-8")
            textes = [html.unescape(re.sub(r"<[^>]+>", "", m.group(0))) for m in PARAGRAPHE_ODF.finditer(xml)]
            return [(f"paragraphe {i}", t) for i, t in enumerate(textes, 1) if t.strip()]
        for partie in parties_ooxml(archive):
            xml = archive.read(partie).decode("utf-8")
            textes = ["".join(html.unescape(r.group(3)) for r in RUN.finditer(m.group(0)))
                      for m in PARAGRAPHE.finditer(xml)]
            base = lieu_partie(partie)
            resultat += [(base or f"paragraphe {i}", t) for i, t in enumerate(textes, 1) if t.strip()]
    return resultat


def remplacer_dans_paragraphe(xml, avant, apres):
    """Remplace le texte même s'il est coupé entre plusieurs morceaux : le gras des autres morceaux reste."""
    runs = list(RUN.finditer(xml))
    textes = [html.unescape(r.group(3)) for r in runs]
    curseur = 0
    faits = 0
    while (debut := "".join(textes).find(avant, curseur)) >= 0:
        fin, position, ecrit = debut + len(avant), 0, False
        for i, texte in enumerate(textes):
            a, b = position, position + len(texte)
            position = b
            if b <= debut or a >= fin:
                continue
            textes[i] = texte[:max(0, debut - a)] + (apres if not ecrit else "") + texte[max(0, fin - a):]
            ecrit = True
        # On reprend après le nouveau texte, pour ne pas le retraiter.
        curseur = debut + len(apres)
        faits += 1
    return reecrire_runs(xml, runs, textes) if faits else xml


def reecrire_runs(xml, runs, textes):
    morceaux, position = [], 0
    for run, texte in zip(runs, textes):
        morceaux.append(xml[position:run.start()])
        attributs = run.group(2) or ""
        if texte != texte.strip() and "xml:space" not in attributs:
            attributs += ' xml:space="preserve"'
        lettre = run.group(1)
        morceaux.append(f"<{lettre}:t{attributs}>{html.escape(texte, quote=False)}</{lettre}:t>")
        position = run.end()
    morceaux.append(xml[position:])
    return "".join(morceaux)


def remplacer(donnees, suffixe, avant, apres, toutes=False):
    """Renvoie (nouveau contenu, nombre de remplacements). Le fichier d'origine n'est pas touché."""
    if suffixe in SUFFIXES_TEXTE:
        texte, encodage = decoder(donnees)
        nombre = texte.count(avant)
        if nombre != 1 and not toutes:
            return donnees, nombre
        bom = donnees.startswith(b"\xef\xbb\xbf")
        return (b"\xef\xbb\xbf" if bom else b"") + texte.replace(avant, apres).encode(encodage), nombre

    nombre = sum(t.count(avant) for _, t in paragraphes(donnees, suffixe))
    if nombre == 0 or (nombre != 1 and not toutes):
        return donnees, nombre
    sortie = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(donnees)) as source, zipfile.ZipFile(sortie, "w") as cible:
        for info in source.infolist():
            contenu = source.read(info.filename)
            if suffixe in SUFFIXES_ODF and info.filename == "content.xml":
                xml = contenu.decode("utf-8")
                ancien = html.escape(avant, quote=False)
                # Coupé par une mise en forme, le texte ne peut pas être remplacé sans risque dans ce format.
                if xml.count(ancien) != nombre:
                    return donnees, -1
                contenu = xml.replace(ancien, html.escape(apres, quote=False)).encode("utf-8")
            elif suffixe in SUFFIXES_OOXML and PARTIES_OOXML.fullmatch(info.filename):
                xml = contenu.decode("utf-8")
                contenu = PARAGRAPHE.sub(lambda m: remplacer_dans_paragraphe(m.group(0), avant, apres), xml).encode("utf-8")
            cible.writestr(info, contenu)
    return sortie.getvalue(), nombre


def inserer(donnees, suffixe, avant, apres):
    """Ajoute un paragraphe après celui qui contient « avant », avec sa mise en forme.

    Renvoie (nouveau contenu, nombre de paragraphes trouvés), ou -2 si le format ne le permet pas.
    """
    if suffixe in SUFFIXES_ODF:
        return donnees, -2
    if suffixe in SUFFIXES_TEXTE:
        texte, encodage = decoder(donnees)
        lignes = texte.splitlines(keepends=True)
        indices = [i for i, l in enumerate(lignes) if avant in l]
        if len(indices) != 1:
            return donnees, len(indices)
        fin = "\r\n" if lignes[indices[0]].endswith("\r\n") else "\n"
        lignes[indices[0]] = lignes[indices[0]].rstrip("\r\n") + fin
        lignes.insert(indices[0] + 1, apres + fin)
        bom = donnees.startswith(b"\xef\xbb\xbf")
        return (b"\xef\xbb\xbf" if bom else b"") + "".join(lignes).encode(encodage), 1

    nombre = sum(t.count(avant) for _, t in paragraphes(donnees, suffixe))
    if nombre != 1:
        return donnees, nombre

    def ajouter_apres(m):
        runs = list(RUN.finditer(m.group(0)))
        if avant not in "".join(html.unescape(r.group(3)) for r in runs):
            return m.group(0)
        return m.group(0) + reecrire_runs(m.group(0), runs, [apres] + [""] * (len(runs) - 1))

    sortie = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(donnees)) as source, zipfile.ZipFile(sortie, "w") as cible:
        for info in source.infolist():
            contenu = source.read(info.filename)
            if PARTIES_OOXML.fullmatch(info.filename):
                contenu = PARAGRAPHE.sub(ajouter_apres, contenu.decode("utf-8")).encode("utf-8")
            cible.writestr(info, contenu)
    return sortie.getvalue(), 1


def fichiers_du_dossier(dossier):
    """Renvoie (fichiers lisibles, fichiers impossibles à vérifier), hors historique et fichiers de verrou."""
    lisibles, non_lus = [], []
    for chemin in sorted(Path(dossier).rglob("*")):
        relatif = chemin.relative_to(dossier)
        if not chemin.is_file() or DOSSIERS_IGNORES & set(relatif.parts) or chemin.name.startswith(("~$", ".~lock")):
            continue
        suffixe = chemin.suffix.lower()
        if suffixe in SUFFIXES:
            lisibles.append(chemin)
        elif suffixe in SUFFIXES_NON_LUS:
            non_lus.append(relatif.as_posix())
    return lisibles, non_lus


def motif_reference(terme):
    return re.compile(rf"(?<!\w){re.escape(terme)}(?!\w)", re.IGNORECASE)


def rechercher(terme, dossier):
    """Renvoie (occurrences, fichiers illisibles, fichiers non lus)."""
    motif = motif_reference(terme)
    occurrences, illisibles = [], []
    lisibles, non_lus = fichiers_du_dossier(dossier)
    for chemin in lisibles:
        try:
            morceaux = paragraphes(chemin.read_bytes(), chemin.suffix.lower())
        except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError):
            illisibles.append(chemin.relative_to(dossier).as_posix())
            continue
        occurrences += [(chemin.relative_to(dossier).as_posix(), lieu, texte.strip())
                        for lieu, texte in morceaux if motif.search(texte)]
    return occurrences, illisibles + non_lus


def chemin_du_plan(chapitre, fichier):
    """Le plan vient d'un agent : il ne doit pouvoir toucher que les documents de ce chapitre."""
    if not isinstance(fichier, str) or not fichier or Path(fichier).is_absolute():
        sys.exit(f"Chemin refusé dans le plan : {fichier}")
    racine = Path(chapitre).resolve()
    chemin = (racine / fichier).resolve()
    if not chemin.is_relative_to(racine) or DOSSIERS_IGNORES & set(chemin.relative_to(racine).parts):
        sys.exit(f"Chemin refusé dans le plan : {fichier}")
    if chemin.suffix.lower() not in SUFFIXES:
        sys.exit(f"Format non modifiable : {fichier}. Le prof doit le modifier lui-même.")
    if not chemin.is_file():
        sys.exit(f"Fichier introuvable : {fichier}")
    if (chemin.parent / f"~${chemin.name}").exists() or (chemin.parent / f".~lock.{chemin.name}#").exists():
        sys.exit(f"{fichier} est ouvert dans un logiciel : fermez-le, puis relancez.")
    return chemin


def lire_plan(chapitre):
    chemin = Path(chapitre) / PLAN
    if not chemin.is_file():
        sys.exit(f"Aucun plan de modification : {PLAN.as_posix()} est absent.")
    try:
        plan = json.loads(chemin.read_text(encoding="utf-8"))
        modifications, references = plan["modifications"], plan["references"]
        demande = plan["demande"]
    except (OSError, ValueError, KeyError, TypeError):
        sys.exit("Le plan de modification est illisible ou incomplet.")
    if not isinstance(demande, str) or not demande.strip():
        sys.exit("Le plan doit indiquer la demande du prof.")
    if not isinstance(references, list) or not references or not all(isinstance(r, str) and r.strip() for r in references):
        sys.exit("Le plan doit indiquer au moins une référence à rechercher.")
    if not isinstance(modifications, list) or not modifications:
        sys.exit("Le plan ne contient aucune modification.")
    for m in modifications:
        if (not isinstance(m, dict) or m.get("role") not in ("cible", "reference") or not isinstance(m.get("avant"), str)
                or not m["avant"] or not isinstance(m.get("apres"), str) or "\n" in m["avant"] + m["apres"]):
            sys.exit(f"Modification invalide dans le plan : {m}. Le texte tient sur une seule ligne.")
        if m.get("action", "remplacer") not in ("remplacer", "inserer") or (m.get("action") == "inserer" and not m["apres"].strip()):
            sys.exit(f"Action invalide dans le plan : {m}.")
    if not any(m["role"] == "cible" for m in modifications):
        sys.exit("Le plan doit désigner l'endroit demandé avec le rôle « cible ».")
    return plan


def preparer(chapitre):
    """Calcule tout sans rien écrire. Renvoie un dictionnaire qui décrit l'effet exact du plan."""
    plan = lire_plan(chapitre)
    racine = Path(chapitre).resolve()
    ignorer = plan.get("ignorer") or {}
    if not isinstance(ignorer, dict) or not all(isinstance(r, str) and r.strip() for r in ignorer.values()):
        sys.exit("Chaque fichier à ignorer doit avoir une raison.")
    nouveaux, erreurs, ajouts = {}, [], {}
    for m in plan["modifications"]:
        chemin = chemin_du_plan(chapitre, m.get("fichier"))
        relatif = chemin.relative_to(racine).as_posix()
        actuel = nouveaux.get(relatif, chemin.read_bytes())
        toutes = m.get("toutes") is True
        try:
            if m.get("action") == "inserer":
                contenu, nombre = inserer(actuel, chemin.suffix.lower(), m["avant"], m["apres"])
            else:
                contenu, nombre = remplacer(actuel, chemin.suffix.lower(), m["avant"], m["apres"], toutes)
        except (zipfile.BadZipFile, KeyError, UnicodeDecodeError) as e:
            erreurs.append(f"{relatif} : lecture impossible ({e}).")
            continue
        if nombre == -2:
            erreurs.append(f"{relatif} : ajouter un paragraphe n'est pas possible dans ce format. Le prof doit le faire lui-même.")
        elif nombre == -1:
            erreurs.append(f"{relatif} : « {m['avant']} » est coupé par une mise en forme. Le prof doit le modifier lui-même.")
        elif nombre == 0:
            erreurs.append(f"{relatif} : « {m['avant']} » est introuvable.")
        elif nombre > 1 and not toutes:
            erreurs.append(f"{relatif} : « {m['avant']} » apparaît {nombre} fois. Précisez l'endroit avec plus de texte.")
        else:
            nouveaux[relatif] = contenu
            ajouts.setdefault(relatif, []).append((m["apres"], nombre))

    restes = {}
    lisibles, non_lus = fichiers_du_dossier(racine)
    illisibles = list(non_lus)
    for chemin in lisibles:
        relatif = chemin.relative_to(racine).as_posix()
        try:
            donnees = nouveaux.get(relatif, chemin.read_bytes())
            morceaux = paragraphes(donnees, chemin.suffix.lower())
        except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError):
            illisibles.append(relatif)
            continue
        for reference in plan["references"]:
            motif = motif_reference(reference)
            nombre = sum(len(motif.findall(t)) for _, t in morceaux)
            # Le nouveau texte peut garder le terme : seul ce qui n'a pas été traité reste à signaler.
            nombre -= sum(len(motif.findall(apres)) * n for apres, n in ajouts.get(relatif, []))
            if nombre > 0:
                restes.setdefault(relatif, []).extend(t.strip() for _, t in morceaux if motif.search(t))
    non_traites = {f: lignes for f, lignes in restes.items() if f not in ignorer}

    empreinte = hashlib.sha256((Path(chapitre) / PLAN).read_bytes())
    for relatif in sorted({m["fichier"] for m in plan["modifications"]}):
        chemin = chemin_du_plan(chapitre, relatif)
        empreinte.update(relatif.encode("utf-8") + chemin.read_bytes())
    return {"plan": plan, "nouveaux": nouveaux, "erreurs": erreurs, "non_traites": non_traites, "ignorer": ignorer,
            "illisibles": sorted(set(illisibles)), "jeton": empreinte.hexdigest()[:12],
            "complet": not erreurs and not non_traites}


def afficher_apercu(etat):
    plan = etat["plan"]
    print(f"MODIFICATION PROPOSÉE\n\nDemande : {plan['demande']}")
    for role, titre in (("cible", "Endroit demandé"), ("reference", "Références à mettre à jour")):
        lignes = [m for m in plan["modifications"] if m["role"] == role]
        if lignes:
            print(f"\n{titre} :")
        for m in lignes:
            if m.get("action") == "inserer":
                print(f"\n  {m['fichier']}\n  après : {m['avant']}\n  + {m['apres']}")
            else:
                print(f"\n  {m['fichier']}\n  - {m['avant']}\n  + {m['apres']}")
    if etat["ignorer"]:
        print("\nFichiers laissés tels quels :")
        for fichier, raison in etat["ignorer"].items():
            print(f"  {fichier} : {raison}")
    if etat["illisibles"]:
        print("\nFichiers non vérifiés, à contrôler vous-même :")
        for fichier in etat["illisibles"]:
            print(f"  {fichier}")
    for erreur in etat["erreurs"]:
        print(f"\n✗ {erreur}")
    if etat["non_traites"]:
        print("\n✗ Références encore présentes et non traitées :")
        for fichier, lignes in etat["non_traites"].items():
            for ligne in lignes:
                print(f"  {fichier} : {ligne}")
    if etat["complet"]:
        print(f"\nSTATUS: EN_ATTENTE_DE_VALIDATION\nJETON: {etat['jeton']}\n\n[1] Appliquer\n[2] Modifier\n[3] Annuler")
    else:
        print("\nSTATUS: PLAN_INCOMPLET")


def sauvegarder(chapitre, message):
    versions = Path(__file__).resolve().parent / "versions.py"
    r = subprocess.run([sys.executable, str(versions), "sauver", message], cwd=chapitre,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(f"Sauvegarde impossible, rien n'a été modifié : {r.stderr.strip()}")


def ecrire_fichiers(chapitre, nouveaux):
    """Prépare tout à côté de chaque fichier, puis remplace : en cas d'échec, les originaux sont remis."""
    racine = Path(chapitre).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        copies = []
        try:
            for i, (relatif, contenu) in enumerate(nouveaux.items()):
                chemin = racine / relatif
                copie = Path(tmp) / str(i)
                copie.write_bytes(chemin.read_bytes())
                copies.append((chemin, copie))
                provisoire = chemin.with_name(f".{chemin.name}.modification")
                provisoire.write_bytes(contenu)
                os.replace(provisoire, chemin)
        except OSError as e:
            for chemin, copie in copies:
                chemin.write_bytes(copie.read_bytes())
                chemin.with_name(f".{chemin.name}.modification").unlink(missing_ok=True)
            sys.exit(f"Écriture impossible, les fichiers d'origine sont conservés : {e}")


def appliquer(chapitre, jeton):
    etat = preparer(chapitre)
    if not etat["complet"]:
        afficher_apercu(etat)
        sys.exit("Plan incomplet : rien n'a été modifié.")
    # Le jeton lie l'application à l'aperçu montré : un changement depuis oblige à le remontrer au prof.
    if jeton != etat["jeton"]:
        sys.exit("Le plan ou un fichier a changé depuis l'aperçu : rien n'a été modifié. Montrez un nouvel aperçu au prof.")
    plan = etat["plan"]
    sauvegarder(chapitre, f"Avant modification : {plan['demande']}")
    ecrire_fichiers(chapitre, etat["nouveaux"])
    journal = Path(chapitre) / JOURNAL
    entrees = json.loads(journal.read_text(encoding="utf-8")) if journal.is_file() else []
    entrees.append({"date": time.strftime("%Y-%m-%dT%H:%M:%S"), "demande": plan["demande"], "jeton": jeton,
                    "modifications": plan["modifications"], "ignorer": etat["ignorer"]})
    journal.write_text(json.dumps(entrees, ensure_ascii=False, indent=2), encoding="utf-8")
    (Path(chapitre) / PLAN).unlink()
    sauvegarder(chapitre, f"Modification : {plan['demande']}")
    print(f"Modification appliquée à {len(etat['nouveaux'])} fichier(s).")
    if (Path(chapitre) / ".travail" / "objectifs.md").is_file():
        problemes, _ = controler(Path(chapitre))
        for probleme in problemes:
            print(f"Problème : {probleme}")


def main():
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    sous = p.add_subparsers(dest="commande", required=True)
    r = sous.add_parser("rechercher")
    r.add_argument("terme")
    r.add_argument("dossier", nargs="?", default=".")
    sous.add_parser("apercu").add_argument("chapitre", nargs="?", default=".")
    a = sous.add_parser("appliquer")
    a.add_argument("chapitre", nargs="?", default=".")
    a.add_argument("--jeton", required=True)
    args = p.parse_args()
    if args.commande == "rechercher":
        if not args.terme.strip():
            sys.exit("Indiquez le texte à rechercher.")
        occurrences, non_verifies = rechercher(args.terme, args.dossier)
        for fichier, lieu, texte in occurrences:
            print(f"{fichier} | {lieu} | {texte}")
        print(f"{len(occurrences)} occurrence(s).")
        for fichier in non_verifies:
            print(f"Non vérifié : {fichier}")
    elif args.commande == "apercu":
        etat = preparer(args.chapitre)
        afficher_apercu(etat)
        sys.exit(0 if etat["complet"] else 1)
    else:
        appliquer(args.chapitre, args.jeton)


if __name__ == "__main__":
    main()
