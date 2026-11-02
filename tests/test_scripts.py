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
                         ["## Titre", "Un texte"])

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
        """Écrit un cours valide de deux séances ; une clé « s1_qcm » désigne seance-1/qcm.md."""
        qcm = "".join(f"## Question {i}\nÉnoncé\nA. un\nB. deux\nC. trois\nD. quatre\n" for i in range(1, 6))
        reponses = "".join(f"Question {i} : {l} (OBJ1, OBJ2)\n" for i, l in enumerate("ABCDA", 1))
        fichiers = {
            "objectifs": ("objectifs.md", "Niveau : Première\nMatière : SVT\n"
                                          "Durée totale : 2 h 30\n- OBJ1 : définir\n- OBJ2 : identifier\n\n"
                                          "Séance 1 : 1 h 30 — OBJ1\nSéance 2 : 1 h — OBJ2\n"),
        }
        for n, duree, objectif in ((1, 90, "OBJ1"), (2, 60, "OBJ2")):
            fichiers[f"s{n}_scenario"] = (f"seance-{n}/scenario.md", f"## 0-20 min — A\n- {objectif}\n## 20-{duree} min — B\n")
            fichiers[f"s{n}_diapos"] = (f"seance-{n}/diapos.md", f"# Un\n- x\n> Objectif : {objectif}\n")
            fichiers[f"s{n}_qcm"] = (f"seance-{n}/qcm.md", qcm)
            fichiers[f"s{n}_corrige"] = (f"seance-{n}/qcm-corrige.md",
                                         reponses.replace("(OBJ1, OBJ2)", f"({objectif})"))
        for cle, texte in remplacements.items():
            fichiers[cle] = (fichiers[cle][0], texte)
        for chemin, texte in fichiers.values():
            (self.d / chemin).parent.mkdir(exist_ok=True)
            (self.d / chemin).write_text(texte, encoding="utf-8")

    def test_controle_cours_coherent(self):
        self.ecrire_cours()
        r = lancer("controler.py", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("2 séance(s), 150 min", r.stdout)

    def test_controle_detecte_les_problemes(self):
        qcm_4 = "".join(f"## Question {i}\nA. un\nB. deux\nC. trois\n" for i in range(1, 5))
        qcm_5 = qcm_4 + "## Question 5\nA. un\nB. deux\nC. trois\n"
        reponses = "Question 1 : A (OBJ1)\nQuestion 2 : B\nQuestion 3 : C\nQuestion 4 : A\nQuestion 5 : B\n"
        cas = {
            "4 question(s) au lieu de 5": {"s1_qcm": qcm_4},
            "question 2 du QCM a moins": {"s1_qcm": qcm_5.replace("C. trois\n", "", 2)},
            "ne donne pas la réponse à la question 5": {"s1_corrige": reponses.replace("Question 5 : B\n", "")},
            "réponse E de la question 1": {"s1_corrige": reponses.replace("1 : A", "1 : E"), "s1_qcm": qcm_5},
            "toutes les bonnes réponses": {"s1_corrige": "".join(f"Question {i} : A (OBJ1)\n" for i in range(1, 6)),
                                           "s1_qcm": qcm_5},
            "ne doit pas citer les objectifs": {"s1_qcm": qcm_5 + "OBJ1\n"},
            "OBJ1 n'est pas couvert dans diapos.md": {"s1_diapos": "# Un\n- x\n"},
            "début attendu à 20": {"s1_scenario": "## 0-20 min\n- OBJ1\n## 25-90 min\n"},
            "dure 60 min pour une séance de 90": {"s1_scenario": "## 0-60 min\n- OBJ1\n"},
            "totalisent 150 min": {"objectifs": "Durée totale : 3 h\n- OBJ1 : a\n- OBJ2 : b\n\n"
                                                "Séance 1 : 1 h 30 — OBJ1\nSéance 2 : 1 h — OBJ2\n"},
            "OBJ2 n'est attribué": {"objectifs": "- OBJ1 : a\n- OBJ2 : b\n\nSéance 1 : 1 h 30 — OBJ1\nSéance 2 : 1 h — OBJ1\n"},
            "seance-2 ne correspond": {"objectifs": "- OBJ1 : a\n\nSéance 1 : 1 h 30 — OBJ1\n"},
            "durée illisible": {"objectifs": "- OBJ1 : a\n- OBJ2 : b\n\nSéance 1 : bientôt — OBJ1\nSéance 2 : 1 h — OBJ2\n"},
            "7 puces": {"s1_diapos": "# Un\n> OBJ1\n" + "- x\n" * 7},
        }
        for attendu, remplacement in cas.items():
            with self.subTest(attendu):
                self.ecrire_cours(**remplacement)
                r = lancer("controler.py", dossier=self.d)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(attendu, r.stdout)

    def test_controle_exige_niveau_et_matiere(self):
        self.ecrire_cours(objectifs="- OBJ1 : a\n- OBJ2 : b\n\nSéance 1 : 1 h 30 — OBJ1\nSéance 2 : 1 h — OBJ2\n")
        r = lancer("controler.py", dossier=self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("n'indique pas : niveau de la classe", r.stdout)
        self.assertIn("n'indique pas : matière", r.stdout)

    def test_molecules_non_confondues_avec_objectifs(self):
        molecules = "Le dioxygène O" + "2 et l'ozone O" + "3\n"
        qcm = "".join(f"## Question {i}\n{molecules}A. un\nB. deux\nC. trois\nD. quatre\n" for i in range(1, 6))
        self.ecrire_cours(s1_qcm=qcm)
        r = lancer("controler.py", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_formules_en_texte_dans_les_fichiers(self):
        formule = "CO₂ + H₂O, x² ≤ √2, 10⁻³, π"
        (self.d / "d.md").write_text(f"# {formule}\n- {formule}\n", encoding="utf-8")
        (self.d / "e.md").write_text(f"{formule}\n", encoding="utf-8")
        self.assertEqual(lancer("generer.py", "pptx", "d.md", "d.pptx", dossier=self.d).returncode, 0)
        self.assertEqual(lancer("generer.py", "docx", "e.md", "e.docx", dossier=self.d).returncode, 0)
        self.assertIn(formule, lancer("extraire_texte.py", "d.pptx", dossier=self.d).stdout)
        self.assertIn(formule, lancer("extraire_texte.py", "e.docx", dossier=self.d).stdout)

    def test_profils_de_matiere_et_niveaux_complets(self):
        racine = Path(__file__).resolve().parent.parent / "references"
        profils = {p.stem: p.read_text(encoding="utf-8") for p in (racine / "matieres").glob("*.md")}
        self.assertLessEqual({"svt", "maths", "physique-chimie", "francais", "histoire-geo", "autres"}, set(profils))
        for nom, texte in profils.items():
            for section in ("## Démarche", "## Scénario", "## Diapos", "## QCM", "## À surveiller"):
                self.assertIn(section, texte, nom)
        niveaux = (racine / "niveaux.md").read_text(encoding="utf-8")
        for niveau in ("6e", "3e", "Seconde", "Première", "Terminale", "Post-bac"):
            self.assertIn(niveau, niveaux)

    def test_controle_evaluation_finale_facultative(self):
        self.ecrire_cours()
        (self.d / "evaluation.md").write_text("Total : 10 points\n## Q (9 points)\n", encoding="utf-8")
        r = lancer("controler.py", dossier=self.d)
        self.assertIn("corrige.md est absent", r.stdout)
        self.assertIn("totalisent 9 points", r.stdout)

    def test_durees_lisibles(self):
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        from controler import minutes

        for texte, attendu in (("2 h", 120), ("1h30", 90), ("1 h 30", 90), ("1 h 30 min", 90),
                               ("2 heures", 120), ("55 min", 55), ("demain", None), ("", None)):
            self.assertEqual(minutes(texte), attendu, texte)

    def test_lecture_des_cours_texte_word_et_libreoffice(self):
        import zipfile
        from docx import Document

        doc = Document()
        doc.add_heading("Chapitre un", level=1)
        doc.add_paragraph("Texte Word")
        doc.save(self.d / "c.docx")
        self.assertEqual(lancer("extraire_texte.py", "c.docx", dossier=self.d).stdout.splitlines(),
                         ["## Chapitre un", "Texte Word"])

        with zipfile.ZipFile(self.d / "c.odt", "w") as z:
            z.writestr("content.xml", '<d xmlns:t="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
                                      "<t:h>Chapitre</t:h><t:p>Texte</t:p></d>")
        self.assertEqual(lancer("extraire_texte.py", "c.odt", dossier=self.d).stdout.splitlines(),
                         ["## Chapitre", "Texte"])

        (self.d / "utf8.txt").write_text("Séance", encoding="utf-8")
        (self.d / "windows.txt").write_bytes("Séance".encode("cp1252"))
        for nom in ("utf8.txt", "windows.txt"):
            self.assertEqual(lancer("extraire_texte.py", nom, dossier=self.d).stdout.strip(), "Séance")

    def test_ancien_format_word_explique(self):
        (self.d / "c.doc").write_bytes(b"binaire")
        r = lancer("extraire_texte.py", "c.doc", dossier=self.d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("docx, odt ou txt", r.stderr)

    def test_qcm_docx(self):
        from docx import Document

        (self.d / "q.md").write_text("# QCM\n## Question 1\nÉnoncé\nA. Un\nB. Deux\n", encoding="utf-8")
        self.assertEqual(lancer("generer.py", "docx", "q.md", "q.docx", dossier=self.d).returncode, 0)
        self.assertEqual([p.text for p in Document(self.d / "q.docx").paragraphs],
                         ["QCM", "Question 1", "Énoncé", "A. Un", "B. Deux"])

    def test_exemples_du_depot_sont_coherents(self):
        exemples = Path(__file__).resolve().parent.parent / "exemples"
        for exemple in ("photosynthese", "systemes-agentiques"):
            with self.subTest(exemple):
                r = lancer("controler.py", str(exemples / exemple), dossier=self.d)
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
