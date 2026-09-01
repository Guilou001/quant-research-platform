# Le moteur de validation

Un modèle qui apprend sur des données mélangées au hasard triche, et il triche
d'une façon qui ne se voit pas dans les métriques. Cette page dit pourquoi, et
ce que le laboratoire met à la place.

## L'interdit fondateur

```python
train_test_split(X, y, shuffle=True)  # INTERDIT sur des séries temporelles
```

Mélanger place des observations de 2020 dans l'entraînement et des observations
de 2015 dans le test. Le modèle apprend l'avenir et le rend au passé. La mesure
hors échantillon devient une mesure dans l'échantillon, et elle est excellente.

## Le découpage du temps

```
1995 ─────────────── 2010 │ 2011 ──── 2014 │ 2015 ──── 2019 │ 2020 ─── 2026
      ENTRAÎNEMENT         │  VALIDATION    │     TEST       │  HOLDOUT FINAL
                           │                │                │  (gelé)
```

L'entraînement estime. La validation choisit les paramètres. Le test mesure. Le
holdout final ne sert à rien tant qu'on n'a pas fini, et une fois lu il n'est
plus hors échantillon.

Puis le walk-forward, en deux variantes.

| Variante | Fenêtre d'entraînement | Quand l'utiliser |
|---|---|---|
| **ancré** | croît, part toujours du début | quand la relation est stable et que plus de données aident |
| **glissant** | longueur fixe qui avance | quand la relation change, et qu'un passé lointain nuit |

Le choix se déclare avant de voir les résultats, pas après.

## Le purging et l'embargo

Le problème apparaît dès qu'une étiquette dépend de plusieurs périodes. Si
l'étiquette au temps \(t\) est le rendement sur \(t\) à \(t+20\), alors les
observations voisines partagent de l'information, et une frontière nette entre
entraînement et test n'en est pas une.

```
        étiquette de l'observation t : rendement de t à t+20
        ┌──────────────────────────┐
────────┼────────────┬─────────────┼───────────────────────────
        t         frontière      t+20
        │◄── ENTRAÎNEMENT ──►│◄────── TEST ──────►
                             ▲
                  cette observation d'entraînement CONNAÎT
                  déjà une partie de la période de test
```

Deux gestes le corrigent.

**Le purging** retire de l'entraînement toute observation dont l'étiquette
déborde sur la période de test.

**L'embargo** retire en plus les observations immédiatement postérieures au
test, parce que l'autocorrélation des rendements fait fuiter l'information dans
l'autre sens.

Les deux viennent de López de Prado (2018), *Advances in Financial Machine
Learning*.

## La validation croisée combinatoire purgée

Un seul découpage donne une seule mesure hors échantillon, et cette mesure
dépend du découpage. La CPCV en produit beaucoup.

Le principe : découper l'échantillon en \(N\) blocs, en tester \(k\)
simultanément, et répéter sur toutes les combinaisons. Le nombre de chemins de
test obtenus vaut \(\binom{N}{k} \cdot k / N\), ce qui donne une **distribution**
de performance au lieu d'un point.

C'est cette distribution qui compte. Une stratégie dont le ratio de Sharpe vaut
1,2 en moyenne sur les chemins mais s'étale de \(-0{,}3\) à \(2{,}6\) n'est pas
une stratégie de Sharpe 1,2.

Le laboratoire s'appuie sur `skfolio.model_selection.CombinatorialPurgedCV`
(version 1.0.3, signature vérifiée le 2026-09-01 :
`n_folds=10, n_test_folds=8, purged_size=0, embargo_size=0`) et porte sa propre
implémentation pédagogique à côté, pour que la méthode ne reste pas une boîte
noire.

## Le surapprentissage de backtest

Deux mesures, complémentaires.

**Le ratio de Sharpe dégonflé** (Bailey et López de Prado, 2014) répond à :
compte tenu du nombre d'essais menés et de la dispersion de leurs résultats,
quelle est la probabilité que ce ratio de Sharpe dépasse zéro pour une autre
raison que la chance ? Il exige de connaître le nombre d'essais, ce qui est la
raison pour laquelle le laboratoire les compte tous, y compris les ratés.

**La probabilité de surapprentissage** (Bailey, Borwein, López de Prado et Zhu,
2016) répond à : quelle est la probabilité que la configuration la meilleure
dans l'échantillon soit sous la médiane hors échantillon ? Une probabilité
élevée signifie que le processus de sélection lui-même est cassé, quel que soit
le résultat obtenu.

## La correction pour tests multiples

Chercher parmi \(N\) stratégies revient à faire \(N\) tests, et le seuil de
signification doit en tenir compte. Harvey, Liu et Zhu (2016) montrent que le
seuil usuel de 2,0 en valeur de \(t\) est très insuffisant dans la littérature
sur les facteurs, où des centaines de facteurs ont été testés et publiés.

Le laboratoire implémente Bonferroni, Holm, Benjamini-Hochberg-Yekutieli, et
rapporte ce que chaque correction change au verdict.

## Le bootstrap

Les intervalles de confiance analytiques supposent l'indépendance. Des
rendements ne le sont pas, et un bootstrap indépendant et identiquement
distribué détruit exactement la structure qu'on veut préserver.

Le laboratoire utilise donc le bootstrap par blocs et le bootstrap stationnaire
de Politis et Romano (1994), qui tirent des segments contigus plutôt que des
points isolés.

## Ce que la validation ne peut pas faire

Elle ne répare pas un biais de sélection en amont. Choisir d'étudier le momentum
en 2026 parce qu'il a fonctionné depuis 1993 est un choix informé par l'avenir,
et aucun découpage temporel ne le corrige.

Elle ne remplace pas non plus l'hypothèse économique. Une stratégie qui passe
tous les contrôles sans mécanisme nommé reste une coïncidence bien testée.
