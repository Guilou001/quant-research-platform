"""Les fournisseurs de données, tous derrière le même protocole.

Aucun module de stratégie n'importe ce sous-paquet. C'est ce qui rend
``YahooProvider`` remplaçable par un fournisseur professionnel sans réécrire une
ligne de recherche, et un test mécanique le vérifie
(``tests/unit/test_architecture.py``).

Chaque fournisseur écrit la réponse BRUTE dans ``data/raw/`` avant tout parsage,
calcule son empreinte, et rend un manifeste qui déclare honnêtement ce que la
source donne et ce qu'elle ne donne pas. Deux d'entre eux seulement sont
point-in-time, ``AlfredProvider`` et ``SecProvider``, et c'est ce qui les rend
utilisables pour un backtest fondamental ou macroéconomique.
"""

from quantlab.data.providers.base import (
    BaseProvider,
    HttpClient,
    ProviderError,
    RateLimitError,
    RawResponse,
    SourceUnavailableError,
)

__all__ = [
    "BaseProvider",
    "HttpClient",
    "ProviderError",
    "RateLimitError",
    "RawResponse",
    "SourceUnavailableError",
]
