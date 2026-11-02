"""Vérifie le modèle de cours et la traçabilité des objectifs, sans aucun appel à un modèle de langage."""
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
import modele  # noqa: E402
from fixtures import ecrire_chapitre  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)


class TestModele(Base):
    def test_contient_toutes_les_parties(self):
        ecrire_chapitre(self.d)
        m = modele.construire_modele(self.d)
        self.assertEqual(set(m), {"version", "metadata", "objectives", "concepts", "sessions", "evaluations", "traceability"})
        self.assertEqual(m["metadata"]["title"], "la digestion")
        self.assertEqual(m["metadata"]["subject"], "SVT")
        self.assertEqual(m["metadata"]["level"], "Cinquième")
        self.assertEqual(m["metadata"]["duration_minutes"], 120)
        self.assertEqual(m["metadata"]["source"], ["Cours/cours.txt"])

    def test_identifiants_lisibles(self):
        ecrire_chapitre(self.d)
        m = modele.construire_modele(self.d)
        self.assertEqual([o["id"] for o in m["objectives"]], ["OBJ-001", "OBJ-002"])
        self.assertEqual(m["objectives"][0]["source_id"], "OBJ1")
        self.assertEqual(m["sessions"][1]["id"], "SES-002")
        self.assertEqual(m["sessions"][0]["activities"][1]["id"], "ACT-002")
        self.assertEqual(m["sessions"][0]["activities"][1]["exercise"], "EX-001")
        self.assertEqual(m["sessions"][0]["activities"][1]["duration_minutes"], 30)
        self.assertEqual(m["sessions"][1]["resources"][0]["id"], "RES-002")
        self.assertEqual(m["evaluations"][0]["id"], "EVAL-001")
        self.assertEqual(m["evaluations"][0]["type"], "qcm")
        self.assertEqual(m["concepts"][0], {"id": "C-001", "label": "estomac", "objectives": ["OBJ-001"]})

    def test_reproductible(self):
        ecrire_chapitre(self.d)
        self.assertEqual(modele.construire_modele(self.d), modele.construire_modele(self.d))

    def test_structure_valide_et_references_cassees(self):
        ecrire_chapitre(self.d)
        m = modele.construire_modele(self.d)
        self.assertEqual(modele.verifier_modele(m), [])
        m["sessions"][0]["activities"][0]["objectives"] = ["OBJ-099"]
        m["evaluations"][1]["id"] = m["evaluations"][0]["id"]
        erreurs = " ".join(modele.verifier_modele(m))
        self.assertIn("ACT-001 cite OBJ-099", erreurs)
        self.assertIn("Identifiant en double : EVAL-001", erreurs)

    def test_objectif_inconnu_cite_dans_un_scenario(self):
        ecrire_chapitre(self.d, seance_1__scenario=fixtures.scenario("OBJ9"))
        self.assertIn("cite OBJ-009", " ".join(modele.verifier_modele(modele.construire_modele(self.d))))

    def test_evaluation_finale_avec_types(self):
        ecrire_chapitre(self.d)
        (self.d / ".travail/evaluation.md").write_text("## Question 1\nType : vrai-faux\nVrai ?\n\n## Question 2 (4 points)\nDites.\n", encoding="utf-8")
        (self.d / ".travail/corrige.md").write_text("Question 1 : Vrai (OBJ1)\n| 2 | OBJ2 | Réponse | 4 |\n", encoding="utf-8")
        finales = [e for e in modele.construire_modele(self.d)["evaluations"] if e["session"] is None]
        self.assertEqual([(e["label"], e["type"], e["objectives"]) for e in finales],
                         [("FINAL-1", "vrai-faux", ["OBJ-001"]), ("FINAL-2", "question-ouverte", ["OBJ-002"])])

    def test_ancien_chapitre_sans_notions(self):
        ecrire_chapitre(self.d, objectifs=fixtures.OBJECTIFS.replace("  - Notions : estomac, sucs digestifs\n", "")
                        .replace("  - Notions : intestin grêle, nutriments\n", ""))
        m = modele.construire_modele(self.d)
        self.assertEqual(m["concepts"], [])
        self.assertEqual(m["traceability"]["OBJ-001"]["status"], modele.COMPLET)

    def test_chapitre_vide_ne_plante_pas(self):
        (self.d / ".travail").mkdir()
        (self.d / ".travail/objectifs.md").write_text("", encoding="utf-8")
        m = modele.construire_modele(self.d)
        self.assertEqual((m["objectives"], m["metadata"]["source"]), ([], []))

    def test_exemples_du_depot(self):
        chapitres = [p.parent for p in (RACINE / "exemples").rglob(".travail")]
        self.assertEqual(len(chapitres), 2)
        for chapitre in chapitres:
            with self.subTest(chapitre.name):
                self.assertEqual(modele.verifier_modele(modele.construire_modele(chapitre)), [])


class TestTracabilite(Base):
    def test_complet(self):
        ecrire_chapitre(self.d)
        t = modele.construire_modele(self.d)["traceability"]["OBJ-001"]
        self.assertEqual(t["status"], modele.COMPLET)
        self.assertEqual(t["concepts"], ["C-001", "C-002"])
        self.assertEqual(t["sessions"], ["SES-001"])
        self.assertEqual(t["activities"], ["ACT-001", "ACT-002", "ACT-003"])
        self.assertEqual(t["exercises"], ["EX-001"])
        self.assertEqual(t["evaluations"][:2], ["EVAL-001", "EVAL-002"])

    def test_partiel_explique(self):
        ecrire_chapitre(self.d, seance_1__diapos="# Un\n- x\n")
        t = modele.construire_modele(self.d)["traceability"]["OBJ-001"]
        self.assertEqual((t["status"], t["missing"]), (modele.PARTIEL, ["resources"]))
        self.assertIn("ressource ou diapo", t["explanation"])

    def test_manquant_explique(self):
        ecrire_chapitre(self.d, seance_2__scenario="## 0-60 min — Exposé\n", seance_2__diapos="# Un\n- x\n", seance_2__qcm_corrige="")
        t = modele.construire_modele(self.d)["traceability"]["OBJ-002"]
        self.assertEqual(t["status"], modele.MANQUANT)
        self.assertIn("OBJ-002 est défini, mais n'a aucune activité", t["explanation"])

    def test_sortie_et_fichier(self):
        ecrire_chapitre(self.d, seance_2__scenario="## 0-60 min — Exposé\n", seance_2__diapos="# Un\n- x\n", seance_2__qcm_corrige="")
        r = subprocess.run([sys.executable, str(RACINE / "scripts/modele.py"), str(self.d)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        for attendu in ("OBJECTIVE COVERAGE", "OBJ-001 ✓", "OBJ-002 ✗ MISSING", "├── concepts : C-001, C-002", "n'a aucune activité"):
            self.assertIn(attendu, r.stdout)
        self.assertEqual(json.loads((self.d / modele.FICHIER).read_text(encoding="utf-8"))["version"], modele.VERSION_MODELE)

    def test_dossier_invalide(self):
        r = subprocess.run([sys.executable, str(RACINE / "scripts/modele.py"), str(self.d)], capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("objectifs.md est absent", r.stderr)


if __name__ == "__main__":
    unittest.main()
