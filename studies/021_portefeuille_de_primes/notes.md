# Notes de l'étude 021

## Ce qui a été décidé avant de voir un chiffre

Les trois jambes et leur provenance, la règle de poids en inverse de
volatilité, l'équipondération comme variante déclarée. La cible de 10 %, le
plafond de 1,5 et le plafond de 1,0 comme variante, les quatre coûts. La
borne du holdout au 2020-01-31, les sept seuils du verdict, et le compte de
douze essais. La configuration de référence est nommée dans `config.yaml`,
et le verdict ne porte que sur elle.

## Ce qui a surpris

Le plafond. Le mélange de trois primes en inverse de volatilité n'a que
4,6 % de volatilité, parce que le mélange valeur et momentum de l'étude 003
en a 2,9 % et reçoit le plus gros poids. La cible de 10 % voudrait une
exposition de 2,2 ; le plafond de 1,5 la bloque pendant 90,4 % des mois, et
le portefeuille réalise 6,7 %. Le plafond était déclaré, il est resté.

Le sens du levier. Sans levier, 0,688 de Sharpe ; avec, 0,629. Le
demi-dollar emprunté coûte cinquante points de base par an et chaque
changement d'exposition quatre points de base, et ces deux coûts retirent
0,06 de Sharpe à un portefeuille qui n'en a que 0,7. Le levier multiplie le
rendement, pas le ratio, et il a un prix.

La tendance. Sa version de l'étude 001, vingt-huit fonds cotés, rend 0,21
de Sharpe net sur 2010-2026 ; l'article en trouve 0,76 sur 137 ans de
contrats à terme. Elle coûte 0,25 au portefeuille, et elle a pourtant rendu
+14,3 % en mars 2020 quand la vente de puts perdait 13,6 %. Une jambe peut
être une mauvaise stratégie et une bonne assurance.

## Les essais ratés

Un, et il a été vu. La première exécution complète lisait +35,0 % sur la
vente de puts en janvier 2007. Le fichier du Cboe porte sept points isolés
entre 1991 et 2004 avant son historique quotidien, et le rendement du
premier mois traversait le trou depuis 2004. Ses chiffres, Sharpe 0,575 et
holdout 0,80, ont été lus avant la correction. Le fournisseur ne garde
désormais que le segment continu, la configuration n'a pas changé, et la
lecture compte comme un essai de plus, treize au lieu de douze.

## Ce qui reste ouvert

Une jambe de tendance sur contrats à terme, que les données gratuites ne
donnent pas. La seule libre est celle des fonds cotés de tendance, DBMF
depuis 2019 et KMLM depuis 2020, trop courtes pour cette fenêtre. Et le
prix réel du levier pour un particulier, que ni cette étude ni la
spécification 007 ne mesurent.
