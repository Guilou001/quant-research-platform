# ADR-005 : quatre étages de données, chacun avec une règle

**Statut** : acceptée le 2026-09-01.

## Contexte

Une donnée subit entre son téléchargement et son usage une suite de
transformations, et chacune peut introduire une erreur. Parsage, typage,
alignement de calendrier, traitement des divisions et des dividendes, conversion
de devise, calcul de rendement. Quand un résultat surprend, il faut pouvoir
remonter la chaîne et savoir laquelle a menti.

Un seul répertoire de données rend ce diagnostic impossible, parce qu'il ne
reste que le résultat final.

## Décision

Quatre étages, et une règle par étage.

**`raw`** conserve la donnée exactement comme elle est arrivée, octet pour
octet, avec son horodatage de téléchargement. Elle est **immuable**. On n'y
corrige rien, jamais : une correction y détruit la seule preuve de ce que la
source répondait ce jour-là. Un nouveau téléchargement crée un nouveau fichier
horodaté, il n'écrase pas l'ancien.

**`bronze`** porte le même contenu, lisible : parsage, typage, colonnes nommées.
Aucune décision financière n'y est prise.

**`silver`** porte la donnée propre : calendrier cohérent, doublons retirés,
actions de société traitées, devise déclarée. Toutes les décisions
méthodologiques vivent ici, et chacune est tracée dans le manifeste.

**`gold`** porte les jeux directement consommables par un facteur, un modèle, un
backtest ou un optimiseur. Un jeu *gold* sans manifeste ne se charge pas :
`write_table` lève `ProvenanceError`.

## Conséquences

Le disque porte quatre copies partielles de la même information. Sur les volumes
visés, quelques dizaines de gigaoctets, le coût est négligeable devant la
capacité de diagnostic.

Chaque promotion d'un étage au suivant écrit un manifeste enfant qui cite son
parent, ce qui rend la lignée reconstructible par `lineage(dataset_id)`.

## Options écartées

**Deux étages, brut et propre.** Rejetée parce qu'elle mélange le parsage et les
décisions financières. Quand un rendement surprend, on ne sait pas si c'est le
lecteur de CSV ou le traitement des dividendes.

**Aucun étage, tout en mémoire à la volée.** Rejetée parce qu'elle rend le
résultat dépendant de l'état du serveur distant au moment de l'exécution, donc
non reproductible.
