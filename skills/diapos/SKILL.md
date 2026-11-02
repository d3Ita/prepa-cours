---
name: diapos
description: Crée ou met à jour les diapos d'une séance au format PowerPoint, lisible aussi dans LibreOffice Impress, à partir de son scénario.
argument-hint: "[numéro de séance]"
---

# Créer les diapos d'une séance

Lis `objectifs.md`, `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md` et le fichier de la matière dans `${CLAUDE_PLUGIN_ROOT}/references/matieres/` (`autres.md` s'il n'y en a pas), et applique-les. Écris ensuite `seance-N/diapos.md` à partir de `seance-N/scenario.md`, puis génère `seance-N/diapos.pptx` (LibreOffice Impress l'ouvre aussi).

```markdown
# Titre de la diapo
- Point clé avec un mot **important**
  - Détail
![Schéma de la feuille](images/feuille.png)
> Objectif : OBJ1
> Note pour le prof, visible seulement en mode présentateur
```

Le chemin d'une image part du dossier de la séance. Génération depuis le dossier du cours :

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" pptx seance-N/diapos.md seance-N/diapos.pptx --outils "${CLAUDE_PLUGIN_DATA}"`

Ajoute `--modele fichier.pptx` si le prof a un modèle d'établissement.

## Règles

- Une idée par diapo, six puces au maximum, une image au maximum.
- Le nombre de diapos reste réaliste pour la durée de la séance.
- Le discours va dans les notes, pas sur la diapo.
- Chaque objectif de la séance est cité dans une note `> Objectif : OBJ1` sur au moins une diapo.
- N'utilise que des images fournies par le prof. S'il en manque une, décris-la dans les notes : « Image à ajouter : … ».
- Toute information absente du cours source porte la mention `[À VÉRIFIER]`.

## Si `diapos.pptx` existe déjà

Le prof l'a peut-être retouché, et le régénérer effacerait ses modifications de la version courante.

1. Sauvegarde : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" sauver "Avant mise à jour des diapos"`.
2. Liste les changements proposés, diapo par diapo.
3. Demande au prof s'il préfère les appliquer lui-même ou tout régénérer.
4. Ajoute `--ecraser` seulement s'il a choisi de tout régénérer.
