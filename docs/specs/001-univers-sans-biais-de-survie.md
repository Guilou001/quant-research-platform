# Spécification 001 : un univers d'actions qui garde les sociétés radiées

**Statut** : brouillon, écrite le 2026-09-03.
**Règles concernées** : 1, 4, 5, 13, 15.

## Ce que cela doit faire

Le laboratoire doit pouvoir rejouer une stratégie sur les actions qui
existaient à chaque date, et non sur celles qui existent aujourd'hui. L'étude
013 a mesuré ce que le contraire fabrique. Un décile de perdants de long
terme rapporte 7,1 % par an chez les survivants et coûte 1,7 % sur les
déciles de Kenneth French. Le mécanisme est un fournisseur de données
quotidiennes qui rend, pour une date donnée, la liste des titres cotés ce
jour-là avec leur prix. Il garde le dernier prix et la raison de sortie d'un
titre radié.

La source candidate est Polygon, dont la documentation annonce que les titres
radiés gardent leur historique et que les données sont datées par symbole
sans réemploi silencieux d'un symbole. Statut rapporté, lu le 2026-09-03 ; la
clé de l'auteur existe déjà pour le programme intrajournalier. La couverture
en années dépend du forfait, à mesurer avant de choisir.

## Ce que le dépôt porte déjà, et qui sera appelé plutôt que recopié

`quantlab.data.providers.base` pour le client HTTP, le cache brut et le
manifeste. `quantlab.data.lake` pour les quatre étages. Le schéma long de
`quantlab.data.providers.yahoo` pour les barres. `quantlab.models.panel`
pour les rangs transversaux. `gvf.marches` pour la lecture des clés hors du
code.

## Les critères d'acceptation, mesurables

1. Pour dix dates tirées entre 1996 et 2026, le nombre de titres rendus est
   supérieur au nombre de titres du S&P 500 d'aujourd'hui présents à ces dates,
   et l'écart croît en remontant dans le temps.
2. Pour cinq radiations connues, Lehman Brothers, Enron, WorldCom, Bear
   Stearns, Washington Mutual, le fournisseur rend un dernier prix et une date
   de sortie, et aucun prix après cette date.
3. Le contrôle de biais de survie de l'étude 013 refait sur cet univers rend,
   pour le renversement de long terme, un écart décile haut moins bas dont le
   signe est celui des déciles de Kenneth French, et non l'inverse.
4. Le manifeste porte la licence, l'empreinte et la date de chaque appel, et
   `make test` ne fait aucun appel réseau.

## Les décisions de conception, et ce qu'elles écartent

Le fournisseur rend un univers point-in-time par appartenance à la cote, pas
par appartenance à un indice : l'historique des membres d'un indice n'est pas
libre. Un titre radié reçoit un rendement de sortie égal à son dernier prix
contre le précédent, sans le rendement de radiation de CRSP, absent des
sources libres. La limite est déclarée, et son sens aussi : un biais vers le
haut.

## Le plan, en étapes vérifiables

1. Mesurer la couverture réelle du forfait : années disponibles, titres
   radiés présents, débit. Une page de mesures, avant tout code.
2. Le fournisseur, avec réponses enregistrées pour les tests.
3. L'univers point-in-time dans le lac, étage argent.
4. Le critère 3, comme étude 015, sur le protocole de l'étude 013.

## Hors périmètre

Les fondamentaux des sociétés radiées, qui restent ceux de la SEC ; l'univers
canadien, pour lequel aucune source libre n'a été trouvée.
