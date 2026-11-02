"""Le style « cahier d'exposé » des diapos : papier chaud, notes scotchées, schémas dessinés à la main.

Le fond, les polices et les titres sont écrits dans le masque : le prof peut les changer d'un coup.
Le reste se compose diapo par diapo selon le contenu. Un modèle d'établissement n'utilise rien de tout cela.
"""
import json
import math
import random
import re
import sys

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.opc.constants import RELATIONSHIP_TYPE
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Inches, Pt

LARGEUR, HAUTEUR = 13.333, 7.5  # 16:9, en pouces
PAPIER, ENCRE, TEXTE, ROUGE, VERT, JAUNE, BLEU, BRUN, TERRE = ("FBF4E4", "232019", "2F2A22", "D2502B", "3F8F5A",
                                                               "F4C542", "3C86B5", "8A5A32", "E8D7B5")
VERT_CLAIR = "5BAE74"
CARTES = ("DCEFE2", "D7E9F5", "FBE0D6", "FFF1C2")
BASE = {"fond": PAPIER, "titre": ENCRE, "texte": TEXTE, "accent": ROUGE, "police": "Georgia"}
POLICE_TITRES, POLICE_TEXTE = "Georgia", "Trebuchet MS"
COULEURS_DESSIN = {"vert": VERT, "bleu": BLEU, "rouge": ROUGE, "jaune": JAUNE, "brun": BRUN, "encre": ENCRE}
ACTIVITE = re.compile(r"(à vous|activité|exercice|atelier)\b", re.IGNORECASE)
TAILLES_LISTE = (2600, 2200, 2000, 1800, 1800)

# Présentes sous Windows et macOS, et remplacées proprement ailleurs : le rendu reste prévisible en classe.
POLICES = ("Georgia", "Trebuchet MS", "Arial", "Verdana", "Tahoma", "Times New Roman")
COULEURS_THEME = ("fond", "titre", "texte", "accent")
CONTRASTE_TEXTE, CONTRASTE_GRAND = 4.5, 3.0  # Seuils WCAG AA pour le texte courant et les grands textes.
HEXA = re.compile(r"[0-9A-Fa-f]{6}")
NOM_THEME = re.compile(r"[\w-]+")
MAX_ELEMENTS_DESSIN = 30
LONGUEUR_ETIQUETTE = 60


def luminance(couleur):
    canaux = [int(couleur[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, v, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux]
    return 0.2126 * r + 0.7152 * v + 0.0722 * b


def contraste(a, b):
    """Le rapport de contraste WCAG entre deux couleurs : de 1 (identiques) à 21 (noir sur blanc)."""
    clair, sombre = sorted((luminance(a), luminance(b)), reverse=True)
    return (clair + 0.05) / (sombre + 0.05)


def verifier_theme(nom, theme):
    """Renvoie les erreurs d'un thème. Le fichier vient d'un agent : rien n'est appliqué sans ce contrôle."""
    if not NOM_THEME.fullmatch(nom):
        return [f"Nom de thème invalide : {nom}."]
    if not isinstance(theme, dict):
        return [f"Thème « {nom} » : description invalide."]
    erreurs = [f"Thème « {nom} » : « {c} » doit être une couleur comme 1F5F4A." for c in COULEURS_THEME
               if not isinstance(theme.get(c), str) or not HEXA.fullmatch(theme[c])]
    if theme.get("police", POLICE_TITRES) not in POLICES:
        erreurs.append(f"Thème « {nom} » : police inconnue. Choisissez parmi : {', '.join(POLICES)}.")
    if erreurs:
        return erreurs
    essais = [("texte", theme["fond"], CONTRASTE_TEXTE, "ce fond"), ("titre", theme["fond"], CONTRASTE_GRAND, "ce fond"),
              ("accent", "FFFFFF", CONTRASTE_GRAND, "le blanc du titre d'activité")]
    essais += [("texte", carte, CONTRASTE_TEXTE, f"une carte {carte}") for carte in CARTES]
    for champ, autre, seuil, lieu in essais:
        valeur = contraste(theme[champ], autre)
        if valeur < seuil:
            erreurs.append(f"Thème « {nom} » : « {champ} » est illisible sur {lieu} (contraste {valeur:.1f}, minimum {seuil}).")
    return erreurs


def lire_themes(chemin):
    """Lit le fichier des thèmes et arrête tout s'il y en a un mauvais : mieux vaut une erreur qu'une diapo illisible."""
    try:
        themes = json.loads(chemin.read_text(encoding="utf-8"))
    except OSError:
        sys.exit(f"Fichier de thèmes introuvable : {chemin}")
    except ValueError as e:
        sys.exit(f"Fichier de thèmes illisible : {e}")
    if not isinstance(themes, dict):
        sys.exit("Le fichier de thèmes doit associer un nom à chaque thème.")
    erreurs = [e for nom, theme in themes.items() for e in verifier_theme(nom, theme)]
    if erreurs:
        sys.exit("\n".join(erreurs))
    return themes


def lire_element(ligne):
    """Lit « plante 50 80 1 » ou « fleche 10 30 40 45 rouge ». Renvoie un dictionnaire ; une erreur lève ValueError."""
    morceaux = ligne.split()
    if not morceaux:
        raise ValueError("ligne vide")
    genre, valeurs = morceaux[0], morceaux[1:]
    formes = {"sol": 1, "plante": 3, "soleil": 3, "cercle": 4, "rect": 5, "trait": 5, "fleche": 5}

    def nombre(texte, minimum=0.0, maximum=100.0):
        try:
            valeur = float(texte.replace(",", "."))
        except ValueError:
            raise ValueError(f"« {texte} » n'est pas un nombre") from None
        if not math.isfinite(valeur) or not minimum <= valeur <= maximum:
            raise ValueError(f"{texte} doit être entre {minimum:g} et {maximum:g}")
        return valeur

    def couleur(nom):
        if nom not in COULEURS_DESSIN:
            raise ValueError(f"couleur inconnue : {nom} (choisir parmi {', '.join(COULEURS_DESSIN)})")
        return COULEURS_DESSIN[nom]

    if genre == "etiquette":
        if len(valeurs) < 4:
            raise ValueError("écrire : etiquette x y couleur texte")
        texte = " ".join(valeurs[3:])
        if len(texte) > LONGUEUR_ETIQUETTE:
            raise ValueError(f"étiquette de plus de {LONGUEUR_ETIQUETTE} caractères")
        return {"genre": genre, "x": nombre(valeurs[0]), "y": nombre(valeurs[1]), "couleur": couleur(valeurs[2]), "texte": texte}
    if genre not in formes:
        raise ValueError(f"élément inconnu : {genre} (choisir parmi {', '.join([*formes, 'etiquette'])})")
    if len(valeurs) != formes[genre]:
        raise ValueError(f"{genre} attend {formes[genre]} valeurs")
    if genre == "sol":
        return {"genre": genre, "y": nombre(valeurs[0])}
    if genre in ("plante", "soleil"):
        return {"genre": genre, "x": nombre(valeurs[0]), "y": nombre(valeurs[1]), "taille": nombre(valeurs[2], 0.3, 2)}
    if genre == "cercle":
        return {"genre": genre, "x": nombre(valeurs[0]), "y": nombre(valeurs[1]), "taille": nombre(valeurs[2], 1, 60), "couleur": couleur(valeurs[3])}
    a, b, c, d = (nombre(v) for v in valeurs[:4])
    return {"genre": genre, "a": a, "b": b, "c": c, "d": d, "couleur": couleur(valeurs[4])}


def lire_dessin(contenu):
    """Valide le dessin d'une diapo avant de créer le moindre fichier."""
    lignes = contenu["dessin"]
    if lignes and ACTIVITE.match(contenu["titre"]):
        sys.exit(f"Diapo « {contenu['titre']} » : une diapo d'activité ne peut pas contenir de dessin.")
    if len(lignes) > MAX_ELEMENTS_DESSIN:
        sys.exit(f"Diapo « {contenu['titre']} » : plus de {MAX_ELEMENTS_DESSIN} éléments de dessin.")
    elements = []
    for ligne in lignes:
        try:
            elements.append(lire_element(ligne))
        except ValueError as e:
            sys.exit(f"Diapo « {contenu['titre']} », dessin « {ligne} » : {e}.")
    return elements


def regler_theme_base(prs):
    partie = prs.slide_master.part.part_related_by(RELATIONSHIP_TYPE.THEME)
    xml = partie.blob.decode("utf-8")
    couleurs = {"dk1": TEXTE, "lt1": PAPIER, "dk2": ENCRE, "lt2": TERRE, "accent1": ROUGE, "accent2": JAUNE, "accent3": VERT,
                "accent4": BLEU, "accent5": BRUN, "accent6": VERT_CLAIR, "hlink": BLEU, "folHlink": BRUN}
    for nom, couleur in couleurs.items():
        xml = re.sub(rf"<a:{nom}>.*?</a:{nom}>", f'<a:{nom}><a:srgbClr val="{couleur}"/></a:{nom}>', xml, flags=re.DOTALL)
    for bloc, police in (("majorFont", POLICE_TITRES), ("minorFont", POLICE_TEXTE)):
        xml = re.sub(rf'(<a:{bloc}><a:latin typeface=")[^"]*', rf"\g<1>{police}", xml)
    partie._blob = xml.encode("utf-8")


def passer_en_16_9(prs):
    """Étire toutes les mises en page : celles que le plugin n'utilise pas restent correctes pour le prof."""
    largeur = Inches(LARGEUR)
    rapport = largeur / prs.slide_width
    prs.slide_width, prs.slide_height = largeur, Inches(HAUTEUR)
    for porteur in (prs.slide_master, *prs.slide_layouts):
        for forme in porteur.placeholders:
            xfrm = forme._element.spPr.find(qn("a:xfrm"))
            if xfrm is not None:
                decalage, taille = xfrm.find(qn("a:off")), xfrm.find(qn("a:ext"))
                decalage.set("x", str(int(int(decalage.get("x")) * rapport)))
                taille.set("cx", str(int(int(taille.get("cx")) * rapport)))


def regler_style_niveau(niveau, taille, nom_couleur, police, gras=False):
    """Remplace le style de texte d'un niveau, sans toucher aux puces ni aux retraits."""
    niveau.set("algn", "l")
    ancien = niveau.find(qn("a:defRPr"))
    if ancien is not None:
        niveau.remove(ancien)
    # Sans cette référence à la police du thème, Keynote n'affiche plus le gras.
    niveau.append(parse_xml(f'<a:defRPr {nsdecls("a")} sz="{taille}" b="{int(gras)}" kern="1200">'
                            f'<a:solidFill><a:schemeClr val="{nom_couleur}"/></a:solidFill><a:latin typeface="{police}"/></a:defRPr>'))


def regler_masque(prs):
    styles = prs.slide_master.element.find(qn("p:txStyles"))
    regler_style_niveau(styles.find(qn("p:titleStyle")).find(qn("a:lvl1pPr")), 4400, "tx2", "+mj-lt", gras=True)
    corps = styles.find(qn("p:bodyStyle"))
    for numero, taille in enumerate(TAILLES_LISTE, 1):
        niveau = corps.find(qn(f"a:lvl{numero}pPr"))
        regler_style_niveau(niveau, taille, "tx1", "+mn-lt")
        espace = niveau.find(qn("a:spcBef"))
        if espace is not None:
            niveau.remove(espace)
        # L'ordre des éléments est imposé par le format : l'espacement vient en premier, la couleur de puce ensuite.
        niveau.insert(0, parse_xml(f'<a:spcBef {nsdecls("a")}><a:spcPts val="{1000 if numero == 1 else 400}"/></a:spcBef>'))
        niveau.insert(1, parse_xml(f'<a:buClr {nsdecls("a")}><a:schemeClr val="accent1"/></a:buClr>'))


def placer(forme, x, y, largeur, hauteur):
    forme.left, forme.top, forme.width, forme.height = Inches(x), Inches(y), Inches(largeur), Inches(hauteur)


def regler_texte_mise_en_page(espace, taille, nom_couleur, police, gras=False):
    liste = espace._element.txBody.find(qn("a:lstStyle"))
    niveau = liste.find(qn("a:lvl1pPr"))
    if niveau is None:
        niveau = parse_xml(f'<a:lvl1pPr {nsdecls("a")}/>')
        liste.insert(0, niveau)
    regler_style_niveau(niveau, taille, nom_couleur, police, gras)


def trait_mise_en_page(identifiant, x, y, largeur, hauteur):
    return parse_xml(
        f'<p:sp {nsdecls("p", "a")}><p:nvSpPr><p:cNvPr id="{identifiant}" name="Trait"/><p:cNvSpPr/><p:nvPr userDrawn="1"/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{Inches(x)}" y="{Inches(y)}"/><a:ext cx="{Inches(largeur)}" cy="{Inches(hauteur)}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:schemeClr val="accent2"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="fr-FR"/></a:p></p:txBody></p:sp>')


def regler_mises_en_page(prs):
    page = prs.slide_layouts[0]
    titre, sous_titre = page.placeholders[0], page.placeholders[1]
    placer(titre, .7, .75, 7.2, 3.3)
    titre._element.txBody.find(qn("a:bodyPr")).set("anchor", "b")
    regler_texte_mise_en_page(titre, 7200, "tx2", "+mj-lt", gras=True)
    placer(sous_titre, .7, 4.5, 7.2, 1.9)
    regler_texte_mise_en_page(sous_titre, 2800, "tx1", "+mn-lt")

    page = prs.slide_layouts[1]
    titre, corps = page.placeholders[0], page.placeholders[1]
    placer(titre, .6, .25, 12.1, 1.05)
    titre._element.txBody.find(qn("a:bodyPr")).set("anchor", "b")
    placer(corps, .6, 1.7, 12.1, 5.3)
    corps_pr = corps._element.txBody.find(qn("a:bodyPr"))
    if corps_pr.find(qn("a:normAutofit")) is None:
        corps_pr.append(parse_xml(f'<a:normAutofit {nsdecls("a")}/>'))
    page.shapes._spTree.insert(2, trait_mise_en_page(101, .7, 1.36, 3.6, .12))


def appliquer_base(prs):
    regler_theme_base(prs)
    passer_en_16_9(prs)
    regler_masque(prs)
    regler_mises_en_page(prs)


def bloc(formes, genre, x, y, largeur, hauteur, couleur, rotation=0, opacite=None):
    forme = formes.add_shape(genre, Inches(x), Inches(y), Inches(largeur), Inches(hauteur))
    forme.fill.solid()
    forme.fill.fore_color.rgb = RGBColor.from_string(couleur)
    forme.line.fill.background()
    forme.rotation = rotation
    forme.shadow.inherit = False
    if opacite is not None:
        forme.fill._xPr.find(qn("a:solidFill"))[0].append(parse_xml(f'<a:alpha {nsdecls("a")} val="{opacite}"/>'))
    return forme


def derriere_le_texte(diapo, *formes):
    """Le décor passe sous le titre : on ne doit jamais avoir à lire à travers."""
    arbre = diapo.shapes._spTree
    for position, forme in enumerate(formes, 2):
        arbre.remove(forme._element)
        arbre.insert(position, forme._element)


def lignes_estimees(texte, largeur, taille):
    """Estime les lignes d'un texte : une moyenne de 0,52 cadratin par caractère, un peu large pour rester prudent."""
    return math.ceil(len(texte.replace("*", "")) / max(1, (largeur * 72) / (taille * .52)))


def tient(puces, largeur, hauteur, taille):
    # Un mot plus large que la zone serait coupé en deux : c'est illisible, même si le texte tient en hauteur.
    if any(len(mot) * taille * .62 / 72 > largeur for _, texte in puces for mot in texte.replace("*", "").split()):
        return False
    lignes = sum(lignes_estimees(texte, largeur, taille) for _, texte in puces)
    return lignes * taille * 1.25 / 72 + .15 * max(0, len(puces) - 1) <= hauteur


def remplir(cadre, lignes, morceaux, police, taille, couleur_texte, gras=False, accent=None):
    cadre.word_wrap = True
    for numero, ligne in enumerate(lignes):
        para = cadre.paragraphs[0] if numero == 0 else cadre.add_paragraph()
        if numero:
            para.space_before = Pt(10)
        for morceau, en_gras in morceaux(ligne):
            run = para.add_run()
            run.text = morceau
            run.font.name = police
            run.font.size = Pt(taille)
            run.font.bold = gras or en_gras
            run.font.color.rgb = RGBColor.from_string(accent if accent and en_gras else couleur_texte)


def carte(diapo, x, y, largeur, hauteur, couleur, rotation, groupe, morceaux, taille, palette):
    forme = bloc(diapo.shapes, MSO_SHAPE.RECTANGLE, x, y, largeur, hauteur, couleur, rotation)
    cadre = forme.text_frame
    cadre.vertical_anchor = MSO_ANCHOR.MIDDLE
    cadre.margin_left = cadre.margin_right = Inches(.28)
    cadre.margin_top = cadre.margin_bottom = Inches(.14)
    remplir(cadre, groupe, morceaux, POLICE_TEXTE, taille, palette["texte"])
    for numero, para in enumerate(cadre.paragraphs):
        para.alignment = 1  # À gauche : le texte d'une note se lit comme une note.
        for run in para.runs if numero else ():
            run.font.size = Pt(round(taille * .8))
    return forme


def grouper_puces(puces):
    """Rassemble chaque puce et ses sous-puces : une idée et ses détails tiennent sur la même carte."""
    groupes = []
    for niveau, texte in puces:
        if niveau and groupes:
            groupes[-1].append(texte)
        else:
            groupes.append([texte])
    return groupes


def disposer_cartes(puces, zone):
    """Renvoie (groupes, position de chaque carte, taille du texte), ou None si les cartes ne conviennent pas à ce contenu."""
    groupes = grouper_puces(puces)
    n = len(groupes)
    if not groupes or n > (3 if zone else 4):
        return None
    hauteur_ligne = (5.3 - .22 * (n - 1)) / n
    en_lignes = [(.6, 1.75 + i * (hauteur_ligne + .22), 12.1, hauteur_ligne) for i in range(n)]
    if zone:
        possibles = [[(.5, 1.75 + i * (hauteur_ligne + .22), 3.9, hauteur_ligne) for i in range(n)]]
    elif n == 4:
        possibles = [[(.6 + c * 6.2, 1.8 + r * 2.65, 5.9, 2.4) for r in range(2) for c in range(2)], en_lignes]
    else:
        largeur = (12.1 - .3 * (n - 1)) / n
        possibles = [[(.6 + i * (largeur + .3), 1.95, largeur, 4.6 if n > 1 else 3.6) for i in range(n)], en_lignes]
    # La plus grande taille qui tient, pour que le texte occupe la carte au lieu d'y flotter.
    # Quand des colonnes étroites forceraient un texte minuscule, les lignes le gardent lisible.
    for taille in (44, 38, 32, 28, 24, 20) if not zone else (32, 28, 24, 20):
        for cases in possibles:
            if all(tient([(0, t) for t in g], c[2] - .56, c[3] - .28, taille) for g, c in zip(groupes, cases)):
                return groupes, cases, taille
    return None


def trace_main(formes, points, couleur, epaisseur, graine, tremblement=.018):
    """Une ligne légèrement irrégulière : c'est ce qui donne l'impression d'un dessin à la main."""
    alea = random.Random(graine)
    suite = []
    for (a, b), (c, d) in zip(points, points[1:]):
        n = max(2, int(math.hypot(c - a, d - b) / .18))
        suite += [(a + (c - a) * i / n + alea.uniform(-tremblement, tremblement),
                   b + (d - b) * i / n + alea.uniform(-tremblement, tremblement)) for i in range(n)]
    suite.append(points[-1])
    emu = [(Inches(x), Inches(y)) for x, y in suite]
    constructeur = formes.build_freeform(emu[0][0], emu[0][1], scale=1.0)
    constructeur.add_line_segments(emu[1:], close=False)
    forme = constructeur.convert_to_shape()
    forme.fill.background()
    forme.line.color.rgb = RGBColor.from_string(couleur)
    forme.line.width = Pt(epaisseur)
    forme.shadow.inherit = False


def dessiner_fleche(formes, a, b, c, d, couleur, graine):
    trace_main(formes, [(a, b), (c, d)], couleur, 4, graine)
    angle = math.atan2(d - b, c - a)
    for ecart in (2.6, -2.6):
        trace_main(formes, [(c, d), (c + .3 * math.cos(angle + ecart), d + .3 * math.sin(angle + ecart))], couleur, 4, graine + 1, .004)


def dessiner_plante(formes, x, sol, echelle):
    trace_main(formes, [(x, sol), (x + .05 * echelle, sol - 1.3 * echelle), (x - .03 * echelle, sol - 2.7 * echelle)], VERT, 5 * echelle, 3, .012)
    for dx, dy, rotation, couleur in ((.04, -1.5, 0, VERT_CLAIR), (-1.2, -1.85, 270, VERT), (-.02, -3.05, 315, VERT)):
        bloc(formes, MSO_SHAPE.TEAR, x + dx * echelle, sol + dy * echelle, 1.15 * echelle, .72 * echelle, couleur, rotation)
    for graine, (dx, dy) in enumerate(((-.9, .75), (-.35, .95), (.3, .98), (.9, .72))):
        trace_main(formes, [(x, sol), (x + dx * .55 * echelle, sol + dy * .55 * echelle), (x + dx * echelle, sol + dy * echelle)], BRUN, 3, graine + 7, .03)


def dessiner_soleil(formes, x, y, rayon):
    bloc(formes, MSO_SHAPE.OVAL, x - rayon, y - rayon, 2 * rayon, 2 * rayon, "E9A91D")
    for i in range(10):
        angle = i * math.pi / 5
        trace_main(formes, [(x + (rayon + .13) * math.cos(angle), y + (rayon + .13) * math.sin(angle)),
                            (x + (rayon + .45) * math.cos(angle), y + (rayon + .45) * math.sin(angle))], "E9A91D", 4, i, .008)


def dessiner(diapo, elements, x0, y0, largeur, hauteur):
    """Compose un schéma dans sa zone : ses formes restent groupées, pour que le prof le déplace d'un geste."""
    groupe = diapo.shapes.add_group_shape()
    formes = groupe.shapes
    position = lambda px, py: (x0 + largeur * px / 100, y0 + hauteur * py / 100)
    echelle = min(largeur, hauteur) / 5
    for graine, e in enumerate(elements, 1):
        if e["genre"] == "sol":
            _, y = position(0, e["y"])
            bloc(formes, MSO_SHAPE.RECTANGLE, x0, y, largeur, y0 + hauteur - y, TERRE)
        elif e["genre"] == "plante":
            x, y = position(e["x"], e["y"])
            dessiner_plante(formes, x, y, echelle * e["taille"])
        elif e["genre"] == "soleil":
            x, y = position(e["x"], e["y"])
            dessiner_soleil(formes, x, y, .55 * echelle * e["taille"])
        elif e["genre"] == "cercle":
            x, y = position(e["x"], e["y"])
            rayon = largeur * e["taille"] / 100
            bloc(formes, MSO_SHAPE.OVAL, x - rayon, y - rayon, 2 * rayon, 2 * rayon, e["couleur"], opacite=55000)
        elif e["genre"] == "rect":
            xa, ya = position(e["a"], e["b"])
            xb, yb = position(e["c"], e["d"])
            bloc(formes, MSO_SHAPE.RECTANGLE, min(xa, xb), min(ya, yb), abs(xb - xa), abs(yb - ya), e["couleur"], opacite=55000)
        elif e["genre"] in ("trait", "fleche"):
            xa, ya = position(e["a"], e["b"])
            xb, yb = position(e["c"], e["d"])
            if e["genre"] == "trait":
                trace_main(formes, [(xa, ya), (xb, yb)], e["couleur"], 4, graine)
            else:
                dessiner_fleche(formes, xa, ya, xb, yb, e["couleur"], graine)
        else:
            x, y = position(e["x"], e["y"])
            boite = formes.add_textbox(Inches(x), Inches(y), Inches(max(1.2, x0 + largeur - x)), Inches(.5))
            boite.text_frame.margin_left = boite.text_frame.margin_top = 0
            remplir(boite.text_frame, [e["texte"]], lambda t: [(t, True)], POLICE_TEXTE, 24, e["couleur"])
    return groupe


def placer_image(diapo, chemin, x0, y0, largeur, hauteur):
    image = diapo.shapes.add_picture(str(chemin), Inches(x0), Inches(y0), width=Inches(largeur))
    if image.height > Inches(hauteur):
        image.width = int(image.width * Inches(hauteur) / image.height)
        image.height = Inches(hauteur)
    image.left = Inches(x0) + (Inches(largeur) - image.width) // 2
    image.top = Inches(y0) + (Inches(hauteur) - image.height) // 2


def taille_titre(titre, grande, moyenne, petite):
    return grande if len(titre) <= 20 else moyenne if len(titre) <= 42 else petite


def regler_titre(diapo, contenu, palette, taille, couleur=None):
    for para in diapo.shapes.title.text_frame.paragraphs:
        for run in para.runs:
            run.font.size = Pt(taille)
            run.font.name = palette["police"]
            run.font.bold = True
            run.font.color.rgb = RGBColor.from_string(couleur or palette["titre"])


def retirer(corps):
    if corps is not None:
        corps._element.getparent().remove(corps._element)


def remplir_liste(corps, puces, morceaux, couleur, accent, taille=None):
    for numero, (niveau, puce) in enumerate(puces):
        para = corps.text_frame.paragraphs[0] if numero == 0 else corps.text_frame.add_paragraph()
        para.level = niveau
        for morceau, gras in morceaux(puce):
            run = para.add_run()
            run.text = morceau
            run.font.color.rgb = RGBColor.from_string(couleur)
            if taille:
                run.font.size = Pt(taille - 4 * min(niveau, 2))
            if gras:
                run.font.bold = True
        para._p.get_or_add_pPr().insert(0, parse_xml(f'<a:buClr {nsdecls("a")}><a:srgbClr val="{accent}"/></a:buClr>'))


def composer_ouverture(diapo, contenu, corps, dossier, palette, morceaux):
    regler_titre(diapo, contenu, palette, taille_titre(contenu["titre"], 72, 54, 40))
    decor = bloc(diapo.shapes, MSO_SHAPE.OVAL, 7.9, -1.4, 6.6, 6.6, JAUNE, opacite=38000)
    regle = bloc(diapo.shapes, MSO_SHAPE.RECTANGLE, .78, 4.2, 5.8, .16, JAUNE)
    derriere_le_texte(diapo, decor, regle)
    if contenu["puces"]:
        remplir_liste(corps, [(0, p) for _, p in contenu["puces"]], morceaux, palette["texte"], palette["accent"])
    else:
        retirer(corps)
    elements = lire_dessin(contenu)
    if elements:
        dessiner(diapo, elements, 7.9, 0, LARGEUR - 7.9, HAUTEUR)
    if contenu["image"]:
        placer_image(diapo, dossier / contenu["image"], 8.1, .9, 4.8, 5.7)


def composer_activite(diapo, contenu, corps, palette, morceaux):
    diapo.background.fill.solid()
    diapo.background.fill.fore_color.rgb = RGBColor.from_string(JAUNE if palette["fond"] == PAPIER else palette["fond"])
    bande = bloc(diapo.shapes, MSO_SHAPE.RECTANGLE, 0, 0, 4.6, HAUTEUR, palette["accent"])
    titre = diapo.shapes.title
    placer(titre, .4, .75, 3.85, 5.8)
    titre._element.txBody.find(qn("a:bodyPr")).set("anchor", "t")
    regler_titre(diapo, contenu, palette, 60 if len(contenu["titre"]) <= 8 else 36, "FFFFFF")
    derriere_le_texte(diapo, bande)
    retirer(corps)
    if contenu["puces"]:
        lignes = [p for _, p in contenu["puces"]]
        for taille in (44, 38, 34, 30, 26, 22, 18):
            if tient([(0, l) for l in lignes], 6.75, 4.7, taille):
                break
        note = bloc(diapo.shapes, MSO_SHAPE.RECTANGLE, 5.1, 1.05, 7.6, 5.4, "FFFDF5", -1.5)
        cadre = note.text_frame
        cadre.vertical_anchor = MSO_ANCHOR.MIDDLE
        cadre.margin_left = cadre.margin_right = Inches(.42)
        remplir(cadre, lignes, morceaux, palette["police"], taille, palette["texte"], accent=palette["accent"])
        for para in cadre.paragraphs:
            para.alignment = 1
        bloc(diapo.shapes, MSO_SHAPE.RECTANGLE, 8.1, .86, 1.6, .42, "E6D7A6", -2, opacite=70000)


def composer_contenu(diapo, contenu, corps, dossier, palette, morceaux):
    regler_titre(diapo, contenu, palette, taille_titre(contenu["titre"], 44, 44, 34))
    elements = lire_dessin(contenu)
    zone = bool(elements or contenu["image"])
    disposition = disposer_cartes(contenu["puces"], zone)
    if disposition:
        retirer(corps)
        groupes, cases, taille = disposition
        for numero, (groupe, (x, y, largeur, hauteur)) in enumerate(zip(groupes, cases)):
            carte(diapo, x, y, largeur, hauteur, CARTES[numero % len(CARTES)], (-1.5, 1, -1, 1.5)[numero % 4], groupe, morceaux, taille, palette)
    elif contenu["puces"]:
        largeur = 3.7 if zone else 11.5
        if zone:
            placer(corps, .6, 1.7, 4.2, 5.3)
        tailles = [t for t in (36, 32, 28, 24, 20) if tient(contenu["puces"], largeur, 5.1, t)]
        remplir_liste(corps, contenu["puces"], morceaux, palette["texte"], palette["accent"], tailles[0] if tailles else 18)
    else:
        retirer(corps)
    if elements:
        dessiner(diapo, elements, 4.7 if contenu["puces"] else .6, 1.55, 8.3 if contenu["puces"] else 12.1, 5.75)
    if contenu["image"]:
        placer_image(diapo, dossier / contenu["image"], 4.9 if contenu["puces"] else .9, 1.7, 7.9 if contenu["puces"] else 11.5, 5.4)


def composer(diapo, numero, contenu, corps, dossier, themes, morceaux):
    """Choisit la disposition selon la place de la diapo et son contenu, puis la compose."""
    palette = {**BASE, **themes.get(contenu["theme"], {})}
    palette = {k: v.upper() if k in COULEURS_THEME else v for k, v in palette.items()}
    if contenu["theme"]:
        diapo.background.fill.solid()
        diapo.background.fill.fore_color.rgb = RGBColor.from_string(palette["fond"])
    if numero == 0:
        composer_ouverture(diapo, contenu, corps, dossier, palette, morceaux)
    elif ACTIVITE.match(contenu["titre"]):
        composer_activite(diapo, contenu, corps, palette, morceaux)
    else:
        composer_contenu(diapo, contenu, corps, dossier, palette, morceaux)
