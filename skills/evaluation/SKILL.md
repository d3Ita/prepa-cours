---
name: evaluation
description: Crée une évaluation et son corrigé en Word/LibreOffice Writer, alignés sur objectifs.md et scenario.md. Ne corrige pas de copies d'élèves.
---

# Créer l'évaluation

Écris `evaluation.md` et `corrige.md`. Formats disponibles : titres (`#`, `##`), puces (`- `), listes numérotées (`1. `), `**gras**`, tableaux Markdown, et `[réponse: 4]` seul sur une ligne pour laisser 4 lignes de réponse à l'élève.

```markdown
# Évaluation : titre
Durée : 30 min. Total : 20 points.

## Question 1 (5 points)
Énoncé de la question.
[réponse: 4]
```

Génère ensuite les fichiers à imprimer :

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" docx evaluation.md evaluation.docx --outils "${CLAUDE_PLUGIN_DATA}"`

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" docx corrige.md corrige.docx --outils "${CLAUDE_PLUGIN_DATA}"`

Si un `.docx` existe déjà, sauvegarde avec `versions.py sauver`, demande au prof, puis ajoute `--ecraser` seulement s'il accepte.

## Règles

- Chaque question évalue un objectif : indique O1, O2… dans `corrige.md`, pas dans le sujet.
- N'évalue que ce qui a été vu dans le scénario.
- Écris chaque barème sous la forme `(5 points)` et le total sous la forme `Total : 20 points`.
- Le temps estimé pour un élève est réaliste par rapport à la durée prévue.
- Le corrigé donne la réponse attendue et les critères d'attribution des points.
- Signale au prof de relire le corrigé. Ajoute `[À VÉRIFIER]` à toute réponse absente du cours.
- Refuse de traiter des copies ou des noms d'élèves dans cette version : ce sont des données personnelles.
