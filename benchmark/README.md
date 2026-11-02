# Benchmark de Prépa Cours

> **Ce benchmark ne mesure pas directement la qualité pédagogique humaine. Il mesure des indicateurs techniques et structurels.** Aucune comparaison réelle entre agent unique et multi-agent n'a encore été exécutée, et ce dépôt ne contient aucun résultat montrant qu'une architecture est meilleure.

## Objectif

Rendre mesurable la question : l'architecture multi-agent apporte-t-elle une amélioration par rapport à un agent unique ? La méthode complète se trouve dans [`docs/methodology.md`](../docs/methodology.md).

## Commandes

Installez les dépendances, depuis la racine du dépôt :

```bash
pip install python-pptx==1.0.2 python-docx==1.2.0
```

Vérifiez les contrôles sur les dix cas, sans modèle de langage :

```bash
python3 benchmark/run.py verify
```

Testez le banc d'essai avec des données simulées :

```bash
python3 benchmark/run.py run --runner fixture
```

Lancez une vraie comparaison, longue et payante :

```bash
python3 benchmark/run.py run --runner claude --i-accept-llm-costs --repetitions 3 --model NOM_DU_MODELE
```

Produisez à nouveau le rapport de la dernière exécution :

```bash
python3 benchmark/run.py report
```

Voyez le parcours complet, avec des agents simulés :

```bash
python3 benchmark/parcours_mock.py
```

## Organisation

```text
benchmark/
├── courses/     les cours sources
├── fixtures/    les dix cas et leur résultat attendu
├── metrics/     le calcul, l'agrégation et l'export des métriques
├── prompts/     les consignes des modes A et B
├── runners.py   les exécuteurs : fixture et claude
├── run.py       la ligne de commande
├── outputs/     les sorties, non versionnées
└── reports/     les rapports, non versionnés
```

Une exécution produit :

```text
outputs/<id>/
├── manifest.json
├── single_agent/<cas>/repetition-1/{output/, run.log, metrics.json}
└── multi_agent/<cas>/repetition-1/{output/, run.log, metrics.json}
reports/<id>/{report.txt, benchmark_results.json, benchmark_results.csv}
```

## Les cas

| Cas | Défaut | Comportement attendu |
|---|---|---|
| `01_coherent` | Aucun | Aucun problème, couverture à 100 % |
| `02_objectif_non_couvert` | Objectif sans activité ni évaluation | `OBJ-003` est `MISSING`, problème bloquant |
| `03_temps_impossible` | 107 min pour une séance de 60 min | Temps invalide, écart signalé |
| `04_plusieurs_bonnes_reponses` | Corrigé « A, C » | Problème bloquant |
| `05_corrige_incorrect` | Réponse inexistante dans le QCM | Problème bloquant |
| `06_hallucination` | Nom et date absents du cours | Deux termes signalés |
| `07_cours_incomplet` | Section, notion et documents manquants | Complétude faible, problèmes bloquants |
| `08_contradictions` | Durée et corrigé contradictoires | Les deux sont signalés |
| `09_tres_court` | Aucun, une séance de 30 min | Aucun problème |
| `10_complexe` | Aucun, 4 séances et plusieurs types de questions | Aucun problème, modèle complet |

Ces cas sont écrits à la main et testent **les contrôles** : ils ne mesurent pas ce que produirait un modèle de langage. Ils servent aussi de tests de régression dans `tests/test_benchmark_cas.py`.

## Les exécuteurs

- **`fixture` :** recopie les cas dans les deux modes, à l'identique. Son rapport est toujours marqué `DONNÉES SIMULÉES`, et son temps et ses interventions restent `non mesuré`.
- **`claude` :** lance Claude Code sans interaction, dans le mode demandé, et mesure le temps réel. Un échec est enregistré, jamais remplacé par une valeur. **Ce mode n'a été testé qu'avec un faux exécutable, jamais avec un vrai modèle.** Les consignes devront sans doute être ajustées au premier essai.

Pour ajouter un exécuteur, écrivez une classe avec `nom`, `simulated`, `modele` et `executer`.

## Les métriques

| Métrique | Méthode | Disponible aujourd'hui |
|---|---|---|
| `objective_coverage`, `timing_validity`, `evaluation_quality`, `content_completeness` | Code | Oui |
| `hallucination_count` | Heuristique de code | Oui, avec des faux positifs et des oublis possibles |
| `critical_error_count`, `warning_count` | Code | Oui |
| `revision_count` | Enregistré par `qualite.py decider` | Oui si la boucle tourne, sinon 0 |
| `generation_time` | Exécuteur | Seulement avec `claude` |
| `accuracy`, `critic_critical_count` | Agent `critique` | Seulement si une critique valide existe, et mode B seulement sans critique commune |
| `human_interventions` | Décisions enregistrées | **Non mesuré par le banc automatique** |

Une valeur absente s'affiche `non mesuré`, jamais 0. Les compteurs comparés viennent du code seul : sinon, le mode qui lance une critique serait pénalisé pour avoir cherché ses erreurs.

## Limites

- **Taille du corpus :** quatre cours courts ne permettent aucune conclusion générale.
- **Ce que le code ne voit pas :** une mauvaise lettre qui existe dans le QCM, ou une contradiction de sens, restent invisibles sans critique ni relecture. Des tests documentent ces deux limites.
- **Détection des termes :** elle cherche des nombres et des noms propres, pas des phrases fausses.
- **Pas de statistiques :** l'outil calcule des moyennes et leur effectif, mais ne teste aucune différence. Analysez le CSV avec les méthodes prévues dans la méthodologie.
- **Pas de jugement humain :** la [grille humaine](../human_evaluation/rubric.md) est prête, mais l'étude reste à faire.

## Reproductibilité

Les contrôles et les fixtures donnent toujours le même résultat, et un test le vérifie. Les générations réelles varient : gardez `manifest.json`, `run.log` et `output/`.
