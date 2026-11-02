# Les outils et la mémoire
- Rappel : quelles sont les étapes de la boucle ?
- Comment un agent peut-il agir ?
> Objectif : O3

# À quoi sert un outil ?
- Il permet d'agir hors de la conversation
- Exemples : chercher une information, lire un fichier
- Lancer un calcul, envoyer un message
> Objectif : O3

# Comment se passe un appel ?
- Le modèle **demande** un appel
- Le programme **l'exécute**
- Le programme **renvoie** le résultat au modèle
> Objectif : O3
> Insister : le modèle ne lance pas l'outil lui-même.

# À vous : jouez un appel d'outil
- Un modèle, un programme, un outil
- Jouez l'appel par groupe de trois
> Objectif : O3

# Un bon outil a…
- Un nom clair
- Une **description précise**
- Des paramètres définis
- Des erreurs compréhensibles
> Objectif : O4
> C'est à partir de la description que le modèle choisit l'outil.

# À vous : décrivez un outil
- Nom
- Description
- Paramètres
- Messages d'erreur
> Objectif : O4

# Deux types de mémoire
- **Court terme** : la conversation et les résultats en cours
  - Taille limitée
- **Long terme** : conservée entre plusieurs tâches
  - Fichiers, base de données
> Objectif : O5

# À vous : que faut-il conserver ?
- Trop d'informations : plus cher, et l'agent peut se distraire
- Trop peu : l'agent doit refaire son travail
> Objectif : O5

# Bilan
- Le programme exécute les appels d'outils
- La description guide le choix de l'outil
- La mémoire se choisit
> Objectifs : O3, O4, O5
> Puis distribuer le QCM.
