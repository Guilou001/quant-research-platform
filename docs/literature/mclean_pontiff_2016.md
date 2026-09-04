# Does academic research destroy stock return predictability?

| | |
|---|---|
| **Auteurs** | R. David McLean, Jeffrey Pontiff |
| **Année** | 2016 |
| **Revue ou source** | The Journal of Finance, vol. 71, no 1, janvier 2016, p. 5-32, DOI 10.1111/jofi.12365 |
| **Lien** | Résumé lu le 2026-09-03 par l'interface Crossref, <https://api.crossref.org/works/10.1111/jofi.12365> ; l'éditeur et SSRN ont refusé l'accès automatisé ce jour-là, et l'article n'a pas été lu en entier |
| **Statut de réplication** | étude 014, sur les huit séries du laboratoire plutôt que sur les 97 caractéristiques de l'article |

Ce que cette fiche porte vient du résumé de l'article, statut **rapporté**.
Tout ce qui n'y figure pas est marqué non consulté plutôt que complété.

## La question de recherche

Quand une régularité des rendements d'actions est publiée dans une revue
académique, continue-t-elle d'exister ? Et si elle s'affaiblit, est-ce parce
que l'échantillon d'origine l'avait exagérée, ou parce que des investisseurs
ont lu l'article et l'ont négociée jusqu'à la faire disparaître ?

En mots simples : un truc pour battre le marché survit-il au jour où tout le
monde peut le lire ?

## L'intuition économique

Deux causes se superposent, et les auteurs les séparent par le calendrier.
La première est statistique : un chercheur qui trouve une régularité l'a
trouvée dans un échantillon, et le maximum de plusieurs essais est en moyenne
au-dessus de sa vraie valeur. La baisse entre l'échantillon de l'article et les
années qui le suivent, avant que l'article ne paraisse, borne cet effet par le
haut. La seconde est économique : une fois l'article public, des investisseurs
prennent la position, et leurs achats et leurs ventes rapprochent le prix de sa
valeur. La baisse supplémentaire après publication mesure cet apprentissage.

## Les données

Le résumé annonce 97 variables dont la littérature a montré qu'elles
prédisent les rendements transversaux des actions américaines. Les sources,
les dates et la construction des portefeuilles ne sont pas dans le résumé :
non consulté.

## L'univers

Actions américaines. Le détail des filtres n'est pas dans le résumé : non
consulté.

## La méthodologie

Pour chaque variable, un portefeuille et trois fenêtres : celle de l'article
d'origine, la fenêtre entre la fin de cet échantillon et la publication, et la
fenêtre après publication. Les rendements des trois fenêtres sont comparés,
et la baisse relative de la seconde et de la troisième par rapport à la
première est la mesure. La forme exacte de la régression n'est pas dans le
résumé : non consulté.

## Les équations qui comptent

La décomposition du résumé se lit comme une soustraction. Si la baisse hors
échantillon vaut 26 % et la baisse après publication 58 %, la part attribuée
aux investisseurs informés par la publication vaut 58 moins 26, soit 32 %. La
première borne par le haut l'effet du surapprentissage, la seconde y ajoute
l'effet de la publication.

## Les résultats originaux

Rapportés, résumé de l'article. Les rendements des portefeuilles sont 26 %
plus bas hors échantillon et 58 % plus bas après publication. Les auteurs en
déduisent une baisse de 32 % due aux transactions informées par la
publication. La baisse après publication est plus forte pour les prédicteurs
au rendement plus élevé dans l'échantillon. Les rendements restent plus
élevés pour les portefeuilles concentrés sur des actions au risque
idiosyncratique élevé et à la liquidité faible. Après publication, les
portefeuilles de prédicteurs deviennent plus corrélés entre eux. La
conclusion des auteurs est que les investisseurs apprennent les erreurs de
prix dans les publications académiques.

## Les critiques connues

Jacobs et Müller ont étudié la même question hors des États-Unis et n'ont pas
trouvé de baisse après publication sur les marchés étrangers, ce qui
affaiblit l'explication par l'apprentissage des investisseurs. Référence citée
de mémoire, Journal of Financial Economics, 2020, non revérifiée le
2026-09-03. Le laboratoire n'a consulté aucune autre critique.

## Les problèmes de réplication connus

Le jeu de données en source ouverte de Chen et Zimmermann, que le laboratoire
cite dans ses sources, refait des centaines de ces portefeuilles et publie leur
comportement après publication. Non consulté sur ce point précis.

## Les biais possibles

La date de publication est celle du numéro de la revue, alors que les
documents de travail circulent des années avant. La fenêtre « hors échantillon,
avant publication » contient donc des mois où l'article était déjà lu, ce qui
pousse sa baisse vers celle de la fenêtre suivante. Les 97 variables sont
celles qui ont été publiées, donc celles qui ont réussi dans leur échantillon.
La baisse hors échantillon mesure ce biais de sélection, et c'est le sens que
les auteurs lui donnent.

## Nos décisions d'implémentation

L'étude 014 applique les trois fenêtres aux huit séries de tête du
laboratoire, avec la fin d'échantillon et le mois de publication de chaque
article lus dans sa fiche. La mise en commun se fait par la moyenne des
rapports de rendement et par une régression des rendements normalisés sur
deux indicatrices, effet fixe par stratégie, erreurs types groupées par mois.

## Nos écarts avec l'article

Huit stratégies au lieu de 97 caractéristiques, de toutes classes d'actifs et
non des tris d'actions américaines. Une fenêtre hors échantillon n'est mesurée
que si elle compte au moins vingt-quatre mois.

## Nos résultats

Étude 014, verdict `EXPERIMENTAL`. Les huit stratégies perdent après
publication, 73 % du rendement mensuel moyen par la moyenne des rapports et
67 % par la régression, contre 58 % dans l'article. Étude 016, sur 208 portefeuilles de Chen et Zimmermann : 47 % en moyenne,
58 % en médiane. La part perdue ne dépend pas de la force du prédicteur,
alors que le niveau perdu en dépend, corrélation de rang 0,54. La baisse entre la fin de
l'échantillon et la publication vaut 3 % à 8 %, contre 26 % dans l'article.

## Notre contrôle de robustesse

Retirer une stratégie à la fois laisse la baisse après publication entre 61 %
et 77 %. L'hétérogénéité annoncée par l'article, une baisse plus forte quand
le rendement de l'échantillon est plus élevé, ne se retrouve pas sur huit
stratégies, corrélation de rang de 0,12. Le test n'a aucune puissance à cet
effectif.

## Références

McLean, R. D. et Pontiff, J. (2016). Does Academic Research Destroy Stock
Return Predictability? The Journal of Finance, 71(1), 5-32.
DOI 10.1111/jofi.12365.
