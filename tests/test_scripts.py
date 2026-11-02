"""Vérifie les scripts du plugin : python -m unittest discover tests (python-pptx et python-docx requis)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
DIAPOS = "# Mon cours\n> Bonjour\n\n# Partie 1\n- Idée A\n  - Détail\n> Note secrète\n"


def lancer(script, *args, dossier):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=dossier,
                          capture_output=True, text=True, encoding="utf-8")


class TestScripts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)

    def test_pptx_et_extraction(self):
        (self.d / "d.md").write_text(DIAPOS, encoding="utf-8")
        self.assertEqual(lancer("generer.py", "pptx", "d.md", "d.pptx", dossier=self.d).returncode, 0)
        texte = lancer("extraire_texte.py", "d.pptx", dossier=self.d).stdout
        for attendu in ("Mon cours", "Partie 1", "Idée A", "Détail", "Note secrète"):
            self.assertIn(attendu, texte)

    def test_modele_remplace_les_diapos_exemple(self):
        from pptx import Presentation

        (self.d / "d.md").write_text(DIAPOS, encoding="utf-8")
        lancer("generer.py", "pptx", "d.md", "modele.pptx", dossier=self.d)
        r = lancer("generer.py", "pptx", "d.md", "s.pptx", "--modele", "modele.pptx", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(Presentation(self.d / "s.pptx").slides), 2)

    def test_docx_et_extraction(self):
        (self.d / "e.md").write_text("# Sujet\n## Question 1\n- Choix A\nTexte libre\n", encoding="utf-8")
        self.assertEqual(lancer("generer.py", "docx", "e.md", "e.docx", dossier=self.d).returncode, 0)
        texte = lancer("extraire_texte.py", "e.docx", dossier=self.d).stdout
        for attendu in ("Sujet", "Question 1", "Choix A", "Texte libre"):
            self.assertIn(attendu, texte)

    def test_extraction_odt(self):
        import zipfile

        xml = ('<d xmlns:t="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
               '<t:h>Titre</t:h><t:p>Un <t:span>texte</t:span></t:p></d>')
        with zipfile.ZipFile(self.d / "c.odt", "w") as z:
            z.writestr("content.xml", xml)
        self.assertEqual(lancer("extraire_texte.py", "c.odt", dossier=self.d).stdout.split("\n")[:2],
                         ["Titre", "Un texte"])

    def test_refuse_decraser_sans_demande(self):
        (self.d / "d.md").write_text(DIAPOS, encoding="utf-8")
        (self.d / "d.pptx").write_text("retouché", encoding="utf-8")
        self.assertNotEqual(lancer("generer.py", "pptx", "d.md", "d.pptx", dossier=self.d).returncode, 0)
        self.assertEqual((self.d / "d.pptx").read_text(encoding="utf-8"), "retouché")

    def test_sauver_et_restaurer(self):
        f = self.d / "diapos.pptx"
        f.write_text("v1", encoding="utf-8")
        self.assertEqual(lancer("versions.py", "sauver", "un", dossier=self.d).returncode, 0)
        version = lancer("versions.py", "historique", dossier=self.d).stdout.split()[0]
        f.write_text("v2 non sauvegardée", encoding="utf-8")
        r = lancer("versions.py", "restaurer", version, "diapos.pptx", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(f.read_text(encoding="utf-8"), "v1")
        # La v2 reste récupérable : c'est toute la promesse de la restauration.
        histo = lancer("versions.py", "historique", dossier=self.d).stdout
        avant = next(l.split()[0] for l in histo.splitlines() if "Avant le retour" in l)
        lancer("versions.py", "restaurer", avant, "diapos.pptx", dossier=self.d)
        self.assertEqual(f.read_text(encoding="utf-8"), "v2 non sauvegardée")

    def test_image_gras_et_zone_vide(self):
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        # PNG 1x1 valide : évite de versionner une image pour le test.
        png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                            "1f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")
        (self.d / "i.png").write_bytes(png)
        (self.d / "d.md").write_text("# Un\n# Deux\n- Mot **fort**\n![x](i.png)\n# Trois\n![x](i.png)\n# Quatre\n",
                                     encoding="utf-8")
        r = lancer("generer.py", "pptx", "d.md", "d.pptx", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        prs = Presentation(self.d / "d.pptx")
        for diapo in list(prs.slides)[1:3]:
            images = [s for s in diapo.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
            self.assertEqual(len(images), 1)
            self.assertLessEqual(images[0].left + images[0].width, prs.slide_width)
            self.assertLessEqual(images[0].top + images[0].height, prs.slide_height)
        runs = list(prs.slides[1].placeholders[1].text_frame.paragraphs[0].runs)
        self.assertEqual([(r.text, r.font.bold) for r in runs], [("Mot ", None), ("fort", True)])
        self.assertEqual(len(list(prs.slides[3].placeholders)), 1)

    def test_image_absente_ne_cree_pas_de_fichier(self):
        (self.d / "d.md").write_text("# Un\n![x](absente.png)\n", encoding="utf-8")
        r = lancer("generer.py", "pptx", "d.md", "d.pptx", dossier=self.d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("absente.png", r.stderr)
        self.assertFalse((self.d / "d.pptx").exists())

    def test_docx_tableau_liste_et_lignes_reponse(self):
        from docx import Document

        (self.d / "e.md").write_text(
            "# Sujet\n1. Première\n[réponse: 3]\n\n| A | B |\n|---|---|\n| **1** | 2 |\n\nFin\n", encoding="utf-8")
        r = lancer("generer.py", "docx", "e.md", "e.docx", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = Document(self.d / "e.docx")
        textes = [p.text for p in doc.paragraphs]
        self.assertEqual(sum(t.startswith("___") for t in textes), 3)
        self.assertIn("Première", textes)
        self.assertEqual(textes[-1], "Fin")
        table = doc.tables[0]
        self.assertEqual((len(table.rows), table.cell(1, 0).text), (2, "1"))
        self.assertTrue(table.cell(1, 0).paragraphs[0].runs[0].bold)

    def test_comparer_versions_pptx(self):
        (self.d / "d.md").write_text("# Titre\n- Ancienne idée\n", encoding="utf-8")
        lancer("generer.py", "pptx", "d.md", "d.pptx", dossier=self.d)
        lancer("versions.py", "sauver", "un", dossier=self.d)
        version = lancer("versions.py", "historique", dossier=self.d).stdout.split()[0]
        (self.d / "d.md").write_text("# Titre\n- Nouvelle idée\n", encoding="utf-8")
        lancer("generer.py", "pptx", "d.md", "d.pptx", "--ecraser", dossier=self.d)
        r = lancer("versions.py", "comparer", version, "d.pptx", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Retiré : Ancienne idée", r.stdout)
        self.assertIn("Ajouté : Nouvelle idée", r.stdout)

    def ecrire_cours(self, **remplacements):
        fichiers = {
            "objectifs.md": "Durée : 30 min\n- O1 : définir\n- O2 : identifier\n",
            "scenario.md": "## 0-10 min — A\n- O1\n## 10-30 min — B\n- O2\n",
            "diapos.md": "# Un\n- x\n> Objectif : O1\n> Objectif : O2\n",
            "evaluation.md": "Total : 10 points\n## Q1 (4 points)\n## Q2 (6 points)\n",
            "corrige.md": "Q1 : O1\nQ2 : O2\n",
        }
        fichiers.update(remplacements)
        for nom, texte in fichiers.items():
            (self.d / nom).write_text(texte, encoding="utf-8")

    def test_controle_cours_coherent(self):
        self.ecrire_cours()
        r = lancer("controler.py", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("Barème : 10 points", r.stdout)

    def test_controle_detecte_les_problemes(self):
        cas = {
            "O2 n'est pas couvert dans corrige.md": {"corrige.md": "Q1 : O1\n"},
            "cite O9": {"corrige.md": "Q1 : O1\nQ2 : O2\nQ3 : O9\n"},
            "attendu un début à 10": {"scenario.md": "## 0-10 min\n- O1\n## 15-30 min\n- O2\n"},
            "annonce 30 min": {"scenario.md": "## 0-10 min\n- O1\n## 10-25 min\n- O2\n"},
            "totalisent 9 points": {"evaluation.md": "Total : 10 points\n## Q1 (4 points)\n## Q2 (5 points)\n"},
            "7 puces": {"diapos.md": "# Un\n> O1 O2\n" + "- x\n" * 7},
        }
        for attendu, remplacement in cas.items():
            with self.subTest(attendu):
                self.ecrire_cours(**remplacement)
                r = lancer("controler.py", dossier=self.d)
                self.assertEqual(r.returncode, 1)
                self.assertIn(attendu, r.stdout)

    def test_exemple_du_depot_est_coherent(self):
        exemple = Path(__file__).resolve().parent.parent / "exemples" / "photosynthese"
        r = lancer("controler.py", str(exemple), dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_version_invalide_refusee(self):
        (self.d / "a.txt").write_text("x", encoding="utf-8")
        lancer("versions.py", "sauver", "un", dossier=self.d)
        self.assertNotEqual(lancer("versions.py", "restaurer", "--force", "a.txt", dossier=self.d).returncode, 0)

    def test_ignore_les_fichiers_verrou(self):
        (self.d / "a.txt").write_text("x", encoding="utf-8")
        (self.d / ".~lock.a.odp#").write_text("verrou", encoding="utf-8")
        (self.d / "~$a.pptx").write_text("verrou", encoding="utf-8")
        lancer("versions.py", "sauver", "un", dossier=self.d)
        suivis = subprocess.run(["git", "ls-files"], cwd=self.d, capture_output=True, text=True).stdout
        self.assertNotIn("lock", suivis)
        self.assertNotIn("~$", suivis)


if __name__ == "__main__":
    unittest.main()
