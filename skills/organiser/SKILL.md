---
name: organiser
description: Organise le dossier de cours d'un enseignant par niveau, classe et chapitre, avec Cours, Diapos, QCM, Evaluations et Corrections. À utiliser quand un prof veut retrouver, ranger ou classer ses cours, voir ce qu'il a déjà, créer un chapitre ou réutiliser un chapitre pour une autre classe.
argument-hint: "[voir | ranger | créer | réutiliser]"
---

# Organiser le dossier de cours

Dossier de cours configuré : `${user_config.dossier_cours}`

Si cette valeur est vide ou n'est pas un chemin, demande au prof où il veut garder ses cours et propose un dossier `Cours` dans ses Documents. Refuse son dossier personnel entier ou tout un disque. Parle de « dossiers » et de « sauvegardes », jamais de Git ou de script.

## L'organisation

```text
Dossier de cours/
└── Terminale/                       ← niveau
    └── Terminale 2/                 ← classe
        └── Chapitre 01 - Génétique/ ← chapitre
            ├── Cours/        cours d'origine et scénarios
            ├── Diapos/       diapos et images
            ├── QCM/          sujets de QCM
            ├── Evaluations/  sujets d'évaluation
            └── Corrections/  corrigés
```

Écris les niveaux simplement : `6e`, `5e`, `4e`, `3e`, `Seconde`, `Première`, `Terminale`. Demande au prof le nom exact de la classe, sans le déduire. Le dossier caché `.travail` contient les textes de travail du plugin : ne le présente pas au prof et ne lui demande pas de le ranger.

## Commandes

Sous Windows, remplace `python3` par `python` si besoin.

- Voir ce qui existe : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/organiser.py" arbre "<dossier de cours>"`
- Créer ou retrouver un chapitre, sans écraser l'existant : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/organiser.py" creer "<dossier de cours>" "<niveau>" "<classe>" "<titre du chapitre>"`. La commande numérote le chapitre et affiche son chemin.
- Ranger une copie d'un fichier : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/organiser.py" ranger "<fichier>" "<chapitre>" <Cours|Diapos|QCM|Evaluations|Corrections>`. Ajoute `--deplacer` pour le déplacer.
- Réutiliser un chapitre pour une autre classe : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/organiser.py" dupliquer "<chapitre>" "<dossier de l'autre classe>"`

## Ranger des fichiers déjà existants

1. Liste les fichiers du dossier que le prof indique, sans rien modifier.
2. Lis-les si leur nom ne suffit pas, et propose un tableau : fichier, niveau, classe, chapitre, catégorie. Signale chaque doute au lieu de le trancher.
3. **Attends sa validation.** Ne range jamais d'après une simple supposition.
4. Fais une sauvegarde depuis le dossier de cours : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" sauver "Avant rangement"`.
5. Par défaut, copie les fichiers. Déplace-les seulement si le prof le demande.

Si deux fichiers portent le même nom, demande lequel renommer. Ne supprime jamais rien.

## Réutiliser un chapitre pour une autre classe

Crée le dossier de l'autre classe si besoin, duplique le chapitre, puis rappelle au prof que chaque classe a désormais sa propre copie : modifier l'une ne change pas l'autre. Si l'autre classe a un autre niveau, suis `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md`.
