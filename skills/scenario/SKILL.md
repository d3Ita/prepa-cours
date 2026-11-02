---
name: scenario
description: Rédige le scénario pédagogique minuté d'une séance à partir du cours de l'enseignant et du découpage de objectifs.md.
argument-hint: "[numéro de séance]"
---

# Écrire le scénario d'une séance

Lis le cours source et `objectifs.md`. Lis aussi `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md` et le fichier de la matière dans `${CLAUDE_PLUGIN_ROOT}/references/matieres/` (`autres.md` s'il n'y en a pas), et applique-les. Écris ensuite `seance-N/scenario.md` pour la séance demandée :

```markdown
# Séance 1 : titre
Niveau, durée de la séance, matériel nécessaire

## 0-10 min — Accroche
- Objectif visé : OBJ1
- Le prof : ce qu'il dit ou fait
- Les élèves : ce qu'ils font
- Support : diapos concernées

## 10-25 min — Activité
- Objectif visé : OBJ1
```

Génère ensuite la version à lire depuis le dossier du cours, en ajoutant `--ecraser` seulement si tu as sauvegardé avant et que le prof a demandé cette mise à jour :

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" docx seance-N/scenario.md seance-N/scenario.docx --outils "${CLAUDE_PLUGIN_DATA}"`

## Règles

- La durée vient de `objectifs.md` : les phases s'enchaînent sans trou et s'arrêtent exactement à la fin de la séance.
- Traite tous les objectifs attribués à la séance, et seulement le contenu prévu pour elle.
- À partir de la séance 2, commence par un rappel de la séance précédente.
- Termine par le QCM (10 min), sauf si le prof a décidé de le faire hors de la classe.
- Respecte la durée maximale sans activité des élèves indiquée pour le niveau. Sur une séance de plus d'1 h 30, prévois une pause si le prof le souhaite.
- Termine le document par ce qu'il faut couper en cas de retard.
- N'invente aucun contenu : tout ajout porte la mention `[À VÉRIFIER]`.
