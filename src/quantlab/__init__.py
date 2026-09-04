"""quantlab : laboratoire de recherche quantitative.

Le paquet est organisé par étape du raisonnement, et non par technologie :

- ``core``       les contrats, la configuration, le calendrier, le journal ;
- ``data``       le lac de données, la provenance, le point-in-time, la qualité ;
- ``analytics``  la mesure de la performance et du risque ;
- ``validation`` ce qui sépare un résultat d'une coïncidence ;
- ``features``, ``signals``, ``strategies``, ``models``   la recherche d'alpha ;
- ``portfolio``, ``risk``, ``execution``, ``backtest``    la mise en portefeuille ;
- ``reporting``, ``experiments``                          la trace et le rapport.

Chaque module documente le problème qu'il traite, l'intuition, la formule, ses
hypothèses, sa provenance académique, ses limites et la façon de vérifier que
l'implémentation est correcte.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("quantlab")
except PackageNotFoundError:  # pragma: no cover - exécution sans installation
    __version__ = "0.0.0"

#: L'adresse publique du dépôt, écrite une fois ; CITATION.cff et le rapport la reprennent.
REPOSITORY_URL = "https://github.com/Guilou001/quant-research-platform"

__all__ = ["REPOSITORY_URL", "__version__"]
