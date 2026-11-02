# Les systèmes agentiques

Faux cours de démonstration, niveau licence 3 informatique.

## 1. Qu'est-ce qu'un agent ?

Un agent est un programme qui poursuit un objectif en choisissant lui-même ses prochaines actions. Un chatbot classique répond à un message, puis attend le suivant. Un agent peut enchaîner plusieurs actions sans nouvelle demande de l'utilisateur.

Un script suit des étapes fixées à l'avance par son auteur. Un agent décide de ses étapes pendant l'exécution, à partir de ce qu'il observe.

## 2. La boucle d'un agent

Un agent fonctionne en boucle : il observe la situation, décide de la prochaine action, agit, puis observe le résultat. La boucle s'arrête quand l'objectif est atteint ou quand une limite est dépassée.

Une limite d'arrêt est indispensable, par exemple un nombre maximal d'étapes ou un budget. Sans elle, un agent bloqué peut tourner sans fin et consommer des ressources.

## 3. Les outils

Un outil permet à l'agent d'agir hors de la conversation : chercher une information, lire un fichier, lancer un calcul ou envoyer un message. Le modèle ne lance pas l'outil lui-même : il demande un appel, le programme l'exécute, puis lui renvoie le résultat.

Un bon outil a un nom clair, une description précise, des paramètres définis et des messages d'erreur compréhensibles. La description est essentielle, car c'est à partir d'elle que le modèle choisit l'outil.

## 4. La mémoire

La mémoire à court terme contient la conversation et les résultats de la tâche en cours. Sa taille est limitée. La mémoire à long terme conserve des informations entre plusieurs tâches, par exemple dans des fichiers ou une base de données.

Il faut choisir ce que l'agent conserve : trop d'informations coûtent cher et peuvent le distraire, trop peu l'obligent à refaire son travail.

## 5. Un agent ou plusieurs ?

Un seul agent est plus simple à construire, à surveiller et à corriger. Il faut commencer par cette solution.

Plusieurs agents sont utiles quand des tâches peuvent avancer en parallèle ou demandent des rôles bien séparés. Un agent superviseur répartit alors le travail et rassemble les résultats. En contrepartie, le système coûte plus cher, et ses erreurs sont plus difficiles à retrouver.

## 6. Les risques

Un agent peut se tromper puis agir à partir de son erreur. L'injection de prompt est un autre risque : un texte lu par l'agent, comme une page web ou un e-mail, contient des instructions cachées qu'il risque de suivre. Enfin, un agent qui a trop de droits peut provoquer des dégâts importants, comme supprimer des données.

## 7. Les protections

Il faut donner à l'agent seulement les droits nécessaires à sa tâche. Les actions difficiles à annuler doivent être validées par un humain. Le contenu lu par l'agent doit être traité comme des données et non comme des ordres. Il faut aussi journaliser les actions de l'agent pour comprendre ce qu'il a fait, et le tester sur des cas préparés avant de l'utiliser.
