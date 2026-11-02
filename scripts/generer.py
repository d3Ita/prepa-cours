#!/usr/bin/env python3
"""Génère un .pptx ou un .docx à partir du Markdown simple du plugin.

Usage : generer.py pptx|docx source.md sortie [--modele modele.pptx] [--themes themes.json] [--ecraser] [--outils dossier]

--outils : dossier où installer python-pptx et python-docx au premier lancement.
--themes : couleurs inventées pour certaines diapos, appliquées par une ligne « @theme: nom ».
Les lignes « @theme » et « @dessin » sont ignorées avec un modèle d'établissement, qui décide seul de l'apparence.
"""
import argparse
import re
import subprocess
import sys
import venv
from pathlib import Path

DEPENDANCES = ["python-pptx==1.0.2", "python-docx==1.2.0"]
IMAGE = re.compile(r"!\[(.*?)\]\((.+?)\)")
REPONSE = re.compile(r"\[réponse\s*:\s*(\d+)\]", re.IGNORECASE)
THEME = re.compile(r"@theme\s*:\s*([\w-]+)", re.IGNORECASE)
DESSIN = re.compile(r"@dessin\s*:\s*(.+)", re.IGNORECASE)
MARGE_IMAGE = 0.05


def assurer_outils(dossier):
    """Relance le script dans un environnement Python dédié si les bibliothèques manquent."""
    try:
        import docx, pptx  # noqa: E401,F401
        return
    except ImportError:
        pass
    if not dossier:
        sys.exit("python-pptx et python-docx manquent : relancez avec --outils <dossier>.")
    env = Path(dossier) / "venv"
    if Path(sys.prefix).resolve() == env.resolve():
        sys.exit(f"Installation incomplète : supprimez {env} puis relancez.")
    python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.exists():
        venv.create(env, with_pip=True)
    if subprocess.run([python, "-c", "import docx, pptx"], capture_output=True).returncode:
        print("Installation des outils (première utilisation)…", flush=True)
        r = subprocess.run([python, "-m", "pip", "install", "-q", *DEPENDANCES],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"Installation impossible (Internet est-il disponible ?) : {r.stderr.strip()}")
    sys.exit(subprocess.run([python, __file__, *sys.argv[1:]]).returncode)


def morceaux(texte):
    """Découpe « a **b** c » en [(a, False), (b, True), (c, False)]."""
    parties = re.split(r"\*\*(.+?)\*\*", texte)
    return [(p, i % 2 == 1) for i, p in enumerate(parties) if p]


def lire_diapos(texte):
    diapos = []
    for ligne in texte.splitlines():
        propre = ligne.strip()
        if propre.startswith("# "):
            diapos.append({"titre": propre[2:].strip(), "puces": [], "notes": [], "image": None, "theme": None, "dessin": []})
        elif not propre or set(propre) == {"-"}:
            continue
        elif not diapos:
            sys.exit(f"Le texte doit commencer par un titre « # » : {propre}")
        elif THEME.fullmatch(propre):
            diapos[-1]["theme"] = THEME.fullmatch(propre).group(1)
        elif DESSIN.fullmatch(propre):
            diapos[-1]["dessin"].append(DESSIN.fullmatch(propre).group(1))
        elif propre.startswith(">"):
            diapos[-1]["notes"].append(propre[1:].strip())
        elif IMAGE.fullmatch(propre):
            if diapos[-1]["image"]:
                sys.exit(f"Une seule image par diapo : « {diapos[-1]['titre']} ».")
            diapos[-1]["image"] = IMAGE.fullmatch(propre).group(2)
        elif propre.startswith("- "):
            niveau = (len(ligne) - len(ligne.lstrip())) // 2
            diapos[-1]["puces"].append((niveau, propre[2:].strip()))
        else:
            diapos[-1]["puces"].append((0, propre))
    if not diapos:
        sys.exit("Aucune diapo trouvée : chaque diapo commence par « # Titre ».")
    return diapos


def placer_image(prs, diapo, corps, chemin, avec_texte):
    """Place l'image à droite du texte, ou sur toute la zone de contenu s'il n'y a pas de texte."""
    marge = int(prs.slide_width * MARGE_IMAGE)
    haut = corps.top if corps is not None else int(prs.slide_height * 0.25)
    gauche, largeur = marge, prs.slide_width - 2 * marge
    if avec_texte:
        largeur = (prs.slide_width - 3 * marge) // 2
        corps.left, corps.top, corps.width = marge, haut, largeur
        corps.height = prs.slide_height - haut - marge
        gauche = 2 * marge + largeur
    hauteur = prs.slide_height - haut - marge
    image = diapo.shapes.add_picture(str(chemin), gauche, haut, width=largeur)
    if image.height > hauteur:
        image.width = int(image.width * hauteur / image.height)
        image.height = hauteur
    image.left = gauche + (largeur - image.width) // 2


def declarer_masque_notes(prs):
    """python-pptx crée le masque des notes sans le déclarer : Keynote et l'aperçu de macOS bloquent alors sur le fichier."""
    from lxml import etree
    from pptx.opc.constants import RELATIONSHIP_TYPE
    from pptx.oxml.ns import qn

    presentation = prs.part._element
    if presentation.find(qn("p:notesMasterIdLst")) is not None:
        return
    liste = etree.Element(qn("p:notesMasterIdLst"))
    etree.SubElement(liste, qn("p:notesMasterId")).set(
        qn("r:id"), prs.part.relate_to(prs.part.notes_master_part, RELATIONSHIP_TYPE.NOTES_MASTER))
    presentation.find(qn("p:sldMasterIdLst")).addnext(liste)


def vers_pptx(texte, sortie, modele, base, chemin_themes=None):
    from pptx import Presentation

    import design

    diapos = lire_diapos(texte)
    for contenu in diapos:
        if contenu["image"] and not (base / contenu["image"]).is_file():
            sys.exit(f"Image introuvable : {contenu['image']} (diapo « {contenu['titre']} »).")
    # Un modèle d'établissement décide seul de l'apparence : les thèmes inventés ne s'y appliquent pas.
    themes = design.lire_themes(chemin_themes) if chemin_themes and not modele else {}
    if not modele:
        for contenu in diapos:
            if contenu["theme"] and contenu["theme"] not in themes:
                sys.exit(f"Thème inconnu : {contenu['theme']} (diapo « {contenu['titre']} »). Indiquez-le dans le fichier passé à --themes.")
            design.lire_dessin(contenu)

    prs = Presentation(modele) if modele else Presentation()
    if not modele:
        design.appliquer_base(prs)
    # Un modèle d'établissement contient souvent des diapos d'exemple à retirer.
    ids = prs.slides._sldIdLst
    for diapo in list(ids):
        prs.part.drop_rel(diapo.rId)
        ids.remove(diapo)

    mises_en_page = prs.slide_layouts
    for i, contenu in enumerate(diapos):
        page = mises_en_page[0 if i == 0 or len(mises_en_page) < 2 else 1]
        diapo = prs.slides.add_slide(page)
        if diapo.shapes.title is None:
            sys.exit(f"Le modèle n'a pas de zone de titre (mise en page « {page.name} »).")
        diapo.shapes.title.text = contenu["titre"]
        corps = next((p for p in diapo.placeholders
                      if p.placeholder_format.idx != 0 and p.has_text_frame), None)
        if contenu["puces"] and corps is None:
            sys.exit(f"Le modèle n'a pas de zone de texte (mise en page « {page.name} »).")
        if not modele:
            design.composer(diapo, i, contenu, corps, base, themes, morceaux)
            if contenu["notes"]:
                diapo.notes_slide.notes_text_frame.text = "\n".join(contenu["notes"])
            continue
        for j, (niveau, puce) in enumerate(contenu["puces"]):
            para = corps.text_frame.paragraphs[0] if j == 0 else corps.text_frame.add_paragraph()
            para.level = niveau
            for morceau, gras in morceaux(puce):
                run = para.add_run()
                run.text = morceau
                if gras:
                    run.font.bold = True
        if contenu["image"]:
            placer_image(prs, diapo, corps, base / contenu["image"], bool(contenu["puces"]))
        # Sinon PowerPoint afficherait « Cliquez pour ajouter du texte » en édition.
        if corps is not None and not contenu["puces"]:
            corps._element.getparent().remove(corps._element)
        if contenu["notes"]:
            diapo.notes_slide.notes_text_frame.text = "\n".join(contenu["notes"])
    if any(contenu["notes"] for contenu in diapos):
        declarer_masque_notes(prs)
    prs.save(sortie)


def ajouter_texte(para, texte):
    for morceau, gras in morceaux(texte):
        para.add_run(morceau).bold = gras


def ajouter_tableau(doc, lignes):
    rangees = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lignes]
    rangees = [r for r in rangees if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    colonnes = max(len(r) for r in rangees)
    tableau = doc.add_table(rows=len(rangees), cols=colonnes, style="Table Grid")
    for i, rangee in enumerate(rangees):
        for j, cellule in enumerate(rangee):
            para = tableau.cell(i, j).paragraphs[0]
            for morceau, gras in morceaux(cellule):
                para.add_run(morceau).bold = gras or i == 0


def vers_docx(texte, sortie):
    from docx import Document

    doc = Document()
    tableau = []
    for ligne in texte.splitlines() + [""]:
        propre = ligne.strip()
        if propre.startswith("|"):
            tableau.append(propre)
            continue
        if tableau:
            ajouter_tableau(doc, tableau)
            tableau = []
        if not propre or set(propre) == {"-"}:
            continue
        diese = len(propre) - len(propre.lstrip("#"))
        numero = re.match(r"\d+\.\s+", propre)
        reponse = REPONSE.fullmatch(propre)
        if 1 <= diese <= 6 and propre[diese:].startswith(" "):
            doc.add_heading(propre[diese:].strip(), level=diese)
        elif reponse:
            for _ in range(int(reponse.group(1))):
                doc.add_paragraph("_" * 70)
        elif propre.startswith("- "):
            style = "List Bullet 2" if len(ligne) - len(ligne.lstrip()) >= 2 else "List Bullet"
            ajouter_texte(doc.add_paragraph(style=style), propre[2:].strip())
        elif numero:
            ajouter_texte(doc.add_paragraph(style="List Number"), propre[numero.end():])
        else:
            ajouter_texte(doc.add_paragraph(), propre)
    doc.save(sortie)


def main():
    # Sous Windows, la sortie par défaut n'est pas en UTF-8 et abîme les accents.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("format", choices=["pptx", "docx"])
    p.add_argument("source", type=Path)
    p.add_argument("sortie", type=Path)
    p.add_argument("--modele", type=Path)
    p.add_argument("--themes", type=Path)
    p.add_argument("--ecraser", action="store_true")
    p.add_argument("--outils", type=Path)
    a = p.parse_args()

    # Le fichier a pu être retouché à la main : ne jamais l'écraser sans demande explicite.
    if a.sortie.exists() and not a.ecraser:
        sys.exit(f"{a.sortie} existe déjà. Sauvegardez-le, puis utilisez --ecraser si besoin.")
    if (a.modele or a.themes) and a.format != "pptx":
        sys.exit("--modele et --themes ne fonctionnent qu'avec pptx.")
    if a.modele and not a.modele.is_file():
        sys.exit(f"Modèle introuvable : {a.modele}")
    if not a.source.is_file():
        sys.exit(f"Fichier introuvable : {a.source}")
    assurer_outils(a.outils)
    texte = a.source.read_text(encoding="utf-8")
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    try:
        if a.format == "pptx":
            vers_pptx(texte, a.sortie, a.modele, a.source.resolve().parent, a.themes)
        else:
            vers_docx(texte, a.sortie)
    except PermissionError:
        sys.exit(f"Impossible d'écrire {a.sortie} : fermez-le dans PowerPoint, Word ou LibreOffice.")
    print(f"Créé : {a.sortie}")


if __name__ == "__main__":
    main()
