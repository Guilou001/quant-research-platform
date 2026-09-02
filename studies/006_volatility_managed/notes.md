# Journal de l'étude 006

Ce fichier porte ce que le README ne porte pas : les essais qui n'ont rien donné, les fausses pistes,
et les surprises. Le compte des essais qui entre dans le ratio de Sharpe dégonflé est celui de
`results/tables/trials.csv`, soit **89**.

## Le compte des essais, famille par famille

| Famille | Essais | Ce qu'elle couvre |
|---|---:|---|
| `in_sample` | 8 | Un par facteur, réplication du tableau 1 |
| `real_time` | 8 | Un par facteur, constante en expansion |
| `combination` | 16 | Quatre aversions par quatre fenêtres |
| `costs_ex_post` | 4 | Quatre taux de coût, version ex post |
| `costs` | 4 | Quatre taux de coût, version en temps réel |
| `cost_multiple` | 6 | Six multiples de coût |
| `hedge` | 1 | Bêta de couverture de plein échantillon |
| `delay` | 3 | Trois délais d'exécution |
| `sweep` | 35 | Sept mesures de variance par cinq plafonds de levier |
| `window` | 4 | Quatre fenêtres minimales de la constante |
| **Total** | **89** | |

Le balayage compte pour autant d'essais qu'il a de cellules, règle 8. Les trente et une cellules du
balayage dont le ratio de Sharpe net est inférieur à -0,05 sont dans le compte.

**Le compte a été corrigé le 2026-09-02, de 78 à 89.** La première version enregistrait les quatre
taux de coût de la version en temps réel et oubliait les quatre de la version ex post, les six
multiples de coût, et le bêta de couverture de plein échantillon. Onze évaluations de performance
étaient donc menées sans être comptées, et une phrase de ce fichier affirmait le contraire. L'erreur
ne flattait rien : le ratio dégonflé passe de 3,5e-26 à 7,0e-37 et le seuil de Bonferroni de 3,41 à
3,45, contre une statistique t observée de -1,18. Deux essais restent hors du compte et sont nommés :
la variante de Newey-West, non exécutée, et les huit régressions d'extension, qui portent la série de
l'article plutôt qu'une stratégie candidate.

## Le front 1, et la fausse piste du nombre de séances

**Ce qui a été essayé d'abord.** L'ancre du 2026-09-02 suggérait que l'écart de huit mois venait
probablement de la date de départ. Quatre dates ont donc été essayées, juillet 1926, août 1926,
novembre 1926 et janvier 1927. Aucune ne rend 1 065 : les deux premières donnent 1 073, la troisième
1 070, la quatrième 1 068. La piste est morte en une exécution.

**La deuxième fausse piste, plus séduisante.** L'équation (2) de l'article écrit une somme de
\(d = 1/22\) à 1, avec 22 au dénominateur. Exiger un nombre minimal de séances dans le mois semblait
donc naturel. Le seuil de dix-huit séances rend 1 066 pour le marché, à une unité de la cible, et
c'est exactement le genre de coïncidence qui fait accepter une explication fausse. Le contrôle qui
l'a tuée est le second échantillon : le même seuil retire cinq mois à l'échantillon de 1963 et rend
624 au lieu de 621. Un seul mécanisme doit expliquer les deux écarts, et celui-là n'y arrive pas.

**Ce qui a fermé la question.** L'écart vaut exactement huit dans les deux échantillons, 1 073 contre
1 065 et 629 contre 621. Un écart constant en niveau, et non en proportion, désigne un décalage de
borne. Reculer la fin de décembre 2015 à avril 2015 rend les six comptes exacts, momentum compris.
C'est le genre de raisonnement qu'une seule des deux séries n'aurait pas permis.

**Ce qui reste ouvert.** Les deux facteurs q rendent 579 mois contre 575 publiés à la même date de
fin. Un départ en juin 1967 au lieu de janvier 1967 rend le compte exact, et c'est la convention
retenue, déclarée dans `config.yaml` sous `global_q_start`. Nous ne savons pas si le millésime de
2015 commençait en juin ou si les auteurs ont coupé, et c'est écrit tel quel.

## La surprise principale, et pourquoi elle a changé le récit

L'hypothèse de travail était que la constante rétrospective GONFLE l'alpha. Elle est fausse, mesuré.

Sur les mêmes 1 079 mois, l'alpha du marché vaut 2,60 % avec la constante ex post et 2,44 % avec la
constante en temps réel, soit 0,16 point de moins. La statistique t, elle, tombe de 1,79 à 1,25, et le
ratio d'appréciation de 0,190 à 0,133. Le mécanisme est dans la volatilité, pas dans la moyenne. La
version en temps réel porte 1,58 fois la volatilité du marché, contre 1,20 pour la version ex post.
La constante ex post agit donc en tenant le dénominateur, ce qu'elle est faite pour faire, et non en
poussant le numérateur.

**Ce que cela oblige à écrire.** Une première version du README annonçait que « l'alpha passe de 4,74
à 2,44 », ce qui aurait attribué à la fuite un effet qui vient pour l'essentiel du changement
d'échantillon. La fenêtre en expansion consomme 120 mois, donc elle commence en août 1936 et perd la
Grande Dépression, où la stratégie gagnait le plus. La phrase a été refaite en deux étapes séparées,
4,74 vers 2,60 pour l'échantillon et 2,60 vers 2,44 pour la constante.

## La validation croisée combinatoire, d'abord inutile

**Le premier essai n'a rien mesuré.** Appliquer `cpcv_performance_distribution` à la série de
rendements de l'écart couvert rend sept chemins de ratio de Sharpe identiques, à l'écart type nul
près. C'est mathématiquement forcé : un chemin de validation croisée combinatoire reconstruit
l'échantillon entier, et une série figée ne dépend pas du bloc d'apprentissage.

**Le correctif.** La validation croisée juge le PROCESSUS de sélection. Sur chaque bloc
d'apprentissage, la meilleure des trente-cinq configurations du balayage est retenue, puis son
rendement du bloc de test est collecté. Les sept chemins ainsi reconstruits vont de -0,145 à -0,075,
tous négatifs. Le résultat n'a de sens que dans cette seconde forme, et la première est un piège que
n'importe quelle étude à série figée rencontrera.

## Ce qui a été essayé et n'a rien donné

**Le rabais de Harvey et Liu.** `haircut_sharpe` refuse un ratio de Sharpe observé négatif, et cette
refus est correcte : rabattre un nombre négatif n'a pas de sens. La statistique t brute est reportée
telle quelle et la colonne `haircut_status` de `results/tables/deflated_sharpe.csv` le déclare. Le
critère de verdict échoue donc par la valeur mesurée, non par une valeur absente.

**Le GARCH réestimé.** L'annexe A.1 de l'article annonce que des modèles de variance plus élaborés
améliorent le résultat. Sur la version tenable, c'est l'inverse : les cinq cellules du GARCH sont les
cinq plus mauvaises du balayage, de -0,194 à -0,261. Une explication possible est que le GARCH réagit
plus vite, donc négocie davantage, mais elle n'a pas été isolée et reste une conjecture.

**La combinaison moyenne-variance.** Elle devait reproduire le renversement de Cederburg et
coauteurs, 0,42 contre 0,46. Elle ne le reproduit pas : la combinaison l'emporte dans 12 des 16
cellules, de sept points de base d'équivalent certain par an au réglage de référence. Trois
différences de protocole sont déclarées dans le README, et aucune n'a été isolée faute des 103
stratégies qu'ils emploient. Résultat **déclaré non résolu**, et non arrangé.

**Le plafond de levier.** Cinq plafonds ont été essayés. Le meilleur, 1,5, améliore le ratio de
Sharpe net de -0,080 à -0,039, donc il réduit le mal sans le guérir. Aucun plafond ne rend une
cellule positive.

## Les deux défauts trouvés dans notre propre code

**Le compteur d'essais ne comptait rien.** `TrialCounter` est gelé et `record` rend un NOUVEAU
registre. Écrire `counter.record(...)` sans réaffecter laisse le registre vide, et le ratio de Sharpe
dégonflé aurait été calculé sur zéro essai. Le défaut s'est signalé par une exception à la première
exécution complète, parce que `sharpe_variance` refuse moins de deux essais. Sans ce refus, le calcul
serait passé avec un compte faux.

**Le plafond de levier s'appliquait au mauvais endroit.** La première version bornait l'inverse de la
variance AVANT la constante, si bien qu'un plafond de 1,5 ne voulait rien dire en levier. Il borne
maintenant le poids final, et un test le vérifie sur un cas à la main : constante de deux, variance de
0,5, plafond de trois, poids attendu trois et non quatre.

## Les trois défauts trouvés par la contre-vérification du 2026-09-02

**Cinq chiffres faux dans le tableau des coûts du README.** La ligne ex post annonçait 4,33 % brut,
3,53 % net, un Sharpe de 0,245 et un coût de rentabilité de 53,4 points de base, cité deux fois.
`results/tables/costs.csv` porte 4,347, 3,543, 0,247 et 53,64. Tous les autres chiffres du README ont
été confrontés au fichier qui les porte, et aucun autre écart n'a été trouvé.

**Le tableau du délai d'exécution ne partait pas du cas de référence.** Il rebâtissait les poids par
`managed_weights(variance, constant=live.constant)`, ce qui applique un décalage de plus à la
constante et rend le poids du mois \(t\) égal à \(c_{t-1} / \sigma^2_{t-1}\) au lieu de
\(c_t / \sigma^2_{t-1}\). La ligne « un mois » portait donc 1 078 mois et un alpha de 2,4364 quand
la série de référence en porte 1 079 et 2,4382. Le tableau part maintenant de `live.weights`, et la
première ligne coïncide exactement avec la série publiée ailleurs. Le défaut était conservateur, une
information de plus étant retardée, mais il faisait comparer deux objets différents.

**Une étiquette de configuration morte.** `params.subperiod_labels` annonçait « 1926-1955 » et trois
autres bornes que le code ne lisait pas, les étiquettes publiées étant déduites des dates réellement
couvertes. La version tenable ne commence qu'en août 1946, donc l'étiquette morte contredisait la
sortie. La clé est retirée.

## Le contrôle par mutation des tests de causalité

Trois `shift(1)` portent toute la règle 1 de ce module. Ils ont été remplacés par `shift(0)`, et huit
tests sur quarante-trois ont échoué, dont les trois tests de causalité écrits pour cela. Une première
version de ces trois tests perturbait le DERNIER mois et vérifiait que les précédents ne bougeaient
pas : elle passait avec et sans le défaut, donc elle ne testait rien. Les tests perturbent maintenant
un mois du milieu et exigent que la valeur de CE mois reste identique.

## La preuve d'absence d'information future, par troncature

Les trois `shift(1)` ne prouvent pas qu'aucune statistique de fin d'échantillon ne remonte le temps.
La propriété qui le prouve est la stabilité par troncature. La chaîne tenable rebâtie sur 1926 à 2005
doit rendre les mêmes valeurs que celle rebâtie sur 1926 à 2026, sur les mois communs.
Mesuré sur le marché à quatre dates d'arrêt, 1990-12, 2005-06, 2015-04 et 2020-12 : écart maximal
exactement nul, sur 533 à 893 mois. Deux tests portent maintenant cette propriété, dont un contrôle
inverse qui exige que la constante de plein échantillon, elle, se déplace quand on tronque. La
mutation le vérifie : remplacer l'écart type en expansion par celui de plein échantillon fait échouer
trois tests.

## Ce qui n'a pas été fait

**Le panneau B du tableau 1**, qui ajoute les trois facteurs de Fama et French au dénominateur de la
régression. Il ne changerait pas la conclusion sur la constante, qui est l'objet de l'étude.

**Le tableau 2**, les sept portefeuilles moyenne-variance efficients. Il demande une optimisation par
combinaison de facteurs, donc une couche de choix supplémentaire, et il aurait fallu la compter dans
les essais.

**Le tableau 3**, l'interaction avec le témoin de récession du NBER. La série est disponible chez
FRED sous `USREC`, et le fournisseur existe dans le dépôt. Report assumé, faute de valeur ajoutée par
rapport aux sous-périodes déjà publiées.

**Les erreurs types de Newey-West.** L'argument `cov_type` de `spanning_regression` les rend
disponibles. Le cas de référence garde les erreurs types ordinaires pour rester comparable au
tableau 1, et la variante n'a pas été essayée, donc elle ne figure pas dans le compte des essais.

## Un détail de numérotation

Le fichier `studies/README.md` inscrit Moreira et Muir (2017) au numéro 008 de l'ordre prévu, et la
consigne de cette étude demande le numéro 006. C'est le numéro 006 qui a été retenu, et le tableau de
`studies/README.md` n'a pas été modifié, ce fichier n'étant pas dans le périmètre d'écriture de
l'étude.
