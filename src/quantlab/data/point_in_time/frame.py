"""Le registre point-in-time : ce qui était connaissable, à la date où l'on décidait.

**Le problème.** Un rapport trimestriel décrit le trimestre clos le 31 mars 2015,
mais la SEC ne le reçoit que le 15 mai 2015. Un portefeuille formé le 31 mars 2015
ne peut donc pas s'en servir. La quasi-totalité des bases comptables historiques
range pourtant ce chiffre sous la date du 31 mars, et une jointure naïve sur cette
date donne à la stratégie six semaines et demie d'avance sur le marché. L'alpha
qui en sort n'existe pas.

**Le remède.** Deux dates portées par chaque ligne, et jamais une seule.
``period_end`` dit quelle période économique le chiffre décrit. ``available_from``
dit à partir de quel instant ce chiffre était connaissable. Le module ne lit
jamais ``period_end`` pour décider ce qui est visible, et ne lit jamais autre
chose que ``available_from``.

Le schéma temporel
------------------

::

    2015-01-01           2015-03-31                      2015-05-15
        |                     |                              |
        |==== trimestre ======|                              |
        |  période économique |                              |
        |                     |<------- 45 jours ----------->|
        |                     |      d'ignorance             |
    ----+---------------------+------------------------------+-------> temps
                              ^                              ^
                        period_end                     available_from

    Décision du 2015-03-31 : le chiffre du trimestre est INCONNAISSABLE.
    Décision du 2015-05-15 : le chiffre devient connaissable, et pas avant.

La distance entre les deux dates n'est ni un détail ni une marge de prudence :
c'est la seule chose qui sépare une réplication d'un artefact.

Combien de jours, et pourquoi
-----------------------------

Le délai de dépôt est fixé par la SEC, pas par le chercheur. Valeurs RAPPORTÉES,
tirées des instructions générales des formulaires et de la règle finale 33-8644
de 2005, « Revisions to Accelerated Filer Definition and Accelerated Deadlines ».

Formulaire 10-Q, le rapport trimestriel. Quarante jours au plus après la clôture
pour un grand déposant accéléré comme pour un déposant accéléré. Quarante-cinq
jours pour un déposant non accéléré.

Formulaire 10-K, le rapport annuel. Soixante jours au plus pour un grand
déposant accéléré, soixante-quinze pour un déposant accéléré, quatre-vingt-dix
pour un déposant non accéléré.

Le décalage médian réellement observé sur les dépôts n'est pas mesuré par ce
module, et le laboratoire ne l'affirme donc pas. Deux choses sont sûres. Un
chiffre trimestriel arrive de l'ordre de quarante jours après la clôture, un
chiffre annuel davantage. Et la retenue de six mois de Fama et French (1992)
majore prudemment ce délai au lieu de le mesurer.

Pourquoi ignorer ce décalage fabrique de l'alpha
------------------------------------------------

Le mécanisme n'a rien de subtil. Un bénéfice publié le 15 mai est corrélé au
rendement de l'action entre le 31 mars et le 15 mai. Le marché apprend en effet
la nouvelle en cours de route, et le titre bouge le jour du dépôt. Attribuer ce
bénéfice au 31 mars revient donc à trier les titres, au 31 mars, sur une variable
qui contient déjà le rendement des six semaines suivantes. Le tri paraît alors
prédictif ; il est en réalité descriptif.

Banz et Breen ont mesuré cet effet les premiers sur Compustat. La prime
bénéfice/prix apparaît sur la base annotée après coup, et s'évanouit sur la base
reconstruite à la date de disponibilité. Voir « Sample-Dependent Results Using
Accounting and Market Data: Some Evidence », *Journal of Finance*, 41(4) (1986),
779-793.

Fama et French en tirent la convention encore employée trente ans plus tard. Les
comptes de l'exercice clos en année :math:`t-1` ne servent qu'aux rendements à
partir de juillet de l'année :math:`t`. Voir « The Cross-Section of Expected
Stock Returns », *Journal of Finance*, 47(2) (1992), 427-465.

Le second piège porte un autre nom, le *restatement*. Une même période est
souvent publiée deux fois, la seconde corrigeant la première. Une base qui ne
garde que la dernière version fait connaître au 15 mai 2015 un chiffre corrigé le
9 novembre 2015. La correction est ici traitée comme une ligne de plus, avec sa
propre disponibilité, et :meth:`PITFrame.as_of` rend la version en vigueur à la
date demandée, pas la meilleure version connue aujourd'hui.

Ce que le module garantit, et ce qu'il ne garantit pas
------------------------------------------------------

Il garantit qu'aucune ligne rendue par :meth:`PITFrame.as_of` ne porte une
disponibilité postérieure à la date demandée. Il garantit aussi, par la
validation du constructeur, qu'aucune ligne ne prétend être disponible avant la
fin de la période qu'elle décrit.

Il ne garantit pas que la date de disponibilité fournie soit la bonne. Une base
qui horodate mal ses dépôts produira un registre valide et faux. Le contrôle de
cette qualité-là appartient au fournisseur, et il se déclare.

Exemple d'emploi :

.. code-block:: python

    pit = PITFrame(fundamentals, entity_col="ticker")
    connu = pit.as_of("2015-03-31")          # vide : le 10-Q n'est pas déposé
    connu = pit.as_of("2015-05-15")          # une ligne : le dépôt du jour
    panel = pit.panel(dates_de_rebalancement)
    assert_no_lookahead(panel, "as_of_date")
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, LookAheadError
from quantlab.core.logging import get_logger

_logger = get_logger(__name__)

#: Nom imposé de la colonne qui porte la fin de la période économique décrite.
PERIOD_END_COLUMN: str = "period_end"
#: Nom imposé de la colonne qui porte l'instant à partir duquel la ligne est connaissable.
AVAILABLE_FROM_COLUMN: str = "available_from"
#: Nom de la colonne ajoutée par :meth:`PITFrame.panel`, qui porte la date de décision.
AS_OF_COLUMN: str = "as_of_date"
#: Nom par défaut de la clé d'entité, remplaçable à la construction.
DEFAULT_ENTITY_COLUMN: str = "entity_id"

#: Nombre de secondes dans une journée, pour convertir un écart en jours décimaux.
_SECONDS_PER_DAY: float = 86_400.0
#: Nombre de lignes fautives détaillées dans un message d'erreur.
_MAX_OFFENDERS_SHOWN: int = 5

KeepRule = Literal["last", "first", "all"]
JoinDirection = Literal["backward", "forward", "nearest"]
MomentLike = str | dt.date | dt.datetime | pd.Timestamp

#: Rang des résolutions temporelles de pandas, de la plus grossière à la plus fine.
_UNIT_RANK: dict[str, int] = {"s": 0, "ms": 1, "us": 2, "ns": 3}

#: Contenus de colonne refusés comme dates, tels que les nomme ``pandas.api.types.infer_dtype``.
#: Le dtype déclaré ne suffit pas : une colonne ``object`` remplie d'entiers annonce ``object``
#: et se lit pourtant en nanosecondes depuis 1970.
_NON_DATE_CONTENTS: frozenset[str] = frozenset(
    {"integer", "floating", "mixed-integer-float", "mixed-integer", "boolean", "decimal"}
)


def _to_datetime_column(values: pd.Series, column: str) -> pd.Series:
    """Rend la colonne convertie en dates, ou refuse d'aller plus loin.

    Args:
        values: la colonne telle qu'elle arrive.
        column: son nom, pour le message d'erreur.

    Returns:
        La même colonne, de type ``datetime64``.

    Raises:
        DataQualityError: si la colonne est numérique, si la conversion échoue,
            ou si elle porte une date manquante. Une colonne VIDE échappe à la
            règle du numérique : pandas type un tableau sans ligne en ``float64``,
            et refuser un registre vide n'apporterait rien.

    Note:
        Une colonne numérique est refusée plutôt que convertie. ``pd.to_datetime``
        lirait un entier comme un nombre de nanosecondes depuis 1970, ce qui
        placerait des dates de janvier 1970 sans rien signaler. Le portefeuille a
        déjà payé ce défaut au paquet ``gvf.marches``, où des horodatages lus dans
        la mauvaise unité appariaient les prix aux mauvaises minutes.

        Le contrôle porte sur le CONTENU de la colonne et non sur son dtype
        déclaré. Une colonne ``object`` remplie d'entiers annonce ``object``, passe
        donc à côté d'un contrôle de dtype, et se lit pourtant en nanosecondes.
        Mesuré : ``period_end = 20150331`` et ``available_from = 20150515`` en
        dtype ``object`` devenaient ``1970-01-01 00:00:00.020150331`` et
        ``1970-01-01 00:00:00.020150515``. L'ordre des deux dates étant préservé,
        le registre était accepté, et ``as_of("2015-03-31")`` rendait la ligne
        qu'elle doit refuser. La garantie du module tombait en silence.
    """
    if not pd.api.types.is_datetime64_any_dtype(values):
        if values.empty:
            return values.astype("datetime64[ns]")
        content = pd.api.types.infer_dtype(values, skipna=True)
        if content in _NON_DATE_CONTENTS:
            raise DataQualityError(
                f"la colonne « {column} » porte des nombres et non des dates (contenu lu : {content}) ; "
                "convertissez-la explicitement avant de construire le registre"
            )
        try:
            values = pd.to_datetime(values)
        except (ValueError, TypeError) as exc:
            raise DataQualityError(f"la colonne « {column} » n'est pas convertible en dates : {exc}") from exc
    if values.isna().any():
        n_missing = int(values.isna().sum())
        raise DataQualityError(
            f"la colonne « {column} » porte {n_missing} date(s) manquante(s) ; "
            "une comparaison contre NaT rend toujours False et masquerait une fuite"
        )
    return values


def _column_timezone(values: pd.Series) -> dt.tzinfo | None:
    """Rend le fuseau d'une colonne de dates, ou ``None`` si elle est naïve."""
    return getattr(values.dtype, "tz", None)


def _as_timestamp(value: MomentLike, tz: dt.tzinfo | None, argument: str) -> pd.Timestamp:
    """Rend l'instant demandé sous forme de ``Timestamp`` compatible avec la colonne.

    Args:
        value: la date de décision, chaîne, ``date``, ``datetime`` ou ``Timestamp``.
        tz: le fuseau de la colonne de disponibilité, ``None`` si elle est naïve.
        argument: le nom de l'argument, pour le message d'erreur.

    Returns:
        L'instant converti, avec le même caractère naïf ou localisé que la colonne.

    Raises:
        ConfigError: si la valeur n'est pas une date, ou si son fuseau ne
            correspond pas à celui de la colonne de disponibilité.
    """
    try:
        moment = pd.Timestamp(value)
    except (ValueError, TypeError) as exc:
        raise ConfigError(f"{argument} vaut {value!r}, qui n'est pas une date lisible") from exc
    if moment is pd.NaT:
        raise ConfigError(f"{argument} vaut NaT ; une date de décision manquante n'a pas de sens")
    if tz is None and moment.tz is not None:
        raise ConfigError(
            f"{argument} porte un fuseau alors que la colonne « {AVAILABLE_FROM_COLUMN} » est naïve ; "
            "alignez les deux plutôt que de laisser pandas trancher"
        )
    if tz is not None and moment.tz is None:
        raise ConfigError(
            f"{argument} est naïf alors que la colonne « {AVAILABLE_FROM_COLUMN} » porte le fuseau {tz} ; "
            "localisez la date de décision"
        )
    return moment


def _gap_in_days(later: pd.Series, earlier: pd.Series) -> pd.Series:
    """Rend l'écart ``later - earlier`` en jours décimaux, positif quand ``later`` suit."""
    return (later - earlier).dt.total_seconds() / _SECONDS_PER_DAY


@dataclass(frozen=True, slots=True)
class LookAheadReport:
    """Le compte rendu d'un contrôle anti-fuite, chiffré et lisible.

    Attributes:
        n_rows: nombre de lignes contrôlées.
        n_violations: nombre de lignes dont la disponibilité dépasse la date de
            décision au-delà de la tolérance.
        entities: les entités concernées, triées, sans doublon.
        max_gap_days: le pire écart, en jours, entre la disponibilité et la date
            de décision. Vaut 0,0 quand aucune ligne ne viole la règle.
        tolerance_days: la tolérance appliquée, en jours.
        sample: jusqu'à cinq lignes fautives décrites en clair.

    Example:
        >>> report = LookAheadReport(10, 0, (), 0.0, 0.0, ())
        >>> report.clean
        True
    """

    n_rows: int
    n_violations: int
    entities: tuple[str, ...]
    max_gap_days: float
    tolerance_days: float
    sample: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        """Vrai quand aucune ligne ne viole la règle."""
        return self.n_violations == 0

    def describe(self) -> str:
        """Rend une phrase qui dit ce qui a été contrôlé et ce qui a été trouvé."""
        if self.clean:
            return (
                f"{self.n_rows} ligne(s) contrôlée(s), aucune fuite, "
                f"tolérance {self.tolerance_days:g} jour(s)"
            )
        head = (
            f"{self.n_violations} fuite(s) sur {self.n_rows} ligne(s) contrôlée(s), "
            f"écart maximal {self.max_gap_days:.2f} jour(s), tolérance {self.tolerance_days:g} jour(s), "
            f"entités : {', '.join(self.entities)}"
        )
        if not self.sample:
            return head
        return head + " | " + " ; ".join(self.sample)


@dataclass(frozen=True, eq=False, slots=True)
class PITFrame:
    """Un tableau dont chaque ligne dit ce qu'elle décrit et quand elle est devenue connaissable.

    **Le problème.** Un tableau comptable ordinaire porte une seule date, celle de
    la période. Interrogé à une date de décision, il rend des chiffres que
    personne ne pouvait connaître ce jour-là.

    **L'intuition.** Séparer les deux dates, puis ne filtrer que sur la seconde.
    La période sert à identifier l'observation, la disponibilité seule sert à
    décider si on a le droit de la lire.

    La règle du filtre s'écrit, pour une entité :math:`i`, une période :math:`p` et
    une date de décision :math:`d` :

    .. math::

        \\mathcal{V}_{i,p}(d) = \\{\\, k : e_k = i,\\; p_k = p,\\; a_k \\le d \\,\\}
        \\qquad
        \\hat{x}_{i,p}(d) = x_{k^\\star}, \\quad
        k^\\star = \\arg\\max_{k \\in \\mathcal{V}_{i,p}(d)} a_k

    où :math:`e_k` est l'entité de la ligne :math:`k`, :math:`p_k` sa fin de
    période ``period_end``, :math:`a_k` sa disponibilité ``available_from``,
    :math:`x_k` ses valeurs, et :math:`d` la date de décision. L'ensemble
    :math:`\\mathcal{V}_{i,p}(d)` est vide tant qu'aucune version n'est déposée,
    et :meth:`as_of` ne rend alors aucune ligne pour ce couple.

    **Les hypothèses.** Trois, et elles sont vérifiées à la construction. La
    disponibilité n'est jamais antérieure à la fin de période, sans quoi le
    registre décrit un impossible. Aucune des deux dates n'est manquante, une
    comparaison contre NaT rendant silencieusement ``False``. La clé d'entité est
    présente et non manquante.

    **La provenance.** La séparation période/disponibilité répond au biais
    mesuré par Banz et Breen (1986) sur Compustat. La convention de retenue de
    Fama et French (1992) en est la version prudente, à délai fixe. Ce registre
    remplace le délai fixe par la date réelle quand elle existe.

    **Les limites.** Le registre ne connaît que ce que la source horodate. Une
    base qui ne fournit aucune date de dépôt exige un délai posé à la main, et ce
    délai est alors une hypothèse, pas une mesure. Le module n'invente aucune
    date : il refuse.

    Seconde limite, mesurée. La classe est déclarée ``frozen``, mais l'attribut
    ``data`` reste un ``DataFrame`` modifiable. Le constructeur en prend une
    copie, si bien que modifier le tableau d'origine ne change rien. Modifier
    ``pit.data`` lui-même casse en revanche les invariants sans que rien ne le
    signale. Le tableau se lit, il ne se modifie pas.

    **Les alternatives.** Le décalage forfaitaire, de trois ou six mois, est plus
    simple mais paie deux fois. Il retarde l'information des sociétés promptes.
    Et il ne rattrape pas les sociétés en retard, dont le dépôt arrive parfois
    après le délai forfaitaire. La sélection sur la dernière version connue est
    plus simple encore, et fausse.

    **Pourquoi ce choix ici.** Le laboratoire réplique des articles dont le
    verdict tient à quelques dizaines de points de base par an. Un décalage de six
    semaines suffit à retourner un tel verdict, donc la date réelle est retenue
    partout où la source la donne.

    **Comment vérifier.** Trois contrôles, tous dans ``tests/unit/test_point_in_time.py``.
    Le cas canonique du 10-Q déposé le 15 mai refuse l'accès au 31 mars. Une
    correction publiée en novembre laisse la version de mai en vigueur jusqu'au
    jour de la correction. Et une propriété ``hypothesis`` vérifie que toute ligne
    rendue par :meth:`as_of` porte une disponibilité antérieure ou égale à la date
    demandée, pour toute date et tout registre.

    Args:
        data: le tableau source, portant au minimum ``period_end``,
            ``available_from`` et la colonne d'entité.
        entity_col: le nom de la clé d'entité. Vaut ``« entity_id »`` par défaut.

    Raises:
        DataQualityError: colonne absente, colonne en double, date illisible ou
            manquante, entité manquante.
        LookAheadError: au moins une ligne prétend être disponible avant la fin de
            la période qu'elle décrit.

    Example:
        >>> import pandas as pd
        >>> data = pd.DataFrame(
        ...     {
        ...         "entity_id": ["AAA"],
        ...         "period_end": ["2015-03-31"],
        ...         "available_from": ["2015-05-15"],
        ...         "eps": [1.10],
        ...     }
        ... )
        >>> pit = PITFrame(data)
        >>> len(pit.as_of("2015-03-31"))
        0
        >>> float(pit.as_of("2015-05-15")["eps"].iloc[0])
        1.1
    """

    data: pd.DataFrame
    entity_col: str = DEFAULT_ENTITY_COLUMN

    def __post_init__(self) -> None:
        """Valide le contrat, normalise les dates, ordonne les lignes."""
        if not isinstance(self.data, pd.DataFrame):
            raise DataQualityError(f"data doit être un DataFrame pandas, reçu {type(self.data).__name__}")

        frame = self.data.copy()
        required = (self.entity_col, PERIOD_END_COLUMN, AVAILABLE_FROM_COLUMN)
        missing = [name for name in required if name not in frame.columns]
        if missing:
            raise DataQualityError(
                f"colonnes absentes du registre : {missing}. "
                f"Un registre point-in-time porte obligatoirement « {PERIOD_END_COLUMN} », "
                f"« {AVAILABLE_FROM_COLUMN} » et sa clé d'entité"
            )
        if frame.columns.has_duplicates:
            duplicated = sorted(set(frame.columns[frame.columns.duplicated()]))
            raise DataQualityError(f"colonnes en double dans le registre : {duplicated}")

        frame[PERIOD_END_COLUMN] = _to_datetime_column(frame[PERIOD_END_COLUMN], PERIOD_END_COLUMN)
        frame[AVAILABLE_FROM_COLUMN] = _to_datetime_column(
            frame[AVAILABLE_FROM_COLUMN], AVAILABLE_FROM_COLUMN
        )
        if _column_timezone(frame[PERIOD_END_COLUMN]) != _column_timezone(frame[AVAILABLE_FROM_COLUMN]):
            raise DataQualityError(
                f"« {PERIOD_END_COLUMN} » et « {AVAILABLE_FROM_COLUMN} » n'ont pas le même fuseau ; "
                "leur comparaison serait refusée par pandas ou fausse selon la version"
            )
        if frame[self.entity_col].isna().any():
            n_missing = int(frame[self.entity_col].isna().sum())
            raise DataQualityError(
                f"la clé d'entité « {self.entity_col} » porte {n_missing} valeur(s) manquante(s)"
            )

        _validate_availability(frame, self.entity_col)

        frame = frame.sort_values([self.entity_col, PERIOD_END_COLUMN, AVAILABLE_FROM_COLUMN], kind="stable")
        object.__setattr__(self, "data", frame)
        _logger.debug(
            "registre point-in-time construit",
            extra={"n_rows": len(frame), "entity_col": self.entity_col},
        )

    def __len__(self) -> int:
        """Rend le nombre de lignes du registre, versions successives comprises."""
        return len(self.data)

    @property
    def entities(self) -> tuple[object, ...]:
        """Rend les entités présentes, triées, sans doublon."""
        return tuple(sorted(pd.unique(self.data[self.entity_col]).tolist()))

    @property
    def value_columns(self) -> tuple[str, ...]:
        """Rend les colonnes de valeurs, c'est-à-dire tout ce qui n'est pas une clé."""
        keys = {self.entity_col, PERIOD_END_COLUMN, AVAILABLE_FROM_COLUMN}
        return tuple(name for name in self.data.columns if name not in keys)

    def as_of(self, date: MomentLike, keep: KeepRule = "last") -> pd.DataFrame:
        """Rend l'état du registre connaissable à ``date``, et rien d'autre.

        Pour chaque entité et chaque ``period_end``, la ligne rendue est la
        dernière observation dont ``available_from`` est antérieure ou égale à
        ``date``. Une période dont aucune version n'est encore déposée n'apparaît
        pas ; une période corrigée apparaît dans la version en vigueur ce jour-là.

        Args:
            date: la date de décision. Chaîne, ``date``, ``datetime`` ou ``Timestamp``.
            keep: ``« last »`` pour la version en vigueur, ``« first »`` pour la
                publication d'origine, ``« all »`` pour toutes les versions déjà
                connaissables. Vaut ``« last »`` par défaut, qui est la seule règle
                correcte pour former un portefeuille.

        Returns:
            Un tableau aux mêmes colonnes que le registre, ordonné par entité puis
            par période. Vide, et non nul, quand rien n'est encore connaissable.

        Raises:
            ConfigError: date illisible, ou ``keep`` inconnu.

        Note:
            À égalité de ``available_from``, l'ordre d'arrivée des lignes dans le
            tableau source tranche : ``« last »`` rend la dernière des ex aequo.
            Le tri interne est stable, cette règle est donc reproductible.

            La comparaison est LARGE, :math:`a_k \\le d`. Une ligne devient donc
            lisible à l'instant exact de sa disponibilité. Sur des dates tronquées
            au jour, cela vaut minuit, et une stratégie qui décide à l'ouverture
            lit un dépôt arrivé le soir même, soit jusqu'à une journée d'avance.
            Le module ne corrige pas cela, faute de savoir à quelle heure la
            décision est prise. Deux remèdes existent, et ils appartiennent à
            l'appelant. Interroger la veille, ``as_of(d - 1 jour)``, ou porter
            l'heure réelle du dépôt dans ``available_from``, ce que la SEC publie.

        Example:
            >>> import pandas as pd
            >>> data = pd.DataFrame(
            ...     {
            ...         "entity_id": ["AAA", "AAA"],
            ...         "period_end": ["2015-03-31", "2015-03-31"],
            ...         "available_from": ["2015-05-15", "2015-11-09"],
            ...         "eps": [1.10, 0.85],
            ...     }
            ... )
            >>> pit = PITFrame(data)
            >>> float(pit.as_of("2015-08-01")["eps"].iloc[0])
            1.1
            >>> float(pit.as_of("2015-11-09")["eps"].iloc[0])
            0.85
        """
        if keep not in ("last", "first", "all"):
            raise ConfigError(f"keep vaut {keep!r}, attendu « last », « first » ou « all »")
        moment = _as_timestamp(date, _column_timezone(self.data[AVAILABLE_FROM_COLUMN]), "date")
        visible = self.data[self.data[AVAILABLE_FROM_COLUMN] <= moment]
        if keep == "all" or visible.empty:
            return visible.copy()
        return visible.drop_duplicates(subset=[self.entity_col, PERIOD_END_COLUMN], keep=keep).copy()

    def latest_as_of(self, date: MomentLike) -> pd.DataFrame:
        """Rend une seule ligne par entité, celle de la période la plus récente connaissable.

        C'est l'état que lit un modèle qui n'a besoin que du dernier trimestre
        publié, sans historique. La sélection se fait en deux temps : d'abord la
        version en vigueur de chaque période, ensuite la période la plus récente
        de chaque entité.

        Args:
            date: la date de décision.

        Returns:
            Un tableau d'au plus une ligne par entité, ordonné par entité. Vide
            quand aucune entité n'a encore publié.

        Raises:
            ConfigError: date illisible.

        Note:
            La période la plus récente n'est pas forcément la dernière publiée.
            Une société qui dépose son trimestre en retard peut voir son
            trimestre suivant devenir connaissable le même jour, et c'est bien le
            trimestre le plus récent qui est rendu.
        """
        visible = self.as_of(date, keep="last")
        if visible.empty:
            return visible
        return visible.drop_duplicates(subset=[self.entity_col], keep="last").copy()

    def panel(
        self,
        dates: Iterable[MomentLike],
        keep: KeepRule = "last",
        as_of_col: str = AS_OF_COLUMN,
    ) -> pd.DataFrame:
        """Empile les états connaissables sur une suite de dates de rééquilibrage.

        Le tableau obtenu est un panneau de caractéristiques sans fuite par
        construction : chaque ligne porte la date de décision qui l'a fait
        apparaître, et cette date est postérieure ou égale à sa disponibilité.

        Args:
            dates: les dates de décision, en général les dates de rééquilibrage.
                Elles sont triées par ordre croissant, et les doublons sont refusés.
            keep: la règle de sélection passée à :meth:`as_of`.
            as_of_col: le nom de la colonne ajoutée, placée en première position.

        Returns:
            Un tableau dont l'index est réinitialisé, la colonne ``as_of_col``
            en tête, puis les colonnes du registre.

        Raises:
            ConfigError: date illisible, date répétée, ou collision entre
                ``as_of_col`` et une colonne existante.

        Example:
            >>> import pandas as pd
            >>> data = pd.DataFrame(
            ...     {
            ...         "entity_id": ["AAA"],
            ...         "period_end": ["2015-03-31"],
            ...         "available_from": ["2015-05-15"],
            ...         "eps": [1.10],
            ...     }
            ... )
            >>> panel = PITFrame(data).panel(["2015-04-30", "2015-05-31"])
            >>> len(panel)
            1
        """
        if as_of_col in self.data.columns:
            raise ConfigError(
                f"as_of_col vaut {as_of_col!r}, qui est déjà une colonne du registre ; "
                "choisissez un autre nom"
            )
        tz = _column_timezone(self.data[AVAILABLE_FROM_COLUMN])
        moments = [_as_timestamp(value, tz, "dates") for value in dates]
        if len(set(moments)) != len(moments):
            raise ConfigError(
                "dates porte au moins une date répétée, ce qui dupliquerait des lignes du panneau"
            )
        moments.sort()

        blocks: list[pd.DataFrame] = []
        for moment in moments:
            block = self.as_of(moment, keep=keep)
            stamp = pd.Series(moment, index=block.index, dtype=self.data[AVAILABLE_FROM_COLUMN].dtype)
            block.insert(0, as_of_col, stamp)
            blocks.append(block)
        if not blocks:
            empty = self.data.iloc[0:0].copy()
            empty.insert(0, as_of_col, pd.Series([], dtype=self.data[AVAILABLE_FROM_COLUMN].dtype))
            return empty
        return pd.concat(blocks, axis=0, ignore_index=True)


def _validate_availability(frame: pd.DataFrame, entity_col: str) -> None:
    """Refuse un registre dont une ligne serait disponible avant la fin de sa période.

    Args:
        frame: le registre, dates déjà converties.
        entity_col: le nom de la clé d'entité, pour nommer les lignes fautives.

    Raises:
        LookAheadError: au moins une ligne porte ``available_from < period_end``.

    Note:
        Ce contrôle n'est pas une coquetterie de typage. Une base qui range la
        date de dépôt dans la colonne de période, et réciproquement, produit
        exactement cette signature, et le registre entier serait inversé sans que
        rien d'autre ne le signale.
    """
    offending = frame[frame[AVAILABLE_FROM_COLUMN] < frame[PERIOD_END_COLUMN]]
    if offending.empty:
        return
    gaps = _gap_in_days(offending[PERIOD_END_COLUMN], offending[AVAILABLE_FROM_COLUMN])
    lines = [
        f"[{index}] {entity} : {PERIOD_END_COLUMN}={period:%Y-%m-%d}, "
        f"{AVAILABLE_FROM_COLUMN}={available:%Y-%m-%d}, soit {gap:.2f} jour(s) trop tôt"
        for index, entity, period, available, gap in zip(
            offending.index[:_MAX_OFFENDERS_SHOWN],
            offending[entity_col].iloc[:_MAX_OFFENDERS_SHOWN],
            offending[PERIOD_END_COLUMN].iloc[:_MAX_OFFENDERS_SHOWN],
            offending[AVAILABLE_FROM_COLUMN].iloc[:_MAX_OFFENDERS_SHOWN],
            gaps.iloc[:_MAX_OFFENDERS_SHOWN],
            strict=False,
        )
    ]
    raise LookAheadError(
        f"{len(offending)} ligne(s) sur {len(frame)} sont disponibles avant la fin de la période "
        f"qu'elles décrivent, ce qui est impossible. Écart maximal {gaps.max():.2f} jour(s). "
        + " ; ".join(lines)
    )


def _resolve_decision_dates(
    frame: pd.DataFrame,
    decision_dates: str | MomentLike | Sequence[MomentLike] | pd.Series,
    tz: dt.tzinfo | None,
) -> pd.Series:
    """Rend, ligne à ligne, la date de décision à opposer à la disponibilité.

    Args:
        frame: le tableau contrôlé.
        decision_dates: un nom de colonne du tableau, une date unique diffusée à
            toutes les lignes, une ``Series`` alignée sur l'index, ou une suite de
            la longueur du tableau.
        tz: le fuseau de la colonne de disponibilité.

    Returns:
        Une ``Series`` de dates, indexée comme ``frame``.

    Raises:
        ConfigError: forme non reconnue, longueur discordante, ou index incompatible.

    Note:
        Une chaîne est d'abord cherchée parmi les colonnes du tableau, et lue
        comme une date seulement si elle n'en est pas une. La règle est explicite
        pour qu'un nom de colonne ressemblant à une date ne bascule pas en silence.
    """
    if isinstance(decision_dates, str) and decision_dates in frame.columns:
        return _to_datetime_column(frame[decision_dates], decision_dates)
    if isinstance(decision_dates, pd.Series):
        if not decision_dates.index.equals(frame.index):
            raise ConfigError(
                "decision_dates est une Series dont l'index ne coïncide pas avec celui du tableau"
            )
        return _to_datetime_column(decision_dates, "decision_dates")
    if isinstance(decision_dates, str | dt.date | dt.datetime | pd.Timestamp):
        moment = _as_timestamp(decision_dates, tz, "decision_dates")
        return pd.Series(moment, index=frame.index)
    if isinstance(decision_dates, Sequence) or hasattr(decision_dates, "__len__"):
        values = list(decision_dates)
        if len(values) != len(frame):
            raise ConfigError(
                f"decision_dates porte {len(values)} date(s) pour {len(frame)} ligne(s). "
                f"Pour un panneau, passez le nom de la colonne de décision, par exemple « {AS_OF_COLUMN} »"
            )
        return _to_datetime_column(pd.Series(values, index=frame.index), "decision_dates")
    raise ConfigError(
        f"decision_dates vaut {decision_dates!r}, attendu un nom de colonne, une date, "
        "une Series alignée ou une suite de la longueur du tableau"
    )


def lookahead_report(
    frame: PITFrame | pd.DataFrame,
    decision_dates: str | MomentLike | Sequence[MomentLike] | pd.Series,
    tolerance_days: float = 0,
    entity_col: str = DEFAULT_ENTITY_COLUMN,
) -> LookAheadReport:
    """Rend le compte rendu du contrôle anti-fuite, sans lever d'erreur.

    Une ligne viole la règle quand sa disponibilité dépasse sa date de décision de
    plus de ``tolerance_days`` jours :

    .. math::

        \\text{fuite}_k \\iff a_k - d_k > \\tau

    où :math:`a_k` est ``available_from``, :math:`d_k` la date de décision de la
    ligne, et :math:`\\tau` la tolérance en jours. La tolérance vaut zéro par
    défaut, et une tolérance strictement positive doit se justifier : elle autorise
    délibérément une avance sur le marché.

    **Les hypothèses.** Les deux dates décrivent le même axe du temps, toutes deux
    naïves ou toutes deux localisées. L'appariement est ligne à ligne, sans
    agrégation ni jointure implicite.

    **La provenance.** Le contrôle formalise le diagnostic de Banz et Breen (1986),
    qui attribuent la prime bénéfice/prix de Compustat à un décalage de dates.
    L'écart :math:`a_k - d_k` est la quantité qu'ils mesurent en jours.

    **Les alternatives.** Le contrôle visuel d'un graphique de rendements cumulés
    voit un alpha trop régulier, mais après coup et sans le chiffrer. Le décalage
    forfaitaire des variables prévient la fuite sans la détecter, donc il ne dit
    jamais si une base est propre.

    **Pourquoi ce choix ici.** Un chiffre, en jours, se compare d'une étude à
    l'autre et se met dans un rapport. Un booléen ne le permet pas.

    **Les limites.** La fonction juge des dates fournies, pas de leur exactitude.
    Un registre dont toutes les disponibilités sont fausses passe le contrôle.

    **Comment vérifier.** Une décision au 31 mars 2015 contre un dépôt du
    15 mai 2015 doit rendre 45 jours. L'addition se fait à la main, 30 jours
    d'avril plus 15 jours de mai. Le test correspondant le vérifie.

    Args:
        frame: un :class:`PITFrame` ou un tableau portant ``available_from``.
        decision_dates: nom de colonne, date unique, ``Series`` alignée, ou suite
            de la longueur du tableau.
        tolerance_days: la marge tolérée, en jours. Doit être positive ou nulle.
        entity_col: la clé d'entité, ignorée quand ``frame`` est un
            :class:`PITFrame`, qui porte déjà la sienne.

    Returns:
        Le :class:`LookAheadReport` du contrôle.

    Raises:
        ConfigError: tolérance négative, ou ``decision_dates`` de forme invalide.
        DataQualityError: colonne de disponibilité absente, ou l'une des deux
            colonnes de temps naïve quand l'autre est localisée.

    Note:
        Deux fuseaux différents mais tous deux explicites sont acceptés, et
        comparés sur l'instant absolu. C'est ce que fait déjà
        :meth:`PITFrame.as_of`, et les deux entrées doivent rendre le même
        verdict sur le même registre. Seul le mélange naïf et localisé est
        refusé, parce que lui seul exigerait de supposer un fuseau.

    Example:
        >>> import pandas as pd
        >>> data = pd.DataFrame(
        ...     {
        ...         "entity_id": ["AAA"],
        ...         "period_end": ["2015-03-31"],
        ...         "available_from": ["2015-05-15"],
        ...     }
        ... )
        >>> report = lookahead_report(PITFrame(data), "2015-03-31")
        >>> report.n_violations, round(report.max_gap_days)
        (1, 45)
    """
    if tolerance_days < 0:
        raise ConfigError(f"tolerance_days vaut {tolerance_days}, il doit être positif ou nul")
    if isinstance(frame, PITFrame):
        table, key = frame.data, frame.entity_col
    else:
        table, key = frame, entity_col
    if AVAILABLE_FROM_COLUMN not in table.columns:
        raise DataQualityError(f"le tableau contrôlé ne porte pas de colonne « {AVAILABLE_FROM_COLUMN} »")

    available = _to_datetime_column(table[AVAILABLE_FROM_COLUMN], AVAILABLE_FROM_COLUMN)
    decisions = _resolve_decision_dates(table, decision_dates, _column_timezone(available))
    if (_column_timezone(available) is None) != (_column_timezone(decisions) is None):
        raise DataQualityError(
            "l'une des deux colonnes est naïve et l'autre localisée ; leur comparaison exigerait "
            "un fuseau supposé, et ce module ne suppose rien. Alignez-les avant le contrôle"
        )

    gaps = _gap_in_days(available, decisions)
    breached = gaps > tolerance_days
    n_violations = int(breached.sum())
    if n_violations == 0:
        return LookAheadReport(len(table), 0, (), 0.0, float(tolerance_days), ())

    offending = table[breached]
    offending_gaps = gaps[breached]
    entities: tuple[str, ...] = ()
    if key in table.columns:
        entities = tuple(sorted({str(value) for value in offending[key]}))
    sample = tuple(
        f"[{index}] {AVAILABLE_FROM_COLUMN}={a:%Y-%m-%d} > décision={d:%Y-%m-%d}, écart {gap:.2f} jour(s)"
        for index, a, d, gap in zip(
            offending.index[:_MAX_OFFENDERS_SHOWN],
            available[breached].iloc[:_MAX_OFFENDERS_SHOWN],
            decisions[breached].iloc[:_MAX_OFFENDERS_SHOWN],
            offending_gaps.iloc[:_MAX_OFFENDERS_SHOWN],
            strict=False,
        )
    )
    return LookAheadReport(
        n_rows=len(table),
        n_violations=n_violations,
        entities=entities,
        max_gap_days=float(offending_gaps.max()),
        tolerance_days=float(tolerance_days),
        sample=sample,
    )


def assert_no_lookahead(
    frame: PITFrame | pd.DataFrame,
    decision_dates: str | MomentLike | Sequence[MomentLike] | pd.Series,
    tolerance_days: float = 0,
    entity_col: str = DEFAULT_ENTITY_COLUMN,
) -> LookAheadReport:
    """Échoue si une ligne du tableau était inconnaissable à sa date de décision.

    C'est la fonction que les contrôles anti-biais du laboratoire appellent, et
    elle s'arrête net : une fuite n'est pas un avertissement, c'est un résultat de
    recherche invalidé.

    Args:
        frame: un :class:`PITFrame` ou un tableau portant ``available_from``.
        decision_dates: nom de colonne, date unique, ``Series`` alignée, ou suite
            de la longueur du tableau.
        tolerance_days: la marge tolérée, en jours, nulle par défaut.
        entity_col: la clé d'entité, pour nommer les entités fautives.

    Returns:
        Le :class:`LookAheadReport` du contrôle, propre par construction puisque
        le cas contraire lève.

    Raises:
        LookAheadError: au moins une ligne viole la règle.
        ConfigError: tolérance négative, ou ``decision_dates`` de forme invalide.
        DataQualityError: colonne de disponibilité absente.

    Example:
        >>> import pandas as pd
        >>> data = pd.DataFrame(
        ...     {
        ...         "entity_id": ["AAA"],
        ...         "period_end": ["2015-03-31"],
        ...         "available_from": ["2015-05-15"],
        ...     }
        ... )
        >>> assert_no_lookahead(PITFrame(data), "2015-06-30").clean
        True
    """
    report = lookahead_report(frame, decision_dates, tolerance_days, entity_col)
    if not report.clean:
        raise LookAheadError(report.describe())
    return report


def _check_time_column(frame: pd.DataFrame, column: str, side: str) -> pd.Series:
    """Rend la colonne de temps validée : présente, datée, sans trou, et triée.

    Args:
        frame: le tableau à joindre.
        column: le nom de la colonne de temps.
        side: ``« left »`` ou ``« right »``, pour le message d'erreur.

    Returns:
        La colonne, de type ``datetime64``.

    Raises:
        DataQualityError: colonne absente, non datée, porteuse d'une date
            manquante, ou non triée par ordre croissant.
    """
    if column not in frame.columns:
        raise DataQualityError(f"colonne de temps « {column} » absente du tableau {side}")
    values = frame[column]
    if not pd.api.types.is_datetime64_any_dtype(values):
        raise DataQualityError(
            f"la colonne de temps « {column} » du tableau {side} est de type {values.dtype}, "
            "une jointure temporelle exige des dates"
        )
    if values.isna().any():
        raise DataQualityError(
            f"la colonne de temps « {column} » du tableau {side} porte des dates manquantes"
        )
    if not values.is_monotonic_increasing:
        raise DataQualityError(
            f"le tableau {side} n'est pas trié par « {column} » ; "
            "pandas.merge_asof exige un tri croissant global, y compris avec une clé de groupe"
        )
    return values


def _align_resolution(left: pd.Series, right: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Rend les deux colonnes de temps ramenées à la plus fine des deux résolutions.

    Note:
        ``merge_asof`` refuse deux clés de résolutions différentes. Aligner sur la
        plus fine ne perd aucune information, alors qu'aligner sur la plus
        grossière tronquerait des horodatages.
    """
    left_unit = left.dt.unit
    right_unit = right.dt.unit
    if left_unit == right_unit:
        return left, right
    finest = left_unit if _UNIT_RANK[left_unit] >= _UNIT_RANK[right_unit] else right_unit
    return left.dt.as_unit(finest), right.dt.as_unit(finest)


def asof_join(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: str | Sequence[str],
    left_time: str,
    right_time: str,
    direction: JoinDirection = "backward",
    allow_exact_matches: bool = True,
    allow_lookahead: bool = False,
    tolerance: pd.Timedelta | None = None,
    suffixes: tuple[str, str] = ("_x", "_y"),
) -> pd.DataFrame:
    """Joint chaque décision à la dernière information connaissable, et refuse le reste.

    **Le problème.** ``pandas.merge_asof`` fait exactement le bon calcul et
    n'oppose aucune garde. Un tableau mal trié rend un résultat faux, parfois
    sans lever d'erreur. Une colonne de temps typée en texte compare des chaînes.
    Et ``direction="forward"`` apparie chaque décision à l'information SUIVANTE,
    ce qui est la fuite parfaite.

    **L'intuition.** Envelopper l'appel et refuser d'exécuter tant que les
    conditions de correction ne sont pas vérifiées. La direction rétrograde apparie
    la décision :math:`d` à l'observation :math:`a^\\star` telle que

    .. math::

        a^\\star = \\max \\{\\, a_k : g_k = g,\\; a_k \\le d \\,\\}

    où :math:`g` est la clé de groupe passée par ``on``, :math:`a_k` l'horodatage
    des lignes de droite, et :math:`d` celui de la ligne de gauche. Avec
    ``allow_exact_matches=False``, la comparaison devient stricte, :math:`a_k < d`.

    **Les hypothèses.** Les deux colonnes de temps sont datées, sans trou, et
    triées globalement par ordre croissant. La clé de groupe existe des deux côtés
    et s'apparie à l'identique.

    **La provenance.** L'appariement rétrograde est la jointure temporelle usuelle
    des bases de marché, et la convention de retenue de Fama et French (1992) en
    est le cas particulier à délai fixe.

    **Les alternatives.** Une jointure exacte sur la période est plus simple et
    fabrique le biais que ce module combat. Une jointure exacte sur la
    disponibilité perd toute décision qui ne tombe pas un jour de dépôt.

    **Pourquoi ce choix ici.** Une décision se prend à une date quelconque, alors
    qu'un dépôt arrive à des dates irrégulières. Seul l'appariement rétrograde
    relie les deux sans rien inventer.

    **Les limites.** Sans ``tolerance``, une décision de 2025 s'apparie à un dépôt
    de 2015 sans réserve. La garde en amont n'existe pas, elle appartient à
    l'appelant.

    **Comment vérifier.** La décision du 30 juin 2015 doit recevoir le dépôt du
    15 mai, et non celui du 14 août qui lui est postérieur. La décision du
    30 septembre doit recevoir celui du 14 août. Le test correspondant le vérifie.

    Args:
        left: les décisions, par exemple les dates de rééquilibrage par titre.
        right: l'information, par exemple les dépôts réglementaires par titre.
        on: la clé de groupe, appariée à l'identique dans les deux tableaux. Une
            chaîne ou une suite de chaînes. C'est le ``by`` de ``merge_asof``.
        left_time: la colonne de temps du tableau de gauche.
        right_time: la colonne de temps du tableau de droite.
        direction: ``« backward »`` par défaut, la seule sûre. ``« forward »`` et
            ``« nearest »`` lisent l'avenir et exigent ``allow_lookahead=True``.
        allow_exact_matches: autorise l'appariement à horodatage égal. Vrai par
            défaut. À passer à ``False`` quand les deux dates sont tronquées au
            jour et que l'information n'arrive pas avant la clôture.
        allow_lookahead: aveu explicite qu'une direction non rétrograde est voulue.
        tolerance: écart maximal accepté entre les deux horodatages. ``None``
            n'impose aucune limite, une information vieille de dix ans étant alors
            appariée sans réserve.
        suffixes: suffixes appliqués aux colonnes homonymes.

    Returns:
        Le tableau de gauche, augmenté des colonnes de droite. La colonne
        ``right_time`` est conservée, si bien qu'un contrôle ultérieur retrouve
        quelle observation a servi.

    Raises:
        LookAheadError: ``direction`` lit l'avenir sans ``allow_lookahead=True``.
        ConfigError: direction inconnue.
        DataQualityError: colonne absente, colonne de temps non datée, date
            manquante, ou tableau non trié.

    Note:
        Le tri exigé porte sur la colonne de temps seule, globalement, et non par
        groupe. C'est la règle de ``merge_asof``, elle surprend et elle est
        vérifiée ici plutôt que subie.

    Example:
        >>> import pandas as pd
        >>> decisions = pd.DataFrame({"ticker": ["AAA"], "date": [pd.Timestamp("2015-06-30")]})
        >>> depots = pd.DataFrame(
        ...     {
        ...         "ticker": ["AAA"],
        ...         "available_from": [pd.Timestamp("2015-05-15")],
        ...         "eps": [1.10],
        ...     }
        ... )
        >>> joint = asof_join(decisions, depots, "ticker", "date", "available_from")
        >>> float(joint["eps"].iloc[0])
        1.1
    """
    if direction not in ("backward", "forward", "nearest"):
        raise ConfigError(f"direction vaut {direction!r}, attendu « backward », « forward » ou « nearest »")
    if direction != "backward" and not allow_lookahead:
        raise LookAheadError(
            f"direction={direction!r} apparie une décision à de l'information postérieure. "
            "Si c'est vraiment ce que vous voulez, par exemple pour mesurer l'ampleur du biais, "
            "passez allow_lookahead=True et dites-le dans le rapport"
        )

    by_columns = [on] if isinstance(on, str) else list(on)
    if not by_columns:
        raise ConfigError("on est vide ; une jointure temporelle exige au moins une clé de groupe")
    for name in by_columns:
        if name not in left.columns:
            raise DataQualityError(f"clé de groupe « {name} » absente du tableau left")
        if name not in right.columns:
            raise DataQualityError(f"clé de groupe « {name} » absente du tableau right")

    left_values = _check_time_column(left, left_time, "left")
    right_values = _check_time_column(right, right_time, "right")
    if _column_timezone(left_values) != _column_timezone(right_values):
        raise DataQualityError(
            f"« {left_time} » et « {right_time} » n'ont pas le même fuseau ; alignez-les avant la jointure"
        )

    left_aligned, right_aligned = _align_resolution(left_values, right_values)
    left_ready = left.assign(**{left_time: left_aligned})
    right_ready = right.assign(**{right_time: right_aligned})

    if direction != "backward":
        _logger.warning(
            "jointure temporelle non rétrograde autorisée explicitement",
            extra={"direction": direction, "left_time": left_time, "right_time": right_time},
        )
    return pd.merge_asof(
        left_ready,
        right_ready,
        left_on=left_time,
        right_on=right_time,
        by=by_columns,
        direction=direction,
        allow_exact_matches=allow_exact_matches,
        tolerance=tolerance,
        suffixes=suffixes,
    )
