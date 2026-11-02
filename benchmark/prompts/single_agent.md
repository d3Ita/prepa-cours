Mode de benchmark A : agent unique, sans interaction.

Le dossier courant est un chapitre déjà créé. Le cours est `Cours/{cours}`. Consignes : {consignes}.

Fais tout toi-même dans cette seule conversation : n'utilise aucun sous-agent, aucune critique et aucune boucle de révision. Écris une seule fois chaque document.

Pour connaître les formats attendus, lis `{racine}/skills/decoupage/SKILL.md`, `{racine}/skills/scenario/SKILL.md`, `{racine}/skills/diapos/SKILL.md` et `{racine}/skills/qcm/SKILL.md`, en considérant `${{CLAUDE_PLUGIN_ROOT}}` comme `{racine}`. Lis aussi `{racine}/references/niveaux.md` et le profil de la matière dans `{racine}/references/matieres/`.

Produis `.travail/objectifs.md`, puis pour chaque séance `.travail/seance-N/scenario.md`, `diapos.md`, `qcm.md` et `qcm-corrige.md`. Génère ensuite les documents avec `{racine}/scripts/generer.py` aux emplacements indiqués par ces consignes, sans option `--outils` et avec l'interpréteur `{python}`.

Toute information absente du cours porte la mention `[À VÉRIFIER]`. Ne pose aucune question : personne ne répondra.
