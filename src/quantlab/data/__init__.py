"""Le lac de données, sa provenance, son point-in-time et sa qualité.

Le sous-paquet répond à une seule question, et tout le reste en découle : quelle
donnée exacte a produit ce résultat ? Sans réponse, le résultat n'est pas
reproductible, quelle que soit la qualité du code qui l'a produit.

Quatre étages, quatre règles. ``raw`` conserve la réponse de la source octet
pour octet et ne se corrige jamais. ``bronze`` la rend lisible sans décider quoi
que ce soit. ``silver`` porte les décisions méthodologiques, chacune tracée.
``gold`` porte les jeux consommables, et un jeu sans manifeste ne s'y écrit pas.

Le sous-paquet ``point_in_time`` porte la seule règle non négociable du
laboratoire : un dépôt accepté le 15 mai n'est pas connaissable le 31 mars.
"""

from quantlab.data import lake, manifest, point_in_time, providers, quality

__all__ = [
    "lake",
    "manifest",
    "point_in_time",
    "providers",
    "quality",
]
