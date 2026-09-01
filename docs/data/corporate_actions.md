# Les actions de société, et les trois prix qu'il ne faut pas confondre

Trois prix coexistent pour le même titre au même moment, et les mélanger produit
des rendements faux de plusieurs centaines de pour cent.

| Prix | Ce qu'il est | À quoi il sert |
|---|---|---|
| **brut** | le prix effectivement coté ce jour-là | reconstituer un carnet, calculer un nombre d'actions |
| **ajusté des divisions** | le prix brut corrigé des seules divisions | comparer une série de prix dans le temps |
| **rendement total** | le prix ajusté des divisions et des dividendes réinvestis | mesurer la performance d'un détenteur |

Une division deux pour un divise le prix par deux sans que le détenteur perde
quoi que ce soit. Un rendement calculé sur les prix bruts affiche alors
\(-50\,\%\) un jour donné, et ce chiffre entre dans la volatilité, dans le
drawdown maximal et dans tous les ratios.

## Ce que nous traitons, et comment

| Événement | Traitement | Source |
|---|---|---|
| Division et division inversée | prix ajusté rétroactivement | facteur de la source, contrôlé par `check_split_anomaly` |
| Dividende ordinaire | inclus dans le prix ajusté de Yahoo (`adj_close`) | source |
| Dividende spécial | traité comme un dividende si la source le fait | non vérifié cas par cas |
| Fusion et absorption | non traité | limite déclarée |
| Scission | non traité faute de données | limite déclarée |
| Radiation | non traitée, les titres radiés ne sont pas rendus | voir [biais de survie](survivorship_bias.md) |

Les trois derniers manques sont écrits parce qu'ils sont réels. Une scission non
traitée produit un saut de prix qui ressemble à une perte, et un contrôle de
qualité le signale sans savoir le corriger.

## L'ajustement rétroactif, et pourquoi l'horodatage compte

Le prix ajusté d'aujourd'hui n'est pas celui d'hier. Chaque dividende versé
modifie **toute** l'histoire ajustée en amont. Télécharger la même série à six
mois d'écart rend donc deux séries différentes.

Conséquence pratique : un résultat n'est reproductible que si le manifeste porte
`download_timestamp`, et si la copie brute correspondante existe dans `raw`.
C'est la raison pour laquelle `raw` est immuable.

## Les contrôles qui gardent tout cela

| Contrôle | Ce qu'il attrape | Ce qu'il laisse passer |
|---|---|---|
| `check_extreme_returns` | les rendements quotidiens au-delà d'un seuil | un vrai krach, qui est un faux positif |
| `check_split_anomaly` | un saut proche d'un rapport simple sans mouvement de volume | une division au rapport inhabituel |
| `check_ohlc_consistency` | un haut sous un bas, un volume négatif | une barre cohérente mais fausse |
| `check_stale_prices` | un prix figé plusieurs séances | un titre réellement sans transaction |

Chaque contrôle documente ce qu'il **laisse passer**, parce qu'un contrôle dont
on croit qu'il attrape plus qu'il n'attrape est pire que pas de contrôle.
