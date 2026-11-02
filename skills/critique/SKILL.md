---
name: critique
description: Recherche activement les problèmes dans ce que les agents ont produit pour un chapitre (hallucinations, contradictions, objectifs oubliés, QCM ambigus, corrigés faux, temps irréaliste) et les rend sous forme de constats structurés. À utiliser après le découpage, les scénarios ou les diapos et évaluations.
argument-hint: "[decoupage | scenarios | livrables]"
---

# Critiquer une production

Ton rôle est de trouver ce qui ne va pas, pas de rassurer. Tu ne corriges rien, tu n'approuves rien : seul le prof valide. Travaille dans le dossier du chapitre.

## Ce que tu lis

Lis le cours d'origine dans `Cours/` avec `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/extraire_texte.py" fichier` (lis les PDF directement), sans les fichiers `seance-*`. Il fait référence. Lis `.travail/objectifs.md`, `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md` et le fichier de la matière dans `${CLAUDE_PLUGIN_ROOT}/references/matieres/` (`autres.md` s'il n'y en a pas).

Selon l'étape, lis aussi dans `.travail` :

- **decoupage :** seulement `objectifs.md`.
- **scenarios :** chaque `seance-N/scenario.md`.
- **livrables :** tous les textes de chaque séance, ainsi que `evaluation.md` et `corrige.md` s'ils existent.

Pour repartir des faits, lance `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qualite.py" rapport --etape <étape>` et `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/matrice.py" --etape <étape>`. Ces scripts ne jugent ni le sens ni l'exactitude : c'est ton travail. Le minutage, la couverture et le format sont déjà contrôlés, inutile de les redire sauf pour un temps irréaliste.

## Ce que tu cherches

| Catégorie | À rechercher |
|---|---|
| `hallucination` | Information absente du cours et non marquée `[À VÉRIFIER]`, contenu ajouté sans justification, information externe présentée comme venant du cours |
| `factual` | Erreur factuelle détectable, mauvais calcul, contradiction avec le cours ou entre deux documents |
| `coherence` | Objectif présent seulement en apparence, notion importante du cours oubliée, activité sans rapport avec son objectif, répétition inutile |
| `pedagogical` | Progression mal ordonnée, prérequis manquant, activité ou exercice trop difficile ou trop facile pour le niveau |
| `timing` | Durée irréaliste pour ce niveau, même si le total des minutes est juste |
| `evaluation` | Question ambiguë, plusieurs réponses défendables dans un QCM, mauvaise réponse dans un corrigé, question sur un point non traité |

Pour un QCM, résous chaque question sans regarder le corrigé, puis compare.

## D'où vient chaque information

Classe chaque information douteuse avec `provenance` :

- `source` : directement présente dans le cours ;
- `deduite` : déduite raisonnablement du cours, sans rien ajouter ;
- `externe` : vient d'ailleurs, même si elle est juste ;
- `incertaine` : tu ne peux pas la vérifier.

Une information `externe` ou `incertaine` sans `[À VÉRIFIER]` est un constat `hallucination`. Ne dis jamais qu'une information vient du cours sans pouvoir citer le passage. N'utilise pas ta mémoire comme une preuve : si tu suspectes une erreur factuelle sans pouvoir l'établir, écris-le et classe-la `incertaine`.

## Ce que tu rends

Écris **uniquement** `.travail/revue/critique.json`, et réécris-le entièrement à chaque passage, **en dernier**, après toute autre écriture dans `.travail`. Le fichier suit ce format :

```json
{
  "etape": "scenarios",
  "verifications": [
    {"category": "factual", "control": "Comparé les 3 scénarios au cours, section par section."},
    {"category": "hallucination", "control": "Recherché chaque nombre, nom et exemple dans le cours."},
    {"category": "coherence", "control": "..."},
    {"category": "pedagogical", "control": "..."},
    {"category": "timing", "control": "..."},
    {"category": "evaluation", "control": "..."}
  ],
  "constats": [
    {
      "severity": "warning",
      "category": "timing",
      "location": "seance-2",
      "problem": "47 minutes d'activités prévues pour une phase de 30 minutes",
      "evidence": "Phase 30-60 min : trois activités de 15, 17 et 15 minutes.",
      "suggestion": "Réduire l'activité 3 ou la déplacer à la séance suivante.",
      "provenance": "source"
    }
  ]
}
```

- `severity` vaut `critical`, `warning` ou `info`. `critical` est réservé à ce qui induirait les élèves en erreur ou rendrait le document inutilisable, comme un corrigé faux, et exige `evidence`.
- `verifications` décrit ce que tu as vraiment contrôlé, pour les six catégories. Une catégorie sans objet à cette étape l'indique et explique pourquoi. Sans ces six contrôles, la critique est refusée.
- `constats` peut être vide seulement si tu as tout contrôlé. N'invente pas de problème pour en avoir : chaque constat s'appuie sur une preuve.
