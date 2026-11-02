---
name: versions
description: Sauvegarde les fichiers d'un cours, montre leur historique, compare deux versions ou revient à une ancienne version. À utiliser quand un prof veut sauvegarder, retrouver, comparer ou annuler une version de ses diapos ou documents.
argument-hint: "[sauver | historique | comparer | restaurer]"
---

# Gérer les versions du cours

Parle de « sauvegardes » et de « versions », jamais de Git. Lance les commandes depuis le dossier du cours (sous Windows, remplace `python3` par `python` si besoin).

- Sauvegarder : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" sauver "ce qui a changé"`
- Voir l'historique : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" historique`
- Voir le texte qui a changé depuis une version : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" comparer <version> <fichier>`
- Revenir en arrière : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/versions.py" restaurer <version> <fichier>`

Présente l'historique par date et par message plutôt qu'avec les identifiants. La comparaison porte sur le texte : précise au prof qu'elle ne voit ni les images ni la mise en forme.

Avant de restaurer, confirme le fichier et la date avec le prof, et demande-lui de fermer le fichier dans PowerPoint ou LibreOffice. L'état actuel est sauvegardé automatiquement, donc une restauration peut elle-même être annulée.

Les sauvegardes restent sur cet ordinateur. Elles ne protègent pas d'une panne du disque : dis-le au prof la première fois. Ne configure et n'envoie rien vers un serveur.
