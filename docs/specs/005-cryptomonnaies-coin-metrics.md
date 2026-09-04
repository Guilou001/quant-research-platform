# Spécification 005 : lire les prix et les capitalisations quotidiens des cryptomonnaies, actifs disparus compris

**Statut** : acceptée le 2026-09-04.
**Règles concernées** : 1, 4, 5, 13.

## Ce que cela doit faire

Le laboratoire doit pouvoir rejouer les trois facteurs de Liu, Tsyvinski et
Wu (2022), marché, taille et momentum, sur un univers de cryptomonnaies qui
garde les actifs disparus, avec des capitalisations datées. Mesuré le 2026-09-04 : CoinGecko gratuit ne rend qu'un an d'historique, et
Coinbase n'a pas de capitalisation. Les CSV communautaires de Coin Metrics
portent, pour plus de mille actifs et depuis leur naissance, le prix en
dollars et la capitalisation courante. La licence est CC BY-NC 4.0, avec un
retard de publication de quelques mois. C'est la source.

En mots simples : un fichier par monnaie, un prix et une taille par jour,
depuis le premier jour de chaque monnaie, mortes comprises.

## Ce que le dépôt porte déjà, et qui sera appelé plutôt que recopié

`BaseProvider` et le cache brut ; `quantlab.analytics.returns.resample_returns`
pour passer en semaines ; `quantlab.models.panel` pour les rangs ; le moteur
de backtest et le moteur de verdict.

## Les critères d'acceptation, mesurables

1. La liste des actifs vient de l'arbre du dépôt, en un appel, et compte plus
   de mille fichiers, mesuré.
2. Le fichier de BTC, lu par le fournisseur, rend un prix et une
   capitalisation le 2017-12-17, jour du sommet de 2017, et la capitalisation
   vaut le prix multiplié par l'offre à moins de 1 %.
3. Un actif disparu, LUNA de Terra en mai 2022, garde ses prix jusqu'à sa
   chute, mesuré.
4. Le manifeste porte la licence CC BY-NC 4.0 et le retard de publication.
5. `make test` ne fait aucun appel réseau.

## Les décisions de conception, et ce qu'elles écartent

L'univers d'une semaine est l'ensemble des actifs dont la capitalisation
dépasse un million de dollars cette semaine-là, comme dans l'article, et non
les plus gros d'aujourd'hui. Le fichier d'un actif est lu en entier depuis le
dépôt public, sans clé ; un miroir local n'est pas commité.

## Le plan, en étapes vérifiables

1. Le fournisseur et ses analyseurs, testés sur un extrait à la main.
2. L'étude 019 : les trois facteurs, la fenêtre de l'article 2014-2020, puis
   après publication 2022-2026.

## Hors périmètre

Les données à la minute, les carnets d'ordres, les rendements de jalonnement.
