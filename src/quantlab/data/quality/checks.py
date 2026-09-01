r"""Les contrôles de qualité : échouer bruyamment plutôt que laisser passer.

**Le problème.** Une donnée fausse ne se voit pas dans un backtest, elle s'y
lit comme une performance. Un horodatage en double compte deux fois le même
rendement. Une division non ajustée fabrique une baisse de 50 % qui n'a jamais
eu lieu. Un prix figé sur douze séances fait paraître une stratégie moins
volatile qu'elle ne l'est. Aucun de ces trois défauts ne lève d'exception, et
tous les trois déplacent le ratio de Sharpe publié.

**Le remède.** Des contrôles nommés, purs, qui rendent un verdict au lieu de
corriger en silence. Une correction silencieuse est pire que le défaut : elle
supprime la trace de ce qui s'est passé. Le laboratoire préfère
:class:`~quantlab.core.errors.DataQualityError` levée à la porte du lac, avec
le nom du contrôle, le nombre de lignes fautives et un échantillon de ces
lignes.

**La règle de lecture qui gouverne tout le module.** Chaque contrôle documente
ce qu'il attrape RÉELLEMENT et ce qu'il laisse passer. Un contrôle dont on
croit qu'il attrape plus qu'il n'attrape est pire que pas de contrôle : il
donne une confiance que rien ne soutient. La section « Ce qu'il laisse passer »
de chaque docstring est donc la partie qui compte, et elle est écrite avant la
partie flatteuse.

**Le vocabulaire du module.**

``contrôle``
    Une fonction pure qui prend un tableau et rend un :class:`CheckResult`. Elle
    ne modifie rien, ne journalise rien de bloquant, ne lève pas d'exception sur
    une donnée fautive. C'est :meth:`QualityReport.raise_if_failed` qui décide
    d'arrêter le pipeline, et personne d'autre.

``gravité``
    Trois niveaux, :attr:`Severity.INFO`, :attr:`Severity.WARNING` et
    :attr:`Severity.ERROR`. La gravité est un ARGUMENT de chaque contrôle, avec
    une valeur par défaut déclarée, parce que le même défaut n'a pas le même
    poids selon l'étage du lac. Un prix figé est bloquant en *gold* et
    seulement notable en *bronze*.

``violation``
    Une ligne, ou un élément, qui viole le contrat du contrôle. Chaque contrôle
    dit dans sa docstring ce qu'il compte exactement, parce que « 12 violations »
    ne veut rien dire tant qu'on ne sait pas si l'unité est la ligne, la plage
    ou la colonne.

**Statut des chiffres de ce module.** Les taux de fausse alarme cités pour
:func:`check_extreme_returns` et :func:`check_split_anomaly` sont MODÉLISÉS.
Ils viennent d'une simulation dont les hypothèses sont déclarées dans chaque
docstring, et non d'un comptage sur des données réelles. Aucun taux mesuré sur
un univers réel n'est disponible à ce jour, et il est déclaré non trouvé.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from quantlab.core.calendars import DEFAULT_CALENDAR, sessions
from quantlab.core.errors import DataQualityError
from quantlab.core.logging import get_logger

__all__ = [
    "DEFAULT_SPLIT_RATIOS",
    "DEFAULT_VOLUME_TOLERANCE",
    "MAX_SAMPLE_ROWS",
    "OHLC_COLUMNS",
    "VOLUME_COLUMN",
    "CheckResult",
    "QualityReport",
    "Severity",
    "check_column_schema",
    "check_extreme_returns",
    "check_missing_sessions",
    "check_monotonic_index",
    "check_no_duplicate_timestamps",
    "check_ohlc_consistency",
    "check_positive_prices",
    "check_split_anomaly",
    "check_stale_prices",
    "check_timezone",
    "run_checks",
]

if TYPE_CHECKING:
    import datetime as dt

_log = get_logger(__name__)

#: Nombre de lignes fautives conservées dans l'échantillon d'un résultat. Dix
#: suffisent à reconnaître un motif, et un rapport reste lisible.
MAX_SAMPLE_ROWS = 10

#: Les colonnes d'une barre de prix, dans l'ordre habituel des fournisseurs.
OHLC_COLUMNS: tuple[str, str, str, str] = ("open", "high", "low", "close")

#: La colonne de volume, séparée des quatre prix parce qu'elle a une unité
#: différente et une règle différente : elle peut valoir zéro, pas eux.
VOLUME_COLUMN = "volume"

#: Tolérance relative par défaut sur le volume de :func:`check_split_anomaly`.
#: Elle vaut moins d'un tiers, borne au delà de laquelle un volume INCHANGÉ
#: passerait pour corroborant sur le plus petit rapport candidat, trois pour
#: deux. La dérivation est écrite dans la docstring du contrôle.
DEFAULT_VOLUME_TOLERANCE = 0.30

#: Les rapports de division retenus par défaut par :func:`check_split_anomaly`.
#: La liste couvre les divisions et regroupements courants des marchés nord
#: américains. Le plus petit écart de prix considéré vaut donc un tiers, ce qui
#: est déjà un mouvement quotidien très rare.
DEFAULT_SPLIT_RATIOS: tuple[float, ...] = (
    2.0,
    3.0,
    4.0,
    5.0,
    10.0,
    20.0,
    3.0 / 2.0,
    2.0 / 3.0,
    1.0 / 2.0,
    1.0 / 3.0,
    1.0 / 4.0,
    1.0 / 5.0,
    1.0 / 10.0,
    1.0 / 20.0,
)


class Severity(StrEnum):
    """La gravité d'un contrôle : notable, suspect, ou bloquant.

    Trois niveaux et pas quatre. Le quatrième niveau que l'on ajoute toujours,
    « critique », ne change aucune décision : soit le pipeline s'arrête, soit il
    continue. Un niveau qui ne change pas de décision est un niveau qui sert à
    éviter de trancher.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    @property
    def rank(self) -> int:
        """Rend le rang de la gravité, de 0 pour ``INFO`` à 2 pour ``ERROR``.

        Le rang existe parce que ``StrEnum`` compare ses membres par leur
        chaîne, et que l'ordre alphabétique met ``ERROR`` avant ``INFO``, ce qui
        est exactement l'inverse de l'ordre voulu.
        """
        return {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}[self]


@dataclass(frozen=True, eq=False)
class CheckResult:
    """Le verdict d'un contrôle, et de quoi le comprendre sans relire le code.

    Attributes:
        name: le nom du contrôle, tel qu'il apparaît dans le rapport.
        passed: ``True`` si aucune violation n'a été trouvée.
        severity: la gravité déclarée du contrôle, indépendante du verdict. Un
            contrôle réussi garde sa gravité, si bien qu'un rapport dit aussi
            ce qui aurait bloqué.
        n_violations: le nombre d'éléments fautifs, dont l'unité est précisée
            par la docstring du contrôle.
        sample: les premières lignes fautives, au plus
            :data:`MAX_SAMPLE_ROWS`. Tableau vide quand le contrôle passe.
        message: une phrase en français qui dit ce qui a été trouvé, et où.

    Note:
        La classe est gelée et compare par identité (``eq=False``). Comparer
        deux résultats par valeur exigerait de comparer deux ``DataFrame``, dont
        l'égalité rend un tableau de booléens et non un booléen. Les tests
        comparent les champs un par un.
    """

    name: str
    passed: bool
    severity: Severity
    n_violations: int = 0
    sample: pd.DataFrame = field(default_factory=pd.DataFrame)
    message: str = ""

    def __str__(self) -> str:
        etat = "OK" if self.passed else "ÉCHEC"
        return f"[{self.severity.value}] {self.name} : {etat} ({self.n_violations}) {self.message}"


@dataclass(frozen=True, eq=False)
class QualityReport:
    """L'agrégat des verdicts d'une suite de contrôles.

    Le rapport ne décide rien tout seul. Il porte les résultats, et
    :meth:`raise_if_failed` applique le seuil de gravité choisi par l'appelant.
    Cette séparation est voulue. Le même jeu de contrôles sert à inspecter un
    fichier brut, où l'on veut tout voir, et à barrer l'entrée de la couche
    *gold*, où le moindre défaut bloquant arrête la chaîne.
    """

    results: tuple[CheckResult, ...]

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self) -> Iterator[CheckResult]:
        return iter(self.results)

    @property
    def passed(self) -> bool:
        """``True`` si tous les contrôles ont passé, quelle que soit la gravité."""
        return all(r.passed for r in self.results)

    def failures(self, severity: Severity = Severity.INFO) -> tuple[CheckResult, ...]:
        """Rend les contrôles échoués dont la gravité atteint le seuil.

        Args:
            severity: seuil de gravité, ``INFO`` par défaut, ce qui rend tous
                les échecs.

        Returns:
            Les résultats échoués, dans l'ordre où les contrôles ont tourné.
        """
        seuil = Severity(severity).rank
        return tuple(r for r in self.results if not r.passed and r.severity.rank >= seuil)

    def raise_if_failed(self, severity: Severity = Severity.ERROR) -> None:
        """Lève :class:`DataQualityError` si un contrôle échoue au seuil donné.

        Args:
            severity: gravité minimale qui bloque. ``ERROR`` par défaut, donc un
                avertissement laisse passer.

        Raises:
            DataQualityError: avec le nom, le compte et le message de chaque
                contrôle échoué au seuil. Le message porte tous les échecs, pas
                seulement le premier : corriger une donnée un défaut à la fois
                coûte un aller-retour par défaut.
        """
        echecs = self.failures(severity)
        if not echecs:
            return
        lignes = "\n".join(f"  - {r}" for r in echecs)
        raise DataQualityError(
            f"{len(echecs)} contrôle(s) de qualité en échec au seuil {Severity(severity).value} :\n{lignes}"
        )

    def to_frame(self) -> pd.DataFrame:
        """Rend le rapport sous forme de tableau, une ligne par contrôle.

        Returns:
            Un tableau aux colonnes ``name``, ``passed``, ``severity``,
            ``n_violations`` et ``message``, dans l'ordre d'exécution.
        """
        return pd.DataFrame(
            {
                "name": [r.name for r in self.results],
                "passed": [r.passed for r in self.results],
                "severity": [r.severity.value for r in self.results],
                "n_violations": [r.n_violations for r in self.results],
                "message": [r.message for r in self.results],
            }
        )


#: Signature d'un contrôle tel que :func:`run_checks` l'attend.
Check = Callable[[pd.DataFrame], CheckResult]


# ---------------------------------------------------------------------------
# Aides internes
# ---------------------------------------------------------------------------


def _empty_sample() -> pd.DataFrame:
    """Rend un tableau vide, l'échantillon d'un contrôle qui passe."""
    return pd.DataFrame()


def _head(frame: pd.DataFrame, max_sample: int) -> pd.DataFrame:
    """Rend au plus ``max_sample`` lignes, copiées pour ne rien partager."""
    return frame.head(max_sample).copy()


def _missing_columns_result(
    name: str,
    missing: Sequence[str],
    severity: Severity,
) -> CheckResult:
    """Rend l'échec type d'un contrôle privé de la colonne qu'il lui faut.

    Un contrôle qui ne trouve pas sa colonne échoue au lieu de passer. Le
    contraire donnerait un rapport vert sur un tableau que personne n'a
    contrôlé, ce qui est le défaut exact que ce module existe pour éviter.
    """
    liste = ", ".join(f"« {c} »" for c in missing)
    return CheckResult(
        name=name,
        passed=False,
        severity=severity,
        n_violations=len(missing),
        sample=_empty_sample(),
        message=f"colonne(s) absente(s) : {liste}, le contrôle n'a pas pu tourner",
    )


def _numeric(series: pd.Series) -> pd.Series:
    """Rend la série en flottants, sans conversion silencieuse d'objets.

    Raises:
        DataQualityError: si la colonne n'est pas numérique. La conversion
            implicite d'une colonne de texte en nombres est morte en pandas 3,
            et le laboratoire ne la ressuscite pas. Une colonne de prix arrivée
            en texte est un défaut de chargement, pas un détail de typage.
    """
    if not pd.api.types.is_numeric_dtype(series):
        raise DataQualityError(
            f"la colonne « {series.name} » est de type {series.dtype}, un contrôle numérique "
            "ne s'applique pas à du texte"
        )
    return series.astype("float64")


def _index_dates(index: pd.Index, session_tz: str | None) -> pd.DatetimeIndex:
    """Rend les dates de calendrier de l'index, fuseau retiré.

    Args:
        index: l'index du tableau, temporel.
        session_tz: si donné et si l'index est averti, convertit dans ce fuseau
            avant de prendre la date. Sans valeur, le fuseau est retiré sans
            conversion, ce qui garde la date telle qu'elle est écrite.

    Raises:
        DataQualityError: si l'index n'est pas un index temporel.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise DataQualityError(
            f"l'index est de type {type(index).__name__}, un contrôle de calendrier exige un DatetimeIndex"
        )
    idx = index
    if idx.tz is not None:
        idx = idx.tz_convert(session_tz).tz_localize(None) if session_tz else idx.tz_localize(None)
    return pd.DatetimeIndex(idx).normalize()


# ---------------------------------------------------------------------------
# Les contrôles
# ---------------------------------------------------------------------------


def check_no_duplicate_timestamps(
    df: pd.DataFrame,
    keys: Sequence[str] | None = None,
    *,
    severity: Severity = Severity.ERROR,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    """Rend le verdict sur les clés en double, index ou colonnes.

    Le problème. Un doublon compte deux fois le même jour. Sur une série de
    rendements, il ajoute une observation de rendement nul, ce qui fait baisser
    la volatilité mesurée sans toucher au rendement moyen, donc monter le ratio
    de Sharpe. Sur un panel, il duplique une position et double son poids.

    L'intuition. Un couple ``(date, ticker)`` désigne une observation et une
    seule. Deux lignes portant le même couple signifient qu'une fusion a été
    faite deux fois, ou que deux fichiers se recouvrent.

    Args:
        df: le tableau à contrôler.
        keys: les colonnes formant la clé d'unicité. Sans valeur, la clé est
            l'index, ce qui convient à une série d'un seul actif.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes fautives conservées.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` compte les LIGNES en trop,
        c'est à dire le nombre total de lignes dupliquées moins le nombre de
        clés distinctes concernées. Trois lignes portant la même date comptent
        donc pour deux violations.

    Note:
        Ce qu'il attrape. Les clés strictement identiques, adjacentes ou non,
        dans l'index comme dans des colonnes.

        Ce qu'il laisse passer. Trois choses, et elles sont fréquentes.
        Premièrement, deux horodatages voisins mais distincts, par exemple
        ``09:30:00`` et ``09:30:01``, qui désignent la même barre chez un
        fournisseur intrajournalier. Deuxièmement, la même observation présente
        dans deux tableaux différents, puisque le contrôle ne voit qu'un
        tableau. Troisièmement, une ligne dupliquée dont un champ diffère, par
        exemple deux prix pour la même date : le doublon est alors détecté, mais
        le contrôle ne dit pas lequel des deux prix est le bon.

    Example:
        Sur un index portant deux fois le 5 janvier et une fois le 6, le
        contrôle rend ``n_violations = 1``.
    """
    if keys:
        manquantes = [c for c in keys if c not in df.columns]
        if manquantes:
            return _missing_columns_result("no_duplicate_timestamps", manquantes, severity)
        duplique = df.duplicated(subset=list(keys), keep=False)
        etiquette = "clés " + ", ".join(f"« {c} »" for c in keys)
    else:
        duplique = df.index.duplicated(keep=False)
        etiquette = "index"

    duplique = pd.Series(np.asarray(duplique), index=df.index)
    n_lignes = int(duplique.sum())
    if n_lignes == 0:
        return CheckResult(
            name="no_duplicate_timestamps",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=f"aucun doublon sur {etiquette}, {len(df)} lignes contrôlées",
        )

    fautives = df.loc[duplique.to_numpy()]
    n_cles = int(fautives.groupby(list(keys)).ngroups) if keys else int(fautives.index.nunique())
    n_violations = n_lignes - n_cles
    return CheckResult(
        name="no_duplicate_timestamps",
        passed=False,
        severity=severity,
        n_violations=n_violations,
        sample=_head(fautives, max_sample),
        message=(
            f"{n_violations} ligne(s) en trop sur {etiquette}, réparties sur {n_cles} clé(s) dupliquée(s)"
        ),
    )


def check_monotonic_index(
    df: pd.DataFrame,
    *,
    strict: bool = True,
    severity: Severity = Severity.ERROR,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    """Rend le verdict sur l'ordre chronologique de l'index.

    Le problème. Tout calcul à fenêtre glissante suppose que la ligne suivante
    est postérieure à la précédente. C'est le cas du maximum courant d'un
    drawdown, du rendement calculé par différence de prix, et du décalage qui
    reporte un signal à la séance d'après. Un index en désordre ne lève aucune
    exception et fausse ces trois calculs en silence.

    Le portefeuille a payé ce défaut au paquet ``gvf.marches``. Des horodatages
    lus en nanosecondes alors qu'ils étaient en millisecondes donnaient des
    dates de 1970 en désordre, et le tri appariait ensuite les prix aux
    mauvaises minutes. Le tableau gardait le bon nombre de lignes et les bonnes
    colonnes, et un tiers des barres était décalé.

    Args:
        df: le tableau à contrôler.
        strict: si ``True``, deux valeurs égales consécutives comptent pour une
            violation. Mettre ``False`` sur un panel où plusieurs actifs
            partagent la même date.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes fautives conservées.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` compte les POSITIONS ``i``
        telles que ``index[i]`` ne suit pas ``index[i-1]``. L'échantillon porte
        les lignes de ces positions.

    Note:
        Ce qu'il attrape. Toute inversion locale, et, en mode strict, les
        doublons adjacents.

        Ce qu'il laisse passer. Deux choses. Un index parfaitement croissant
        mais entièrement faux, par exemple décalé d'un jour, ce qui est
        exactement le défaut le plus coûteux et que seul un recoupement avec une
        source indépendante détecte. Et, en mode non strict, tous les doublons,
        adjacents ou non, dont :func:`check_no_duplicate_timestamps` a la
        charge.

    Example:
        Sur l'index ``[1, 3, 2]``, le contrôle rend ``n_violations = 1``, la
        position fautive étant la troisième.
    """
    n = len(df.index)
    if n <= 1:
        return CheckResult(
            name="monotonic_index",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=f"index de {n} élément(s), l'ordre est trivialement respecté",
        )

    valeurs = df.index.to_numpy()
    precedent, suivant = valeurs[:-1], valeurs[1:]
    fautif = suivant <= precedent if strict else suivant < precedent
    n_violations = int(fautif.sum())
    if n_violations == 0:
        sens = "strictement croissant" if strict else "croissant"
        return CheckResult(
            name="monotonic_index",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=f"index {sens} sur {n} éléments",
        )

    positions = np.flatnonzero(fautif) + 1
    return CheckResult(
        name="monotonic_index",
        passed=False,
        severity=severity,
        n_violations=n_violations,
        sample=_head(df.iloc[positions], max_sample),
        message=(
            f"{n_violations} rupture(s) d'ordre dans l'index, première à la position {int(positions[0])}"
        ),
    )


def check_ohlc_consistency(
    df: pd.DataFrame,
    *,
    columns: Sequence[str] = OHLC_COLUMNS,
    volume_column: str | None = VOLUME_COLUMN,
    severity: Severity = Severity.ERROR,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    r"""Rend le verdict sur la cohérence interne des barres de prix.

    Le problème. Une barre décrit quatre prix d'une même séance, et ces quatre
    prix sont ordonnés par construction. Le plus bas de la séance ne peut pas
    dépasser le prix d'ouverture, et le plus haut ne peut pas lui être
    inférieur. Une barre qui viole cet ordre vient d'un mélange de sources, d'un
    ajustement appliqué à trois colonnes sur quatre, ou d'une inversion de
    colonnes au chargement.

    L'intuition. Le contrôle ne demande pas si les prix sont justes, question à
    laquelle un tableau seul ne peut pas répondre. Il demande s'ils sont
    compatibles entre eux, ce qui se vérifie sans aucune source extérieure.

    La formule. Pour chaque barre :math:`t` :

    .. math::

        L_t \le \min(O_t, C_t)
        \quad\text{et}\quad
        \max(O_t, C_t) \le H_t
        \quad\text{et}\quad
        V_t \ge 0

    où :math:`O_t` est le prix d'ouverture, :math:`H_t` le plus haut,
    :math:`L_t` le plus bas, :math:`C_t` le prix de clôture et :math:`V_t` le
    volume échangé de la séance.

    Hypothèses. Les quatre prix décrivent la même séance, la même place et la
    même devise, et ils portent le même traitement des actions de société. Un
    tableau qui mélange un ``close`` ajusté et un ``high`` brut viole ces
    inégalités et se fait attraper, ce qui est le comportement voulu.

    Args:
        df: le tableau à contrôler.
        columns: les quatre colonnes de prix, dans l'ordre ouverture, plus haut,
            plus bas, clôture.
        volume_column: la colonne de volume, ou ``None`` pour ne pas la
            contrôler. L'absence de la colonne nommée fait échouer le contrôle.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes fautives conservées.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` compte les LIGNES violant
        au moins une des trois inégalités. Une ligne qui les viole toutes
        compte pour une.

    Note:
        Ce qu'il attrape. Les inversions de colonnes, un ``high`` inférieur au
        ``close``, un volume négatif, et le mélange d'une colonne ajustée avec
        trois colonnes brutes quand le dividende suffit à renverser une
        inégalité.

        Ce qu'il laisse passer, et c'est l'essentiel. Une barre entièrement
        fausse mais cohérente. Multiplier les quatre prix par deux conserve les
        deux inégalités, si bien qu'une division non ajustée passe ce contrôle
        sans une seule violation. C'est le rôle de
        :func:`check_extreme_returns` et de :func:`check_split_anomaly`, et
        aucun des trois ne remplace les deux autres. Passe également un volume
        nul sur une séance ouverte, qui est faux sur un titre liquide et normal
        sur un titre qui ne s'échange pas.

    Example:
        Une barre ``open = 10``, ``high = 9``, ``low = 8``, ``close = 8,5``
        viole la seconde inégalité, ``max(10 ; 8,5) = 10`` dépassant
        ``high = 9``. Elle compte pour une violation.

    Note:
        Vérification de l'implémentation. Une barre construite à la main dont
        chaque inégalité est violée séparément doit rendre exactement une
        violation par barre, et une barre plate où les quatre prix sont égaux
        doit passer, les inégalités étant larges.
    """
    besoin = list(columns) + ([volume_column] if volume_column else [])
    manquantes = [c for c in besoin if c not in df.columns]
    if manquantes:
        return _missing_columns_result("ohlc_consistency", manquantes, severity)

    ouverture, haut, bas, cloture = (_numeric(df[c]) for c in columns)
    corps_bas = np.minimum(ouverture, cloture)
    corps_haut = np.maximum(ouverture, cloture)
    fautif = (bas > corps_bas) | (corps_haut > haut)
    if volume_column:
        fautif = fautif | (_numeric(df[volume_column]) < 0)
    fautif = fautif.fillna(value=False).astype(bool)

    n_violations = int(fautif.sum())
    if n_violations == 0:
        return CheckResult(
            name="ohlc_consistency",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=f"{len(df)} barre(s) cohérentes, bas <= corps <= haut et volume positif",
        )
    return CheckResult(
        name="ohlc_consistency",
        passed=False,
        severity=severity,
        n_violations=n_violations,
        sample=_head(df.loc[fautif], max_sample),
        message=f"{n_violations} barre(s) incohérentes sur {len(df)}",
    )


def check_missing_sessions(
    df: pd.DataFrame,
    calendar: str = DEFAULT_CALENDAR,
    start: str | dt.date | None = None,
    end: str | dt.date | None = None,
    *,
    flag_non_sessions: bool = True,
    session_tz: str | None = None,
    severity: Severity = Severity.WARNING,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    """Rend le verdict sur les séances absentes et les dates hors séance.

    Le problème. Le trou d'une séance ne se voit pas. Il se lit comme une
    absence de mouvement. Il déplace aussi tous les calculs qui comptent les
    périodes : l'annualisation, la fenêtre d'une moyenne mobile, le report d'un
    signal à la séance d'après. Le défaut symétrique, une date présente alors
    que le marché était fermé, fabrique un rendement qui n'a jamais existé.

    L'intuition qui distingue ce contrôle d'un contrôle naïf. Comparer à une
    grille de jours ouvrés, ``pandas.bdate_range`` par exemple, ne dit rien :
    cette grille contient les jours fériés, et elle ignore les fermetures
    exceptionnelles. La comparaison se fait donc aux séances RÉELLES du
    calendrier d'échange, via :func:`quantlab.core.calendars.sessions`.

    Args:
        df: le tableau à contrôler, indexé par le temps.
        calendar: le code ISO 10383 du marché, ``"XNYS"`` par défaut.
        start: première date de la fenêtre contrôlée. Sans valeur, la première
            date de l'index.
        end: dernière date de la fenêtre. Sans valeur, la dernière date.
        flag_non_sessions: si ``True``, compte aussi les dates présentes qui ne
            sont pas des séances. Mettre ``False`` quand le tableau porte
            volontairement des dates hors bourse, un indice économique par
            exemple.
        session_tz: fuseau de conversion avant la prise de date, pour un index
            averti. Sans valeur, le fuseau est retiré sans conversion. Dans les
            deux cas l'horodatage est ensuite ramené à minuit, si bien qu'un
            index intrajournalier se compare bien aux séances du calendrier.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes conservées dans l'échantillon.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` compte les DATES fautives,
        séances absentes plus, si demandé, dates hors séance. L'échantillon
        porte deux colonnes, ``date`` et ``kind``, cette dernière valant
        ``"séance absente"`` ou ``"date hors séance"``.

    Raises:
        DataQualityError: si l'index n'est pas un ``DatetimeIndex``.

    Note:
        Ce qu'il attrape. Un trou dans une série quotidienne, une fermeture
        exceptionnelle mal traitée, et une série construite sur une grille de
        jours ouvrés au lieu du calendrier d'échange.

        Ce qu'il laisse passer. Quatre choses. Une série à la bonne longueur
        mais décalée d'un jour, puisque le nombre de dates coïncide. Un trou
        situé hors de la fenêtre ``[start, end]``, qui est bornée par les
        données elles mêmes quand l'appelant ne la donne pas, si bien qu'un
        manque au tout début n'est pas vu. Un trou intrajournalier, le contrôle
        travaillant à la date. Et les erreurs propres à
        ``exchange_calendars``, base entretenue par la communauté dont les
        fermetures exceptionnelles antérieures à 1990 sont moins fiables.

    Example:
        La Bourse de New York a fermé le 4 juillet 2023 et le
        23 novembre 2023, jour de l'Action de grâce. Un tableau bâti sur
        ``pandas.bdate_range`` contient ces deux dates : le contrôle rend alors
        zéro séance absente et deux dates hors séance.
    """
    dates = _index_dates(df.index, session_tz)
    if len(dates) == 0:
        return CheckResult(
            name="missing_sessions",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message="tableau vide, aucune séance à contrôler",
        )

    debut = pd.Timestamp(start) if start is not None else dates.min()
    fin = pd.Timestamp(end) if end is not None else dates.max()
    attendues = pd.DatetimeIndex(sessions(debut, fin, calendar)).normalize()
    if attendues.tz is not None:
        attendues = attendues.tz_localize(None)

    presentes = pd.DatetimeIndex(dates.unique()).sort_values()
    dans_fenetre = presentes[(presentes >= debut) & (presentes <= fin)]

    absentes = attendues.difference(dans_fenetre)
    hors = dans_fenetre.difference(attendues) if flag_non_sessions else pd.DatetimeIndex([])

    n_violations = len(absentes) + len(hors)
    if n_violations == 0:
        return CheckResult(
            name="missing_sessions",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=(
                f"{len(attendues)} séance(s) de {calendar} entre {debut.date()} et {fin.date()}, "
                "toutes présentes et aucune date hors séance"
            ),
        )

    echantillon = pd.DataFrame(
        {
            "date": list(absentes) + list(hors),
            "kind": ["séance absente"] * len(absentes) + ["date hors séance"] * len(hors),
        }
    )
    return CheckResult(
        name="missing_sessions",
        passed=False,
        severity=severity,
        n_violations=n_violations,
        sample=_head(echantillon, max_sample),
        message=(
            f"{len(absentes)} séance(s) de {calendar} absente(s) et {len(hors)} date(s) hors "
            f"séance, sur {len(attendues)} séance(s) attendues entre {debut.date()} et {fin.date()}"
        ),
    )


def check_extreme_returns(
    df: pd.DataFrame,
    threshold: float = 0.5,
    *,
    column: str = "close",
    already_returns: bool = False,
    severity: Severity = Severity.WARNING,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    r"""Rend le verdict sur les rendements quotidiens dépassant un seuil.

    Le problème. Une division non ajustée, un prix saisi avec une virgule
    déplacée ou un mélange de deux titres fabriquent un rendement énorme. Ce
    rendement entre tel quel dans la volatilité, dans le pire drawdown et dans
    le rendement composé, et il y pèse plus que tout le reste de l'échantillon.

    L'intuition. Un rendement quotidien de plus de 50 % en valeur absolue est
    possible sur une action, mais il est assez rare pour mériter un regard. Le
    contrôle ne dit pas que la donnée est fausse : il dit où regarder.

    La formule. Pour une série de prix :math:`P_t`, le rendement simple vaut

    .. math::

        r_t = \frac{P_t}{P_{t-1}} - 1

    et la ligne :math:`t` est signalée quand :math:`|r_t| > \tau`, où
    :math:`\tau` est le seuil, 0,5 par défaut.

    Hypothèses. Les prix sont positifs, consécutifs dans le temps et exprimés
    dans la même devise avec le même traitement des actions de société. Le
    rendement est calculé par différence relative de lignes adjacentes, sans
    remplissage : une valeur manquante donne un rendement manquant, qui n'est
    pas signalé.

    Provenance. Le seuil de coupure sur le rendement quotidien est un usage de
    place, décrit notamment par Ince et Porter (2006), « Individual equity
    return data from Thomson Datastream: handle with care! », *Journal of
    Financial Research*, 29(4), 463-479. Leur filtre annule le couple de
    rendements :math:`(r_t, r_{t+1})` quand les deux dépassent 100 % et que leur
    composé retombe sous 20 %, ce qui est la signature d'un renversement
    artificiel. Le seuil par défaut retenu ici, 0,5, est plus prudent que leur
    100 %, et c'est un PRÉCEPTE, sans mesure derrière.

    Limites, et la plus gênante d'abord. Une division deux pour une donne
    exactement :math:`-50\%`, donc :math:`|r_t| = 0{,}5`, qui n'est pas
    strictement supérieur au seuil par défaut et n'est PAS signalé. Le seuil
    doit descendre sous 0,5, par exemple à 0,45, pour attraper ce cas précis, et
    c'est :func:`check_split_anomaly` qui le traite proprement.

    Taux de fausse alarme, MODÉLISÉ le 2026-09-01 sur 2 519 000 rendements
    simulés, mille tirages indépendants de dix ans chacun. Sous une marche
    aléatoire de rendements logarithmiques normaux d'écart type 2 % par séance,
    le seuil de 0,5 ne signale AUCUNE séance. Cet écart type vaut environ 32 %
    en volatilité annuelle, et le seuil dépasse vingt écarts types. Sous des rendements de Student
    à trois degrés de liberté ramenés au même écart type, le taux vaut
    0,00278 %, soit 70 séances signalées sur les 2 519 000. Cela fait une
    fausse alarme tous les 143 titres-années, donc environ deux par an sur un
    univers de 250 titres. Les hypothèses sont celles déclarées ci-dessus, et
    le test ``test_extreme_returns_fausse_alarme_bornee`` vérifie que le taux
    reste sous 0,01 %.

    Alternatives. Un seuil relatif à la volatilité propre du titre, par exemple
    dix écarts types glissants, s'adapte aux titres calmes comme aux titres
    agités, mais il devient aveugle quand la fenêtre d'estimation contient elle
    même l'anomalie. Le seuil fixe a le mérite d'être vérifiable à la main.

    Args:
        df: le tableau à contrôler.
        threshold: le seuil en valeur absolue, 0,5 par défaut, soit 50 %.
        column: la colonne de prix, ou de rendements si ``already_returns``.
        already_returns: ``True`` quand la colonne porte déjà des rendements
            simples de période.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes fautives conservées.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` compte les LIGNES dont le
        rendement dépasse le seuil en valeur absolue. L'échantillon porte la
        colonne contrôlée et une colonne ``return``.

    Raises:
        ValueError: si le seuil n'est pas strictement positif.

    Note:
        Ce qu'il attrape. Les divisions non ajustées assez fortes, les virgules
        déplacées, les prix d'un autre titre glissés dans la série.

        Ce qu'il laisse passer. La division deux pour une au seuil par défaut,
        comme expliqué plus haut. Toute erreur d'échelle constante, qui ne crée
        aucun saut. Un prix faux de 30 %, sous le seuil. Et les erreurs qui
        s'annulent en deux séances, que le filtre d'Ince et Porter attrape et
        que celui ci ne voit pas.

    Example:
        Un prix qui passe de 100 à 40 donne :math:`r = 40/100 - 1 = -0{,}6`,
        dont la valeur absolue dépasse 0,5 : la ligne est signalée.
    """
    if threshold <= 0:
        raise ValueError("threshold doit être strictement positif")
    if column not in df.columns:
        return _missing_columns_result("extreme_returns", [column], severity)

    valeurs = _numeric(df[column])
    rendements = valeurs if already_returns else valeurs / valeurs.shift(1) - 1.0
    fautif = (rendements.abs() > threshold).fillna(value=False).astype(bool)

    n_violations = int(fautif.sum())
    pct = 100.0 * threshold
    if n_violations == 0:
        return CheckResult(
            name="extreme_returns",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=(
                f"aucun rendement au delà de {pct:.4g} % sur {int(rendements.notna().sum())} observations"
            ),
        )

    echantillon = pd.DataFrame({column: valeurs, "return": rendements}).loc[fautif]
    pire = float(rendements.loc[fautif].abs().max())
    return CheckResult(
        name="extreme_returns",
        passed=False,
        severity=severity,
        n_violations=n_violations,
        sample=_head(echantillon, max_sample),
        message=(
            f"{n_violations} rendement(s) au delà de {pct:.4g} % en valeur absolue, "
            f"le plus fort à {100.0 * pire:.4g} %"
        ),
    )


def check_split_anomaly(
    df: pd.DataFrame,
    ratio_tolerance: float = 0.02,
    *,
    price_column: str = "close",
    volume_column: str = VOLUME_COLUMN,
    ratios: Sequence[float] = DEFAULT_SPLIT_RATIOS,
    volume_tolerance: float = DEFAULT_VOLUME_TOLERANCE,
    volume_window: int = 20,
    severity: Severity = Severity.WARNING,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    r"""Rend le verdict sur les sauts de prix qui ressemblent à une division non traitée.

    Le problème. Une division deux pour une divise le prix par deux et multiplie
    le nombre d'actions par deux. Le porteur n'a rien gagné ni perdu. Une série
    de prix qui ne traite pas l'opération affiche un rendement de -50 % ce jour
    là, et ce rendement entre dans tous les calculs comme s'il était réel.

    L'intuition, et c'est elle qui fait la valeur du contrôle. Un saut de prix
    seul ne prouve rien : un titre peut vraiment perdre la moitié de sa valeur
    en une séance. Ce qui distingue une division d'un effondrement, c'est le
    VOLUME. Quand le nombre d'actions est multiplié par :math:`k`, le volume
    échangé est multiplié par environ :math:`k` lui aussi, à liquidité en
    valeur inchangée. Un saut de prix au rapport :math:`k` accompagné d'un
    volume multiplié par :math:`k` est une division cohérente ; le même saut
    sans mouvement de volume est suspect.

    La formule. Pour deux séances consécutives, le rapport de prix vaut

    .. math::

        k_t = \frac{P_{t-1}}{P_t}

    Il est jugé proche d'un rapport simple :math:`r` de la liste déclarée quand

    .. math::

        \left| \frac{k_t}{r} - 1 \right| \le \varepsilon

    où :math:`\varepsilon` est ``ratio_tolerance``, 2 % par défaut. Le volume
    est jugé corroborant quand

    .. math::

        \left| \frac{V_t}{r \, \tilde{V}_{t-1}} - 1 \right| \le \delta

    où :math:`V_t` est le volume de la séance, :math:`\tilde{V}_{t-1}` la
    médiane des ``volume_window`` volumes précédents, et :math:`\delta` la
    tolérance de volume, 0,30 par défaut. La ligne est SIGNALÉE quand le prix
    correspond à un rapport simple et que le volume ne corrobore pas.

    D'où vient ce 0,30, qui n'est pas un nombre choisi au hasard. Le volume est
    jugé corroborant quand :math:`V_t / \tilde{V}_{t-1}` tombe dans
    :math:`[r(1-\delta),\, r(1+\delta)]`. Un volume INCHANGÉ, de facteur 1,
    doit tomber hors de cette bande quel que soit le rapport candidat. La
    condition s'écrit :math:`r(1-\delta) > 1` au plus petit rapport supérieur à
    1 de la liste, soit :math:`r = 3/2`, d'où :math:`\delta < 1/3`. La valeur par
    défaut est la plus grande valeur ronde sous cette borne. Un volume plat
    accompagnant un saut de prix au rapport d'une division est donc toujours
    signalé, ce qui est la raison d'être du contrôle.

    Définition de chaque variable.

    - :math:`P_t`, le prix de clôture de la séance :math:`t` ;
    - :math:`k_t`, le rapport de prix d'une séance à l'autre, supérieur à 1
      pour une division et inférieur à 1 pour un regroupement ;
    - :math:`r`, un rapport de division candidat, par exemple 2 pour une
      division deux pour une, ou 0,1 pour un regroupement un pour dix ;
    - :math:`V_t`, le volume échangé de la séance, compté en actions ;
    - :math:`\tilde{V}_{t-1}`, la médiane glissante du volume. Elle remplace le
      volume de la veille, qui varie du simple au double sans rien signifier.

    Hypothèses, et elles sont fortes. La liquidité en valeur reste stable autour
    de la division, ce qui est faux quand l'opération s'accompagne d'une
    annonce. Le volume publié compte des actions et non des dollars. Et la série
    ne mélange pas des prix ajustés avec des volumes non ajustés, cas dans
    lequel le contrôle signale précisément la ligne, ce qui est le comportement
    voulu.

    Provenance. Le recoupement du prix par le volume pour identifier une action
    de société non traitée est un usage documenté des bases académiques. Deux
    références le portent. Le manuel du CRSP décrit ses facteurs de prix et de
    volume, et Ince et Porter (2006) décrivent le nettoyage de Datastream dans
    « Individual equity return data from Thomson Datastream: handle with care! »,
    *Journal of Financial Research*, 29(4), 463-479. La règle exacte codée ici,
    avec sa médiane glissante et ses deux tolérances, n'est reprise d'aucun
    article : elle est propre au laboratoire, et ses seuils sont des préceptes.

    Taux de fausse alarme, MODÉLISÉ le 2026-09-01 sur 2 519 000 séances
    simulées, mille tirages indépendants de dix ans chacun, sans aucune
    division. Les rendements logarithmiques ont un écart type de 2 % par séance
    et le logarithme du volume un écart type de 0,4. Le volume quotidien varie
    donc d'un facteur 1,5 dans un sens ou dans l'autre une fois sur trois. Sous
    des rendements normaux, le contrôle ne signale AUCUNE ligne. Atteindre le
    bord de la bande du candidat le plus proche, trois pour deux à 2 % près,
    demande un rendement logarithmique de :math:`\ln(1{,}47) = 0{,}385`. Cela
    fait 19,3 écarts types, valeur MESURÉE le 2026-09-01. Sous des rendements
    de Student à
    trois degrés de liberté ramenés au même écart type, le taux vaut
    0,00119 %, soit 30 lignes signalées sur les 2 519 000. Cela fait une fausse
    alarme tous les 333 titres-années, donc environ trois par an sur un univers
    de 250 titres, ou une tous les quatre mois. Le test
    ``test_split_anomaly_fausse_alarme_bornee`` vérifie que le taux reste sous
    0,01 %.

    Le taux de fausse alarme sur des données RÉELLES est déclaré NON TROUVÉ. Il
    dépend de la fréquence des effondrements de plus d'un tiers en une séance
    dans l'univers considéré, et ce module ne mesure pas cette fréquence. Les
    queues d'une loi de Student à trois degrés de liberté n'en sont qu'une
    approximation commode.

    Limites. Le contrôle ne voit que les divisions dont le rapport figure dans
    ``ratios``. Une division trois pour deux au rapport 1,5 y figure, une
    division cinq pour quatre au rapport 1,25 n'y figure pas et n'est pas vue.
    Le recoupement par le volume échoue quand la colonne de volume est elle même
    ajustée pour les divisions, cas dans lequel le volume ne bouge pas et toute
    division déjà traitée serait signalée à tort.

    Alternatives. Comparer la série au fichier des actions de société du
    fournisseur est plus sûr et exige une seconde source, qui n'est pas toujours
    gratuite. Comparer le prix ajusté au prix brut détecte les mêmes cas sans
    volume, et demande que les deux colonnes existent. Le recoupement par le
    volume est retenu ici parce qu'il ne demande rien d'autre que le tableau lui
    même.

    Args:
        df: le tableau à contrôler.
        ratio_tolerance: écart relatif toléré entre le rapport de prix observé
            et le rapport de division candidat, 0,02 par défaut.
        price_column: la colonne de prix.
        volume_column: la colonne de volume, servant au recoupement.
        ratios: les rapports de division candidats.
        volume_tolerance: écart relatif toléré sur le volume attendu, 0,30 par
            défaut, valeur dérivée plus haut pour qu'un volume inchangé ne
            passe jamais pour corroborant.
        volume_window: nombre de séances de la médiane glissante de volume.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes fautives conservées.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` compte les LIGNES dont le
        prix saute d'un rapport simple sans que le volume ne corrobore.
        L'échantillon porte le prix, le volume, le rapport observé
        ``price_ratio``, le rapport candidat ``matched_ratio`` et le rapport de
        volume observé ``volume_factor``.

    Raises:
        ValueError: si une tolérance est négative, si ``volume_window`` est
            inférieur à 1, ou si ``ratios`` est vide.

    Note:
        Ce qu'il attrape. Une division ou un regroupement au rapport déclaré,
        non traité par le fournisseur, quand le volume ne suit pas.

        Ce qu'il laisse passer. Une division dont le rapport n'est pas dans la
        liste. Une division dont le volume suit par coïncidence, auquel cas le
        contrôle conclut à une opération cohérente. Une division sur un titre
        dont le volume est nul ou manquant les jours précédents, cas dans lequel
        la médiane glissante est indéfinie. La ligne est alors signalée faute de
        corroboration possible, et ce faux positif est assumé.

    Example:
        Un prix qui passe de 100 à 50 donne :math:`k = 2`, exactement le
        candidat 2. La médiane glissante du volume vaut 1 000 000, donc le
        volume attendu vaut 2 000 000 et la bande corroborante s'étend de
        1 400 000 à 2 600 000. Un volume de 2 100 000 y tombe, l'écart valant
        :math:`|2{,}1/2 - 1| = 0{,}05`, et la division est jugée cohérente. Un
        volume resté à 1 000 000 donne :math:`|1/2 - 1| = 0{,}50`, au delà de la
        tolérance de 0,30, et la ligne est signalée.
    """
    if ratio_tolerance < 0 or volume_tolerance < 0:
        raise ValueError("les tolérances doivent être positives ou nulles")
    if volume_window < 1:
        raise ValueError("volume_window doit valoir au moins 1")
    candidats = np.asarray(ratios, dtype="float64")
    if candidats.size == 0:
        raise ValueError("ratios ne peut pas être vide")

    manquantes = [c for c in (price_column, volume_column) if c not in df.columns]
    if manquantes:
        return _missing_columns_result("split_anomaly", manquantes, severity)

    prix = _numeric(df[price_column])
    volume = _numeric(df[volume_column])

    rapport = prix.shift(1) / prix
    with np.errstate(invalid="ignore", divide="ignore"):
        ecarts = np.abs(rapport.to_numpy()[:, None] / candidats[None, :] - 1.0)
    # Une ligne sans rapport calculable, la première par exemple, reçoit un écart
    # infini : elle ne peut alors correspondre à aucun rapport candidat.
    ecarts = np.where(np.isnan(ecarts), np.inf, ecarts)
    indices = np.argmin(ecarts, axis=1)
    ecart_min = ecarts[np.arange(len(indices)), indices]
    candidat = candidats[indices]

    prix_saute = pd.Series(ecart_min <= ratio_tolerance, index=df.index)

    reference = volume.rolling(volume_window, min_periods=1).median().shift(1)
    attendu = reference * candidat
    facteur_volume = volume / reference
    with np.errstate(invalid="ignore", divide="ignore"):
        ecart_volume = (volume / attendu - 1.0).abs()
    volume_corrobore = (ecart_volume <= volume_tolerance).fillna(value=False)

    fautif = (prix_saute & ~volume_corrobore).astype(bool)
    n_violations = int(fautif.sum())
    if n_violations == 0:
        return CheckResult(
            name="split_anomaly",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=(
                f"aucun saut de prix proche d'un rapport de division sur {len(df)} lignes, "
                f"tolérance de prix {100.0 * ratio_tolerance:.4g} %"
            ),
        )

    echantillon = pd.DataFrame(
        {
            price_column: prix,
            volume_column: volume,
            "price_ratio": rapport,
            "matched_ratio": pd.Series(candidat, index=df.index),
            "volume_factor": facteur_volume,
        }
    ).loc[fautif]
    return CheckResult(
        name="split_anomaly",
        passed=False,
        severity=severity,
        n_violations=n_violations,
        sample=_head(echantillon, max_sample),
        message=(
            f"{n_violations} saut(s) de prix proche(s) d'un rapport de division sans variation "
            f"correspondante du volume, sur {len(df)} lignes"
        ),
    )


def check_stale_prices(
    df: pd.DataFrame,
    max_repeats: int = 5,
    *,
    column: str = "close",
    severity: Severity = Severity.WARNING,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    """Rend le verdict sur les prix identiques répétés plusieurs séances de suite.

    Le problème. Un fournisseur qui ne reçoit rien recopie souvent la dernière
    valeur connue. La série garde le bon nombre de lignes, et les rendements
    correspondants valent zéro. Le prix est faux et la volatilité mesurée
    baisse, donc le ratio de Sharpe monte, sans qu'aucune ligne ne manque.

    L'intuition. Un prix vraiment inchangé sur six séances est possible sur un
    titre qui ne s'échange pas. Il est presque impossible sur un titre liquide,
    dont le prix bouge d'au moins un cent chaque jour.

    Args:
        df: le tableau à contrôler.
        max_repeats: longueur maximale tolérée d'une plage de valeurs
            identiques. Une plage de longueur strictement supérieure est
            fautive. La valeur par défaut, 5, correspond à une semaine de
            bourse, et c'est un PRÉCEPTE, sans mesure derrière.
        column: la colonne contrôlée.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes fautives conservées.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` compte les LIGNES
        appartenant à une plage stagnante, et non le nombre de plages. Une
        stagnation de huit séances avec ``max_repeats = 5`` rend donc huit
        violations, pas une.

    Raises:
        ValueError: si ``max_repeats`` est inférieur à 1.

    Note:
        Ce qu'il attrape. Le recopiage d'un fournisseur, un titre suspendu de
        cotation, une série qui s'arrête avant sa dernière date.

        Ce qu'il laisse passer. Trois cas. Un prix qui bouge d'un cent chaque
        jour tout en étant recopié pour l'essentiel, puisque les valeurs ne sont
        alors pas identiques. Une stagnation de longueur exactement
        ``max_repeats``. Et une valeur figée sur une colonne non contrôlée, le
        volume par exemple, qui trahit le même défaut.

    Example:
        Sur la série ``[10 ; 11 ; 11 ; 11 ; 12]`` avec ``max_repeats = 2``, la
        plage de trois onze dépasse la tolérance et rend trois violations.
    """
    if max_repeats < 1:
        raise ValueError("max_repeats doit valoir au moins 1")
    if column not in df.columns:
        return _missing_columns_result("stale_prices", [column], severity)

    valeurs = df[column]
    absent = valeurs.isna().to_numpy(dtype=bool)
    # Une valeur absente rompt la plage, des deux côtés de la comparaison. Sur
    # un type nullable, « pd.NA != pd.NA » rend pd.NA et non True, et laisser
    # cette indétermination traverser le cumul efface les plages au lieu de les
    # couper. Le remplissage par True est donc la sémantique voulue, pas un
    # habillage : une valeur absente est une valeur qui a changé.
    change = valeurs.ne(valeurs.shift(1)).fillna(value=True).to_numpy(dtype=bool) | absent
    plage = pd.Series(np.cumsum(change), index=df.index)
    longueur = plage.map(plage.value_counts())
    fautif = pd.Series((longueur.to_numpy() > max_repeats) & ~absent, index=df.index)

    n_violations = int(fautif.sum())
    if n_violations == 0:
        return CheckResult(
            name="stale_prices",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=(
                f"aucune plage de plus de {max_repeats} valeurs identiques dans « {column} » "
                f"sur {len(df)} lignes"
            ),
        )

    n_plages = int(plage.loc[fautif].nunique())
    plus_longue = int(longueur.loc[fautif].max())
    return CheckResult(
        name="stale_prices",
        passed=False,
        severity=severity,
        n_violations=n_violations,
        sample=_head(df.loc[fautif], max_sample),
        message=(
            f"{n_violations} ligne(s) dans {n_plages} plage(s) stagnante(s) de « {column} », "
            f"la plus longue de {plus_longue} séances"
        ),
    )


def check_timezone(
    df: pd.DataFrame,
    expected: str | None,
    *,
    severity: Severity = Severity.ERROR,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    """Rend le verdict sur le fuseau de l'index, et refuse le mélange.

    Le problème. Un horodatage sans fuseau n'a pas de sens tant qu'on ne dit pas
    lequel est sous entendu. Mélanger dans un même index des horodatages naïfs
    et des horodatages avertis produit un index de type objet, dont le tri est
    incohérent et dont les comparaisons échouent ou mentent. Le décalage qui en
    résulte vaut plusieurs heures, donc une séance entière sur une série
    quotidienne.

    L'intuition. Le contrôle ne devine rien. Il compare le fuseau porté par
    l'index au fuseau attendu, déclaré par l'appelant, et refuse tout index qui
    n'en porte pas un seul.

    Args:
        df: le tableau à contrôler.
        expected: le nom du fuseau attendu, par exemple
            ``"America/New_York"``, ou ``None`` pour exiger un index naïf.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes fautives conservées.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` vaut 0 quand le fuseau est
        conforme. En cas de mélange, il compte les HORODATAGES minoritaires,
        c'est à dire ceux qu'il faudrait corriger. Sinon il vaut 1, l'index
        entier portant un fuseau unique mais faux.

    Note:
        Ce qu'il attrape. Un index naïf là où un fuseau était attendu, un index
        en UTC étiqueté New York, et un index de type objet mélangeant les deux
        natures.

        Ce qu'il laisse passer, et c'est le cas le plus coûteux. Un index averti
        du bon fuseau dont les instants sont faux. Localiser en
        ``America/New_York`` des horodatages qui étaient déjà en heure de New
        York décale la série d'exactement cinq heures, et le fuseau lu reste le
        bon. Seul un recoupement avec l'heure d'ouverture connue du marché
        détecte ce défaut.

    Example:
        Un index ``DatetimeIndex`` naïf contrôlé avec
        ``expected = "America/New_York"`` rend une violation et le message dit
        que l'index est naïf.
    """
    index = df.index
    attendu = "naïf" if expected is None else f"« {expected} »"

    if isinstance(index, pd.DatetimeIndex):
        tz = index.tz
        observe = "naïf" if tz is None else f"« {tz} »"
        conforme = (tz is None and expected is None) or (tz is not None and str(tz) == expected)
        if conforme:
            return CheckResult(
                name="timezone",
                passed=True,
                severity=severity,
                n_violations=0,
                sample=_empty_sample(),
                message=f"index temporel de fuseau {observe}, conforme à l'attendu",
            )
        return CheckResult(
            name="timezone",
            passed=False,
            severity=severity,
            n_violations=1,
            sample=_head(df, max_sample),
            message=f"index temporel de fuseau {observe}, alors que {attendu} était attendu",
        )

    horodatages = [v for v in index if isinstance(v, pd.Timestamp)]
    if len(horodatages) != len(index):
        return CheckResult(
            name="timezone",
            passed=False,
            severity=severity,
            n_violations=len(index),
            sample=_head(df, max_sample),
            message=(
                f"l'index est de type {index.dtype} et ne porte pas que des horodatages, "
                f"le fuseau {attendu} ne peut pas être vérifié"
            ),
        )

    avertis = [t for t in horodatages if t.tz is not None]
    naifs = [t for t in horodatages if t.tz is None]
    if avertis and naifs:
        minoritaires = min(len(avertis), len(naifs))
        return CheckResult(
            name="timezone",
            passed=False,
            severity=severity,
            n_violations=minoritaires,
            sample=_head(df, max_sample),
            message=(
                f"l'index mélange {len(naifs)} horodatage(s) naïf(s) et {len(avertis)} averti(s), "
                "un tel index ne se trie ni ne se compare de façon fiable"
            ),
        )
    nature = "naïf" if naifs else "averti"
    return CheckResult(
        name="timezone",
        passed=False,
        severity=severity,
        n_violations=len(index),
        sample=_head(df, max_sample),
        message=(
            f"l'index est un Index d'objets {nature}s et non un DatetimeIndex, "
            f"le fuseau {attendu} ne peut pas être vérifié de façon fiable"
        ),
    )


def check_positive_prices(
    df: pd.DataFrame,
    *,
    columns: Sequence[str] | None = None,
    allow_zero: bool = False,
    severity: Severity = Severity.ERROR,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    """Rend le verdict sur la positivité des colonnes de prix.

    Le problème. Un prix nul ou négatif casse tout ce qui suit. Le rendement
    calculé par rapport de prix devient infini ou change de signe, et le
    logarithme d'un prix négatif n'existe pas. Une seule ligne suffit à rendre
    une série entière inutilisable, souvent sans message d'erreur.

    L'intuition. Un prix de zéro n'est presque jamais un prix : c'est un champ
    vide rempli par défaut, ou une valeur manquante convertie en nombre.

    Args:
        df: le tableau à contrôler.
        columns: les colonnes de prix. Sans valeur, celles de
            :data:`OHLC_COLUMNS` présentes dans le tableau.
        allow_zero: ``True`` pour accepter un prix nul, ce qui est rarement
            justifié et n'est jamais le comportement par défaut.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes fautives conservées.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` compte les LIGNES dont au
        moins une colonne contrôlée est nulle ou négative. Une ligne dont trois
        colonnes sont fautives compte pour une.

    Note:
        Ce qu'il attrape. Les zéros de remplissage, les valeurs négatives nées
        d'un ajustement de dividende appliqué en soustraction sur un titre à
        faible prix, et les colonnes de prix converties depuis un champ vide.

        Ce qu'il laisse passer, et c'est important. Un prix négatif LÉGITIME.
        Le contrat à terme de pétrole WTI d'échéance mai 2020 s'est réglé à
        -37,63 dollars le 20 avril 2020, valeur RAPPORTÉE par le groupe CME. Ce
        contrôle signale donc à tort toute série de contrats à terme de
        matières premières couvrant cette date, et il ne doit pas être posé sur
        elle. Il laisse aussi passer un prix positif mais absurde, un dixième de
        cent par exemple, dont aucune règle simple ne dit s'il est faux. Et il
        laisse passer une valeur MANQUANTE, la comparaison d'un ``NaN`` à zéro
        rendant ``False`` en pandas comme en NumPy. Un trou de prix relève de
        :func:`check_column_schema` pour le type et d'un contrôle de complétude
        que ce module ne porte pas.

    Example:
        Sur une ligne où ``low`` vaut 0 et les trois autres prix sont positifs,
        le contrôle rend une violation.
    """
    if columns is None:
        cibles = [c for c in OHLC_COLUMNS if c in df.columns]
        if not cibles:
            return _missing_columns_result("positive_prices", list(OHLC_COLUMNS), severity)
    else:
        manquantes = [c for c in columns if c not in df.columns]
        if manquantes:
            return _missing_columns_result("positive_prices", manquantes, severity)
        cibles = list(columns)

    fautif = pd.Series(False, index=df.index)
    for nom in cibles:
        valeurs = _numeric(df[nom])
        mauvais = valeurs < 0 if allow_zero else valeurs <= 0
        fautif = fautif | mauvais.fillna(value=False)
    fautif = fautif.astype(bool)

    borne = "négatif" if allow_zero else "nul ou négatif"
    n_violations = int(fautif.sum())
    if n_violations == 0:
        return CheckResult(
            name="positive_prices",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=f"aucun prix {borne} dans {len(cibles)} colonne(s) sur {len(df)} lignes",
        )
    return CheckResult(
        name="positive_prices",
        passed=False,
        severity=severity,
        n_violations=n_violations,
        sample=_head(df.loc[fautif], max_sample),
        message=f"{n_violations} ligne(s) portant un prix {borne} sur {len(df)}",
    )


def check_column_schema(
    df: pd.DataFrame,
    schema: Mapping[str, str | None],
    *,
    allow_extra: bool = True,
    severity: Severity = Severity.ERROR,
    max_sample: int = MAX_SAMPLE_ROWS,
) -> CheckResult:
    """Rend le verdict sur la présence et le type des colonnes attendues.

    Le problème. Un fournisseur renomme une colonne, et le code qui la lisait
    lève une ``KeyError`` trois étages plus loin, dans un message qui ne dit pas
    quelle source a changé. Pire, une colonne de prix arrivée en texte se
    compare, se trie et s'affiche sans se plaindre, et rend des rendements
    faux.

    L'intuition. Le contrat d'un tableau se déclare avant de le lire, pas après
    l'avoir cassé.

    Args:
        df: le tableau à contrôler.
        schema: la correspondance colonne vers type attendu, exprimé comme
            pandas l'écrit, par exemple ``"float64"``, ``"int64"``,
            ``"datetime64[ns]"``. La valeur ``None`` n'exige que la présence de
            la colonne.
        allow_extra: ``True`` pour accepter des colonnes non déclarées, ce qui
            est le cas courant. ``False`` pour exiger le schéma exact, utile à
            l'entrée de la couche *gold*.
        severity: gravité déclarée du contrôle.
        max_sample: nombre de lignes conservées dans l'échantillon.

    Returns:
        Un :class:`CheckResult` dont ``n_violations`` compte les COLONNES
        fautives : absentes, de type inattendu, ou surnuméraires quand
        ``allow_extra`` vaut ``False``. L'échantillon porte trois colonnes,
        ``column``, ``expected`` et ``observed``.

    Note:
        Ce qu'il attrape. Une colonne renommée, une colonne disparue, une
        colonne de nombres arrivée en texte, une colonne surnuméraire quand
        c'est demandé.

        Ce qu'il laisse passer. Le type déclaré est comparé par son nom exact.
        Un ``"float64"`` attendu contre un ``"float32"`` observé est donc une
        violation, alors que les deux portent des flottants, et un ``"int64"``
        attendu contre un ``"Int64"`` observé en est une aussi. Le contrôle ne
        dit rien du CONTENU : une colonne ``float64`` entièrement vide passe,
        comme une colonne de dates toutes égales.

    Example:
        Avec ``schema = {"close": "float64"}`` sur un tableau dont ``close``
        porte du texte, le contrôle rend une violation dont l'échantillon porte
        la ligne ``close``, ``float64``, ``str``. Le nom du type est celui que
        pandas emploie, et il change d'une version à l'autre : pandas 3 nomme
        ``str`` ce que pandas 2 nommait ``object``.
    """
    lignes: list[dict[str, str]] = []
    for nom, type_attendu in schema.items():
        if nom not in df.columns:
            lignes.append({"column": nom, "expected": type_attendu or "présence", "observed": "absente"})
            continue
        if type_attendu is None:
            continue
        observe = str(df[nom].dtype)
        if observe != type_attendu:
            lignes.append({"column": nom, "expected": type_attendu, "observed": observe})

    if not allow_extra:
        for nom in df.columns:
            if nom not in schema:
                lignes.append({"column": str(nom), "expected": "absente", "observed": str(df[nom].dtype)})

    n_violations = len(lignes)
    if n_violations == 0:
        return CheckResult(
            name="column_schema",
            passed=True,
            severity=severity,
            n_violations=0,
            sample=_empty_sample(),
            message=f"{len(schema)} colonne(s) déclarées, toutes présentes et du type attendu",
        )
    noms = ", ".join(f"« {ligne['column']} »" for ligne in lignes[:5])
    return CheckResult(
        name="column_schema",
        passed=False,
        severity=severity,
        n_violations=n_violations,
        sample=_head(pd.DataFrame(lignes), max_sample),
        message=f"{n_violations} colonne(s) non conformes au schéma, dont {noms}",
    )


# ---------------------------------------------------------------------------
# L'agrégation
# ---------------------------------------------------------------------------


def run_checks(df: pd.DataFrame, checks: Sequence[Check]) -> QualityReport:
    """Fait tourner une suite de contrôles et rend leur rapport agrégé.

    Args:
        df: le tableau contrôlé, passé tel quel à chaque contrôle.
        checks: les contrôles, dans l'ordre d'exécution. Un contrôle est un
            appelable qui prend le tableau et rend un :class:`CheckResult`. Les
            arguments propres à un contrôle se fixent avec
            ``functools.partial``.

    Returns:
        Un :class:`QualityReport` portant les résultats dans l'ordre.

    Note:
        Une exception levée par un contrôle N'EST PAS attrapée. Un contrôle qui
        lève est un contrôle bogué, et transformer ce bogue en résultat rouge
        produirait un rapport qui a l'air complet sans l'être. Le laboratoire
        préfère la trace d'appel.

        Le rapport ne décide rien. C'est :meth:`QualityReport.raise_if_failed`
        qui arrête le pipeline, au seuil de gravité que l'appelant choisit.

    Example:
        .. code-block:: python

            from functools import partial

            rapport = run_checks(
                prix,
                [
                    check_monotonic_index,
                    partial(check_no_duplicate_timestamps, keys=["ticker"]),
                    partial(check_extreme_returns, threshold=0.45),
                ],
            )
            rapport.raise_if_failed(Severity.ERROR)
    """
    resultats = tuple(controle(df) for controle in checks)
    n_echecs = sum(1 for r in resultats if not r.passed)
    _log.info(
        "contrôles de qualité terminés",
        extra={"n_checks": len(resultats), "n_failed": n_echecs, "n_rows": len(df)},
    )
    return QualityReport(results=resultats)
