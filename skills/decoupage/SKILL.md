---
name: decoupage
description: Découpe un cours en séances selon le niveau de la classe, la matière, le volume d'heures et le nombre de séances donnés par l'enseignant, ou réajuste un découpage existant. À utiliser dès qu'un prof parle d'heures, de séances, de planning ou d'adapter la durée d'un cours.
argument-hint: "[volume horaire et séances, ex. 12 h en 6 séances de 2 h]"
---

# Découper un cours en séances

Le découpage horaire vient du prof : tu l'appliques exactement et tu adaptes le contenu à ce temps, jamais l'inverse. Les séances peuvent avoir des durées différentes.

## Écrire `.travail/objectifs.md`

Travaille dans le dossier du chapitre, créé avec le skill `organiser`. Lis tout le cours source dans `Cours/`. Si le prof n'a pas donné le niveau, la matière, le volume horaire et la durée de chaque séance, demande-les. Déduis le niveau ou la matière du cours seulement pour les lui proposer. Lis ensuite `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md` et le fichier de sa matière dans `${CLAUDE_PLUGIN_ROOT}/references/matieres/` (`autres.md` s'il n'y en a pas). Écris alors :

```markdown
# Objectifs : titre du cours

Niveau : Première, voie générale
Classe : Première 2
Matière : SVT
Durée totale : 5 h

- OBJ1 : Citer …
  - Notions : photosynthèse, chlorophylle
- OBJ2 : Expliquer …
- OBJ3 : Interpréter …

## Découpage

Séance 1 : 2 h — OBJ1
Séance 2 : 1 h 30 — OBJ2
Séance 3 : 1 h 30 — OBJ3
```

Respecte ce format : le contrôle de cohérence le lit. La ligne `Notions`, facultative mais conseillée, alimente la matrice pédagogique. Écris les durées sous la forme `2 h`, `1 h 30` ou `55 min`.

## Répartir le contenu

- Suis l'ordre du cours, sauf si un prérequis oblige à le changer.
- Dans chaque séance, réserve d'abord le temps de l'accueil, du rappel de la séance précédente et du QCM en classe (10 min). Le reste va au contenu et aux activités.
- Compte large : une notion nouvelle demande du temps d'explication et du temps d'activité, d'autant plus que la classe est jeune.
- Ne coupe jamais une notion au milieu d'une séance sans le signaler.

## Présenter au prof avant de continuer

Montre un tableau séance / durée / contenu / objectifs, puis signale clairement :

- **S'il y a trop de contenu :** ce que tu proposes de condenser ou de retirer, et ce qui passerait en travail personnel. Rien n'est supprimé sans son accord.
- **S'il y a trop de temps :** les exercices ou activités que tu proposes sur le contenu existant. Tout contenu nouveau porte la mention `[À VÉRIFIER]`.
- **Si le QCM ne doit pas se faire en classe :** retire ces 10 minutes de la séance.

**Attends sa validation avant de produire les séances.**

## Réajuster un découpage existant

Quand les heures changent :

1. Sauvegarde : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" sauver "Avant nouveau découpage"`.
2. Compare l'ancien et le nouveau découpage, et liste les séances concernées et les retouches du prof qui seraient perdues.
3. Après validation, modifie `.travail/objectifs.md` et refais seulement les séances concernées.
4. Déplace le contenu des séances supprimées, puis demande l'accord du prof avant de retirer leurs fichiers de `Cours`, `Diapos`, `QCM` et `Corrections`, ainsi que leur dossier dans `.travail`.
