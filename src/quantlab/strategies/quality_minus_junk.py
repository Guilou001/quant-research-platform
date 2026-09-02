"""La qualité moins la camelote d'Asness, Frazzini et Pedersen (2019), en briques réutilisables.

**Le problème.** Le score de qualité agrège vingt et une variables comptables et
boursières en quatre composantes, puis les quatre en un seul nombre. Chaque
variable demande sa propre lecture des postes comptables, et chacune peut se
tromper de dénominateur sans que rien ne le signale. Écrire ces vingt et une
définitions dans un script d'étude garantit qu'aucune ne sera testée.

**Ce que le module contient.** La lecture des jeux trimestriels de la SEC et le
recollement des postes en variables comptables. Puis les variables de chaque
composante, le passage par les rangs, et le tri conditionnel taille puis
qualité. Il porte aussi le repli à trois composantes bâti sur les portefeuilles
triés de Kenneth French.

**Ce qu'il ne contient pas.** Aucune métrique financière n'est recalculée ici.
Le ratio de Sharpe, la rotation et les régressions viennent de
``quantlab.analytics``, conformément à la règle 12 du ``CLAUDE.md``. Aucun accès
réseau non plus : les fonctions de lecture prennent des octets déjà téléchargés,
ce qu'impose la règle d'architecture ADR-003.

**La règle qui gouverne tout le module.** Une donnée comptable entre par sa date
de dépôt, jamais par sa date de période. Les fonctions de ce module ne
choisissent jamais elles-mêmes quelle observation est visible : elles reçoivent
un panneau déjà filtré par :class:`quantlab.data.point_in_time.PITFrame`, dont
la colonne ``as_of`` porte la date de décision.

**Provenance.** Clifford S. Asness, Andrea Frazzini et Lasse Heje Pedersen,
« Quality Minus Junk », *Review of Accounting Studies*, 24(1), 2019, pages 34 à
112. Les définitions suivies sont celles de l'annexe A1 de la version de travail
du 19 juin 2014, la version publiée n'ayant pas été obtenue. La fiche interne
``docs/literature/asness_frazzini_pedersen_2019_qmj.md`` porte le détail et les
contradictions relevées entre les versions.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.signals.standardize import cross_sectional_rank, cross_sectional_zscore

__all__ = [
    "ANNUAL_ITEMS",
    "COMPONENT_VARIABLES",
    "DERA_FORMS",
    "DERA_TAGS",
    "QualityFactor",
    "accounting_items",
    "altman_z_score",
    "annual_records",
    "apply_size_screen",
    "component_scores",
    "dera_quarter_url",
    "dera_quarters",
    "drop_return_outliers",
    "frazzini_pedersen_beta",
    "growth_variables",
    "idiosyncratic_volatility",
    "lagged_records",
    "latest_records",
    "ohlson_o_score",
    "parse_dera_archive",
    "payout_variables",
    "profitability_variables",
    "quality_minus_junk",
    "quality_score",
    "quality_variables",
    "quarterly_roe_volatility",
    "rank_zscore",
    "safety_variables",
    "screen_in_force",
    "size_screens",
    "three_component_proxy",
    "variable_panels",
]

_LOG = get_logger(__name__)

#: Les formulaires retenus dans ``sub.txt``. Le rapport annuel porte les postes
#: de flux sur douze mois, le rapport trimestriel porte les bénéfices dont la
#: volatilité entre dans la composante de sûreté.
DERA_FORMS: tuple[str, ...] = ("10-K", "10-K/A", "10-Q", "10-Q/A")

#: Les colonnes gardées de ``sub.txt``. ``filed`` est la seule qui gouverne
#: l'accès à la donnée, et ``period`` ne sert qu'au diagnostic.
DERA_SUBMISSION_COLUMNS: tuple[str, ...] = (
    "adsh",
    "cik",
    "name",
    "sic",
    "form",
    "period",
    "fy",
    "fp",
    "filed",
    "accepted",
)

#: Les colonnes gardées de ``num.txt``.
DERA_NUMBER_COLUMNS: tuple[str, ...] = (
    "adsh",
    "tag",
    "version",
    "ddate",
    "qtrs",
    "uom",
    "segments",
    "coreg",
    "value",
)

#: Le recollement des balises XBRL vers les postes de l'annexe A1. L'ordre
#: compte : la première balise renseignée gagne, et les suivantes ne servent
#: qu'aux déposants qui n'emploient pas la première. Le nom à gauche est celui
#: de l'annexe, en majuscules, et il est employé partout ensuite.
ANNUAL_ITEMS: Mapping[str, tuple[str, ...]] = {
    "AT": ("Assets",),
    "ACT": ("AssetsCurrent",),
    "LCT": ("LiabilitiesCurrent",),
    "LT": ("Liabilities",),
    "CHE": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "MIB": ("MinorityInterest",),
    "PSTK": ("PreferredStockValue",),
    "SEQ_REPORTED": ("StockholdersEquity",),
    "SEQ_WITH_MINORITY": ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",),
    "RE": ("RetainedEarningsAccumulatedDeficit",),
    "DLTT": ("LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"),
    "DLC": ("LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings", "OtherShortTermBorrowings"),
    "TXP": ("AccruedIncomeTaxesCurrent", "TaxesPayableCurrent"),
    "SHROUT": ("CommonStockSharesOutstanding", "CommonStockSharesIssued"),
    "REVT": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueGoodsNet",
        "RevenuesNetOfInterestExpense",
        "InterestAndDividendIncomeOperating",
    ),
    "COGS": ("CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold", "CostOfServices"),
    "GROSS_PROFIT_REPORTED": ("GrossProfit",),
    "IB": ("NetIncomeLoss", "ProfitLoss"),
    "DP": (
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "Depreciation",
    ),
    "CAPX": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"),
    "EBIT": ("OperatingIncomeLoss",),
    "PT": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ),
}

#: Toutes les balises XBRL téléchargées, dédoublonnées.
DERA_TAGS: frozenset[str] = frozenset(tag for names in ANNUAL_ITEMS.values() for tag in names)

#: Les postes qui sont des soldes de bilan, donc datés d'un instant. Les autres
#: sont des flux sur douze mois. La distinction gouverne la lecture de ``qtrs``.
_INSTANT_ITEMS: frozenset[str] = frozenset(
    {
        "AT",
        "ACT",
        "LCT",
        "LT",
        "CHE",
        "MIB",
        "PSTK",
        "SEQ_REPORTED",
        "SEQ_WITH_MINORITY",
        "RE",
        "DLTT",
        "DLC",
        "TXP",
        "SHROUT",
    }
)

#: Les postes dont l'absence vaut zéro plutôt que valeur manquante. Une société
#: sans dette privilégiée n'écrit pas « zéro », elle n'écrit rien.
_ZERO_IF_ABSENT: frozenset[str] = frozenset({"MIB", "PSTK", "DLTT", "DLC", "TXP"})

#: Les variables de chaque composante, dans l'ordre de l'annexe A1.
COMPONENT_VARIABLES: Mapping[str, tuple[str, ...]] = {
    "profitability": ("gpoa", "roe", "roa", "cfoa", "gmar", "acc"),
    "growth": ("d_gpoa", "d_roe", "d_roa", "d_cfoa", "d_gmar", "d_acc"),
    "safety": ("bab", "ivol", "lev", "o_score", "z_score", "evol"),
    "payout": ("eiss", "diss", "npop"),
}

#: Les coefficients de la cote O d'Ohlson (1980), dans l'ordre de l'annexe A1.
_OHLSON = {
    "const": -1.32,
    "log_adjasset": -0.407,
    "tlta": 6.03,
    "wcta": -1.43,
    "clca": 0.076,
    "oeneg": -1.72,
    "nita": -2.37,
    "futl": -1.83,
    "intwo": 0.285,
    "chin": -0.521,
}

#: Les coefficients de la cote Z d'Altman (1968), version de l'annexe A1.
_ALTMAN = {"wc": 1.2, "re": 1.4, "ebit": 3.3, "me": 0.6, "sale": 1.0}


# --------------------------------------------------------------------------- #
# La lecture des jeux trimestriels de la SEC
# --------------------------------------------------------------------------- #


def dera_quarter_url(base_url: str, year: int, quarter: int) -> str:
    """Rend l'adresse du jeu trimestriel de la SEC pour un trimestre donné.

    Args:
        base_url: la racine du dossier, sans barre oblique finale.
        year: l'année civile du dépôt, pas celle de la période décrite.
        quarter: le trimestre civil du dépôt, de 1 à 4.

    Returns:
        L'adresse du fichier zip.

    Raises:
        ConfigError: si le trimestre sort de l'intervalle admis.

    Example:
        >>> dera_quarter_url("https://x/y", 2015, 2)
        'https://x/y/2015q2.zip'
    """
    if quarter not in (1, 2, 3, 4):
        raise ConfigError(f"trimestre invalide : {quarter}, attendu entre 1 et 4")
    return f"{base_url.rstrip('/')}/{int(year)}q{int(quarter)}.zip"


def dera_quarters(
    first_year: int, first_quarter: int, last_year: int, last_quarter: int
) -> tuple[tuple[int, int], ...]:
    """Rend la suite des trimestres à télécharger, bornes comprises.

    Args:
        first_year: l'année du premier trimestre.
        first_quarter: le premier trimestre, de 1 à 4.
        last_year: l'année du dernier trimestre.
        last_quarter: le dernier trimestre, de 1 à 4.

    Returns:
        Le couple année et trimestre de chaque jeu, dans l'ordre du temps.

    Raises:
        ConfigError: si la borne haute précède la borne basse.

    Example:
        >>> dera_quarters(2015, 3, 2016, 1)
        ((2015, 3), (2015, 4), (2016, 1))
    """
    start, end = (int(first_year), int(first_quarter)), (int(last_year), int(last_quarter))
    if start > end:
        raise ConfigError(f"le trimestre de départ {start} suit celui d'arrivée {end}")
    out: list[tuple[int, int]] = []
    year, quarter = start
    while (year, quarter) <= end:
        out.append((year, quarter))
        quarter += 1
        if quarter == 5:
            year, quarter = year + 1, 1
    return tuple(out)


def parse_dera_archive(
    payload: bytes,
    *,
    tags: frozenset[str] = DERA_TAGS,
    forms: Sequence[str] = DERA_FORMS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lit un jeu trimestriel de la SEC et rend ses deux tables utiles.

    **Le problème.** Le fichier ``num.txt`` d'un trimestre porte deux à trois
    millions de lignes et trois cents mégaoctets. Le garder entier pour en
    employer un centième coûte de la mémoire sans rien apporter.

    **Ce que la fonction retire, et pourquoi.** Trois filtres, chacun pour une
    raison distincte. Les balises hors de ``tags``, parce qu'aucune variable ne
    les consomme. Les lignes dont ``segments`` ou ``coreg`` est renseigné, parce
    qu'elles décrivent un secteur ou une filiale et non le groupe consolidé. Les
    taxonomies hors ``us-gaap``, parce qu'une balise maison porte le même nom
    sans porter la même définition.

    **Le piège du vide.** Les colonnes ``segments`` et ``coreg`` sont vides,
    non manquantes, dans les fichiers de la SEC. Un filtre écrit avec ``isna``
    ne garde donc AUCUNE ligne, sans lever la moindre erreur. Le test du module
    fige ce comportement sur une archive construite à la main.

    Args:
        payload: les octets du fichier zip, tels que la SEC les rend.
        tags: les balises XBRL gardées.
        forms: les formulaires gardés.

    Returns:
        Le couple des dépôts et des valeurs numériques, dans cet ordre.

    Raises:
        DataQualityError: si l'archive ne porte pas ``sub.txt`` et ``num.txt``.
    """
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        present = set(archive.namelist())
        missing = {"sub.txt", "num.txt"} - present
        if missing:
            raise DataQualityError(f"archive DERA incomplète, il manque {sorted(missing)}")
        submissions = pd.read_csv(
            io.BytesIO(archive.read("sub.txt")),
            sep="\t",
            usecols=list(DERA_SUBMISSION_COLUMNS),
            encoding="latin-1",
            low_memory=False,
        )
        numbers = pd.read_csv(
            io.BytesIO(archive.read("num.txt")),
            sep="\t",
            usecols=list(DERA_NUMBER_COLUMNS),
            encoding="latin-1",
            low_memory=False,
        )

    submissions = submissions[submissions["form"].isin(list(forms))].copy()
    submissions["adsh"] = submissions["adsh"].astype("string")
    submissions["cik"] = pd.to_numeric(submissions["cik"], errors="coerce").astype("Int64")

    for column in ("segments", "coreg", "version", "tag", "uom", "adsh"):
        numbers[column] = numbers[column].astype("string").fillna("")
    keep = (
        numbers["tag"].isin(tags)
        & numbers["version"].str.startswith("us-gaap")
        & (numbers["segments"] == "")
        & (numbers["coreg"] == "")
        & numbers["uom"].isin(["USD", "shares"])
        & numbers["adsh"].isin(set(submissions["adsh"]))
        & numbers["value"].notna()
    )
    numbers = numbers.loc[keep, ["adsh", "tag", "ddate", "qtrs", "uom", "value"]].copy()
    numbers = numbers.drop_duplicates(subset=["adsh", "tag", "ddate", "qtrs"], keep="last")
    _LOG.info(
        "archive DERA lue",
        extra={"submissions": len(submissions), "numbers": len(numbers)},
    )
    return submissions.reset_index(drop=True), numbers.reset_index(drop=True)


def _coalesce(frame: pd.DataFrame, names: Sequence[str]) -> pd.Series:
    """Rend la première colonne renseignée parmi ``names``, ligne par ligne."""
    out = pd.Series(np.nan, index=frame.index, dtype="float64")
    for name in names:
        if name in frame.columns:
            out = out.where(out.notna(), pd.to_numeric(frame[name], errors="coerce"))
    return out


def accounting_items(pivoted: pd.DataFrame) -> pd.DataFrame:
    """Recolle les balises XBRL en postes comptables nommés comme l'annexe A1.

    **Le problème.** Un même poste porte plusieurs balises selon le déposant.
    Le chiffre d'affaires s'écrit ``Revenues`` chez les uns et
    ``RevenueFromContractWithCustomerExcludingAssessedTax`` chez les autres, et
    ne lire que la première perd les deux tiers de l'échantillon.

    **La règle de recollement.** La première balise renseignée de
    :data:`ANNUAL_ITEMS` gagne. L'ordre est celui de la fréquence mesurée dans
    les jeux, la balise la plus répandue en premier.

    **Les deux postes déduits.** Les fonds propres comptables valent les
    capitaux propres déclarés, ou à défaut ceux qui incluent les intérêts
    minoritaires moins ces intérêts, le tout moins les actions privilégiées. Le
    profit brut vaut le poste déclaré, ou à défaut les ventes moins le coût des
    ventes.

    Args:
        pivoted: un tableau dont les colonnes sont des balises XBRL.

    Returns:
        Un tableau aux colonnes de :data:`ANNUAL_ITEMS`, plus ``BE``, ``GP``,
        ``WC`` et ``TOTD``, sur le même index.
    """
    out = pd.DataFrame(index=pivoted.index)
    for item, names in ANNUAL_ITEMS.items():
        out[item] = _coalesce(pivoted, names)
    for item in _ZERO_IF_ABSENT:
        out[item] = out[item].fillna(0.0)

    equity = out["SEQ_REPORTED"]
    out["SEQ"] = equity.where(equity.notna(), out["SEQ_WITH_MINORITY"] - out["MIB"])
    out["BE"] = out["SEQ"] - out["PSTK"]
    gross = out["GROSS_PROFIT_REPORTED"]
    out["GP"] = gross.where(gross.notna(), out["REVT"] - out["COGS"])
    out["SALE"] = out["REVT"]
    out["WC"] = out["ACT"] - out["LCT"] - out["CHE"] + out["DLC"] + out["TXP"]
    out["TOTD"] = out["DLTT"] + out["DLC"] + out["MIB"] + out["PSTK"]
    return out.drop(columns=["SEQ_REPORTED", "SEQ_WITH_MINORITY", "GROSS_PROFIT_REPORTED"])


def annual_records(submissions: pd.DataFrame, numbers: pd.DataFrame) -> pd.DataFrame:
    """Assemble les exercices annuels déclarés, avec leur date de disponibilité.

    **Ce qu'est une ligne.** Un exercice d'une société, tel qu'un dépôt donné
    l'a publié. Le même exercice apparaît plusieurs fois quand plusieurs dépôts
    le décrivent, une fois dans son propre rapport annuel puis en comparatif
    dans les suivants. Ce n'est pas un doublon : chaque version porte sa propre
    date de disponibilité, et c'est ce qui rend le registre point-in-time.

    **Comment un exercice est reconnu.** Par la coïncidence d'un solde de bilan
    daté d'un instant et d'un flux couvrant quatre trimestres, tous deux clos à
    la même date. Aucune convention de fin d'exercice n'est supposée, ce qui
    évite de perdre les sociétés dont l'exercice ne finit pas en décembre.

    Args:
        submissions: la table des dépôts, telle que rend :func:`parse_dera_archive`.
        numbers: la table des valeurs numériques, de la même fonction.

    Returns:
        Un tableau long portant ``entity_id``, ``period_end``, ``available_from``,
        le formulaire, le code d'activité et tous les postes comptables.

    Raises:
        InsufficientDataError: si aucun exercice ne se laisse assembler.
    """
    annual_forms = submissions[submissions["form"].isin(["10-K", "10-K/A"])]
    numbers = numbers[numbers["adsh"].isin(set(annual_forms["adsh"]))]
    if numbers.empty:
        raise InsufficientDataError("aucune valeur numérique rattachée à un rapport annuel")

    instant_tags = {tag for item in _INSTANT_ITEMS for tag in ANNUAL_ITEMS[item]}
    instants = numbers[(numbers["qtrs"] == 0) & numbers["tag"].isin(instant_tags)]
    flows = numbers[(numbers["qtrs"] == 4) & ~numbers["tag"].isin(instant_tags)]
    if instants.empty or flows.empty:
        raise InsufficientDataError("les soldes ou les flux annuels manquent dans le jeu")

    left = instants.pivot(index=["adsh", "ddate"], columns="tag", values="value")  # noqa: PD010
    right = flows.pivot(index=["adsh", "ddate"], columns="tag", values="value")  # noqa: PD010
    joined = left.join(right, how="inner").reset_index()
    if joined.empty:
        raise InsufficientDataError("aucun exercice n'associe un bilan et un compte de résultat")

    items = accounting_items(joined)
    items.insert(0, "adsh", joined["adsh"].to_numpy())
    items.insert(1, "ddate", joined["ddate"].to_numpy())
    merged = items.merge(
        annual_forms[["adsh", "cik", "name", "sic", "form", "filed"]], on="adsh", how="inner"
    )
    merged["entity_id"] = merged["cik"].astype("Int64")
    merged["period_end"] = pd.to_datetime(merged["ddate"].astype("int64").astype(str), format="%Y%m%d")
    merged["available_from"] = pd.to_datetime(merged["filed"].astype("int64").astype(str), format="%Y%m%d")
    merged = merged[merged["available_from"] >= merged["period_end"]]
    merged = merged[merged["entity_id"].notna() & merged["AT"].notna() & (merged["AT"] > 0.0)]
    ordered = ["entity_id", "period_end", "available_from", "adsh", "name", "sic", "form"]
    rest = [c for c in merged.columns if c not in {*ordered, "cik", "ddate", "filed"}]
    return (
        merged[[*ordered, *rest]]
        .sort_values(["entity_id", "period_end", "available_from"])
        .reset_index(drop=True)
    )


def quarterly_roe_volatility(
    submissions: pd.DataFrame,
    numbers: pd.DataFrame,
    dates: Sequence[pd.Timestamp],
    *,
    max_quarters: int = 60,
    min_quarters: int = 12,
) -> pd.DataFrame:
    """Rend l'écart type du rendement trimestriel des fonds propres, par date de décision.

    **La variable.** L'annexe A1 définit ``EVOL`` comme l'écart type du
    rendement trimestriel des fonds propres sur soixante trimestres, douze
    observations non manquantes étant exigées. La composante de sûreté en prend
    l'opposé, une volatilité faible étant une marque de sûreté.

    **Ce que la fonction lit.** Le bénéfice d'un trimestre est un flux couvrant
    un trimestre, les fonds propres sont un solde daté du même jour. Le rapport
    des deux est le rendement trimestriel.

    **Une limite mesurée, et déclarée.** La plupart des déposants ne balisent
    pas leur quatrième trimestre, qui n'apparaît que dans le total annuel. La
    série trimestrielle sous-représente donc les quatrièmes trimestres, et
    l'étude publie cette part.

    Args:
        submissions: la table des dépôts.
        numbers: la table des valeurs numériques.
        dates: les dates de décision, en général les fins de mois.
        max_quarters: la longueur de la fenêtre, en trimestres.
        min_quarters: le nombre minimal d'observations exigé.

    Returns:
        Un tableau long aux colonnes ``as_of``, ``entity_id``, ``evol_raw`` et
        ``evol_count``.
    """
    income_tags = list(ANNUAL_ITEMS["IB"])
    equity_tags = [*ANNUAL_ITEMS["SEQ_REPORTED"], *ANNUAL_ITEMS["SEQ_WITH_MINORITY"]]
    income = numbers[(numbers["qtrs"] == 1) & numbers["tag"].isin(income_tags)]
    equity = numbers[(numbers["qtrs"] == 0) & numbers["tag"].isin(equity_tags)]
    if income.empty or equity.empty:
        return pd.DataFrame(columns=["as_of", "entity_id", "evol_raw", "evol_count"])

    left = income.pivot(index=["adsh", "ddate"], columns="tag", values="value")  # noqa: PD010
    right = equity.pivot(index=["adsh", "ddate"], columns="tag", values="value")  # noqa: PD010
    joined = left.join(right, how="inner").reset_index()
    ib = _coalesce(joined, income_tags)
    be = _coalesce(joined, list(ANNUAL_ITEMS["SEQ_REPORTED"]))
    be = be.where(be.notna(), _coalesce(joined, list(ANNUAL_ITEMS["SEQ_WITH_MINORITY"])))
    frame = pd.DataFrame(
        {
            "adsh": joined["adsh"].to_numpy(),
            "ddate": joined["ddate"].to_numpy(),
            "roe": np.where(be.to_numpy() > 0.0, ib.to_numpy() / be.to_numpy(), np.nan),
        }
    )
    frame = frame.merge(submissions[["adsh", "cik", "filed"]], on="adsh", how="inner")
    frame = frame.dropna(subset=["roe", "cik"])
    frame["entity_id"] = frame["cik"].astype("Int64")
    frame["period_end"] = pd.to_datetime(frame["ddate"].astype("int64").astype(str), format="%Y%m%d")
    frame["available_from"] = pd.to_datetime(frame["filed"].astype("int64").astype(str), format="%Y%m%d")
    frame = frame[frame["available_from"] >= frame["period_end"]]
    frame = frame.sort_values(["entity_id", "period_end", "available_from"])
    frame = frame.drop_duplicates(subset=["entity_id", "period_end"], keep="first")

    rows: list[pd.DataFrame] = []
    for moment in pd.DatetimeIndex(sorted(dates)):
        window_start = moment - pd.DateOffset(months=3 * max_quarters)
        visible = frame[
            (frame["available_from"] <= moment)
            & (frame["period_end"] > window_start)
            & (frame["period_end"] <= moment)
        ]
        if visible.empty:
            continue
        grouped = visible.groupby("entity_id", observed=True)["roe"]
        block = pd.DataFrame({"evol_raw": grouped.std(ddof=1), "evol_count": grouped.count()})
        block = block[block["evol_count"] >= min_quarters].reset_index()
        block.insert(0, "as_of", moment)
        rows.append(block)
    if not rows:
        return pd.DataFrame(columns=["as_of", "entity_id", "evol_raw", "evol_count"])
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------- #
# Le crible d'univers, point-in-time
# --------------------------------------------------------------------------- #


def size_screens(
    records: pd.DataFrame,
    screen_dates: Sequence[pd.Timestamp],
    *,
    max_names: int,
    lookback_years: int = 2,
) -> dict[pd.Timestamp, frozenset[int]]:
    """Rend, pour chaque date de crible, l'univers connaissable ce jour-là.

    **Le problème que la fonction résout.** Un crible bâti une fois pour toutes,
    sur la réunion des sélections annuelles, fait entrer trop tôt les sociétés
    qui n'ont grossi que plus tard. Le score se calcule alors sur un univers que
    personne ne connaissait, et la sélection porte une information future.

    **La règle.** À chaque date de crible, seuls comptent les exercices déjà
    déposés. Le dernier exercice connu de chaque société est retenu, les
    exercices trop anciens sont écartés, et les deux classements par actif et
    par chiffre d'affaires se réunissent.

    Args:
        records: les exercices annuels, portant ``entity_id``, ``available_from``,
            ``period_end``, ``AT`` et ``REVT``.
        screen_dates: les dates auxquelles le crible se recalcule.
        max_names: le nombre de sociétés retenues par classement.
        lookback_years: l'âge maximal de la fin d'exercice retenue, en années.

    Returns:
        Un dictionnaire de la date de crible vers l'ensemble des identifiants.

    Raises:
        ConfigError: si une colonne obligatoire manque, ou si ``max_names`` est
            nul ou négatif.

    Example:
        >>> frame = pd.DataFrame(
        ...     {
        ...         "entity_id": [1, 2],
        ...         "available_from": pd.to_datetime(["2015-02-01", "2016-02-01"]),
        ...         "period_end": pd.to_datetime(["2014-12-31", "2015-12-31"]),
        ...         "AT": [10.0, 20.0],
        ...         "REVT": [5.0, 9.0],
        ...     }
        ... )
        >>> screens = size_screens(frame, [pd.Timestamp("2015-06-30")], max_names=5)
        >>> sorted(screens[pd.Timestamp("2015-06-30")])
        [1]
    """
    required = {"entity_id", "available_from", "period_end", "AT", "REVT"}
    missing = required - set(records.columns)
    if missing:
        raise ConfigError(f"colonnes absentes du registre : {sorted(missing)}")
    if int(max_names) <= 0:
        raise ConfigError(f"max_names doit être strictement positif, reçu {max_names}")
    out: dict[pd.Timestamp, frozenset[int]] = {}
    for moment in screen_dates:
        stamp = pd.Timestamp(moment)
        known = records[records["available_from"] <= stamp]
        last = known.sort_values(["entity_id", "period_end", "available_from"])
        last = last.groupby("entity_id", observed=True).tail(1)
        last = last[last["period_end"] >= stamp - pd.DateOffset(years=int(lookback_years))]
        keep = set(last.nlargest(int(max_names), "AT")["entity_id"].dropna().astype("int64"))
        with_sales = last.dropna(subset=["REVT"])
        keep |= set(with_sales.nlargest(int(max_names), "REVT")["entity_id"].dropna().astype("int64"))
        out[stamp] = frozenset(keep)
    return out


def screen_in_force(screens: Mapping[pd.Timestamp, frozenset[int]], moment: pd.Timestamp) -> frozenset[int]:
    """Rend le crible en vigueur à une date, c'est-à-dire le dernier antérieur.

    Un crible recalculé chaque fin de juin gouverne les douze mois qui le
    suivent. Une date antérieure au premier crible reçoit ce premier crible,
    puisque rien de plus ancien n'existe.

    Args:
        screens: les cribles, indexés par leur date de calcul.
        moment: la date de formation à couvrir.

    Returns:
        L'ensemble des identifiants admis à cette date.

    Raises:
        ConfigError: si aucun crible n'est fourni.
    """
    if not screens:
        raise ConfigError("aucun crible d'univers fourni")
    dates = sorted(screens)
    stamp = pd.Timestamp(moment)
    earlier = [d for d in dates if d <= stamp]
    return screens[earlier[-1]] if earlier else screens[dates[0]]


def apply_size_screen(
    variables: pd.DataFrame,
    screens: Mapping[pd.Timestamp, frozenset[int]],
    *,
    as_of_col: str = "as_of",
    entity_col: str = "entity_id",
) -> pd.DataFrame:
    """Retire du tableau les sociétés hors du crible en vigueur à leur date.

    Le filtre s'applique AVANT le passage par les rangs, sans quoi la cote d'une
    société dépendrait de sociétés qui n'appartenaient pas encore à l'univers.

    Args:
        variables: le tableau long des variables, une ligne par date et société.
        screens: les cribles rendus par :func:`size_screens`.
        as_of_col: le nom de la colonne de date de décision.
        entity_col: le nom de la colonne d'identifiant.

    Returns:
        Le même tableau, privé des lignes hors crible.

    Raises:
        ConfigError: si une colonne obligatoire manque.
    """
    missing = {as_of_col, entity_col} - set(variables.columns)
    if missing:
        raise ConfigError(f"colonnes absentes du tableau : {sorted(missing)}")
    admis = variables[as_of_col].map(lambda moment: screen_in_force(screens, moment))
    entities = variables[entity_col].astype("int64")
    mask = [entity in allowed for entity, allowed in zip(entities, admis, strict=True)]
    return variables[pd.Series(mask, index=variables.index)].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# La sélection point-in-time des exercices
# --------------------------------------------------------------------------- #


def latest_records(panel: pd.DataFrame, *, max_staleness_days: int = 548) -> pd.DataFrame:
    """Rend, par date de décision et par société, le dernier exercice connaissable.

    **Ce que la fonction suppose.** Le panneau reçu vient de
    :meth:`quantlab.data.point_in_time.PITFrame.panel`, donc chaque ligne était
    déjà publique à sa date ``as_of``. La fonction ne filtre pas sur la
    disponibilité : elle choisit seulement, parmi ce qui est visible, l'exercice
    le plus récent.

    **Pourquoi une limite d'ancienneté.** Une société qui cesse de déposer garde
    indéfiniment son dernier exercice dans le registre. Sans borne, elle resterait
    dans l'univers des années après sa disparition, avec des chiffres périmés.

    Args:
        panel: le panneau point-in-time, portant ``as_of``, ``entity_id`` et
            ``period_end``.
        max_staleness_days: l'âge maximal de la fin d'exercice, en jours.

    Returns:
        Un tableau à une ligne par couple date et société.

    Raises:
        ConfigError: si une colonne obligatoire manque.
    """
    required = {"as_of", "entity_id", "period_end"}
    missing = required - set(panel.columns)
    if missing:
        raise ConfigError(f"colonnes absentes du panneau : {sorted(missing)}")
    age = (panel["as_of"] - panel["period_end"]).dt.days
    fresh = panel[(age >= 0) & (age <= int(max_staleness_days))]
    ordered = fresh.sort_values(["as_of", "entity_id", "period_end"])
    return ordered.groupby(["as_of", "entity_id"], observed=True).tail(1).reset_index(drop=True)


def lagged_records(
    panel: pd.DataFrame,
    current: pd.DataFrame,
    *,
    years: int = 5,
    tolerance_days: int = 200,
) -> pd.DataFrame:
    """Rend l'exercice clos environ ``years`` années avant l'exercice courant.

    **Pourquoi une tolérance.** Un exercice de cinquante-deux semaines dérive de
    quelques jours par an, et certaines sociétés changent de date de clôture.
    Exiger la date exacte perdrait ces sociétés sans raison.

    **La règle de choix.** Parmi les exercices visibles à la même date de
    décision, celui dont la fin est la plus proche de la cible, à condition que
    l'écart tienne dans la tolérance.

    Args:
        panel: le panneau point-in-time complet.
        current: le tableau rendu par :func:`latest_records`.
        years: le nombre d'années de recul.
        tolerance_days: l'écart maximal accepté autour de la cible.

    Returns:
        Un tableau aux mêmes colonnes que ``panel``, à une ligne par couple date
        et société trouvé, les autres colonnes préfixées par ``lag_``.
    """
    target = current[["as_of", "entity_id", "period_end"]].copy()
    target["target_end"] = target["period_end"] - pd.DateOffset(years=int(years))
    merged = panel.merge(target[["as_of", "entity_id", "target_end"]], on=["as_of", "entity_id"], how="inner")
    merged["gap"] = (merged["period_end"] - merged["target_end"]).dt.days.abs()
    merged = merged[merged["gap"] <= int(tolerance_days)]
    merged = merged.sort_values(["as_of", "entity_id", "gap"])
    chosen = merged.groupby(["as_of", "entity_id"], observed=True).head(1)
    keys = ["as_of", "entity_id"]
    values = [c for c in chosen.columns if c not in {*keys, "target_end", "gap"}]
    out = chosen[[*keys, *values]].rename(columns={c: f"lag_{c}" for c in values})
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Les variables de marché de la composante de sûreté
# --------------------------------------------------------------------------- #


def usable_prices(panel: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Écarte les prix nuls ou négatifs, qui fabriquent des rendements impossibles.

    **Le problème, mesuré.** Un fournisseur de prix gratuit rend parfois zéro,
    ou un nombre négatif, pour une séance d'un titre. Le rapport de deux prix
    successifs vaut alors l'infini ou un nombre inférieur à moins un, et le
    rendement mensuel du titre passe de moins quatre cent quarante pour cent à
    plus l'infini. Aucune de ces deux valeurs n'existe pour une action ordinaire,
    qui ne peut pas perdre plus que sa valeur.

    **Ce que la fonction fait, et ne fait pas.** Elle remplace par une valeur
    manquante tout prix qui n'est pas fini et strictement positif. Elle ne
    corrige pas le prix, elle le retire : inventer une valeur serait un
    comblement spéculatif, et le titre sort simplement de l'univers ce mois-là.

    **Pourquoi ce contrôle n'est pas facultatif.** Un seul rendement infini dans
    une jambe pondérée également suffit à rendre infini le rendement du
    portefeuille, puis toute statistique qui en dépend. Le test du module le
    fige sur un cas construit.

    Args:
        panel: les prix, dates en lignes et titres en colonnes.

    Returns:
        Le couple du panneau nettoyé et du nombre de cellules retirées.
    """
    values = panel.to_numpy(dtype="float64", copy=True)
    bad = ~(np.isfinite(values) & (values > 0.0))
    removed = int(bad.sum() - np.isnan(panel.to_numpy(dtype="float64")).sum())
    values[bad] = np.nan
    cleaned = pd.DataFrame(values, index=panel.index, columns=panel.columns)
    if removed:
        _LOG.warning("prix non exploitables retirés", extra={"cells": removed})
    return cleaned, removed


def drop_return_outliers(
    returns: pd.DataFrame, *, max_return: float, min_return: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retire les rendements qu'aucune action ordinaire ne peut produire.

    **Le problème, mesuré sur trois cas nommés.** Un fournisseur gratuit
    raccorde parfois deux titres sous le même symbole. Chord Energy sort de
    faillite en novembre 2020 avec un regroupement d'actions, et son cours passe
    de onze cents à 34,20 dollars d'un mois à l'autre. Cela fabrique un rendement
    de trente mille pour cent que personne n'a touché. Le même fichier porte un
    prix ajusté NÉGATIF pour un titre, et un prix ajusté exactement NUL pour un
    autre sur onze mois de cotation continue.

    **Pourquoi ce n'est pas un détail.** Une jambe pondérée également de deux
    cent soixante titres transforme un rendement de trois cents fois en cent
    dix-neuf points de rendement de portefeuille, sur un seul mois. Le facteur
    entier bascule alors sur une ligne de données fausse.

    **La règle, et ce qu'elle coûte.** Toute observation hors des bornes
    déclarées devient manquante, donc le titre sort de l'univers ce mois-là. La
    règle retire aussi les rares hausses réelles de cette ampleur, et c'est le
    prix assumé d'un filtre qui ne dépend d'aucune source externe.

    Args:
        returns: les rendements simples, dates en lignes et titres en colonnes.
        max_return: la borne haute, en fraction, par exemple 3,0 pour trois cents
            pour cent.
        min_return: la borne basse, jamais inférieure à moins un.

    Returns:
        Le couple des rendements nettoyés et du tableau des observations
        retirées, aux colonnes ``date``, ``entity`` et ``value``.

    Raises:
        ConfigError: si les deux bornes ne sont pas ordonnées, ou si la borne
            basse descend sous moins un.
    """
    if min_return < -1.0:
        raise ConfigError(f"min_return vaut {min_return}, un rendement ne descend pas sous moins un")
    if max_return <= min_return:
        raise ConfigError(f"bornes non ordonnées : {min_return} et {max_return}")
    values = returns.to_numpy(dtype="float64", copy=True)
    finite = np.isfinite(values)
    bad = finite & ((values > max_return) | (values < min_return))
    rows, cols = np.nonzero(bad)
    removed = pd.DataFrame(
        {
            "date": returns.index[rows],
            "entity": returns.columns[cols],
            "value": values[rows, cols],
        }
    ).sort_values("value", ascending=False, key=abs)
    values[bad] = np.nan
    cleaned = pd.DataFrame(values, index=returns.index, columns=returns.columns)
    if len(removed):
        _LOG.warning("rendements hors bornes retirés", extra={"cells": len(removed)})
    return cleaned, removed.reset_index(drop=True)


def _window_slices(index: pd.DatetimeIndex, moment: pd.Timestamp, length: int) -> slice:
    """Rend la tranche des ``length`` dernières observations à ``moment`` compris."""
    stop = int(index.searchsorted(moment, side="right"))
    return slice(max(0, stop - length), stop)


def frazzini_pedersen_beta(
    daily_returns: pd.DataFrame,
    market: pd.Series,
    dates: Sequence[pd.Timestamp],
    *,
    volatility_window: int = 252,
    correlation_window: int = 1260,
    overlap: int = 3,
    min_volatility_days: int = 120,
    min_correlation_days: int = 750,
    shrinkage_weight: float = 0.6,
    shrinkage_target: float = 1.0,
) -> pd.DataFrame:
    r"""Rend le bêta de Frazzini et Pedersen à chaque date de décision.

    **Le problème.** Le bêta d'une régression sur un an est bruité, et celui
    d'une régression sur cinq ans est périmé. Frazzini et Pedersen séparent les
    deux morceaux : la volatilité se mesure court, la corrélation se mesure long.

    **La formule.**

    .. math::

        \hat{\beta}_i = \hat{\rho}_{i,m}\, \frac{\hat{\sigma}_i}{\hat{\sigma}_m},
        \qquad
        \beta_i = w\, \hat{\beta}_i + (1 - w)\, \beta^{\ast}

    **Les variables.** :math:`\hat{\sigma}_i` est l'écart type des rendements
    logarithmiques quotidiens sur un an, :math:`\hat{\rho}_{i,m}` la corrélation
    des rendements logarithmiques cumulés sur trois jours mesurée sur cinq ans,
    :math:`w` le poids de rétrécissement et :math:`\beta^{\ast}` sa cible.

    **Pourquoi trois jours pour la corrélation.** Les titres peu liquides
    réagissent au marché avec un jour de retard. Cumuler trois jours ramasse
    cette réaction retardée, que la corrélation quotidienne perdrait.

    **Ce que la fonction ne fait pas.** Elle ne calcule rien entre deux dates de
    décision. Chaque fenêtre s'arrête à la date demandée, incluse, ce qui est la
    forme la plus simple de garantie d'absence d'information future.

    **Comment vérifier.** Prendre un titre dont les rendements valent exactement
    deux fois ceux du marché. La corrélation vaut alors un et le rapport des
    écarts types vaut deux, donc le bêta brut vaut deux. Le bêta rétréci vaut
    :math:`0{,}6 \times 2 + 0{,}4 = 1{,}6`, et le test du module le vérifie.

    Args:
        daily_returns: les rendements simples quotidiens, dates en lignes.
        market: le rendement simple quotidien du marché.
        dates: les dates de décision.
        volatility_window: la fenêtre d'écart type, en séances.
        correlation_window: la fenêtre de corrélation, en séances.
        overlap: le nombre de séances cumulées pour la corrélation.
        min_volatility_days: le nombre minimal de séances pour l'écart type.
        min_correlation_days: le nombre minimal de fenêtres pour la corrélation.
        shrinkage_weight: le poids du bêta estimé.
        shrinkage_target: la cible du rétrécissement.

    Returns:
        Un tableau dont l'index porte les dates demandées et les colonnes les
        titres.

    Raises:
        ConfigError: si une fenêtre ou un chevauchement n'est pas positif.
    """
    if volatility_window <= 1 or correlation_window <= 1 or overlap < 1:
        raise ConfigError("les fenêtres et le chevauchement doivent être strictement positifs")
    aligned = daily_returns.reindex(daily_returns.index.union(market.index)).sort_index()
    market = market.reindex(aligned.index)
    log_assets = np.log1p(aligned)
    log_market = np.log1p(market)
    rolled_assets = log_assets.rolling(overlap, min_periods=overlap).sum()
    rolled_market = log_market.rolling(overlap, min_periods=overlap).sum()

    index = pd.DatetimeIndex(aligned.index)
    rows: dict[pd.Timestamp, pd.Series] = {}
    for moment in pd.DatetimeIndex(sorted(dates)):
        vol_slice = _window_slices(index, moment, volatility_window)
        corr_slice = _window_slices(index, moment, correlation_window)
        asset_block = log_assets.iloc[vol_slice]
        sigma_i = asset_block.std(ddof=1).where(asset_block.count() >= min_volatility_days)
        market_block = log_market.iloc[vol_slice]
        sigma_m = float(market_block.std(ddof=1)) if market_block.count() >= min_volatility_days else np.nan

        corr_block = rolled_assets.iloc[corr_slice]
        corr_market = rolled_market.iloc[corr_slice]
        rho = corr_block.corrwith(corr_market)
        rho = rho.where(corr_block.notna().sum() >= min_correlation_days)
        raw = rho * sigma_i / sigma_m if np.isfinite(sigma_m) and sigma_m > 0.0 else rho * np.nan
        rows[moment] = shrinkage_weight * raw + (1.0 - shrinkage_weight) * shrinkage_target
    return pd.DataFrame(rows).T.reindex(columns=daily_returns.columns)


def idiosyncratic_volatility(
    daily_returns: pd.DataFrame,
    market: pd.Series,
    betas: pd.DataFrame,
    dates: Sequence[pd.Timestamp],
    *,
    window: int = 252,
    min_days: int = 120,
    skip_last_day: bool = True,
) -> pd.DataFrame:
    r"""Rend l'écart type du résidu de marché sur un an, à chaque date de décision.

    **La variable.** L'annexe A1 définit ``IVOL`` comme l'écart type sur un an
    du rendement excédentaire quotidien ajusté du bêta, la dernière séance étant
    sautée. La composante de sûreté en prend l'opposé.

    .. math::

        \varepsilon_{i,d} = r_{i,d} - \beta_i\, r_{m,d},
        \qquad
        \sigma^i_{i,t} = \operatorname{sd}\left(\varepsilon_{i,d}\right)

    **Pourquoi sauter la dernière séance.** Le rendement du dernier jour porte
    une part d'écart entre cours acheteur et vendeur qui se retourne le
    lendemain. Le garder gonfle la volatilité mesurée d'une quantité qui n'est
    pas du risque.

    Args:
        daily_returns: les rendements simples quotidiens.
        market: le rendement simple quotidien du marché.
        betas: les bêtas employés, un par date de décision et par titre.
        dates: les dates de décision.
        window: la fenêtre, en séances.
        min_days: le nombre minimal de séances exigé.
        skip_last_day: saute la dernière séance de la fenêtre.

    Returns:
        Un tableau dont l'index porte les dates demandées et les colonnes les titres.
    """
    aligned = daily_returns.reindex(daily_returns.index.union(market.index)).sort_index()
    market = market.reindex(aligned.index)
    index = pd.DatetimeIndex(aligned.index)
    rows: dict[pd.Timestamp, pd.Series] = {}
    for moment in pd.DatetimeIndex(sorted(dates)):
        span = _window_slices(index, moment, window)
        stop = span.stop - 1 if skip_last_day and span.stop > span.start else span.stop
        block = aligned.iloc[span.start : stop]
        market_block = market.iloc[span.start : stop]
        if block.empty:
            continue
        beta_row = betas.loc[moment] if moment in betas.index else pd.Series(np.nan, index=block.columns)
        beta_row = beta_row.reindex(block.columns)
        residual = block.sub(np.outer(market_block.to_numpy(), beta_row.to_numpy()), axis=None)
        sigma = residual.std(ddof=1).where(block.count() >= min_days)
        rows[moment] = sigma
    return pd.DataFrame(rows).T.reindex(columns=daily_returns.columns)


# --------------------------------------------------------------------------- #
# Les deux cotes de faillite
# --------------------------------------------------------------------------- #


def ohlson_o_score(frame: pd.DataFrame, *, cpi: float = 1.0) -> pd.Series:
    r"""Rend la cote O d'Ohlson (1980), telle que l'annexe A1 l'écrit.

    **Ce que la cote mesure.** Une probabilité de défaut, croissante. La
    composante de sûreté en prend l'opposé, plus bas valant plus sûr.

    **La formule.**

    .. math::

        O = -1{,}32 - 0{,}407 \log(ADJASSET/CPI) + 6{,}03\,TLTA - 1{,}43\,WCTA
        + 0{,}076\,CLCA - 1{,}72\,OENEG - 2{,}37\,NITA - 1{,}83\,FUTL
        + 0{,}285\,INTWO - 0{,}521\,CHIN

    **Les variables.** :math:`ADJASSET = AT + 0{,}1(ME - BE)`,
    :math:`TLTA = (DLC + DLTT)/ADJASSET`, :math:`WCTA = (ACT - LCT)/ADJASSET`,
    :math:`CLCA = LCT/ACT`, :math:`OENEG` vaut un quand le passif dépasse
    l'actif, :math:`NITA = IB/AT`, :math:`FUTL = PT/LT`, :math:`INTWO` vaut un
    quand le résultat est négatif deux exercices de suite, et
    :math:`CHIN = (IB_t - IB_{t-1})/(|IB_t| + |IB_{t-1}|)`.

    **Pourquoi l'indice des prix ne change rien ici.** Il entre par
    :math:`-0{,}407 \log(CPI)`, le même terme pour toutes les sociétés d'une
    même date. Le score de qualité passe par les rangs transversaux, et une
    constante commune ne déplace aucun rang. La valeur par défaut de ``cpi`` vaut
    donc un, et le test du module vérifie que le rang ne bouge pas quand on la
    change.

    Args:
        frame: un tableau portant ``AT``, ``ME``, ``BE``, ``DLC``, ``DLTT``,
            ``ACT``, ``LCT``, ``LT``, ``IB``, ``PT`` et ``IB_previous``.
        cpi: l'indice des prix à la consommation de la date.

    Returns:
        La cote, dans le sens d'Ohlson, une valeur haute signalant le risque.

    Raises:
        ConfigError: si l'indice des prix n'est pas strictement positif.
    """
    if cpi <= 0.0:
        raise ConfigError(f"l'indice des prix doit être strictement positif, reçu {cpi}")
    adj_asset = frame["AT"] + 0.1 * (frame["ME"] - frame["BE"])
    adj_asset = adj_asset.where(adj_asset > 0.0)
    previous = frame["IB_previous"]
    chin_denominator = frame["IB"].abs() + previous.abs()
    score = (
        _OHLSON["const"]
        + _OHLSON["log_adjasset"] * np.log(adj_asset / cpi)
        + _OHLSON["tlta"] * (frame["DLC"] + frame["DLTT"]) / adj_asset
        + _OHLSON["wcta"] * (frame["ACT"] - frame["LCT"]) / adj_asset
        + _OHLSON["clca"] * frame["LCT"] / frame["ACT"].where(frame["ACT"] > 0.0)
        + _OHLSON["oeneg"] * (frame["LT"] > frame["AT"]).astype("float64")
        + _OHLSON["nita"] * frame["IB"] / frame["AT"]
        + _OHLSON["futl"] * frame["PT"] / frame["LT"].where(frame["LT"] > 0.0)
        + _OHLSON["intwo"] * ((frame["IB"] < 0.0) & (previous < 0.0)).astype("float64")
        + _OHLSON["chin"] * (frame["IB"] - previous) / chin_denominator.where(chin_denominator > 0.0)
    )
    return score.rename("o_score_raw")


def altman_z_score(frame: pd.DataFrame) -> pd.Series:
    r"""Rend la cote Z d'Altman (1968), telle que l'annexe A1 l'écrit.

    **Ce que la cote mesure.** Une distance au défaut, croissante. La composante
    de sûreté la prend telle quelle, plus haut valant plus sûr.

    **La formule.**

    .. math::

        Z = \frac{1{,}2\,WC + 1{,}4\,RE + 3{,}3\,EBIT + 0{,}6\,ME + SALE}{AT}

    **Les variables.** :math:`WC` est le fonds de roulement, :math:`RE` les
    bénéfices non répartis, :math:`EBIT` le résultat d'exploitation, :math:`ME`
    la valeur boursière des fonds propres, :math:`SALE` le chiffre d'affaires et
    :math:`AT` l'actif total.

    **Une différence avec la formule d'origine.** Altman divise la valeur
    boursière par le passif total, pas par l'actif, et pondère les ventes par
    999 millièmes. L'annexe A1 écrit la version ci-dessus, et c'est elle qui est
    reproduite, l'objet étant de répliquer l'article.

    Args:
        frame: un tableau portant ``WC``, ``RE``, ``EBIT``, ``ME``, ``SALE`` et ``AT``.

    Returns:
        La cote, une valeur haute signalant la solidité.
    """
    assets = frame["AT"].where(frame["AT"] > 0.0)
    numerator = (
        _ALTMAN["wc"] * frame["WC"]
        + _ALTMAN["re"] * frame["RE"]
        + _ALTMAN["ebit"] * frame["EBIT"]
        + _ALTMAN["me"] * frame["ME"]
        + _ALTMAN["sale"] * frame["SALE"]
    )
    return (numerator / assets).rename("z_score_raw")


# --------------------------------------------------------------------------- #
# Les vingt et une variables
# --------------------------------------------------------------------------- #


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Rend le quotient, la division par zéro ou par un négatif rendant NaN."""
    return numerator / denominator.where(denominator > 0.0)


def _cash_flow(frame: pd.DataFrame, prefix: str = "") -> pd.Series:
    """Rend le flux de trésorerie de l'annexe A1, résultat plus dotations moins besoins."""
    return (
        frame[f"{prefix}IB"]
        + frame[f"{prefix}DP"].fillna(0.0)
        - frame[f"{prefix}DELTA_WC"]
        - frame[f"{prefix}CAPX"].fillna(0.0)
    )


def profitability_variables(frame: pd.DataFrame) -> pd.DataFrame:
    """Rend les six variables de la composante de rentabilité.

    **Les six définitions de l'annexe A1.** Le profit brut sur l'actif, le
    résultat sur les fonds propres, le résultat sur l'actif, le flux de
    trésorerie sur l'actif, la marge brute, et l'opposé des régularisations.

    **Le sens de la dernière.** Les régularisations valent la variation du
    besoin en fonds de roulement moins les dotations aux amortissements. Un
    résultat porté par des régularisations est de moins bonne qualité, donc la
    variable est prise en négatif.

    Args:
        frame: un tableau portant les postes comptables et ``DELTA_WC``.

    Returns:
        Un tableau à six colonnes, sur le même index.
    """
    out = pd.DataFrame(index=frame.index)
    out["gpoa"] = _safe_divide(frame["GP"], frame["AT"])
    out["roe"] = _safe_divide(frame["IB"], frame["BE"])
    out["roa"] = _safe_divide(frame["IB"], frame["AT"])
    out["cfoa"] = _safe_divide(_cash_flow(frame), frame["AT"])
    out["gmar"] = _safe_divide(frame["GP"], frame["SALE"])
    out["acc"] = _safe_divide(-(frame["DELTA_WC"] - frame["DP"].fillna(0.0)), frame["AT"])
    return out


def growth_variables(frame: pd.DataFrame) -> pd.DataFrame:
    """Rend les six variables de la composante de croissance.

    **La définition de l'annexe A1.** Chaque variable est la variation du
    numérateur sur cinq ans, divisée par le dénominateur d'il y a cinq ans.

    **Le piège du dénominateur.** La croissance de la marge brute se divise par
    les VENTES d'il y a cinq ans, pas par l'actif. Les cinq autres se divisent
    par l'actif ou par les fonds propres d'il y a cinq ans. Une transcription
    mécanique qui mettrait l'actif partout ne lèverait aucune erreur.

    Args:
        frame: un tableau portant les postes courants et les mêmes postes
            préfixés par ``lag_``.

    Returns:
        Un tableau à six colonnes, sur le même index.
    """
    out = pd.DataFrame(index=frame.index)
    out["d_gpoa"] = _safe_divide(frame["GP"] - frame["lag_GP"], frame["lag_AT"])
    out["d_roe"] = _safe_divide(frame["IB"] - frame["lag_IB"], frame["lag_BE"])
    out["d_roa"] = _safe_divide(frame["IB"] - frame["lag_IB"], frame["lag_AT"])
    out["d_cfoa"] = _safe_divide(_cash_flow(frame) - _cash_flow(frame, "lag_"), frame["lag_AT"])
    out["d_gmar"] = _safe_divide(frame["GP"] - frame["lag_GP"], frame["lag_SALE"])
    current = -(frame["DELTA_WC"] - frame["DP"].fillna(0.0))
    previous = -(frame["lag_DELTA_WC"] - frame["lag_DP"].fillna(0.0))
    out["d_acc"] = _safe_divide(current - previous, frame["lag_AT"])
    return out


def safety_variables(frame: pd.DataFrame, *, cpi: float = 1.0) -> pd.DataFrame:
    """Rend les six variables de la composante de sûreté.

    **Les six définitions de l'annexe A1.** L'opposé du bêta, l'opposé de la
    volatilité du résidu, l'opposé du levier, l'opposé de la cote O, la cote Z,
    et l'opposé de la volatilité des bénéfices.

    **Le signe.** Quatre des six variables sont prises en négatif, parce que la
    sûreté est le contraire de ce qu'elles mesurent. Se tromper de signe sur une
    seule inverse sa contribution au score sans rien casser ailleurs.

    Args:
        frame: un tableau portant ``beta``, ``ivol_raw``, ``evol_raw``, les
            postes comptables et ``ME``.
        cpi: l'indice des prix passé à :func:`ohlson_o_score`.

    Returns:
        Un tableau à six colonnes, sur le même index.
    """
    out = pd.DataFrame(index=frame.index)
    out["bab"] = -frame["beta"]
    out["ivol"] = -frame["ivol_raw"]
    out["lev"] = -_safe_divide(frame["TOTD"], frame["AT"])
    out["o_score"] = -ohlson_o_score(frame, cpi=cpi)
    out["z_score"] = altman_z_score(frame)
    out["evol"] = -frame["evol_raw"]
    return out


def payout_variables(frame: pd.DataFrame) -> pd.DataFrame:
    """Rend les trois variables de la composante de distribution.

    **Les trois définitions de l'annexe A1.** L'opposé de la croissance du
    nombre d'actions, l'opposé de la croissance de la dette totale, et le taux
    de distribution net sur cinq ans.

    **Ce que mesure le taux de distribution net.** La part du profit brut
    cumulé qui n'est pas restée dans les fonds propres. Le numérateur est la
    somme sur cinq exercices du résultat moins la variation des fonds propres,
    ce qui vaut ce qui est sorti vers les apporteurs de capitaux.

    Args:
        frame: un tableau portant ``SHROUT``, ``lag1_SHROUT``, ``TOTD``,
            ``lag1_TOTD``, ``NPOP_NUMERATOR`` et ``NPOP_DENOMINATOR``.

    Returns:
        Un tableau à trois colonnes, sur le même index.
    """
    out = pd.DataFrame(index=frame.index)
    share_ratio = _safe_divide(frame["SHROUT"], frame["lag1_SHROUT"])
    out["eiss"] = -np.log(share_ratio.where(share_ratio > 0.0))
    debt_ratio = _safe_divide(frame["TOTD"], frame["lag1_TOTD"])
    out["diss"] = -np.log(debt_ratio.where(debt_ratio > 0.0))
    out["npop"] = _safe_divide(frame["NPOP_NUMERATOR"], frame["NPOP_DENOMINATOR"])
    return out


def quality_variables(frame: pd.DataFrame, *, cpi: float = 1.0) -> pd.DataFrame:
    """Rend les vingt et une variables de qualité, réunies en un seul tableau.

    Args:
        frame: le tableau des postes comptables et de marché, une ligne par
            couple date de décision et société.
        cpi: l'indice des prix passé à :func:`ohlson_o_score`.

    Returns:
        Un tableau portant ``as_of``, ``entity_id`` et les vingt et une variables.

    Raises:
        ConfigError: si les clés de date et d'entité manquent.
    """
    missing = {"as_of", "entity_id"} - set(frame.columns)
    if missing:
        raise ConfigError(f"colonnes de clé absentes : {sorted(missing)}")
    parts = [
        profitability_variables(frame),
        growth_variables(frame),
        safety_variables(frame, cpi=cpi),
        payout_variables(frame),
    ]
    out = pd.concat(parts, axis=1)
    out.insert(0, "entity_id", frame["entity_id"].to_numpy())
    out.insert(0, "as_of", frame["as_of"].to_numpy())
    return out


# --------------------------------------------------------------------------- #
# Le passage par les rangs, puis l'agrégation
# --------------------------------------------------------------------------- #


def rank_zscore(panel: pd.DataFrame, *, min_names: int = 20) -> pd.DataFrame:
    r"""Rend la cote centrée réduite du rang transversal, date par date.

    **Pourquoi passer par le rang.** L'article standardise des rangs et non des
    niveaux. Une régularisation aberrante ou un levier de mille ne peuvent alors
    déplacer une société que d'une position, et le coefficient de régression se
    lit directement en écarts types.

    .. math::

        z(x)_{i,t} = \frac{r_{i,t} - \bar{r}_t}{s_{r,t}}

    **Les variables.** :math:`r_{i,t}` est le rang de la société dans sa date,
    :math:`\bar{r}_t` la moyenne des rangs de cette date et :math:`s_{r,t}` leur
    écart type.

    **Ce que la fonction n'implémente pas.** Ni le rang ni la cote, qui vivent
    dans :mod:`quantlab.signals.standardize`. Elle enchaîne les deux, et c'est
    tout ce qu'elle fait.

    Args:
        panel: un panneau de dates en lignes et de sociétés en colonnes.
        min_names: le nombre minimal de sociétés renseignées à une date.

    Returns:
        Le panneau standardisé, aux mêmes dimensions.
    """
    ranked = cross_sectional_rank(panel, min_names=min_names)
    return cross_sectional_zscore(ranked, min_names=min_names)


def variable_panels(
    variables: pd.DataFrame,
    *,
    groups: Mapping[str, Sequence[str]] = COMPONENT_VARIABLES,
    min_names: int = 20,
) -> dict[str, pd.DataFrame]:
    """Rend, pour chaque variable, son panneau de cotes de rang transversales.

    Args:
        variables: le tableau long rendu par :func:`quality_variables`.
        groups: la composition de chaque composante.
        min_names: le nombre minimal de sociétés renseignées à une date.

    Returns:
        Un dictionnaire du nom de variable vers son panneau standardisé, tous
        alignés sur le même index de dates et les mêmes colonnes de sociétés.

    Raises:
        ConfigError: si une variable annoncée manque au tableau.
    """
    absent = [name for names in groups.values() for name in names if name not in variables.columns]
    if absent:
        raise ConfigError(f"variables absentes du tableau : {absent}")
    dates = pd.DatetimeIndex(sorted(pd.unique(variables["as_of"])))
    entities = pd.Index(sorted(pd.unique(variables["entity_id"])), name="entity_id")
    out: dict[str, pd.DataFrame] = {}
    for names in groups.values():
        for name in names:
            raw = variables.pivot(index="as_of", columns="entity_id", values=name)  # noqa: PD010
            raw = raw.reindex(index=dates, columns=entities)
            out[name] = rank_zscore(raw, min_names=min_names).reindex(index=dates, columns=entities)
    return out


def component_scores(
    variables: pd.DataFrame,
    *,
    groups: Mapping[str, Sequence[str]] = COMPONENT_VARIABLES,
    min_variables: Mapping[str, int] | None = None,
    min_names: int = 20,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Rend la cote de chaque composante et le nombre de variables qui l'a produite.

    **La règle de l'article.** Chaque variable devient une cote de rang, les
    cotes d'une composante s'additionnent, et la somme est standardisée à son
    tour.

    **Notre écart, et sa raison.** Une somme portant une valeur manquante vaut
    manquant. La base de l'article couvre presque toutes ses lignes, la nôtre
    non : une banque ne déclare pas de coût des ventes, donc son profit brut
    n'existe pas. La composante se calcule donc sur la MOYENNE des cotes
    renseignées, à condition qu'il y en ait assez, ce qui laisse les banques
    dans l'univers. Le seuil vit dans la configuration de l'étude.

    **Pourquoi la moyenne redonne la somme.** Sur une ligne complète, moyenne et
    somme diffèrent d'un facteur constant, et la standardisation qui suit efface
    ce facteur. Les deux lectures coïncident donc exactement quand rien ne
    manque, ce qu'un test du module vérifie.

    Args:
        variables: le tableau long rendu par :func:`quality_variables`.
        groups: la composition de chaque composante.
        min_variables: le nombre minimal de variables renseignées par composante.
        min_names: le nombre minimal de sociétés à une date.

    Returns:
        Le couple des panneaux de cotes et des panneaux de comptes, tous deux
        indexés par composante.
    """
    seuils = dict(min_variables or {})
    standardized = variable_panels(variables, groups=groups, min_names=min_names)
    scores: dict[str, pd.DataFrame] = {}
    counts: dict[str, pd.DataFrame] = {}
    for component, names in groups.items():
        block = np.stack([standardized[name].to_numpy(dtype="float64") for name in names])
        present = np.isfinite(block)
        count = present.sum(axis=0)
        total = np.where(present, block, 0.0).sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(count > 0, total / np.maximum(count, 1), np.nan)
        floor = int(seuils.get(component, 1))
        blocked = np.where(count >= floor, mean, np.nan)
        model = standardized[names[0]]
        panel = pd.DataFrame(blocked, index=model.index, columns=model.columns)
        scores[component] = cross_sectional_zscore(panel, min_names=min_names).reindex(
            index=model.index, columns=model.columns
        )
        counts[component] = pd.DataFrame(count, index=model.index, columns=model.columns)
    return scores, counts


def quality_score(
    components: Mapping[str, pd.DataFrame],
    *,
    min_components: int = 3,
    min_names: int = 20,
) -> pd.DataFrame:
    """Rend le score de qualité, cote de la somme des cotes de composantes.

    Args:
        components: les panneaux rendus par :func:`component_scores`.
        min_components: le nombre minimal de composantes renseignées.
        min_names: le nombre minimal de sociétés à une date.

    Returns:
        Le panneau du score, dates en lignes et sociétés en colonnes.

    Raises:
        ConfigError: si aucune composante n'est fournie.
    """
    if not components:
        raise ConfigError("aucune composante fournie pour le score de qualité")
    names = list(components)
    model = components[names[0]]
    block = np.stack([components[name].reindex_like(model).to_numpy(dtype="float64") for name in names])
    present = np.isfinite(block)
    count = present.sum(axis=0)
    total = np.where(present, block, 0.0).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(count > 0, total / np.maximum(count, 1), np.nan)
    blocked = np.where(count >= int(min_components), mean, np.nan)
    panel = pd.DataFrame(blocked, index=model.index, columns=model.columns)
    return cross_sectional_zscore(panel, min_names=min_names).reindex(
        index=model.index, columns=model.columns
    )


# --------------------------------------------------------------------------- #
# Le facteur
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class QualityFactor:
    """Ce que rend une construction de facteur, séries et pièces comprises.

    Attributes:
        returns: le rendement mensuel du facteur, long qualité moins camelote.
        legs: le rendement de chacun des quatre coins du tri conditionnel.
        weights: les poids longs et courts, une ligne par date de formation.
        counts: le nombre de sociétés de chaque coin, une ligne par date.
    """

    returns: pd.Series
    legs: pd.DataFrame
    weights: pd.DataFrame
    counts: pd.DataFrame


def _leg_return(
    scores: pd.Series,
    equity: pd.Series,
    forward: pd.Series,
    *,
    weighting: str,
) -> tuple[float, pd.Series]:
    """Rend le rendement pondéré d'une jambe et les poids qui l'ont produit."""
    usable = scores.index[forward.reindex(scores.index).notna()]
    if len(usable) == 0:
        return float("nan"), pd.Series(dtype="float64")
    if weighting == "value":
        raw = equity.reindex(usable).astype("float64")
        raw = raw.where(raw > 0.0)
    else:
        raw = pd.Series(1.0, index=usable)
    total = float(raw.sum(skipna=True))
    if not np.isfinite(total) or total <= 0.0:
        return float("nan"), pd.Series(dtype="float64")
    weights = (raw / total).dropna()
    return float((weights * forward.reindex(weights.index)).sum()), weights


def quality_minus_junk(
    scores: pd.DataFrame,
    market_equity: pd.DataFrame,
    forward_returns: pd.DataFrame,
    *,
    quality_quantile: float = 0.30,
    size_quantile: float = 0.50,
    weighting: str = "value",
    min_names_per_leg: int = 20,
) -> QualityFactor:
    r"""Construit le facteur par tri conditionnel, la taille d'abord, la qualité ensuite.

    **La construction de l'article.** Six portefeuilles à l'intersection de deux
    paquets de taille et de trois paquets de qualité. Le facteur est la moyenne
    des deux coins de qualité moins la moyenne des deux coins de camelote :

    .. math::

        QMJ = \tfrac{1}{2}\left(Q^{petit} + Q^{grand}\right)
            - \tfrac{1}{2}\left(J^{petit} + J^{grand}\right)

    **Pourquoi le tri est conditionnel.** La qualité est corrélée à la taille.
    Un tri indépendant mettrait les grandes sociétés d'un côté et les petites de
    l'autre, et le facteur mesurerait la taille. Couper la taille d'abord, puis
    la qualité à l'intérieur de chaque moitié, retire cette exposition par
    construction.

    **Le décalage d'exécution.** Le score porte la date de formation, le
    rendement porte le mois suivant. L'appelant fournit ``forward_returns`` déjà
    décalé, et la fonction ne décale rien elle-même. Ce partage rend le décalage
    visible à un seul endroit du programme.

    **Ce qui arrive à une société sans rendement au mois suivant.** Elle sort de
    sa jambe, et les poids restants sont renormalisés. C'est la convention qui
    flatte la jambe courte, puisqu'une société qui disparaît disparaît souvent
    après une perte. Le biais va donc CONTRE le facteur, et il est déclaré.

    Args:
        scores: le score de qualité, dates en lignes et sociétés en colonnes.
        market_equity: la valeur boursière, aux mêmes dimensions.
        forward_returns: le rendement du mois suivant, aux mêmes dimensions.
        quality_quantile: la part de chaque extrémité de qualité.
        size_quantile: la coupure de taille, en quantile.
        weighting: ``« value »`` ou ``« equal »``.
        min_names_per_leg: le nombre minimal de sociétés par coin.

    Returns:
        Un :class:`QualityFactor`.

    Raises:
        ConfigError: si une part n'est pas dans son intervalle admis, ou si la
            pondération demandée est inconnue.
    """
    if not 0.0 < quality_quantile < 0.5:
        raise ConfigError(f"quality_quantile doit tenir entre 0 et 0,5, reçu {quality_quantile}")
    if not 0.0 < size_quantile < 1.0:
        raise ConfigError(f"size_quantile doit tenir entre 0 et 1, reçu {size_quantile}")
    if weighting not in {"value", "equal"}:
        raise ConfigError(f"pondération inconnue : {weighting}, attendu « value » ou « equal »")

    corners = ("small_quality", "big_quality", "small_junk", "big_junk")
    leg_rows: dict[pd.Timestamp, dict[str, float]] = {}
    count_rows: dict[pd.Timestamp, dict[str, int]] = {}
    weight_rows: list[pd.Series] = []
    weight_index: list[pd.Timestamp] = []

    for moment in scores.index:
        row = scores.loc[moment].dropna()
        equity = (
            market_equity.loc[moment].reindex(row.index).dropna() if moment in market_equity.index else None
        )
        if equity is None or equity.empty:
            continue
        row = row.reindex(equity.index).dropna()
        if len(row) < 4 * min_names_per_leg:
            continue
        forward = forward_returns.loc[moment] if moment in forward_returns.index else None
        if forward is None:
            continue

        size_cut = float(equity.reindex(row.index).quantile(size_quantile))
        groups = {
            "small": row.index[equity.reindex(row.index) <= size_cut],
            "big": row.index[equity.reindex(row.index) > size_cut],
        }
        legs: dict[str, float] = {}
        counts: dict[str, int] = {}
        weights = pd.Series(0.0, index=row.index, dtype="float64")
        complete = True
        for size_name, members in groups.items():
            block = row.reindex(members).dropna()
            if len(block) < 2 * min_names_per_leg:
                complete = False
                break
            low = float(block.quantile(quality_quantile))
            high = float(block.quantile(1.0 - quality_quantile))
            junk = block.index[block <= low]
            good = block.index[block >= high]
            if len(junk) < min_names_per_leg or len(good) < min_names_per_leg:
                complete = False
                break
            for corner, members_of_corner, sign in (
                (f"{size_name}_quality", good, 0.5),
                (f"{size_name}_junk", junk, -0.5),
            ):
                value, leg_weights = _leg_return(
                    row.reindex(members_of_corner),
                    equity.reindex(members_of_corner),
                    forward,
                    weighting=weighting,
                )
                if not np.isfinite(value):
                    complete = False
                    break
                legs[corner] = value
                counts[corner] = len(leg_weights)
                weights.loc[leg_weights.index] = weights.loc[leg_weights.index] + sign * leg_weights
            if not complete:
                break
        if not complete or set(legs) != set(corners):
            continue
        leg_rows[moment] = legs
        count_rows[moment] = counts
        weight_rows.append(weights[weights != 0.0])
        weight_index.append(moment)

    if not leg_rows:
        raise InsufficientDataError("aucune date ne remplit les quatre coins du tri conditionnel")

    legs_frame = pd.DataFrame(leg_rows).T[list(corners)].sort_index()
    counts_frame = pd.DataFrame(count_rows).T[list(corners)].sort_index().astype("int64")
    returns = (
        0.5 * (legs_frame["small_quality"] + legs_frame["big_quality"])
        - 0.5 * (legs_frame["small_junk"] + legs_frame["big_junk"])
    ).rename("qmj")
    weights_frame = pd.DataFrame(weight_rows, index=pd.DatetimeIndex(weight_index)).fillna(0.0)
    return QualityFactor(
        returns=returns, legs=legs_frame, weights=weights_frame.sort_index(), counts=counts_frame
    )


def three_component_proxy(legs: Mapping[str, tuple[pd.Series, pd.Series]]) -> pd.DataFrame:
    """Rend l'approximation à trois composantes bâtie sur des portefeuilles déjà triés.

    **À quoi elle sert.** Les jeux de Kenneth French portent des portefeuilles
    triés sur la rentabilité, l'investissement et le bêta, sur soixante-trois
    ans et sans biais du survivant. Ils permettent donc un contrôle long là où
    notre construction complète ne couvre qu'une décennie.

    **Ce qu'elle n'est pas.** Une réplication. L'article agrège des cotes de
    rang au niveau des sociétés ; cette approximation agrège des RENDEMENTS de
    portefeuilles déjà formés, et la distribution y manque faute de tri publié.
    Les deux objets ne coïncident que si les composantes sont indépendantes, ce
    qu'elles ne sont pas.

    Args:
        legs: pour chaque composante, le couple de la jambe longue et de la
            jambe courte, en rendements mensuels.

    Returns:
        Un tableau portant une colonne par composante et la colonne ``proxy``,
        moyenne à parts égales des composantes disponibles.

    Raises:
        ConfigError: si aucune composante n'est fournie.
    """
    if not legs:
        raise ConfigError("aucune composante fournie pour l'approximation")
    columns = {name: (long - short).rename(name) for name, (long, short) in legs.items()}
    out = pd.concat(columns.values(), axis=1)
    out["proxy"] = out[list(columns)].mean(axis=1, skipna=False)
    return out
