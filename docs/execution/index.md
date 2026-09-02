# Les coûts, l'impact et la capacité

**Implémenté le 2026-09-02**, phase 6 de la feuille de route. Deux modules,
`quantlab.execution.costs` et `quantlab.execution.capacity`, et une étude, la
010, qui les applique aux deux stratégies du laboratoire dont les instruments
ont un volume mesurable.

## Le coût se décompose, et chaque terme s'active séparément

\[
C = Commission + Spread + Slippage + Impact + Borrow + Financing
\]

Un backtest qui ne dit pas lesquels il a activés publie un rendement net qui ne
veut rien dire. Les trois premiers sont proportionnels au montant négocié. Le
quatrième est convexe en taille. Les deux derniers sont des loyers, sur
l'exposition vendeuse et sur l'exposition au-delà du capital.

## L'impact croît en racine carrée de la participation

\[
I_i = \kappa \, \sigma_i \sqrt{\frac{Q_i}{ADV_i}}
\]

La participation est le montant négocié sur un actif rapporté au volume que le
marché y échange par séance. La forme est empruntée à Almgren, Thum, Hauptmann
et Li (2005) et à Gatheral (2010). Le coefficient \( \kappa \) n'est calibré sur
aucune exécution réelle : tout chiffre qui en sort porte le statut **modélisé**.

## La capacité est le capital où le rendement net moyen s'annule

Le module rejoue les mêmes poids à plusieurs tailles de capital. Comme l'impact
croît en racine du capital, le rendement net moyen est une droite en
\( \sqrt{A} \), et le capital d'annulation a une forme fermée :

\[
\bar{r}^{net}(A) = g - s - \sqrt{A}\,K
\qquad\Longrightarrow\qquad
A^{\ast} = \left(\frac{g - s}{K}\right)^{2}
\]

où \( g \) est le brut moyen, \( s \) le demi-écart moyen payé et \( K \) la
charge d'impact moyenne mesurée au capital unité. Le moteur est ensuite relancé
à \( A^{\ast} \), et le rendement net moyen qu'il y rend doit valoir zéro à la
précision machine. Ce contrôle est publié dans l'objet rendu, et un désaccord
hors écrêtage lève une erreur.

Deux entrées sont calculées sans regarder l'avenir : le volume quotidien moyen
en dollars, médiane d'un mois décalée d'une séance, et la volatilité quotidienne
réalisée, décalée de même.

## Le plafond de participation borne la crédibilité du modèle

Au-delà d'une participation de 10 % du volume quotidien, le modèle écrête le
coût et le déclare minorant. Quand la plus grosse transaction dépasse ce plafond
avant le capital d'annulation, la capacité retenue est le capital où le plafond
est atteint. Cette lecture est plus prudente que la forme fermée, et c'est celle
que l'étude 010 publie.

## Ce que la phase ne fait pas

Le coefficient d'impact est déclaré, non mesuré, et la capacité lui est
proportionnelle à la puissance moins deux : le diviser par deux la multiplie par
quatre. L'étude 010 publie donc la sensibilité à deux coefficients et à une
exécution étalée sur cinq séances. Le capital est constant sur tout
l'historique. Aucun carnet d'ordres, aucune file d'attente, aucun impact croisé
entre titres du même secteur.

Six des huit stratégies du laboratoire tournent sur des portefeuilles de
facteurs publiés, sans poids par titre ni volume. Leur capacité est **non
calculable** avec les données gratuites, et c'est écrit tel quel.

La décision d'architecture est l'[ADR-012](../architecture/adr/adr-012-capacite-par-forme-fermee.md).
