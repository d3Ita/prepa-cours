---
name: diapos
description: Crée ou met à jour les diapos d'une séance au format PowerPoint, lisible aussi dans LibreOffice Impress, à partir de son scénario.
argument-hint: "[numéro de séance]"
---

# Créer les diapos d'une séance

Travaille dans le dossier du chapitre. Lis `.travail/objectifs.md`, `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md` et le fichier de la matière dans `${CLAUDE_PLUGIN_ROOT}/references/matieres/` (`autres.md` s'il n'y en a pas), et applique-les. Écris ensuite `.travail/seance-N/diapos.md` à partir de `.travail/seance-N/scenario.md`, puis génère `Diapos/seance-N-diapos.pptx` (LibreOffice Impress l'ouvre aussi).

```markdown
# Titre de la diapo
- Point clé avec un mot **important**
  - Détail
![Schéma de la feuille](../../Diapos/images/feuille.png)
> Objectif : OBJ1
> Note pour le prof, visible seulement en mode présentateur
```

Range les images du prof dans `Diapos/images/`. Génération :

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" pptx .travail/seance-N/diapos.md Diapos/seance-N-diapos.pptx --outils "${CLAUDE_PLUGIN_DATA}"`

Si le chapitre a des thèmes, ajoute `--themes .travail/themes.json`. Ajoute `--modele fichier.pptx` si le prof a un modèle d'établissement : il décide alors seul de l'apparence, et n'invente aucun thème.

## Le style « cahier d'exposé »

Sans modèle d'établissement, le script compose chaque diapo tout seul :

- **La première diapo** devient une ouverture : grand titre, et ses puces deviennent le sous-titre.
- **Un titre qui commence par « À vous », « Activité », « Exercice » ou « Atelier »** donne une diapo d'activité : le titre dans une bande de couleur, et les puces sur une grande note scotchée. Écris-y une consigne courte. Mets en `**gras**` la question à retenir.
- **Les autres diapos** montrent chaque puce sur une carte, avec ses sous-puces en dessous, jusqu'à 4 cartes, ou 3 à côté d'un dessin ou d'une image. Le script passe en liste s'il y a trop de puces ou trop de texte. **Préfère donc 2 à 4 puces courtes.**

Pour que les diapos ne soient ni sages ni vides, dessine un schéma dès qu'il aide à comprendre : une plante et ses échanges, une boucle, une chaîne de causes. Ajoute une ligne `@dessin:` par élément, sous le titre. Les positions vont de 0 à 100 dans la zone du dessin :

```text
@dessin: sol 80
@dessin: plante 50 80 1
@dessin: soleil 85 15 1
@dessin: fleche 15 30 40 45 rouge
@dessin: etiquette 2 20 rouge CO₂ entre
```

| Élément | Écriture |
|---|---|
| Sol | `sol y` |
| Plante, soleil | `plante x y taille`, `soleil x y taille` (taille de 0,3 à 2 ; pour la plante, `y` est le niveau du sol) |
| Cercle | `cercle x y rayon couleur` |
| Rectangle, trait, flèche | `rect x1 y1 x2 y2 couleur`, `trait x1 y1 x2 y2 couleur`, `fleche x1 y1 x2 y2 couleur` |
| Étiquette | `etiquette x y couleur texte` (60 caractères au maximum) |

Les couleurs sont `vert`, `bleu`, `rouge`, `jaune`, `brun` et `encre`. Limite-toi à 30 éléments par diapo, sans dessin sur une diapo d'activité. Ces formes restent simples : si un sujet demande un dessin que tu ne peux pas composer proprement (un organe, une carte), n'essaie pas. Écris dans les notes « Image à ajouter : … », ou compose un schéma abstrait avec des cercles et des flèches. Un dessin n'est jamais une preuve : ses étiquettes respectent les mêmes règles que le texte. Signale au prof quels dessins il doit regarder de près, car ni toi ni le script ne les voyez une fois rendus.

## Adapter les couleurs au sujet

Le papier chaud convient à tous les cours. Pour certaines diapos, comme une ouverture ou une notion clé, tu peux choisir des couleurs qui évoquent le sujet. Partage 1 à 3 thèmes pour tout le chapitre, dans `.travail/themes.json`, en complétant ce fichier s'il existe, sans changer les thèmes en place :

```json
{
  "feuillage": {"fond": "F1F7EE", "titre": "24562F", "texte": "1F2933", "accent": "2F7D4F", "police": "Georgia"}
}
```

Ajoute `@theme: feuillage` sous le titre de chaque diapo concernée, et laisse les autres sur le papier chaud. `police` est facultative, parmi Georgia, Trebuchet MS, Arial, Verdana, Tahoma et Times New Roman. Le script refuse un thème peu lisible : choisis alors des couleurs plus contrastées, en gardant un fond clair. Évite l'identité visuelle d'une marque, et respecte le ton du sujet. Indique au prof les thèmes créés et les diapos concernées.

## Règles

- Une idée par diapo, six puces au maximum, une image au maximum.
- Le nombre de diapos reste réaliste pour la durée de la séance.
- Le discours va dans les notes, pas sur la diapo.
- Chaque objectif de la séance est cité dans une note `> Objectif : OBJ1` sur au moins une diapo.
- N'utilise que des images fournies par le prof. S'il en manque une, décris-la dans les notes : « Image à ajouter : … ».
- Toute information absente du cours source porte la mention `[À VÉRIFIER]`.

## Si `Diapos/seance-N-diapos.pptx` existe déjà

Le prof l'a peut-être retouché, et le régénérer effacerait ses modifications de la version courante.

1. Sauvegarde : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" sauver "Avant mise à jour des diapos"`.
2. Liste les changements proposés, diapo par diapo.
3. Demande au prof s'il préfère les appliquer lui-même ou tout régénérer.
4. Ajoute `--ecraser` seulement s'il a choisi de tout régénérer.
