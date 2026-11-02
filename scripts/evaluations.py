#!/usr/bin/env python3
"""Lit et contrôle les questions d'évaluation, quel que soit leur type.

Pour ajouter un type, il suffit d'ajouter une entrée au dictionnaire TYPES.
Dans un sujet, une ligne « Type : vrai-faux » sous « ## Question N » choisit le type de la question.
"""
import re
from dataclasses import dataclass, field

# « OBJ » et non « O » : en sciences, O2 et O3 désignent aussi des molécules.
OBJECTIF = re.compile(r"\bOBJ\d+\b")
CHOIX_MINIMUM = 3
QUESTION = re.compile(r"^##\s*Question\s+(\d+).*$", re.MULTILINE | re.IGNORECASE)
TYPE_QUESTION = re.compile(r"^Type\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
CHOIX = re.compile(r"^([A-Z])[.)]\s+(\S.*?)\s*$", re.MULTILINE)
LIGNE_REPONSE = re.compile(r"^[-*\s]*Question\s+(\d+)\s*:\s*(.*)$", re.MULTILINE | re.IGNORECASE)
LIGNE_TABLEAU = re.compile(r"^\|\s*(\d+)\s*\|(.*)\|\s*$", re.MULTILINE)
LETTRES = re.compile(r"\**\s*([A-Z](?![A-Za-zÀ-ÿ])(?:\s*(?:,|/|&|et)\s*[A-Z](?![A-Za-zÀ-ÿ]))*)")


@dataclass
class Question:
    numero: int
    type: str
    enonce: str
    choix: list = field(default_factory=list)


@dataclass
class Reponse:
    numero: int
    texte: str
    objectifs: list

    @property
    def lettres(self):
        m = LETTRES.match(self.texte)
        return re.findall(r"[A-Z]", m.group(1)) if m else []


def lire_sujet(texte, type_defaut):
    """Renvoie les questions d'un sujet, dans l'ordre."""
    parties = QUESTION.split(texte)
    questions = []
    for numero, bloc in zip(parties[1::2], parties[2::2]):
        indication = TYPE_QUESTION.search(bloc)
        type_question = indication.group(1).casefold().replace(" ", "-") if indication else type_defaut
        questions.append(Question(int(numero), type_question, TYPE_QUESTION.sub("", bloc).strip(), CHOIX.findall(bloc)))
    return questions


def lire_corrige(texte):
    """Renvoie toutes les réponses : lignes « Question 1 : B (OBJ1) — … » ou tableau « | 1 | … | »."""
    trouvees = LIGNE_REPONSE.findall(texte) + LIGNE_TABLEAU.findall(texte)
    return [Reponse(int(n), reste.strip(), OBJECTIF.findall(reste)) for n, reste in trouvees]


def verifier_qcm(question, reponse):
    numero = question.numero
    if reponse is None:
        return []
    lettres = [c[0] for c in question.choix]
    donnees = reponse.lettres
    problemes = []
    if len(donnees) > 1:
        problemes.append(f"la question {numero} du QCM a plusieurs bonnes réponses : {', '.join(donnees)}.")
    problemes += [f"la réponse {d} de la question {numero} n'existe pas dans le QCM."
                  for d in donnees if d not in lettres]
    if not donnees:
        problemes.append(f"la réponse à la question {numero} du QCM n'indique aucune lettre.")
    textes = [c[1].casefold() for c in question.choix]
    if len(set(textes)) != len(textes):
        problemes.append(f"la question {numero} du QCM propose deux fois le même choix.")
    return problemes


def verifier_vrai_faux(question, reponse):
    if reponse is not None and not re.match(r"\**\s*(vrai|faux)\b", reponse.texte, re.IGNORECASE):
        return [f"la réponse à la question {question.numero} doit être « Vrai » ou « Faux »."]
    return []


def verifier_redige(question, reponse):
    if reponse is not None and not OBJECTIF.sub("", reponse.texte).strip(" |()—-"):
        return [f"la réponse attendue à la question {question.numero} est vide."]
    return []


TYPES = {
    "qcm": verifier_qcm,
    "vrai-faux": verifier_vrai_faux,
    "question-ouverte": verifier_redige,
    "exercice": verifier_redige,
    "etude-de-cas": verifier_redige,
    "probleme": verifier_redige,
    "reflexion": verifier_redige,
}


def verifier(sujet, corrige, type_defaut):
    """Contrôle un sujet et son corrigé : chaque type applique ses règles à chaque question."""
    questions = lire_sujet(sujet, type_defaut)
    reponses = {}
    problemes = []
    for reponse in lire_corrige(corrige):
        precedente = reponses.setdefault(reponse.numero, reponse)
        # Deux lignes rédigées peuvent se compléter (réponse et barème) ; deux lettres différentes, non.
        if precedente.lettres and reponse.lettres and precedente.lettres != reponse.lettres:
            problemes.append(f"le corrigé se contredit sur la question {reponse.numero} : "
                             f"« {precedente.texte} » puis « {reponse.texte} ».")
    for question in questions:
        controle = TYPES.get(question.type)
        if controle is None:
            problemes.append(f"la question {question.numero} a un type inconnu : {question.type} "
                             f"(types possibles : {', '.join(TYPES)}).")
            continue
        reponse = reponses.get(question.numero)
        if reponse is None:
            problemes.append(f"le corrigé ne donne pas la réponse à la question {question.numero}.")
        problemes += controle(question, reponse)
    return problemes
