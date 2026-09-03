"""Phase 9. Le pont entre le laboratoire et LEAN, le moteur événementiel de contrôle.

**Le problème.** L'ADR-008 exige qu'une stratégie soit rejouée dans un moteur
écrit par d'autres avant de mériter du capital. LEAN lit ses propres fichiers,
et rend sa propre courbe de richesse. Deux conversions sont donc nécessaires,
l'une à l'entrée, l'autre à la sortie, et chacune est un endroit où un décalage
d'une journée peut naître sans bruit.

**Ce que le module fait.** Il écrit des barres quotidiennes au format de LEAN
depuis une série de prix. Il relit la valeur liquidative que l'algorithme
journalise, et il compare les rendements mensuels des deux moteurs. Il ne porte
aucune logique de stratégie : l'algorithme LEAN est écrit à part, sans importer
ce paquet, et un test mécanique le vérifie.

**La convention d'ouverture.** LEAN remplit un ordre au marché à l'ouverture de
la barre qui suit la décision. Le moteur du laboratoire suppose l'exécution à la
clôture de la barre de décision. Pour que les deux conventions désignent le même
prix, l'ouverture écrite pour le jour ``d`` est la clôture du jour ``d - 1``.
C'est une convention d'export, déclarée ici et dans le rapport de
réconciliation, et non une propriété des données.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError

#: LEAN encode les prix des actions en dix-millièmes de dollar, en entiers.
LEAN_PRICE_SCALE: float = 10_000.0

#: Préfixe des lignes de journal que l'algorithme écrit chaque jour.
PORTFOLIO_VALUE_TAG: str = "PV"


def lean_daily_bars(prices: pd.Series, volume: pd.Series | None = None) -> pd.DataFrame:
    """Construit des barres quotidiennes dont l'ouverture est la clôture de la veille.

    La première barre n'a pas de veille : son ouverture est sa propre clôture.
    Le plus haut et le plus bas encadrent l'ouverture et la clôture, si bien que
    la barre reste cohérente pour tout modèle d'exécution.

    Args:
        prices: les prix de clôture ajustés, indexés par date, sans valeur
            manquante après le premier prix.
        volume: les volumes aux mêmes dates ; absents, ils valent zéro.

    Returns:
        Un tableau ``open``, ``high``, ``low``, ``close``, ``volume`` indexé par
        date croissante.

    Raises:
        DataQualityError: un prix manque, n'est pas fini ou n'est pas positif,
            ou l'index n'est pas croissant.
    """
    serie = prices.dropna().astype(float)
    if serie.empty:
        raise DataQualityError("aucun prix à convertir en barres LEAN.")
    if not serie.index.is_monotonic_increasing:
        raise DataQualityError("les prix doivent être triés par date croissante.")
    if not np.isfinite(serie.to_numpy()).all() or (serie <= 0).any():
        raise DataQualityError("un prix n'est pas fini ou n'est pas strictement positif.")
    ouverture = serie.shift(1).fillna(serie.iloc[0])
    barres = pd.DataFrame(
        {
            "open": ouverture,
            "high": np.maximum(ouverture, serie),
            "low": np.minimum(ouverture, serie),
            "close": serie,
        }
    )
    if volume is None:
        barres["volume"] = 0
    else:
        barres["volume"] = volume.reindex(serie.index).fillna(0.0).round().astype("int64")
    return barres


def format_lean_daily(bars: pd.DataFrame) -> str:
    """Encode des barres au format texte des fichiers quotidiens d'actions de LEAN.

    Une ligne par jour : ``AAAAMMJJ 00:00,ouverture,haut,bas,clôture,volume``,
    les prix en dix-millièmes de dollar arrondis à l'entier.

    Args:
        bars: le tableau rendu par :func:`lean_daily_bars`.

    Returns:
        Le contenu du fichier CSV, une ligne par barre, sans en-tête.
    """
    colonnes = ("open", "high", "low", "close")
    manquantes = [c for c in (*colonnes, "volume") if c not in bars.columns]
    if manquantes:
        raise ConfigError(f"colonnes manquantes pour l'encodage LEAN : {manquantes}.")
    lignes = []
    for date, ligne in bars.iterrows():
        prix = ",".join(str(round(float(ligne[c]) * LEAN_PRICE_SCALE)) for c in colonnes)
        lignes.append(f"{pd.Timestamp(date).strftime('%Y%m%d')} 00:00,{prix},{int(ligne['volume'])}")
    return "\n".join(lignes) + "\n"


def write_lean_daily_zip(root: Path, ticker: str, prices: pd.Series, volume: pd.Series | None = None) -> Path:
    """Écrit ``<root>/equity/usa/daily/<ticker>.zip`` au format de LEAN.

    Args:
        root: la racine du dossier de données que LEAN lira.
        ticker: le symbole, mis en minuscules dans le nom de fichier.
        prices: les prix de clôture ajustés.
        volume: les volumes, facultatifs.

    Returns:
        Le chemin de l'archive écrite.
    """
    dossier = root / "equity" / "usa" / "daily"
    dossier.mkdir(parents=True, exist_ok=True)
    nom = ticker.lower()
    chemin = dossier / f"{nom}.zip"
    contenu = format_lean_daily(lean_daily_bars(prices, volume))
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{nom}.csv", contenu)
    chemin.write_bytes(tampon.getvalue())
    return chemin


def parse_portfolio_value_log(text: str, *, tag: str = PORTFOLIO_VALUE_TAG) -> pd.Series:
    """Relit la valeur liquidative que l'algorithme LEAN journalise chaque jour.

    Chaque ligne utile contient ``<tag>,AAAA-MM-JJ,valeur`` ; LEAN préfixe ses
    lignes de journal par un horodatage et le mot ``Trace``, ce qui est ignoré.

    Args:
        text: le contenu du fichier journal de LEAN.
        tag: le préfixe qui distingue les lignes de valeur liquidative.

    Returns:
        La valeur liquidative indexée par date, triée, sans doublon.

    Raises:
        DataQualityError: aucune ligne ne porte le préfixe, ou une date se
            répète avec deux valeurs différentes.
    """
    marqueur = f"{tag},"
    valeurs: dict[pd.Timestamp, float] = {}
    for ligne in text.splitlines():
        position = ligne.find(marqueur)
        if position < 0:
            continue
        champs = ligne[position + len(marqueur) :].strip().split(",")
        if len(champs) < 2:
            continue
        date = pd.Timestamp(champs[0])
        valeur = float(champs[1])
        if date in valeurs and valeurs[date] != valeur:
            raise DataQualityError(f"deux valeurs liquidatives pour le {date.date()}.")
        valeurs[date] = valeur
    if not valeurs:
        raise DataQualityError("aucune ligne de valeur liquidative dans le journal LEAN.")
    return pd.Series(valeurs, name="portfolio_value").sort_index()


def monthly_returns_from_values(values: pd.Series) -> pd.Series:
    """Rend les rendements mensuels d'une valeur liquidative quotidienne.

    La valeur retenue pour un mois est la dernière observée dans ce mois, et le
    rendement est daté de la fin de mois civile, la convention des études.

    Args:
        values: la valeur liquidative indexée par date de séance.

    Returns:
        Les rendements simples mensuels, le premier mois n'en ayant pas.
    """
    serie = values.dropna().sort_index()
    if serie.empty:
        raise DataQualityError("aucune valeur liquidative à convertir en rendements mensuels.")
    fins = serie.groupby([serie.index.year, serie.index.month]).last()
    dates = serie.index.to_series().groupby([serie.index.year, serie.index.month]).max()
    mensuel = pd.Series(fins.to_numpy(), index=pd.DatetimeIndex(dates.to_numpy()))
    mensuel.index = mensuel.index.to_period("M").to_timestamp("M")
    return mensuel.pct_change().dropna().rename("monthly_return")


def reconcile_monthly(
    lab_excess: pd.Series,
    lean_total: pd.Series,
    financing: pd.Series,
) -> pd.DataFrame:
    r"""Aligne les deux moteurs sur les mois communs et mesure leur écart.

    **La formule de passage.** Le laboratoire travaille en rendements
    excédentaires et LEAN en rendements totaux, sans rémunération de
    l'encaisse ni coût d'emprunt. Sur un mois où les poids exécutés somment à
    :math:`\sum_i w_i` et où le taux sans risque vaut :math:`r_f`,

    .. math::

        r^{\text{LEAN}}_t = r^{\text{lab}}_t + r_{f,t} \sum_i w_{i,t}

    Le terme de financement est donc retranché à LEAN avant comparaison.

    Args:
        lab_excess: les rendements mensuels excédentaires bruts du laboratoire.
        lean_total: les rendements mensuels totaux tirés de LEAN.
        financing: :math:`r_{f,t} \sum_i w_{i,t}`, aux mêmes dates.

    Returns:
        Un tableau indexé par mois commun : ``lab``, ``lean_total``,
        ``financing``, ``lean_excess`` et ``difference`` (LEAN moins
        laboratoire, après passage).
    """
    communs = lab_excess.index.intersection(lean_total.index)
    if len(communs) == 0:
        raise DataQualityError("aucun mois commun entre le laboratoire et LEAN.")
    tableau = pd.DataFrame(
        {
            "lab": lab_excess.reindex(communs),
            "lean_total": lean_total.reindex(communs),
            "financing": financing.reindex(communs).fillna(0.0),
        }
    )
    tableau["lean_excess"] = tableau["lean_total"] - tableau["financing"]
    tableau["difference"] = tableau["lean_excess"] - tableau["lab"]
    return tableau
