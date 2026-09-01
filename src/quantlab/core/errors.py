"""Les erreurs du laboratoire, et ce que chacune signale.

Une erreur porte un nom parce qu'elle appelle une correction différente. Une
``LookAheadError`` n'est pas un bogue de calcul : c'est un résultat de recherche
qui vient d'être invalidé, et le pipeline doit s'arrêter net plutôt que produire
un chiffre qu'on croira.
"""

from __future__ import annotations


class QuantLabError(Exception):
    """Racine de toutes les erreurs du paquet.

    Attraper cette classe attrape tout ce que le laboratoire lève
    volontairement, et rien de ce que lève une bibliothèque tierce.
    """


class ConfigError(QuantLabError):
    """Une configuration est absente, mal formée ou incohérente.

    Levée avant tout calcul. Une expérience dont la configuration ne valide pas
    ne démarre pas : un paramètre par défaut silencieux est un paramètre que
    personne ne saura retrouver six mois plus tard.
    """


class DataQualityError(QuantLabError):
    """Une donnée viole un contrat déclaré.

    Exemples : un ``high`` inférieur à un ``low``, un horodatage en double, un
    rendement quotidien de +900 % sans division correspondante.
    """


class InsufficientDataError(QuantLabError):
    """Le calcul demandé exige plus d'observations que le jeu n'en porte.

    Levée plutôt que de rendre un ``NaN``. Un ``NaN`` se propage en silence et
    ressort en fin de chaîne sous la forme d'un ratio de Sharpe manquant, sans
    que personne sache où il est né.
    """


class LookAheadError(QuantLabError):
    """De l'information future a été demandée à une date passée.

    C'est l'erreur la plus grave du laboratoire, et la seule dont la règle est
    absolue. Un rapport financier accepté par la SEC le 15 mai 2015 n'est pas
    connaissable au 31 mars 2015, quelle que soit la période qu'il décrit. Le
    pipeline échoue immédiatement (*fail fast*) plutôt que de produire un
    backtest flatteur et faux.
    """


class NotReplicatedError(QuantLabError):
    """Une étude prétend répliquer un article sans avoir passé son contrôle.

    Le verdict d'une étude ne se déclare pas à la main : il se déduit des
    contrôles de réplication qui ont réellement tourné.
    """
