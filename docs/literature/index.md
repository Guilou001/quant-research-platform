# La littérature

Chaque stratégie du laboratoire vient d'un article, et chaque article a sa
fiche. La fiche existe avant le code : elle porte l'hypothèse économique, la
méthodologie originale, les résultats publiés qui serviront de cible, et les
critiques connues.

Le point le plus important d'une fiche est sa section « Les critiques connues ».
Un article cité mille fois a presque toujours été contredit quelque part, et
répliquer sans connaître la contradiction revient à répliquer à moitié.

## Le gabarit

Quinze sections, dans le même ordre pour toutes les fiches. La question de
recherche, l'intuition économique, les données, l'univers, la méthodologie. Puis
les équations qui comptent, les résultats originaux, les critiques connues, les
problèmes de réplication connus, les biais possibles. Puis nos décisions
d'implémentation, nos écarts avec l'article, nos résultats, notre contrôle de
robustesse, et les références.

Les quatre sections « Nos ... » restent à « non commencé » tant que l'étude n'a
pas tourné. Elles ne s'anticipent pas.

## Règle sur les chiffres

Aucun chiffre d'une fiche ne s'écrit de mémoire. Chaque nombre porte sa source
et son statut : **rapporté** quand il vient de l'article, **non trouvé** quand
la recherche n'a rien donné, **non vérifié** quand un doute subsiste. Un ratio
de Sharpe inventé qui a l'air juste est la faute la plus grave possible ici,
parce qu'il servira ensuite de cible de réplication et fera juger notre code
défaillant alors qu'il aura raison.

## Les familles

| Famille | Ce qu'elle apporte au laboratoire |
|---|---|
| Théorie du portefeuille | Markowitz, Black-Litterman, DeMiguel, Ledoit-Wolf, HRP, loi fondamentale |
| Momentum | Jegadeesh-Titman, Moskowitz-Ooi-Pedersen, Hurst-Ooi-Pedersen, Asness-Moskowitz-Pedersen |
| Qualité et défensif | Quality Minus Junk, Betting Against Beta |
| Portage et volatilité | Koijen et coauteurs, Moreira-Muir |
| Arbitrage statistique | Gatev-Goetzmann-Rouwenhorst, Avellaneda-Lee |
| Apprentissage et exécution | Gu-Kelly-Xiu, Almgren-Chriss, Gârleanu-Pedersen, Lou-Polk-Skouras |
| Surapprentissage | ratio de Sharpe dégonflé, PBO, Harvey-Liu-Zhu, McLean-Pontiff, Chen-Zimmermann |
| Données datées de la SEC | Cohen-Polk-Silli |

Les fiches vivent dans ce répertoire, une par article, et l'index de navigation
du site les liste sous cette page.

## L'ordre de lecture recommandé

Pour comprendre pourquoi le laboratoire est construit ainsi, trois fiches
suffisent, dans cet ordre : le ratio de Sharpe dégonflé, la probabilité de
surapprentissage, puis Harvey, Liu et Zhu. Elles disent toutes les trois la même
chose sous des angles différents, et cette chose est que la plupart des
résultats publiés en finance empirique ne survivent pas à la correction pour le
nombre d'essais.
