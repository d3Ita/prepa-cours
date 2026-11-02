---
name: scenario
description: Rédige le scénario pédagogique minuté d'une séance à partir du cours de l'enseignant et de objectifs.md.
---

# Écrire le scénario d'une séance

Lis le cours source et `objectifs.md`, puis écris `scenario.md` :

```markdown
# Titre de la séance
Niveau, durée totale, matériel nécessaire

## 0-10 min — Accroche
- Objectif visé : O1
- Le prof : ce qu'il dit ou fait
- Les élèves : ce qu'ils font
- Support : diapos concernées

## 10-25 min — Activité
- Objectif visé : O2
```

Génère ensuite la version à lire, en ajoutant `--ecraser` seulement si tu as sauvegardé avant et que le prof a demandé cette mise à jour :

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" docx scenario.md scenario.docx --outils "${CLAUDE_PLUGIN_DATA}"`

## Règles

- Les phases s'enchaînent sans trou et s'arrêtent à la durée de la séance.
- Chaque objectif apparaît dans au moins une phase.
- Pas plus de 15 minutes sans activité des élèves.
- Termine par ce qu'il faut couper en cas de retard.
- N'invente aucun contenu : tout ajout porte la mention `[À VÉRIFIER]`.
