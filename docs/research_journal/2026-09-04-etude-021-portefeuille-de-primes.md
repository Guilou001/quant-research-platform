# 2026-09-04 : le portefeuille de primes, écrit avant d'être regardé

## Question

Vingt études ont dit qu'aucun signal publié ne mérite du capital une fois
payé et sorti de sa fenêtre. La part reproductible des fonds spéculatifs est
une construction, pas un signal : plusieurs primes lentes, peu corrélées, à
volatilité constante, avec un levier modéré. Se tient-elle avec des données
gratuites, quand elle est déclarée avant tout calcul ?

## Hypothèse

Écrite dans la configuration de l'étude 021. La tendance, la valeur et le
momentum, et la vente de puts, en inverse de volatilité et empilées à 1,5,
rendent un Sharpe net hors échantillon d'au moins 0,5. Et elles battent la
meilleure jambe seule.

## Expérience

La spécification 007 a d'abord posé les deux briques manquantes, testées à
la main. Le fournisseur des indices du Cboe, dont l'indice PUT depuis 1991.
Le module d'empilement, une exposition à cible de volatilité financée au
taux court plus un écart. Puis l'étude : trois jambes nettes et la marche
avant de l'étude 009. Deux règles de poids fois deux plafonds, trois
retraits, cinq multiples de coûts, douze essais. Le holdout du 2020-01-31
n'est jamais lu avant le verdict.

## Résultat

`REJECTED`, le plus serré du laboratoire. Sharpe net 0,629 sur 187 mois,
0,88 sur les 78 mois du holdout, quatre sous-périodes positives, pire repli
16,0 %, survie à vingt fois les coûts, Sharpe dégonflé 0,974, probabilité
de surapprentissage 0,371. Mais la vente de puts seule rend 0,696 sur les
mêmes mois et le t du holdout vaut 2,30. La tendance sur fonds cotés, 0,21
de Sharpe net, retire 0,25 au portefeuille ; sans elle, 0,878. Le levier
retire 0,06 de Sharpe au lieu d'en ajouter, et plafonne à 1,5 pendant
90,4 % des mois.

Un défaut de données trouvé en route, et vu. Le fichier PUT du Cboe porte
sept points isolés entre 1991 et 2004 avant son historique quotidien, et la
première lecture prenait +35,0 % en janvier 2007 à travers le trou. Le
fournisseur ne garde plus que le segment continu ; la lecture d'avant,
Sharpe 0,575, compte comme un treizième essai.

## Décision

Le verdict reste `REJECTED` et la jambe de tendance reste dedans. La retirer
après l'avoir vue coûter 0,25 serait le geste que l'étude 009 a déjà nommé
surapprentissage. Ce qui est établi vaut quand même. La construction des fonds à primes se
tient gratuitement, et elle égale presque le fonds Style Premia d'AQR avec
une corrélation de 0,21 et un repli de 16 % contre 40 %. Elle ne franchit pas la
barre du laboratoire.

## Question suivante

Une jambe de tendance sur contrats à terme plutôt que sur fonds cotés,
déclarée dans une nouvelle configuration et jugée sur son propre holdout.
Les données gratuites ne la donnent pas encore ; les fonds cotés de
tendance n'ont que six ans.
