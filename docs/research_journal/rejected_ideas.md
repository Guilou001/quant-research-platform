# Les idées rejetées

Cette page est aussi importante que les résultats. Une stratégie qui échoue est
une information ; la taire produit le biais de publication qui rend la
littérature financière si difficile à répliquer.

Elle sert aussi à quelque chose de très concret. Le ratio de Sharpe dégonflé a
besoin du nombre d'essais menés. Chaque ligne ici est un essai, et l'oublier
gonfle mécaniquement tous les résultats gardés.

## Le gabarit

| Champ | Ce qu'il porte |
|---|---|
| Date | quand l'essai a été mené |
| Idée | ce qui a été testé, en une phrase |
| Hypothèse économique | pourquoi cela aurait dû fonctionner |
| Ce qui a été mesuré | les chiffres, avec leur échantillon et leurs coûts |
| Pourquoi c'est rejeté | l'étape du parcours qui a échoué |
| Ce que cela apprend | ce qui reste utile de l'essai |

## Les rejets

Trois des huit réplications de la phase 4 sont rejetées, et chacune l'est pour
une raison différente. Aucune n'échoue faute de se répliquer.

### 2026-09-02, portefeuilles gérés en volatilité

**Idée.** Diviser un facteur par sa variance réalisée du mois précédent produit
de l'alpha (Moreira et Muir, 2017).

**Hypothèse économique.** La volatilité est prévisible à court terme alors que le
rendement attendu ne l'est pas, donc réduire l'exposition quand la volatilité
monte améliore le rapport rendement sur risque.

**Ce qui a été mesuré.** L'alpha se réplique sur huit contrôles sur huit, dont
l'erreur type au centième, 1,565 contre 1,56. La version réellement négociable,
l'écart couvert par un bêta estimé sur le passé, rapporte -0,32 %/an brut et
-1,30 %/an net de dix points de base, avec un ratio de Sharpe hors échantillon
de -0,362 sur 134 mois.

**Pourquoi c'est rejeté.** Le signe du ratio de Sharpe hors échantillon. La
constante de calibrage de l'article est choisie en connaissance de tout
l'échantillon, et l'estimer en expansion suffit à faire disparaître le gain.

**Ce que cela apprend.** Un article peut se répliquer parfaitement et rester
inutilisable. La réplication et l'investissabilité sont deux questions
distinctes.

### 2026-09-02, parier contre le bêta

**Idée.** Acheter les titres à faible bêta avec du levier et vendre ceux à fort
bêta produit un alpha (Frazzini et Pedersen, 2014).

**Hypothèse économique.** Les intervenants qui ne peuvent pas emprunter achètent
du bêta à la place, donc ils le paient trop cher.

**Ce qui a été mesuré.** Le facteur publié ne s'affaiblit pas après l'article,
0,703 contre 0,689, p = 0,960. Mais un détail d'estimation décide de tout : le
rétrécissement du bêta de 0,6 vers un. Le ratio de Sharpe du facteur reconstruit
au niveau du titre passe de 0,394 sans rétrécissement à -0,001 au réglage de
l'article. Le CLASSEMENT des titres est pourtant identique dans les deux cas, et
le bêta réalisé du facteur passe de +0,081 à -0,182.

**Pourquoi c'est rejeté.** Notre reconstruction au réglage de l'article ne
produit pas d'alpha, et le paramètre qui décide n'est pas justifié par une
mesure.

**Ce que cela apprend.** Une hypothèse de construction non discutée peut porter
tout le résultat. Le constat rejoint la critique de Novy-Marx et Velikov.

### 2026-09-02, arbitrage statistique sur résidus d'analyse en composantes principales

**Idée.** Les résidus d'un modèle factoriel reviennent à leur moyenne, et le
s-score dit quand entrer (Avellaneda et Lee, 2010).

**Hypothèse économique.** Les écarts de valorisation entre titres d'un même
secteur se referment, parce que des arbitragistes les referment.

**Ce qui a été mesuré.** Le ratio de Sharpe brut se réplique presque exactement,
1,460 contre 1,44 publié. Le coût de seuil de rentabilité vaut 3,92 points de
base par unité négociée, contre les 5 points de base par transaction que
l'article lui-même retient. Hors échantillon, après 2010, le ratio net vaut
-1,060 avec un t de -4,20 et un pire repli de -85,4 %.

**Pourquoi c'est rejeté.** La stratégie meurt sous les coûts que son propre
article suppose, et la perte hors échantillon est établie plutôt que conjecturée.

**Ce que cela apprend.** Une rotation annuelle de 344 fois transforme un écart de
quelques points de base en la totalité du rendement.

### 2026-09-02, portefeuille de huit stratégies à parité de risque

**Idée.** Combiner les huit stratégies répliquées par un budget de risque
estimé chaque année sur le passé.

**Hypothèse économique.** Leurs mauvais mois ne tombent pas aux mêmes dates, et
la loi fondamentale multiplie l'avantage par la racine du nombre de paris
indépendants.

**Ce qui a été mesuré.** Corrélation moyenne de 0,097, largeur effective de
5,4 paris sur huit. Parité de risque nette : Sharpe 0,652 sur 198 mois hors
échantillon contre 0,693 pour la meilleure stratégie seule ; 0,239 sur le
holdout 2020-2026, t de 0,585. Quatre allocations sur six battent la meilleure
jambe, dont la parité hiérarchique à 0,900.

**Pourquoi c'est rejeté.** La référence désignée avant le calcul ne bat pas la
meilleure jambe, et rien ne survit au holdout. La parité hiérarchique n'est pas
retenue parce qu'elle a été vue gagner parmi six essais.

**Ce que cela apprend.** La diversification travaille, et la discipline de la
référence déclarée empêche de le transformer en résultat.

## Le décompte des essais

| Famille de stratégies | Essais menés | Retenus | Rejetés |
|---|---:|---:|---:|
| Momentum temporel | 73 | 0 | 0 |
| Momentum transversal | 53 | 0 | 0 |
| Valeur et momentum | 207 | 0 | 0 |
| Qualité | 67 | 0 | 0 |
| Bêta défensif | 144 | 0 | 1 |
| Gestion de la volatilité | 89 | 0 | 1 |
| Arbitrage statistique | 49 | 0 | 1 |
| Portage | 33 | 0 | 0 |
| Portefeuille multi-stratégies | 20 | 0 | 1 |
| Capacité, deux stratégies chiffrables | 8 | 0 | 1 |
| Apprentissage transversal, six méthodes | 17 | 0 | 1 |
| Portefeuille multi-stratégies, séries nettes | 20 | 0 | 1 |
| Apprentissage transversal, quarante ans de survivants | 17 | 0 | 1 |
| **Total** | **797** | **0** | **8** |

Ce tableau alimente directement `quantlab.validation.dsr`. Il se met à jour à
chaque expérience, y compris celles qui ne mènent nulle part.

Comment le lire, en deux constats. Le premier est que 797 essais ont été menés
et qu'aucun n'a produit une stratégie retenue, ce qui est exactement ce que la
correction pour tests multiples sert à rendre visible. Le deuxième est que les
207 essais de l'étude 003 ramènent son ratio de Sharpe dégonflé à 0,000012 :
avoir beaucoup cherché coûte, et ce coût est chiffré plutôt que passé sous
silence.

Une colonne « retenus » à zéro n'est pas un échec du laboratoire. C'est le
résultat de la phase 4, et il est cohérent avec ce que Harvey, Liu et Zhu (2016)
prédisent d'une littérature où des centaines de facteurs ont été testés avant
publication.
