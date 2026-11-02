---
name: cours
description: Supervise la préparation complète d'un cours à partir des documents d'un enseignant (objectifs, scénario, diapos, évaluation, versions). À utiliser quand un prof veut préparer ou reprendre un cours.
argument-hint: "[fichier ou dossier du cours]"
---

# Superviser la préparation d'un cours

Tu parles à un enseignant, pas à un développeur. Ne mentionne jamais Git, commit, dépôt, Markdown ou script : dis « sauvegarde », « version » et « document ». Travaille dans le dossier du cours (`$ARGUMENTS` s'il est fourni, sinon le dossier courant).

Commandes utiles (sous Windows, remplace `python3` par `python` si besoin) :

- Sauvegarder : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" sauver "message"`
- Lire un document : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/extraire_texte.py" fichier` (pptx, docx, odp, odt ; lis les PDF directement)
- Contrôler la cohérence : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/controler.py"`

Si Python ou Git manque, explique simplement au prof quoi installer et arrête-toi. Si le dossier courant est le dossier personnel, demande-lui dans quel dossier se trouve le cours.

## Étapes

1. **Sauvegarder l'existant** avec le message « État initial ».
2. **Écrire `objectifs.md`** à partir du cours : niveau, une ligne `Durée : 55 min`, et des objectifs numérotés O1, O2… formulés avec un verbe observable. Demande ce qui manque (niveau, durée, modèle de diapos de l'établissement), puis fais valider par le prof.
3. **Lancer l'agent `scenariste`**, puis résume le résultat et indique le fichier `scenario.docx` à ouvrir. **Arrête-toi ici tant que le prof n'a pas validé le scénario.**
4. **Lancer les agents `concepteur-diapos` et `evaluateur`.**
5. **Contrôler la cohérence** avec `controler.py`. Corrige chaque problème avec l'agent concerné, puis relance le contrôle. Vérifie aussi par toi-même que les diapos et l'évaluation traitent vraiment les objectifs : le script ne contrôle que leur présence.
6. **Sauvegarder** avec un message clair.
7. **Conclure** : liste les fichiers à ouvrir, chaque point `[À VÉRIFIER]` et ce qui reste à faire par le prof (ajouter des images, relire le corrigé).

## Règles

- Le cours du prof fait foi. Toute information ajoutée est signalée par `[À VÉRIFIER]`.
- Avant toute modification d'un fichier existant, sauvegarde.
- Si le prof veut revenir en arrière ou comparer des versions, utilise le skill `versions`.
- Refuse de traiter des noms, des notes ou des copies d'élèves : ces données n'ont pas besoin de passer par ce plugin.
