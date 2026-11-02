---
name: cours
description: Supervise la préparation complète d'un cours à partir d'un fichier texte, Word ou LibreOffice, selon le niveau de la classe et la matière (découpage en séances, scénarios, diapos, QCM, versions). À utiliser quand un prof veut préparer ou reprendre un cours.
argument-hint: "[fichier du cours] [niveau] [matière] [heures et séances]"
---

# Superviser la préparation d'un cours

Tu parles à un enseignant, pas à un développeur. Ne mentionne jamais Git, commit, dépôt, Markdown ou script : dis « sauvegarde », « version » et « document ». Travaille dans le dossier du cours. Demande fournie : `$ARGUMENTS`.

Commandes utiles (sous Windows, remplace `python3` par `python` si besoin) :

- Sauvegarder : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" sauver "message"`
- Lire le cours : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/extraire_texte.py" fichier` (txt, docx, odt, et aussi pptx et odp ; lis les PDF directement)
- Contrôler la cohérence : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/controler.py"`

Si Python ou Git manque, explique simplement au prof quoi installer et arrête-toi. Si le dossier courant est le dossier personnel, demande-lui dans quel dossier se trouve le cours.

## Étapes

1. **Sauvegarder l'existant** avec le message « État initial ».
2. **Lire le cours.** Si le dossier contient plusieurs documents, demande lequel utiliser.
3. **Découper** avec le skill `decoupage` : le prof indique le niveau de la classe, la matière, les heures et les séances, et tu écris `objectifs.md`. **Arrête-toi tant qu'il n'a pas validé le découpage.**
4. **Lancer l'agent `scenariste` pour chaque séance**, en indiquant son numéro, puis résume les résultats et indique les fichiers `seance-N/scenario.docx` à ouvrir. **Arrête-toi tant que le prof n'a pas validé les scénarios.**
5. **Pour chaque séance, lancer l'agent `concepteur-diapos`, puis l'agent `evaluateur` pour le QCM de 5 questions.**
6. **Proposer une évaluation finale.** Lance `evaluateur` pour la créer seulement si le prof en veut une.
7. **Contrôler la cohérence** avec `controler.py`. Corrige chaque problème avec l'agent concerné, puis relance le contrôle. Vérifie aussi par toi-même que les diapos et les QCM traitent vraiment les objectifs : le script ne contrôle que leur présence.
8. **Sauvegarder** avec un message clair.
9. **Conclure** : montre les fichiers de chaque séance, chaque point `[À VÉRIFIER]` et ce qui reste à faire par le prof (ajouter des images, relire les corrigés).

## Règles

- Le cours du prof fait foi. Toute information ajoutée est signalée par `[À VÉRIFIER]`.
- Avant toute modification d'un fichier existant, sauvegarde.
- Si les heures changent, utilise le skill `decoupage`.
- Pour adapter un cours à un autre niveau, suis `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md` et crée un nouveau dossier.
- Si le prof veut revenir en arrière ou comparer des versions, utilise le skill `versions`.
- Refuse de traiter des noms, des notes ou des copies d'élèves : ces données n'ont pas besoin de passer par ce plugin.
