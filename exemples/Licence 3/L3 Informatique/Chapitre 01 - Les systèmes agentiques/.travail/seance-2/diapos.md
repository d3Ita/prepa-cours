# Les outils et la mémoire
- Rappel : quelles sont les étapes de la boucle ?
- Comment un agent peut-il agir ?
> Objectif : OBJ3

# À quoi sert un outil ?
- Il permet d'agir hors de la conversation
- Exemples : chercher une information, lire un fichier
- Lancer un calcul, envoyer un message
> Objectif : OBJ3

# Comment se passe un appel ?
@theme: atelier
@dessin: rect 2 18 36 72 bleu
@dessin: etiquette 9 40 encre Modèle
@dessin: rect 62 18 98 72 vert
@dessin: etiquette 65 40 encre Programme
@dessin: fleche 38 32 60 32 rouge
@dessin: etiquette 39 20 rouge Demande
@dessin: fleche 60 58 38 58 bleu
@dessin: etiquette 39 62 bleu Résultat
- Le modèle **demande** un appel
- Le programme **l'exécute**
- Le programme **renvoie** le résultat au modèle
> Objectif : OBJ3
> Insister : le modèle ne lance pas l'outil lui-même.

# À vous : jouez un appel d'outil
- Un modèle, un programme, un outil
- Jouez l'appel par groupe de trois
> Objectif : OBJ3

# Un bon outil a…
- Un nom clair
- Une **description précise**
- Des paramètres définis
- Des erreurs compréhensibles
> Objectif : OBJ4
> C'est à partir de la description que le modèle choisit l'outil.

# À vous : décrivez un outil
- Nom
- Description
- Paramètres
- Messages d'erreur
> Objectif : OBJ4

# Deux types de mémoire
- **Court terme** : la conversation et les résultats en cours
  - Taille limitée
- **Long terme** : conservée entre plusieurs tâches
  - Fichiers, base de données
> Objectif : OBJ5

# À vous : que faut-il conserver ?
- Trop d'informations : plus cher, et l'agent peut se distraire
- Trop peu : l'agent doit refaire son travail
> Objectif : OBJ5

# Bilan
- Le programme exécute les appels d'outils
- La description guide le choix de l'outil
- La mémoire se choisit
> Objectifs : OBJ3, OBJ4, OBJ5
> Puis distribuer le QCM.
