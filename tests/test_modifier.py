"""Vérifie la modification ciblée : aperçu, validation, références et documents intacts ailleurs."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixtures  # noqa: E402
import modifier  # noqa: E402
import qualite  # noqa: E402


def lancer(script, *args, dossier=None):
    return subprocess.run([sys.executable, str(RACINE / "scripts" / script), *args], cwd=dossier,
                          capture_output=True, text=True, encoding="utf-8")


def texte_de(chemin):
    return " | ".join(t for _, t in modifier.paragraphes(chemin.read_bytes(), chemin.suffix.lower()))


class Base(unittest.TestCase):
    AVANT = "Les aliments deviennent des nutriments"
    APRES = "Les aliments sont transformés en nutriments"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.racine = Path(tmp.name).resolve() / "Cours"
        self.d = self.racine / "5e" / "5e A" / "Chapitre 01"
        self.d.mkdir(parents=True)
        (self.racine / ".prepa-cours").touch()
        fixtures.ecrire_chapitre(self.d)
        for n in (1, 2):
            source = self.d / f".travail/seance-{n}/diapos.md"
            self.generer("pptx", source, self.d / f"Diapos/seance-{n}-diapos.pptx")
            for nom, sortie in (("qcm", f"QCM/seance-{n}-qcm"), ("qcm-corrige", f"Corrections/seance-{n}-qcm-corrige"),
                                ("scenario", f"Cours/seance-{n}-scenario")):
                self.generer("docx", self.d / f".travail/seance-{n}/{nom}.md", self.d / f"{sortie}.docx")

    def generer(self, format_, source, sortie):
        r = lancer("generer.py", format_, str(source), str(sortie), "--ecraser")
        self.assertEqual(r.returncode, 0, r.stderr)

    def plan_complet(self, **autres):
        modifications = [
            {"fichier": "Diapos/seance-1-diapos.pptx", "role": "cible", "avant": self.AVANT, "apres": self.APRES},
            {"fichier": "Diapos/seance-2-diapos.pptx", "role": "reference", "avant": self.AVANT, "apres": self.APRES},
            {"fichier": ".travail/seance-1/diapos.md", "role": "reference", "avant": self.AVANT, "apres": self.APRES},
            {"fichier": ".travail/seance-2/diapos.md", "role": "reference", "avant": self.AVANT, "apres": self.APRES},
        ]
        return {"demande": "Reformuler la phrase", "references": [self.AVANT], "modifications": modifications, **autres}

    def ecrire_plan(self, plan):
        chemin = self.d / modifier.PLAN
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    def jeton(self):
        r = lancer("modifier.py", "apercu", str(self.d))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.split("JETON: ")[1].split()[0]


class TestRecherche(Base):
    def test_trouve_dans_tous_les_formats_et_les_notes(self):
        r = lancer("modifier.py", "rechercher", "brasse", str(self.d))
        self.assertIn(".txt", r.stdout)
        (self.d / ".travail/seance-1/diapos.md").write_text("# Un\n- x\n> Note sur le chyme\n", encoding="utf-8")
        self.generer("pptx", self.d / ".travail/seance-1/diapos.md", self.d / "Diapos/seance-1-diapos.pptx")
        r = lancer("modifier.py", "rechercher", "CHYME", str(self.d))
        self.assertIn("Diapos/seance-1-diapos.pptx | notes de la diapo 1 | Note sur le chyme", r.stdout)
        self.assertIn(".travail/seance-1/diapos.md | ligne 3", r.stdout)
        self.assertIn("2 occurrence(s).", r.stdout)

    def test_mot_entier_seulement(self):
        (self.d / "Cours/notes.txt").write_text("24 heures\n240 repas\n", encoding="utf-8")
        occurrences, _ = modifier.rechercher("24", self.d / "Cours")
        self.assertIn("24 heures", [o[2] for o in occurrences])
        self.assertNotIn("240 repas", [o[2] for o in occurrences])

    def test_chapitre_par_un_chemin_relatif_ou_un_lien(self):
        self.ecrire_plan(self.plan_complet())
        self.assertEqual(lancer("modifier.py", "apercu", dossier=self.d).returncode, 0)
        lien = self.racine.parent / "lien"
        try:
            lien.symlink_to(self.d, target_is_directory=True)
        except OSError:
            self.skipTest("Liens symboliques indisponibles sur ce système.")
        self.assertEqual(lancer("modifier.py", "apercu", str(lien)).returncode, 0)

    def test_signale_ce_qu_elle_ne_peut_pas_lire(self):
        (self.d / "Cours/ancien.pdf").write_bytes(b"%PDF")
        (self.d / "Cours/casse.docx").write_bytes(b"pas un zip")
        r = lancer("modifier.py", "rechercher", "x", str(self.d))
        self.assertIn("Non vérifié : Cours/ancien.pdf", r.stdout)
        self.assertIn("Non vérifié : Cours/casse.docx", r.stdout)


class TestRemplacement(Base):
    def test_ne_change_que_le_texte_vise_dans_un_pptx(self):
        chemin = self.d / "Diapos/seance-1-diapos.pptx"
        donnees = chemin.read_bytes()
        nouveau, nombre = modifier.remplacer(donnees, ".pptx", self.AVANT, self.APRES)
        self.assertEqual(nombre, 1)
        with zipfile.ZipFile(chemin) as a:
            avant = {n: a.read(n) for n in a.namelist()}
        (self.d / "n.pptx").write_bytes(nouveau)
        with zipfile.ZipFile(self.d / "n.pptx") as b:
            self.assertEqual(b.namelist(), list(avant))
            changes = [n for n in b.namelist() if b.read(n) != avant[n]]
        self.assertEqual(changes, ["ppt/slides/slide1.xml"])
        from pptx import Presentation
        textes = [s.text_frame.text for s in Presentation(self.d / "n.pptx").slides[0].shapes if s.has_text_frame]
        self.assertIn(self.APRES, textes)

    def test_retouche_en_gras_conservee_et_texte_coupe_remplace(self):
        from docx import Document

        doc = Document()
        para = doc.add_paragraph()
        para.add_run("Début ")
        para.add_run("mot").bold = True
        para.add_run(" à changer ici")
        doc.add_paragraph("Autre paragraphe & intact")
        chemin = self.d / "r.docx"
        doc.save(chemin)
        nouveau, nombre = modifier.remplacer(chemin.read_bytes(), ".docx", "mot à changer", "terme <nouveau>")
        self.assertEqual(nombre, 1)
        chemin.write_bytes(nouveau)
        relu = Document(chemin)
        self.assertEqual(relu.paragraphs[0].text, "Début terme <nouveau> ici")
        self.assertEqual(relu.paragraphs[1].text, "Autre paragraphe & intact")
        self.assertTrue(relu.paragraphs[0].runs[1].bold)
        self.assertEqual(relu.paragraphs[0].runs[2].text, " ici")

    def test_toutes_les_occurrences_seulement_si_demande(self):
        donnees = b"a chat\nb chat\n"
        self.assertEqual(modifier.remplacer(donnees, ".md", "chat", "chien"), (donnees, 2))
        nouveau, nombre = modifier.remplacer(donnees, ".md", "chat", "chien", toutes=True)
        self.assertEqual((nouveau.decode(), nombre), ("a chien\nb chien\n", 2))

    def test_plusieurs_occurrences_dans_un_paragraphe(self):
        from docx import Document

        doc = Document()
        doc.add_paragraph("chat et chat et chaton")
        chemin = self.d / "m.docx"
        doc.save(chemin)
        nouveau, nombre = modifier.remplacer(chemin.read_bytes(), ".docx", "chat", "chat noir", toutes=True)
        self.assertEqual(nombre, 3)
        chemin.write_bytes(nouveau)
        self.assertEqual(Document(chemin).paragraphs[0].text, "chat noir et chat noir et chat noiron")

    def test_texte_windows_garde_son_encodage(self):
        donnees = "Séance\nCafé\n".encode("cp1252")
        nouveau, _ = modifier.remplacer(donnees, ".txt", "Café", "Thé")
        self.assertEqual(nouveau, "Séance\nThé\n".encode("cp1252"))

    def odt(self, xml):
        chemin = self.d / "c.odt"
        with zipfile.ZipFile(chemin, "w") as z:
            z.writestr("mimetype", "application/vnd.oasis.opendocument.text", zipfile.ZIP_STORED)
            z.writestr("content.xml", f'<d xmlns:text="urn:t">{xml}</d>')
        return chemin

    def test_libreoffice(self):
        chemin = self.odt("<text:p>Le mot &amp; le reste</text:p>")
        self.assertEqual(modifier.paragraphes(chemin.read_bytes(), ".odt"), [("paragraphe 1", "Le mot & le reste")])
        nouveau, nombre = modifier.remplacer(chemin.read_bytes(), ".odt", "mot & le", "terme & ce")
        self.assertEqual(nombre, 1)
        self.assertEqual(modifier.paragraphes(nouveau, ".odt")[0][1], "Le terme & ce reste")
        chemin.write_bytes(nouveau)
        with zipfile.ZipFile(chemin) as z:
            self.assertEqual(z.namelist()[0], "mimetype")
            self.assertEqual(z.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)

    def test_libreoffice_texte_coupe_refuse(self):
        chemin = self.odt("<text:p>Le <text:span>mot</text:span> ici</text:p>")
        donnees = chemin.read_bytes()
        self.assertEqual(modifier.remplacer(donnees, ".odt", "Le mot", "Un mot"), (donnees, -1))


class TestValidation(Base):
    def test_apercu_ne_modifie_rien(self):
        self.ecrire_plan(self.plan_complet())
        avant = {p: p.read_bytes() for p in self.d.rglob("*") if p.is_file()}
        r = lancer("modifier.py", "apercu", str(self.d))
        self.assertEqual(r.returncode, 0, r.stdout)
        for attendu in ("Endroit demandé", "Références à mettre à jour", f"- {self.AVANT}", f"+ {self.APRES}",
                        "STATUS: EN_ATTENTE_DE_VALIDATION", "[1] Appliquer", "[2] Modifier", "[3] Annuler"):
            self.assertIn(attendu, r.stdout)
        self.assertEqual({p: p.read_bytes() for p in self.d.rglob("*") if p.is_file()}, avant)

    def test_rien_sans_jeton_valide(self):
        self.ecrire_plan(self.plan_complet())
        avant = (self.d / "Diapos/seance-1-diapos.pptx").read_bytes()
        self.assertNotEqual(lancer("modifier.py", "appliquer", str(self.d)).returncode, 0)
        r = lancer("modifier.py", "appliquer", str(self.d), "--jeton", "faux")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("rien n'a été modifié", r.stderr)
        self.assertEqual((self.d / "Diapos/seance-1-diapos.pptx").read_bytes(), avant)

    def test_plan_modifie_apres_l_apercu_refuse(self):
        self.ecrire_plan(self.plan_complet())
        jeton = self.jeton()
        plan = self.plan_complet()
        plan["modifications"][0]["apres"] = "Autre texte"
        self.ecrire_plan(plan)
        self.assertNotEqual(lancer("modifier.py", "appliquer", str(self.d), "--jeton", jeton).returncode, 0)

    def test_fichier_modifie_apres_l_apercu_refuse(self):
        self.ecrire_plan(self.plan_complet())
        jeton = self.jeton()
        (self.d / ".travail/seance-1/diapos.md").write_text(fixtures.diapos("OBJ1") + "- Retouche\n", encoding="utf-8")
        r = lancer("modifier.py", "appliquer", str(self.d), "--jeton", jeton)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("a changé depuis l'aperçu", r.stderr)

    def test_appliquer_met_tout_a_jour_et_sauvegarde(self):
        self.ecrire_plan(self.plan_complet())
        temoin = (self.d / "QCM/seance-1-qcm.docx").read_bytes()
        r = lancer("modifier.py", "appliquer", str(self.d), "--jeton", self.jeton())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("appliquée à 4 fichier(s)", r.stdout)
        for relatif in ("Diapos/seance-1-diapos.pptx", "Diapos/seance-2-diapos.pptx",
                        ".travail/seance-1/diapos.md", ".travail/seance-2/diapos.md"):
            self.assertIn(self.APRES, texte_de(self.d / relatif))
            self.assertNotIn(self.AVANT, texte_de(self.d / relatif))
        self.assertEqual((self.d / "QCM/seance-1-qcm.docx").read_bytes(), temoin)
        self.assertFalse((self.d / modifier.PLAN).exists())
        journal = json.loads((self.d / modifier.JOURNAL).read_text(encoding="utf-8"))
        self.assertEqual(journal[0]["demande"], "Reformuler la phrase")
        histo = lancer("versions.py", "historique", dossier=self.d).stdout
        self.assertIn("Avant modification : Reformuler la phrase", histo)
        self.assertIn("Modification : Reformuler la phrase", histo)

    def test_retour_en_arriere_possible(self):
        self.ecrire_plan(self.plan_complet())
        chemin = self.d / "Diapos/seance-1-diapos.pptx"
        origine = chemin.read_bytes()
        self.assertEqual(lancer("modifier.py", "appliquer", str(self.d), "--jeton", self.jeton()).returncode, 0)
        version = [l for l in lancer("versions.py", "historique", dossier=self.d).stdout.splitlines()
                   if "Avant modification" in l][0].split()[0]
        r = lancer("versions.py", "restaurer", version, "Diapos/seance-1-diapos.pptx", dossier=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(chemin.read_bytes(), origine)

    def test_annule_critique_et_validation_precedentes(self):
        fixtures.ecrire_critique(self.d)
        qualite.valider(self.d, "livrables", "valider")
        self.assertEqual(qualite.construire_rapport(self.d, "livrables")["statut"], "HUMAN_VALIDATED")
        # La fixture date la critique dans le futur : on la ramène avant la modification.
        critique = self.d / ".travail/revue/critique.json"
        os.utime(critique, (1, 1))
        self.ecrire_plan(self.plan_complet())
        self.assertEqual(lancer("modifier.py", "appliquer", str(self.d), "--jeton", self.jeton()).returncode, 0)
        rapport = qualite.construire_rapport(self.d, "livrables")
        self.assertNotEqual(rapport["statut"], "HUMAN_VALIDATED")
        self.assertEqual(rapport["critique"], "obsolète")

    def test_controle_signale_un_probleme_cree(self):
        plan = {"demande": "Retirer le lien", "references": ["zzz"], "modifications": [
            {"fichier": ".travail/seance-1/diapos.md", "role": "cible", "avant": "> Objectif : OBJ1", "apres": "> Note"}]}
        self.ecrire_plan(plan)
        r = lancer("modifier.py", "appliquer", str(self.d), "--jeton", self.jeton())
        self.assertIn("Problème : seance-1 : OBJ1 n'est pas couvert dans diapos.md.", r.stdout)


class TestReferences(Base):
    def test_reference_oubliee_bloque_l_application(self):
        plan = self.plan_complet()
        oubliee = plan["modifications"].pop(1)
        self.ecrire_plan(plan)
        r = lancer("modifier.py", "apercu", str(self.d))
        self.assertEqual(r.returncode, 1)
        self.assertIn("STATUS: PLAN_INCOMPLET", r.stdout)
        self.assertIn(oubliee["fichier"], r.stdout)
        self.assertNotIn("JETON", r.stdout)
        r = lancer("modifier.py", "appliquer", str(self.d), "--jeton", modifier.preparer(self.d)["jeton"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(self.AVANT, texte_de(self.d / "Diapos/seance-1-diapos.pptx"))

    def test_fichier_ignore_avec_raison(self):
        plan = self.plan_complet()
        plan["modifications"].pop(1)
        plan["ignorer"] = {"Diapos/seance-2-diapos.pptx": "Le prof garde cette version."}
        self.ecrire_plan(plan)
        r = lancer("modifier.py", "apercu", str(self.d))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("Le prof garde cette version.", r.stdout)
        plan["ignorer"] = {"Diapos/seance-2-diapos.pptx": " "}
        self.ecrire_plan(plan)
        self.assertIn("doit avoir une raison", lancer("modifier.py", "apercu", str(self.d)).stderr)

    def test_nouveau_texte_qui_garde_le_terme_n_est_pas_un_oubli(self):
        (self.d / "Cours/note.txt").write_text("Le nutriment passe.\n", encoding="utf-8")
        plan = {"demande": "Préciser", "references": ["nutriment"], "modifications": [
            {"fichier": "Cours/note.txt", "role": "cible", "avant": "Le nutriment passe.", "apres": "Le nutriment passe dans le sang."}]}
        self.ecrire_plan(plan)
        self.assertEqual(modifier.preparer(self.d)["non_traites"], {})

    def test_deuxieme_occurrence_dans_un_fichier_du_plan_bloque(self):
        (self.d / "Cours/note.txt").write_text("Un chyme ici.\nUn chyme là.\n", encoding="utf-8")
        plan = {"demande": "Changer", "references": ["chyme"], "modifications": [
            {"fichier": "Cours/note.txt", "role": "cible", "avant": "Un chyme ici.", "apres": "Une bouillie ici."}]}
        self.ecrire_plan(plan)
        self.assertIn("Cours/note.txt", modifier.preparer(self.d)["non_traites"])

    def test_fichier_illisible_annonce_au_prof(self):
        (self.d / "Cours/ancien.pdf").write_bytes(b"%PDF")
        self.ecrire_plan(self.plan_complet())
        self.assertIn("Cours/ancien.pdf", lancer("modifier.py", "apercu", str(self.d)).stdout)


class TestPlanInvalide(Base):
    def refuse(self, attendu, **remplacement):
        plan = self.plan_complet()
        plan.update(remplacement)
        self.ecrire_plan(plan)
        r = lancer("modifier.py", "apercu", str(self.d))
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn(attendu, r.stdout + r.stderr)

    def ligne(self, **champs):
        return [{"fichier": "Cours/cours.txt", "role": "cible", "avant": "estomac", "apres": "x", **champs}]

    def test_chemins_hors_du_chapitre_refuses(self):
        (self.d.parent / "secret.txt").write_text("estomac", encoding="utf-8")
        for fichier in ("../secret.txt", str(self.d.parent / "secret.txt"), ".git/config", ".travail/revue/etat.md"):
            with self.subTest(fichier):
                self.refuse("Chemin refusé", modifications=self.ligne(fichier=fichier))

    def test_format_non_modifiable(self):
        (self.d / "Cours/a.pdf").write_bytes(b"%PDF")
        self.refuse("Format non modifiable", modifications=self.ligne(fichier="Cours/a.pdf"))

    def test_fichier_ouvert_refuse(self):
        chemin = self.d / "Diapos/seance-1-diapos.pptx"
        (chemin.parent / f"~${chemin.name}").touch()
        self.refuse("est ouvert dans un logiciel", modifications=self.ligne(fichier="Diapos/seance-1-diapos.pptx"))

    def test_texte_introuvable_ou_ambigu(self):
        self.refuse("est introuvable", modifications=self.ligne(avant="absent du fichier"))
        (self.d / "Cours/double.txt").write_text("chat\nchat\n", encoding="utf-8")
        self.refuse("apparaît 2 fois", modifications=self.ligne(fichier="Cours/double.txt", avant="chat"))

    def test_contenu_du_plan_exige(self):
        self.refuse("Le plan ne contient aucune modification", modifications=[])
        self.refuse("au moins une référence", references=[])
        self.refuse("indiquer la demande", demande=" ")
        self.refuse("rôle « cible »", modifications=self.ligne(role="reference"))
        self.refuse("Modification invalide", modifications=self.ligne(role="autre"))
        self.refuse("Modification invalide", modifications=self.ligne(apres="deux\nlignes"))
        (self.d / modifier.PLAN).write_text("{pas du json", encoding="utf-8")
        self.assertIn("illisible", lancer("modifier.py", "apercu", str(self.d)).stderr)

    def test_sans_plan(self):
        self.assertIn("Aucun plan", lancer("modifier.py", "apercu", str(self.d)).stderr)


if __name__ == "__main__":
    unittest.main()
