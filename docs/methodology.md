# Méthodologie d'évaluation

**État actuel : aucune expérience n'a été menée.** Ce document décrit une question de recherche, des hypothèses à tester et un protocole. Il ne contient aucun résultat.

## Question de recherche

Une architecture multi-agent spécialisée améliore-t-elle la qualité et la cohérence de supports pédagogiques générés par un modèle de langage, par rapport à une architecture à agent unique ?

## Hypothèses à tester

| | Hypothèse | Mesure principale |
|---|---|---|
| H1 | L'architecture multi-agent améliore la couverture des objectifs | `objective_coverage` |
| H2 | L'architecture multi-agent réduit les erreurs critiques | `critical_error_count`, évaluation humaine |
| H3 | L'architecture multi-agent augmente le temps de génération | `generation_time` |
| H4 | La critique automatique réduit les interventions humaines nécessaires | `human_interventions` |

Ces hypothèses peuvent être infirmées. Un résultat nul ou défavorable au mode multi-agent reste un résultat à publier.

## Conditions comparées

- **Mode A, agent unique :** une seule conversation écrit tous les documents, sans sous-agent, critique ni révision ([consigne](../benchmark/prompts/single_agent.md)).
- **Mode B, multi-agent :** le skill `cours`, avec ses agents, sa critique et sa boucle limitée de révisions ([consigne](../benchmark/prompts/multi_agent.md)).

Les deux modes partent du même cours, ont les mêmes consignes, le même modèle et les mêmes formats de sortie, et sont mesurés par le même code.

## Protocole

1. **Préenregistrer** le corpus, les hypothèses et l'analyse avant de voir les résultats.
2. **Constituer le corpus :** des cours réels ou synthétiques, de matières et de niveaux variés, avec le droit de les utiliser. Les cours actuels de `benchmark/courses` sont trop peu nombreux et trop courts pour conclure.
3. **Générer** plusieurs fois chaque cours dans chaque mode, car les résultats varient d'une exécution à l'autre : `python3 benchmark/run.py run --runner claude --i-accept-llm-costs --repetitions N --model NOM`.
4. **Mesurer** automatiquement les indicateurs (voir ci-dessous).
5. **Faire évaluer à l'aveugle** par des enseignants avec la [grille humaine](../human_evaluation/rubric.md), sans leur indiquer le mode utilisé.
6. **Analyser** avec des comparaisons appariées par cours, en rapportant les tailles d'effet et leurs intervalles de confiance, ainsi que les exécutions en échec.

## Métriques

| Métrique | Méthode | Limite |
|---|---|---|
| `objective_coverage` | Code | Présence d'un lien, pas qualité de l'enseignement |
| `timing_validity` | Code | Cohérence des minutes, pas réalisme en classe |
| `evaluation_quality` | Code | Format et cohérence du corrigé, pas justesse des questions |
| `content_completeness` | Code | Présence de mots, pas qualité du traitement |
| `hallucination_count` | Heuristique de code | Faux positifs possibles, et une phrase fausse écrite avec des mots courants n'est pas vue |
| `critical_error_count`, `warning_count` | Code | Ne contient que ce que le code sait détecter |
| `revision_count` | Enregistré | Toujours 0 en mode A, par construction |
| `generation_time` | Mesuré par l'exécuteur | Dépend du service et de la charge |
| `human_interventions` | Enregistré | **Non mesuré par le banc automatique**, où personne ne valide. Demande une étude avec de vrais utilisateurs |
| `accuracy`, `critic_critical_count` | Agent `critique` | Jugement d'un modèle de langage, pas une vérité. Absents en mode A, sauf si la même critique lui est appliquée après coup |

## Menaces à la validité

- **Circularité.** La critique fait partie du mode B. Si elle mesurait aussi le résultat, ce mode serait juge et partie. C'est pourquoi les compteurs comparés viennent du code seul, et pourquoi l'exactitude doit être jugée par une critique commune indépendante ou, mieux, par des humains.
- **Optimisation pour la mesure.** Les agents du mode B connaissent les formats contrôlés par le code, comme le mode A qui lit les mêmes consignes. Un bon score peut donc refléter le respect d'un format plutôt que la qualité.
- **Validations automatiques.** En mode non interactif, le banc répond « valider » à la place du prof, donc le rôle réel de l'humain n'est pas observé.
- **Poids arbitraires.** Les pénalités du score (40, 12 et 3) sont un choix de conception. Les analyses doivent porter sur les métriques détaillées plutôt que sur le score global.
- **Généralisation.** Les résultats dépendent du modèle, de sa version, de la langue française et du corpus.

## Reproductibilité

Chaque exécution enregistre dans `manifest.json` la date, le commit, l'exécuteur, le modèle, les cas et les répétitions. Les contrôles et les fixtures sont déterministes, contrairement aux générations par un modèle de langage : conservez donc leurs sorties et leurs journaux.
