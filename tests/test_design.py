"""Vérifie le style des diapos : dispositions, dessins, couleurs par sujet et modèle d'établissement."""
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))

import design  # noqa: E402

THEME = {"fond": "F1F7EE", "titre": "24562F", "texte": "1F2933", "accent": "2F7D4F", "police": "Georgia"}
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)

    def generer(self, md, *args):
        (self.d / "d.md").write_text(md, encoding="utf-8")
        return subprocess.run([sys.executable, str(RACINE / "scripts/generer.py"), "pptx", "d.md", "d.pptx", "--ecraser", *args],
                              cwd=self.d, capture_output=True, text=True, encoding="utf-8")

    def diapos(self, md, *args):
        from pptx import Presentation

        r = self.generer(md, *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return Presentation(self.d / "d.pptx")

    def xml(self, chemin):
        with zipfile.ZipFile(self.d / "d.pptx") as z:
            return z.read(chemin).decode("utf-8")

    def cartes(self, diapo):
        return [s for s in diapo.shapes if s.has_text_frame and s.text_frame.text and not s.is_placeholder]


class TestDispositions(Base):
    def test_format_et_polices(self):
        prs = self.diapos("# Cours\n- Sous-titre\n")
        self.assertEqual((prs.slide_width, prs.slide_height), (12191695, 6858000))
        theme = self.xml("ppt/theme/theme1.xml")
        for attendu in ('typeface="Georgia"', 'typeface="Trebuchet MS"', design.PAPIER):
            self.assertIn(attendu, theme)

    def test_ouverture_garde_titre_et_sous_titre_editables(self):
        diapo = self.diapos("# Cours\n- Sous-titre\n").slides[0]
        self.assertEqual(diapo.shapes.title.text_frame.text, "Cours")
        self.assertEqual(diapo.placeholders[1].text_frame.text, "Sous-titre")

    def test_puces_courtes_en_cartes(self):
        prs = self.diapos("# Un\n\n# Deux\n- Idée une\n- Idée **deux**\n- Idée trois\n")
        cartes = self.cartes(prs.slides[1])
        self.assertEqual([c.text_frame.text for c in cartes], ["Idée une", "Idée deux", "Idée trois"])
        self.assertEqual(len(list(prs.slides[1].placeholders)), 1)
        self.assertTrue(any(c.rotation for c in cartes))
        self.assertTrue(all(c.left + c.width <= prs.slide_width and c.top + c.height <= prs.slide_height for c in cartes))
        self.assertEqual(self.xml("ppt/slides/slide2.xml").count('b="1"') >= 2, True)

    def test_passe_en_liste_quand_les_cartes_ne_conviennent_pas(self):
        cas = {"trop de puces": "- A\n- B\n- C\n- D\n- E\n", "texte trop long": "- " + "mot " * 800 + "\n"}
        for nom, puces in cas.items():
            with self.subTest(nom):
                prs = self.diapos(f"# Un\n\n# Deux\n{puces}")
                self.assertEqual(self.cartes(prs.slides[1]), [])
                self.assertIn(puces.split()[1], prs.slides[1].placeholders[1].text_frame.text)

    def test_sous_puces_sur_la_carte_de_leur_idee(self):
        cartes = self.cartes(self.diapos("# Un\n\n# Deux\n- Court terme\n  - Taille limitée\n- Long terme\n  - Fichiers\n").slides[1])
        self.assertEqual([c.text_frame.text for c in cartes], ["Court terme\nTaille limitée", "Long terme\nFichiers"])
        ligne, detail = cartes[0].text_frame.paragraphs
        self.assertLess(detail.runs[0].font.size, ligne.runs[0].font.size)

    def test_le_texte_court_remplit_sa_carte(self):
        from pptx.util import Pt

        cartes = self.cartes(self.diapos("# Un\n\n# Deux\n- Idée\n- Autre\n").slides[1])
        self.assertEqual(cartes[0].text_frame.paragraphs[0].runs[0].font.size, Pt(44))

    def test_un_mot_long_ne_se_coupe_pas_sur_une_carte_etroite(self):
        from pptx.util import Pt

        cartes = self.cartes(self.diapos("# Un\n\n# Deux\n- Couche délibérative\n- Le planificateur\n- Explosion combinatoire\n").slides[1])
        taille = cartes[0].text_frame.paragraphs[0].runs[0].font.size
        largeur_utile = (cartes[0].width - 2 * cartes[0].text_frame.margin_left) / 12700
        self.assertLessEqual(len("combinatoire") * taille.pt * .62, largeur_utile)
        # Le texte reste grand : les cartes passent en lignes plutôt que de le rapetisser.
        self.assertGreaterEqual(taille, Pt(32))

    def test_quatre_cartes_dans_le_cadre(self):
        prs = self.diapos("# Un\n\n# Deux\n- A\n- B\n- C\n- D\n")
        cartes = self.cartes(prs.slides[1])
        self.assertEqual(len(cartes), 4)
        self.assertTrue(all(c.left + c.width <= prs.slide_width and c.top + c.height <= prs.slide_height for c in cartes))

    def test_diapo_d_activite(self):
        for titre in ("À vous !", "Activité : classer", "Exercice 1", "Atelier"):
            with self.subTest(titre):
                prs = self.diapos(f"# Un\n\n# {titre}\n- Par deux, **expliquez**\n")
                diapo = prs.slides[1]
                self.assertEqual(diapo.shapes.title.text_frame.text, titre)
                self.assertIn("Par deux, expliquez", [s.text_frame.text for s in self.cartes(diapo)])
                self.assertIn("<p:bg>", self.xml("ppt/slides/slide2.xml"))

    def test_titre_seul_sans_zone_vide(self):
        self.assertEqual(len(list(self.diapos("# Un\n\n# Deux\n").slides[1].placeholders)), 1)

    def test_image_a_cote_des_cartes(self):
        from pptx.enum.shapes import MSO_SHAPE_TYPE
        from pptx.util import Inches

        (self.d / "i.png").write_bytes(PNG)
        prs = self.diapos("# Un\n\n# Deux\n- Texte\n![x](i.png)\n")
        image = next(s for s in prs.slides[1].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE)
        self.assertGreaterEqual(image.left, Inches(4.5))
        self.assertLessEqual(image.left + image.width, prs.slide_width)
        self.assertLessEqual(image.top + image.height, prs.slide_height)


class TestDessins(Base):
    SCHEMA = ("@dessin: sol 80\n@dessin: plante 50 80 1\n@dessin: soleil 85 15 1\n@dessin: fleche 10 20 40 45 rouge\n"
              "@dessin: trait 5 5 20 5 bleu\n@dessin: cercle 20 70 5 jaune\n@dessin: rect 60 60 90 75 vert\n@dessin: etiquette 2 10 rouge CO₂ entre\n")

    def test_dessin_groupe_et_dans_le_cadre(self):
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        prs = self.diapos(f"# Un\n\n# Deux\n{self.SCHEMA}- Idée\n")
        groupe = next(s for s in prs.slides[1].shapes if s.shape_type == MSO_SHAPE_TYPE.GROUP)
        self.assertGreater(len(list(groupe.shapes)), 10)
        self.assertLessEqual(groupe.left + groupe.width, prs.slide_width + 200000)
        self.assertLessEqual(groupe.top + groupe.height, prs.slide_height + 200000)

    def test_etiquette_lisible_par_recherche_et_modification(self):
        sys.path.insert(0, str(RACINE / "scripts"))
        import modifier

        self.diapos(f"# Un\n\n# Deux\n{self.SCHEMA}")
        donnees = (self.d / "d.pptx").read_bytes()
        self.assertIn("CO₂ entre", [t for _, t in modifier.paragraphes(donnees, ".pptx")])
        nouveau, nombre = modifier.remplacer(donnees, ".pptx", "CO₂ entre", "CO₂ arrive")
        self.assertEqual(nombre, 1)
        self.assertIn("CO₂ arrive", [t for _, t in modifier.paragraphes(nouveau, ".pptx")])

    def test_lignes_de_dessin_absentes_du_texte(self):
        self.diapos(f"# Un\n\n# Deux\n{self.SCHEMA}- Idée\n")
        self.assertNotIn("@dessin", self.xml("ppt/slides/slide2.xml"))

    def test_dessin_invalide_refuse_sans_creer_de_fichier(self):
        cas = {"élément inconnu": "@dessin: licorne 1 2 3", "doit être entre": "@dessin: plante 150 20 1", "attend 3 valeurs": "@dessin: plante 10",
               "n'est pas un nombre": "@dessin: soleil a b 1", "couleur inconnue": "@dessin: fleche 1 2 3 4 violet", "doit être entre 0.3 et 2": "@dessin: plante 1 2 9",
               "plus de 60 caractères": "@dessin: etiquette 1 2 rouge " + "x" * 61, "écrire : etiquette": "@dessin: etiquette 1 2 rouge", "nan": "@dessin: plante nan 2 1"}
        for attendu, ligne in cas.items():
            with self.subTest(attendu):
                r = self.generer(f"# Un\n\n# Deux\n{ligne}\n")
                self.assertNotEqual(r.returncode, 0, ligne)
                self.assertFalse((self.d / "d.pptx").exists())
                if attendu != "nan":
                    self.assertIn(attendu, r.stderr)

    def test_trop_d_elements_ou_activite_refuses(self):
        self.assertIn("plus de 30", self.generer("# Un\n\n# Deux\n" + "@dessin: sol 80\n" * 31).stderr)
        self.assertIn("diapo d'activité", self.generer("# Un\n\n# À vous\n@dessin: sol 80\n").stderr)

    def test_le_controle_lit_les_etiquettes_mais_pas_les_coordonnees(self):
        sys.path.insert(0, str(RACINE / "tests"))
        import fixtures
        import qualite

        dessin = "# Le système digestif\n@dessin: plante 50 80 1\n@dessin: fleche 10 20 40 45 rouge\n@dessin: etiquette 2 10 rouge Le chercheur Beaumont\n- Les aliments deviennent des nutriments\n> Objectif : OBJ1\n"
        fixtures.ecrire_chapitre(self.d, seance_1__diapos=dessin)
        problemes = [c["problem"] for c in qualite.construire_rapport(self.d, "livrables")["constats"] if c["category"] == "hallucination"]
        self.assertEqual(problemes, ["« Beaumont » n'apparaît pas dans le cours d'origine."])


class TestThemes(Base):
    def avec_theme(self, theme, md="# Un\n\n# Partie\n@theme: t\n- Idée\n\n# Autre\n- Texte\n"):
        (self.d / "t.json").write_text(json.dumps({"t": theme}), encoding="utf-8")
        return self.generer(md, "--themes", "t.json")

    def test_couleurs_sur_une_seule_diapo(self):
        self.assertEqual(self.avec_theme(THEME).returncode, 0)
        self.assertIn("F1F7EE", self.xml("ppt/slides/slide2.xml"))
        self.assertNotIn("F1F7EE", self.xml("ppt/slides/slide3.xml"))

    def test_theme_illisible_ou_invalide_refuse(self):
        cas = {"« texte » est illisible": {"texte": "EEF5EA"}, "« titre » est illisible": {"titre": "E8EFE4"}, "doit être une couleur": {"fond": "vert"},
               "police inconnue": {"police": "Comic Sans MS"}, "le blanc du titre": {"accent": "F4C542"}, "une carte": {"fond": "101010", "texte": "FFFFFF", "titre": "FFFFFF"}}
        for attendu, changement in cas.items():
            with self.subTest(attendu):
                (self.d / "d.pptx").unlink(missing_ok=True)
                r = self.avec_theme({**THEME, **changement})
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(attendu, r.stderr)
                self.assertFalse((self.d / "d.pptx").exists())

    def test_theme_inconnu_ou_fichier_casse(self):
        self.assertIn("Thème inconnu : absent", self.generer("# Un\n@theme: absent\n").stderr)
        (self.d / "t.json").write_text("{pas du json", encoding="utf-8")
        self.assertIn("illisible", self.generer("# Un\n", "--themes", "t.json").stderr)
        self.assertIn("introuvable", self.generer("# Un\n", "--themes", "absent.json").stderr)


class TestModele(Base):
    def test_modele_d_etablissement_garde_son_apparence(self):
        from pptx import Presentation

        modele = Presentation()
        modele.save(self.d / "modele.pptx")
        prs = self.diapos("# Un\n@theme: absent\n@dessin: licorne\n\n# À vous\n- Consigne\n", "--modele", "modele.pptx")
        self.assertEqual(prs.slide_width, modele.slide_width)
        self.assertEqual(prs.slides[1].placeholders[1].text_frame.text, "Consigne")
        self.assertNotIn("<p:bg>", self.xml("ppt/slides/slide2.xml"))
        with zipfile.ZipFile(self.d / "modele.pptx") as z:
            self.assertEqual(z.read("ppt/theme/theme1.xml").decode("utf-8"), self.xml("ppt/theme/theme1.xml"))


class TestContraste(unittest.TestCase):
    def test_valeurs_connues(self):
        self.assertAlmostEqual(design.contraste("000000", "FFFFFF"), 21)
        self.assertAlmostEqual(design.contraste("777777", "777777"), 1)

    def test_le_style_de_base_est_lisible(self):
        self.assertEqual(design.verifier_theme("base", design.BASE), [])


if __name__ == "__main__":
    unittest.main()
