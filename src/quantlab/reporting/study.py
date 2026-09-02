r"""Le rapport d'étude, et le verdict qui se déduit au lieu de se choisir.

**Le problème.** Un backtest rend toujours un chiffre. Rien dans ce chiffre ne
dit s'il décrit un mécanisme ou le bruit de l'échantillon. La décision de
publier, de garder ou de jeter se prend donc au jugé, et le jugé penche
toujours du côté du résultat qu'on vient de trouver.

**Le remède.** Une échelle de cinq verdicts, des seuils écrits avant de voir
les résultats, et une fonction qui applique les seuils sans rien interpréter.
Le chercheur choisit les seuils, dans :class:`VerdictCriteria`, une fois pour
toutes. Il ne choisit jamais le verdict.

**Ce que le module refuse explicitement.** Un ratio de Sharpe supérieur à 1 ne
suffit à aucun niveau de l'échelle. Aucun seuil de Sharpe, si haut soit-il, ne
donne à lui seul un verdict. Un Sharpe de 3 dans l'échantillon
d'entraînement, sans réplication et sans contrôle de surapprentissage, reste
au niveau ``EXPERIMENTAL``.

**L'échelle, et sa stricte progression.** Les cinq verdicts sont ordonnés, et
chaque niveau exige tous les précédents.

.. math::

    \text{REJECTED} \prec \text{EXPERIMENTAL} \prec \text{REPLICATED}
    \prec \text{ROBUST} \prec \text{PORTFOLIO\_CANDIDATE}

**La sortie double.** :func:`decide_verdict` rend le verdict et la liste des
raisons. Un verdict sans ses raisons ne se publie pas, parce qu'un lecteur qui
ne voit pas la valeur mesurée en face du seuil n'a aucun moyen de contester.

**Provenance des seuils par défaut.** Trois viennent de la littérature. Le t de
Student minimal après correction pour essais multiples vient de Harvey, Liu et
Zhu (2016), *Review of Financial Studies* 29(1), pages 5 à 68. Le seuil du
ratio de Sharpe dégonflé vient de Bailey et Lopez de Prado (2014), *Journal of
Portfolio Management* 40(5), pages 94 à 107. Le seuil de la probabilité de
surapprentissage vient de Bailey, Borwein, Lopez de Prado et Zhu (2017),
*Journal of Computational Finance* 20(4), pages 39 à 69. Les cinq autres sont
des PRÉCEPTES de ce laboratoire, déclarés comme tels et révisables.

**Les limites.** Un verdict reste conditionnel aux contrôles qui ont tourné.
Une étude qui n'a mesuré ni le hors échantillon ni les coûts ne peut pas
dépasser ``EXPERIMENTAL``, et c'est voulu. Le module ne sait pas si les
contrôles ont été conduits honnêtement, il sait seulement s'ils existent.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml
from pydantic import Field

from quantlab.core.config import StrictModel
from quantlab.core.errors import ConfigError
from quantlab.core.logging import get_logger
from quantlab.core.paths import ensure
from quantlab.core.types import CostBasis, SampleTag, Verdict

__all__ = [
    "DEFAULT_MAX_PBO",
    "DEFAULT_MAX_PORTFOLIO_CORRELATION",
    "DEFAULT_MIN_COST_MULTIPLE",
    "DEFAULT_MIN_DSR",
    "DEFAULT_MIN_OOS_SHARPE",
    "DEFAULT_MIN_POSITIVE_SUBPERIOD_SHARE",
    "DEFAULT_MIN_TSTAT",
    "DEFAULT_REPLICATION_TOLERANCE",
    "REJECTION_OOS_SHARPE",
    "REPORT_SECTIONS",
    "VERDICT_LADDER",
    "MetricLabel",
    "ReplicationCheck",
    "ReportFigure",
    "ReportTable",
    "StudyReport",
    "VerdictCriteria",
    "VerdictEvidence",
    "decide_verdict",
    "generate_report",
    "metrics_table",
    "replication_table",
    "section_keys",
]

_LOG = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Les seuils par défaut, chacun avec son statut
# --------------------------------------------------------------------------- #

#: Tolérance relative par défaut d'un contrôle de réplication, soit 10 %.
#: PRÉCEPTE de ce laboratoire. Une réplication qui retrouve un Sharpe publié de
#: 0,80 à 0,74 près reste une réplication ; à 0,60 près, non.
DEFAULT_REPLICATION_TOLERANCE = 0.10

#: Ratio de Sharpe hors échantillon minimal, annualisé. PRÉCEPTE.
#: Le chiffre est bas volontairement : il écarte le néant, pas la médiocrité.
DEFAULT_MIN_OOS_SHARPE = 0.5

#: Statistique t minimale après correction pour essais multiples. RAPPORTÉ de
#: Harvey, Liu et Zhu (2016). Leur recommandation est 3,0 contre les 1,96
#: usuels, parce que des centaines de facteurs ont été essayés avant celui-ci.
DEFAULT_MIN_TSTAT = 3.0

#: Ratio de Sharpe dégonflé minimal, une probabilité. RAPPORTÉ de Bailey et
#: Lopez de Prado (2014), qui retiennent 0,95 comme seuil de publication.
DEFAULT_MIN_DSR = 0.95

#: Probabilité de surapprentissage maximale. RAPPORTÉ de Bailey, Borwein,
#: Lopez de Prado et Zhu (2017). Au-delà de 0,5, la configuration retenue fait
#: pire hors échantillon que la médiane du tirage au sort.
DEFAULT_MAX_PBO = 0.5

#: Part minimale de sous-périodes à performance positive. PRÉCEPTE. Une
#: stratégie qui gagne dans deux sous-périodes sur trois ne dépend pas d'un
#: seul épisode de marché.
DEFAULT_MIN_POSITIVE_SUBPERIOD_SHARE = 0.60

#: Multiple de coûts auquel la stratégie doit encore survivre. PRÉCEPTE. Le
#: multiple 2 signifie que doubler les frais estimés laisse la performance
#: nette positive.
DEFAULT_MIN_COST_MULTIPLE = 2.0

#: Corrélation maximale avec le portefeuille existant, en valeur absolue.
#: PRÉCEPTE. Au-delà, la stratégie répète ce qui est déjà détenu.
DEFAULT_MAX_PORTFOLIO_CORRELATION = 0.60

#: Le seuil de rejet sur le ratio de Sharpe hors échantillon. Un Sharpe hors
#: échantillon négatif ou nul réfute l'hypothèse plutôt que de la laisser en
#: attente, donc il rend le verdict ``REJECTED`` et non ``EXPERIMENTAL``.
REJECTION_OOS_SHARPE = 0.0

#: La marge d'arrondi de la comparaison d'un écart à sa tolérance. MESURÉ :
#: un écart mathématiquement égal à 10 % tombe des deux côtés selon les
#: décimales qui l'ont produit. La paire 0,80 contre 0,72 rend
#: 0,10000000000000009 et la paire 2,0 contre 1,8 rend 0,09999999999999998.
#: Sans marge, la première échoue et la seconde passe, à tolérance égale et à
#: écart vrai égal. La marge relative de 1e-12 les fait passer toutes deux, et
#: elle reste sous le millième de point de base, donc elle ne peut sauver
#: aucun écart réel.
_MARGE_ARRONDI = 1e-12

#: L'échelle des verdicts, du plus bas au plus haut.
VERDICT_LADDER: tuple[Verdict, ...] = (
    Verdict.REJECTED,
    Verdict.EXPERIMENTAL,
    Verdict.REPLICATED,
    Verdict.ROBUST,
    Verdict.PORTFOLIO_CANDIDATE,
)

#: Les quinze sections du rapport, dans l'ordre imposé. La clé est un
#: identifiant anglais stable, le titre est la prose française affichée.
REPORT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("hypothesis", "L'hypothèse"),
    ("paper", "L'article"),
    ("methodology", "La méthodologie"),
    ("data", "Les données"),
    ("implementation", "L'implémentation"),
    ("assumptions", "Les hypothèses"),
    ("replication", "La réplication"),
    ("performance", "La performance"),
    ("costs", "Les coûts"),
    ("robustness", "La robustesse"),
    ("out_of_sample", "Le hors échantillon"),
    ("statistical_tests", "Les tests statistiques"),
    ("factor_attribution", "L'attribution factorielle"),
    ("limitations", "Les limites"),
    ("verdict", "Le verdict"),
)

#: Les marques de succès et d'échec qui ouvrent chaque raison.
_PASS = "RÉUSSI"
_FAIL = "ÉCHOUÉ"

#: Le texte employé quand une grandeur n'a pas été mesurée.
_NON_MESURE = "non mesuré"

#: Les noms des fichiers écrits par :func:`generate_report`.
_FICHIER_HTML = "report.html"
_FICHIER_METRIQUES = "metrics.json"
_FICHIER_CONFIG = "config.yaml"
_FICHIER_MANIFESTE = "data_manifest.json"
_DOSSIER_FIGURES = "figures"
_DOSSIER_TABLEAUX = "tables"


def section_keys() -> tuple[str, ...]:
    """Rend les quinze clés de section, dans l'ordre du rapport.

    Returns:
        Le tuple des identifiants de section, de ``hypothesis`` à ``verdict``.
    """
    return tuple(cle for cle, _ in REPORT_SECTIONS)


# --------------------------------------------------------------------------- #
# Le formatage des nombres dans les raisons
# --------------------------------------------------------------------------- #


def _fr(valeur: float | None, decimales: int = 3) -> str:
    """Rend un nombre en français, virgule décimale, ou la mention d'absence."""
    if valeur is None:
        return _NON_MESURE
    if isinstance(valeur, float) and math.isnan(valeur):
        return _NON_MESURE
    return f"{valeur:.{decimales}f}".replace(".", ",")


def _raison(reussi: bool, libelle: str, mesure: str, seuil: str) -> str:
    """Assemble une raison lisible : marque, libellé, mesure, seuil."""
    marque = _PASS if reussi else _FAIL
    return f"{marque} | {libelle} : {mesure}, {seuil}"


def _mesure_texte(valeur: float | None, participe: str = "mesuré") -> str:
    """Rend « 0,700 mesuré », ou la seule mention d'absence si rien n'existe.

    Sans cette fonction, une grandeur absente s'écrirait « non mesuré mesuré ».
    """
    if valeur is None or (isinstance(valeur, float) and math.isnan(valeur)):
        return _NON_MESURE
    return f"{_fr(valeur)} {participe}"


# --------------------------------------------------------------------------- #
# Les contrôles de réplication
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ReplicationCheck:
    r"""Un contrôle chiffré de notre résultat contre une valeur publiée.

    **Le problème.** « Nous répliquons Moskowitz, Ooi et Pedersen (2012) » est
    une affirmation invérifiable tant qu'aucun nombre de l'article n'est mis en
    face d'un nombre à nous. Un contrôle de réplication est ce couple de
    nombres, plus la tolérance déclarée avant la comparaison.

    **L'intuition.** Deux implémentations d'une même méthode ne rendent jamais
    le même chiffre au dernier décimal. Les données diffèrent, les conventions
    de calendrier diffèrent, l'arrondi diffère. La question n'est donc pas
    l'égalité, elle est la distance, mesurée contre une tolérance fixée avant.

    **La formule.** L'écart absolu et l'écart relatif s'écrivent

    .. math::

        e_{abs} = \left| x_{nous} - x_{papier} \right|, \qquad
        e_{rel} = \frac{\left| x_{nous} - x_{papier} \right|}{\left| x_{papier} \right|}

    où :math:`x_{papier}` est la valeur imprimée dans l'article et
    :math:`x_{nous}` la valeur rendue par notre code.

    **Les hypothèses.** La valeur publiée est lue sans erreur de transcription,
    et les deux nombres mesurent la même grandeur sur la même période. Ces deux
    hypothèses sont les sources d'erreur les plus fréquentes, et aucune n'est
    vérifiable par le code.

    **Les limites.** L'écart relatif n'a pas de sens quand la valeur publiée
    vaut zéro. Dans ce cas, la tolérance doit être déclarée absolue, sans quoi
    l'écart relatif vaut l'infini et le contrôle échoue toujours.

    **Une alternative écartée.** Un test statistique d'égalité entre les deux
    chiffres demanderait l'erreur type de la valeur publiée, que les articles
    ne donnent presque jamais pour les grandeurs dérivées.

    **Comment vérifier l'implémentation.** Poser une valeur publiée de 0,80 et
    une valeur à nous de 0,74. L'écart absolu vaut 0,06 et l'écart relatif
    0,075, donc le contrôle passe à 10 % de tolérance et échoue à 5 %.

    Attributes:
        quantity: la grandeur comparée, nommée comme dans l'article.
        published: la valeur imprimée dans l'article.
        ours: la valeur rendue par notre code.
        tolerance: la tolérance déclarée, relative ou absolue.
        tolerance_kind: ``« relative »`` ou ``« absolute »``.
        source: la citation exacte, table et page quand elles existent.
        note: toute réserve utile, en français.
    """

    quantity: str
    published: float
    ours: float
    tolerance: float = DEFAULT_REPLICATION_TOLERANCE
    tolerance_kind: Literal["relative", "absolute"] = "relative"
    source: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        """Refuse une tolérance négative et un nom de grandeur vide."""
        if not self.quantity.strip():
            raise ConfigError("un contrôle de réplication porte le nom de la grandeur comparée.")
        if self.tolerance < 0.0:
            raise ConfigError(f"tolérance négative pour « {self.quantity} » : {self.tolerance}.")

    @property
    def absolute_error(self) -> float:
        """L'écart absolu entre notre valeur et la valeur publiée."""
        return abs(self.ours - self.published)

    @property
    def relative_error(self) -> float:
        """L'écart relatif, ou l'infini quand la valeur publiée vaut zéro."""
        if self.published == 0.0:
            return math.inf
        return self.absolute_error / abs(self.published)

    @property
    def error(self) -> float:
        """L'écart qui sert au verdict, selon le genre de tolérance déclaré."""
        return self.relative_error if self.tolerance_kind == "relative" else self.absolute_error

    @property
    def passed(self) -> bool:
        """Dit si l'écart retenu tient dans la tolérance déclarée.

        La comparaison porte une marge d'arrondi relative,
        :data:`_MARGE_ARRONDI`, sans laquelle un écart mathématiquement égal à
        la tolérance passe ou échoue selon les décimales qui l'ont produit.
        Une tolérance nulle reste une tolérance nulle, la marge étant
        multiplicative.
        """
        return bool(self.error <= self.tolerance * (1.0 + _MARGE_ARRONDI))

    @property
    def verdict(self) -> str:
        """Rend ``« répliqué »`` ou ``« écart »``, pour le tableau papier."""
        return "répliqué" if self.passed else "écart"

    def as_row(self) -> dict[str, Any]:
        """Rend le contrôle sous forme de ligne de tableau.

        Returns:
            Un dictionnaire à neuf clés, prêt pour :func:`replication_table`.
        """
        return {
            "quantity": self.quantity,
            "published": self.published,
            "ours": self.ours,
            "absolute_error": self.absolute_error,
            "relative_error": self.relative_error,
            "tolerance": self.tolerance,
            "tolerance_kind": self.tolerance_kind,
            "verdict": self.verdict,
            "source": self.source,
        }


#: Les colonnes du tableau papier contre réplication, dans cet ordre.
_COLONNES_REPLICATION = (
    "quantity",
    "published",
    "ours",
    "absolute_error",
    "relative_error",
    "tolerance",
    "tolerance_kind",
    "verdict",
    "source",
)


def replication_table(checks: Sequence[ReplicationCheck]) -> pd.DataFrame:
    """Rend le tableau papier contre réplication du portefeuille.

    Ce tableau est la pièce que le lecteur regarde en premier. Il porte, pour
    chaque grandeur, le chiffre de l'article, le nôtre, les deux écarts, la
    tolérance et le verdict de la ligne.

    Args:
        checks: les contrôles, dans l'ordre où ils doivent apparaître.

    Returns:
        Un tableau à neuf colonnes. Une suite vide rend un tableau vide qui
        porte quand même ses colonnes, pour que le rapport reste écrivable.

    Example:
        >>> t = replication_table([ReplicationCheck("Sharpe", 0.80, 0.74)])
        >>> round(float(t.loc[0, "relative_error"]), 4)
        0.075
    """
    lignes = [c.as_row() for c in checks]
    if not lignes:
        return pd.DataFrame({nom: pd.Series(dtype="object") for nom in _COLONNES_REPLICATION})
    return pd.DataFrame(lignes, columns=list(_COLONNES_REPLICATION))


# --------------------------------------------------------------------------- #
# Les seuils, et les preuves
# --------------------------------------------------------------------------- #


class VerdictCriteria(StrictModel):
    """Les seuils qui décident du verdict, tous déclarés et configurables.

    **Pourquoi un modèle gelé.** Un seuil qui bouge après avoir vu le résultat
    n'est plus un seuil. Le modèle est gelé et refuse toute clé inconnue, donc
    une faute de frappe lève à la construction au lieu de passer pour une
    valeur par défaut.

    **Où ces seuils vivent.** Dans la configuration de l'étude, versionnée,
    donc lisible dans une revue de code avant que les résultats existent.

    Attributes:
        replication_tolerance: tolérance relative des contrôles de réplication.
        min_oos_sharpe: ratio de Sharpe hors échantillon minimal, annualisé.
        min_tstat: statistique t minimale après correction pour essais
            multiples.
        min_dsr: ratio de Sharpe dégonflé minimal, une probabilité.
        max_pbo: probabilité de surapprentissage maximale.
        min_positive_subperiod_share: part minimale de sous-périodes positives.
        min_cost_multiple: multiple de coûts auquel la stratégie survit encore.
        max_portfolio_correlation: corrélation maximale, en valeur absolue,
            avec le portefeuille déjà détenu.
    """

    replication_tolerance: float = Field(
        default=DEFAULT_REPLICATION_TOLERANCE,
        ge=0.0,
        description="Tolérance relative maximale acceptée d'un contrôle de réplication.",
    )
    min_oos_sharpe: float = Field(
        default=DEFAULT_MIN_OOS_SHARPE,
        description="Ratio de Sharpe hors échantillon minimal, annualisé.",
    )
    min_tstat: float = Field(
        default=DEFAULT_MIN_TSTAT,
        description="Statistique t minimale après correction pour essais multiples.",
    )
    min_dsr: float = Field(
        default=DEFAULT_MIN_DSR,
        ge=0.0,
        le=1.0,
        description="Ratio de Sharpe dégonflé minimal, une probabilité.",
    )
    max_pbo: float = Field(
        default=DEFAULT_MAX_PBO,
        ge=0.0,
        le=1.0,
        description="Probabilité de surapprentissage maximale acceptée.",
    )
    min_positive_subperiod_share: float = Field(
        default=DEFAULT_MIN_POSITIVE_SUBPERIOD_SHARE,
        ge=0.0,
        le=1.0,
        description="Part minimale de sous-périodes à performance positive.",
    )
    min_cost_multiple: float = Field(
        default=DEFAULT_MIN_COST_MULTIPLE,
        ge=0.0,
        description="Multiple des coûts estimés auquel la stratégie reste rentable.",
    )
    max_portfolio_correlation: float = Field(
        default=DEFAULT_MAX_PORTFOLIO_CORRELATION,
        ge=0.0,
        le=1.0,
        description="Corrélation absolue maximale avec le portefeuille existant.",
    )


@dataclass(frozen=True)
class VerdictEvidence:
    """Les preuves mesurées d'une étude, face auxquelles les seuils s'appliquent.

    Chaque champ vaut ``None`` tant que le contrôle correspondant n'a pas
    tourné. Une preuve absente fait échouer son critère, elle ne le laisse pas
    passer par défaut. C'est la règle qui empêche une étude incomplète
    d'atteindre un verdict élevé faute de mesure contraire.

    Attributes:
        hypothesis_supported: le signe économique attendu est-il retrouvé.
        replication_checks: les contrôles chiffrés contre l'article.
        oos_sharpe: le ratio de Sharpe hors échantillon, annualisé.
        tstat_after_multiplicity: le t après correction pour essais multiples.
        deflated_sharpe: le ratio de Sharpe dégonflé, entre 0 et 1.
        pbo: la probabilité de surapprentissage, entre 0 et 1.
        positive_subperiod_share: la part de sous-périodes positives.
        surviving_cost_multiple: le plus grand multiple de coûts survécu.
        portfolio_correlation: la corrélation avec le portefeuille existant.
        notes: les réserves du chercheur, reproduites telles quelles.
    """

    hypothesis_supported: bool = True
    replication_checks: tuple[ReplicationCheck, ...] = ()
    oos_sharpe: float | None = None
    tstat_after_multiplicity: float | None = None
    deflated_sharpe: float | None = None
    pbo: float | None = None
    positive_subperiod_share: float | None = None
    surviving_cost_multiple: float | None = None
    portfolio_correlation: float | None = None
    notes: str = ""


def _mesure_atteint(valeur: float | None, seuil: float, sens: Literal["min", "max"]) -> bool:
    """Dit si une mesure atteint son seuil, une absence valant échec."""
    if valeur is None or math.isnan(valeur):
        return False
    return valeur >= seuil if sens == "min" else valeur <= seuil


def _raisons_de_rejet(evidence: VerdictEvidence) -> tuple[bool, list[str]]:
    """Rend l'état de non-rejet et les deux raisons qui le fondent."""
    raisons: list[str] = []
    signe = bool(evidence.hypothesis_supported)
    raisons.append(
        _raison(
            signe,
            "hypothèse économique",
            "signe attendu retrouvé" if signe else "signe attendu NON retrouvé",
            "le signe décide du rejet",
        )
    )
    sharpe = evidence.oos_sharpe
    sharpe_refute = sharpe is not None and not math.isnan(sharpe) and sharpe <= REJECTION_OOS_SHARPE
    raisons.append(
        _raison(
            not sharpe_refute,
            "signe du Sharpe hors échantillon",
            _mesure_texte(sharpe),
            f"rejet à {_fr(REJECTION_OOS_SHARPE)} ou moins",
        )
    )
    return (signe and not sharpe_refute), raisons


def _tolerance_relative_equivalente(check: ReplicationCheck) -> float | None:
    r"""Rend la tolérance d'un contrôle exprimée en relatif, ou ``None``.

    **Le problème.** Une tolérance absolue et une tolérance relative se
    comparent seulement après conversion. Sans conversion, une tolérance
    absolue échappe à la tolérance déclarée de l'étude, et le contrôle passe
    quel que soit l'écart.

    **La formule.** Une tolérance absolue :math:`t_{abs}` équivaut à la
    tolérance relative

    .. math::

        t_{rel} = \frac{t_{abs}}{\left| x_{papier} \right|}

    parce que la condition :math:`\left| x_{nous} - x_{papier} \right| \le
    t_{abs}` s'écrit aussi :math:`e_{rel} \le t_{abs} / \left| x_{papier}
    \right|`.

    **La limite.** À valeur publiée nulle, le quotient n'existe pas et la
    fonction rend ``None``. Ce cas ne se compare donc à aucune tolérance
    relative, et la raison du verdict le signale au lecteur.

    Args:
        check: le contrôle dont la tolérance se convertit.

    Returns:
        La tolérance en relatif, ou ``None`` si la valeur publiée vaut zéro.
    """
    if check.tolerance_kind == "relative":
        return check.tolerance
    if check.published == 0.0:
        return None
    return check.tolerance / abs(check.published)


def _raisons_de_replication(evidence: VerdictEvidence, criteria: VerdictCriteria) -> tuple[bool, list[str]]:
    """Rend l'état de réplication et une raison par contrôle, plus la synthèse."""
    raisons: list[str] = []
    checks = tuple(evidence.replication_checks)
    if not checks:
        raisons.append(
            _raison(
                False,
                "réplication",
                "aucun contrôle chiffré fourni",
                f"tolérance déclarée {_fr(criteria.replication_tolerance)}",
            )
        )
        return False, raisons

    conformes = 0
    for check in checks:
        equivalente = _tolerance_relative_equivalente(check)
        plafond = criteria.replication_tolerance * (1.0 + _MARGE_ARRONDI)
        trop_large = equivalente is not None and equivalente > plafond
        reussi = check.passed and not trop_large
        conformes += int(reussi)
        detail = f"{_fr(check.ours)} contre {_fr(check.published)} publié"
        ecart = f"écart relatif {_fr(check.relative_error)}"
        seuil = f"tolérance {_fr(check.tolerance)} ({check.tolerance_kind})"
        if check.tolerance_kind == "absolute":
            seuil += (
                f", soit {_fr(equivalente)} en relatif"
                if equivalente is not None
                else ", sans équivalent relatif car la valeur publiée est nulle"
            )
        if trop_large:
            seuil += f", plus large que la tolérance déclarée {_fr(criteria.replication_tolerance)}"
        raisons.append(_raison(reussi, f"réplication de « {check.quantity} »", f"{detail}, {ecart}", seuil))

    total = len(checks)
    tous = conformes == total
    raisons.append(
        _raison(
            tous,
            "réplication",
            f"{conformes} contrôle(s) sur {total} dans la tolérance",
            "tous exigés",
        )
    )
    return tous, raisons


def _raisons_de_robustesse(evidence: VerdictEvidence, criteria: VerdictCriteria) -> tuple[bool, list[str]]:
    """Rend l'état de robustesse et les six raisons, une par critère."""
    controles: tuple[tuple[str, float | None, float, Literal["min", "max"]], ...] = (
        ("Sharpe hors échantillon", evidence.oos_sharpe, criteria.min_oos_sharpe, "min"),
        (
            "t après correction pour essais multiples",
            evidence.tstat_after_multiplicity,
            criteria.min_tstat,
            "min",
        ),
        ("Sharpe dégonflé", evidence.deflated_sharpe, criteria.min_dsr, "min"),
        ("probabilité de surapprentissage", evidence.pbo, criteria.max_pbo, "max"),
        (
            "part de sous-périodes positives",
            evidence.positive_subperiod_share,
            criteria.min_positive_subperiod_share,
            "min",
        ),
        (
            "multiple de coûts survécu",
            evidence.surviving_cost_multiple,
            criteria.min_cost_multiple,
            "min",
        ),
    )
    raisons: list[str] = []
    tous = True
    for libelle, valeur, seuil, sens in controles:
        reussi = _mesure_atteint(valeur, seuil, sens)
        tous = tous and reussi
        mot = "minimum" if sens == "min" else "maximum"
        raisons.append(_raison(reussi, libelle, _mesure_texte(valeur), f"{mot} {_fr(seuil)}"))
    return tous, raisons


def _raison_d_apport(evidence: VerdictEvidence, criteria: VerdictCriteria) -> tuple[bool, str]:
    """Rend l'état de l'apport au portefeuille et la raison correspondante."""
    correlation = evidence.portfolio_correlation
    absolue = None if correlation is None or math.isnan(correlation) else abs(correlation)
    reussi = _mesure_atteint(absolue, criteria.max_portfolio_correlation, "max")
    return reussi, _raison(
        reussi,
        "corrélation absolue avec le portefeuille existant",
        _mesure_texte(absolue, "mesurée"),
        f"maximum {_fr(criteria.max_portfolio_correlation)}",
    )


def decide_verdict(
    evidence: VerdictEvidence, criteria: VerdictCriteria | None = None
) -> tuple[Verdict, list[str]]:
    r"""Déduit le verdict d'une étude, et rend les raisons qui le fondent.

    **Le problème.** Le verdict d'une étude se choisit d'ordinaire après avoir
    vu les résultats, ce qui garantit qu'il leur ressemble. Une stratégie
    décevante devient « prometteuse », une stratégie flatteuse devient
    « robuste », et le mot ne porte plus d'information.

    **L'intuition.** Séparer le moment où l'on fixe les seuils du moment où
    l'on regarde les mesures. Les seuils vivent dans
    :class:`VerdictCriteria`, écrits dans la configuration de l'étude. Cette
    fonction ne fait qu'appliquer une comparaison, sans interprétation.

    **La règle, en une formule.** Soit :math:`C_1` à :math:`C_4` les quatre
    groupes de critères, du plus bas au plus haut. Le verdict retenu est le
    plus haut niveau dont tous les groupes précédents sont satisfaits :

    .. math::

        V = \max \left\{ v \in \{1, \ldots, 5\} \;:\;
        \forall\, u < v, \; C_u = \text{vrai} \right\}

    où :math:`C_1` interdit le rejet, :math:`C_2` exige la réplication,
    :math:`C_3` exige les six contrôles de robustesse et :math:`C_4` exige
    l'apport au portefeuille.

    **Les variables.** Le groupe :math:`C_1` porte le signe économique attendu
    et le signe du Sharpe hors échantillon. Le groupe :math:`C_2` porte les
    contrôles de :class:`ReplicationCheck`. Le groupe :math:`C_3` porte le
    Sharpe hors échantillon, le t corrigé, le Sharpe dégonflé, la probabilité
    de surapprentissage, la part de sous-périodes positives et le multiple de
    coûts. Le groupe :math:`C_4` porte la corrélation au portefeuille détenu.

    **Les hypothèses.** Une preuve absente vaut échec de son critère. Les
    seuils sont fixés avant de voir les résultats. Les mesures fournies portent
    bien sur l'échantillon qu'elles prétendent décrire, ce que le code ne peut
    pas vérifier.

    **Ce que la fonction refuse.** Un ratio de Sharpe supérieur à 1 ne suffit à
    aucun niveau de l'échelle. Il n'existe dans ce laboratoire aucun seuil de
    Sharpe qui donnerait seul un verdict, si haut soit-il. Une stratégie de
    Sharpe 3 sans contrôle de réplication reste ``EXPERIMENTAL``.

    **Les limites.** La progression est stricte, donc une étude sans article de
    référence ne peut pas dépasser ``EXPERIMENTAL``, même parfaitement conduite.
    C'est un choix du laboratoire, qui vise la réplication. Une recherche
    propre, sans papier de référence, appelle un autre jeu de critères.

    **Une alternative écartée.** Un score continu, moyenne pondérée des huit
    critères, permettrait à un excellent Sharpe de compenser une probabilité de
    surapprentissage élevée. C'est exactement la compensation que l'échelle
    interdit, donc le score est écarté.

    **Comment vérifier l'implémentation.** Construire une preuve qui satisfait
    tous les critères sauf la corrélation, et vérifier que le verdict est
    ``ROBUST`` et non ``PORTFOLIO_CANDIDATE``. Puis relâcher la corrélation
    seule, et vérifier le passage à ``PORTFOLIO_CANDIDATE``.

    Args:
        evidence: les grandeurs mesurées par l'étude.
        criteria: les seuils. Les seuils par défaut du laboratoire sinon.

    Returns:
        Le couple ``(verdict, raisons)``. La liste des raisons porte une ligne
        par critère, avec la valeur mesurée en face du seuil, et elle est
        rendue en entier quel que soit le verdict.

    Example:
        >>> v, r = decide_verdict(VerdictEvidence(hypothesis_supported=False))
        >>> v is Verdict.REJECTED
        True
        >>> r[0].startswith("ÉCHOUÉ")
        True
    """
    seuils = criteria if criteria is not None else VerdictCriteria()

    non_rejete, raisons_rejet = _raisons_de_rejet(evidence)
    replique, raisons_replication = _raisons_de_replication(evidence, seuils)
    robuste, raisons_robustesse = _raisons_de_robustesse(evidence, seuils)
    apporte, raison_apport = _raison_d_apport(evidence, seuils)

    raisons = [*raisons_rejet, *raisons_replication, *raisons_robustesse, raison_apport]

    if not non_rejete:
        verdict = Verdict.REJECTED
    elif not replique:
        verdict = Verdict.EXPERIMENTAL
    elif not robuste:
        verdict = Verdict.REPLICATED
    elif not apporte:
        verdict = Verdict.ROBUST
    else:
        verdict = Verdict.PORTFOLIO_CANDIDATE

    raisons.append(f"VERDICT | {verdict.value}")
    return verdict, raisons


# --------------------------------------------------------------------------- #
# Le tableau des métriques
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MetricLabel:
    """L'étiquette obligatoire d'une métrique publiée.

    Un ratio de Sharpe sans échantillon ni base de coût est un nombre sans
    signification. Le même 1,20 vaut une découverte hors échantillon, net de
    frais, et rien du tout dans l'échantillon d'entraînement, brut de frais.

    Attributes:
        sample: l'échantillon dont la métrique sort.
        cost_basis: la performance est brute ou nette de frais.
    """

    sample: SampleTag
    cost_basis: CostBasis


#: Les colonnes du tableau des métriques, dans cet ordre.
_COLONNES_METRIQUES = ("metric", "value", "sample", "cost_basis")


def _normaliser_etiquette(nom: str, brute: object) -> MetricLabel:
    """Rend une :class:`MetricLabel` depuis un couple ou une étiquette."""
    if isinstance(brute, MetricLabel):
        return brute
    if isinstance(brute, tuple | list) and len(brute) == 2:
        return MetricLabel(sample=SampleTag(brute[0]), cost_basis=CostBasis(brute[1]))
    raise ConfigError(
        f"la métrique « {nom} » porte une étiquette illisible : "
        "il faut une MetricLabel ou un couple (SampleTag, CostBasis)."
    )


def metrics_table(
    result: Mapping[str, float],
    samples: Mapping[str, MetricLabel | tuple[SampleTag, CostBasis]],
) -> pd.DataFrame:
    """Rend le tableau des métriques, chacune avec son échantillon et sa base.

    **La règle appliquée.** Une métrique sans étiquette d'échantillon ou sans
    base de coût ne s'écrit pas. La fonction lève plutôt que d'écrire une ligne
    incomplète, parce qu'un tableau où deux lignes sur dix manquent de leur
    étiquette est plus dangereux qu'un tableau absent.

    **La symétrie du contrôle.** Une étiquette déclarée pour une métrique
    absente lève aussi. C'est le cas d'une faute de frappe dans un nom, qui
    laisserait la vraie métrique sans étiquette et l'étiquette sans métrique.

    Args:
        result: les métriques, nom vers valeur.
        samples: les étiquettes, nom vers :class:`MetricLabel` ou couple
            ``(SampleTag, CostBasis)``.

    Returns:
        Un tableau à quatre colonnes : ``metric``, ``value``, ``sample`` et
        ``cost_basis``. Les lignes suivent l'ordre de ``result``.

    Raises:
        ConfigError: si une métrique n'a pas d'étiquette, si une étiquette n'a
            pas de métrique, ou si une étiquette est illisible.

    Example:
        >>> t = metrics_table(
        ...     {"sharpe": 1.2},
        ...     {"sharpe": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET)},
        ... )
        >>> list(t.columns)
        ['metric', 'value', 'sample', 'cost_basis']
    """
    manquantes = [nom for nom in result if nom not in samples]
    if manquantes:
        raise ConfigError(
            "ces métriques n'ont ni étiquette d'échantillon ni base de coût, "
            f"donc elles ne s'écrivent pas : {sorted(manquantes)}."
        )
    orphelines = [nom for nom in samples if nom not in result]
    if orphelines:
        raise ConfigError(f"ces étiquettes ne correspondent à aucune métrique : {sorted(orphelines)}.")

    lignes: list[dict[str, Any]] = []
    for nom, valeur in result.items():
        etiquette = _normaliser_etiquette(nom, samples[nom])
        lignes.append(
            {
                "metric": nom,
                "value": float(valeur),
                "sample": etiquette.sample.value,
                "cost_basis": etiquette.cost_basis.value,
            }
        )
    if not lignes:
        return pd.DataFrame({nom: pd.Series(dtype="object") for nom in _COLONNES_METRIQUES})
    return pd.DataFrame(lignes, columns=list(_COLONNES_METRIQUES))


# --------------------------------------------------------------------------- #
# Le rapport
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ReportFigure:
    """Une figure du rapport, rattachée à sa section.

    Attributes:
        name: le nom du fichier écrit sous ``figures/``, sans extension.
        section: la clé de section où la figure apparaît.
        path: le fichier image source, déjà écrit sur disque.
        caption: la légende, qui dit ce que la figure montre.
    """

    name: str
    section: str
    path: Path
    caption: str = ""


@dataclass(frozen=True, eq=False)
class ReportTable:
    """Un tableau du rapport, rattaché à sa section.

    L'égalité automatique est retirée : comparer deux tableaux pandas avec
    ``==`` rend un tableau de booléens et non un booléen, ce qui casserait
    l'égalité de la classe.

    Attributes:
        name: le nom du fichier écrit sous ``tables/``, sans extension.
        section: la clé de section où le tableau apparaît.
        frame: le contenu.
        caption: la légende, qui dit comment lire le tableau.
    """

    name: str
    section: str
    frame: pd.DataFrame
    caption: str = ""


@dataclass(frozen=True, eq=False)
class StudyReport:
    """Tout ce qu'une étude produit, réuni en un seul objet gelé.

    **Pourquoi un objet unique.** Le rapport, les métriques, la configuration
    et les manifestes de données doivent voyager ensemble. Séparés, ils
    divergent : le rapport cite un chiffre que la configuration ne produit
    plus, et personne ne s'en aperçoit.

    **Pourquoi gelé.** Un rapport qu'on modifie après l'avoir écrit n'est plus
    la trace de ce qui a tourné. L'égalité automatique est retirée pour la
    raison exposée dans :class:`ReportTable`.

    Attributes:
        study_name: le nom de l'étude, employé dans le chemin de sortie.
        experiment_id: l'identifiant d'expérience, employé dans le chemin.
        hypothesis: l'hypothèse économique, en une phrase.
        paper: la citation complète de l'article répliqué.
        criteria: les seuils de verdict retenus.
        evidence: les grandeurs mesurées.
        sections: la prose de chaque section, par clé de section.
        metrics: le tableau rendu par :func:`metrics_table`.
        tables: les tableaux joints.
        figures: les figures jointes.
        config: la configuration de l'étude, écrite en YAML.
        dataset_manifests: les manifestes des jeux de données employés.
        created_at: l'instant de construction du rapport, en UTC.
    """

    study_name: str
    experiment_id: str
    hypothesis: str
    paper: str
    criteria: VerdictCriteria = field(default_factory=VerdictCriteria)
    evidence: VerdictEvidence = field(default_factory=VerdictEvidence)
    sections: Mapping[str, str] = field(default_factory=dict)
    metrics: pd.DataFrame | None = None
    tables: Sequence[ReportTable] = ()
    figures: Sequence[ReportFigure] = ()
    config: Mapping[str, Any] = field(default_factory=dict)
    dataset_manifests: Sequence[Mapping[str, Any]] = ()
    created_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))

    def verdict(self) -> tuple[Verdict, list[str]]:
        """Rend le verdict de l'étude et ses raisons.

        Returns:
            Le couple rendu par :func:`decide_verdict`, appliqué aux preuves et
            aux seuils portés par ce rapport.
        """
        return decide_verdict(self.evidence, self.criteria)


#: Les caractères qui feraient d'un nom de pièce un chemin. Un nom de figure
#: ou de tableau sert à fabriquer un fichier sous ``figures/`` ou ``tables/``,
#: donc il doit rester un nom de fichier et jamais devenir un chemin.
_SEPARATEURS_INTERDITS = ("/", "\\", "..")


def _valider_noms(pieces: Sequence[Any], genre: str, pluriel: str) -> None:
    """Refuse un nom de pièce vide, en double, ou qui contient un chemin.

    Deux pièces de même nom s'écrasent en silence sur le disque, et la page
    montre alors deux fois le même fichier sous deux légendes différentes. Un
    nom qui porte un séparateur écrit hors du répertoire du rapport.

    Args:
        pieces: les figures ou les tableaux du rapport.
        genre: le mot au singulier, employé dans le message d'erreur.
        pluriel: le même mot au pluriel.

    Raises:
        ConfigError: si un nom est vide, en double, ou porte un chemin.
    """
    vus: set[str] = set()
    for piece in pieces:
        nom = str(piece.name)
        if not nom.strip():
            raise ConfigError(f"un {genre} du rapport porte un nom vide.")
        if any(marque in nom for marque in _SEPARATEURS_INTERDITS):
            raise ConfigError(f"le nom de {genre} « {nom} » porte un chemin, il faut un nom de fichier.")
        if nom in vus:
            raise ConfigError(
                f"deux {pluriel} du rapport portent le nom « {nom} », un seul fichier survivrait."
            )
        vus.add(nom)


def _valider_sections(report: StudyReport) -> None:
    """Refuse une clé de section inconnue et une figure au fichier absent."""
    connues = set(section_keys())
    inconnues = sorted(set(report.sections) - connues)
    if inconnues:
        raise ConfigError(f"sections inconnues dans le rapport : {inconnues}.")
    for objet in (*report.tables, *report.figures):
        if objet.section not in connues:
            raise ConfigError(f"« {objet.name} » vise une section inconnue : {objet.section}.")
    _valider_noms(report.figures, "figure", "figures")
    _valider_noms(report.tables, "tableau", "tableaux")
    for figure in report.figures:
        if not Path(figure.path).is_file():
            raise ConfigError(f"la figure « {figure.name} » ne pointe sur aucun fichier : {figure.path}.")


def _valider_metriques(report: StudyReport) -> None:
    """Refuse un tableau de métriques sans échantillon ni base de coût."""
    if report.metrics is None:
        return
    attendues = {"metric", "value", "sample", "cost_basis"}
    absentes = sorted(attendues - set(report.metrics.columns))
    if absentes:
        raise ConfigError(
            "le tableau des métriques doit porter l'échantillon et la base de coût ; "
            f"colonnes absentes : {absentes}."
        )


def _serialisable(valeur: Any) -> Any:
    """Rend une valeur prête pour JSON ou YAML, sans perte silencieuse."""
    if isinstance(valeur, Path):
        return str(valeur)
    if isinstance(valeur, dt.datetime | dt.date):
        return valeur.isoformat()
    if isinstance(valeur, Mapping):
        return {str(k): _serialisable(v) for k, v in valeur.items()}
    if isinstance(valeur, list | tuple):
        return [_serialisable(v) for v in valeur]
    if hasattr(valeur, "value") and isinstance(getattr(valeur, "value", None), str):
        return valeur.value
    if hasattr(valeur, "item") and not isinstance(valeur, str | bytes):
        return valeur.item()
    return valeur


#: La feuille de style du rapport, écrite dans le fichier pour qu'il soit
#: autonome. Aucune police ni aucune image ne vient du réseau.
_STYLE = """
:root { color-scheme: light dark; }
body { font-family: Georgia, 'Times New Roman', serif; line-height: 1.55;
       max-width: 52rem; margin: 2rem auto; padding: 0 1rem; }
h1 { font-size: 1.7rem; border-bottom: 2px solid currentColor; padding-bottom: .3rem; }
h2 { font-size: 1.25rem; margin-top: 2.2rem; }
nav ol { columns: 2; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { border: 1px solid #999; padding: .3rem .5rem; text-align: right; }
th:first-child, td:first-child { text-align: left; }
figure { margin: 1rem 0; }
img { max-width: 100%; height: auto; }
.meta { font-size: .85rem; }
.verdict { font-size: 1.1rem; font-weight: bold; }
.reason-pass::before { content: "OK "; }
.reason-fail::before { content: "NON "; }
ul.reasons { list-style: none; padding-left: 0; }
ul.reasons li { border-left: 3px solid #999; padding-left: .6rem; margin: .3rem 0; }
"""


def _table_html(frame: pd.DataFrame) -> str:
    """Rend un tableau pandas en HTML échappé, sans style en ligne."""
    return frame.to_html(index=False, border=0, escape=True, na_rep="")


def _section_html(cle: str, titre: str, rang: int, report: StudyReport, verdict_bloc: str) -> str:
    """Assemble une section du rapport : titre, prose, tableaux, figures."""
    morceaux = [f'<section id="{cle}">', f"<h2>{rang}. {html.escape(titre)}</h2>"]
    prose = report.sections.get(cle, "").strip()
    morceaux.append(f"<p>{html.escape(prose)}</p>" if prose else "<p>Section non renseignée.</p>")

    if cle == "replication":
        morceaux.append(_table_html(replication_table(tuple(report.evidence.replication_checks))))
    if cle == "performance" and report.metrics is not None:
        morceaux.append(_table_html(report.metrics))
    if cle == "verdict":
        morceaux.append(verdict_bloc)

    for tableau in report.tables:
        if tableau.section == cle:
            legende = html.escape(tableau.caption) if tableau.caption else html.escape(tableau.name)
            morceaux.append(
                f"<figure><figcaption>{legende}</figcaption>{_table_html(tableau.frame)}</figure>"
            )
    for figure in report.figures:
        if figure.section == cle:
            fichier = f"{_DOSSIER_FIGURES}/{figure.name}{Path(figure.path).suffix}"
            legende = html.escape(figure.caption) if figure.caption else html.escape(figure.name)
            morceaux.append(
                f'<figure><img src="{html.escape(fichier)}" alt="{legende}">'
                f"<figcaption>{legende}</figcaption></figure>"
            )
    morceaux.append("</section>")
    return "\n".join(morceaux)


def _verdict_html(verdict: Verdict, raisons: Sequence[str]) -> str:
    """Rend le bloc du verdict et de ses raisons, une puce par critère."""
    lignes = [f'<p class="verdict">{html.escape(verdict.value)}</p>', '<ul class="reasons">']
    for raison in raisons:
        classe = "reason-pass" if raison.startswith(_PASS) else "reason-fail"
        lignes.append(f'<li class="{classe}">{html.escape(raison)}</li>')
    lignes.append("</ul>")
    return "\n".join(lignes)


def _corps_html(report: StudyReport, verdict: Verdict, raisons: Sequence[str]) -> str:
    """Assemble le corps du rapport : en-tête, sommaire et quinze sections."""
    entete = [
        f"<h1>{html.escape(report.study_name)}</h1>",
        f'<p class="meta">Expérience {html.escape(report.experiment_id)}, '
        f"écrite le {html.escape(report.created_at.isoformat())}.</p>",
        f'<p class="meta">Article : {html.escape(report.paper)}</p>',
        f'<p class="verdict">Verdict : {html.escape(verdict.value)}</p>',
    ]
    sommaire = ["<nav><ol>"]
    for cle, titre in REPORT_SECTIONS:
        sommaire.append(f'<li><a href="#{cle}">{html.escape(titre)}</a></li>')
    sommaire.append("</ol></nav>")

    verdict_bloc = _verdict_html(verdict, raisons)
    corps = [
        _section_html(cle, titre, rang, report, verdict_bloc)
        for rang, (cle, titre) in enumerate(REPORT_SECTIONS, start=1)
    ]
    return "\n".join([*entete, *sommaire, *corps])


#: Les trois champs qu'un gabarit de rapport peut porter.
_CHAMPS_GABARIT = ("body", "title", "style")

#: Le motif qui reconnaît un champ de gabarit, et lui seul.
_MOTIF_CHAMP = re.compile(r"\{(" + "|".join(_CHAMPS_GABARIT) + r")\}")


def _remplir_gabarit(template: str, valeurs: Mapping[str, str]) -> str:
    """Remplace les trois champs du gabarit, et laisse toute autre accolade.

    **Pourquoi pas ``str.format``.** Un gabarit HTML porte presque toujours un
    bloc de style, donc des accolades de CSS. ``str.format`` les lit comme des
    champs et lève une ``KeyError`` sur le premier sélecteur venu. La
    substitution se fait donc champ par champ, en une seule passe.

    **Pourquoi une seule passe.** Le corps du rapport peut contenir le texte
    ``{title}``, écrit par le chercheur dans sa prose. Une substitution en
    plusieurs passes le remplacerait à son tour, ce qui changerait le rapport
    après son écriture.

    Args:
        template: le gabarit, qui porte au moins le champ ``{body}``.
        valeurs: la valeur de chacun des trois champs.

    Returns:
        Le document, champs remplacés et autres accolades gardées telles quelles.
    """
    return _MOTIF_CHAMP.sub(lambda m: valeurs[m.group(1)], template)


def _document_html(report: StudyReport, corps: str, template: str | None) -> str:
    """Enveloppe le corps dans le gabarit, celui du laboratoire par défaut."""
    titre = html.escape(f"{report.study_name} ({report.experiment_id})")
    if template is None:
        return (
            "<!doctype html>\n"
            '<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{titre}</title>\n<style>{_STYLE}</style>\n</head>\n"
            f"<body>\n{corps}\n</body>\n</html>\n"
        )
    if "{body}" not in template:
        raise ConfigError("le gabarit de rapport doit porter le champ « {body} ».")
    return _remplir_gabarit(template, {"body": corps, "title": titre, "style": _STYLE})


def _ecrire_figures(report: StudyReport, dossier: Path) -> list[str]:
    """Recopie les figures dans le rapport et rend les noms de fichiers écrits."""
    ensure(dossier)
    ecrits: list[str] = []
    for figure in report.figures:
        source = Path(figure.path)
        cible = dossier / f"{figure.name}{source.suffix}"
        shutil.copyfile(source, cible)
        ecrits.append(cible.name)
    return ecrits


def _ecrire_tableaux(report: StudyReport, dossier: Path) -> list[str]:
    """Écrit les tableaux en CSV et rend les noms de fichiers écrits."""
    ensure(dossier)
    ecrits: list[str] = []
    for tableau in report.tables:
        cible = dossier / f"{tableau.name}.csv"
        tableau.frame.to_csv(cible, index=False)
        ecrits.append(cible.name)
    return ecrits


def generate_report(
    study_dir: str | Path,
    report: StudyReport,
    template: str | Path | None = None,
) -> Path:
    """Écrit le rapport complet d'une étude et rend son répertoire.

    **Ce qui est écrit.** Le répertoire ``reports/<étude>/<expérience>/`` reçoit
    six choses : la page ``report.html``, les métriques en JSON, la
    configuration en YAML, les figures, les tableaux et les manifestes de
    données. Rien d'autre n'est nécessaire pour relire l'étude dans un an.

    **Pourquoi une page autonome.** Le fichier HTML ne charge ni police, ni
    feuille de style, ni script depuis le réseau. Il s'ouvre sans connexion, se
    joint à un courriel, et ne dépend d'aucun service qui pourrait disparaître.

    **Le plan imposé.** Les quinze sections de :data:`REPORT_SECTIONS` sont
    écrites dans l'ordre, présentes même vides. Une section absente serait un
    contrôle qu'on aurait oublié de faire, et le rapport ne le dirait pas.

    Args:
        study_dir: le répertoire de l'étude. Le rapport s'écrit dessous.
        report: le rapport à écrire.
        template: un gabarit HTML portant le champ ``{body}``, ou le chemin
            d'un fichier qui le contient. Le gabarit du laboratoire sinon.

    Returns:
        Le répertoire écrit, qui porte ``report.html`` et ses cinq compagnons.

    Raises:
        ConfigError: si une clé de section est inconnue, si une figure ne
            pointe sur aucun fichier, si le tableau des métriques n'a pas ses
            colonnes d'étiquette, ou si le gabarit n'a pas son champ.
    """
    _valider_sections(report)
    _valider_metriques(report)

    gabarit: str | None
    if template is None:
        gabarit = None
    elif isinstance(template, Path):
        gabarit = template.read_text(encoding="utf-8")
    else:
        gabarit = template

    sortie = ensure(Path(study_dir) / "reports" / report.study_name / report.experiment_id)
    verdict, raisons = report.verdict()

    corps = _corps_html(report, verdict, raisons)
    (sortie / _FICHIER_HTML).write_text(_document_html(report, corps, gabarit), encoding="utf-8")

    metriques = {
        "study": report.study_name,
        "experiment_id": report.experiment_id,
        "created_at": report.created_at.isoformat(),
        "hypothesis": report.hypothesis,
        "paper": report.paper,
        "verdict": verdict.value,
        "reasons": list(raisons),
        "criteria": report.criteria.model_dump(mode="json"),
        "metrics": [] if report.metrics is None else report.metrics.to_dict(orient="records"),
        "replication": [check.as_row() for check in report.evidence.replication_checks],
    }
    (sortie / _FICHIER_METRIQUES).write_text(
        json.dumps(_serialisable(metriques), ensure_ascii=False, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )

    (sortie / _FICHIER_CONFIG).write_text(
        yaml.safe_dump(_serialisable(dict(report.config)), allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )

    (sortie / _FICHIER_MANIFESTE).write_text(
        json.dumps(
            {"datasets": _serialisable(list(report.dataset_manifests))},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    figures = _ecrire_figures(report, sortie / _DOSSIER_FIGURES)
    tableaux = _ecrire_tableaux(report, sortie / _DOSSIER_TABLEAUX)

    _LOG.info(
        "rapport écrit",
        extra={
            "study": report.study_name,
            "experiment_id": report.experiment_id,
            "verdict": verdict.value,
            "n_figures": len(figures),
            "n_tables": len(tableaux),
            "path": str(sortie),
        },
    )
    return sortie
