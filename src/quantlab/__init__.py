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

__version__ = "1.0.0"

__all__ = ["__version__"]
