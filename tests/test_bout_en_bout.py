"""Vérifie que toutes les étapes communiquent, de la source au document final, avec des agents simulés."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
for dossier in ("benchmark", "benchmark/fixtures", "scripts"):
    sys.path.insert(0, str(RACINE / dossier))

import modele  # noqa: E402
import parcours_mock  # noqa: E402


class TestParcours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = Path(cls.tmp.name)
        cls.etapes = []
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            cls.resultat = parcours_mock.executer(cls.d, cls.etapes.append)
        cls.rapport = cls.resultat["rapport"]
        cls.qualite = json.loads((cls.d / ".travail/revue/quality_report.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_toutes_les_etapes_sont_jouees_dans_l_ordre(self):
        titres = [e.strip().split(" ")[0] for e in self.etapes if e.strip().startswith("[")]
        self.assertEqual(titres, [f"[{i}/8]" for i in range(1, 9)])

    def test_source_conservee(self):
        self.assertTrue((self.d / "Cours/digestion.txt").is_file())

    def test_critique_declenche_une_revision_puis_la_validation(self):
        self.assertEqual(self.resultat["decisions"][0], "DECISION: REVISION 1/2")
        self.assertEqual(self.resultat["decisions"][1], "DECISION: VALIDATION_HUMAINE")

    def test_revision_oblige_une_nouvelle_critique(self):
        self.assertTrue(any("CRITIQUE_REQUISE (critique obsolète)" in e for e in self.etapes))

    def test_le_code_seul_ne_voyait_pas_l_erreur_de_sens(self):
        self.assertTrue(any("0 problème bloquant" in e for e in self.etapes))

    def test_quality_report_final(self):
        self.assertEqual(self.qualite["status"], "HUMAN_VALIDATED")
        self.assertEqual(self.qualite["critic"], "ok")
        self.assertEqual(self.qualite["overall_score"], 100)
        self.assertEqual(self.qualite["critical_issues"], [])

    def test_revisions_et_validations_tracees(self):
        self.assertEqual(self.qualite["revisions"]["count"], 1)
        self.assertEqual([(h["critical"], h["decision"]) for h in self.qualite["revisions"]["history"] if h["stage"] == "livrables"],
                         [(1, "REVISION 1/2"), (0, "HUMAN_VALIDATION")])
        self.assertEqual([(e["stage"], e["action"]) for e in self.qualite["human_interventions"]["events"]],
                         [("decoupage", "approve"), ("livrables", "approve")])

    def test_modele_relie_l_objectif_a_l_evaluation(self):
        m = json.loads((self.d / modele.FICHIER).read_text(encoding="utf-8"))
        self.assertEqual(modele.verifier_modele(m), [])
        self.assertTrue(all(t["status"] == modele.COMPLET for t in m["traceability"].values()))

    def test_documents_finaux_lisibles_et_corriges(self):
        from docx import Document
        from pptx import Presentation

        self.assertIn("Diapos/seance-1-diapos.pptx", self.resultat["documents"])
        self.assertEqual(len(self.resultat["documents"]), 8)
        self.assertGreater(len(Presentation(self.d / "Diapos/seance-1-diapos.pptx").slides), 0)
        texte = " ".join(p.text for p in Document(self.d / "Corrections/seance-1-qcm-corrige.docx").paragraphs)
        self.assertIn("Question 1 : A", texte)
        self.assertNotIn("Question 1 : B", texte)


class TestCommande(unittest.TestCase):
    def test_exemple_annonce_qu_il_est_simule(self):
        r = subprocess.run([sys.executable, str(RACINE / "benchmark/parcours_mock.py")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        for attendu in ("EXEMPLE SIMULÉ", "[8/8]", "QUALITY REPORT", "STATUS: HUMAN_VALIDATED"):
            self.assertIn(attendu, r.stdout)

    def test_refuse_un_dossier_non_vide(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "fichier").touch()
            r = subprocess.run([sys.executable, str(RACINE / "benchmark/parcours_mock.py"), tmp], capture_output=True, text=True, encoding="utf-8")
            self.assertIn("n'est pas vide", r.stderr)


if __name__ == "__main__":
    unittest.main()
