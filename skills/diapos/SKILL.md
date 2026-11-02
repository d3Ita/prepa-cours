---
name: diapos
description: Crée ou met à jour les diapos d'un cours au format PowerPoint, lisible aussi dans LibreOffice Impress, à partir de scenario.md.
---

# Créer les diapos

Écris `diapos.md` à partir de `scenario.md`, puis génère `diapos.pptx` (LibreOffice Impress l'ouvre aussi).

```markdown
# Titre de la diapo
- Point clé avec un mot **important**
  - Détail
![Schéma de la feuille](images/feuille.png)
> Objectif : O1
> Note pour le prof, visible seulement en mode présentateur
```

Génération :

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" pptx diapos.md diapos.pptx --outils "${CLAUDE_PLUGIN_DATA}"`

Ajoute `--modele fichier.pptx` si le prof a un modèle d'établissement.

## Règles

- Une idée par diapo, six puces au maximum, une image au maximum.
- Le discours va dans les notes, pas sur la diapo.
- Chaque objectif est cité dans une note `> Objectif : O1` sur au moins une diapo.
- N'utilise que des images fournies par le prof. S'il en manque une, décris-la dans les notes : « Image à ajouter : … ».
- Toute information absente du cours source porte la mention `[À VÉRIFIER]`.

## Si `diapos.pptx` existe déjà

Le prof l'a peut-être retouché, et le régénérer effacerait ses modifications de la version courante.

1. Sauvegarde : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" sauver "Avant mise à jour des diapos"`.
2. Liste les changements proposés, diapo par diapo.
3. Demande au prof s'il préfère les appliquer lui-même ou tout régénérer.
4. Ajoute `--ecraser` seulement s'il a choisi de tout régénérer.
