# Notes de l'étude 011

## Ce qui a été décidé avant de voir un chiffre

Le modèle simple à battre est la régression pénalisée en carré, le modèle
complexe les arbres amplifiés. Cinq ans d'entraînement, un an de test, purge
d'un mois, validation sur les vingt-quatre derniers mois de l'entraînement.
Dix-sept essais : treize configurations et quatre multiples de coûts. La
cible de réplication est le R² de la forêt sur les mille plus grandes
capitalisations, 0,63 %.

## Ce qui a surpris

Le R² hors échantillon et la corrélation de rang disent deux choses opposées.
Le premier est positif pour les six méthodes, entre 0,35 % et 0,48 %, dans la
plage de l'article. La seconde est négative pour les six, et sa moyenne par
année est négative de 2021 à 2025. Le R² sans centrage récompense la
prévision du niveau moyen du mois, que la volatilité passée porte quand les
marchés se retournent ; la corrélation de rang ne récompense que l'ordre des
titres, et cet ordre est nul ou inverse. Les deux métriques de l'article
mesurent des choses différentes, et il faut lire les deux.

Les portefeuilles déciles gagnent malgré une corrélation de rang négative,
les arbres à 0,663 net. Les deux déciles extrêmes se comportent autrement que
la masse, et c'est là que la volatilité et l'endettement, les deux variables
qui portent les arbres, trient le mieux. Ce n'est pas une contradiction, c'est
une raison de plus de ne pas conclure sur un seul chiffre.

Le filet élastique à pénalité 0,01 met tous les coefficients à zéro sur
plusieurs plis : sa prévision est alors constante, sa corrélation de rang
n'est pas définie ces années-là, et sa rotation tombe à 3,2 par an. La
validation l'a pourtant préféré à la pénalité 0,001 sur quatre plis sur six,
ce qui dit combien deux ans de validation sont bruités.

## Les essais ratés

La première exécution a échoué au verdict : la configuration portait une clé
`dm_pvalue_max` dans le bloc des critères, que le modèle strict des critères
refuse. La clé est lue à part désormais. Aucun résultat n'a été consulté avant
la correction, les tables ayant été écrites avant l'erreur mais non lues.

La tolérance de réplication écrite dans la configuration, un demi-point de R²
en absolu, n'est pas celle que le moteur de verdict applique : il convertit
tout écart en relatif et exige les 10 % du laboratoire. L'écart de 23 % a donc
échoué. La règle du laboratoire prime, et la configuration le dit maintenant.

## Ce qui reste ouvert

Refaire l'étude sur le panneau quotidien de survivants de l'étude 002, plus
long de vingt ans, pour donner aux arbres ce qui leur manque le plus, du
temps. Ajouter les réseaux de neurones, dont la fabrique existe, quand le
panneau sera assez long pour qu'ils apprennent autre chose que le bruit.
