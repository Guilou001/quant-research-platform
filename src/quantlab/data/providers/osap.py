"""Les 212 portefeuilles long moins court d'Open Source Asset Pricing, et leur fiche.

**Le problème.** Le laboratoire n'a aucune source libre de rendements
transversaux construits sur un univers qui garde les sociétés radiées. Chen et
Zimmermann (2022) publient les rendements mensuels de 212 portefeuilles long
moins court, un par prédicteur de la littérature, construits sur CRSP. Chacun
porte l'article d'origine, son année et la fin de son échantillon. C'est
ce que l'étude 014 attendait pour tester l'hétérogénéité de la décroissance
après publication sur assez d'unités.

**La source.** Deux fichiers CSV de la publication d'octobre 2025, hébergés
sur Google Drive et lus par l'adresse de téléchargement direct. Les
rendements sont en POURCENTAGE par mois dans le fichier, 1,801 valant 1,801 % ;
le fournisseur les rend en fractions, 0,01801, comme toutes les séries du
laboratoire. Statut de la licence : aucune n'est énoncée sur la page des
données, mesuré le 2026-09-04 ; le code des auteurs est sous GPL-2.0, et ils
demandent la citation de l'article. Le manifeste le dit.

**Provenance.** Chen, A. Y. et Zimmermann, T. (2022). Open Source
Cross-Sectional Asset Pricing. Critical Finance Review, 11(2), 207-264.
"""

from __future__ import annotations

import datetime as dt
import io
from typing import Any, ClassVar, Final

import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import stage
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest
from quantlab.data.providers.base import BaseProvider

OSAP_PROVIDER_NAME: Final[str] = "osap"
#: L'adresse de téléchargement direct d'un fichier Google Drive, par identifiant.
DRIVE_URL: Final[str] = "https://drive.google.com/uc"
#: Les identifiants des deux fichiers, lus sur openassetpricing.com/data le 2026-09-04.
FILE_IDS: Final[dict[str, str]] = {
    "long_short_returns": "10sOryk_ddjkXagaajTKUk1nwJs2ZLRiI",
    "signal_doc": "1Sev9s6cPFUGgxp1pFiej0lGzpsMqJCI2",
}
PERCENT_DIVISOR: Final[float] = 100.0
LICENSE: Final[str] = (
    "Aucune licence énoncée sur la page des données (mesuré le 2026-09-04) ; code des auteurs "
    "sous GPL-2.0 ; citation demandée : Chen et Zimmermann (2022), Critical Finance Review 11(2)"
)
LICENSE_URL: Final[str] = "https://www.openassetpricing.com/data/"
PROCESSING_VERSION: Final[str] = "1.0.0"
#: Les colonnes de la fiche que le laboratoire lit, et leur nom en français.
DOC_COLUMNS: Final[dict[str, str]] = {
    "Acronym": "acronym",
    "Cat.Signal": "category",
    "Authors": "authors",
    "Year": "publication_year",
    "Journal": "journal",
    "SampleStartYear": "sample_start_year",
    "SampleEndYear": "sample_end_year",
    "Predictability in OP": "predictability",
    "Return": "op_return",
    "T-Stat": "op_tstat",
    "LongDescription": "description",
}


def parse_long_short_csv(text: str) -> pd.DataFrame:
    """Lit le fichier des rendements long moins court et le rend en fractions, daté en fin de mois.

    Args:
        text: le contenu CSV, une colonne ``date`` puis une colonne par prédicteur.

    Returns:
        Un tableau indexé par fin de mois civile, une colonne par prédicteur,
        rendements simples en fractions, valeurs absentes conservées.

    Raises:
        DataQualityError: la colonne ``date`` manque, ou aucune colonne de rendement.
    """
    frame = pd.read_csv(io.StringIO(text))
    if "date" not in frame.columns:
        raise DataQualityError("le fichier des rendements ne porte pas de colonne « date ».")
    colonnes = [c for c in frame.columns if c != "date"]
    if not colonnes:
        raise DataQualityError("le fichier des rendements ne porte aucun prédicteur.")
    index = pd.to_datetime(frame["date"]).dt.to_period("M").dt.to_timestamp("M")
    valeurs = frame[colonnes].astype(float) / PERCENT_DIVISOR
    valeurs.index = pd.DatetimeIndex(index, name="date")
    return valeurs.sort_index()


def parse_signal_doc(text: str) -> pd.DataFrame:
    """Lit la fiche des signaux et ne garde que les prédicteurs, colonnes renommées.

    Args:
        text: le contenu CSV de la documentation des signaux.

    Returns:
        Un tableau indexé par acronyme, restreint aux lignes de catégorie
        « Predictor », avec les colonnes de :data:`DOC_COLUMNS`.

    Raises:
        DataQualityError: une colonne attendue manque, ou une année manque.
    """
    frame = pd.read_csv(io.StringIO(text))
    manquantes = [c for c in DOC_COLUMNS if c not in frame.columns]
    if manquantes:
        raise DataQualityError(f"colonnes absentes de la fiche des signaux : {manquantes}.")
    doc = frame[list(DOC_COLUMNS)].rename(columns=DOC_COLUMNS)
    doc = doc[doc["category"] == "Predictor"].set_index("acronym")
    for colonne in ("publication_year", "sample_end_year"):
        if doc[colonne].isna().any():
            raise DataQualityError(f"la colonne « {colonne} » porte une valeur absente.")
        doc[colonne] = doc[colonne].astype(int)
    return doc


class OsapProvider(BaseProvider):
    """Télécharge les deux fichiers d'Open Source Asset Pricing et les rend au format du laboratoire.

    Example:
        .. code-block:: python

            fournisseur = OsapProvider()
            rendements = fournisseur.long_short_returns()
            fiche = fournisseur.signal_documentation()
            fournisseur.manifest().survivorship_free  # True, univers CRSP
    """

    name: ClassVar[str] = OSAP_PROVIDER_NAME

    def __init__(self, **kwargs: Any) -> None:
        """Construit le fournisseur, arguments passés à :class:`BaseProvider`."""
        super().__init__(**kwargs)
        self._last: dict[str, Any] | None = None

    def _download(self, dataset: str, *, refresh: bool) -> str:
        if dataset not in FILE_IDS:
            raise ConfigError(f"jeu inconnu : {dataset!r}, attendu parmi {sorted(FILE_IDS)}.")
        params = {"export": "download", "id": FILE_IDS[dataset], "confirm": "t"}
        with stage("osap.fetch", provider=self.name, dataset=dataset) as payload:
            raw = self.fetch_cached(DRIVE_URL, params=params, label=dataset, refresh=refresh)
            payload["bytes"] = len(raw.content)
        self._last = {
            "dataset": dataset,
            "url": raw.url,
            "checksum": raw.sha256,
            "fetched_at": raw.fetched_at,
        }
        return raw.text()

    def long_short_returns(self, *, refresh: bool = False) -> pd.DataFrame:
        """Rend les 212 rendements mensuels long moins court, en fractions."""
        frame = parse_long_short_csv(self._download("long_short_returns", refresh=refresh))
        if frame.empty:
            raise InsufficientDataError("le fichier des rendements est vide.")
        assert self._last is not None
        self._last.update({"index": frame.index, "columns": tuple(frame.columns), "rows": len(frame)})
        return frame

    def signal_documentation(self, *, refresh: bool = False) -> pd.DataFrame:
        """Rend la fiche des 212 prédicteurs, indexée par acronyme."""
        doc = parse_signal_doc(self._download("signal_doc", refresh=refresh))
        if doc.empty:
            raise InsufficientDataError("la fiche des signaux ne porte aucun prédicteur.")
        assert self._last is not None
        self._last.update({"index": None, "columns": tuple(doc.columns), "rows": len(doc)})
        return doc

    def fetch(
        self, *, start: dt.date | None = None, end: dt.date | None = None, **kwargs: Any
    ) -> pd.DataFrame:
        """Rend les rendements long moins court entre deux dates, pour le protocole commun."""
        frame = self.long_short_returns(refresh=bool(kwargs.get("refresh", False)))
        if start is not None:
            frame = frame.loc[pd.Timestamp(start) :]
        if end is not None:
            frame = frame.loc[: pd.Timestamp(end)]
        if frame.empty:
            raise InsufficientDataError(f"aucun mois entre {start} et {end}.")
        return frame

    def manifest(self, **overrides: Any) -> DatasetManifest:
        """Rend le manifeste du dernier fichier lu, univers CRSP donc sans biais de survie."""
        if self._last is None and not overrides:
            raise ConfigError("aucun fichier lu : appeler long_short_returns() ou signal_documentation().")
        base = dict(self._last or {})
        base.update(overrides)
        index = base.get("index")
        est_serie = index is not None and len(index) > 0
        return DatasetManifest(
            dataset_id=f"osap-{base['dataset'].replace('_', '-')}",
            source="Open Source Asset Pricing, Chen et Zimmermann, publication d'octobre 2025, Google Drive",
            provider=f"quantlab.data.providers.{self.name}",
            url=str(base["url"]),
            download_timestamp=base["fetched_at"],
            data_start=index.min().date() if est_serie else dt.date(1926, 1, 31),
            data_end=index.max().date() if est_serie else dt.date(2024, 12, 31),
            frequency=Frequency.MONTHLY,
            timezone="",
            exchange=None,
            currency="USD",
            adjusted=True,
            point_in_time=False,
            survivorship_free=True,
            corporate_actions=(
                "portefeuilles construits sur CRSP par les auteurs, rendements de radiation compris"
            ),
            revision_policy=(
                "publication annuelle par les auteurs, les millésimes antérieurs ne sont pas conservés ici"
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
                "rendements en pourcentage dans le fichier, divisés par cent ici ; long moins court, "
                "brut de frais"
            ),
        )


__all__ = ["DOC_COLUMNS", "FILE_IDS", "OsapProvider", "parse_long_short_csv", "parse_signal_doc"]
