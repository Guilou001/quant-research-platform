r"""Les fondamentaux point-in-time de la SEC, et la date à partir de laquelle on peut s'en servir.

**Le problème.** Un chiffre comptable porte deux dates, et confondre les deux
fabrique un backtest faux. La première est la fin de la période décrite, par
exemple le trimestre clos le 31 mars 2015. La seconde est le jour où ce chiffre
est devenu public, par exemple le 15 mai 2015. Un portefeuille construit le
31 mars 2015 ne peut utiliser que ce qui était public ce jour-là. Une base de
données qui ne garde que la période détruit cette distinction, et la stratégie
qu'on teste dessus gagne avec de l'information qu'elle n'avait pas.

**La deuxième source de fuite, moins connue.** Une société corrige ses comptes.
Le même trimestre est déclaré une première fois, puis redéclaré plus tard avec
une valeur différente. La base qui ne garde que la dernière valeur donne au
backtest le chiffre corrigé des années à l'avance. Un cas mesuré le 2026-09-01
sur le concept ``us-gaap:Assets`` d'Apple le montre. La période close le
27 septembre 2008 vaut 39 572 000 000 dollars dans le 10-Q déposé le 22 juillet
2009. Elle vaut 36 171 000 000 dollars dans le 10-K/A déposé le 25 janvier 2010,
soit 3 401 000 000 dollars de moins, 8,6 % du premier chiffre. Ce trimestre est
déclaré sept fois en tout dans ce fichier.

**Le remède tenu par ce module.** Le tableau rendu par :func:`to_point_in_time`
garde toutes les déclarations, et porte quatre dates par ligne :

- ``period_end``, la fin de la période économique décrite ;
- ``filing_date``, le jour du dépôt, champ ``filed`` du JSON de la SEC ;
- ``accepted_timestamp``, l'instant d'acceptation, absent du JSON des faits et
  rempli depuis les soumissions quand l'appelant les fournit ;
- ``available_from``, la date à partir de laquelle l'information est utilisable.

La règle d'``available_from`` est écrite une fois pour toutes dans
:data:`AVAILABILITY_RULE` : elle vaut ``filing_date``, jamais ``period_end``,
avec un décalage optionnel de un jour de bourse pour l'étude qui veut se donner
une marge. Le choix de la valeur retenue à une date donnée appartient à
:func:`as_of`, qui rend la dernière déclaration connue à cette date et rien
d'autre.

**Le débit, et le 403 de la SEC.** Le service EDGAR annonce dix requêtes par
seconde et exige un ``User-Agent`` nominatif avec un courriel. Deux mesures
opposées sur le même environnement : le 2026-08-29, tout le domaine ``sec.gov``
répondait 403 « Request Rate Threshold Exceeded », y compris ``data.sec.gov``,
avec l'en-tête d'identification, sur sept relances en vingt minutes. Le
2026-09-01, les trois adresses ci-dessous répondent 200 avec le même en-tête.
Le blocage était donc un débit, et non une politique visant l'adresse. La
conséquence pratique est dans :data:`MIN_REQUEST_DELAY_S` : le fournisseur
n'accepte jamais une pause plus courte qu'un dixième de seconde entre deux
requêtes vers le même hôte.

Adresses mesurées en réponse 200 le 2026-09-01 :

.. code-block:: text

    https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/Assets.json
    https://data.sec.gov/submissions/CIK0000320193.json
    https://www.sec.gov/Archives/edgar/full-index/2015/QTR2/master.idx

**La frontière du module.** Les fonctions pures font tout le travail
scientifique et se testent sans réseau : :func:`to_point_in_time`,
:func:`as_of`, :func:`assert_no_lookahead`, :func:`parse_master_index`,
:func:`parse_company_tickers`, :func:`parse_acceptance`. La classe
:class:`SecProvider` ne fait que le réseau, le cache brut et la provenance.

Statut des chiffres de ce module : les deux dates de mesure du domaine
``sec.gov``, les valeurs d'Apple citées plus haut et les extraits recopiés dans
les tests sont mesurés le 2026-09-01. La limite de dix requêtes par seconde est
rapportée, elle vient de la documentation « Accessing EDGAR Data » de la SEC.

Exemple :

.. code-block:: python

    provider = SecProvider()
    pit = to_point_in_time(provider.company_facts(320193), tags=("Assets",))
    connu = as_of(pit, "2009-12-31")
    corrige = as_of(pit, "2010-06-30")
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, Final

import pandas as pd

from quantlab.core.calendars import DEFAULT_CALENDAR, get_calendar
from quantlab.core.errors import ConfigError, DataQualityError, LookAheadError
from quantlab.core.logging import get_logger, stage
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest
from quantlab.data.providers.base import BaseProvider, HttpClient

log = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Constantes de la source
# --------------------------------------------------------------------------- #

#: Le nom du fournisseur, qui nomme aussi son dossier de cache brut.
PROVIDER_NAME: Final[str] = "sec"

#: La racine des interfaces de données XBRL et des soumissions.
DATA_BASE_URL: Final[str] = "https://data.sec.gov"

#: La racine des fichiers statiques et des archives EDGAR.
WWW_BASE_URL: Final[str] = "https://www.sec.gov"

#: Le nombre de requêtes par seconde annoncé par la SEC. Chiffre rapporté,
#: repris de sa page « Accessing EDGAR Data ».
MAX_REQUESTS_PER_SECOND: Final[float] = 10.0

#: La pause minimale entre deux requêtes vers le même hôte, en secondes. Elle
#: vaut l'inverse de :data:`MAX_REQUESTS_PER_SECOND`, soit 0,1 seconde.
MIN_REQUEST_DELAY_S: Final[float] = 1.0 / MAX_REQUESTS_PER_SECOND

#: La taxonomie XBRL par défaut, celle des principes comptables américains.
DEFAULT_TAXONOMY: Final[str] = "us-gaap"

#: La licence de la source. Une œuvre du gouvernement fédéral américain n'est
#: pas protégée par le droit d'auteur, 17 U.S.C. § 105.
LICENSE: Final[str] = "domaine public (17 U.S.C. § 105)"

#: L'adresse de la licence, la page de politique de diffusion de la SEC.
LICENSE_URL: Final[str] = "https://www.sec.gov/about/privacy-information#security"

#: Ce qui arrive au chiffre déjà déposé quand la société le corrige.
REVISION_POLICY: Final[str] = (
    "une société redéclare le même trimestre dans un dépôt ultérieur, avec une "
    "valeur différente ; toutes les déclarations sont conservées et « as_of » "
    "choisit la dernière connue à la date demandée"
)

#: La règle d'utilisabilité, écrite une fois et citée partout ailleurs.
AVAILABILITY_RULE: Final[str] = (
    "available_from vaut filing_date, le jour du dépôt, éventuellement décalé "
    "d'un nombre entier de jours de bourse ; il ne vaut jamais period_end"
)

#: Les limites connues de la source. Aucune n'est corrigeable par du code.
KNOWN_LIMITATIONS: Final[tuple[str, ...]] = (
    "Le JSON des faits XBRL ne porte aucun horodatage d'acceptation : ses "
    "enregistrements ont « filed » et « accn », rien de plus. Mesuré le "
    "2026-09-01 sur companyconcept et companyfacts. Un dépôt accepté après la "
    "clôture est donc traité comme utilisable le jour même, ce qui est "
    "optimiste, et le décalage d'un jour de bourse est la façon d'y remédier.",
    "Les données XBRL commencent aux environs de 2009 pour la plupart des "
    "sociétés, l'obligation de dépôt structuré ayant été échelonnée de 2009 à "
    "2011. Une étude antérieure à 2009 ne se bâtit pas sur cette interface.",
    "Le fichier company_tickers.json ne liste que les émetteurs courants, donc "
    "un univers bâti dessus porte un biais de survie. Les dépôts des sociétés "
    "disparues restent dans les archives EDGAR, qui n'en portent pas.",
    "Un même concept comptable change de balise XBRL d'un exercice à l'autre, "
    "et la SEC ne publie aucune table de correspondance. Une série longue sur "
    "une balise unique se coupe donc sans prévenir.",
    "EDGAR reçoit des dépôts les jours où la Bourse est fermée. Mesuré le "
    "2026-09-01 sur l'index du deuxième trimestre 2015 : 3 542 des 260 019 "
    "dépôts, soit 1,36 %, tombent hors séance, le Vendredi saint du 3 avril et "
    "le samedi 25 avril. Avec un décalage nul, available_from vaut alors une "
    "date sans séance, ce qui est la règle littérale et non un défaut. Un "
    "décalage d'au moins une séance ramène la date sur le calendrier.",
    "Le décalage en séances ne va pas plus loin que le calendrier chargé. "
    "Mesuré le 2026-09-01 : exchange_calendars ouvre XNYS le 2006-09-01 et le "
    "ferme le 2027-09-01, soit vingt et un ans glissants. Un dépôt antérieur "
    "lève plutôt que de rendre une date fausse. Les faits XBRL commençant vers "
    "2009, la borne basse ne gêne pas, mais elle se déplace avec la date du "
    "jour et n'est donc pas un acquis.",
)

#: Le schéma du tableau point-in-time. Aucune fonction n'en rend un autre.
PIT_SCHEMA: Final[tuple[str, ...]] = (
    "cik",
    "entity_name",
    "taxonomy",
    "tag",
    "unit",
    "period_start",
    "period_end",
    "filing_date",
    "accepted_timestamp",
    "available_from",
    "value",
    "accession",
    "form",
    "fiscal_year",
    "fiscal_period",
    "frame",
    "is_instant",
    "is_restatement",
)

#: Le type de chaque colonne du schéma point-in-time.
PIT_DTYPES: Final[dict[str, str]] = {
    "cik": "str",
    "entity_name": "str",
    "taxonomy": "str",
    "tag": "str",
    "unit": "str",
    "period_start": "datetime64[ns]",
    "period_end": "datetime64[ns]",
    "filing_date": "datetime64[ns]",
    "accepted_timestamp": "datetime64[ns, UTC]",
    "available_from": "datetime64[ns]",
    "value": "float64",
    "accession": "str",
    "form": "str",
    "fiscal_year": "Int64",
    "fiscal_period": "str",
    "frame": "str",
    "is_instant": "bool",
    "is_restatement": "bool",
}

#: Les colonnes qui identifient une période déclarée, hors date de dépôt. Deux
#: lignes qui partagent ces cinq valeurs décrivent la même chose, déclarée deux
#: fois.
PERIOD_KEY: Final[tuple[str, ...]] = ("cik", "taxonomy", "tag", "unit", "period_end")

#: Les colonnes du tableau rendu par :func:`parse_master_index`.
INDEX_SCHEMA: Final[tuple[str, ...]] = (
    "cik",
    "company_name",
    "form_type",
    "date_filed",
    "filename",
    "url",
)

#: Les colonnes du tableau rendu par :func:`parse_company_tickers`.
TICKER_SCHEMA: Final[tuple[str, ...]] = ("ticker", "cik", "title")

#: La ligne de tirets qui sépare l'en-tête des données dans un ``master.idx``.
_INDEX_SEPARATOR: Final[str] = "-----"

#: Le nombre de champs d'une ligne de ``master.idx``.
_INDEX_FIELDS: Final[int] = 5

#: La longueur d'un identifiant de déposant, complété par des zéros à gauche.
_CIK_WIDTH: Final[int] = 10

#: Les trimestres acceptés par :meth:`SecProvider.full_index`.
_QUARTERS: Final[frozenset[int]] = frozenset({1, 2, 3, 4})

#: La première année pour laquelle EDGAR publie un index complet. Mesuré le
#: 2026-09-01 : l'adresse de 1993/QTR1 répond, celle de 1992 non.
_FIRST_INDEX_YEAR: Final[int] = 1993

_DIGITS = re.compile(r"\d+")

#: La forme écrite acceptée pour un identifiant de déposant : un préfixe ``CIK``
#: facultatif, des zéros de tête facultatifs, puis les chiffres, et rien après.
_CIK_TEXT = re.compile(r"^(?:cik)?[\s_]*0*(\d+)$", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Identifiants et adresses
# --------------------------------------------------------------------------- #


def normalize_cik(cik: int | str) -> str:
    """Rend l'identifiant de déposant sur dix chiffres, zéros de tête compris.

    (1) Le problème : la SEC écrit le même déposant de trois façons, ``320193``
    dans un JSON, ``0000320193`` dans une adresse, ``CIK0000320193`` dans un nom
    de fichier. Trois écritures qui ne se joignent pas entre elles. (2)
    L'intuition : reconnaître ces trois écritures, et elles seules, puis
    compléter à gauche par des zéros jusqu'à dix. (5) L'hypothèse : un
    identifiant de déposant tient sur dix chiffres, ce qui est la règle de la
    SEC.

    (7) **La limite qui a coûté un correctif.** Une lecture qui se contenterait
    de récolter tous les chiffres de l'écriture décimale trahirait un flottant
    en silence. Le nombre ``320193.0``, forme sous laquelle pandas rend une
    colonne d'entiers dès qu'elle porte une valeur manquante, s'écrit
    ``« 320193.0 »``, dont les chiffres récoltés font ``3201930``. Apple
    deviendrait alors le déposant ``0003201930``, sans un mot. Un flottant est
    donc accepté seulement s'il est entier, et une écriture qui porte autre
    chose que le préfixe, les zéros et les chiffres est refusée.

    Args:
        cik: l'identifiant, entier ou chaîne, avec ou sans préfixe ``CIK`` et
            zéros de tête. Un flottant entier est accepté et converti ; un
            flottant à partie décimale est refusé.

    Returns:
        Les dix chiffres, sous forme de chaîne.

    Raises:
        ValueError: si l'entrée ne porte aucun chiffre, si elle ne s'écrit pas
            comme un identifiant, si elle est négative ou non entière, ou si
            elle porte plus de dix chiffres.

    Example:
        >>> normalize_cik(320193)
        '0000320193'
        >>> normalize_cik("CIK0000320193")
        '0000320193'
        >>> normalize_cik(320193.0)
        '0000320193'

    Note:
        (10) Vérification, en trois contrôles. Les trois écritures ci-dessus
        rendent la même chaîne. Une entrée de onze chiffres lève plutôt que de
        tronquer. Et ``normalize_cik(320193.0)`` rend le même identifiant que
        ``normalize_cik(320193)``, au lieu d'en fabriquer un autre.
    """
    if isinstance(cik, bool):
        raise ValueError(f"un booléen n'est pas un identifiant de déposant, reçu {cik}")
    if isinstance(cik, float):
        if cik != cik or cik in (float("inf"), float("-inf")) or not float(cik).is_integer():
            raise ValueError(f"un identifiant de déposant est un entier, reçu le flottant {cik}")
        cik = int(cik)
    if isinstance(cik, int):
        if cik < 0:
            raise ValueError(f"un identifiant de déposant est positif, reçu {cik}")
        digits = str(cik)
    else:
        text = str(cik).strip()
        match = _CIK_TEXT.match(text)
        if match is None:
            if not _DIGITS.search(text):
                raise ValueError(f"aucun chiffre dans l'identifiant de déposant « {cik} »")
            raise ValueError(
                f"« {cik} » ne s'écrit pas comme un identifiant de déposant : un préfixe "
                "« CIK » facultatif, des zéros de tête facultatifs, des chiffres, et rien d'autre"
            )
        digits = match.group(1)
    stripped = digits.lstrip("0") or "0"
    if len(stripped) > _CIK_WIDTH:
        raise ValueError(
            f"un identifiant de déposant tient sur {_CIK_WIDTH} chiffres, « {cik} » en porte {len(stripped)}"
        )
    return stripped.zfill(_CIK_WIDTH)


def company_facts_url(cik: int | str) -> str:
    """Rend l'adresse du JSON de tous les faits XBRL d'un déposant."""
    return f"{DATA_BASE_URL}/api/xbrl/companyfacts/CIK{normalize_cik(cik)}.json"


def company_concept_url(cik: int | str, taxonomy: str, tag: str) -> str:
    """Rend l'adresse du JSON d'un seul concept comptable d'un déposant."""
    return f"{DATA_BASE_URL}/api/xbrl/companyconcept/CIK{normalize_cik(cik)}/{taxonomy}/{tag}.json"


def submissions_url(cik: int | str) -> str:
    """Rend l'adresse du JSON des soumissions d'un déposant."""
    return f"{DATA_BASE_URL}/submissions/CIK{normalize_cik(cik)}.json"


def company_tickers_url() -> str:
    """Rend l'adresse du fichier qui associe un symbole boursier à un déposant."""
    return f"{WWW_BASE_URL}/files/company_tickers.json"


def full_index_url(year: int, quarter: int) -> str:
    """Rend l'adresse de l'index complet d'un trimestre d'EDGAR.

    Args:
        year: l'année, à partir de 1993.
        quarter: le trimestre, de 1 à 4.

    Raises:
        ValueError: si le trimestre n'est pas dans 1 à 4, ou l'année trop
            ancienne.
    """
    if quarter not in _QUARTERS:
        raise ValueError(f"le trimestre vaut 1, 2, 3 ou 4, reçu {quarter}")
    if int(year) < _FIRST_INDEX_YEAR:
        raise ValueError(f"EDGAR ne publie pas d'index complet avant {_FIRST_INDEX_YEAR}, reçu {year}")
    return f"{WWW_BASE_URL}/Archives/edgar/full-index/{int(year)}/QTR{int(quarter)}/master.idx"


def polite_delay_s(configured_delay_s: float) -> float:
    """Rend la pause à tenir entre deux requêtes, jamais plus courte que la limite.

    La SEC annonce dix requêtes par seconde. Une configuration plus agressive
    est relevée au plancher plutôt que refusée, parce qu'un réglage global du
    laboratoire ne connaît pas les contraintes de chaque source.

    Args:
        configured_delay_s: la pause demandée par la configuration, en secondes.

    Returns:
        Le maximum entre la pause demandée et :data:`MIN_REQUEST_DELAY_S`.

    Example:
        >>> polite_delay_s(0.0)
        0.1
        >>> polite_delay_s(0.5)
        0.5
    """
    return max(float(configured_delay_s), MIN_REQUEST_DELAY_S)


# --------------------------------------------------------------------------- #
# Lecture du JSON des faits
# --------------------------------------------------------------------------- #


def _as_timestamp(value: object) -> pd.Timestamp:
    """Rend une date ISO en horodatage sans fuseau, ou ``NaT`` si elle manque."""
    if value is None or value == "":
        return pd.NaT
    return pd.Timestamp(str(value)).normalize()


def _utc_timestamp(value: object) -> pd.Timestamp:
    """Rend un horodatage en temps universel, qu'il porte déjà un fuseau ou non.

    Un horodatage naïf est supposé exprimé en temps universel, ce qui est le cas
    de tout ce que la SEC publie sous la forme ``...Z``.
    """
    stamp = pd.Timestamp(value)
    return stamp.tz_convert("UTC") if stamp.tzinfo is not None else stamp.tz_localize("UTC")


def _naive_midnight(value: pd.Timestamp) -> pd.Timestamp:
    """Rend un horodatage ramené à minuit et privé de son fuseau."""
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("UTC").tz_localize(None)
    return stamp.normalize()


def _iter_concept_blocks(payload: Mapping[str, Any]) -> Iterator[tuple[str, str, str, list[Any]]]:
    """Parcourt un JSON de faits et rend un bloc par taxonomie, balise et unité.

    Les deux interfaces de la SEC sont acceptées. ``companyfacts`` porte une
    clé ``facts`` à deux niveaux, taxonomie puis balise. ``companyconcept``
    porte directement ``units``, la taxonomie et la balise étant à la racine.

    Raises:
        DataQualityError: si le JSON ne ressemble à aucune des deux formes.
    """
    facts = payload.get("facts")
    if isinstance(facts, Mapping):
        for taxonomy, tags in facts.items():
            if not isinstance(tags, Mapping):
                continue
            for tag, body in tags.items():
                units = body.get("units") if isinstance(body, Mapping) else None
                if not isinstance(units, Mapping):
                    continue
                for unit, records in units.items():
                    yield str(taxonomy), str(tag), str(unit), list(records or [])
        return

    units = payload.get("units")
    if isinstance(units, Mapping):
        taxonomy = str(payload.get("taxonomy", ""))
        tag = str(payload.get("tag", ""))
        for unit, records in units.items():
            yield taxonomy, tag, str(unit), list(records or [])
        return

    raise DataQualityError(
        "le JSON reçu ne porte ni « facts » ni « units » : ce n'est ni une réponse "
        "companyfacts ni une réponse companyconcept de la SEC"
    )


def empty_pit_frame() -> pd.DataFrame:
    """Rend un tableau point-in-time vide, aux colonnes et aux types du schéma.

    Un tableau vide typé vaut mieux qu'un tableau vide nu : la suite du pipeline
    peut le concaténer, le filtrer et le trier sans traiter le cas particulier
    de l'absence de colonnes.
    """
    empty = pd.DataFrame({name: pd.Series(dtype=PIT_DTYPES[name]) for name in PIT_SCHEMA})
    return empty


def to_point_in_time(
    company_facts: Mapping[str, Any],
    *,
    taxonomies: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    units: Sequence[str] | None = None,
    acceptance: Mapping[str, Any] | None = None,
    availability_lag_business_days: int = 0,
    calendar: str = DEFAULT_CALENDAR,
) -> pd.DataFrame:
    r"""Rend le tableau point-in-time des faits XBRL, restatements compris.

    (1) **Le problème.** Le JSON de la SEC est un dictionnaire imbriqué où la
    même période apparaît autant de fois qu'elle a été déclarée. Aplati sans
    précaution, il perd la seule chose qui compte pour un backtest : la date à
    laquelle chaque valeur est devenue publique.

    (2) **L'intuition.** Une ligne par déclaration, jamais par période. Deux
    déclarations du même trimestre restent deux lignes, distinguées par leur
    date de dépôt, et la sélection est remise à plus tard, à :func:`as_of`.

    (3) **La règle d'utilisabilité.**

    .. math::

        a_i = \operatorname{sess}^{(k)}\!\left(f_i\right),
        \qquad k \in \mathbb{N},
        \qquad a_i \neq e_i

    (4) **Les variables.** :math:`a_i` est ``available_from`` de la ligne
    :math:`i`, :math:`f_i` sa ``filing_date``, :math:`e_i` sa ``period_end``,
    :math:`k` le décalage ``availability_lag_business_days``, et
    :math:`\operatorname{sess}^{(k)}` la composée :math:`k` fois de « séance
    suivante » du calendrier d'échange. Avec :math:`k = 0`, la composée est
    l'identité et :math:`a_i = f_i`.

    (5) **Les hypothèses.** Le champ ``filed`` est bien le jour de mise à
    disposition publique du dépôt. Un dépôt accepté après la clôture est traité
    comme utilisable le jour même, ce qui est optimiste, et c'est la raison
    d'être du décalage. Les valeurs ``val`` sont numériques.

    (6) **La provenance.** La distinction entre période décrite et date de
    connaissance est celle des bases point-in-time de la littérature comptable.
    Sloan (1996) la chiffre pour les accruals, dont l'effet se réduit quand on
    n'utilise que l'information réellement publiée. Livnat et Mendenhall (2006)
    montrent que la surprise de bénéfice calculée sur données révisées diffère
    de celle calculée en temps réel. Statut de ces deux renvois : rapporté, non
    revérifié ici.

    (7) **Les limites.** Le JSON des faits ne porte pas d'horodatage
    d'acceptation, seulement une date de dépôt et un numéro d'accession, mesuré
    le 2026-09-01. La finesse maximale est donc le jour. Les autres limites de
    la source sont énumérées dans :data:`KNOWN_LIMITATIONS`.

    (8) **Les alternatives.** Compustat point-in-time et le fichier « Unrestated
    Quarterly » offrent l'horodatage à l'heure et remontent avant 2009, tous
    deux payants. L'interface « frames » de la SEC rend une période pour tous
    les déposants d'un coup, mais elle ne garde qu'une déclaration par période,
    donc elle détruit précisément ce que cette fonction conserve.

    (9) **Pourquoi celle-ci.** Elle est gratuite, elle porte la date de dépôt
    dans chaque enregistrement, et elle conserve les redéclarations. Les trois
    conditions d'une base point-in-time honnête sont réunies sans payer.

    Args:
        company_facts: le JSON décodé d'une réponse ``companyfacts`` ou
            ``companyconcept`` de la SEC.
        taxonomies: les taxonomies gardées, par exemple ``("us-gaap",)``. Sans
            valeur, toutes.
        tags: les balises gardées, par exemple ``("Assets", "Revenues")``. Sans
            valeur, toutes.
        units: les unités gardées, par exemple ``("USD",)``. Sans valeur,
            toutes.
        acceptance: une correspondance du numéro d'accession vers l'instant
            d'acceptation, telle que la rend :func:`parse_acceptance`. Sans
            valeur, la colonne ``accepted_timestamp`` reste vide, ce qui est le
            statut « non trouvé » et non zéro.
        availability_lag_business_days: le nombre de séances ajoutées à la date
            de dépôt. Zéro par défaut, ce qui est la règle littérale. Un jour
            est le choix conservateur pour un dépôt accepté après la clôture.
        calendar: le calendrier d'échange servant au décalage, la Bourse de
            New York par défaut.

    Returns:
        Un tableau au schéma :data:`PIT_SCHEMA`, trié par période puis par date
        de dépôt croissante, où toutes les déclarations sont conservées.

    Raises:
        DataQualityError: si le JSON n'a pas la forme attendue, ou si un
            enregistrement porte une valeur non numérique.
        ValueError: si le décalage est négatif.

    Example:
        >>> extrait = {
        ...     "cik": 320193,
        ...     "taxonomy": "us-gaap",
        ...     "tag": "Assets",
        ...     "units": {"USD": [
        ...         {"end": "2008-09-27", "val": 39572000000,
        ...          "accn": "0001193125-09-153165", "fy": 2009, "fp": "Q3",
        ...          "form": "10-Q", "filed": "2009-07-22"},
        ...     ]},
        ... }
        >>> pit = to_point_in_time(extrait)
        >>> pit.loc[0, "available_from"] == pd.Timestamp("2009-07-22")
        True

    Note:
        (10) **Comment vérifier.** Trois contrôles indépendants du code. Le
        premier est une identité : ``available_from`` égale ``filing_date``
        quand le décalage est nul, sur toutes les lignes. Le deuxième est un
        comptage : le nombre de lignes dont ``is_restatement`` est faux égale le
        nombre de périodes distinctes. Le troisième est une valeur publiée par
        la source elle-même, les deux déclarations du 27 septembre 2008 d'Apple
        citées en tête de module.
    """
    if int(availability_lag_business_days) < 0:
        raise ValueError(
            "availability_lag_business_days ne peut pas être négatif : "
            "avancer la disponibilité d'une information est exactement la fuite "
            f"que ce module empêche, reçu {availability_lag_business_days}"
        )

    cik = normalize_cik(company_facts["cik"]) if "cik" in company_facts else ""
    entity_name = str(company_facts.get("entityName", ""))
    keep_taxonomies = frozenset(taxonomies) if taxonomies is not None else None
    keep_tags = frozenset(tags) if tags is not None else None
    keep_units = frozenset(units) if units is not None else None
    acceptance_map = dict(acceptance or {})

    rows: list[dict[str, Any]] = []
    for taxonomy, tag, unit, records in _iter_concept_blocks(company_facts):
        if keep_taxonomies is not None and taxonomy not in keep_taxonomies:
            continue
        if keep_tags is not None and tag not in keep_tags:
            continue
        if keep_units is not None and unit not in keep_units:
            continue
        for record in records:
            rows.append(_row_from_record(record, cik, entity_name, taxonomy, tag, unit, acceptance_map))

    frame = _assemble_pit_frame(rows)
    frame["available_from"] = _availability_dates(
        frame["filing_date"],
        lag_business_days=int(availability_lag_business_days),
        calendar=calendar,
    )
    frame = frame.sort_values([*PERIOD_KEY, "filing_date", "accession"], kind="stable", ignore_index=True)
    frame["is_restatement"] = frame.duplicated(subset=list(PERIOD_KEY), keep="first")
    return frame.loc[:, list(PIT_SCHEMA)]


def _row_from_record(
    record: Mapping[str, Any],
    cik: str,
    entity_name: str,
    taxonomy: str,
    tag: str,
    unit: str,
    acceptance: Mapping[str, Any],
) -> dict[str, Any]:
    """Rend une ligne du tableau depuis un enregistrement du JSON de la SEC.

    Raises:
        DataQualityError: si l'enregistrement n'a ni ``end``, ni ``filed``, ni
            valeur numérique.
    """
    for required in ("end", "filed", "val"):
        if required not in record:
            raise DataQualityError(
                f"enregistrement XBRL sans champ « {required} » pour {taxonomy}:{tag} "
                f"du déposant {cik or 'inconnu'}"
            )
    try:
        value = float(record["val"])
    except (TypeError, ValueError) as exc:
        raise DataQualityError(
            f"valeur non numérique « {record['val']!r} » pour {taxonomy}:{tag}, "
            f"dépôt {record.get('accn', 'inconnu')}"
        ) from exc

    accession = str(record.get("accn", ""))
    period_end = _as_timestamp(record["end"])
    filing_date = _as_timestamp(record["filed"])
    # Une date vide ou illisible se lit en « NaT », qui traverse ensuite tout le
    # module sans un mot. La ligne devient invisible à « as_of », qui écarte les
    # dates manquantes. Le garde anti-fuite la laisse passer aussi, parce que ses
    # deux comparaisons sont fausses face à « NaT ». Perdre une déclaration en
    # silence est pire que refuser le fichier, donc on refuse.
    for name, stamp in (("end", period_end), ("filed", filing_date)):
        if pd.isna(stamp):
            raise DataQualityError(
                f"date « {name} » illisible ou vide (« {record[name]!r} ») pour {taxonomy}:{tag}, "
                f"dépôt {accession or 'inconnu'} du déposant {cik or 'inconnu'}"
            )
    accepted = acceptance.get(accession)
    start = record.get("start")
    fiscal_year = record.get("fy")
    return {
        "cik": cik,
        "entity_name": entity_name,
        "taxonomy": taxonomy,
        "tag": tag,
        "unit": unit,
        "period_start": _as_timestamp(start),
        "period_end": period_end,
        "filing_date": filing_date,
        "accepted_timestamp": _utc_timestamp(accepted) if accepted is not None else pd.NaT,
        "available_from": pd.NaT,
        "value": value,
        "accession": accession,
        "form": str(record.get("form", "")),
        "fiscal_year": pd.NA if fiscal_year is None else int(fiscal_year),
        "fiscal_period": str(record.get("fp", "")),
        "frame": str(record.get("frame", "")),
        "is_instant": start is None,
        "is_restatement": False,
    }


def _assemble_pit_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Rend le tableau typé correspondant aux lignes lues, vide compris."""
    if not rows:
        return empty_pit_frame()
    frame = pd.DataFrame.from_records(rows, columns=list(PIT_SCHEMA))
    for name, dtype in PIT_DTYPES.items():
        if dtype == "datetime64[ns, UTC]":
            frame[name] = pd.to_datetime(frame[name], utc=True).astype(dtype)
        else:
            frame[name] = frame[name].astype(dtype)
    return frame


def _availability_dates(
    filing_dates: pd.Series,
    *,
    lag_business_days: int,
    calendar: str,
) -> pd.Series:
    """Rend la date d'utilisabilité de chaque dépôt, décalage appliqué.

    Le décalage passe par les séances du calendrier d'échange plutôt que par des
    jours calendaires : un dépôt du vendredi n'est pas négociable le samedi.

    **La date de dépôt n'est pas toujours une séance, et c'est le point
    délicat.** EDGAR reçoit des dépôts les jours où la Bourse de New York est
    fermée. Mesuré le 2026-09-01 sur l'index complet du deuxième trimestre
    2015 : 3 542 des 260 019 dépôts tombent un jour qui n'est pas une séance,
    soit 1,36 %. Deux jours portent ces dépôts, le Vendredi saint du 3 avril
    2015 et le samedi 25 avril 2015. Le décalage ne peut donc pas partir d'une
    fonction qui exige
    que son argument soit lui-même une séance. Il est calculé par recherche
    dichotomique dans la liste des séances : la position de la première séance
    strictement postérieure au dépôt, plus le décalage moins un.

    Le calcul se fait sur les dates distinctes, puis se recopie, ce qui évite
    autant de recherches qu'il y a de lignes.

    Args:
        filing_dates: les dates de dépôt, une par ligne du tableau.
        lag_business_days: le nombre de séances ajoutées, zéro compris.
        calendar: le code du calendrier d'échange.

    Returns:
        Les dates d'utilisabilité, dans le même ordre et avec le même index.

    Raises:
        DataQualityError: si une date de dépôt précède le début du calendrier,
            ou si le calendrier s'arrête avant la séance visée.
    """
    if lag_business_days == 0:
        return filing_dates.copy()
    all_sessions = pd.DatetimeIndex(get_calendar(calendar).sessions)
    uniques = pd.DatetimeIndex(filing_dates.dropna().unique())
    mapping: dict[pd.Timestamp, pd.Timestamp] = {}
    for stamp in uniques:
        moment = pd.Timestamp(stamp)
        if moment < all_sessions[0]:
            raise DataQualityError(
                f"le calendrier {calendar} commence le {all_sessions[0].date()} et ne peut pas "
                f"décaler la date de dépôt {moment.date()} : la séance suivante est inconnue"
            )
        position = int(all_sessions.searchsorted(moment, side="right")) + lag_business_days - 1
        if position >= len(all_sessions):
            raise DataQualityError(
                f"le calendrier {calendar} s'arrête le {all_sessions[-1].date()} et ne porte pas "
                f"{lag_business_days} séance(s) après la date de dépôt {moment.date()}"
            )
        mapping[moment] = all_sessions[position]
    return filing_dates.map(mapping)


# --------------------------------------------------------------------------- #
# Lecture à une date passée
# --------------------------------------------------------------------------- #


def as_of(
    table: pd.DataFrame,
    date: dt.date | str,
    *,
    tags: Sequence[str] | None = None,
    keep_all_revisions: bool = False,
) -> pd.DataFrame:
    """Rend ce que le tableau point-in-time disait à la date demandée, et rien de plus.

    (1) **Le problème.** Un tableau qui garde toutes les déclarations ne se lit
    pas directement. Au 30 juin 2010, le trimestre clos en septembre 2008 a
    plusieurs valeurs déclarées, dont une seule était la dernière connue ce
    jour-là.

    (2) **L'intuition.** Deux gestes, dans cet ordre. Écarter tout ce qui
    n'était pas encore public, puis, parmi ce qui reste, garder la déclaration
    la plus récente de chaque période.

    (3) **La formule.** Pour une période :math:`p` et une date :math:`d` :

    .. math::

        v_p(d) = v_{i^\\star}, \\qquad
        i^\\star = \\arg\\max_{i \\,:\\, a_i \\le d,\\; \\pi_i = p} f_i

    (4) **Les variables.** :math:`a_i` est ``available_from``, :math:`f_i`
    ``filing_date``, :math:`\\pi_i` la clé de période :data:`PERIOD_KEY`,
    :math:`v_i` la valeur, et :math:`d` la date demandée.

    (5) **Les hypothèses.** Le tableau porte les colonnes de
    :data:`PIT_SCHEMA`. Les égalités de date de dépôt se départagent par le
    numéro d'accession, ordre arbitraire mais déterministe.

    (6) **La provenance.** La règle « dernière valeur connue à la date, et non
    dernière valeur connue aujourd'hui » est celle des bases point-in-time.
    Livnat et Mendenhall (2006) mesurent l'écart entre une surprise de bénéfice
    calculée sur données révisées et la même calculée en temps réel. Statut :
    rapporté, non revérifié ici.

    (7) **Les limites.** La comparaison est faite au jour, donc un dépôt du jour
    même est considéré comme utilisable dans la journée. Une étude
    intrajournalière doit passer par ``availability_lag_business_days=1``.

    (8) **Les alternatives.** Garder la dernière valeur quelle que soit sa date,
    ce qui est la fuite du module entier. Garder la première déclaration et
    ignorer les corrections, défendable pour étudier ce que le marché voyait,
    mais faux dès qu'une correction est devenue publique avant la date demandée.
    Une jointure temporelle ``merge_asof``, écartée parce qu'elle ne sait pas
    départager deux déclarations de la même période.

    (9) **Pourquoi celle-ci.** Elle est la seule des trois qui redonne
    exactement l'information publique à la date demandée, ce qui est la
    définition d'une caractéristique utilisable dans un backtest.

    Args:
        table: un tableau rendu par :func:`to_point_in_time`.
        date: la date du portefeuille. Une heure éventuelle est ignorée, la
            source ne descendant pas sous le jour.
        tags: restreint aux balises demandées, sans valeur toutes.
        keep_all_revisions: vrai, rend toutes les déclarations déjà publiques
            sans garder seulement la dernière. Sert à examiner l'historique des
            corrections, pas à construire une caractéristique.

    Returns:
        Un tableau au même schéma, une ligne par période quand
        ``keep_all_revisions`` est faux, index réinitialisé.

    Raises:
        DataQualityError: si le tableau ne porte pas les colonnes du schéma.

    Example:
        Sur les deux déclarations d'Apple pour la période close le 27 septembre
        2008, ``as_of(pit, "2009-12-31")`` rend 39 572 000 000 dollars et
        ``as_of(pit, "2010-06-30")`` rend 36 171 000 000 dollars.

    Note:
        (10) **Comment vérifier.** Une date antérieure à tout dépôt rend un
        tableau vide, et le nombre de lignes visibles ne décroît jamais quand la
        date avance. Les deux sont testés.
    """
    missing = [name for name in ("available_from", "filing_date", *PERIOD_KEY) if name not in table]
    if missing:
        raise DataQualityError(f"colonnes absentes du tableau point-in-time : {missing}")

    stamp = _naive_midnight(pd.Timestamp(date))
    visible = table.loc[table["available_from"].notna() & (table["available_from"] <= stamp)]
    if tags is not None:
        visible = visible.loc[visible["tag"].isin(list(tags))]
    ordered = visible.sort_values([*PERIOD_KEY, "filing_date", "accession"], kind="stable")
    if keep_all_revisions:
        return ordered.reset_index(drop=True)
    return ordered.drop_duplicates(subset=list(PERIOD_KEY), keep="last").reset_index(drop=True)


def assert_no_lookahead(table: pd.DataFrame, *, max_reported: int = 5) -> None:
    r"""Vérifie que le tableau ne rend disponible aucune information trop tôt, ou lève.

    (1) **Le problème.** Un tableau point-in-time peut être fabriqué ailleurs
    que par :func:`to_point_in_time`, recopié, joint, filtré. Rien ne garantit
    alors que sa colonne d'utilisabilité dise encore la vérité, et une fuite ne
    se voit pas dans un résultat : elle se voit dans un résultat trop beau.

    (2) **L'intuition.** Deux inégalités suffisent, et elles ne se recouvrent
    pas. Le premier contrôle est un invariant de construction : la date
    d'utilisabilité ne précède jamais le dépôt. Le second est la règle
    économique : elle suit strictement la fin de la période décrite.

    (3) **La règle.** Pour chaque ligne :math:`i` :

    .. math::

        a_i \ge f_i \quad \text{et} \quad a_i > e_i

    (4) **Les variables.** :math:`a_i` est ``available_from``, :math:`f_i`
    ``filing_date``, :math:`e_i` ``period_end``.

    (5) **Les hypothèses.** Les trois colonnes sont présentes et renseignées.
    Une date manquante n'est pas une ligne saine : les deux comparaisons sont
    fausses face à ``NaT``, si bien qu'une ligne sans date passerait le contrôle
    sans le subir. Elle est donc refusée avant les deux inégalités.

    (6) **La provenance.** La règle 1 du fichier ``CLAUDE.md`` de ce dépôt, dont
    l'énoncé vient de la pratique des bases point-in-time décrite par Sloan
    (1996) et Livnat et Mendenhall (2006). Statut : rapporté.

    (7) **Les limites.** Le contrôle est syntaxique. Il attrape une colonne
    mal remplie, jamais une date de dépôt fausse à la source : si la SEC
    publiait un ``filed`` erroné, les deux inégalités tiendraient quand même.

    (8) **Les alternatives.** Un contrôle statistique, qui signalerait une
    performance trop régulière, écarté parce qu'il ne dit pas où est la faute.
    Un contrôle par rejeu complet du pipeline à chaque date, exact mais dont le
    coût interdit de le lancer à chaque construction.

    (9) **Pourquoi celui-ci.** Il est exact, il coûte deux comparaisons
    vectorielles, et il nomme les lignes fautives, ce qui rend la correction
    possible sans enquête.

    Args:
        table: le tableau à contrôler.
        max_reported: le nombre de lignes fautives citées dans le message.

    Raises:
        LookAheadError: si l'un des contrôles échoue. Le message cite les
            premières lignes fautives, avec leur période et leur dépôt.

    Example:
        Le contrôle canonique du laboratoire : un dépôt accepté le 15 mai 2015
        n'est pas connaissable au 31 mars 2015. Le tableau qui le prétendrait
        échoue ici.

    Note:
        (10) **Comment vérifier.** Trois tableaux truqués à la main, un par
        faute : ``available_from`` posé à ``period_end``, posé à la veille du
        dépôt, et une ligne dont la date d'utilisabilité manque. Les trois
        doivent lever, et le tableau issu de :func:`to_point_in_time` ne doit
        pas lever.

        La fonction ne s'appelle pas toute seule dans :func:`to_point_in_time`.
        Elle est faite pour être lancée sur le panel d'une étude, une fois, et
        pour arrêter le pipeline plutôt que de laisser produire un résultat
        flatteur.
    """
    columns = ("available_from", "filing_date", "period_end")
    missing = [name for name in columns if name not in table]
    if missing:
        raise DataQualityError(f"colonnes absentes du tableau point-in-time : {missing}")
    absent = table.loc[table[list(columns)].isna().any(axis=1)]
    if not absent.empty:
        raise LookAheadError(
            f"{len(absent)} ligne(s) portent une date manquante parmi {columns} : une date "
            "absente échappe aux deux contrôles au lieu de les subir, donc elle est refusée. "
            f"Premiers numéros d'accession : {list(absent['accession'].head(max_reported))}"
        )
    early = table.loc[table["available_from"] < table["filing_date"]]
    if not early.empty:
        raise LookAheadError(
            "available_from précède la date de dépôt sur "
            f"{len(early)} ligne(s) : {_offenders(early, max_reported)}"
        )
    premature = table.loc[table["available_from"] <= table["period_end"]]
    if not premature.empty:
        raise LookAheadError(
            "de l'information est déclarée utilisable avant la fin de la période "
            f"qu'elle décrit, sur {len(premature)} ligne(s) : {_offenders(premature, max_reported)}"
        )


def _offenders(rows: pd.DataFrame, limit: int) -> str:
    """Rend une description courte des premières lignes fautives."""
    head = rows.head(limit)
    parts = [
        f"{row.tag} période {row.period_end.date()} dépôt {row.filing_date.date()} "
        f"utilisable {row.available_from.date()}"
        for row in head.itertuples()
    ]
    suffix = ", ..." if len(rows) > limit else ""
    return "; ".join(parts) + suffix


class PointInTimeFundamentals:
    """Un panel de fondamentaux qui sait ce qu'il était à une date passée.

    La classe tient le protocole
    :class:`quantlab.core.protocols.PointInTimeDataset`. Elle ne fait rien de
    plus que porter le tableau et appeler :func:`as_of`, ce qui suffit à ce que
    le reste du pipeline la reçoive sans savoir d'où vient la donnée.

    Args:
        table: un tableau rendu par :func:`to_point_in_time`.
        validate: vrai, le tableau passe :func:`assert_no_lookahead` à la
            construction. C'est le comportement par défaut, parce qu'un panel
            fautif doit échouer avant le backtest, pas pendant.

    Raises:
        LookAheadError: si ``validate`` et que le tableau contient une fuite.

    Example:
        .. code-block:: python

            panel = PointInTimeFundamentals(pit)
            connu = panel.as_of("2015-03-31")
    """

    def __init__(self, table: pd.DataFrame, *, validate: bool = True) -> None:
        if validate:
            assert_no_lookahead(table)
        self._table = table

    @property
    def table(self) -> pd.DataFrame:
        """Rend le tableau porté, toutes déclarations comprises."""
        return self._table

    def as_of(self, date: dt.date | str) -> pd.DataFrame:
        """Rend l'état du panel tel qu'il était connaissable à la date demandée."""
        return as_of(self._table, date)

    def __len__(self) -> int:
        return len(self._table)


# --------------------------------------------------------------------------- #
# Les autres formats de la SEC
# --------------------------------------------------------------------------- #


def parse_acceptance(payload: Mapping[str, Any]) -> dict[str, pd.Timestamp]:
    """Rend la correspondance du numéro d'accession vers l'instant d'acceptation.

    Le JSON des soumissions porte, lui, l'horodatage que le JSON des faits n'a
    pas. Le rapprocher par le numéro d'accession donne à chaque fait la minute
    de son acceptation, et non seulement son jour.

    Args:
        payload: le JSON décodé d'une réponse ``submissions``, ou l'un des
            fichiers supplémentaires listés dans ``filings.files``, qui portent
            les mêmes clés à la racine.

    Returns:
        Un dictionnaire du numéro d'accession vers un horodatage en temps
        universel.

    Raises:
        DataQualityError: si le JSON ne porte pas les deux colonnes attendues.

    Note:
        Limite mesurée le 2026-09-01 : le bloc ``filings.recent`` d'Apple
        s'arrête au dépôt du 2015-06-08, les plus anciens vivant dans le fichier
        ``CIK0000320193-submissions-001.json``. Un rapprochement complet exige
        donc de lire aussi ces fichiers, ce que fait
        :meth:`SecProvider.acceptance_timestamps`.
    """
    block = payload.get("filings", {}).get("recent") if "filings" in payload else payload
    if not isinstance(block, Mapping):
        raise DataQualityError("le JSON de soumissions ne porte pas de bloc de dépôts")
    accessions = block.get("accessionNumber")
    stamps = block.get("acceptanceDateTime")
    if accessions is None or stamps is None:
        raise DataQualityError("le bloc de dépôts ne porte pas « accessionNumber » et « acceptanceDateTime »")
    if len(accessions) != len(stamps):
        raise DataQualityError(
            f"{len(accessions)} numéros d'accession pour {len(stamps)} horodatages d'acceptation"
        )
    return {
        str(accession): _utc_timestamp(stamp)
        for accession, stamp in zip(accessions, stamps, strict=True)
        if accession and stamp
    }


def parse_company_tickers(payload: Mapping[str, Any]) -> pd.DataFrame:
    """Rend le tableau des symboles boursiers et de leur déposant.

    Args:
        payload: le JSON décodé de ``company_tickers.json``. Deux formes sont
            acceptées, celle d'un dictionnaire indexé par un rang, mesurée le
            2026-09-01, et celle d'un couple ``fields`` et ``data`` que la SEC
            emploie ailleurs.

    Returns:
        Un tableau aux colonnes :data:`TICKER_SCHEMA`, dans l'ordre du fichier.

    Raises:
        DataQualityError: si aucune des deux formes n'est reconnue.

    Note:
        Limite : ce fichier ne liste que les émetteurs courants. Un univers
        bâti dessus ne contient aucune société radiée, donc il porte un biais de
        survie, et c'est la troisième entrée de :data:`KNOWN_LIMITATIONS`.
    """
    records: list[Mapping[str, Any]]
    if "fields" in payload and "data" in payload:
        fields = [str(f) for f in payload["fields"]]
        records = [dict(zip(fields, row, strict=False)) for row in payload["data"]]
    elif all(isinstance(v, Mapping) for v in payload.values()):
        records = [dict(v) for v in payload.values()]
    else:
        raise DataQualityError(
            "le JSON des symboles n'a ni la forme « rang vers objet » ni la forme « fields/data »"
        )

    rows = [
        {
            "ticker": str(rec.get("ticker", "")).upper(),
            "cik": normalize_cik(rec["cik_str"]) if "cik_str" in rec else normalize_cik(rec["cik"]),
            "title": str(rec.get("title", "")),
        }
        for rec in records
        if rec.get("ticker")
    ]
    if not rows:
        return pd.DataFrame({name: pd.Series(dtype="str") for name in TICKER_SCHEMA})
    return pd.DataFrame.from_records(rows, columns=list(TICKER_SCHEMA)).astype("str")


def parse_master_index(text: str) -> pd.DataFrame:
    """Rend le tableau des dépôts d'un trimestre depuis un fichier ``master.idx``.

    Le fichier porte un en-tête de quelques lignes, une ligne de tirets, puis
    une ligne par dépôt, cinq champs séparés par une barre verticale. Le nom de
    société peut lui-même contenir une barre, donc la découpe se fait par les
    extrémités. Le premier champ est l'identifiant, les trois derniers sont le
    type, la date et le fichier, et le milieu est le nom.

    Args:
        text: le contenu du fichier, décodé.

    Returns:
        Un tableau aux colonnes :data:`INDEX_SCHEMA`, la colonne ``url`` portant
        l'adresse complète du dépôt.

    Raises:
        DataQualityError: si aucune ligne exploitable n'est trouvée.

    Example:
        Extrait mesuré le 2026-09-01 dans ``2015/QTR2/master.idx`` :
        ``1000045|NICHOLAS FINANCIAL INC|10-K|2015-06-15|edgar/data/1000045/0001193125-15-223218.txt``
        donne l'identifiant ``0001000045`` et la date du 15 juin 2015.
    """
    rows: list[dict[str, Any]] = []
    started = False
    for line in text.splitlines():
        stripped = line.strip()
        if not started:
            if stripped.startswith(_INDEX_SEPARATOR):
                started = True
            continue
        if not stripped or "|" not in stripped:
            continue
        parts = stripped.split("|")
        if len(parts) < _INDEX_FIELDS:
            continue
        filename = parts[-1]
        rows.append(
            {
                "cik": normalize_cik(parts[0]),
                "company_name": "|".join(parts[1:-3]),
                "form_type": parts[-3],
                "date_filed": _as_timestamp(parts[-2]),
                "filename": filename,
                "url": f"{WWW_BASE_URL}/Archives/{filename}",
            }
        )
    if not rows:
        raise DataQualityError(
            "aucune ligne de dépôt trouvée dans le fichier d'index : l'en-tête ou la "
            "ligne de tirets manque, ou le contenu n'est pas un master.idx"
        )
    frame = pd.DataFrame.from_records(rows, columns=list(INDEX_SCHEMA))
    frame["date_filed"] = pd.to_datetime(frame["date_filed"])
    for name in ("cik", "company_name", "form_type", "filename", "url"):
        frame[name] = frame[name].astype("str")
    return frame


# --------------------------------------------------------------------------- #
# Le fournisseur
# --------------------------------------------------------------------------- #


class SecProvider(BaseProvider):
    """Télécharge les fondamentaux d'EDGAR, les met en cache et déclare leur provenance.

    La classe ne fait que le réseau et la provenance. Toute la mise en forme
    appartient aux fonctions pures du module, qui se testent sans sortir.

    Trois règles tenues ici et nulle part ailleurs. Le ``User-Agent`` porte un
    courriel, sans quoi la SEC répond 403. La pause entre deux requêtes ne
    descend jamais sous :data:`MIN_REQUEST_DELAY_S`. Chaque réponse est écrite
    dans le cache brut avant d'être interprétée, ce dont s'occupe
    :meth:`BaseProvider.fetch_cached`.

    Args:
        client: le client HTTP. Sans valeur, il est créé au premier besoin, avec
            l'exigence de courriel et le plancher de débit.
        raw_root: la racine du cache brut. Sans valeur,
            ``data/raw/sec/``.
        availability_lag_business_days: le décalage appliqué par défaut à
            ``available_from``, en séances.
        calendar: le calendrier servant à ce décalage.

    Attributes:
        name: « sec », le nom qui apparaît dans une configuration d'expérience.

    Example:
        .. code-block:: python

            provider = SecProvider()
            panel = provider.fundamentals_panel(
                ciks=[320193], tags=["Assets"], start="2015-01-01", end="2020-12-31"
            )
            provider.manifest().point_in_time  # True, toujours
    """

    name = PROVIDER_NAME

    def __init__(
        self,
        *,
        client: HttpClient | None = None,
        raw_root: Any | None = None,
        availability_lag_business_days: int = 0,
        calendar: str = DEFAULT_CALENDAR,
    ) -> None:
        super().__init__(client=client, raw_root=raw_root)
        if int(availability_lag_business_days) < 0:
            raise ConfigError(
                "availability_lag_business_days ne peut pas être négatif, reçu "
                f"{availability_lag_business_days}"
            )
        self.availability_lag_business_days = int(availability_lag_business_days)
        self.calendar = str(calendar)
        self._last: dict[str, Any] | None = None

    # ---------------------------------------------------------- réseau --

    @property
    def client(self) -> HttpClient:
        """Rend le client HTTP, créé au premier appel avec les règles de la SEC.

        Le client créé ici exige un courriel dans le ``User-Agent`` et relève sa
        pause au plancher de :func:`polite_delay_s`. Un client fourni par
        l'appelant n'est pas modifié : c'est lui qui a la responsabilité de son
        propre débit.
        """
        if self._client is None:
            created = HttpClient(require_email_contact=True)
            created.limiter.delay_s = polite_delay_s(created.limiter.delay_s)
            self._client = created
        return self._client

    def company_facts(self, cik: int | str, *, refresh: bool = False) -> dict[str, Any]:
        """Rend tous les faits XBRL d'un déposant, sous la forme du JSON de la SEC.

        Args:
            cik: l'identifiant du déposant, dans n'importe laquelle de ses
                écritures.
            refresh: force un nouveau téléchargement.

        Returns:
            Le JSON décodé.

        Raises:
            ProviderError: si la source refuse ou ne répond pas.
        """
        url = company_facts_url(cik)
        raw = self.fetch_cached(url, label=f"companyfacts-{normalize_cik(cik)}", refresh=refresh)
        return dict(raw.json())

    def company_concept(
        self,
        cik: int | str,
        taxonomy: str = DEFAULT_TAXONOMY,
        tag: str = "Assets",
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Rend l'historique d'un seul concept comptable d'un déposant.

        Cette adresse est plus légère que ``companyfacts``, qui rend parfois
        plusieurs mégaoctets. Elle est le bon choix quand l'étude ne suit que
        deux ou trois balises.

        Args:
            cik: l'identifiant du déposant.
            taxonomy: la taxonomie, « us-gaap » par défaut.
            tag: la balise, par exemple « Assets » ou « Revenues ».
            refresh: force un nouveau téléchargement.
        """
        url = company_concept_url(cik, taxonomy, tag)
        label = f"concept-{normalize_cik(cik)}-{taxonomy}-{tag}"
        raw = self.fetch_cached(url, label=label, refresh=refresh)
        return dict(raw.json())

    def submissions(self, cik: int | str, *, refresh: bool = False) -> dict[str, Any]:
        """Rend le JSON des soumissions d'un déposant, horodatages d'acceptation compris.

        Args:
            cik: l'identifiant du déposant.
            refresh: force un nouveau téléchargement.

        Note:
            Le bloc ``filings.recent`` est tronqué aux dépôts les plus récents,
            les plus anciens vivant dans les fichiers que liste
            ``filings.files``. Mesuré le 2026-09-01 sur Apple : la partie
            courante s'arrête au 2015-06-08.
        """
        url = submissions_url(cik)
        raw = self.fetch_cached(url, label=f"submissions-{normalize_cik(cik)}", refresh=refresh)
        return dict(raw.json())

    def acceptance_timestamps(
        self,
        cik: int | str,
        *,
        include_history: bool = True,
        refresh: bool = False,
    ) -> dict[str, pd.Timestamp]:
        """Rend l'instant d'acceptation de chaque dépôt d'un déposant.

        Args:
            cik: l'identifiant du déposant.
            include_history: vrai, télécharge aussi les fichiers d'archive
                listés dans ``filings.files``, sans quoi les dépôts anciens
                n'ont pas d'horodatage.
            refresh: force un nouveau téléchargement.

        Returns:
            Le dictionnaire du numéro d'accession vers l'horodatage en temps
            universel, archives comprises quand elles sont demandées.
        """
        payload = self.submissions(cik, refresh=refresh)
        stamps = parse_acceptance(payload)
        if not include_history:
            return stamps
        for extra in payload.get("filings", {}).get("files", []) or []:
            name = str(extra.get("name", ""))
            if not name:
                continue
            url = f"{DATA_BASE_URL}/submissions/{name}"
            raw = self.fetch_cached(url, label=f"submissions-{name}", refresh=refresh)
            stamps.update(parse_acceptance(dict(raw.json())))
        return stamps

    def ticker_to_cik(self, *, refresh: bool = False) -> dict[str, str]:
        """Rend la correspondance du symbole boursier vers l'identifiant du déposant.

        Args:
            refresh: force un nouveau téléchargement.

        Returns:
            Un dictionnaire du symbole en majuscules vers les dix chiffres de
            l'identifiant. En cas de symbole répété, la première occurrence du
            fichier est gardée, et :func:`parse_company_tickers` rend le tableau
            complet pour qui veut les voir toutes.
        """
        raw = self.fetch_cached(company_tickers_url(), label="company-tickers", refresh=refresh)
        frame = parse_company_tickers(dict(raw.json()))
        mapping: dict[str, str] = {}
        for ticker, cik in zip(frame["ticker"], frame["cik"], strict=True):
            mapping.setdefault(ticker, cik)
        return mapping

    def full_index(self, year: int, quarter: int, *, refresh: bool = False) -> pd.DataFrame:
        """Rend la liste de tous les dépôts d'un trimestre d'EDGAR.

        Args:
            year: l'année, à partir de 1993.
            quarter: le trimestre, de 1 à 4.
            refresh: force un nouveau téléchargement.

        Returns:
            Un tableau aux colonnes :data:`INDEX_SCHEMA`.

        Note:
            Le fichier est encodé en Latin-1, non en UTF-8 : des noms de société
            portent des caractères qu'un décodage UTF-8 refuse. Le décodage
            Latin-1 ne peut pas échouer, ce qui est ici la propriété utile.
        """
        url = full_index_url(year, quarter)
        raw = self.fetch_cached(url, label=f"master-{year}-QTR{quarter}", refresh=refresh)
        return parse_master_index(raw.text(encoding="latin-1"))

    # ------------------------------------------------------------ panel --

    def fundamentals_panel(
        self,
        ciks: Iterable[int | str],
        tags: Sequence[str],
        start: dt.date | str,
        end: dt.date | str,
        *,
        taxonomy: str = DEFAULT_TAXONOMY,
        units: Sequence[str] | None = None,
        filter_on: str = "period_end",
        with_acceptance: bool = False,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Rend le panel point-in-time de plusieurs déposants et de plusieurs balises.

        Le panel est long, une ligne par déclaration, et il garde toutes les
        redéclarations. C'est ce qui le rend utilisable pour construire une
        caractéristique : à chaque date de rééquilibrage, l'étude appelle
        :func:`as_of` et n'obtient que ce qui était public ce jour-là.

        Args:
            ciks: les déposants demandés.
            tags: les balises XBRL suivies.
            start: première date de la fenêtre, incluse.
            end: dernière date de la fenêtre, incluse.
            taxonomy: la taxonomie, « us-gaap » par défaut.
            units: les unités gardées, sans valeur toutes.
            filter_on: la colonne sur laquelle la fenêtre s'applique,
                « period_end » par défaut, ou « available_from » pour garder
                tout ce qui est devenu public dans la fenêtre.
            with_acceptance: vrai, télécharge aussi les soumissions pour remplir
                ``accepted_timestamp``. Cela double le nombre de requêtes.
            refresh: force un nouveau téléchargement.

        Returns:
            Un tableau au schéma :data:`PIT_SCHEMA`, trié, index réinitialisé.

        Raises:
            ValueError: si ``filter_on`` n'est ni « period_end » ni
                « available_from », ou si la fenêtre est inversée.

        Example:
            .. code-block:: python

                panel = provider.fundamentals_panel(
                    ciks=[320193, 789019],
                    tags=["Assets", "Liabilities"],
                    start="2012-01-01",
                    end="2020-12-31",
                )
        """
        if filter_on not in {"period_end", "available_from"}:
            raise ValueError(f"filter_on vaut « period_end » ou « available_from », reçu « {filter_on} »")
        first, last = _naive_midnight(pd.Timestamp(start)), _naive_midnight(pd.Timestamp(end))
        if last < first:
            raise ValueError(f"la fenêtre est inversée : {first.date()} après {last.date()}")

        identifiers = [normalize_cik(c) for c in ciks]
        pieces: list[pd.DataFrame] = []
        with stage(
            "sec.fundamentals_panel",
            provider=self.name,
            n_ciks=len(identifiers),
            n_tags=len(tuple(tags)),
            start=first.date().isoformat(),
            end=last.date().isoformat(),
        ) as payload:
            for cik in identifiers:
                facts = self.company_facts(cik, refresh=refresh)
                acceptance = self.acceptance_timestamps(cik, refresh=refresh) if with_acceptance else None
                pit = to_point_in_time(
                    facts,
                    taxonomies=(taxonomy,),
                    tags=tuple(tags),
                    units=tuple(units) if units is not None else None,
                    acceptance=acceptance,
                    availability_lag_business_days=self.availability_lag_business_days,
                    calendar=self.calendar,
                )
                window = pit.loc[pit[filter_on].between(first, last)]
                pieces.append(window)
            panel = (pd.concat(pieces, ignore_index=True) if pieces else empty_pit_frame()).sort_values(
                [*PERIOD_KEY, "filing_date", "accession"], kind="stable", ignore_index=True
            )
            payload["rows"] = len(panel)

        self._last = {
            "ciks": tuple(identifiers),
            "tags": tuple(tags),
            "start": first.date(),
            "end": last.date(),
            "rows": len(panel),
            "retrieved_at": dt.datetime.now(dt.UTC),
        }
        return panel

    def fetch(self, *, start: dt.date, end: dt.date, **kwargs: Any) -> pd.DataFrame:
        """Rend le panel de fondamentaux, sous la signature du protocole ``DataProvider``.

        Args:
            start: première date de la fenêtre, incluse.
            end: dernière date de la fenêtre, incluse.
            **kwargs: ``ciks`` et ``tags`` sont exigés, les autres arguments
                sont ceux de :meth:`fundamentals_panel`.

        Raises:
            ValueError: si ``ciks`` ou ``tags`` manquent.
        """
        if "ciks" not in kwargs or "tags" not in kwargs:
            raise ValueError("fetch exige les arguments « ciks » et « tags »")
        ciks = kwargs.pop("ciks")
        tags = kwargs.pop("tags")
        return self.fundamentals_panel(ciks, tags, start, end, **kwargs)

    # ------------------------------------------------------- provenance --

    def manifest(self, **overrides: Any) -> DatasetManifest:
        """Rend la provenance du dernier panel construit, ou celle qu'on décrit.

        Trois champs portent la valeur de ce manifeste. ``point_in_time`` vaut
        vrai : chaque ligne porte sa date de dépôt et sa date d'utilisabilité.
        Le champ ``adjusted`` vaut faux, un chiffre comptable ne se corrigeant
        d'aucune action sur le capital.

        Le champ ``survivorship_free`` reste indéterminé, et c'est la réponse
        honnête. Les archives EDGAR gardent les dépôts des sociétés disparues,
        donc elles n'ont pas de biais de survie. Un univers bâti sur
        ``company_tickers.json`` en a un.

        Args:
            **overrides: décrit un panel sans en avoir construit un. Clés
                acceptées : ``ciks``, ``tags``, ``start``, ``end``, ``rows``.

        Raises:
            ConfigError: si aucun panel n'a été construit et que ``start`` et
                ``end`` manquent.
            ValueError: si une clé de remplacement est inconnue.
        """
        accepted = {"ciks", "tags", "start", "end", "rows", "retrieved_at"}
        unknown = sorted(set(overrides) - accepted)
        if unknown:
            raise ValueError(f"clés de manifeste inconnues : {unknown} ; acceptées : {sorted(accepted)}")

        base: dict[str, Any] = dict(self._last or {})
        base.update(overrides)
        for required in ("start", "end"):
            if required not in base:
                raise ConfigError("le manifeste exige un panel préalable, ou les clés start et end")

        ciks = tuple(str(c) for c in base.get("ciks", ()))
        tags = tuple(str(t) for t in base.get("tags", ()))
        return DatasetManifest(
            dataset_id=f"sec-fundamentals-{base['start']}-{base['end']}",
            source="SEC EDGAR, interface XBRL company facts",
            provider=self.name,
            url=f"{DATA_BASE_URL}/api/xbrl/companyfacts/",
            download_timestamp=base.get("retrieved_at") or dt.datetime.now(dt.UTC),
            data_start=base["start"],
            data_end=base["end"],
            frequency=Frequency.QUARTERLY,
            timezone="America/New_York",
            currency="USD",
            adjusted=False,
            point_in_time=True,
            survivorship_free=None,
            corporate_actions="aucun ajustement : un montant comptable n'en demande pas",
            revision_policy=REVISION_POLICY,
            license=LICENSE,
            license_url=LICENSE_URL,
            n_rows=int(base.get("rows", 0)),
            n_columns=len(PIT_SCHEMA),
            columns=PIT_SCHEMA,
            processing_version="1.0.0",
            layer=Layer.BRONZE,
            notes=(
                f"{AVAILABILITY_RULE}. Déposants : {len(ciks)}. Balises : {', '.join(tags) or 'aucune'}. "
                f"Limites connues : {len(KNOWN_LIMITATIONS)}, voir sec.KNOWN_LIMITATIONS."
            ),
        )
