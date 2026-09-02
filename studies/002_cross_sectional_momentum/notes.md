# Journal de l'étude 002

Ce fichier porte ce qui n'entre pas dans le rapport. Il dit ce qui a été essayé,
ce qui a échoué, ce qui a surpris, et le compte exact des essais qui alimente le
ratio de Sharpe dégonflé. Il est tenu dans l'ordre où le travail s'est fait.

## Le compte des essais, 53 au total

La règle 8 du `CLAUDE.md` exige que tout essai soit compté, y compris ceux qui
n'ont rien donné, et qu'un balayage de paramètres compte pour autant d'essais
qu'il a de cellules. Le compte ci-dessous est celui que `config.yaml` déclare
sous `params.n_trials`, et il entre dans le Sharpe dégonflé.

**Quarante-quatre essais portent un ratio de Sharpe**, tous listés dans
`results/tables/validation_essais.csv`.

| Famille | Nombre | Ce que c'est |
|---|---:|---|
| `grille_jambe_b` | 32 | les seize cellules J sur K, deux panneaux |
| `comparaison_jambe_b` | 2 | le tri 12 moins 2 détenu un mois, en déciles et en quintiles |
| `jambe_a` | 2 | les déciles de Kenneth French, deux pondérations |
| `jambe_a_controle` | 4 | grandes et petites capitalisations, deux pondérations |
| `delai_jambe_b` | 4 | le même tri exécuté un, deux, trois puis six mois plus tard |

**Cinq essais de plus sont le balayage des coûts**, les cinq multiplicateurs de
`results/tables/robustesse_couts.csv`. Ils ne portent pas de ratio de Sharpe
comparable aux quarante-quatre autres, la stratégie y étant la même sous une
hypothèse de coût différente, et ils n'entrent donc pas dans la VARIANCE des
Sharpe. Ils entrent dans le COMPTE, parce que cinq chiffres ont été regardés.

**Quatre essais n'ont pas de ratio de Sharpe publiable**, et ils sont décrits un
à un ci-dessous, sous les numéros 41 à 43 et 46. Trois autres sont des défauts de
code trouvés en route, les numéros 44 et 45 et le champ mal lu. Ce ne sont pas
des essais économiques. Chacun a pourtant produit un jeu de résultats regardé
avant d'être jeté, et un chiffre regardé est un essai.

**Ce que le compte ne retient pas, et pourquoi.** Les six sous-périodes de
`robustesse_sous_periodes.csv` découpent une seule série, elles ne proposent
aucune stratégie de rechange. Les cinq fenêtres nommées de la jambe A mesurent la
même stratégie sur des périodes différentes. Ni les unes ni les autres n'offrent
un choix dont on aurait retenu le meilleur, et le Sharpe dégonflé corrige
exactement ce choix-là.

**La sensibilité du Sharpe dégonflé au compte, mesurée.** À 44 essais il vaut
0,067, à 53 essais 0,061, à 100 essais 0,017. Le seuil du verdict valant 0,95, le
critère échoue sur toute la plage, et le compte exact ne décide donc de rien
ici.

## Essai 41, abandonné : jambe B ouverte en 1986 avec cinquante titres

Premier passage, la jambe B partait de 1986 avec un plancher de cinquante titres
classables. Mesuré : 216 titres disponibles en 1986. Le tri en dix déciles n'en
met alors que cinq par paquet, et le décile extrême devient le portefeuille de
cinq titres, pas celui d'un décile de marché.

Abandonné pour un plancher de cent titres et un départ en janvier 1991, où 238
titres de l'univers sont cotés. Le paramètre vit dans `config.yaml` sous
`params.min_names` et `params.leg_b_start`.

## Essai 42, abandonné : jambe B sans panneau à décalage

Deuxième passage, la grille ne portait que le panneau sans décalage, sur trois
formations et trois détentions. Résultat mesuré : six cellules sur neuf
négatives, ce qui contredisait l'article sur le signe même.

L'explication tenait au mois de renversement à court terme, que le panneau sans
décalage inclut entièrement. Le panneau à décalage d'une semaine a été ajouté, et
il redresse quinze des seize cellules comparées. La leçon est celle que l'article
énonce sans la chiffrer : le rebond entre cours acheteur et cours vendeur mange
le signal quand la mesure touche la date de formation.

## Essai 43, abandonné : jambe B sans nettoyage des ruptures de prix

Troisième passage, avant l'écriture de `truncate_before_return_breaks`. La jambe
B rendait alors 0,175 % par mois en déciles, contre 0,417 % après nettoyage, et
son écart d'octobre 1993 valait moins 111,5 %.

**C'est la surprise principale de l'étude, et elle a failli produire un résultat
faux.** Un seul rendement mensuel, celui de NVR à plus 2 600 % en octobre 1993,
déplaçait la moyenne de trente-cinq ans de 0,26 point de pourcentage par mois. Il
aurait donné une mesure du biais de survie de l'ordre de cinq à six points par
an, contre les deux à quatre points mesurés après nettoyage, et le récit aurait
été plus spectaculaire. Rien dans les tests de forme ne l'aurait signalé : le
tableau avait le bon nombre de lignes, les bonnes colonnes et aucune valeur
manquante.

Ce qui l'a attrapé est un contrôle qui ne cherchait pas ce défaut. Le calcul du
repli maximal a levé une `DataQualityError` en refusant un rendement simple
inférieur à moins 100 %, ce qui a mené à l'inspection du mois fautif.

Les deux ruptures trouvées, NVR en octobre 1993 et HUBB en octobre 1994, sont
des changements de base de série de prix, non des mouvements de marché. Le seuil
retenu, 400 % par mois, vient de la distribution complète des rendements mensuels
de l'univers. Deux observations le dépassent, et la plus forte hausse RÉELLE vaut
plus 358,9 %, pour Regeneron en février 2000. Le seuil vit dans `config.yaml`
sous `params.max_abs_monthly_return`.

## Essai 44, jeté : exposition brute de deux dans le backtest

L'écart publié par l'article achète un dollar et en vend un, donc son exposition
brute vaut deux. Le backtest a d'abord été lancé ainsi, et le calcul du repli
maximal a échoué sur un mois inférieur à moins 100 %, celui de l'essai 43.

Après nettoyage, l'exposition brute a été ramenée à un, celle d'un portefeuille
déployable dont la moitié est achetée et l'autre vendue. Le rendement du moteur
vaut alors exactement la moitié de l'écart publié, ce qu'un contrôle interne
vérifie à chaque exécution.

**Cette décision a produit le défaut le plus coûteux de l'étude, et il a été
corrigé.** Le seuil de rentabilité ne dépend pas de l'échelle tant que le
rendement et la rotation portent la MÊME exposition brute. Or le seuil de la
jambe A divisait l'écart des déciles, d'exposition brute deux, par la rotation
empruntée à la jambe B, d'exposition brute un. Le seuil publié valait donc
141,06 points de base au lieu de 70,53, exactement le double, et le multiple de
coûts survécu 2,82 au lieu de 1,41. La conclusion de la section des coûts s'en
trouve renversée : la stratégie ne survit plus au double de l'hypothèse de
l'article, elle meurt entre 50 et 100 points de base par sens. Les deux
expositions vivent désormais dans `config.yaml` sous `spread_gross_exposure` et
`backtest_gross_exposure`, et le facteur d'échelle appliqué est publié dans
`results/metrics.json`.

Ce que rien n'aurait signalé : les deux séries avaient le bon nombre de mois, le
bon index et aucune valeur manquante, et le nombre rendu, 141 points de base,
était parfaitement plausible.

## Le test de délai qui ne testait rien, corrigé

Le premier test de délai décalait la SÉRIE DE RENDEMENTS de la jambe A de un à
cinq mois, puis mesurait son ratio de Sharpe sur la fenêtre d'après publication.
Il rendait 0,306, 0,294, 0,269 et 0,249, une décroissance lente dont la fiche
concluait que le classement change peu d'un mois à l'autre.

**Ce test ne mesurait aucun délai.** Décaler une série de rendements déjà
réalisés ne retarde aucune exécution : elle fait glisser la fenêtre de mesure
vers le passé. Vérifié à l'égalité près, la série dite « retardée de cinq mois »
est exactement celle d'août 1993 à janvier 2026. La décroissance observée
n'était que l'échange de cinq mois récents contre cinq mois de 1993.

Le test porte désormais sur la jambe B, la seule des deux qui porte des poids, et
le moteur de backtest les exécute avec le retard demandé. Le verdict s'inverse :
0,189 puis 0,147, 0,075 et 0,007, donc 3,7 % du ratio de Sharpe survit à six mois
de retard, et non 81 %. La leçon est celle du reste de l'étude : un chiffre
plausible produit par un calcul qui ne répond pas à la question est plus
dangereux qu'une erreur qui lève.

## Essai 45, jeté : bootstrap par blocs sur une série sans dépendance

Le rééchantillonnage stationnaire a été demandé par défaut. La règle de Politis
et White rend une taille de bloc moyenne de 1,0, le plancher, et la fonction lève
alors une `ConfigError` disant qu'une moyenne de un rend le tirage indépendant.

Le message avait raison. La série de l'écart après publication ne porte aucune
dépendance sérielle exploitable, et le tirage indépendant est la forme correcte.
Le code choisit désormais l'un ou l'autre selon la taille de bloc mesurée, et le
résultat publie laquelle des deux méthodes a servi.

## Essai 46, jeté : appariement des deux jambes sur la date brute

Le premier calcul du biais de survie rendait 298 mois communs sur les 426
attendus, et un écart de 0,57 point de pourcentage par an avec un t de 0,15.

La cause n'est pas économique. Kenneth French date ses mois du dernier jour du
CALENDRIER, Yahoo de la dernière SÉANCE. Mars 1991 tombe donc le 31 chez l'un et
le 28 chez l'autre, et l'intersection des index perdait un mois sur trois. Aucune
erreur n'était levée, aucun avertissement n'était écrit, et le tableau publié
portait sa colonne `n_periods` à 298 sans que rien n'attire l'œil.

**La leçon de méthode.** Une intersection d'index qui rend un résultat plausible
est le pire des cas. Le contrôle qui l'a attrapée est le rapport du nombre de
mois communs au nombre de mois attendus, et il vaut désormais 426 sur 426. Ce
rapport est publié dans `results/metrics.json` sous `leg_b_common_months`.

Après correction, l'écart passe de 0,57 à 2,04 points de pourcentage par an et
son t de 0,15 à 0,61.

## Ce qui a surpris, au-delà des essais jetés

**Le signe du biais de survie.** L'énoncé de la mission demandait de combien le
biais de survie GONFLE le rendement du momentum. Il ne le gonfle pas, il le
retire, de 2,04 à 4,34 points de pourcentage par an selon la référence. Le
mécanisme est visible dans le profil des déciles de la jambe B, où le décile
perdant rapporte 1,978 % par mois, davantage que les huit déciles suivants. Un
titre ne se trouve dans l'univers d'aujourd'hui qu'après avoir survécu, donc les
perdants d'hier qui y figurent sont ceux qui sont remontés.

**La chute du t n'est pas significative.** Le t passe de 5,12 à 1,75, ce qui
paraît décisif. La régression de l'écart sur une indicatrice d'après publication,
avec erreurs types corrigées à la Newey-West, rend pourtant une valeur p de
0,115. Les deux faits doivent être énoncés ensemble, et le second contrarie le
premier.

**Le renversement de janvier a grossi.** L'article mesure moins 6,86 % en janvier
sur 1965-1989. Nous mesurons moins 5,26 % sur la même fenêtre et moins 5,87 %
après publication, avec un t de moins 2,73. La saisonnalité que l'article
attribue à la vente fiscale de fin d'année est donc l'une des rares choses qui ne
se soient pas affaiblies.

**Le renversement du 1975-1979.** L'article publie moins 0,44 % par mois pour
cette sous-période, la seule négative des cinq. Nous mesurons plus 0,17 % en
équipondération, donc la plus faible des cinq mais positive. Le signe ne se
retrouve pas, et l'ordre des sous-périodes non plus : notre plus mauvaise
sous-période pondérée par la capitalisation est 1980-1984 à plus 0,92 %, quand
l'article donne 1975-1979.

**Le tri par déciles n'apporte plus rien au facteur publié.** L'alpha
équipondéré contre les cinq facteurs de Fama et French plus le momentum de
Carhart passe de plus 7,26 % par an sur la fenêtre de l'article à moins 0,11 %
après publication. Le R² reste au-dessus de 0,67 dans les quatre fenêtres
publiées par la fiche, donc le tri est très largement le facteur lui-même,
amplifié d'un facteur 1,08 à 1,57. Les quatre autres fenêtres du fichier
descendent jusqu'à 0,660.

## Deux défauts d'infrastructure, signalés et non corrigés

**Trois journaux lèvent au lieu d'écrire.** Les appels des lignes 283 de
`quantlab/experiments/registry.py` et 439 et 564 de
`quantlab/strategies/base.py` passent la clé `name` dans leur `extra`. Cette clé
est réservée par la bibliothèque standard, qui lève une `KeyError` avant même de
fabriquer la ligne. Les deux registres sont donc inutilisables tant que ces
journaux sont actifs au niveau INFO.

Le contournement retenu élève le niveau des deux journaux le temps d'écrire, ce
qui empêche la ligne fautive d'être fabriquée. Aucun test du dépôt ne couvre
`quantlab.experiments`, ce qui explique la survie du défaut. La correction tient
en trois renommages, et cette étude n'a pas le droit d'y toucher.

**Un champ mal nommé m'a fait publier quatre fois la même valeur.**
`FactorRegressionResult.alpha_annualized` est un BOOLÉEN qui dit si `alpha` est
annualisé, non la valeur annualisée. Le lire comme un nombre rendait 100,0 pour
toutes les fenêtres, valeur assez ronde pour attirer l'œil. Une valeur moins
ronde serait passée.

## Ce qui reste ouvert

La décomposition en trois sources de l'article, celle qui sépare la dispersion
des rendements espérés, la synchronisation du facteur commun et l'autocovariance
des composantes propres, demande des rendements par titre sur 1965-1989. La jambe
A ne les fournit qu'agrégés et la jambe B ne remonte pas si haut. Le test de
retard de Lo et MacKinlay est écarté pour la même raison.

Le rendement de radiation n'est pas modélisé. L'article ne dit pas comment il
traite les titres sortis de la cote, et l'information est déclarée non trouvée
dans la fiche de littérature.
