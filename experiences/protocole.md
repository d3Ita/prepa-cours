# Comparer un agent unique et le système multi-agent

Ce protocole prépare une évaluation. **Elle n'a pas encore été menée : ce dépôt ne contient aucun résultat montrant qu'un mode est meilleur que l'autre.**

## Les deux modes

- **Mode A, agent unique :** une seule conversation reçoit le cours, le niveau, la matière, le découpage et les formats des skills, puis écrit tous les fichiers de `.travail`, sans critique ni boucle de révision.
- **Mode B, multi-agent :** `/prepa-cours:cours`, avec les agents spécialisés, la critique et la boucle de révision.

Les deux modes écrivent les mêmes fichiers. `qualite.py` peut donc les mesurer de la même manière.

## Déroulement

1. Réunir plusieurs vrais cours, ou des cours synthétiques, de matières et de niveaux variés, avec leurs droits d'utilisation.
2. Lancer les deux modes sur chaque cours, avec le même modèle et le même découpage, plusieurs fois, car les résultats varient d'une exécution à l'autre.
3. Faire critiquer les deux modes de la même façon : lancer l'agent `critique` une fois sur la sortie du mode A et sur la sortie finale du mode B, à partir d'une session neuve.
4. Lancer `python3 scripts/qualite.py rapport <chapitre> --etape livrables --json` et conserver le champ `metriques`.
5. Faire évaluer les sorties par des enseignants qui ignorent le mode utilisé. Ce point est indispensable : le score est calculé à partir des constats de la critique, qui fait partie du mode B, et il ne peut donc pas prouver seul la supériorité de ce mode.

## Métriques

| Métrique | Calcul actuel | Limite |
|---|---|---|
| `accuracy` | Score Exactitude | Dépend de ce que la critique détecte |
| `pedagogical_coherence` | Moyenne de Cohérence et Progression | Idem |
| `objective_coverage` | Moyenne de la couverture des objectifs | Mesure les liens, pas la qualité de l'enseignement |
| `timing_validity` | Score Timing | Ne prouve pas qu'une séance tient en classe |
| `evaluation_quality` | Score Évaluation | Ne remplace pas une relecture |
| `hallucination_rate` | Constats d'hallucination non marqués, par fichier produit | Dépend de la détection, et une liste de termes suspects peut contenir de faux positifs |
| `human_interventions` | Nombre de décisions enregistrées par `qualite.py valider` | À compter de la même façon dans les deux modes |
| `generation_time` | `null` : à mesurer par la personne qui lance l'expérience | Pas encore automatisé |
