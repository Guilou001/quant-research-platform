# La réconciliation avec LEAN : deux moteurs, un même résultat

Un moteur écrit par la même personne que la stratégie partage ses angles
morts. La phase 9 confronte donc le moteur du laboratoire, qui travaille sur
des poids et des rendements mensuels, à LEAN. LEAN est le moteur événementiel de
QuantConnect : il passe des ordres et les remplit à un prix de marché. La
stratégie rejouée est le momentum de série temporelle de l'étude 001, sur
vingt-huit fonds cotés de 2007 à 2026.

## Ce que la comparaison établit

| Mesure, 234 mois | Valeur |
|---|---:|
| Écart mensuel maximal entre les deux moteurs, après retrait du financement | 4,0e-6 |
| Mois au-delà du seuil de 1e-4, déclaré avant la lecture | 0 |
| Ratio de Sharpe, laboratoire et LEAN | 0,3770 et 0,3770 |
| Exécutions remplies à la clôture du jour de décision | 6 447 sur 6 447 |
| Dates de décision où le nombre d'instruments ou un signe diffère | 0 sur 234 |
| Coût d'un retard d'une séance sur les ordres | 71 points de base par an, Sharpe 0,377 à 0,336 |

Statut mesuré le 2026-09-03. Le rapport complet, avec les conventions de
passage, le détail des exécutions et l'explication du seul écart de poids
visible, vit dans le dossier `lean/` du dépôt, page
[lean/README.md](https://github.com/Guilou001/quant-research-platform/blob/main/lean/README.md).

## Les trois conventions qui rendent la comparaison possible

L'export écrit pour chaque jour une ouverture égale à la clôture de la veille.
L'exécution à l'ouverture suivante de LEAN et l'exécution à la clôture de
décision du laboratoire désignent donc le même prix. Le rendement total
de LEAN, qui ne rémunère pas l'encaisse, se ramène au rendement excédentaire
du laboratoire en retranchant le taux sans risque multiplié par la somme des
poids. Le taux sans risque de Kenneth French est lu dans deux fichiers, et
l'algorithme n'en consulte jamais une valeur postérieure à la date courante.

## Ce que la phase laisse ouvert

Une seule stratégie a été réconciliée, parce qu'aucune n'a atteint `ROBUST`.
Le pont est en place : une stratégie retenue n'aurait plus qu'à ajouter son
algorithme dans `lean/algorithm/` et un export de ses entrées. Le choix de
faire tourner l'image publique de LEAN sans `lean-cli` est écrit dans
[ADR-015](../architecture/adr/adr-015-lean-dans-docker-sans-lean-cli.md).
