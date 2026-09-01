# Ce que les données gratuites ne donneront pas

Cette page existe pour une raison : un projet qui cache les limites de ses
données produit des résultats que personne du métier ne croira, et il a raison
de ne pas les croire.

## Le tableau des manques

| Ce qui manque | Ce que cela empêche | Ce que nous faisons à la place |
|---|---|---|
| Univers sans biais de survie complet | tout backtest actions sur titres individuels vraiment propre | facteurs de Ken French, univers de FNB, marquage explicite |
| Titres radiés historiques | mesurer le rendement des positions qui ont disparu | déclarer le biais, ne pas viser `ROBUST` |
| Base de référence des titres façon CRSP | suivre une entreprise à travers ses changements de symbole | correspondance par CIK pour la SEC, symbole ailleurs |
| Carnet d'ordres et meilleures limites nationales | mesurer un vrai écart acheteur-vendeur | écart supposé, déclaré en points de base |
| Données tick à tick | microstructure, exécution fine | modèle d'impact stylisé en racine carrée |
| Historique d'options | volatilité implicite, portage d'options, surface | études d'options non prévues en phase 1 à 7 |
| Coûts d'emprunt de titres | coût réel d'une position vendeuse | hypothèse déclarée, plus des scénarios à un, deux et cinq fois |
| Disponibilité à l'emprunt et rappels | savoir si la vente est réalisable | supposée réalisable, ce qui est **optimiste** et écrit comme tel |
| Contrats à terme continus de qualité institutionnelle | TSMOM sur cinquante-huit instruments comme dans l'article | FNB de matières premières et de taux, écart avec l'article déclaré |
| Historique complet des actions de société | rendement total exact sur longue période | prix ajustés de la source, avec leurs défauts documentés |
| Impact de marché mesuré | capacité chiffrée avec précision | modèle stylisé, clairement marqué comme modélisé |

## Ce que cela change pour les verdicts

Une étude dont une donnée manquante affecte le résultat ne peut pas dépasser
`REPLICATED`. Le passage à `ROBUST` exige que les limites connues soient sans
effet sur la conclusion, ou que leur effet ait été borné.

Exemple concret. Une stratégie vendeuse dont l'alpha net est de 200 points de
base par an, testée avec un coût d'emprunt supposé de 50 points de base, ne
tient plus si le coût réel est de 300. Le laboratoire teste donc à un, deux et
cinq fois l'hypothèse, et publie à partir de quel multiple la stratégie meurt.
Ce multiple est l'information utile, pas l'alpha central.

## L'architecture prévoit le remplacement

Le protocole `DataProvider` existe pour cela. Le jour où un fournisseur
professionnel remplace Yahoo, aucune stratégie ne change : seule une classe
apparaît, et les manifestes qu'elle écrit portent d'autres valeurs.

```
FreeDataProvider  ──►  ProfessionalDataProvider
```

La contrainte est simple à énoncer : rien dans `strategies/`, `signals/` ou
`portfolio/` n'a le droit d'importer un module de `providers/`.

## La règle d'écriture

Une limite se déclare à l'endroit où elle porte, pas dans une annexe. Un
rapport d'étude qui suppose un coût d'emprunt le dit dans la section des
hypothèses **et** à côté du chiffre de performance nette.
