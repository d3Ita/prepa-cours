"""Tests de régression : chaque cas du benchmark doit provoquer exactement le comportement attendu."""
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
for dossier in ("scripts", "benchmark/fixtures", "benchmark/metrics"):
    sys.path.insert(0, str(RACINE / dossier))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cas as cas_benchmark  # noqa: E402
import fixtures  # noqa: E402
import mesures  # noqa: E402
import qualite  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)

    def chapitre(self, identifiant):
        cas = cas_benchmark.trouver(identifiant)
        cas_benchmark.materialiser(cas, self.d)
        return cas

    def verifier(self, identifiant):
        self.assertEqual(mesures.verifier_cas(self.chapitre(identifiant), self.d), [])


class TestCas(Base):
    def test_dix_cas_avec_un_resultat_attendu(self):
        self.assertEqual(len(cas_benchmark.CAS), 10)
        self.assertEqual(len({c.id for c in cas_benchmark.CAS}), 10)
        for cas in cas_benchmark.CAS:
            self.assertTrue(cas.attendu, cas.id)
            self.assertTrue((cas_benchmark.COURS / cas.cours).is_file(), cas.id)

    def test_cours_coherent(self):
        self.verifier("01_coherent")

    def test_objective_coverage(self):
        self.verifier("02_objectif_non_couvert")

    def test_timing_validation(self):
        self.verifier("03_temps_impossible")

    def test_multiple_correct_answers(self):
        self.verifier("04_plusieurs_bonnes_reponses")

    def test_answer_key_consistency(self):
        self.verifier("05_corrige_incorrect")

    def test_hallucination_detection(self):
        self.verifier("06_hallucination")

    def test_missing_content(self):
        self.verifier("07_cours_incomplet")

    def test_contradiction_detection(self):
        self.verifier("08_contradictions")

    def test_cours_tres_court(self):
        self.verifier("09_tres_court")

    def test_cours_complexe(self):
        self.verifier("10_complexe")


class TestLimitesConnues(Base):
    """Ce que le code ne sait pas détecter : la critique en a besoin, et les rapports doivent le dire."""

    def test_mauvaise_lettre_existante_non_detectee_sans_critique(self):
        cas = cas_benchmark.trouver("01_coherent")
        cas_benchmark.materialiser(cas, self.d)
        chemin = self.d / ".travail/seance-1/qcm-corrige.md"
        chemin.write_text(chemin.read_text(encoding="utf-8").replace("Question 1 : A", "Question 1 : B"), encoding="utf-8")
        self.assertEqual(qualite.construire_rapport(self.d, "livrables")["critiques"], 0)
        fixtures.ecrire_critique(self.d, constats=[fixtures.constat("critical", "evaluation", "seance-1", "Le corrigé de la question 1 est faux.")])
        rapport = qualite.construire_rapport(self.d, "livrables")
        self.assertEqual(rapport["critiques"], 1)
        self.assertEqual(rapport["statut"], "HUMAN_REVIEW_REQUIRED")

    def test_contradiction_de_sens_non_detectee_sans_critique(self):
        cas_benchmark.materialiser(cas_benchmark.trouver("01_coherent"), self.d)
        chemin = self.d / ".travail/seance-2/diapos.md"
        chemin.write_text(chemin.read_text(encoding="utf-8") + "- L'intestin grêle ne reçoit jamais de nutriments\n", encoding="utf-8")
        self.assertEqual(qualite.construire_rapport(self.d, "livrables")["critiques"], 0)


class TestMesures(Base):
    def test_valeur_non_mesuree_reste_vide(self):
        self.chapitre("01_coherent")
        m = mesures.mesurer(self.d)
        self.assertIsNone(m["generation_time"])
        self.assertIsNone(m["human_interventions"])
        self.assertIsNone(m["accuracy"])
        self.assertEqual(m["critic"], "absente")

    def test_critique_d_un_mode_ne_change_pas_les_compteurs_compares(self):
        self.chapitre("01_coherent")
        sans = mesures.mesurer(self.d)
        fixtures.ecrire_critique(self.d, constats=[fixtures.constat("critical", "factual"), fixtures.constat("warning", "hallucination", provenance="externe")])
        avec = mesures.mesurer(self.d)
        for metrique in ("critical_error_count", "warning_count", "hallucination_count", "evaluation_quality", "timing_validity"):
            self.assertEqual(avec[metrique], sans[metrique], metrique)
        self.assertEqual(avec["critic_critical_count"], 1)
        self.assertEqual(avec["accuracy"], 48)
        self.assertEqual(avec["status"], "HUMAN_REVIEW_REQUIRED")

    def test_valeurs_de_l_executeur(self):
        self.chapitre("01_coherent")
        m = mesures.mesurer(self.d, {"generation_time": 12.5, "human_interventions_recorded": True})
        self.assertEqual((m["generation_time"], m["human_interventions"]), (12.5, 0))

    def test_mesures_reproductibles(self):
        self.chapitre("03_temps_impossible")
        self.assertEqual(mesures.mesurer(self.d), mesures.mesurer(self.d))

    def test_toutes_les_metriques_ont_une_methode(self):
        self.chapitre("01_coherent")
        for colonne in mesures.COLONNES:
            self.assertIn(colonne, mesures.mesurer(self.d))

    def test_agregat_ignore_les_valeurs_absentes_et_les_echecs(self):
        ligne = {c: None for c in mesures.COLONNES}
        lignes = [{**ligne, "case": "a", "run_status": "completed", "objective_coverage": 100, "timing_validity": True},
                  {**ligne, "case": "b", "run_status": "completed", "objective_coverage": 50, "timing_validity": False},
                  {**ligne, "case": "c", "run_status": "failed", "objective_coverage": 0}]
        r = mesures.agreger(lignes)
        self.assertEqual((r["courses"], r["runs"], r["failed_runs"]), (3, 3, 1))
        self.assertEqual(r["objective_coverage"], {"mean": 75.0, "n": 2})
        self.assertEqual(r["timing_validity"], {"mean": 50.0, "n": 2})
        self.assertEqual(r["generation_time"], {"mean": None, "n": 0})


if __name__ == "__main__":
    unittest.main()
