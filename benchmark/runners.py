"""Les exécuteurs du benchmark : ce qui produit les sorties d'un cas dans un mode donné.

Pour ajouter un exécuteur, il suffit d'écrire une classe avec `simulated`, `nom` et `executer`.
"""
import shlex
import subprocess
import sys
import time
from pathlib import Path

from cas import ecrire_source, materialiser

RACINE = Path(__file__).resolve().parent.parent
PROMPTS = Path(__file__).resolve().parent / "prompts"
SINGLE_AGENT, MULTI_AGENT = "single_agent", "multi_agent"
MODES = (SINGLE_AGENT, MULTI_AGENT)
TERMINE, ECHEC = "completed", "failed"
OUTILS = "Read,Write,Edit,Bash,Glob,Grep"


class FixtureRunner:
    """Recopie les sorties écrites à la main, pour tester le banc d'essai sans modèle de langage.

    Les deux modes reçoivent les mêmes fichiers : leur comparaison n'a aucune valeur et reste marquée comme simulée.
    """

    nom = "fixture"
    simulated = True
    modele = None

    def executer(self, cas, mode, chapitre, journal):
        materialiser(cas, chapitre)
        return {"run_status": TERMINE, "generation_time": None, "human_interventions_recorded": False}


class ClaudeRunner:
    """Lance une vraie génération avec Claude Code, sans interaction : le temps mesuré est réel.

    Personne ne valide pendant ce mode : les validations sont automatiques, et les interventions humaines restent non mesurées.
    """

    nom = "claude"
    simulated = False

    def __init__(self, commande="claude", modele=None, delai=1800, max_cycles=2):
        self.commande = shlex.split(commande) if isinstance(commande, str) else list(commande)
        self.modele, self.delai, self.max_cycles = modele, delai, max_cycles

    def construire_commande(self, cas, mode):
        gabarit = (PROMPTS / f"{mode}.md").read_text(encoding="utf-8")
        consigne = gabarit.format(cours=cas.cours, consignes=cas.consignes, racine=RACINE, python=sys.executable, max_cycles=self.max_cycles)
        commande = [*self.commande, "-p", consigne, "--plugin-dir", str(RACINE), "--allowedTools",
                    OUTILS + (",Agent" if mode == MULTI_AGENT else ""), "--output-format", "json"]
        if mode == SINGLE_AGENT:
            commande += ["--disallowedTools", "Agent"]
        if self.modele:
            commande += ["--model", self.modele]
        return commande

    def executer(self, cas, mode, chapitre, journal):
        ecrire_source(cas, chapitre)
        # Le chapitre a son propre historique : les sauvegardes ne touchent jamais le dépôt du plugin.
        subprocess.run(["git", "init", "-q"], cwd=chapitre, check=True)
        debut = time.monotonic()
        try:
            r = subprocess.run(self.construire_commande(cas, mode), cwd=chapitre, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=self.delai, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return self.echec(journal, f"Délai de {self.delai} s dépassé.")
        except OSError as e:
            return self.echec(journal, f"Lancement impossible : {e}")
        duree = round(time.monotonic() - debut, 2)
        journal.write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
        if r.returncode:
            return {"run_status": ECHEC, "error": f"Code de sortie {r.returncode}.", "generation_time": duree, "human_interventions_recorded": False}
        return {"run_status": TERMINE, "generation_time": duree, "human_interventions_recorded": False}

    @staticmethod
    def echec(journal, message):
        journal.write_text(message, encoding="utf-8")
        return {"run_status": ECHEC, "error": message, "generation_time": None, "human_interventions_recorded": False}
