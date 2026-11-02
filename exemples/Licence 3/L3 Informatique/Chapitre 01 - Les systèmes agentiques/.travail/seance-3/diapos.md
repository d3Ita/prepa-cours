# Plusieurs agents, risques et protections
- Rappel : à quoi servent les outils et la mémoire ?
> Objectif : OBJ6

# Commencer par un seul agent
- Plus simple à construire
- Plus simple à surveiller
- Plus simple à corriger
> Objectif : OBJ6

# Quand utiliser plusieurs agents ?
- Des tâches peuvent avancer **en parallèle**
- Des rôles doivent être bien séparés
- Un **superviseur** répartit le travail et rassemble les résultats
- Contrepartie : coût plus élevé, erreurs plus difficiles à retrouver
> Objectif : OBJ6

# À vous : un agent ou plusieurs ?
- Lisez chaque cas d'usage
- Choisissez une architecture
- Justifiez votre choix
> Objectif : OBJ6
> Prévoir les cas d'usage à distribuer. [À VÉRIFIER]

# Trois risques
- L'agent se trompe, puis agit à partir de son erreur
- **Injection de prompt** : des instructions cachées dans un texte lu
- Trop de droits : des dégâts importants
> Objectif : OBJ7

# À vous : repérez l'instruction cachée
- Lisez cet e-mail
- Quelle instruction est cachée ?
- Que risquerait de faire l'agent ?
> Objectif : OBJ7
> Préparer un e-mail d'exemple sans danger. [À VÉRIFIER]

# Cinq protections
- Donner seulement les droits nécessaires
- Faire valider les actions difficiles à annuler
- Traiter le contenu lu comme des données
- Journaliser les actions
- Tester sur des cas préparés
> Objectif : OBJ8

# À vous : sécurisez un agent d'e-mails
- Quels droits lui donner ?
- Quelles actions faire valider ?
- Quels cas tester ?
> Objectif : OBJ8

# Bilan
- Commencer simple
- Limiter les droits
- Garder un humain pour les actions difficiles à annuler
> Objectifs : OBJ6, OBJ7, OBJ8
> Puis distribuer le QCM.
