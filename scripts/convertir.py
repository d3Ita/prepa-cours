"""Convertit les documents générés vers le format préféré de l'utilisateur.

Le plugin construit toujours un .pptx ou un .docx, puis le convertit avec LibreOffice ou, sur Mac, avec Keynote.
odp et odt remplacent le fichier d'origine, car ils restent modifiables. pdf et key s'y ajoutent : le plugin
ne sait pas les modifier, et le fichier éditable reste nécessaire aux retouches.
"""
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FORMATS = {"pptx": ("pptx", "odp", "key", "pdf"), "docx": ("docx", "odt", "pdf")}
REMPLACE = ("odp", "odt")
SUFFIXES_SORTIE = (".pptx", ".docx", ".odp", ".odt", ".key", ".pdf")
DELAI = 180
CHEMINS_SOFFICE = ("soffice", "libreoffice", "/Applications/LibreOffice.app/Contents/MacOS/soffice",
                   r"C:\Program Files\LibreOffice\program\soffice.exe")


def lire_format(valeur, source):
    """Renvoie le format demandé, ou None pour garder le .pptx ou le .docx.

    Sans réglage, la valeur peut rester un texte « ${user_config…} » : cela revient au format par défaut.
    """
    if not valeur or valeur.startswith("$") or valeur == source:
        return None
    format_demande = valeur.strip().lstrip(".").casefold()
    if format_demande == source:
        return None
    if format_demande not in FORMATS[source]:
        sys.exit(f"Format de sortie inconnu pour un {source} : {valeur}. Choisissez parmi : {', '.join(FORMATS[source])}.")
    return format_demande


def commande_soffice():
    """Une variable d'environnement permet de choisir le programme, par exemple pour les tests."""
    imposee = os.environ.get("PREPA_COURS_SOFFICE")
    if imposee:
        return shlex.split(imposee)
    for chemin in CHEMINS_SOFFICE:
        trouve = shutil.which(chemin) or (chemin if Path(chemin).is_file() else None)
        if trouve:
            return [trouve]
    return None


def avec_libreoffice(source, cible, format_demande):
    commande = commande_soffice()
    if commande is None:
        return "LibreOffice n'est pas installé"
    with tempfile.TemporaryDirectory() as dossier:
        # Un profil à part : la conversion fonctionne même si le prof a LibreOffice ouvert.
        profil = Path(dossier, "profil").as_uri()
        try:
            r = subprocess.run([*commande, f"-env:UserInstallation={profil}", "--headless", "--convert-to", format_demande,
                                "--outdir", dossier, str(source)], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=DELAI, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"LibreOffice a échoué ({e})"
        produit = Path(dossier) / f"{Path(source).stem}.{format_demande}"
        if r.returncode or not produit.is_file():
            return f"LibreOffice a échoué ({(r.stderr or r.stdout).strip()[:200]})"
        shutil.move(str(produit), str(cible))
    return None


def avec_keynote(source, cible, format_demande):
    if sys.platform != "darwin" or not Path("/Applications/Keynote.app").exists():
        return "Keynote n'est disponible que sur Mac"
    action = (f'export d to POSIX file "{cible}" as PDF' if format_demande == "pdf"
              else f'save d in POSIX file "{cible}"')
    script = ["-e", f"with timeout of {DELAI} seconds", "-e", 'tell application "Keynote"',
              "-e", f'set d to open POSIX file "{source}"', "-e", action, "-e", "close d saving no", "-e", "end tell", "-e", "end timeout"]
    try:
        r = subprocess.run(["osascript", *script], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=DELAI + 20)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"Keynote a échoué ({e})"
    if r.returncode or not Path(cible).exists():
        return f"Keynote a échoué ({r.stderr.strip()[:200]})"
    return None


def convertir(source, cible, format_demande):
    """Écrit le fichier converti. Renvoie None si tout va bien, sinon la raison de l'échec."""
    source, cible = Path(source).resolve(), Path(cible).resolve()
    if any(c in str(source) + str(cible) for c in '"\\') and format_demande == "key":
        return "Ce chemin de fichier ne permet pas la conversion avec Keynote"
    if format_demande == "key":
        return avec_keynote(source, cible, format_demande)
    erreur = avec_libreoffice(source, cible, format_demande)
    # Sans LibreOffice, un Mac peut encore produire le PDF de diapos avec Keynote.
    if erreur and format_demande == "pdf" and source.suffix == ".pptx" and '"' not in str(source) + str(cible):
        if avec_keynote(source, cible, format_demande) is None:
            return None
    return erreur
