"""Polygon : le référentiel des titres, radiés compris, et les barres quotidiennes du forfait.

**Le problème.** Aucune source libre du dépôt ne dit quels titres existaient à
une date passée. Polygon publie un référentiel de tous les titres, actifs et
radiés, avec la date de radiation, et des barres quotidiennes dont la
profondeur dépend du forfait. Le fournisseur lit les deux et déclare dans son
manifeste ce que le forfait a réellement rendu : la profondeur mesurée est une
donnée, pas une promesse de la documentation.

**Ce qui a été mesuré le 2026-09-04 avec le forfait gratuit.** Les barres
quotidiennes remontent à deux ans, le 2024-09-04 pour AAPL. Une demande sur
2008 pour un titre radié, LEH, répond 403 « Your plan doesn't include this
data timeframe ». Le référentiel, lui, est entier : 36 623 titres, dont
23 469 radiés, et 6 425 actions ordinaires radiées datées depuis 2004. Le
forfait accepte cinq requêtes par minute, d'où la pause entre deux pages.

**La clé.** Lue dans la variable d'environnement ``POLYGON_API_KEY`` ou dans le
fichier de clés de ``gvf.marches``, jamais dans le code ni dans le cache. La
clé est passée en en-tête et n'entre jamais au cache brut.

**Provenance.** Documentation de Polygon, page produit, rapportée : « delisted
tickers keep their full history ».
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from collections.abc import Callable, Sequence
from typing import Any, ClassVar, Final

import pandas as pd

from quantlab.core.errors import ConfigError, InsufficientDataError
from quantlab.core.logging import stage
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest
from quantlab.data.providers.base import BaseProvider, ProviderError

POLYGON_PROVIDER_NAME: Final[str] = "polygon"
BASE_URL: Final[str] = "https://api.polygon.io"
#: La pause entre deux requêtes du forfait gratuit, cinq par minute.
FREE_TIER_PAUSE_S: Final[float] = 13.0
PAGE_LIMIT: Final[int] = 1000
LICENSE: Final[str] = "Conditions d'utilisation de Polygon selon le forfait ; usage personnel de recherche"
LICENSE_URL: Final[str] = "https://polygon.io/terms"
PROCESSING_VERSION: Final[str] = "1.0.0"
REFERENCE_COLUMNS: Final[tuple[str, ...]] = (
    "ticker",
    "name",
    "type",
    "primary_exchange",
    "active",
    "delisted_utc",
    "cik",
    "composite_figi",
)


def read_api_key() -> str:
    """Rend la clé Polygon, depuis l'environnement ou le fichier de clés du portefeuille.

    Raises:
        ConfigError: aucune clé trouvée.
    """
    cle = os.environ.get("POLYGON_API_KEY")
    if not cle:
        try:
            from gvf.marches import charger_les_cles

            cles = charger_les_cles()
            cle = cles.get("POLYGON_API_KEY") if isinstance(cles, dict) else os.environ.get("POLYGON_API_KEY")
        except Exception:
            cle = None
    if not cle:
        raise ConfigError("aucune clé Polygon : poser POLYGON_API_KEY ou le fichier de clés de gvf.marches.")
    return cle


def parse_reference_page(text: str) -> tuple[pd.DataFrame, str | None]:
    """Lit une page du référentiel et rend ses lignes et l'adresse de la page suivante.

    Args:
        text: le JSON de la page.

    Returns:
        Le tableau des titres de la page, colonnes :data:`REFERENCE_COLUMNS`,
        et l'adresse de la page suivante, ou ``None`` à la dernière.
    """
    payload = json.loads(text)
    lignes = payload.get("results", [])
    frame = pd.DataFrame(lignes)
    for colonne in REFERENCE_COLUMNS:
        if colonne not in frame.columns:
            frame[colonne] = None
    frame = frame[list(REFERENCE_COLUMNS)]
    if "delisted_utc" in frame.columns:
        frame["delisted_utc"] = pd.to_datetime(frame["delisted_utc"], errors="coerce", utc=True)
    return frame, payload.get("next_url")


def parse_daily_bars(text: str, ticker: str) -> pd.DataFrame:
    """Lit une réponse d'agrégats quotidiens et la rend au format long du laboratoire.

    Args:
        text: le JSON de la réponse.
        ticker: le symbole demandé.

    Returns:
        Un tableau ``date``, ``ticker``, ``open``, ``high``, ``low``, ``close``,
        ``volume``, ``vwap``, ``transactions``, trié par date.
    """
    payload = json.loads(text)
    lignes = payload.get("results") or []
    if not lignes:
        return pd.DataFrame(
            columns=["date", "ticker", "open", "high", "low", "close", "volume", "vwap", "transactions"]
        )
    frame = pd.DataFrame(lignes).rename(
        columns={
            "t": "date",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "vwap",
            "n": "transactions",
        }
    )
    frame["date"] = (
        pd.to_datetime(frame["date"], unit="ms", utc=True)
        .dt.tz_convert("America/New_York")
        .dt.normalize()
        .dt.tz_localize(None)
    )
    frame["ticker"] = ticker
    colonnes = ["date", "ticker", "open", "high", "low", "close", "volume", "vwap", "transactions"]
    for colonne in colonnes:
        if colonne not in frame.columns:
            frame[colonne] = float("nan")
    return frame[colonnes].sort_values("date").reset_index(drop=True)


class PolygonProvider(BaseProvider):
    """Le référentiel des titres et les barres quotidiennes de Polygon, à la cadence du forfait."""

    name: ClassVar[str] = POLYGON_PROVIDER_NAME

    def __init__(
        self,
        *,
        api_key: str | None = None,
        pause_s: float = FREE_TIER_PAUSE_S,
        sleeper: Callable[[float], None] = time.sleep,
        **kwargs: Any,
    ) -> None:
        """Construit le fournisseur.

        Args:
            api_key: la clé ; sans valeur, :func:`read_api_key` la cherche.
            pause_s: la pause après chaque requête RÉSEAU, en secondes.
            sleeper: la fonction d'attente, injectable dans les tests.
            **kwargs: ``client``, ``raw_root`` et ``now``, voir :class:`BaseProvider`.
        """
        super().__init__(**kwargs)
        self._api_key = api_key
        self._pause_s = pause_s
        self._sleeper = sleeper
        self._last: dict[str, Any] | None = None

    def _key(self) -> str:
        if self._api_key is None:
            self._api_key = read_api_key()
        return self._api_key

    def _get(self, path_or_url: str, params: dict[str, Any], *, label: str, refresh: bool) -> str:
        """Une requête, la clé passée en en-tête et jamais dans les paramètres mis en cache."""
        url = path_or_url if path_or_url.startswith("http") else BASE_URL + path_or_url
        avant = self.raw_root
        raw = self.fetch_cached(
            url,
            params=params,
            headers={"Authorization": f"Bearer {self._key()}"},
            label=label,
            refresh=refresh,
        )
        # Une réponse relue du cache ne coûte rien au forfait ; une réponse
        # fraîche impose la pause, et le cache est le seul témoin de la différence.
        if raw.fetched_at >= self._now_floor:
            self._sleeper(self._pause_s)
        _ = avant
        self._last = {"url": raw.url, "checksum": raw.sha256, "fetched_at": raw.fetched_at, "label": label}
        return raw.text()

    @property
    def _now_floor(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC) - dt.timedelta(seconds=5)

    def reference_tickers(
        self, *, active: bool, market: str = "stocks", refresh: bool = False, max_pages: int | None = None
    ) -> pd.DataFrame:
        """Rend le référentiel des titres actifs ou radiés, page par page.

        Args:
            active: vrai pour les titres cotés aujourd'hui, faux pour les radiés.
            market: le marché de Polygon, ``stocks`` par défaut.
            refresh: force le téléchargement.
            max_pages: borne le nombre de pages, pour les essais.

        Returns:
            Le tableau des titres, colonnes :data:`REFERENCE_COLUMNS`.
        """
        params: dict[str, Any] = {
            "active": "true" if active else "false",
            "market": market,
            "limit": PAGE_LIMIT,
            "sort": "ticker",
        }
        pages: list[pd.DataFrame] = []
        with stage("polygon.reference", provider=self.name, active=active) as payload:
            suivant: str | None = "/v3/reference/tickers"
            numero = 0
            while suivant is not None and (max_pages is None or numero < max_pages):
                numero += 1
                texte = self._get(
                    suivant,
                    params if numero == 1 else {},
                    label=f"reference-{params['active']}-{numero}",
                    refresh=refresh,
                )
                frame, suivant = parse_reference_page(texte)
                pages.append(frame)
            payload["pages"] = numero
        if not pages:
            raise InsufficientDataError("le référentiel ne rend aucune page.")
        tableau = pd.concat(pages, ignore_index=True)
        self._last.update({"rows": len(tableau), "columns": tuple(tableau.columns), "index": None})
        return tableau

    def daily_bars(
        self, ticker: str, *, start: dt.date | str, end: dt.date | str, refresh: bool = False
    ) -> pd.DataFrame:
        """Rend les barres quotidiennes ajustées d'un titre entre deux dates, telles que le forfait les donne.

        Raises:
            ProviderError: le forfait refuse la fenêtre, code 403, message de la source conservé.
        """
        debut, fin = pd.Timestamp(start).date(), pd.Timestamp(end).date()
        chemin = f"/v2/aggs/ticker/{ticker}/range/1/day/{debut.isoformat()}/{fin.isoformat()}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000}
        texte = self._get(chemin, params, label=f"daily-{ticker}-{debut}-{fin}", refresh=refresh)
        frame = parse_daily_bars(texte, ticker)
        self._last.update(
            {
                "rows": len(frame),
                "columns": tuple(frame.columns),
                "index": pd.DatetimeIndex(frame["date"]) if len(frame) else None,
            }
        )
        return frame

    def fetch(
        self, tickers: Sequence[str] | str, *, start: dt.date | str, end: dt.date | str, **kwargs: Any
    ) -> pd.DataFrame:
        """Rend les barres de plusieurs titres, pour le protocole commun."""
        symboles = [tickers] if isinstance(tickers, str) else list(tickers)
        morceaux = [
            self.daily_bars(t, start=start, end=end, refresh=bool(kwargs.get("refresh", False)))
            for t in symboles
        ]
        return pd.concat(morceaux, ignore_index=True)

    def manifest(self, **overrides: Any) -> DatasetManifest:
        """Rend le manifeste de la dernière requête, profondeur mesurée et non promise."""
        if self._last is None and not overrides:
            raise ConfigError("aucune requête faite.")
        base = dict(self._last or {})
        base.update(overrides)
        index = base.get("index")
        a_dates = index is not None and len(index) > 0
        return DatasetManifest(
            dataset_id=f"polygon-{str(base.get('label', 'inconnu')).lower()}",
            source="Polygon, interface REST, forfait mesuré à l'appel",
            provider=f"quantlab.data.providers.{self.name}",
            url=str(base["url"]),
            download_timestamp=base["fetched_at"],
            data_start=index.min().date() if a_dates else base["fetched_at"].date(),
            data_end=index.max().date() if a_dates else base["fetched_at"].date(),
            frequency=Frequency.DAILY,
            timezone="America/New_York",
            exchange=None,
            currency="USD",
            adjusted=True,
            point_in_time=True,
            survivorship_free=True,
            corporate_actions=(
                "ajustées par la source quand adjusted=true ; référentiel avec date de radiation"
            ),
            revision_policy=(
                "la source réécrit ses barres à chaque ajustement ; le cache brut garde la lecture"
            ),
            license=LICENSE,
            license_url=LICENSE_URL,
            checksum_sha256=str(base["checksum"]),
            n_rows=int(base.get("rows", 0)),
            n_columns=len(base.get("columns", ())),
            columns=tuple(base.get("columns", ())),
            processing_version=PROCESSING_VERSION,
            layer=Layer.RAW,
            notes=(
                "profondeur d'historique selon le forfait : deux ans mesurés le 2026-09-04 "
                "sur le forfait gratuit"
            ),
        )


__all__ = ["PolygonProvider", "ProviderError", "parse_daily_bars", "parse_reference_page", "read_api_key"]
