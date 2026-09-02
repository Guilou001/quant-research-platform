"""Phase 8. Les modèles d'apprentissage transversal, du linéaire aux arbres.

Trois modules. :mod:`quantlab.models.panel` assemble le panneau (date, titre),
met les caractéristiques à l'échelle par leur rang transversal et construit
l'étiquette du mois suivant par un décalage explicite.
:mod:`quantlab.models.cross_sectional` enveloppe les estimateurs de
``scikit-learn`` derrière une spécification nommée et une analyse glissante qui
règle les hyperparamètres sur la fin de l'entraînement, jamais sur le test.
:mod:`quantlab.models.evaluation` porte le R² hors échantillon de Gu, Kelly et
Xiu (2020) et le test de Diebold et Mariano.

Chaque modèle ajusté satisfait :class:`quantlab.core.protocols.AlphaModel`.
``scikit-learn`` n'est importé qu'ici et dans :mod:`quantlab.portfolio`, ce
qu'un test d'architecture vérifie (ADR-013).
"""

from __future__ import annotations

from quantlab.models import cross_sectional, evaluation, panel

__all__ = ["cross_sectional", "evaluation", "panel"]
