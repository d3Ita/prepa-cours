"""Vérifie la rédaction du cours, sa révision et le verrou avant la suite du pipeline."""
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
import modifier  # noqa: E402
import qualite  # noqa: E402
import redaction  # noqa: E402
from controler import controler  # noqa: E402

BROUILLON = ("# La digestion\n\n## L'estomac\nL'estomac brasse les aliments.\n\n"
             "## Sources utilisées\n- notes.txt : le rôle de l'estomac\n")


def lancer(script, *args, dossier=None):
    return subprocess.run([sys.executable, str(RACINE / "scripts" / script), *args], cwd=dossier,
                          capture_output=True, text=True, encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        racine = self.tmp / "Cours"
        self.d = racine / "5e" / "5e A" / "Chapitre 01"
        self.d.mkdir(parents=True)
        (racine / ".prepa-cours").touch()
        self.source = self.tmp / "notes.txt"
        self.source.write_text("L'estomac brasse les aliments.\n", encoding="utf-8")

    def demarrer(self):
        r = lancer("redaction.py", "demarrer", str(self.d), "--sources", str(self.source))
        self.assertEqual(r.returncode, 0, r.stderr)

    def produire(self, brouillon=BROUILLON):
        self.demarrer()
        (self.d / redaction.BROUILLON).write_text(brouillon, encoding="utf-8")
        r = lancer("redaction.py", "produire", str(self.d))
        self.assertEqual(r.returncode, 0, r.stderr)

    def etat(self):
        return lancer("redaction.py", "etat", str(self.d)).stdout

    def modifier_cours(self):
        """Simule une retouche du prof dans Word."""
        cours = self.d / redaction.COURS
        nouveau, nombre = modifier.remplacer(cours.read_bytes(), ".docx", "brasse", "mélange")
        self.assertEqual(nombre, 1)
        cours.write_bytes(nouveau)


class TestRedaction(Base):
    def test_sans_redaction_rien_ne_change(self):
        fixtures.ecrire_chapitre(self.d)
        self.assertIsNone(redaction.statut(self.d))
        self.assertEqual(controler(self.d)[0], [])
        self.assertIn("AUCUNE_REDACTION", self.etat())

    def test_documents_copies_et_originaux_intacts(self):
        self.demarrer()
        self.assertEqual((self.d / redaction.SOURCES / "notes.txt").read_text(encoding="utf-8"), self.source.read_text(encoding="utf-8"))
        self.assertTrue(self.source.exists())
        self.assertIn("EN_ATTENTE_DU_PREMIER_DOCUMENT", self.etat())

    def test_source_jamais_ecrasee(self):
        self.demarrer()
        self.source.write_text("Autre texte\n", encoding="utf-8")
        r = lancer("redaction.py", "demarrer", str(self.d), "--sources", str(self.source))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("existe déjà", r.stderr)
        self.assertIn("L'estomac", (self.d / redaction.SOURCES / "notes.txt").read_text(encoding="utf-8"))

    def test_document_absent_ne_copie_rien(self):
        r = lancer("redaction.py", "demarrer", str(self.d), "--sources", str(self.source), str(self.tmp / "absent.docx"))
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.d / redaction.SOURCES).exists())

    def test_produire_cree_le_document_et_retire_le_brouillon(self):
        self.produire()
        self.assertTrue((self.d / redaction.COURS).is_file())
        self.assertFalse((self.d / redaction.BROUILLON).exists())
        self.assertIn("Première version du cours", lancer("versions.py", "historique", dossier=self.d).stdout)
        self.assertIn("STATUS: EN_COURS", self.etat())
        self.assertIn("[2] Valider et passer à la suite", self.etat())

    def test_produire_ne_recrit_jamais_le_cours(self):
        self.produire()
        self.modifier_cours()
        retouche = (self.d / redaction.COURS).read_bytes()
        (self.d / redaction.BROUILLON).write_text(BROUILLON, encoding="utf-8")
        r = lancer("redaction.py", "produire", str(self.d))
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.d / redaction.COURS).read_bytes(), retouche)

    def test_produire_sans_brouillon(self):
        self.assertIn("Aucun brouillon", lancer("redaction.py", "produire", str(self.d)).stderr)


class TestVerification(Base):
    def test_termes_absents_des_documents(self):
        self.produire(BROUILLON + "\nLe chercheur Beaumont a observé 1833 repas.\n")
        sortie = self.etat()
        self.assertIn("« Beaumont »", sortie)
        self.assertIn("« 1833 »", sortie)

    def test_nom_du_document_dans_les_sources_utilisees_non_suspect(self):
        self.produire()
        self.assertNotIn("Absents des documents", self.etat())

    def test_source_illisible_ne_fait_rien_affirmer(self):
        (self.tmp / "scan.pdf").write_bytes(b"%PDF")
        lancer("redaction.py", "demarrer", str(self.d), "--sources", str(self.tmp / "scan.pdf"))
        self.produire(BROUILLON + "\nLe chercheur Beaumont.\n")
        sortie = self.etat()
        self.assertNotIn("« Beaumont »", sortie)
        self.assertIn("Documents non comparés automatiquement : scan.pdf", sortie)

    def test_a_verifier_empeche_la_validation_sans_accord(self):
        self.produire(BROUILLON + "\nUn complément externe [À VÉRIFIER]\n")
        self.assertIn("1 point(s) à vérifier", self.etat())
        r = lancer("redaction.py", "valider", str(self.d))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("accord explicite", r.stderr)
        self.assertEqual(redaction.statut(self.d), "en_cours")
        r = lancer("redaction.py", "valider", str(self.d), "--malgre-a-verifier")
        self.assertEqual(r.returncode, 0, r.stderr)
        trace = json.loads((self.d / redaction.ETAT).read_text(encoding="utf-8"))
        self.assertEqual(trace["validations"][0]["a_verifier_restants"], 1)


class TestVerrou(Base):
    def preparer_pipeline(self):
        self.produire()
        fixtures.ecrire_chapitre(self.d)

    def test_pipeline_bloque_tant_que_le_cours_n_est_pas_valide(self):
        self.preparer_pipeline()
        problemes, _ = controler(self.d)
        self.assertIn("Le cours est encore en rédaction : le prof ne l'a pas validé.", problemes)
        fixtures.ecrire_critique(self.d, "decoupage")
        r = qualite.construire_rapport(self.d, "decoupage")
        self.assertGreaterEqual(r["critiques"], 1)
        self.assertEqual(r["statut"], "HUMAN_REVIEW_REQUIRED")

    def test_validation_debloque(self):
        self.preparer_pipeline()
        self.assertEqual(lancer("redaction.py", "valider", str(self.d)).returncode, 0)
        self.assertEqual(redaction.statut(self.d), "validee")
        self.assertEqual(controler(self.d)[0], [])
        self.assertIn("Cours validé par le prof", lancer("versions.py", "historique", dossier=self.d).stdout)

    def test_modification_apres_validation_rebloque(self):
        self.preparer_pipeline()
        lancer("redaction.py", "valider", str(self.d))
        self.modifier_cours()
        self.assertEqual(redaction.statut(self.d), "modifie_apres_validation")
        self.assertIn("Le cours a changé depuis sa validation : le prof doit le revalider.", controler(self.d)[0])
        self.assertIn("STATUS: MODIFIE_APRES_VALIDATION", self.etat())
        self.assertEqual(lancer("redaction.py", "valider", str(self.d)).returncode, 0)
        self.assertEqual(controler(self.d)[0], [])
        trace = json.loads((self.d / redaction.ETAT).read_text(encoding="utf-8"))
        self.assertEqual(len(trace["validations"]), 2)

    def test_rouvrir_annule_la_validation(self):
        self.preparer_pipeline()
        lancer("redaction.py", "valider", str(self.d))
        self.assertEqual(lancer("redaction.py", "rouvrir", str(self.d)).returncode, 0)
        self.assertEqual(redaction.statut(self.d), "en_cours")

    def test_valider_sans_cours_refuse(self):
        self.demarrer()
        self.assertIn("rien à valider", lancer("redaction.py", "valider", str(self.d)).stderr)

    def test_le_cours_valide_sert_de_reference_pas_les_sources(self):
        self.source.write_text("Le terme Beaumont figure seulement ici.\n", encoding="utf-8")
        self.produire()
        self.assertNotIn("beaumont", qualite.lire_source(self.d).casefold())
        self.assertIn("estomac", qualite.lire_source(self.d).casefold())


class TestRevision(Base):
    def plan(self, modifications, **autres):
        (self.d / modifier.PLAN).write_text(json.dumps(
            {"demande": "Réviser", "references": ["zzz"], "modifications": modifications, **autres}, ensure_ascii=False), encoding="utf-8")

    def test_ajouter_un_paragraphe_garde_le_reste(self):
        self.produire()
        self.modifier_cours()
        self.plan([{"fichier": "Cours/cours.docx", "role": "cible", "action": "inserer",
                    "avant": "L'estomac mélange les aliments.", "apres": "Il produit aussi des sucs digestifs."}])
        etat = modifier.preparer(self.d)
        r = lancer("modifier.py", "appliquer", str(self.d), "--jeton", etat["jeton"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        from docx import Document

        paragraphes = Document(self.d / redaction.COURS).paragraphs
        textes = [p.text for p in paragraphes]
        i = textes.index("L'estomac mélange les aliments.")
        self.assertEqual(textes[i + 1], "Il produit aussi des sucs digestifs.")
        self.assertEqual(paragraphes[i + 1].style.name, paragraphes[i].style.name)
        self.assertIn("La digestion", textes)

    def test_enchainer_des_ajouts(self):
        self.produire()
        self.plan([{"fichier": "Cours/cours.docx", "role": "cible", "action": "inserer", "avant": "brasse les aliments", "apres": "Deuxième."},
                   {"fichier": "Cours/cours.docx", "role": "reference", "action": "inserer", "avant": "Deuxième.", "apres": "Troisième."}])
        etat = modifier.preparer(self.d)
        self.assertEqual(etat["erreurs"], [])
        textes = [t for _, t in modifier.paragraphes(etat["nouveaux"]["Cours/cours.docx"], ".docx")]
        self.assertEqual(textes[textes.index("Deuxième.") + 1], "Troisième.")

    def test_ajout_dans_un_fichier_texte_garde_ses_fins_de_ligne(self):
        self.assertEqual(modifier.inserer(b"un\r\ndeux\r\n", ".txt", "un", "entre")[0], b"un\r\nentre\r\ndeux\r\n")
        self.assertEqual(modifier.inserer(b"un", ".md", "un", "fin")[0], b"un\nfin\n")
        self.assertEqual(modifier.inserer("é\n".encode("cp1252"), ".txt", "é", "è")[0], "é\nè\n".encode("cp1252"))

    def test_ajout_ambigu_ou_introuvable_refuse(self):
        self.assertEqual(modifier.inserer(b"a\na\n", ".md", "a", "b")[1], 2)
        self.assertEqual(modifier.inserer(b"a\n", ".md", "z", "b")[1], 0)

    def test_ajout_vide_refuse_et_format_libreoffice_explique(self):
        self.produire()
        self.plan([{"fichier": "Cours/cours.docx", "role": "cible", "action": "inserer", "avant": "brasse", "apres": " "}])
        self.assertIn("Action invalide", lancer("modifier.py", "apercu", str(self.d)).stderr)
        self.assertEqual(modifier.inserer(b"x", ".odt", "a", "b")[1], -2)

    def test_les_documents_d_origine_ne_bloquent_pas_et_restent_intacts(self):
        self.produire()
        (self.d / modifier.PLAN).write_text(json.dumps({
            "demande": "Changer", "references": ["brasse"], "modifications": [
                {"fichier": "Cours/cours.docx", "role": "cible", "avant": "brasse", "apres": "mélange"}]}, ensure_ascii=False), encoding="utf-8")
        self.assertTrue(modifier.preparer(self.d)["complet"])
        self.plan([{"fichier": "Cours/Sources/notes.txt", "role": "cible", "avant": "brasse", "apres": "x"}])
        self.assertIn("Chemin refusé", lancer("modifier.py", "apercu", str(self.d)).stderr)

    def test_retour_a_une_version_precedente_du_cours(self):
        self.produire()
        origine = (self.d / redaction.COURS).read_bytes()
        version = lancer("versions.py", "historique", dossier=self.d).stdout.split()[0]
        self.modifier_cours()
        r = lancer("versions.py", "restaurer", version, "Cours/cours.docx", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.d / redaction.COURS).read_bytes(), origine)


if __name__ == "__main__":
    unittest.main()
