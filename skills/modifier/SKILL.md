---
name: modifier
description: Modifie un endroit précis d'une diapo, d'un scénario, d'un cours, d'un QCM ou d'un autre document d'un chapitre, puis met à jour tous les fichiers qui y font référence, seulement après validation du prof. À utiliser quand un prof veut changer, corriger ou reformuler un élément précis sans tout refaire.
argument-hint: "[fichier et endroit] [changement demandé]"
---

# Modifier un endroit précis

Demande fournie : `$ARGUMENTS`. Parle au prof de « documents » et de « sauvegardes », jamais de Git ou de script.

Sous Windows, remplace `python3` par `python` si besoin.

1. **Comprendre la demande.** Trouve le chapitre avec le skill `organiser` s'il n'est pas clair. Si le fichier, l'endroit ou le nouveau texte manque, ou si plusieurs endroits correspondent, demande au prof de préciser.
2. **Préparer.** Lance l'agent `modificateur` avec le chapitre et la demande exacte du prof. Il écrit un plan et ne modifie aucun document.
3. **Montrer l'aperçu.** Dans le dossier du chapitre, lance `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/modifier.py" apercu` et montre au prof, tel quel : chaque changement, les fichiers laissés tels quels et les fichiers non vérifiés. Avec `STATUS: PLAN_INCOMPLET`, renvoie les erreurs à l'agent `modificateur`, puis recommence cette étape.
4. **Attendre sa réponse.** **N'applique rien sans son accord explicite sur cet aperçu.** Propose : [1] Appliquer, [2] Modifier, [3] Annuler. Après « Modifier », renvoie sa demande à l'agent. Après « Annuler », ne fais rien d'autre que le dire.
5. **Appliquer**, seulement après « Appliquer » : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/modifier.py" appliquer --jeton <JETON de l'aperçu>`. Le script sauvegarde avant et après. Si le jeton est refusé, un fichier ou le plan a changé : remontre un nouvel aperçu. Ne recalcule jamais un jeton pour passer outre.
6. **Conclure.** Dis quels fichiers ont changé et comment revenir en arrière avec le skill `versions`. Signale tout problème affiché par le contrôle. La validation précédente de l'étape ne vaut plus : propose au prof de relancer la boucle de qualité du skill `cours`, sans le faire d'office.

## Limites

- Ce skill remplace du texte. Pour ajouter ou retirer une diapo, une question ou une séance, ou changer une image, explique-le au prof et utilise l'agent qui produit ce document, avec sa validation.
- Il ne modifie que le chapitre demandé. Chaque classe a sa propre copie : si le prof veut aussi corriger une autre classe, cherche avec `modifier.py rechercher "<terme>" "<dossier de cours>"`, puis traite chaque chapitre séparément, avec sa propre validation.
