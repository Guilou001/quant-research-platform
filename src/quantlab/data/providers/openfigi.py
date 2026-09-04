"""OpenFIGI : de l'identifiant CUSIP d'une position déclarée au symbole boursier.

**Le problème.** Les jeux 13F de la SEC désignent chaque position par son
CUSIP, et les prix se demandent par symbole. OpenFIGI, l'annuaire ouvert de
Bloomberg, rend pour un CUSIP le symbole, le FIGI composite et le type de
titre. Sans clé, l'interface accepte vingt-cinq requêtes par minute, mesuré
le 2026-09-04 par l'en-tête de réponse, et dix identifiants par requête.

**Ce qui n'est pas trouvé.** Un CUSIP radié depuis longtemps rend une réponse
vide, mesuré sur Lehman Brothers. L'absence est rendue telle quelle, et c'est
l'appelant qui la compte, parce que ce décompte mesure le biais de survie d'un
portefeuille reconstruit.

**Provenance.** OpenFIGI, interface de correspondance, version 3.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

import pandas as pd
import requests

from quantlab.core.errors import DataQualityError
from quantlab.data.providers.base import SourceUnavailableError

MAPPING_URL: Final[str] = "https://api.openfigi.com/v3/mapping"
#: Sans clé, dix identifiants par requête et vingt-cinq requêtes par minute.
JOBS_PER_REQUEST: Final[int] = 10
PAUSE_S: Final[float] = 2.5
COLUMNS: Final[tuple[str, ...]] = ("cusip", "ticker", "composite_figi", "security_type", "name", "found")


def parse_mapping_response(cusips: Sequence[str], payload: list[dict[str, Any]]) -> pd.DataFrame:
    """Lit la réponse d'une requête de correspondance, un enregistrement par CUSIP demandé.

    Le premier titre coté aux États-Unis est retenu ; à défaut, le premier
    rendu ; à défaut, la ligne porte ``found`` à faux.
    """
    if len(payload) != len(cusips):
        raise DataQualityError(f"{len(payload)} réponses pour {len(cusips)} identifiants.")
    lignes = []
    for cusip, reponse in zip(cusips, payload, strict=True):
        candidats = reponse.get("data") or []
        americains = [c for c in candidats if c.get("exchCode") == "US"]
        choisi = (americains or candidats or [None])[0]
        if choisi is None:
            lignes.append(
                {
                    "cusip": cusip,
                    "ticker": None,
                    "composite_figi": None,
                    "security_type": None,
                    "name": None,
                    "found": False,
                }
            )
        else:
            lignes.append(
                {
                    "cusip": cusip,
                    "ticker": choisi.get("ticker"),
                    "composite_figi": choisi.get("compositeFIGI"),
                    "security_type": choisi.get("securityType"),
                    "name": choisi.get("name"),
                    "found": True,
                }
            )
    return pd.DataFrame(lignes, columns=list(COLUMNS))


class OpenFigiMapper:
    """Correspondance CUSIP vers symbole, avec un cache sur disque et la cadence de l'interface."""

    def __init__(
        self,
        cache_path: Path,
        *,
        session: Any | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        pause_s: float = PAUSE_S,
        user_agent: str = "quantlab research",
    ) -> None:
        self._cache_path = Path(cache_path)
        self._session = session or requests.Session()
        self._sleeper = sleeper
        self._pause_s = pause_s
        self._user_agent = user_agent
        self._cache: dict[str, dict[str, Any]] = {}
        if self._cache_path.exists():
            self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")

    def map(self, cusips: Sequence[str]) -> pd.DataFrame:
        """Rend la correspondance des CUSIP demandés, du cache d'abord, de l'interface ensuite."""
        uniques = sorted({c.strip().upper() for c in cusips if isinstance(c, str) and c.strip()})
        manquants = [c for c in uniques if c not in self._cache]
        for debut in range(0, len(manquants), JOBS_PER_REQUEST):
            lot = manquants[debut : debut + JOBS_PER_REQUEST]
            corps = [{"idType": "ID_CUSIP", "idValue": c} for c in lot]
            reponse = self._session.post(
                MAPPING_URL,
                json=corps,
                headers={"Content-Type": "application/json", "User-Agent": self._user_agent},
                timeout=60,
            )
            if reponse.status_code == 429:
                self._sleeper(60.0)
                reponse = self._session.post(
                    MAPPING_URL,
                    json=corps,
                    headers={"Content-Type": "application/json", "User-Agent": self._user_agent},
                    timeout=60,
                )
            if reponse.status_code != 200:
                raise SourceUnavailableError(f"OpenFIGI répond {reponse.status_code}.", url=MAPPING_URL)
            tableau = parse_mapping_response(lot, reponse.json())
            for ligne in tableau.to_dict(orient="records"):
                self._cache[ligne["cusip"]] = ligne
            self._save()
            self._sleeper(self._pause_s)
        return pd.DataFrame([self._cache[c] for c in uniques], columns=list(COLUMNS))


__all__ = ["OpenFigiMapper", "parse_mapping_response"]
