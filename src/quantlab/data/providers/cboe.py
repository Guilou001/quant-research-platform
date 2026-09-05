"""Les indices de stratégie du Cboe : ce que rapporte la vente d'options sur le S&P 500, jour par jour.

**Le problème.** La prime de volatilité, l'écart entre ce que paient les
acheteurs d'options et ce que les options coûtent ensuite, est l'une des
primes les plus anciennes de la littérature. Le laboratoire n'avait aucune
source libre d'options. Le Cboe publie le niveau quotidien de ses indices de
référence. PUT et WPUT vendent des puts sur le S&P 500 chaque mois ou chaque
semaine, BXM et BXMD vendent des calls couverts, CLL tient un collier. Ces
indices portent les prix réellement négociés, là où une reconstruction par
Black-Scholes au VIX était trop riche de 523 points de base par an, mesuré
dans le dépôt 16 du portefeuille.

**La source.** ``https://cdn.cboe.com/api/global/us_indices/daily_prices/<INDICE>_History.csv``,
un fichier par indice, deux colonnes, la date au format mois, jour, année et
le niveau. Mesuré le 2026-09-04 : le fichier de PUT compte 4 957 lignes depuis le
1991-03-04, mais seulement sept points isolés avant le 2007-01-03, puis une
ligne par séance. Les autres indices ont la même forme, et le VIX porte
quatre colonnes, ouverture, plus haut, plus bas et clôture. Un rendement
calculé à travers un trou de plusieurs années est faux ; :func:`daily_segment`
ne garde que la partie continue de l'historique, et l'étude 021 l'emploie.

**Licence.** Accord d'abonné du Cboe, usage personnel et non commercial par
un abonné non professionnel, aucun produit financier bâti sur l'indice sans
autorisation. Statut rapporté, lu le 2026-09-04.

**Provenance.** Cboe Global Indices. Employé par l'étude 021.
"""

from __future__ import annotations

import datetime as dt
import io
from typing import Any, ClassVar, Final

import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError
from quantlab.core.logging import stage
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest
from quantlab.data.providers.base import BaseProvider

CBOE_PROVIDER_NAME: Final[str] = "cboe"
HISTORY_URL: Final[str] = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{index}_History.csv"
LICENSE: Final[str] = (
    "Accord d'abonné du Cboe : usage personnel et non commercial, aucun produit bâti sur l'indice"
)
LICENSE_URL: Final[str] = "https://cdn.cboe.com/resources/membership/Subscriber_Agreement.pdf"
PROCESSING_VERSION: Final[str] = "1.0.0"

#: Les indices que le laboratoire sait lire, et ce que chacun tient.
INDICES: Final[dict[str, str]] = {
    "PUT": "vente mensuelle de puts au niveau du S&P 500, garantie en bons du Trésor",
    "WPUT": "vente hebdomadaire de puts au niveau du S&P 500",
    "BXM": "S&P 500 et vente mensuelle de calls au niveau",
    "BXMD": "S&P 500 et vente mensuelle de calls à 30 delta",
    "CLL": "S&P 500 avec put à 95 % et call à 110 %, collier",
    "VIX": "volatilité implicite à trente jours du S&P 500, clôture",
}


def parse_history_csv(text: str, index: str) -> pd.DataFrame:
    """Rend la table datée des niveaux d'un fichier d'historique du Cboe.

    Args:
        text: le contenu du fichier, une ligne d'en-tête puis une ligne par jour.
        index: le code de l'indice, qui nomme sa colonne ; le VIX se lit à la clôture.

    Returns:
        ``date`` en horodatage et ``level`` en flottant, triés par date.

    Raises:
        DataQualityError: la colonne de l'indice manque, une date se répète,
            ou un niveau n'est pas strictement positif.
    """
    if index not in INDICES:
        raise ConfigError(f"indice inconnu : {index} ; connus : {', '.join(INDICES)}.")
    brut = pd.read_csv(io.StringIO(text))
    brut.columns = [str(c).strip().upper() for c in brut.columns]
    colonne = "CLOSE" if index == "VIX" else index
    if "DATE" not in brut.columns or colonne not in brut.columns:
        raise DataQualityError(f"colonnes attendues DATE et {colonne}, lues : {', '.join(brut.columns)}.")
    table = pd.DataFrame(
        {
            "date": pd.to_datetime(brut["DATE"], format="%m/%d/%Y"),
            "level": pd.to_numeric(brut[colonne], errors="coerce"),
        }
    ).sort_values("date")
    if table["date"].duplicated().any():
        doublon = table.loc[table["date"].duplicated(), "date"].iloc[0]
        raise DataQualityError(f"date répétée dans l'historique de {index} : {doublon.date()}.")
    if table["level"].isna().any() or (table["level"] <= 0).any():
        raise DataQualityError(f"niveau manquant ou non positif dans l'historique de {index}.")
    return table.reset_index(drop=True)


def daily_segment(table: pd.DataFrame, *, max_gap_days: int = 7) -> pd.DataFrame:
    """Rend la partie finale de l'historique où deux dates consécutives sont à moins de ``max_gap_days``.

    Les fichiers du Cboe portent quelques points isolés avant leur historique
    quotidien ; mesuré sur PUT, sept points entre 1991 et 2004 puis une ligne
    par séance depuis le 2007-01-03. La coupure est la dernière date dont
    l'écart avec la précédente dépasse le seuil.

    Args:
        table: la table datée de :func:`parse_history_csv`.
        max_gap_days: l'écart calendaire maximal entre deux lignes consécutives.

    Returns:
        La même table, restreinte au dernier segment continu, index remis à zéro.
    """
    if table.empty:
        return table
    ecarts = table["date"].diff().dt.days
    trous = ecarts[ecarts > max_gap_days]
    debut = int(trous.index[-1]) if len(trous) else 0
    return table.iloc[debut:].reset_index(drop=True)


class CboeIndexProvider(BaseProvider):
    """Les historiques quotidiens des indices de stratégie du Cboe, gardés tels quels dans le cache brut."""

    name: ClassVar[str] = CBOE_PROVIDER_NAME

    def __init__(self, **kwargs: Any) -> None:
        """Construit le fournisseur, arguments passés à :class:`BaseProvider`."""
        super().__init__(**kwargs)
        self._last: dict[str, Any] | None = None

    def history(self, index: str, *, refresh: bool = False) -> pd.DataFrame:
        """Télécharge et lit l'historique d'un indice, voir :func:`parse_history_csv`."""
        if index not in INDICES:
            raise ConfigError(f"indice inconnu : {index} ; connus : {', '.join(INDICES)}.")
        url = HISTORY_URL.format(index=index)
        with stage(f"{self.name}.history", provider=self.name, index=index):
            raw = self.fetch_cached(url, label=f"{index}_History", refresh=refresh)
            table = parse_history_csv(raw.text(), index)
            self._last = {
                "label": index,
                "url": raw.url,
                "fetched_at": raw.fetched_at,
                "checksum": raw.sha256,
                "rows": len(table),
                "columns": tuple(table.columns),
                "index": table["date"],
            }
        return table

    def fetch(
        self,
        indices: list[str] | str = "PUT",
        *,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Rend l'historique d'un ou plusieurs indices en format long, borné aux dates demandées."""
        noms = [indices] if isinstance(indices, str) else list(indices)
        morceaux = []
        for nom in noms:
            table = self.history(nom, refresh=bool(kwargs.get("refresh", False)))
            morceaux.append(table.assign(index=nom))
        frame = pd.concat(morceaux, ignore_index=True)
        if start is not None:
            frame = frame[frame["date"] >= pd.Timestamp(start)]
        if end is not None:
            frame = frame[frame["date"] <= pd.Timestamp(end)]
        return frame.reset_index(drop=True)

    def manifest(self, **overrides: Any) -> DatasetManifest:
        """Rend le manifeste de la dernière lecture."""
        if self._last is None and not overrides:
            raise ConfigError("aucune lecture faite.")
        base = dict(self._last or {})
        base.update(overrides)
        dates = base.get("index")
        a_dates = dates is not None and len(dates) > 0
        return DatasetManifest(
            dataset_id=f"cboe-{str(base.get('label', 'inconnu')).lower()}",
            source="Cboe Global Indices, historiques quotidiens publics",
            provider=f"quantlab.data.providers.{self.name}",
            url=str(base["url"]),
            download_timestamp=base["fetched_at"],
            data_start=dates.min().date() if a_dates else base["fetched_at"].date(),
            data_end=dates.max().date() if a_dates else base["fetched_at"].date(),
            frequency=Frequency.DAILY,
            timezone="America/Chicago",
            exchange="Cboe",
            currency="USD",
            adjusted=False,
            point_in_time=False,
            survivorship_free=True,
            corporate_actions="sans objet ; un indice de stratégie n'a ni dividende ni division",
            revision_policy="l'historique est réécrit à chaque publication ; le cache brut garde la lecture",
            license=LICENSE,
            license_url=LICENSE_URL,
            checksum_sha256=str(base["checksum"]),
            n_rows=int(base.get("rows", 0)),
            n_columns=len(base.get("columns", ())),
            columns=tuple(base.get("columns", ())),
            processing_version=PROCESSING_VERSION,
            layer=Layer.RAW,
            notes=INDICES.get(str(base.get("label")), ""),
        )
