"""Phase 4. Les caractéristiques, et la règle unique qui les gouverne toutes.

Une caractéristique datée ``t`` n'utilise que de l'information disponible à
``t`` inclus. Une moyenne mobile centrée est interdite, un ``shift`` négatif
aussi. La seule exception est l'ÉTIQUETTE, le rendement futur qu'un modèle
apprend à prévoir, et elle porte le préfixe ``label_`` pour se signaler.

La règle ne se surveille pas à la relecture : elle se vérifie. La fonction
:func:`quantlab.features.transforms.assert_causal` modifie les données après
une date, recalcule, et refuse toute caractéristique qui a bougé avant cette
date.

La normalisation TRANSVERSALE, celle qui compare les actifs entre eux à une
date donnée, ne vit pas ici mais dans :mod:`quantlab.signals`. La distinction
est celle du z-score : contre son propre passé dans ``features``, contre les
autres actifs dans ``signals``.
"""

from quantlab.features import transforms

__all__ = ["transforms"]
