# Les formules de référence

Cette page rassemble les définitions que le laboratoire tient pour vraies. Une
formule qui ne figure pas ici et qui apparaît dans le code est un défaut à
corriger, parce qu'une définition financière qui vit à deux endroits finit par
diverger.

Chaque formule renvoie à son implémentation. La docstring de l'implémentation
porte le détail : hypothèses, provenance, limites, alternatives, façon de
vérifier.

## Rendements

**Rendement simple** et **rendement logarithmique** :

\[
r_t = \frac{P_t}{P_{t-1}} - 1
\qquad
r_t^{\log} = \ln\!\left(\frac{P_t}{P_{t-1}}\right) = \ln(1 + r_t)
\]

Le simple s'agrège dans la dimension des actifs, le logarithmique dans celle du
temps. Aucun des deux n'est le bon en général.

Exemple chiffré à retenir. Une hausse de 10 % suivie d'une baisse de 10 % laisse
0,99, soit une perte de 1 %, alors que la moyenne des deux rendements simples
vaut zéro. En logarithme, \(+0{,}09531\) puis \(-0{,}10536\) somment à
\(-0{,}01005\), dont l'exponentielle rend exactement 0,99.

**Croissance annualisée composée** :

\[
CAGR = \left(\frac{V_T}{V_0}\right)^{1/T} - 1
\]

où \(T\) est la durée en **années**, pas en périodes.

Implémentation : `quantlab.analytics.returns`.

## Risque

**Volatilité annualisée** :

\[
\sigma_{ann} = \sigma_{p\acute{e}riode}\sqrt{N}
\]

où \(N\) est le nombre de périodes par an. La racine suppose des rendements non
corrélés dans le temps. Quand ils sont autocorrélés, la correction de Lo (2002)
remplace \(\sqrt{N}\) par :

\[
\sqrt{N + 2\sum_{k=1}^{N-1}(N-k)\,\rho_k}
\]

où \(\rho_k\) est l'autocorrélation d'ordre \(k\). Une autocorrélation positive
fait sous-estimer la volatilité annuelle, donc surestimer le ratio de Sharpe.

**Valeur à risque** et **perte espérée au-delà** :

\[
VaR_\alpha = -\inf\{x : P(R \le x) > \alpha\}
\qquad
ES_\alpha = \mathbb{E}[L \mid L > VaR_\alpha]
\]

La convention du laboratoire exprime les deux en **perte positive**. La perte
espérée est sous-additive, la valeur à risque ne l'est pas (Artzner, Delbaen,
Eber et Heath, 1999).

**Perte depuis le sommet** :

\[
DD_t = \frac{NAV_t - \max_{s \le t} NAV_s}{\max_{s \le t} NAV_s}
\]

Valeurs négatives ou nulles, par convention déclarée.

Implémentation : `quantlab.analytics.risk` et `quantlab.analytics.drawdown`.

## Ratios

\[
Sharpe = \frac{\mathbb{E}[R - R_f]}{\sigma(R)}
\qquad
Sortino = \frac{\mathbb{E}[R - R_f]}{DD_{\text{baissier}}}
\qquad
Calmar = \frac{CAGR}{|MaxDD|}
\]

Le numérateur s'annualise en \(N\), le dénominateur en \(\sqrt{N}\), donc le
ratio annualisé vaut \(\sqrt{N}\) fois le ratio périodique. Le taux sans risque
se soustrait **avant** l'annualisation, jamais après.

Erreur type du ratio de Sharpe sous indépendance (Jobson et Korkie 1981,
corrigée par Memmel 2003) :

\[
\hat{\sigma}(SR) \approx \sqrt{\frac{1 + SR^2/2}{T}}
\]

Implémentation : `quantlab.analytics.ratios`.

## Signal et prédiction

**Coefficient d'information** :

\[
IC_t = \mathrm{Corr}\big(\hat{r}_{i,t+1},\, r_{i,t+1}\big)
\]

calculé en transversal à chaque date, en Pearson ou en rang de Spearman.

**Loi fondamentale de la gestion active** (Grinold, 1989) :

\[
IR \approx IC\sqrt{BR}
\]

où \(BR\) est le nombre de paris **effectivement indépendants**. C'est le point
que la formule cache : mille prédictions fortement corrélées ne valent pas mille
paris. Le laboratoire mesure la largeur effective plutôt que de compter les
lignes.

Implémentation : `quantlab.analytics.ic`.

## Portefeuille

**Volatilité, contribution marginale, contribution au risque** :

\[
\sigma_p = \sqrt{w^\top \Sigma w}
\qquad
MR_i = \frac{(\Sigma w)_i}{\sigma_p}
\qquad
RC_i = w_i \, MR_i
\]

Le théorème d'Euler rend la décomposition **exacte** et non approximative : la
volatilité est homogène de degré un en \(w\), donc \(\sum_i RC_i = \sigma_p\).

**Rotation**, convention du laboratoire :

\[
Turnover_t = \frac{1}{2}\sum_i \left| w_{i,t} - w_{i,t}^{\text{dérivé}} \right|
\]

Le facteur un demi compte un aller-retour une fois. Les poids dérivés sont ceux
vers lesquels le marché a fait glisser le portefeuille avant rééquilibrage :
confondre poids cibles et poids dérivés fait payer des frais fantômes.

**Fonction objectif de l'optimiseur** :

\[
\max_w \; \alpha^\top w - \frac{\lambda}{2} w^\top \Sigma w - \gamma \, C(w - w_{old})
\]

où \(\alpha\) est l'alpha attendu, \(\Sigma\) la covariance, \(\lambda\)
l'aversion au risque, \(C\) le coût de négociation et \(\gamma\) son poids.

**Cible de volatilité** :

\[
L_t = \frac{\sigma^*}{\hat{\sigma}_t}
\]

avec un plafond de levier obligatoire : quand la volatilité prévue approche
zéro, le levier explose, et le plafond est la seule chose qui l'empêche.

Implémentation : `quantlab.analytics.contributions`, `quantlab.analytics.turnover`,
puis `quantlab.portfolio` en phase 5.

## Coûts

\[
C = Commission + Spread + Slippage + Impact + Borrow + Financing
\]

Modèle d'impact en racine carrée, stylisé :

\[
Impact \propto \sigma \sqrt{\frac{Q}{ADV}}
\]

où \(Q\) est la quantité négociée et \(ADV\) le volume quotidien moyen. C'est une
approximation sans microstructure, et elle est déclarée comme telle partout où
elle sert.

Capacité, le capital \(A\) où le rendement net moyen s'annule. Comme l'impact
croît en racine du capital, le net moyen est une droite en \(\sqrt{A}\) :

\[
\bar{r}^{net}(A) = g - s - \sqrt{A}\,K
\qquad\Longrightarrow\qquad
A^{\ast} = \left(\frac{g - s}{K}\right)^{2}
\]

où \(g\) est le brut moyen par période, \(s\) le demi-écart moyen payé et \(K\)
la charge d'impact moyenne au capital unité. Le moteur relancé à \(A^{\ast}\)
doit rendre un net moyen nul à la précision machine ; sinon le calcul lève.

Implémentation : `quantlab.execution.costs` et `quantlab.execution.capacity`,
phase 6, ADR-012.
