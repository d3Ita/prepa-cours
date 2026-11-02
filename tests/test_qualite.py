"""Vérifie la matrice, les évaluations, le score et la boucle de révision, sans aucun appel à un modèle."""
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

import evaluations  # noqa: E402
import fixtures  # noqa: E402
import matrice  # noqa: E402
import qualite  # noqa: E402
from controler import controler  # noqa: E402
from fixtures import constat, ecrire_chapitre, ecrire_critique, vieillir_revue  # noqa: E402


def lancer(script, *args):
    return subprocess.run([sys.executable, str(RACINE / "scripts" / script), *args],
                          capture_output=True, text=True, encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)

    def rapport(self, etape="livrables"):
        return qualite.construire_rapport(self.d, etape)

    def problemes(self, rapport=None):
        return [c["problem"] for c in (rapport or self.rapport())["constats"]]


class TestEvaluations(unittest.TestCase):
    QUESTIONS = ("## Question 1\nA. a\nB. b\nC. c\n\n## Question 2\nType : vrai-faux\nLa terre tourne.\n\n"
                 "## Question 3\nType : Etude de cas\nAnalysez.\n\n## Question 4\nType : question-ouverte\nDites.\n")

    def test_types_de_question_lus_depuis_le_sujet(self):
        types = [q.type for q in evaluations.lire_sujet(self.QUESTIONS, "qcm")]
        self.assertEqual(types, ["qcm", "vrai-faux", "etude-de-cas", "question-ouverte"])

    def test_chaque_type_applique_ses_regles(self):
        corrige = "Question 1 : B\nQuestion 2 : Vrai\nQuestion 3 : Une analyse\nQuestion 4 : Une réponse\n"
        self.assertEqual(evaluations.verifier(self.QUESTIONS, corrige, "qcm"), [])
        faux = corrige.replace("2 : Vrai", "2 : Peut-être")
        self.assertIn("doit être « Vrai » ou « Faux »", " ".join(evaluations.verifier(self.QUESTIONS, faux, "qcm")))

    def test_type_inconnu_explique(self):
        message = " ".join(evaluations.verifier("## Question 1\nType : chanson\nChantez.\n", "Question 1 : la la\n", "qcm"))
        self.assertIn("type inconnu : chanson", message)

    def test_registre_extensible_sans_toucher_au_reste(self):
        evaluations.TYPES["oral"] = lambda question, reponse: [f"oral {question.numero}"]
        self.addCleanup(evaluations.TYPES.pop, "oral")
        self.assertEqual(evaluations.verifier("## Question 1\nType : oral\n", "Question 1 : x\n", "qcm"), ["oral 1"])

    def test_plusieurs_bonnes_reponses(self):
        for reponse in ("A, C", "A et C", "**A/C**"):
            with self.subTest(reponse):
                problemes = evaluations.verifier("## Question 1\nA. a\nB. b\nC. c\n", f"Question 1 : {reponse}\n", "qcm")
                self.assertIn("plusieurs bonnes réponses", " ".join(problemes))

    def test_reponse_de_qcm_seule_lettre(self):
        for texte, lettres in (("B (OBJ1) — Oui", ["B"]), ("**C**", ["C"]), ("Vrai", []), ("A, D", ["A", "D"]), ("Le cours", [])):
            self.assertEqual(evaluations.Reponse(1, texte, []).lettres, lettres, texte)

    def test_corrige_contradictoire(self):
        problemes = evaluations.verifier("## Question 1\nA. a\nB. b\nC. c\n", "Question 1 : A\nQuestion 1 : B\n", "qcm")
        self.assertIn("se contredit", " ".join(problemes))

    def test_reponse_et_bareme_ne_se_contredisent_pas(self):
        corrige = "| 1 | OBJ1 | Une réponse | 4 |\n\nQuestion 1 : 1 point pour ceci.\n"
        self.assertEqual(evaluations.verifier("## Question 1 (4 points)\nDites.\n", corrige, "question-ouverte"), [])

    def test_meme_choix_propose_deux_fois(self):
        problemes = evaluations.verifier("## Question 1\nA. a\nB. a\nC. c\n", "Question 1 : C\n", "qcm")
        self.assertIn("deux fois le même choix", " ".join(problemes))


class TestMatrice(Base):
    def test_trace_un_objectif_jusqu_a_l_evaluation(self):
        ecrire_chapitre(self.d)
        entree = matrice.construire(self.d)["OBJ1"]
        self.assertEqual(entree["notions"], ["estomac", "sucs digestifs"])
        self.assertEqual(entree["seances"], [1])
        self.assertEqual(entree["activites"], ["ACT-01", "ACT-02", "ACT-03"])
        self.assertEqual(entree["exercices"], ["EX-01"])
        self.assertEqual(entree["diapos"], ["S1:1"])
        self.assertEqual(entree["evaluations"][0], "S1-QCM-1")

    def test_couverture_complete(self):
        ecrire_chapitre(self.d)
        for c in matrice.couverture(matrice.construire(self.d)).values():
            self.assertEqual(c, {"pourcentage": 100, "manquants": []})

    def test_objectif_sans_activite_ni_evaluation_est_detecte(self):
        ecrire_chapitre(self.d, seance_2__scenario="## 0-60 min — Exposé\n", seance_2__diapos="# Un\n- x\n",
                        seance_2__qcm_corrige="")
        c = matrice.couverture(matrice.construire(self.d))["OBJ2"]
        self.assertEqual(c["pourcentage"], 0)
        constats = [x for x in self.rapport()["constats"] if x["location"] == "OBJ2"]
        self.assertEqual(constats[0]["severity"], "critical")

    def test_couverture_depend_de_l_etape(self):
        ecrire_chapitre(self.d)
        (self.d / ".travail/seance-1/diapos.md").unlink()
        m = matrice.construire(self.d)
        self.assertEqual(matrice.couverture(m, "scenarios")["OBJ1"]["pourcentage"], 100)
        self.assertEqual(matrice.couverture(m, "livrables")["OBJ1"]["pourcentage"], 75)
        self.assertEqual(matrice.couverture(m, "decoupage")["OBJ1"]["pourcentage"], 100)

    def test_sortie_lisible(self):
        ecrire_chapitre(self.d)
        (self.d / ".travail/seance-2/qcm-corrige.md").write_text(fixtures.corrige("OBJ1"), encoding="utf-8")
        sortie = lancer("matrice.py", str(self.d)).stdout
        self.assertIn("OBJECTIVE COVERAGE", sortie)
        self.assertIn("OBJ1 ✓ 100%", sortie)
        self.assertIn("OBJ2 ⚠ 75%", sortie)
        self.assertIn("OBJ2 : manque évaluation.", sortie)
        self.assertIn('"couverture"', lancer("matrice.py", str(self.d), "--json").stdout)


class TestDetection(Base):
    def test_cours_valide_sans_probleme(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d)
        r = self.rapport()
        self.assertEqual(self.problemes(r), [])
        self.assertEqual(r["global"], 100)
        self.assertEqual(r["statut"], "READY_FOR_HUMAN_VALIDATION")

    def test_timing_impossible(self):
        ecrire_chapitre(self.d, seance_1__scenario="## 0-77 min — A\n- OBJ1\n")
        r = self.rapport()
        self.assertIn("le scénario dure 77 min pour une séance de 60 min", " ".join(self.problemes(r)))
        self.assertEqual(r["scores"]["timing"]["score"], 88)
        self.assertEqual(r["constats"][0]["category"], "timing")

    def test_phase_sans_temps(self):
        ecrire_chapitre(self.d, seance_1__scenario=fixtures.scenario("OBJ1") + "## Activité sans horaire\n- OBJ1\n")
        self.assertIn("La phase « Activité sans horaire » n'a pas de temps défini.", self.problemes())

    def test_qcm_avec_plusieurs_bonnes_reponses_bloque(self):
        ecrire_chapitre(self.d, seance_1__qcm_corrige="Question 1 : A, B (OBJ1)\nQuestion 2 : B\nQuestion 3 : C\nQuestion 4 : D\nQuestion 5 : A\n")
        r = self.rapport()
        self.assertIn("plusieurs bonnes réponses", " ".join(self.problemes(r)))
        self.assertGreaterEqual(r["critiques"], 1)
        self.assertEqual(r["statut"], "HUMAN_REVIEW_REQUIRED")

    def test_corrige_incoherent_bloque(self):
        ecrire_chapitre(self.d, seance_1__qcm_corrige="Question 1 : Z (OBJ1)\nQuestion 2 : B\nQuestion 3 : C\nQuestion 4 : D\nQuestion 5 : A\n")
        problemes, _ = controler(self.d)
        self.assertIn("la réponse Z de la question 1 n'existe pas", " ".join(problemes))
        self.assertGreaterEqual(self.rapport()["critiques"], 1)

    def test_contradiction_dans_un_corrige(self):
        ecrire_chapitre(self.d, seance_1__qcm_corrige=fixtures.corrige("OBJ1") + "Question 1 : C\n")
        self.assertIn("se contredit sur la question 1", " ".join(self.problemes()))

    def test_contradiction_sur_la_duree_totale(self):
        ecrire_chapitre(self.d, objectifs=fixtures.OBJECTIFS.replace("Durée totale : 2 h", "Durée totale : 3 h"))
        self.assertIn("Les séances totalisent 120 min", " ".join(self.problemes()))

    def test_nombre_et_nom_absents_du_cours(self):
        ecrire_chapitre(self.d, seance_1__diapos="# Un\n- Le chercheur Beaumont a mesuré 1833 repas\n> Objectif : OBJ1\n")
        r = self.rapport()
        suspects = [c for c in r["constats"] if c["category"] == "hallucination"]
        self.assertEqual({c["provenance"] for c in suspects}, {"externe"})
        self.assertIn("« 1833 » n'apparaît pas dans le cours d'origine.", self.problemes(r))
        self.assertIn("« Beaumont » n'apparaît pas dans le cours d'origine.", self.problemes(r))

    def test_ce_qui_vient_du_cours_n_est_pas_suspect(self):
        ecrire_chapitre(self.d, seance_1__diapos="# Un\n- La digestion complète dure environ 24 heures\n- Bilan : L'estomac brasse\n> Objectif : OBJ1\n")
        self.assertEqual([c for c in self.rapport()["constats"] if c["category"] == "hallucination"], [])

    def test_information_a_verifier_tracee_sans_etre_cachee(self):
        ecrire_chapitre(self.d, seance_1__diapos="# Un\n- Le chercheur Beaumont [À VÉRIFIER]\n> Objectif : OBJ1\n")
        constats = [c for c in self.rapport()["constats"] if c["category"] == "hallucination"]
        self.assertEqual(len(constats), 1)
        self.assertEqual((constats[0]["severity"], constats[0]["provenance"]), ("info", "incertaine"))
        self.assertIn("Beaumont", constats[0]["evidence"])

    def test_source_illisible_signalee(self):
        ecrire_chapitre(self.d)
        (self.d / "Cours" / "cours.txt").unlink()
        (self.d / "Cours" / "cours.pdf").write_bytes(b"%PDF")
        self.assertIn("Le cours d'origine n'a pas pu être lu par le contrôle.", self.problemes())

    def test_etapes_ne_reclament_pas_ce_qui_n_existe_pas_encore(self):
        ecrire_chapitre(self.d)
        for n in (1, 2):
            for f in ("diapos.md", "qcm.md", "qcm-corrige.md"):
                (self.d / f".travail/seance-{n}/{f}").unlink()
        self.assertEqual(self.rapport("scenarios")["critiques"], 0)
        self.assertGreater(self.rapport("livrables")["critiques"], 0)
        import shutil
        shutil.rmtree(self.d / ".travail/seance-1")
        shutil.rmtree(self.d / ".travail/seance-2")
        r = self.rapport("decoupage")
        self.assertEqual(r["critiques"], 0)
        self.assertIsNone(r["scores"]["evaluation"]["score"])


class TestCritique(Base):
    def test_absente_ne_donne_pas_un_score_complet(self):
        ecrire_chapitre(self.d)
        r = self.rapport()
        self.assertTrue(r["partiel"])
        self.assertIsNone(r["scores"]["exactitude"]["score"])
        self.assertIsNone(r["scores"]["progression"]["score"])
        self.assertEqual(r["statut"], "HUMAN_REVIEW_REQUIRED")

    def test_un_simple_ok_est_refuse(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, verifs=[])
        self.assertEqual(self.rapport()["critique"], "incomplète")
        ecrire_critique(self.d, verifs=fixtures.verifications(fixtures.CATEGORIES[:5]))
        self.assertEqual(self.rapport()["critique"], "incomplète")

    def test_constat_mal_forme_refuse(self):
        ecrire_chapitre(self.d)
        for mauvais in (constat(severity="grave"), constat(category="autre"), constat(problem=""),
                        constat(severity="critical", evidence=""), constat(provenance="ailleurs"), "texte"):
            with self.subTest(mauvais):
                ecrire_critique(self.d, constats=[mauvais])
                self.assertEqual(self.rapport()["critique"], "invalide")

    def test_json_casse_refuse(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d)
        chemin = self.d / ".travail/revue/critique.json"
        stat = chemin.stat()
        chemin.write_text("{pas du json", encoding="utf-8")
        os.utime(chemin, (stat.st_atime, stat.st_mtime))
        self.assertEqual(self.rapport()["critique"], "invalide")

    def test_critique_d_une_autre_etape_ignoree(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, etape="scenarios", constats=[constat()])
        self.assertEqual(self.rapport("livrables")["critique"], "d'une autre étape")

    def test_revision_rend_la_critique_obsolete(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d)
        self.assertEqual(self.rapport()["critique"], "ok")
        vieillir_revue(self.d)
        self.assertEqual(self.rapport()["critique"], "obsolète")

    def test_hallucination_de_la_critique_compte_dans_l_exactitude(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat("critical", "hallucination", problem="Date inventée", provenance="externe")])
        r = self.rapport()
        self.assertEqual(r["scores"]["exactitude"]["score"], 60)
        self.assertEqual(r["statut"], "HUMAN_REVIEW_REQUIRED")
        # Un constat pour neuf fichiers produits : objectifs.md et quatre textes par séance.
        self.assertEqual(r["metriques"]["hallucination_rate"], round(1 / 9, 2))


class TestScore(Base):
    def test_explicable_et_borne(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat("warning", "timing", "seance-2", "Séance trop chargée")] * 2
                        + [constat("info", "pedagogical", "seance-1", "Répétition")] + [constat("warning", "factual")] * 10)
        s = self.rapport()["scores"]
        self.assertEqual(s["timing"]["score"], 76)
        self.assertIn("Séance trop chargée (seance-2) : Une preuve", s["timing"]["details"])
        self.assertEqual(s["progression"]["score"], 97)
        self.assertEqual(s["exactitude"]["score"], 0)

    def test_probleme_bloquant_plafonne_le_global(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat("critical", "pedagogical")])
        r = self.rapport()
        self.assertEqual(r["global"], qualite.PLAFOND_CRITIQUE)
        self.assertEqual(r["critiques"], 1)

    def test_rapport_affiche_et_enregistre(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat("critical", "evaluation", problem="Corrigé faux")])
        r = lancer("qualite.py", "rapport", str(self.d))
        self.assertEqual(r.returncode, 1)
        for attendu in ("QUALITY SCORE", "Global", "Évaluation", "- Corrigé faux", "OBJECTIVE COVERAGE", "CRITICAL ISSUES: 1",
                        "WARNINGS: 0", "STATUS: HUMAN_REVIEW_REQUIRED", "Diapos et évaluations terminées.",
                        "[1] Valider", "[2] Modifier", "[3] Relancer l'analyse"):
            self.assertIn(attendu, r.stdout)
        enregistre = json.loads((self.d / ".travail/revue/qualite.json").read_text(encoding="utf-8"))
        self.assertEqual(enregistre["constats"][0]["problem"], "Corrigé faux")

    def test_metriques_de_comparaison_completes(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d)
        m = self.rapport()["metriques"]
        self.assertEqual(set(m), {"accuracy", "pedagogical_coherence", "objective_coverage", "timing_validity",
                                  "evaluation_quality", "content_completeness", "hallucination_rate", "hallucination_count",
                                  "critical_error_count", "warning_count", "human_interventions", "revision_count", "generation_time"})
        self.assertEqual(m["objective_coverage"], 100)

    def test_chapitre_inconnu_explique(self):
        r = lancer("qualite.py", "rapport", str(self.d))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("objectifs.md est absent", r.stderr)


class TestBoucle(Base):
    def decider(self, cycles=2, etape="livrables"):
        return qualite.decider(self.d, etape, cycles)

    def test_critique_requise_avant_toute_decision(self):
        ecrire_chapitre(self.d)
        self.assertIn("CRITIQUE_REQUISE (critique absente)", self.decider())

    def test_sans_probleme_va_au_prof_jamais_validee_seule(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d)
        self.assertEqual(self.decider(), "DECISION: VALIDATION_HUMAINE")
        self.assertEqual(self.rapport()["statut"], "READY_FOR_HUMAN_VALIDATION")

    def test_limite_de_revisions_rend_la_main_au_prof(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat()])
        self.assertEqual(self.decider(), "DECISION: REVISION 1/2")
        self.assertEqual(self.decider(), "DECISION: REVISION 2/2")
        fin = self.decider()
        self.assertIn("⚠ Révision maximale atteinte.\nUne validation humaine est requise.", fin)
        self.assertTrue(fin.endswith("DECISION: VALIDATION_HUMAINE"))
        self.assertEqual(self.decider(), fin)

    def test_limite_configurable_et_zero(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat()])
        self.assertIn("Révision maximale", self.decider(cycles=0))

    def test_reglage_illisible_garde_le_defaut(self):
        for valeur, attendu in (("3", 3), (0, 0), ("${user_config.max_revision_cycles}", 2), ("", 2), (None, 2), ("99", 2), ("-1", 2)):
            self.assertEqual(qualite.lire_max_cycles(valeur), attendu, valeur)

    def test_compteur_par_etape(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat()], etape="scenarios")
        self.assertEqual(self.decider(etape="scenarios"), "DECISION: REVISION 1/2")
        ecrire_critique(self.d, constats=[constat()], etape="livrables")
        self.assertEqual(self.decider(etape="livrables"), "DECISION: REVISION 1/2")

    def test_boucle_complete_jusqu_a_la_correction(self):
        ecrire_chapitre(self.d, seance_1__scenario="## 0-77 min — Activité\n- OBJ1\n")
        ecrire_critique(self.d)
        self.assertEqual(self.decider(), "DECISION: REVISION 1/2")
        (self.d / ".travail/seance-1/scenario.md").write_text(fixtures.scenario("OBJ1"), encoding="utf-8")
        vieillir_revue(self.d)
        self.assertIn("CRITIQUE_REQUISE (critique obsolète)", self.decider())
        ecrire_critique(self.d)
        self.assertEqual(self.decider(), "DECISION: VALIDATION_HUMAINE")

    def test_seule_la_reponse_du_prof_valide(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d)
        self.assertNotEqual(self.rapport()["statut"], "HUMAN_VALIDATED")
        r = lancer("qualite.py", "valider", str(self.d), "--etape", "livrables", "--decision", "valider")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rapport()["statut"], "HUMAN_VALIDATED")
        self.assertEqual(self.rapport()["metriques"]["human_interventions"], 1)
        trace = json.loads((self.d / ".travail/revue/validations.json").read_text(encoding="utf-8"))
        self.assertEqual((trace[0]["etape"], trace[0]["decision"], trace[0]["score"]), ("livrables", "valider", 100))

    def test_modification_apres_validation_annule_la_validation(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d)
        qualite.valider(self.d, "livrables", "valider")
        vieillir_revue(self.d)
        self.assertNotEqual(self.rapport()["statut"], "HUMAN_VALIDATED")

    def test_le_prof_peut_valider_malgre_un_probleme(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat("critical", "factual")])
        qualite.valider(self.d, "livrables", "valider")
        r = self.rapport()
        self.assertEqual((r["statut"], r["critiques"]), ("HUMAN_VALIDATED", 1))

    def test_relancer_rouvre_la_boucle(self):
        ecrire_chapitre(self.d)
        ecrire_critique(self.d, constats=[constat()])
        self.assertIn("REVISION", self.decider(cycles=1))
        self.assertIn("Révision maximale", self.decider(cycles=1))
        qualite.valider(self.d, "livrables", "relancer")
        self.assertNotEqual(self.rapport()["statut"], "HUMAN_VALIDATED")
        ecrire_critique(self.d, constats=[constat()])
        self.assertIn("REVISION", self.decider(cycles=1))


class TestNonRegression(Base):
    def test_exemples_sans_probleme_bloquant(self):
        chapitres = [p.parent for p in (RACINE / "exemples").rglob(".travail")]
        self.assertEqual(len(chapitres), 2)
        for chapitre in chapitres:
            with self.subTest(chapitre.name):
                import shutil
                copie = self.d / chapitre.name
                shutil.copytree(chapitre, copie)
                self.assertEqual(controler(copie)[0], [])
                r = qualite.construire_rapport(copie, "livrables")
                self.assertEqual(r["critiques"], 0, [c["problem"] for c in r["constats"]])

    def test_ancien_chapitre_sans_revue_ni_notions_reste_lisible(self):
        ecrire_chapitre(self.d, objectifs=fixtures.OBJECTIFS.replace("  - Notions : estomac, sucs digestifs\n", "")
                        .replace("  - Notions : intestin grêle, nutriments\n", ""))
        self.assertEqual(controler(self.d)[0], [])
        self.assertEqual(matrice.construire(self.d)["OBJ1"]["notions"], [])
        self.assertFalse((self.d / ".travail/revue").exists())

    def test_ancienne_evaluation_finale_redigee_ne_fait_pas_echouer_le_controle(self):
        ecrire_chapitre(self.d)
        (self.d / ".travail/evaluation.md").write_text("Total : 4 points\n## Question 1 (4 points)\nDites.\n", encoding="utf-8")
        (self.d / ".travail/corrige.md").write_text("Une réponse libre, sans numéro (OBJ1).\n", encoding="utf-8")
        for f in ("Evaluations/evaluation.docx", "Corrections/evaluation-corrige.docx"):
            (self.d / f).parent.mkdir(exist_ok=True)
            (self.d / f).touch()
        self.assertEqual(controler(self.d)[0], [])
        self.assertIn("le corrigé ne donne pas la réponse à la question 1.", self.problemes())

    def test_controle_reste_une_liste_de_messages(self):
        ecrire_chapitre(self.d, seance_1__qcm="# QCM\n")
        problemes, _ = controler(self.d)
        self.assertTrue(all(isinstance(p, str) for p in problemes))
        self.assertIn("seance-1 : le QCM a 0 question(s) au lieu de 5.", problemes)


if __name__ == "__main__":
    unittest.main()
