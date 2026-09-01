# Le lac de données

Le lac répond à une question et à une seule : quelle donnée exacte a produit ce
résultat ? Si la réponse manque, le résultat n'est pas reproductible, quelle que
soit la qualité du code qui l'a produit.

## Quatre étages, quatre règles

| Étage | Ce qu'il porte | La règle |
|---|---|---|
| `raw` | la réponse de la source, octet pour octet | **immuable**, jamais corrigée, jamais écrasée |
| `bronze` | le même contenu, parsé et typé | aucune décision financière |
| `silver` | la donnée propre | toute décision méthodologique est tracée |
| `gold` | les jeux consommables | pas de manifeste, pas de chargement |

Le raisonnement complet vit dans
[ADR-005](../architecture/adr/adr-005-quatre-etages-du-lac.md).

## Le manifeste

Chaque jeu porte un manifeste, écrit sous `metadata/manifests/`. Vingt-trois
champs, dont ceux qui décident vraiment :

| Champ | Pourquoi il compte |
|---|---|
| `download_timestamp` | Yahoo recalcule ses prix ajustés à chaque dividende, donc la même requête rend des valeurs différentes à six mois d'écart |
| `adjusted` | un prix ajusté et un prix brut ne se comparent pas |
| `point_in_time` | seul un jeu point-in-time peut alimenter un backtest fondamental |
| `survivorship_free` | vaut `True`, `False` ou `None`, et `None` signifie « non vérifié », jamais « probablement bon » |
| `corporate_actions` | dit ce qui a été traité, et donc ce qui ne l'a pas été |
| `revision_policy` | dit si la source réécrit son passé |
| `checksum_sha256` | permet de prouver qu'un fichier n'a pas bougé |
| `parent_datasets` | reconstruit la lignée, d'un jeu gold jusqu'au fichier brut |

Un jeu sans manifeste ne se charge pas en gold. `write_table` lève
`ProvenanceError`.

## Les sources retenues, et leur état mesuré

Toutes les vérifications ci-dessous datent du **2026-09-01**, avec un en-tête
d'identification HTTP.

| Source | Ce qu'elle donne | État mesuré | Point-in-time |
|---|---|---|---|
| Yahoo (`yfinance` 1.7.0) | OHLCV quotidien, FNB, actions | disponible | non |
| SEC EDGAR (`data.sec.gov`) | dépôts, XBRL, horodatages | **200**, contre 403 le 2026-08-29 | **oui**, par les dates de dépôt |
| FRED | séries macro | 200, export CSV sans clé | non |
| ALFRED | millésimes des séries macro | 200 | **oui** |
| Ken French | facteurs MKT, SMB, HML, RMW, CMA, MOM | 200, fichier quotidien à 177 852 octets | non |
| AQR | jeux BAB, QMJ, valeur et momentum | 200 | non |
| Open Source Asset Pricing | plusieurs centaines de caractéristiques documentées | dépôt accessible | variable |

Le cas de la SEC mérite une note. Le 2026-08-29, tout le domaine `sec.gov`
répondait 403 « Request Rate Threshold Exceeded » depuis cet environnement, y
compris `data.sec.gov`, sur sept relances en vingt minutes. Le 2026-09-01, les
trois points d'entrée testés répondent 200 avec le même en-tête. Le blocage
était donc un débit, pas une politique, et la conclusion pratique est de
respecter la limite de dix requêtes par seconde annoncée par la SEC plutôt que
de conclure à une indisponibilité.

## Ce que le lac ne peut pas donner

Les limites des sources gratuites sont réelles, connues et écrites :
[limites des données gratuites](free_data_limitations.md). Elles ne sont jamais
cachées derrière une approximation.
