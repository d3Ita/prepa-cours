---
name: rediger
description: Rédige un cours à partir des documents d'un enseignant, puis l'accompagne pendant une longue période de révision du document, avant de passer à la suite. À utiliser quand un prof a des documents, des notes ou d'anciens cours et veut en faire un cours, ou veut reprendre la révision d'un cours en rédaction.
argument-hint: "[documents] [niveau] [matière] [chapitre]"
---

# Rédiger puis réviser un cours

Demande fournie : `$ARGUMENTS`. Parle au prof de « documents », de « versions » et de « sauvegardes », jamais de Git, de Markdown ou de script. Lance les commandes dans le dossier du chapitre (sous Windows, remplace `python3` par `python` si besoin).

**Reprise :** commence toujours par `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/redaction.py" etat`. Si un cours est déjà en rédaction, reprends directement à la période de révision et n'en recrée pas.

## Créer le premier cours

1. Trouve ou crée le chapitre avec le skill `organiser`.
2. Demande ce qui manque : niveau, matière, public, longueur souhaitée, points à privilégier ou à laisser de côté.
3. Copie ses documents : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/redaction.py" demarrer --sources "<fichier>" "<fichier>"`. Les originaux ne sont ni déplacés ni modifiés.
4. Lance l'agent `redacteur` avec le chapitre et ces consignes.
5. Crée le document : `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/redaction.py" produire --outils "${CLAUDE_PLUGIN_DATA}"`. Il devient `Cours/cours.docx`, et ce document est désormais la seule référence.
6. Présente le plan, les manques et les points à vérifier, puis ouvre la période de révision.

## Période de révision

Elle dure aussi longtemps que le prof le veut, sur autant de sessions qu'il faut. **Ne le presse jamais et ne lance pas la suite de toi-même.** Il peut alterner librement :

- **Retoucher le document lui-même** dans Word ou LibreOffice. Quand il revient, demande-lui s'il a fermé le fichier, sauvegarde avec `versions.py sauver "Retouches du prof"`, puis relis le document : tes connaissances peuvent être dépassées.
- **Demander une modification dans le tchat :** utilise le skill `modifier`. Il montre un aperçu et attend son accord, puis modifie le document sur place sans perdre ses retouches. Il peut remplacer du texte et ajouter des paragraphes.
- **Demander un changement plus large**, comme réorganiser un chapitre : propose un découpage en petites modifications, et applique-les avec le skill `modifier`. Ne recrée jamais tout le document, sauf s'il le demande explicitement après avoir compris qu'il perdrait ses retouches ; dans ce cas, sauvegarde d'abord.
- **Ajouter un document :** relance `demarrer --sources`, puis propose les ajouts avec le skill `modifier`.
- **Demander une relecture :** lance l'agent `critique` avec l'étape `redaction`, et présente ses constats sans rien corriger sans son accord.
- **Comparer ou revenir en arrière :** utilise le skill `versions`.

Après chaque tour, lance `redaction.py etat` et montre où en est le cours, les points à vérifier et les termes absents des documents, puis propose : **[1] Continuer à modifier, [2] Valider et passer à la suite**.

## Valider

Seule sa réponse explicite compte. Une phrase comme « c'est bien » sur un passage ne valide pas tout le cours : en cas de doute, demande-lui.

1. Montre chaque point `[À VÉRIFIER]` restant. Il peut les traiter maintenant ou accepter de les garder.
2. Lance `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/redaction.py" valider`. Ajoute `--malgre-a-verifier` seulement si, après les avoir vus, il accepte de les garder.
3. Si le cours change ensuite, le pipeline se bloque jusqu'à une nouvelle validation. Pour reprendre la révision, lance `redaction.py rouvrir`.

Pour la suite, passe au skill `cours`, à partir du découpage. Le cours validé devient alors la référence.
