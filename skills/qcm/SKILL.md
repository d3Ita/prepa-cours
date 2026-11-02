---
name: qcm
description: Crée le QCM de 5 questions d'une séance et son corrigé, à imprimer depuis Word ou LibreOffice. À utiliser quand un prof demande un QCM, un quiz ou un test rapide pour une séance.
argument-hint: "[numéro de séance]"
---

# Créer le QCM d'une séance

Chaque séance a exactement **5 questions**. Travaille dans le dossier du chapitre. Lis `.travail/objectifs.md`, `.travail/seance-N/scenario.md`, `${CLAUDE_PLUGIN_ROOT}/references/niveaux.md` et le fichier de la matière dans `${CLAUDE_PLUGIN_ROOT}/references/matieres/` (`autres.md` s'il n'y en a pas), et applique-les. Écris ensuite `.travail/seance-N/qcm.md` et `.travail/seance-N/qcm-corrige.md`.

`qcm.md` :

```markdown
# QCM : séance 1
Nom : ____________________  Date : ____________

## Question 1
Par où la plante absorbe-t-elle l'eau ?
A. Par les feuilles
B. Par les racines
C. Par les fleurs
D. Par la tige
```

`qcm-corrige.md` :

```markdown
# Corrigé du QCM : séance 1

Question 1 : B (OBJ1) — L'eau entre par les racines.
```

Génère ensuite les fichiers à imprimer, le sujet dans `QCM` et le corrigé dans `Corrections` :

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" docx .travail/seance-N/qcm.md QCM/seance-N-qcm.docx --outils "${CLAUDE_PLUGIN_DATA}" --sortie-format "${user_config.format_documents}"`

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/generer.py" docx .travail/seance-N/qcm-corrige.md Corrections/seance-N-qcm-corrige.docx --outils "${CLAUDE_PLUGIN_DATA}" --sortie-format "${user_config.format_documents}"`

Le format suit le réglage de l'utilisateur, et seule l'extension peut changer. Si le script affiche `⚠`, dis au prof que ce format n'a pas pu être créé.

Si le document existe déjà, sauvegarde avec `versions.py sauver`, demande au prof, puis ajoute `--ecraser` seulement s'il accepte.

## Règles

- Quatre choix de A à D, une seule bonne réponse.
- N'interroge que sur ce qui a été vu pendant cette séance.
- Couvre tous les objectifs de la séance avec les 5 questions, et cite-les seulement dans le corrigé. Si une séance a plus de 5 objectifs, signale-le au prof.
- Varie la place de la bonne réponse.
- Les mauvaises réponses sont plausibles et de longueur comparable à la bonne, sans piège de vocabulaire.
- Évite « toutes les réponses », « aucune réponse » et les formulations négatives.
- Toute réponse absente du cours porte la mention `[À VÉRIFIER]` dans le corrigé.
- Signale au prof de relire le corrigé. Ne corrige pas de copies d'élèves.
