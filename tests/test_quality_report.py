"""Vérifie le quality report, la complétude, les révisions et les interventions humaines."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixtures  # noqa: E402
import qualite  # noqa: E402
import redaction  # noqa: E402
from fixtures import constat, ecrire_chapitre, ecrire_critique, vieillir_revue  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)

    def rapport(self, etape="livrables"):
        qualite.construire_rapport(self.d, etape)
        return json.loads((self.d / ".travail/revue/quality_report.json").read_text(encoding="utf-8"))


class TestRapport(Base):
    def test_contient_tous_les_champs_demandes(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d)
        q = self.rapport()
        for champ in ("overall_score", "accuracy_score", "objective_coverage_score", "pedagogical_coherence_score", "timing_score",
                      "evaluation_score", "content_completeness_score", "critical_issues", "warnings", "infos", "objective_coverage"):
            self.assertIn(champ, q)
        self.assertEqual(q["overall_score"], 100)
        self.assertEqual(q["objective_coverage"][0]["id"], "OBJ-001")
        self.assertEqual(q["objective_coverage"][0]["status"], "COMPLETE")

    def test_chaque_score_indique_sa_methode_et_ses_explications(self):
        ecrire_chapitre(self.d, seance_1__scenario="## 0-77 min — A\n- OBJ1\n")
        ecrire_critique(self.d)
        q = self.rapport()
        self.assertEqual(q["score_details"]["objective_coverage_score"]["method"], "deterministic")
        self.assertEqual(q["score_details"]["accuracy_score"]["method"], "deterministic+llm_critic")
        self.assertIn("77 min", " ".join(q["score_details"]["timing_score"]["explanation"]))

    def test_sans_critique_rien_n_est_presente_comme_evalue_par_elle(self):
        ecrire_chapitre(self.d)
        q = self.rapport()
        self.assertTrue(q["partial"])
        self.assertIsNone(q["accuracy_score"])
        self.assertEqual(q["score_details"]["accuracy_score"]["method"], "not_evaluated")
        self.assertEqual(q["score_details"]["timing_score"]["method"], "deterministic")

    def test_problemes_tries_par_gravite(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat("critical", "factual", problem="A"), constat("warning", "timing", problem="B"),
                                          constat("info", "pedagogical", problem="C")])
        q = self.rapport()
        self.assertEqual([[c["problem"] for c in q[k]] for k in ("critical_issues", "warnings", "infos")], [["A"], ["B"], ["C"]])

    def test_affichage(self):
        ecrire_chapitre(self.d)
        r = subprocess.run([sys.executable, str(RACINE / "scripts/qualite.py"), "quality-report", str(self.d)],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        for attendu in ("QUALITY REPORT", "Overall:", "Accuracy: not evaluated [not_evaluated]",
                        "Objective coverage: 100 [deterministic]", "Critical issues: 0", "Revisions: 0", "Human interventions: 0"):
            self.assertIn(attendu, r.stdout)

    def test_modele_ecrit_avec_le_rapport(self):
        ecrire_chapitre(self.d)
        self.rapport()
        self.assertTrue((self.d / ".travail/revue/course_model.json").is_file())


class TestCompletude(Base):
    def test_cours_complet(self):
        ecrire_chapitre(self.d)
        self.assertEqual(qualite.mesurer_completude(self.d, "livrables"), (100, []))

    def test_notion_oubliee(self):
        ecrire_chapitre(self.d, objectifs=fixtures.OBJECTIFS.replace("sucs digestifs", "bile"))
        score, constats = qualite.mesurer_completude(self.d, "livrables")
        self.assertLess(score, 100)
        self.assertIn("La notion « bile » n'apparaît dans aucun document produit.", [c["problem"] for c in constats])

    def test_section_du_cours_oubliee(self):
        ecrire_chapitre(self.d)
        (self.d / "Cours/cours.txt").write_text(fixtures.COURS + "\n## Le foie et la vésicule\nLa bile.\n", encoding="utf-8")
        _, constats = qualite.mesurer_completude(self.d, "livrables")
        self.assertIn("La section « Le foie et la vésicule » du cours n'apparaît pas dans les documents produits.", [c["problem"] for c in constats])

    def test_fichier_absent(self):
        ecrire_chapitre(self.d)
        (self.d / ".travail/seance-1/qcm.md").unlink()
        self.assertLess(qualite.mesurer_completude(self.d, "livrables")[0], 100)

    def test_pas_mesuree_au_decoupage(self):
        ecrire_chapitre(self.d)
        self.assertEqual(qualite.mesurer_completude(self.d, "decoupage"), (None, []))
        self.assertIsNone(self.rapport("decoupage")["content_completeness_score"])


class TestRevisions(Base):
    def test_historique_et_compteur(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat("critical", "factual", problem="Un"), constat("warning", "timing", problem="Deux")])
        self.assertEqual(qualite.decider(self.d, "livrables", 2), "DECISION: REVISION 1/2")
        ecrire_critique(self.d, constats=[constat("warning", "timing", problem="Deux")])
        self.assertEqual(qualite.decider(self.d, "livrables", 2), "DECISION: REVISION 2/2")
        ecrire_critique(self.d)
        self.assertEqual(qualite.decider(self.d, "livrables", 2), "DECISION: VALIDATION_HUMAINE")
        q = self.rapport()
        self.assertEqual(q["revisions"]["count"], 2)
        self.assertEqual([(h["issues"], h["critical"], h["decision"]) for h in q["revisions"]["history"]],
                         [(2, 1, "REVISION 1/2"), (1, 0, "REVISION 2/2"), (0, 0, "HUMAN_VALIDATION")])

    def test_limite_tracee_sans_compter_de_revision_en_plus(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat()])
        qualite.decider(self.d, "livrables", 0)
        q = self.rapport()
        self.assertEqual(q["revisions"]["count"], 0)
        self.assertEqual(q["revisions"]["history"][0]["decision"], "REVISION_LIMIT_REACHED")

    def test_relancer_ne_perd_pas_le_compte(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat()])
        qualite.decider(self.d, "livrables", 1)
        qualite.valider(self.d, "livrables", "relancer")
        self.assertEqual(self.rapport()["revisions"]["count"], 1)

    def test_critique_requise_ne_compte_pas(self):
        ecrire_chapitre(self.d)
        qualite.decider(self.d, "livrables", 2)
        self.assertEqual(self.rapport()["revisions"]["history"], [])


class TestInterventions(Base):
    def test_toutes_les_decisions_du_prof_sont_comptees(self):
        ecrire_chapitre(self.d)
        qualite.valider(self.d, "decoupage", "valider")
        qualite.valider(self.d, "scenarios", "modifier")
        qualite.valider(self.d, "livrables", "relancer")
        (self.d / ".travail/revue/modifications.json").write_text(json.dumps([{"date": "2030-01-01T00:00:00"}]), encoding="utf-8")
        redaction.ecrire_etat(self.d, {"statut": "en_cours", "validations": [{"date": "2000-01-01T00:00:00"}]})
        q = self.rapport()
        self.assertEqual(q["human_interventions"]["count"], 5)
        self.assertEqual([(e["stage"], e["action"]) for e in q["human_interventions"]["events"]],
                         [("redaction", "approve"), ("decoupage", "approve"), ("scenarios", "modify"), ("livrables", "rerun"), ("modification", "apply")])

    def test_aucune_decision_inventee(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d)
        qualite.decider(self.d, "livrables", 2)
        self.assertEqual(self.rapport()["human_interventions"], {"count": 0, "events": []})


if __name__ == "__main__":
    unittest.main()
