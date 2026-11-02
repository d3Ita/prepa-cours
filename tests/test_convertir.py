"""Vérifie le choix du format de sortie, avec un faux LibreOffice : aucun logiciel réel n'est nécessaire."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import convertir  # noqa: E402
import fixtures  # noqa: E402
import modifier  # noqa: E402
import redaction  # noqa: E402
from controler import controler  # noqa: E402

FAUX_SOFFICE = """
import sys
from pathlib import Path
a = sys.argv[1:]
if "ECHEC" in Path(a[-1]).parent.as_posix() or Path("echec.txt").exists():
    print("erreur simulée", file=sys.stderr)
    sys.exit(2)
format_ = a[a.index("--convert-to") + 1]
sortie = Path(a[a.index("--outdir") + 1]) / (Path(a[-1]).stem + "." + format_)
sortie.write_bytes(b"converti depuis " + Path(a[-1]).read_bytes()[:2])
"""


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name).resolve()
        faux = self.d / "faux_soffice.py"
        faux.write_text(FAUX_SOFFICE, encoding="utf-8")
        self.env = {**os.environ, "PREPA_COURS_SOFFICE": f'"{sys.executable}" "{faux}"'.replace("\\", "/")}
        (self.d / "d.md").write_text("# Titre\n- Idée\n", encoding="utf-8")

    def generer(self, format_source, sortie, *args, env=None):
        return subprocess.run([sys.executable, str(RACINE / "scripts/generer.py"), format_source, "d.md", sortie, *args],
                              cwd=self.d, capture_output=True, text=True, encoding="utf-8", env=env or self.env)


class TestLireFormat(unittest.TestCase):
    def test_valeurs_valides(self):
        for valeur, source, attendu in (("odp", "pptx", "odp"), (".PDF", "docx", "pdf"), ("key", "pptx", "key"), ("odt", "docx", "odt"), ("pptx", "pptx", None), ("DOCX", "docx", None)):
            self.assertEqual(convertir.lire_format(valeur, source), attendu, valeur)

    def test_reglage_absent_garde_le_defaut(self):
        for valeur in (None, "", "${user_config.format_diapos}"):
            self.assertIsNone(convertir.lire_format(valeur, "pptx"))

    def test_format_incoherent_refuse(self):
        for valeur, source in (("odt", "pptx"), ("key", "docx"), ("exe", "pptx"), ("../x", "docx")):
            with self.assertRaises(SystemExit):
                convertir.lire_format(valeur, source)


class TestGeneration(Base):
    def test_format_par_defaut_inchange(self):
        for args in ((), ("--sortie-format", "pptx"), ("--sortie-format", "${user_config.format_diapos}")):
            (self.d / "x.pptx").unlink(missing_ok=True)
            r = self.generer("pptx", "x.pptx", *args)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((self.d / "x.pptx").is_file())

    def test_odp_et_odt_remplacent_le_fichier(self):
        for source, cible, seul in (("pptx", "odp", "a.pptx"), ("docx", "odt", "b.docx")):
            with self.subTest(cible):
                r = self.generer(source, seul, "--sortie-format", cible)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue((self.d / seul).with_suffix(f".{cible}").is_file())
                self.assertFalse((self.d / seul).exists())
                self.assertIn(f"Créé : {Path(seul).with_suffix('.' + cible)}", r.stdout)

    def test_pdf_s_ajoute_au_fichier_modifiable(self):
        r = self.generer("docx", "c.docx", "--sortie-format", "pdf")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.d / "c.docx").is_file())
        self.assertTrue((self.d / "c.pdf").is_file())
        for attendu in ("Créé : c.docx", "Créé : c.pdf"):
            self.assertIn(attendu, r.stdout)

    def test_sans_libreoffice_le_fichier_reste_et_l_utilisateur_le_sait(self):
        (self.d / "echec.txt").touch()
        r = self.generer("docx", "c.docx", "--sortie-format", "odt")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.d / "c.docx").is_file())
        self.assertFalse((self.d / "c.odt").exists())
        self.assertIn("⚠ Le fichier odt n'a pas été créé", r.stdout)
        self.assertIn("c.docx est conservé", r.stdout)

    def test_programme_absent(self):
        env = {**self.env, "PREPA_COURS_SOFFICE": "programme-qui-n-existe-pas-xyz"}
        r = self.generer("docx", "c.docx", "--sortie-format", "odt", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("⚠", r.stdout)
        self.assertTrue((self.d / "c.docx").is_file())

    def test_n_ecrase_jamais_le_format_choisi_sans_demande(self):
        (self.d / "c.odt").write_text("retouché", encoding="utf-8")
        r = self.generer("docx", "c.docx", "--sortie-format", "odt")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.d / "c.odt").read_text(encoding="utf-8"), "retouché")
        self.assertEqual(self.generer("docx", "c.docx", "--sortie-format", "odt", "--ecraser").returncode, 0)
        self.assertNotEqual((self.d / "c.odt").read_text(encoding="utf-8"), "retouché")

    def test_n_ecrase_pas_le_fichier_modifiable_sans_demande(self):
        (self.d / "c.docx").write_text("retouché", encoding="utf-8")
        r = self.generer("docx", "c.docx", "--sortie-format", "pdf")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.d / "c.pdf").exists())

    def test_format_invalide_ne_cree_rien(self):
        r = self.generer("pptx", "a.pptx", "--sortie-format", "odt")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Format de sortie inconnu", r.stderr)
        self.assertFalse((self.d / "a.pptx").exists())


class TestSuitePipeline(Base):
    def test_le_controle_accepte_chaque_format(self):
        chapitre = self.d / "chapitre"
        chapitre.mkdir()
        fixtures.ecrire_chapitre(chapitre)
        self.assertEqual(controler(chapitre)[0], [])
        (chapitre / "Diapos/seance-1-diapos.pptx").rename(chapitre / "Diapos/seance-1-diapos.odp")
        (chapitre / "QCM/seance-1-qcm.docx").rename(chapitre / "QCM/seance-1-qcm.odt")
        self.assertEqual(controler(chapitre)[0], [])
        (chapitre / "QCM/seance-1-qcm.odt").unlink()
        self.assertIn("Le fichier QCM/seance-1-qcm.docx est absent.", controler(chapitre)[0])

    def test_le_controle_signale_une_ancienne_seance_dans_tout_format(self):
        chapitre = self.d / "chapitre"
        chapitre.mkdir()
        fixtures.ecrire_chapitre(chapitre)
        (chapitre / "Diapos/seance-9-diapos.odp").touch()
        self.assertIn("Diapos/seance-9-diapos.odp ne correspond", " ".join(controler(chapitre)[0]))

    def test_copies_pdf_et_key_annoncees_comme_non_verifiees(self):
        (self.d / "c.pdf").touch()
        (self.d / "c.key").touch()
        _, non_verifies = modifier.rechercher("x", self.d)
        self.assertLessEqual({"c.pdf", "c.key"}, set(non_verifies))

    def test_cours_redige_en_odt_suivi_et_valide(self):
        chapitre = self.d / "chapitre"
        (chapitre / ".travail/revue").mkdir(parents=True)
        (chapitre / redaction.BROUILLON).write_text("# Cours\nTexte\n", encoding="utf-8")
        (chapitre / redaction.COURS_ODT).parent.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=chapitre, check=True)
        env = self.env
        r = subprocess.run([sys.executable, str(RACINE / "scripts/redaction.py"), "produire", str(chapitre), "--sortie-format", "odt"],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(redaction.chemin_cours(chapitre), chapitre / redaction.COURS_ODT)
        self.assertEqual(redaction.statut(chapitre), "en_cours")
        ancien = redaction.empreinte(chapitre)
        (chapitre / redaction.COURS_ODT).write_bytes(b"retouche")
        self.assertNotEqual(redaction.empreinte(chapitre), ancien)

    def test_cours_pdf_reste_un_docx_modifiable(self):
        chapitre = self.d / "chapitre"
        (chapitre / ".travail/revue").mkdir(parents=True)
        (chapitre / redaction.BROUILLON).write_text("# Cours\nTexte\n", encoding="utf-8")
        (chapitre / "Cours").mkdir()
        subprocess.run(["git", "init", "-q"], cwd=chapitre, check=True)
        r = subprocess.run([sys.executable, str(RACINE / "scripts/redaction.py"), "produire", str(chapitre), "--sortie-format", "pdf"],
                           capture_output=True, text=True, encoding="utf-8", env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(redaction.chemin_cours(chapitre), chapitre / redaction.COURS)

    def test_reglages_declares_dans_le_plugin(self):
        manifeste = json.loads((RACINE / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifeste["userConfig"]["format_diapos"]["options"], list(convertir.FORMATS["pptx"]))
        self.assertEqual(manifeste["userConfig"]["format_documents"]["options"], list(convertir.FORMATS["docx"]))

    def test_chaque_commande_de_generation_suit_le_reglage(self):
        for nom in ("scenario", "qcm", "evaluation", "diapos"):
            for ligne in (RACINE / "skills" / nom / "SKILL.md").read_text(encoding="utf-8").splitlines():
                if 'scripts/generer.py"' in ligne:
                    self.assertIn("--sortie-format", ligne, nom)


if __name__ == "__main__":
    unittest.main()
