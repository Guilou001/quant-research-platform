# Notes de l'étude 013

## Ce qui a été décidé avant de voir un chiffre

Le protocole de l'étude 011, avec dix ans d'entraînement au lieu de cinq, la
forêt à cent arbres, et les mêmes seuils. Référence : la régression pénalisée
en carré ; modèle complexe : les arbres amplifiés. Dix-sept essais.

## Ce qui a surpris

Tout est positif. Six méthodes, trente plis, cinq sous-périodes, une
corrélation de rang à t 2,9 pour les six, un décile net à 0,85 pour les arbres
avec un t de 5,1. Aucune étude du laboratoire n'avait rendu cela, et c'est
précisément ce qui a déclenché le contrôle de biais de survie plutôt que la
publication. Un titre du S&P 500 d'aujourd'hui qui a chuté en 2008 a remonté
par construction ; un modèle qui achète les perdants de long terme et les
titres volatils le trouve sans effort, et l'importance par permutation désigne
exactement ces deux variables.

Le premier contrôle, sur le seul momentum, a rendu l'inverse de ce que le
biais laisse attendre : le décile de momentum des survivants rend 1,5 % par an
contre 7,3 % pour les déciles CRSP de Kenneth French, ce que l'étude 002 avait
déjà mesuré. La survie ne flatte pas tous les signaux dans le même sens, et un
seul contrôle ne suffisait pas. Le contrôle a donc été étendu au renversement
à un mois et au renversement à long terme, qui ont chacun un décile publié.

## Les essais ratés

La première exécution du contrôle étendu a échoué sur l'en-tête
d'identification exigé par le fournisseur de Kenneth French : les deux jeux
de renversement n'étaient pas encore dans le cache, et le téléchargement
demande la variable d'environnement `QUANTLAB_USER_AGENT`. Relancé avec elle.

La deuxième a échoué sur le nom du tableau : le fichier des déciles de
renversement à un mois de Kenneth French titre son premier bloc « Aerage Value
Weighted Returns », avec la coquille, alors que les deux autres fichiers
écrivent « Average ». Le tableau se choisit désormais par une règle sur son
nom, et la coquille est écrite ici plutôt que corrigée à la main.

## Ce qui reste ouvert

Refaire la même étude sur un univers qui inclut les radiations, ce que les
données gratuites ne donnent pas. Tant que ce panneau n'existe pas, aucune
étude d'apprentissage transversal sur actions individuelles ne peut conclure
au-delà de ce que dit l'étude 011 : la non-linéarité ne bat pas le linéaire.
