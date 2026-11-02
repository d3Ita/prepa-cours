# Prépa Cours

[![Tests](https://github.com/d3Ita/prepa-cours/actions/workflows/tests.yml/badge.svg)](https://github.com/d3Ita/prepa-cours/actions/workflows/tests.yml)
[![Licence : MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

**Gardez tous vos cours bien rangés par niveau, classe et chapitre. Donnez un cours en Word, LibreOffice ou texte, indiquez la matière, vos heures et vos séances : récupérez pour chaque séance un scénario minuté, des diapos et un QCM de 5 questions, dans des fichiers que vous pouvez retoucher avec PowerPoint, Word ou LibreOffice.**

*Claude Code plugin that organizes a teacher's courses by level, class and chapter, and fits a course to a subject and a given number of hours and sessions, then produces a lesson plan, slides and a 5-question quiz for each session, with version history. The plugin speaks French.*

> **Version 0.7 : préversion.** Les scripts sont testés automatiquement, mais le parcours complet avec les agents n'a pas encore été éprouvé sur de vrais cours. Le score qualité aide à repérer des problèmes, il ne garantit pas l'exactitude. Relisez toujours ce qui est produit, surtout les corrigés, avant de l'utiliser en classe.

## Vos cours bien rangés

Tous vos cours vivent dans un seul dossier, toujours organisé de la même façon :

```text
Dossier de cours/
└── Terminale/                       ← niveau
    └── Terminale 2/                 ← classe
        └── Chapitre 01 - Génétique/ ← chapitre
            ├── Cours/        votre cours et les scénarios de séance
            ├── Diapos/       les diapos
            ├── QCM/          les QCM à imprimer
            ├── Evaluations/  les évaluations à imprimer
            └── Corrections/  les corrigés
```

Vous pouvez demander à tout moment : « montre-moi mes cours de Terminale », « range ces fichiers » ou « réutilise ce chapitre pour la Terminale 3 ». Le plugin vous montre son classement avant de ranger des fichiers existants, les copie par défaut et ne supprime rien. Vous pouvez aussi lancer `/prepa-cours:organiser`.

## Architecture

Le découpage, les scénarios puis les diapos et évaluations passent chacun par ce parcours :

```text
Source Course
     ↓
Analyzer                skill decoupage
     ↓
Pedagogical Planner     skill decoupage, objectifs et matrice
     ↓
Generator               agents scenariste, concepteur-diapos, evaluateur
     ↓
Critic                  agent critique
     ↓
Revision                l'agent qui a produit le document, limité par qualite.py
     ↓
Quality Evaluator       controler.py, matrice.py, qualite.py
     ↓
Human Validation        le prof : Valider, Modifier ou Relancer
     ↓
Final Outputs           Cours, Diapos, QCM, Evaluations, Corrections
```

Le projet n'ajoute qu'un agent. Ce que du code peut vérifier de façon fiable (minutage, format, couverture, limite de révisions) reste dans les scripts ; le jugement sur le fond revient à l'agent `critique` ; la décision revient au prof.

| Commande | Ce qu'elle fait |
| --- | --- |
| `/prepa-cours:cours` | Enchaîne les étapes, attend votre validation et contrôle la cohérence |
| `/prepa-cours:organiser` | Classe vos cours par niveau, classe et chapitre, et réutilise un chapitre pour une autre classe |
| `/prepa-cours:decoupage` | Adapte le cours à vos heures et à vos séances, ou réajuste un découpage existant |
| `/prepa-cours:critique` | Lance une critique des documents d'une étape |
| `/prepa-cours:modifier` | Modifie un endroit précis et ses références, après votre accord |
| `/prepa-cours:versions` | Sauvegarde, compare et restaure vos fichiers |

### Agents

| Agent | Rôle | Entrées | Sorties | Limites |
| --- | --- | --- | --- | --- |
| `scenariste` | Écrit le déroulé minuté d'une séance | Cours, objectifs, niveau, matière, constats éventuels | `scenario.md`, `Cours/seance-N-scenario.docx` | Le temps prévu reste une estimation |
| `concepteur-diapos` | Crée les diapos et les notes | Scénario, objectifs, constats éventuels | `diapos.md`, `Diapos/seance-N-diapos.pptx` | N'invente pas d'images, n'écrase pas vos retouches |
| `evaluateur` | Crée les QCM, les corrigés et l'évaluation finale demandée | Scénario, objectifs, constats éventuels | `qcm.md`, `qcm-corrige.md`, `evaluation.md`, `corrige.md` et leurs `.docx` | Ne corrige pas de copies d'élèves |
| `critique` | Cherche les problèmes des autres agents | Cours d'origine, documents de l'étape, rapports des scripts | `.travail/revue/critique.json` | Ne corrige rien, n'approuve rien, et peut manquer des erreurs |
| `modificateur` | Prépare une modification précise et la liste de ses références | Votre demande, documents du chapitre | `.travail/revue/modification.json` | N'applique rien lui-même, et peut manquer une référence qui ne cite pas le terme |

### Modifier un endroit précis

Demandez par exemple : « dans la diapo 3 de la séance 1, remplace "capte la lumière" par "absorbe la lumière" ».

```text
Votre demande → Plan de modification → Aperçu → Votre accord → Sauvegarde → Modification
```

1. L'agent `modificateur` trouve l'endroit et recherche ses références dans tous les fichiers du chapitre, y compris les notes des diapos et les textes de travail.
2. Vous voyez chaque changement, « avant » et « après », avec les fichiers laissés tels quels et ceux que le plugin ne peut pas vérifier, comme un PDF.
3. Rien n'est écrit sans votre accord. Si un fichier change entre l'aperçu et votre réponse, ou si une référence trouvée n'est pas traitée, l'application est refusée.
4. Le plugin sauvegarde, puis modifie les `.pptx`, `.docx`, `.odt`, `.odp` et fichiers texte **sur place, sans les régénérer**. Vos retouches, vos images et votre mise en forme restent intactes, et un retour en arrière reste possible.

Ensuite, la validation et la critique précédentes ne valent plus : le plugin vous propose de relancer la boucle de qualité. Il remplace du texte : pour ajouter ou retirer une diapo, une question ou une séance, il passe par l'agent qui produit ce document. Chaque classe ayant sa propre copie, il ne modifie qu'un chapitre à la fois, après votre accord pour chacun.

### Boucle de critique

```text
generate → critic → revise → critic → … → validation humaine
```

1. L'agent `critique` écrit ses constats, chacun avec une gravité, une catégorie (`factual`, `pedagogical`, `timing`, `coherence`, `evaluation`, `hallucination`), un lieu, un problème, une preuve et une suggestion.
2. `qualite.py decider` choisit la suite. S'il reste un problème, l'agent responsable le corrige, puis la critique recommence.
3. Après `max_revision_cycles` corrections par étape (2 par défaut, de 0 à 5 dans les réglages du plugin), la boucle s'arrête :

```text
⚠ Révision maximale atteinte.
Une validation humaine est requise.
```

Une critique qui ne détaille pas ses six contrôles, mal formée ou plus ancienne que les documents n'est pas prise en compte.

### Validation humaine

Rien n'est considéré comme validé sans votre réponse. À chaque étape importante, le plugin affiche par exemple :

```text
Découpage terminé.

Quality score: 87/100

⚠ 2 warning(s)

[1] Valider
[2] Modifier
[3] Relancer l'analyse
```

Votre réponse est enregistrée dans `.travail/revue/validations.json`. Toute modification ultérieure annule la validation de l'étape. Vous gardez le dernier mot, même en présence d'un problème signalé.

### Score qualité

```text
QUALITY SCORE

Global          84/100
Exactitude      92/100
Objectifs       88/100
Cohérence       86/100
Progression     79/100
Timing          72/100
Évaluation      85/100
```

| Dimension | Ce qui la fait baisser |
| --- | --- |
| Exactitude | Constats `factual` et `hallucination` |
| Objectifs | Liens manquants dans la matrice : c'est la couverture moyenne |
| Cohérence | Constats `coherence` et fichiers absents |
| Progression | Constats `pedagogical` |
| Timing | Constats `timing` |
| Évaluation | Constats `evaluation` |

Chaque dimension part de 100 et perd 40 points par problème `critical`, 12 par `warning` et 3 par `info`. Le score global est leur moyenne, plafonnée à 69 s'il reste un problème bloquant. Chaque point perdu est expliqué :

```text
Timing : 76/100
- Le scénario dure 77 min pour une séance de 60 min (seance-2)
- La phase « Activité » n'a pas de temps défini (seance-4)
```

Ces poids sont un choix de conception, pas une mesure validée. Sans critique, Exactitude et Progression restent « non évaluées », et le score est présenté comme partiel. Le statut vaut `HUMAN_REVIEW_REQUIRED`, `READY_FOR_HUMAN_VALIDATION` ou, seulement après votre réponse, `HUMAN_VALIDATED`.

### Matrice pédagogique

```text
Objective → Activity → Exercise → Evaluation
```

`matrice.py` suit chaque objectif à partir des fichiers existants, sans format supplémentaire :

```text
OBJ1 : Décrire le rôle de l'estomac.
 ├── notions : estomac, sucs digestifs
 ├── séances : 1
 ├── activités : ACT-01, ACT-02, ACT-03
 ├── diapos : S1:1
 ├── exercices : EX-01
 ├── évaluations : S1-QCM-1, S1-QCM-2

OBJECTIVE COVERAGE

OBJ1 ✓ 100%
OBJ2 ⚠ 75%
OBJ3 ✗ 0%
```

Un objectif à 0 % est bloquant : rien ne permet de vérifier sa maîtrise. Une phase compte comme exercice si son titre contient par exemple « Activité », « Exercice » ou « Atelier ». La couverture montre qu'un lien existe, pas que l'objectif est bien enseigné : c'est à la critique et à vous d'en juger.

### Provenance des informations

La critique distingue ce qui est présent dans le cours (`source`), déduit raisonnablement (`deduite`), venu d'ailleurs (`externe`) et invérifiable (`incertaine`). Une information `externe` ou `incertaine` sans `[À VÉRIFIER]` est signalée comme `hallucination`. En complément, les scripts signalent les nombres et les noms propres absents du cours. Ce sont des pistes à vérifier, pas des preuves, et ils ne repèrent pas tout.

### Types d'évaluation

Les QCM de 5 questions par séance restent inchangés. Dans l'évaluation finale, une ligne `Type :` sous une question choisit parmi `qcm`, `vrai-faux`, `question-ouverte`, `exercice`, `etude-de-cas`, `probleme` et `reflexion`. Le dictionnaire `TYPES` de [`scripts/evaluations.py`](scripts/evaluations.py) associe à chaque type ses règles : ajouter un type revient à y ajouter une entrée.

### Évaluer le système

[`experiences/protocole.md`](experiences/protocole.md) décrit comment comparer un agent unique et le système multi-agent. **Cette comparaison n'a pas encore été menée** : rien ne prouve à ce stade que la critique améliore les cours.

## Niveaux et matières

Tous les agents s'adaptent à votre classe avant d'écrire.

- **Niveaux :** de la 6e au post-bac, avec notamment la Seconde, la Première et la Terminale. Le niveau règle le vocabulaire, le rythme des activités et la difficulté des QCM.
- **Matières :** SVT, mathématiques, physique-chimie, français, histoire-géographie, SES, philosophie, langues vivantes et informatique/NSI, avec un profil général pour les autres matières. Chaque profil règle la démarche, les activités, les diapos, les QCM et les erreurs à éviter.

Ces repères ne remplacent ni votre cours ni le programme officiel, que le plugin ne cite pas. Une notion qui semble hors du niveau vous est signalée sans être retirée. Pour ajouter une matière, il suffit d'ajouter un fichier dans [`references/matieres`](references/matieres).

## Contrôle et exemples

Le contrôle de cohérence vérifie notamment que le temps de chaque séance correspond à votre découpage, que chaque objectif est traité et que chaque QCM a bien 5 questions avec une seule réponse valide. Toute information qui ne vient pas de votre cours est signalée par `[À VÉRIFIER]`.

Si le cours ne tient pas dans les heures prévues, le plugin vous propose quoi condenser ou passer en travail personnel. Il ne supprime rien sans votre accord.

Le dossier [`exemples`](exemples) montre l'organisation et le format des fichiers produits, avec un chapitre sur la photosynthèse en 5e (2 séances de 55 min) et un faux cours sur les systèmes agentiques en licence 3 (3 séances de 2 h). Ces exemples ont été écrits à la main en suivant les consignes du plugin : ce ne sont pas des sorties réelles de ses agents.

## Installation

Il vous faut [Claude Code](https://code.claude.com/docs), [Python 3](https://www.python.org/downloads/) et [Git](https://git-scm.com/downloads). Dans Claude Code, tapez :

```text
/plugin marketplace add d3Ita/prepa-cours
/plugin install prepa-cours@prepa-cours
```

Internet est nécessaire à la première génération de fichiers, pour installer `python-pptx` et `python-docx`. Le plugin peut vous demander votre dossier de cours à l'activation. Sinon, il vous le demandera à la première utilisation.

## Utilisation

Indiquez votre document (`.docx`, `.odt` ou `.txt`), votre classe, votre chapitre et vos heures :

```text
/prepa-cours:cours mon-cours.docx Terminale 2, SVT, chapitre Génétique, 12 h en 6 séances de 2 h
```

Les séances peuvent aussi avoir des durées différentes : « 3 séances de 2 h, puis 2 séances d'1 h 30 ». Vous obtenez dans le dossier du chapitre :

| Fichier | Contenu |
| --- | --- |
| `Cours/mon-cours.docx` | Une copie de votre cours |
| `Cours/seance-1-scenario.docx` | Le déroulé de la séance |
| `Diapos/seance-1-diapos.pptx` | Les diapos et les notes du présentateur |
| `QCM/seance-1-qcm.docx` | Le QCM de 5 questions à imprimer |
| `Corrections/seance-1-qcm-corrige.docx` | Le corrigé du QCM |
| `Evaluations/evaluation.docx` | L'évaluation finale, si vous en demandez une |
| `Corrections/evaluation-corrige.docx` | Son corrigé |

Les mêmes fichiers sont créés pour chaque séance. Un dossier caché, `.travail`, contient les textes de travail du plugin : ne le supprimez pas, car il sert aux mises à jour et aux contrôles.

Si vos heures changent en cours d'année, dites-le simplement, par exemple : « je n'ai plus que 4 séances ». Le plugin vous montre ce que cela change et ne refait que les séances concernées après votre accord.

Pour vos versions, demandez simplement : « sauvegarde mon cours », « qu'est-ce qui a changé depuis hier ? » ou « reviens aux diapos de lundi ». Vous pouvez aussi lancer `/prepa-cours:versions`.

Vos retouches sont protégées : le plugin n'écrase jamais un fichier existant sans vous le demander, et il sauvegarde avant de restaurer une ancienne version.

## Vos données

- **Ce qui part :** les documents que Claude lit sont envoyés à Anthropic pour être traités, comme dans toute conversation avec Claude.
- **Ce qui reste chez vous :** les sauvegardes sont locales et le plugin n'envoie rien vers GitHub ou un autre serveur.
- **Élèves :** ne donnez ni noms, ni notes, ni copies. Cette version ne corrige pas les copies, précisément pour éviter de traiter ces données personnelles.

## Limites

- Les anciens fichiers Word `.doc` ne sont pas lus : enregistrez-les d'abord en `.docx`.
- La modification ciblée ne peut pas changer un texte coupé par une mise en forme dans un `.odt` ou un `.odp`, ni les PDF : elle vous le signale pour que vous le fassiez vous-même.
- Le plugin ne lit que le texte de votre cours, pas ses images.
- Les formules complexes ne sont pas mises en forme : elles sont signalées `[FORMULE À SAISIR]` pour que vous les saisissiez dans l'éditeur d'équations.
- La durée de chaque notion est une estimation : ajustez-la selon votre classe.
- Réutiliser un chapitre crée une copie par classe : une modification ne se répercute pas sur les autres classes.
- Les sauvegardes ne protègent pas d'une panne de disque : copiez aussi le dossier de cours ailleurs.
- La comparaison de versions porte sur le texte, pas sur les images ni la mise en forme.
- Deux versions modifiées en parallèle ne peuvent pas être fusionnées automatiquement.
- Les diapos sont au format `.pptx`, que LibreOffice ouvre. Le rendu peut varier selon le logiciel et le modèle utilisé.
- Le plugin n'invente pas d'images : il utilise celles que vous fournissez.
- Il a été conçu pour Claude Code. L'usage sur claude.ai ou Cowork n'a pas été testé.

## Contribuer

Les retours d'enseignants sont les plus précieux : [ouvrez une issue](https://github.com/d3Ita/prepa-cours/issues) pour signaler un problème ou raconter ce qui vous manque.

```bash
pip install python-pptx==1.0.2 python-docx==1.2.0
```

```bash
python3 -m unittest discover tests
```

## Licence

[MIT](LICENSE)
