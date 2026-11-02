---
name: cours
description: Supervise la préparation complète d'un cours à partir d'un fichier texte, Word ou LibreOffice, et le range par niveau, classe et chapitre, selon la matière (découpage en séances, scénarios, diapos, QCM, versions). À utiliser quand un prof veut préparer ou reprendre un cours.
argument-hint: "[fichier du cours] [niveau] [classe] [matière] [chapitre] [heures et séances]"
---

# Superviser la préparation d'un cours

Tu parles à un enseignant, pas à un développeur. Ne mentionne jamais Git, commit, dépôt, Markdown ou script : dis « sauvegarde », « version » et « document ». Demande fournie : `$ARGUMENTS`.

Commandes utiles, à lancer depuis le dossier du chapitre (sous Windows, remplace `python3` par `python` si besoin) :

- Sauvegarder : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" sauver "message"`
- Lire le cours : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/extraire_texte.py" fichier` (txt, docx, odt, et aussi pptx et odp ; lis les PDF directement)
- Contrôler la cohérence : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/controler.py"`

Si Python ou Git manque, explique simplement au prof quoi installer et arrête-toi.

## Étapes

1. **Trouver le chapitre** avec le skill `organiser` : montre ce qui existe déjà, demande le niveau, la classe et le titre du chapitre s'ils manquent, puis crée le chapitre. Si le chapitre existe déjà, reprends-le sans rien écraser. Travaille ensuite dans ce dossier et indique son chemin à chaque agent.
2. **Ranger le cours du prof** dans `Cours/` : copie-le avec `organiser.py ranger`, sans jamais déplacer l'original. Si plusieurs documents sont possibles, demande lequel utiliser.
3. **Sauvegarder l'existant** avec le message « État initial ».
4. **Lire le cours et découper** avec le skill `decoupage` : le prof indique la matière, les heures et les séances, et tu écris `.travail/objectifs.md`. **Arrête-toi tant qu'il n'a pas validé le découpage.**
5. **Lancer l'agent `scenariste` pour chaque séance**, en indiquant son numéro, puis résume les résultats et indique les fichiers `Cours/seance-N-scenario.docx` à ouvrir. **Arrête-toi tant que le prof n'a pas validé les scénarios.**
6. **Pour chaque séance, lancer l'agent `concepteur-diapos`, puis l'agent `evaluateur` pour le QCM de 5 questions.**
7. **Proposer une évaluation finale.** Lance `evaluateur` pour la créer seulement si le prof en veut une.
8. **Contrôler la cohérence** avec `controler.py`. Corrige chaque problème avec l'agent concerné, puis relance le contrôle. Vérifie aussi par toi-même que les diapos et les QCM traitent vraiment les objectifs : le script ne contrôle que leur présence.
9. **Sauvegarder** avec un message clair.
10. **Conclure** : montre le chemin du chapitre, les fichiers par dossier, chaque point `[À VÉRIFIER]` et ce qui reste à faire par le prof (ajouter des images, relire les corrigés).

## Règles

- Le cours du prof fait foi. Toute information ajoutée est signalée par `[À VÉRIFIER]`.
- Avant toute modification d'un fichier existant, sauvegarde.
- Chaque fichier produit va dans son dossier : `Cours`, `Diapos`, `QCM`, `Evaluations` ou `Corrections`.
- Si le prof veut retrouver, classer ou réutiliser un cours, utilise le skill `organiser`.
- Si les heures changent, utilise le skill `decoupage`.
- Pour adapter un cours à un autre niveau, suis `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md`.
- Si le prof veut revenir en arrière ou comparer des versions, utilise le skill `versions`.
- Refuse de traiter des noms, des notes ou des copies d'élèves : ces données n'ont pas besoin de passer par ce plugin.
