"""Vérifie le banc d'essai, avec un faux Claude : aucun test n'appelle un modèle de langage."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
for dossier in ("benchmark", "scripts", "benchmark/fixtures", "benchmark/metrics"):
    sys.path.insert(0, str(RACINE / dossier))

import cas as cas_benchmark  # noqa: E402
import run as benchmark  # noqa: E402
from runners import MULTI_AGENT, SINGLE_AGENT, ClaudeRunner, FixtureRunner  # noqa: E402

FAUX_CLAUDE = f"""
import json, os, sys
sys.path[:0] = [{str(RACINE / 'scripts')!r}, {str(RACINE / 'benchmark/fixtures')!r}]
import cas
json.dump(sys.argv[1:], open("arguments.json", "w", encoding="utf-8"))
if os.environ.get("FAUX_CLAUDE") == "echec":
    print("erreur du faux Claude", file=sys.stderr)
    sys.exit(3)
if os.environ.get("FAUX_CLAUDE") != "vide":
    cas.materialiser(cas.trouver("01_coherent"), ".")
"""


def lancer_cli(*args):
    return subprocess.run([sys.executable, str(RACINE / "benchmark/run.py"), *args], capture_output=True, text=True, encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)
        self.sorties, self.rapports = self.d / "outputs", self.d / "reports"
        self.cas = [cas_benchmark.trouver("01_coherent"), cas_benchmark.trouver("03_temps_impossible")]

    def faux_claude(self):
        chemin = self.d / "faux_claude.py"
        chemin.write_text(FAUX_CLAUDE, encoding="utf-8")
        return ClaudeRunner([sys.executable, str(chemin)], modele="modele-test", delai=120)

    def lignes(self, identifiant):
        return benchmark.lire_lignes(self.sorties / identifiant)


class TestFixture(Base):
    def test_arborescence_par_mode(self):
        benchmark.lancer(FixtureRunner(), (SINGLE_AGENT, MULTI_AGENT), self.cas, 1, "essai", self.sorties)
        for mode in ("single_agent", "multi_agent"):
            base = self.sorties / "essai" / mode / "01_coherent" / "repetition-1"
            self.assertTrue((base / "metrics.json").is_file())
            self.assertTrue((base / "output/Diapos/seance-1-diapos.pptx").is_file())
        self.assertEqual(len(self.lignes("essai")), 4)

    def test_toujours_marque_comme_simule(self):
        benchmark.lancer(FixtureRunner(), (SINGLE_AGENT, MULTI_AGENT), self.cas, 1, "essai", self.sorties)
        manifeste = json.loads((self.sorties / "essai/manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifeste["simulated"])
        self.assertTrue(all(l["simulated"] for l in self.lignes("essai")))
        texte = benchmark.rapporter("essai", self.sorties, self.rapports)
        self.assertIn("DONNÉES SIMULÉES", texte)
        self.assertIn("Aucune conclusion", texte)

    def test_aucune_mesure_inventee(self):
        benchmark.lancer(FixtureRunner(), (SINGLE_AGENT,), self.cas, 1, "essai", self.sorties)
        for ligne in self.lignes("essai"):
            self.assertIsNone(ligne["generation_time"])
            self.assertIsNone(ligne["human_interventions"])
            self.assertIsNone(ligne["accuracy"])
        texte = benchmark.rapporter("essai", self.sorties, self.rapports)
        self.assertIn("Generation time (average): non mesuré", texte)
        self.assertIn("Human interventions (average): non mesuré", texte)

    def test_valeurs_mesurees_dans_le_rapport(self):
        benchmark.lancer(FixtureRunner(), (SINGLE_AGENT,), self.cas, 1, "essai", self.sorties)
        texte = benchmark.rapporter("essai", self.sorties, self.rapports)
        self.assertIn("Courses: 2", texte)
        self.assertIn("Timing validity: 50% (n=2)", texte)
        self.assertIn("pas directement la qualité pédagogique", texte)

    def test_exports(self):
        benchmark.lancer(FixtureRunner(), (SINGLE_AGENT, MULTI_AGENT), self.cas, 2, "essai", self.sorties)
        benchmark.rapporter("essai", self.sorties, self.rapports)
        donnees = json.loads((self.rapports / "essai/benchmark_results.json").read_text(encoding="utf-8"))
        self.assertEqual(len(donnees), 8)
        with (self.rapports / "essai/benchmark_results.csv").open(encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f))
        self.assertEqual(len(lignes), 8)
        for colonne in ("mode", "case", "repetition", "simulated", "objective_coverage", "timing_validity", "evaluation_quality",
                        "hallucination_count", "critical_error_count", "warning_count", "human_interventions", "revision_count", "generation_time"):
            self.assertIn(colonne, lignes[0])
        self.assertTrue((self.rapports / "essai/report.txt").is_file())

    def test_reproductible(self):
        for identifiant in ("a", "b"):
            benchmark.lancer(FixtureRunner(), (SINGLE_AGENT,), self.cas, 1, identifiant, self.sorties)
        retirer = lambda lignes: [{k: v for k, v in l.items() if k != "run_id"} for l in lignes]
        self.assertEqual(retirer(self.lignes("a")), retirer(self.lignes("b")))

    def test_ne_recrit_pas_une_execution(self):
        benchmark.lancer(FixtureRunner(), (SINGLE_AGENT,), self.cas[:1], 1, "essai", self.sorties)
        with self.assertRaises(SystemExit):
            benchmark.lancer(FixtureRunner(), (SINGLE_AGENT,), self.cas[:1], 1, "essai", self.sorties)


class TestClaude(Base):
    def test_commandes_differentes_par_mode(self):
        runner = ClaudeRunner("claude --verbose", "un-modele")
        simple = runner.construire_commande(self.cas[0], SINGLE_AGENT)
        multi = runner.construire_commande(self.cas[0], MULTI_AGENT)
        self.assertEqual(simple[:3], ["claude", "--verbose", "-p"])
        self.assertIn("agent unique", simple[3])
        self.assertIn("--disallowedTools", simple)
        self.assertIn("multi-agent", multi[3])
        self.assertNotIn("--disallowedTools", multi)
        self.assertIn("Agent", multi[multi.index("--allowedTools") + 1])
        self.assertEqual(multi[multi.index("--model") + 1], "un-modele")
        for commande in (simple, multi):
            self.assertIn(self.cas[0].consignes, commande[3])
            self.assertIn("--plugin-dir", commande)

    def test_generation_reelle_simulee_par_un_faux_claude(self):
        benchmark.lancer(self.faux_claude(), (SINGLE_AGENT,), self.cas[:1], 1, "essai", self.sorties)
        ligne = self.lignes("essai")[0]
        self.assertEqual(ligne["run_status"], "completed")
        self.assertFalse(ligne["simulated"])
        self.assertIsInstance(ligne["generation_time"], float)
        # Personne n'a validé : ce n'est pas une intervention humaine.
        self.assertIsNone(ligne["human_interventions"])
        self.assertEqual(ligne["objective_coverage"], 100)
        base = self.sorties / "essai/single_agent/01_coherent/repetition-1/output"
        self.assertTrue((base / ".git").is_dir())
        self.assertTrue((base / "arguments.json").is_file())
        manifeste = json.loads((self.sorties / "essai/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifeste["model"], "modele-test")

    def test_echec_enregistre_sans_valeur_inventee(self):
        import os

        os.environ["FAUX_CLAUDE"] = "echec"
        self.addCleanup(os.environ.pop, "FAUX_CLAUDE")
        benchmark.lancer(self.faux_claude(), (SINGLE_AGENT,), self.cas[:1], 1, "essai", self.sorties)
        ligne = self.lignes("essai")[0]
        self.assertEqual((ligne["run_status"], ligne["objective_coverage"]), ("failed", None))
        self.assertIn("Code de sortie 3", ligne["error"])
        self.assertIn("erreur du faux Claude", (self.sorties / "essai/single_agent/01_coherent/repetition-1/run.log").read_text(encoding="utf-8"))
        texte = benchmark.rapporter("essai", self.sorties, self.rapports)
        self.assertIn("Runs: 1, failed: 1", texte)
        self.assertIn("Objective coverage: non mesuré", texte)

    def test_sans_sortie_compte_comme_un_echec(self):
        import os

        os.environ["FAUX_CLAUDE"] = "vide"
        self.addCleanup(os.environ.pop, "FAUX_CLAUDE")
        benchmark.lancer(self.faux_claude(), (SINGLE_AGENT,), self.cas[:1], 1, "essai", self.sorties)
        self.assertIn("Aucune sortie exploitable", self.lignes("essai")[0]["error"])

    def test_commande_absente(self):
        benchmark.lancer(ClaudeRunner(["commande-qui-n-existe-pas-xyz"]), (SINGLE_AGENT,), self.cas[:1], 1, "essai", self.sorties)
        self.assertIn("Lancement impossible", self.lignes("essai")[0]["error"])


class TestLigneDeCommande(Base):
    def test_verify_valide_les_dix_cas(self):
        r = lancer_cli("verify")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Comportements attendus vérifiés : 10/10", r.stdout)

    def test_claude_exige_un_accord_sur_le_cout(self):
        r = lancer_cli("run", "--runner", "claude", "--output-dir", str(self.sorties))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--i-accept-llm-costs", r.stderr)
        self.assertFalse(self.sorties.exists())

    def test_cas_inconnu(self):
        r = lancer_cli("run", "--runner", "fixture", "--cases", "99_absent", "--output-dir", str(self.sorties))
        self.assertIn("Cas inconnu", r.stderr)

    def test_lancer_et_rapporter(self):
        r = lancer_cli("run", "--runner", "fixture", "--cases", "01_coherent", "--run-id", "cli",
                       "--output-dir", str(self.sorties), "--reports-dir", str(self.rapports))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PREPA-COURS BENCHMARK", r.stdout)
        self.assertTrue((self.rapports / "cli/benchmark_results.csv").is_file())
        r = lancer_cli("report", "--output-dir", str(self.sorties), "--reports-dir", str(self.rapports))
        self.assertIn("Run: cli", r.stdout)

    def test_rapport_sans_execution(self):
        self.assertIn("Aucune exécution", lancer_cli("report", "--output-dir", str(self.sorties)).stderr)


if __name__ == "__main__":
    unittest.main()
