# 2026-09-03 : l'audit des phases 9 et 11, et ce qu'il a changé aux chiffres

## Question

Les trois commits de la journée, la réconciliation LEAN, l'étude 014 et la
publication, ont été écrits vite. Que trouve une revue de code à huit angles,
et ce qu'elle trouve change-t-il ce qui a été publié ?

## Hypothèse

Écrite avant la revue. Les chiffres de tête tiennent, 4e-6 par mois et 67 à
73 % de baisse après publication, et les constats portent sur la forme.

## Expérience

La revue de code à haut niveau d'effort sur `5b55a3a..HEAD`, huit angles,
quarante-huit constats bruts, trente-huit distincts une fois les doublons
entre angles retirés. Chacun a été vérifié à la main avant d'être retenu.
Puis les corrections, puis la relance de la réconciliation sur des entrées
fraîches et de l'étude 014.

## Résultat

La première moitié de l'hypothèse tient, la seconde est fausse. Trente-trois
constats ont été corrigés, cinq déclarés sans correction, et quatre des
trente-trois étaient des décisions de conception, pas de la forme.

| Constat de conception | Correction | Ce que cela change |
|---|---|---|
| L'ouverture synthétique rendait le contrôle d'exécution de LEAN inopérant | troisième jeu de données à ouverture réelle | 25 pb/an, le prix mesuré de la convention du laboratoire |
| La série de référence recopiait le passage aux mois de l'étude 001 | `monthly_inputs_from_prices`, appelée par les deux, testée à la main | tables de référence identiques à l'octet avant et après |
| L'algorithme LEAN recopiait l'univers et cinq paramètres | `params.json` écrit par l'export depuis la configuration | rien au résultat, tout à la maintenance |
| L'étude 014 recopiait huit dates que les études portaient sous quatre noms, et 007 divergeait | deux champs typés dans `ExperimentConfig`, lus par 014 | rien au résultat, la date de 007 retenue est celle du numéro |

Trois défauts changeaient un chiffre publié. La régression de l'étude 014
voyait les deux fenêtres de moins de vingt-quatre mois que la moyenne des
rapports excluait. La baisse d'après échantillon passe de 4 % à 8 %, et le
reste bouge à la troisième décimale. Le t des fenêtres venait d'une formule
naïve à côté du t de Lo du laboratoire : la corrélation de rang du test
d'hétérogénéité passe de -0,05 à 0,12, toujours sans puissance à huit unités.
Et trois phrases du README de l'étude 014 comptaient mal ce que sa table
montrait, quatre pour trois, deux pour trois, 61 pour 60.

Sept défauts latents, sans effet sur les chiffres publiés mais qui en
auraient eu au prochain changement. Le pont LEAN laissait passer un trou
intérieur de prix que les deux moteurs auraient lu différemment, et il
absorbait à zéro un financement manquant. Le courriel de repli des tests
réseau contournait le gardien du socle. Le test de coût de la ligne de
commande n'était qu'une borne basse. La version vivait en trois fichiers,
l'image LEAN n'était pas épinglée, et le script de lancement échouait hors
de l'ordre documenté. Tous corrigés, avec un test chacun quand un test a un sens.

Cinq constats sont déclarés plutôt que corrigés. La volatilité de
l'algorithme LEAN se recalcule à chaque décision au lieu de se tenir à jour,
trois secondes par exécution de dix, sans effet sur un chiffre. La régression
de l'étude 014 et les lecteurs de journal de la réconciliation restent dans
leurs scripts, hors de la couverture mesurée par la CI, ce que le tableau des
limites du README dit désormais. Et la conversion des valeurs liquidatives en
mois emploie le rééchantillonnage de pandas plutôt que l'agrégateur du
laboratoire, parce qu'elle part d'une valeur et non d'un rendement.

## Décision

Les corrections sont dans le dépôt, la réconciliation relancée à 4,7e-6 sur
des entrées fraîches, l'étude 014 relancée. La leçon est écrite en ADR-016 :
une page de spécification avant tout chantier d'infrastructure, parce que les
quatre constats de conception y auraient été visibles.

## Question suivante

La feuille de route, `docs/roadmap.md` : ce qui manque au laboratoire pour
que ses stratégies soient meilleures, dans l'ordre où la littérature et nos
propres mesures disent que cela compte.
