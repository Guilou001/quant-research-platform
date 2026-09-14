# 019 Les facteurs des cryptomonnaies paient-ils leur rotation ?

L'étude construit trois séries à partir de prix publics.
Le marché représente l'exposition générale aux monnaies suivies.
La taille compare les petites et grandes capitalisations, tandis que le momentum compare leurs rendements passés.

## Un exemple fictif

Un portefeuille de 1 000 dollars échange pour 2 000 dollars pendant une semaine.
Avec un coût de 50 points de base par montant négocié, il paie dix dollars.
Cela représente 1 % de son capital avant les autres coûts.

Un rendement hebdomadaire brut positif peut donc devenir négatif.
Cette arithmétique dépend du montant réellement échangé et de la convention de coût.

## Le lien avec la littérature

Liu, Tsyvinski et Wu étudient des facteurs communs sur un univers plus large.
Le texte intégral n'a pas été consulté dans l'expérience initiale.
Il faut donc lire ce travail comme une adaptation documentée, sans revendiquer une réplication intégrale.

La [spécification](../../docs/specs/005-cryptomonnaies-coin-metrics.md) décrit les données communautaires Coin Metrics.
Les fichiers conservent certains actifs disparus, mais seuls 139 actifs possèdent un prix dans l'extraction.
Ce n'est pas l'ensemble des cryptomonnaies ayant existé.

## Le résultat après publication

Le momentum présente un Sharpe net de -0,600 sur 213 semaines après avril 2022, jusqu'au 24 mai 2026.
Le coût de base vaut 50 points de base par unité négociée.
La rotation moyenne publiée pour l'ensemble de l'historique vaut 2,04 fois le capital par semaine.

Cette moyenne de rotation ne doit pas être appliquée comme si elle appartenait à chaque sous-période.
Les calculs nets utilisent les échanges datés.

## Ce qui reste à examiner

La qualité des prix, l'emprunt des positions vendues et les différences entre plateformes limitent une interprétation investissable.
Le résultat rejette cette construction selon les hypothèses retenues.
Il ne démontre pas que tout facteur de cryptomonnaies est dépourvu d'information.

## Vérifier le résultat

Les [mesures enregistrées](results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](run.py) relie ces choix aux fonctions du laboratoire.
