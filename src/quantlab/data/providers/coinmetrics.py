"""Les données communautaires de Coin Metrics : prix et capitalisation quotidiens, actifs disparus compris.

**Le problème.** Les cryptomonnaies sont le seul marché jeune où les facteurs
académiques ont été publiés après 2020, et le laboratoire n'avait aucune
source libre de capitalisations datées. Mesuré le 2026-09-04 : CoinGecko
gratuit s'arrête à un an d'historique, Coinbase n'a pas de capitalisation. Le
dépôt public de Coin Metrics porte un CSV par actif, plus de mille, avec
le prix en dollars et la capitalisation courante par jour depuis la naissance
de l'actif. Il garde les actifs disparus.

**La source.** ``https://github.com/coinmetrics/data``, fichiers ``csv/<actif>.csv``,
lus par leur adresse brute. Licence Creative Commons Attribution NonCommercial
4.0, lue dans le fichier LICENSE du dépôt le 2026-09-04. Retard de
publication de quelques mois, mesuré : le fichier de BTC s'arrêtait au
2026-05-24 le 2026-09-04.

**Provenance.** Coin Metrics, Inc., données communautaires. Employées par
l'étude 019 pour Liu, Tsyvinski et Wu (2022).
"""

from __future__ import annotations

import datetime as dt
import io
import json
from typing import Any, ClassVar, Final

import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import stage
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest
from quantlab.data.providers.base import BaseProvider

COINMETRICS_PROVIDER_NAME: Final[str] = "coinmetrics"
TREE_URL: Final[str] = "https://api.github.com/repos/coinmetrics/data/git/trees/master"
RAW_URL: Final[str] = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/{asset}.csv"
LICENSE: Final[str] = (
    "Creative Commons Attribution NonCommercial 4.0 International, LICENSE du dépôt lu le 2026-09-04"
)
LICENSE_URL: Final[str] = "https://github.com/coinmetrics/data/blob/master/LICENSE"
PROCESSING_VERSION: Final[str] = "1.0.0"
#: Les colonnes que le laboratoire lit, et leur nom ici.
COLUMNS: Final[dict[str, str]] = {"time": "date", "PriceUSD": "price_usd", "CapMrktCurUSD": "market_cap_usd"}


def parse_asset_list(text: str) -> list[str]:
    """Rend les actifs présents dans l'arbre du dépôt, un par fichier ``csv/<actif>.csv``.

    Raises:
        DataQualityError: l'arbre est tronqué ou ne porte aucun fichier.
    """
    arbre = json.loads(text)
    if arbre.get("truncated"):
        raise DataQualityError("l'arbre du dépôt est tronqué par l'interface ; la liste serait incomplète.")
    actifs = sorted(
        entree["path"][4:-4]
        for entree in arbre.get("tree", [])
        if entree.get("path", "").startswith("csv/") and entree["path"].endswith(".csv")
    )
    if not actifs:
        raise DataQualityError("aucun fichier csv/ dans l'arbre du dépôt.")
    return actifs


def parse_asset_csv(text: str, asset: str) -> pd.DataFrame:
    """Lit le CSV d'un actif et rend ``date``, ``price_usd``, ``market_cap_usd``.

    Les jours sans prix sont conservés avec une valeur absente ; l'appelant
    décide s'ils comptent. Une capitalisation absente reste absente.

    Raises:
        DataQualityError: la colonne de temps ou de prix manque.
    """
    frame = pd.read_csv(io.StringIO(text))
    manquantes = [c for c in ("time", "PriceUSD") if c not in frame.columns]
    if manquantes:
        raise DataQualityError(f"{asset} : colonnes absentes {manquantes}.")
    if "CapMrktCurUSD" not in frame.columns:
        frame["CapMrktCurUSD"] = float("nan")
    sortie = frame[list(COLUMNS)].rename(columns=COLUMNS)
    sortie["date"] = pd.to_datetime(sortie["date"])
    sortie["asset"] = asset
    return sortie[["date", "asset", "price_usd", "market_cap_usd"]].sort_values("date").reset_index(drop=True)


class CoinMetricsProvider(BaseProvider):
    """Les CSV communautaires de Coin Metrics, un actif à la fois, depuis le cache brut ou le dépôt public."""

    name: ClassVar[str] = COINMETRICS_PROVIDER_NAME

    def __init__(self, **kwargs: Any) -> None:
        """Construit le fournisseur, arguments passés à :class:`BaseProvider`."""
        super().__init__(**kwargs)
        self._last: dict[str, Any] | None = None

    def assets(self, *, refresh: bool = False) -> list[str]:
        """Rend la liste des actifs du dépôt, en un appel à l'arbre."""
        with stage("coinmetrics.assets", provider=self.name) as payload:
            raw = self.fetch_cached(TREE_URL, params={"recursive": "1"}, label="tree", refresh=refresh)
            actifs = parse_asset_list(raw.text())
            payload["n_assets"] = len(actifs)
        self._last = {
            "label": "tree",
            "url": raw.url,
            "checksum": raw.sha256,
            "fetched_at": raw.fetched_at,
            "rows": len(actifs),
            "columns": ("asset",),
            "index": None,
        }
        return actifs

    def asset_history(self, asset: str, *, refresh: bool = False) -> pd.DataFrame:
        """Rend l'historique quotidien d'un actif, prix et capitalisation en dollars."""
        if not asset or "/" in asset or asset != asset.lower():
            raise ConfigError(f"nom d'actif invalide : {asset!r}, attendu en minuscules sans séparateur.")
        raw = self.fetch_cached(RAW_URL.format(asset=asset), label=f"asset-{asset}", refresh=refresh)
        frame = parse_asset_csv(raw.text(), asset)
        if frame.empty:
            raise InsufficientDataError(f"{asset} : fichier vide.")
        self._last = {
            "label": f"asset-{asset}",
            "url": raw.url,
            "checksum": raw.sha256,
            "fetched_at": raw.fetched_at,
            "rows": len(frame),
            "columns": tuple(frame.columns),
            "index": pd.DatetimeIndex(frame["date"]),
        }
        return frame

    def fetch(
        self,
        assets: list[str] | str,
        *,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Rend l'historique de plusieurs actifs en format long, borné aux dates demandées."""
        noms = [assets] if isinstance(assets, str) else list(assets)
        morceaux = [self.asset_history(a, refresh=bool(kwargs.get("refresh", False))) for a in noms]
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
        index = base.get("index")
        a_dates = index is not None and len(index) > 0
        return DatasetManifest(
            dataset_id=f"coinmetrics-{str(base.get('label', 'inconnu')).lower()}",
            source="Coin Metrics, données communautaires, dépôt public GitHub",
            provider=f"quantlab.data.providers.{self.name}",
            url=str(base["url"]),
            download_timestamp=base["fetched_at"],
            data_start=index.min().date() if a_dates else base["fetched_at"].date(),
            data_end=index.max().date() if a_dates else base["fetched_at"].date(),
            frequency=Frequency.DAILY,
            timezone="UTC",
            exchange=None,
            currency="USD",
            adjusted=False,
            point_in_time=False,
            survivorship_free=True,
            corporate_actions="sans objet ; les actifs disparus gardent leur fichier",
            revision_policy="le dépôt est réécrit à chaque publication ; le cache brut garde la lecture",
            license=LICENSE,
            license_url=LICENSE_URL,
            checksum_sha256=str(base["checksum"]),
            n_rows=int(base.get("rows", 0)),
            n_columns=len(base.get("columns", ())),
            columns=tuple(base.get("columns", ())),
            processing_version=PROCESSING_VERSION,
            layer=Layer.RAW,
            notes="retard de publication de quelques mois, mesuré le 2026-09-04 : BTC s'arrête au 2026-05-24",
        )


__all__ = ["COLUMNS", "CoinMetricsProvider", "parse_asset_csv", "parse_asset_list"]
