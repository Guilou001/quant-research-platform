"""Où vit chaque chose sur le disque, et pourquoi le lac a quatre étages.

Le lac se lit de bas en haut, et chaque étage a une règle qui ne se négocie pas.

``raw``
    La donnée exactement comme elle est arrivée, octet pour octet, avec son
    horodatage de téléchargement. **Immuable.** On n'y corrige rien : une
    correction dans ``raw`` détruit la seule preuve de ce que la source
    répondait ce jour-là.

``bronze``
    Le même contenu, lisible. Parsage, typage, colonnes nommées, rien d'autre.
    Aucune décision financière n'est prise ici.

``silver``
    La donnée propre : calendrier cohérent, doublons retirés, actions de société
    traitées, devises déclarées. C'est ici que vivent les décisions
    méthodologiques, et chacune est tracée.

``gold``
    Les jeux directement consommables par un facteur, un modèle, un backtest ou
    un optimiseur. Un jeu *gold* porte son manifeste : sans lui, il ne se charge
    pas.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path


class Layer(StrEnum):
    """Les quatre étages du lac de données."""

    RAW = "raw"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


def project_root() -> Path:
    """Rend la racine du dépôt.

    La variable d'environnement ``QUANTLAB_ROOT`` l'emporte si elle est posée,
    ce qui permet de faire tourner le laboratoire sur un disque externe sans
    toucher au code. Sans elle, la racine se déduit de l'emplacement du paquet.
    """
    env = os.environ.get("QUANTLAB_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def data_dir(layer: Layer | str | None = None) -> Path:
    """Rend le répertoire du lac, ou celui d'un étage donné."""
    base = project_root() / "data"
    return base if layer is None else base / Layer(layer).value


def metadata_dir(kind: str | None = None) -> Path:
    """Rend le répertoire des métadonnées : catalogue, manifestes, schémas."""
    base = project_root() / "metadata"
    return base if kind is None else base / kind


def artifacts_dir() -> Path:
    """Rend le répertoire des artefacts d'expérience."""
    return project_root() / "artifacts"


def configs_dir() -> Path:
    """Rend le répertoire des configurations versionnées."""
    return project_root() / "configs"


def studies_dir() -> Path:
    """Rend le répertoire des études, une par réplication."""
    return project_root() / "studies"


def ensure(path: Path) -> Path:
    """Crée le répertoire s'il manque et le rend, pour chaîner l'appel."""
    path.mkdir(parents=True, exist_ok=True)
    return path
