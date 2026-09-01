# Les coûts, l'impact et la capacité

**Non implémenté au 2026-09-01.** C'est la phase 6 de la feuille de route.

Le levier n'est pas gratuit, et une stratégie sans coûts modélisés n'a pas de
rendement net. La phase 6 apporte la décomposition complète :

\[
C = Commission + Spread + Slippage + Impact + Borrow + Financing
\]

Chaque composante est activable séparément, et un backtest qui ne dit pas
lesquelles il a activées publie un rendement net qui ne veut rien dire.

Le modèle d'impact retenu sera la racine carrée,
\( Impact \propto \sigma \sqrt{Q / ADV} \), déclaré comme **modélisé** partout
où il sert. Les données gratuites ne portent ni carnet d'ordres ni historique de coût
d'emprunt. L'information utile d'une étude sera donc moins l'alpha net central
que le multiple de coûts à partir duquel la stratégie meurt.
