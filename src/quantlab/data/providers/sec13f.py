"""Les jeux de données 13F de la SEC : ce que chaque gestionnaire déclarait, et le jour où il l'a déclaré.

**Le problème.** Les positions des gestionnaires sont publiques, mais lues
sans leur date de dépôt elles font un backtest qui connaît le trimestre avant
sa fin. La SEC publie les déclarations 13F en jeux structurés, un fichier compressé
par trimestre. Chaque déclaration y porte sa date de dépôt, et chaque ligne
le CUSIP, le FIGI, la valeur et le nombre de titres.

**La source.** ``https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets``,
53 fichiers du deuxième trimestre 2013 à 2026, mesuré le 2026-09-04 ; le
fichier du quatrième trimestre 2023 pèse 73 Mo et sa table de positions 294 Mo
une fois décompressée. La SEC exige un en-tête d'identification et limite le
débit, ce que le client du socle applique.

**Le piège des unités.** Jusqu'aux dépôts de 2022, la colonne ``VALUE`` est
en milliers de dollars. Depuis janvier 2023, la SEC la demande en dollars,
et certains déclarants ont changé avant ou après la date. Mesuré sur la
première version de l'étude 020 : lue en dollars, la borne de cent millions
ne retenait que cinq déclarations par trimestre avant 2023, contre plus de
cinq cents après. L'unité se détecte donc déclaration par déclaration, par
la médiane de la valeur par titre. Sous un dollar, la déclaration est en
milliers et se multiplie par mille ; au-delà de cinq mille dollars, elle est
suspecte, et l'étude l'écarte. Mesuré sur le quatrième trimestre 2018 :
4 893 déclarations qui tiennent Apple sont en milliers et redonnent 225,74 $
par titre. 199 sont lues en dollars, et la moitié de celles-ci donnent
22 574 $, cent fois le cours. La colonne ``value_unit`` garde le diagnostic.

**Provenance.** Données publiques de la SEC. Employées par l'étude 020.
"""

from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
from typing import Any, ClassVar, Final

import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, LookAheadError
from quantlab.core.logging import stage
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest
from quantlab.data.providers.base import BaseProvider

SEC13F_PROVIDER_NAME: Final[str] = "sec13f"
INDEX_URL: Final[str] = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
BASE_URL: Final[str] = "https://www.sec.gov"
LICENSE: Final[str] = "Données publiques de la SEC, usage libre avec identification"
LICENSE_URL: Final[str] = "https://www.sec.gov/privacy#security"
PROCESSING_VERSION: Final[str] = "1.0.0"
SUBMISSION_COLUMNS: Final[dict[str, str]] = {
    "ACCESSION_NUMBER": "accession",
    "FILING_DATE": "filing_date",
    "SUBMISSIONTYPE": "submission_type",
    "CIK": "cik",
    "PERIODOFREPORT": "period_end",
}
COVERPAGE_COLUMNS: Final[dict[str, str]] = {
    "ACCESSION_NUMBER": "accession",
    "FILINGMANAGER_NAME": "manager_name",
    "ISAMENDMENT": "is_amendment",
    "REPORTTYPE": "report_type",
}
INFOTABLE_COLUMNS: Final[dict[str, str]] = {
    "ACCESSION_NUMBER": "accession",
    "NAMEOFISSUER": "issuer",
    "TITLEOFCLASS": "title_of_class",
    "CUSIP": "cusip",
    "FIGI": "figi",
    "VALUE": "value_usd",
    "SSHPRNAMT": "shares",
    "SSHPRNAMTTYPE": "shares_type",
    "PUTCALL": "put_call",
    "INVESTMENTDISCRETION": "discretion",
}


def parse_index(html: str) -> list[str]:
    """Rend les adresses des fichiers compressés listés sur la page des jeux 13F, triées."""
    liens = sorted(set(re.findall(r'href="([^"]+form13f[^"]*\.zip)"', html)))
    if not liens:
        raise DataQualityError("aucun fichier 13F trouvé sur la page d'index.")
    return [lien if lien.startswith("http") else BASE_URL + lien for lien in liens]


def _member(z: zipfile.ZipFile, name: str) -> str:
    """Rend le membre dont le nom de base est ``name``, la casse et le dossier variant selon les fichiers.

    Les fichiers trimestriels rangent les tables à la racine ; les fichiers
    par fenêtre de trois mois, depuis 2024, les rangent dans un dossier en
    majuscules. Mesuré le 2026-09-04.
    """
    cible = name.lower()
    for membre in z.namelist():
        if membre.rsplit("/", 1)[-1].lower() == cible:
            return membre
    raise DataQualityError(f"table {name} absente du fichier 13F.")


def _read_tsv(z: zipfile.ZipFile, name: str, columns: dict[str, str]) -> pd.DataFrame:
    with z.open(_member(z, name)) as fichier:
        frame = pd.read_csv(
            fichier,
            sep="\t",
            dtype=str,
            usecols=lambda c: c in columns,
            encoding="utf-8",
            encoding_errors="replace",
            quoting=3,
        )
    manquantes = [c for c in columns if c not in frame.columns and c != "FIGI"]
    if manquantes:
        raise DataQualityError(f"colonnes absentes de {name} : {manquantes}.")
    if "FIGI" in columns and "FIGI" not in frame.columns:
        frame["FIGI"] = None
    return frame.rename(columns=columns)


THOUSANDS_THRESHOLD_USD_PER_SHARE: Final[float] = 1.0
SUSPECT_THRESHOLD_USD_PER_SHARE: Final[float] = 5000.0


def normalize_value_units(positions: pd.DataFrame) -> pd.DataFrame:
    """Ramène ``value_usd`` en dollars, déclaration par déclaration.

    Une déclaration dont la médiane de la valeur par titre est sous un dollar
    est lue en milliers. Aucun portefeuille de dix à cinquante actions n'a
    une action médiane sous un dollar, mais toutes en ont une sous mille.
    Une médiane au-delà de cinq mille dollars n'est ni l'un ni l'autre, et la
    déclaration est marquée suspecte sans correction. Les lignes sans nombre
    de titres suivent le diagnostic de leur déclaration.

    Args:
        positions: la table ``holdings`` avec ``accession``, ``value_usd`` et ``shares``.

    Returns:
        La même table, ``value_usd`` en dollars et ``value_unit`` valant
        ``"thousands"``, ``"dollars"`` ou ``"suspect"`` selon ce qui a été lu.
    """
    if positions.empty:
        return positions.assign(value_unit=pd.Series(dtype="object"))
    par_titre = positions["value_usd"] / positions["shares"].where(positions["shares"] > 0)
    mediane = par_titre.groupby(positions["accession"]).median()
    diagnostic = pd.Series("dollars", index=mediane.index, dtype="object")
    diagnostic[mediane < THOUSANDS_THRESHOLD_USD_PER_SHARE] = "thousands"
    diagnostic[mediane >= SUSPECT_THRESHOLD_USD_PER_SHARE] = "suspect"
    unite = positions["accession"].map(diagnostic).fillna("dollars")
    resultat = positions.copy()
    en_milliers = unite.eq("thousands")
    resultat.loc[en_milliers, "value_usd"] = resultat.loc[en_milliers, "value_usd"] * 1000.0
    resultat["value_unit"] = unite
    return resultat


def parse_quarter(content: bytes) -> dict[str, pd.DataFrame]:
    """Lit un fichier compressé trimestriel et rend ses trois tables typées.

    Args:
        content: le contenu du fichier compressé.

    Returns:
        ``submissions`` (accession, date de dépôt, type, CIK, fin de période).
        ``coverpages`` (accession, nom du gestionnaire, amendement, type de
        rapport). ``holdings`` (accession, émetteur, CUSIP, FIGI, valeur
        ramenée en dollars et unité lue, titres, option, discrétion).

    Raises:
        LookAheadError: une déclaration est déposée avant la fin de sa période.
        DataQualityError: une table ou une colonne manque.
    """
    z = zipfile.ZipFile(io.BytesIO(content))
    soumissions = _read_tsv(z, "SUBMISSION.tsv", SUBMISSION_COLUMNS)
    soumissions["filing_date"] = pd.to_datetime(soumissions["filing_date"], format="%d-%b-%Y")
    soumissions["period_end"] = pd.to_datetime(soumissions["period_end"], format="%d-%b-%Y")
    avant = soumissions["filing_date"] < soumissions["period_end"]
    if avant.any():
        exemple = soumissions.loc[avant].iloc[0]
        raise LookAheadError(
            f"{int(avant.sum())} déclaration(s) déposée(s) avant la fin de leur période, "
            f"par exemple {exemple['accession']} le {exemple['filing_date'].date()}."
        )
    couvertures = _read_tsv(z, "COVERPAGE.tsv", COVERPAGE_COLUMNS)
    positions = _read_tsv(z, "INFOTABLE.tsv", INFOTABLE_COLUMNS)
    positions["value_usd"] = pd.to_numeric(positions["value_usd"], errors="coerce")
    positions["shares"] = pd.to_numeric(positions["shares"], errors="coerce")
    positions = normalize_value_units(positions)
    return {"submissions": soumissions, "coverpages": couvertures, "holdings": positions}


class SecForm13FProvider(BaseProvider):
    """Les jeux 13F trimestriels de la SEC, gardés compressés dans le cache brut."""

    name: ClassVar[str] = SEC13F_PROVIDER_NAME

    def __init__(self, **kwargs: Any) -> None:
        """Construit le fournisseur, arguments passés à :class:`BaseProvider`."""
        super().__init__(**kwargs)
        self._last: dict[str, Any] | None = None

    def quarter_files(self, *, refresh: bool = False) -> list[str]:
        """Rend les adresses des fichiers trimestriels listés par la SEC."""
        raw = self.fetch_cached(INDEX_URL, label="index", refresh=refresh)
        return parse_index(raw.text())

    def quarter(self, url: str, *, refresh: bool = False) -> dict[str, pd.DataFrame]:
        """Télécharge et lit un fichier trimestriel."""
        etiquette = url.rsplit("/", 1)[-1].removesuffix(".zip")
        with stage("sec13f.quarter", provider=self.name, file=etiquette) as payload:
            raw = self.fetch_cached(url, label=etiquette, refresh=refresh)
            tables = parse_quarter(raw.content)
            payload["holdings"] = len(tables["holdings"])
        soumissions = tables["submissions"]
        self._last = {
            "label": etiquette,
            "url": raw.url,
            "checksum": raw.sha256,
            "fetched_at": raw.fetched_at,
            "rows": len(tables["holdings"]),
            "columns": tuple(tables["holdings"].columns),
            "start": soumissions["period_end"].min().date(),
            "end": soumissions["filing_date"].max().date(),
        }
        return tables

    def fetch(self, *, start: dt.date | str, end: dt.date | str, **kwargs: Any) -> pd.DataFrame:
        """Rend les positions de tous les trimestres dont la période finit entre deux dates."""
        debut, fin = pd.Timestamp(start), pd.Timestamp(end)
        morceaux = []
        for url in self.quarter_files():
            tables = self.quarter(url, refresh=bool(kwargs.get("refresh", False)))
            s = tables["submissions"]
            garde = s[(s["period_end"] >= debut) & (s["period_end"] <= fin)]
            if garde.empty:
                continue
            morceaux.append(tables["holdings"].merge(garde, on="accession", how="inner"))
        if not morceaux:
            raise ConfigError(f"aucune période 13F entre {start} et {end}.")
        return pd.concat(morceaux, ignore_index=True)

    def manifest(self, **overrides: Any) -> DatasetManifest:
        """Rend le manifeste du dernier fichier lu, point-in-time par la date de dépôt."""
        if self._last is None and not overrides:
            raise ConfigError("aucun fichier lu.")
        base = dict(self._last or {})
        base.update(overrides)
        return DatasetManifest(
            dataset_id=f"sec13f-{str(base.get('label', 'inconnu')).lower()}",
            source="SEC, Form 13F data sets, fichiers trimestriels structurés",
            provider=f"quantlab.data.providers.{self.name}",
            url=str(base["url"]),
            download_timestamp=base["fetched_at"],
            data_start=base.get("start", base["fetched_at"].date()),
            data_end=base.get("end", base["fetched_at"].date()),
            frequency=Frequency.QUARTERLY,
            timezone="America/New_York",
            exchange=None,
            currency="USD",
            adjusted=False,
            point_in_time=True,
            survivorship_free=True,
            corporate_actions="sans objet ; positions déclarées, valeurs en dollars à la fin de période",
            revision_policy="les amendements sont des dépôts distincts, marqués comme tels",
            license=LICENSE,
            license_url=LICENSE_URL,
            checksum_sha256=str(base["checksum"]),
            n_rows=int(base.get("rows", 0)),
            n_columns=len(base.get("columns", ())),
            columns=tuple(base.get("columns", ())),
            processing_version=PROCESSING_VERSION,
            layer=Layer.RAW,
            notes=(
                "la date de dépôt est la date de disponibilité ; le FIGI n'est présent que dans les "
                "fichiers récents"
            ),
        )


__all__ = ["SecForm13FProvider", "parse_index", "parse_quarter"]
