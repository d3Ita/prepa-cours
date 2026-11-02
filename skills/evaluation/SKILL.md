---
name: evaluation
description: Crée une évaluation finale facultative et son corrigé en Word/LibreOffice Writer, sur l'ensemble du cours. Pour le QCM d'une séance, utiliser le skill qcm. Ne corrige pas de copies d'élèves.
---

# Créer l'évaluation finale

Crée-la seulement si le prof en demande une, en travaillant dans le dossier du chapitre. Lis `.travail/objectifs.md`, `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md` et le fichier de la matière dans `${CLAUDE_PLUGIN_ROOT}/references/matieres/` (`autres.md` s'il n'y en a pas), et applique-les. Écris ensuite `.travail/evaluation.md` et `.travail/corrige.md`. Formats disponibles : titres (`#`, `##`), puces (`- `), listes numérotées (`1. `), `**gras**`, tableaux Markdown, et `[réponse: 4]` seul sur une ligne pour laisser 4 lignes de réponse à l'élève.

```markdown
# Évaluation : titre
Durée : 30 min. Total : 20 points.

## Question 1 (5 points)
Énoncé de la question.
[réponse: 4]
```

Génère ensuite les fichiers à imprimer, le sujet dans `Evaluations` et le corrigé dans `Corrections` :

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" docx .travail/evaluation.md Evaluations/evaluation.docx --outils "${CLAUDE_PLUGIN_DATA}"`

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" docx .travail/corrige.md Corrections/evaluation-corrige.docx --outils "${CLAUDE_PLUGIN_DATA}"`

Si un `.docx` existe déjà, sauvegarde avec `versions.py sauver`, demande au prof, puis ajoute `--ecraser` seulement s'il accepte.

## Règles

- Chaque question évalue un objectif : indique OBJ1, OBJ2… dans le corrigé, pas dans le sujet.
- N'évalue que ce qui a été vu dans les scénarios.
- Écris chaque barème sous la forme `(5 points)` et le total sous la forme `Total : 20 points`.
- Le temps estimé pour un élève est réaliste par rapport à la durée prévue.
- Le corrigé donne la réponse attendue et les critères d'attribution des points.
- Signale au prof de relire le corrigé. Ajoute `[À VÉRIFIER]` à toute réponse absente du cours.
- Refuse de traiter des copies ou des noms d'élèves dans cette version : ce sont des données personnelles.
