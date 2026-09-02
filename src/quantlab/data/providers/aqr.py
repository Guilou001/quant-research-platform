r"""Les jeux de facteurs d'AQR, et la lecture de leurs classeurs Excel.

**La règle d'usage, avant tout le reste.** Ces séries sont la CIBLE de nos
réplications, jamais leur INTRANT. Frazzini et Pedersen publient le facteur BAB
qu'ils ont construit. Notre travail est de le reconstruire depuis les prix, puis
de mesurer ce qui sépare les deux séries. Un backtest qui prendrait la colonne
« USA » de « BAB Factors » comme signal ne réplique rien, il recopie. Son alpha
mesurerait alors la qualité du travail d'AQR, et non le nôtre. Le module sert à
poser côte à côte notre construction et la leur.

**Le problème de lecture.** Ces classeurs ne sont pas des tableaux. Chaque
feuille commence par quinze à vingt et une lignes de prose libre, titre, résumé,
référence de l'article, mention de droit d'auteur, renvoi aux avertissements.
Vient ensuite une ou deux lignes de titres de groupe, puis la ligne d'en-tête
réelle, puis les données, puis des centaines de lignes vides. Le rang de la
ligne d'en-tête change d'un fichier à l'autre, mesuré le 2026-09-02 : la
dix-neuvième pour BAB, QMJ et HML Devil, la vingt-deuxième pour VME, la
dix-huitième pour TSMOM.

**Le remède.** La ligne d'en-tête ne se code pas en dur, elle se cherche. La
première ligne dont la première cellule se lit comme une date ouvre les données,
et la ligne juste au-dessus porte les noms de colonnes. La règle tient sur les
cinq fichiers sans exception, y compris sur TSMOM dont la cellule d'en-tête de
la colonne des dates est VIDE, ce qu'une recherche du mot « DATE » manquerait.

**Ce que les dates sont vraiment.** Deux formes coexistent, mesurées le
2026-09-02. TSMOM écrit un nombre de série Excel mis en forme par le format
natif 14, ainsi 31078 pour le 31 janvier 1985. Les quatre autres écrivent du
TEXTE au format « MM/DD/YYYY ». La convention mois d'abord est prouvée par la
première ligne de « BAB Factors », « 12/31/1930 », dont le 31 ne peut pas être
un mois.

**Ce que les valeurs sont vraiment.** Toutes les feuilles de rendement portent
des DÉCIMALES, pas des pourcentages. Le doute vient de la mise en forme. Les
cellules de « BAB Factors » portent le format 10, soit « 0.00% ». Excel affiche
donc 1,35 % là où le fichier stocke 0,0135, et diviser par cent après lecture
serait une faute d'un facteur cent. Mesuré sur les cinq fichiers le 2026-09-02,
la plus grande valeur absolue d'une feuille de rendement vaut 0,79885. Elle est
négative, et elle se trouve sur la colonne « ISR » de la feuille « MKT », en
février 1995.

Une seule feuille échappe à la règle, « ME(t-1) », qui porte des
capitalisations boursières en millions de dollars américains, de 7,79 à
123 289 465. Sa fiche la déclare par ``kind="level"``, et le contrôle d'échelle
ne s'y applique pas.

**Pourquoi ce module lit le format XLSX lui-même.** Le projet ne déclare aucun
moteur Excel dans ``pyproject.toml``, vérifié le 2026-09-02 : ni ``openpyxl``,
ni ``python-calamine``, ni ``xlrd``. Un appel à ``pandas.read_excel`` lèverait
donc ``ImportError`` sur une installation propre. La lecture est écrite ici sur
la bibliothèque standard, ``zipfile`` et ``xml.etree``, ce qui rend le module
utilisable sans ajouter de dépendance.

**La date d'une ligne n'est pas sa date de disponibilité.** L'index rendu est
une fin de PÉRIODE, jamais une date de publication, et AQR publie avec des
semaines de retard. Deux mesures, prises le 2026-09-02 sur l'en-tête
``Last-Modified`` des cinq classeurs. La dernière ligne de BAB, QMJ, HML Devil
et VME porte le 2026-06-30 dans un fichier modifié le 2026-08-26, soit 57 jours
plus tard. Celle de TSMOM porte le 2026-05-29 dans un fichier modifié le
2026-06-26, soit 28 jours plus tard. Une stratégie qui lit la ligne du
2026-06-30 et agit le 30 juin 2026 emploie donc un nombre qui n'existait pas
avant le 26 août. Le chiffre du retard est :data:`PUBLICATION_LAG`, et il n'y a
aucune date de disponibilité dans ces fichiers : elle se pose par hypothèse, à
la charge de l'étude, et le manifeste le déclare par ``point_in_time=False``.

**Licence, et la conséquence pratique.** Les conditions d'utilisation du site
d'AQR interdisent la redistribution. Le cache brut de ``data/raw/aqr/`` ne se
commite donc pas, et aucune de ces séries ne se republie. Le texte exact est
cité dans :data:`LICENSE`, lu le 2026-09-02.

Exemple :

.. code-block:: python

    provider = AqrProvider()
    tsmom = provider.tsmom_factors()
    ecart = notre_bab["USA"] - provider.bab_factors()["USA"]
"""

from __future__ import annotations

import datetime as dt
import io
import zipfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, Final
from xml.etree import ElementTree

import numpy as np
import pandas as pd

from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.logging import get_logger
from quantlab.core.paths import Layer
from quantlab.core.types import Frequency
from quantlab.data.manifest import DatasetManifest
from quantlab.data.providers.base import BaseProvider, HttpClient, RawResponse
from quantlab.data.providers.french import slice_period

log = get_logger(__name__)

__all__ = [
    "BASE_URL",
    "COPYRIGHT_BY_DATASET",
    "CURRENCY",
    "DEFAULT_DATASET",
    "EXCEL_1900_PHANTOM_SERIAL",
    "LICENSE",
    "LICENSE_URL",
    "PROCESSING_VERSION",
    "PUBLICATION_LAG",
    "RETURN_ABS_MAX_DECIMAL",
    "REVISION_POLICY",
    "SOURCE_NAME",
    "TEXT_DATE_FORMATS",
    "TIMEZONE",
    "XLSX_SIGNATURE",
    "AqrDatasetSpec",
    "AqrProvider",
    "AqrSheetSpec",
    "Sheet",
    "Workbook",
    "available_datasets",
    "detect_header_row",
    "excel_serial_to_datetime",
    "parse_date_cell",
    "percent_scale_suspected",
    "read_workbook",
    "resolve_dataset",
    "sheet_to_frame",
]

# --------------------------------------------------------------------------- #
# Constantes de source
# --------------------------------------------------------------------------- #

#: Racine des classeurs. Mesurée le 2026-09-02 : les cinq noms de
#: :func:`available_datasets` répondent 200 sur cette racine, et leurs tailles
#: sont celles de :attr:`AqrDatasetSpec.file_bytes`.
BASE_URL: Final[str] = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"

#: Signature d'un classeur XLSX, qui est une archive ZIP. Une page d'erreur en
#: HTML arrive avec un code 200 et se lirait sinon comme un classeur vide.
XLSX_SIGNATURE: Final[bytes] = b"PK"

#: Jeu utilisé quand l'appelant n'en nomme aucun. TSMOM est retenu parce qu'il
#: est le plus petit des cinq, 139 830 octets.
DEFAULT_DATASET: Final[str] = "tsmom"

#: Nom lisible de la source, pour le manifeste.
SOURCE_NAME: Final[str] = "AQR Capital Management, LLC, jeux de données publics"

#: Adresse du texte de licence.
LICENSE_URL: Final[str] = "https://www.aqr.com/Terms-of-Use"

#: La licence, citée telle qu'elle est publiée. Contrairement à la bibliothèque
#: de Kenneth French, AQR ne publie aucune clause d'usage académique : ses
#: conditions d'utilisation interdisent la redistribution sans accord écrit.
#: Cherché le 2026-09-02 sur la page du jeu BAB et sur les conditions
#: d'utilisation, aucune demande de citation explicite n'y figure, et ce point
#: est déclaré non trouvé. La référence de l'article reste due par usage
#: académique, et chaque fiche porte la mention de droit d'auteur du classeur.
LICENSE: Final[str] = (
    "propriété d'AQR Capital Management, LLC ; redistribution interdite sans accord écrit "
    "préalable, selon les conditions d'utilisation lues le 2026-09-02 : « You may not reproduce, "
    "modify, copy, alter in any way, distribute, sell, resell, transmit, transfer, license, assign "
    "or publish any information obtained from this Website without AQR's express prior written "
    "consent. » ; aucune clause d'usage non commercial ni demande de citation trouvée sur la page "
    "du jeu"
)

#: Politique de révision, citée mot pour mot depuis la feuille de facteurs, lue
#: le 2026-09-02. Le texte n'est pas le même partout, et la ligne non plus. BAB,
#: QMJ et HML Devil écrivent à leur ligne 12, VME à sa ligne 15 : « AQR
#: reconstructs the full history each time the portfolios are updated. » TSMOM
#: écrit à sa ligne 12 « each time the returns are updated », et non
#: « portfolios ».
REVISION_POLICY: Final[str] = (
    "histoire entière reconstruite à chaque mise à jour, révisions rétroactives comprises, "
    "sans conservation des millésimes précédents par la source"
)

#: Retard de publication, MESURÉ le 2026-09-02 en confrontant la dernière ligne
#: de chaque classeur à son en-tête HTTP ``Last-Modified``. C'est le nombre qui
#: décide si une étude a le droit d'employer la ligne d'un mois à la fin de ce
#: mois, et la réponse est non.
PUBLICATION_LAG: Final[str] = (
    "la dernière observation est publiée avec des semaines de retard : 57 jours pour BAB, QMJ, "
    "HML Devil et VME au 2026-09-02 (ligne du 2026-06-30, fichier modifié le 2026-08-26), "
    "28 jours pour TSMOM (ligne du 2026-05-29, fichier modifié le 2026-06-26) ; l'index est une "
    "fin de période et jamais une date de disponibilité"
)

#: Traitement des actions de société. Les séries sont des rendements totaux en
#: excès du taux sans risque, dividendes réinvestis.
CORPORATE_ACTIONS: Final[str] = (
    "rendements totaux en excès du taux sans risque, dividendes réinvestis, divisions ajustées"
)

#: Devise des montants. Les facteurs sont des rendements, donc sans unité, mais
#: la feuille « ME(t-1) » porte des capitalisations en dollars américains.
CURRENCY: Final[str] = "USD"

#: Fuseau des horodatages. Les dates sont des fins de mois sans heure, si bien
#: que le fuseau ne sert qu'à les situer.
TIMEZONE: Final[str] = "America/New_York"

#: Version du code de lecture. Elle change dès qu'une convention change, par
#: exemple la détection de l'en-tête ou la lecture des dates.
PROCESSING_VERSION: Final[str] = "aqr-1.1.0"

#: Mentions de droit d'auteur, recopiées caractère pour caractère de la feuille
#: de facteurs de chaque classeur, lues le 2026-09-02. Elles se trouvent à la
#: ligne 13 pour BAB, QMJ, HML Devil et TSMOM, et à la ligne 16 pour VME, dont
#: la mise en page compte trois lignes de prose de plus. Le symbole « © » est
#: dans le fichier et il est gardé : une citation se recopie ou n'en est pas
#: une. Elles nomment les auteurs des articles, et non AQR, ce qui est la raison
#: de les garder séparées de :data:`LICENSE`.
COPYRIGHT_BY_DATASET: Final[Mapping[str, str]] = MappingProxyType(
    {
        "bab": "Copyright ©2014 Andrea Frazzini and Lasse Heje Pedersen",
        "qmj": "Copyright ©2014 Cliff Asness, Andrea Frazzini and Lasse Heje Pedersen",
        "hml_devil": "Copyright ©2013 Cliff Asness and Andrea Frazzini",
        "vme": "Copyright ©2013 Cliff Asness, Tobias Moskowitz and Lasse Heje Pedersen",
        "tsmom": "Copyright ©2012 Tobias Moskowitz, Yao Hua Ooi, and Lasse Heje Pedersen",
    }
)

#: Formats de date acceptés pour une cellule de date écrite en TEXTE. Le premier
#: est celui des quatre classeurs qui n'emploient pas de nombre de série ; le
#: second couvre une écriture ISO, au cas où un millésime changerait d'avis.
#: L'ordre décide en cas d'ambiguïté, et le mois vient d'abord.
TEXT_DATE_FORMATS: Final[tuple[str, ...]] = ("%m/%d/%Y", "%Y-%m-%d")

#: Plus grande valeur absolue admise sur une feuille de rendement avant de
#: soupçonner une échelle en pourcentage. Mesuré le 2026-09-02 sur les cinq
#: fichiers, le maximum réel vaut 0,79885, sur la colonne « ISR » de « MKT »,
#: en février 1995. Un passage au pourcentage multiplierait cette valeur par
#: cent, et le seuil de 1,0 laisse donc une marge d'un quart avant l'alerte.
RETURN_ABS_MAX_DECIMAL: Final[float] = 1.0

# --------------------------------------------------------------------------- #
# Lecture du format XLSX, sur la bibliothèque standard
# --------------------------------------------------------------------------- #

#: Espace de noms du contenu d'une feuille et du classeur.
_MAIN_NS: Final[str] = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

#: Espace de noms des identifiants de relation, portés par l'attribut « r:id ».
_DOC_REL_NS: Final[str] = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

#: Espace de noms du fichier de relations lui-même.
_PKG_REL_NS: Final[str] = "{http://schemas.openxmlformats.org/package/2006/relationships}"

#: Chemin du classeur dans l'archive.
_WORKBOOK_PATH: Final[str] = "xl/workbook.xml"

#: Chemin du fichier de relations du classeur.
_WORKBOOK_RELS_PATH: Final[str] = "xl/_rels/workbook.xml.rels"

#: Identifiants de format natifs qui désignent une date ou une heure. La liste
#: vient de la norme ECMA-376, partie 1, tableau des formats prédéfinis. Le
#: format 14 est celui des dates de TSMOM, mesuré le 2026-09-02.
_BUILTIN_DATE_FORMATS: Final[frozenset[int]] = frozenset(
    {14, 15, 16, 17, 18, 19, 20, 21, 22, 27, 30, 36, 45, 46, 47, 50, 57}
)

#: Lettres qui, dans un format personnalisé débarrassé de ses littéraux,
#: signalent une date ou une heure. La lettre « m » est ambiguë entre mois et
#: minute, et les deux sont des composantes de temps.
_DATE_FORMAT_LETTERS: Final[frozenset[str]] = frozenset("ymdhs")

#: Origine du calendrier de 1900, une fois corrigé le décalage historique. Le
#: numéro de série 61 tombe sur le 1er mars 1900.
_EPOCH_1900 = dt.datetime(1899, 12, 30)

#: Origine des numéros de série antérieurs au 1er mars 1900, période où le
#: calendrier de 1900 ne porte pas encore son jour fantôme.
_EPOCH_1900_BEFORE_BUG = dt.datetime(1899, 12, 31)

#: Origine du calendrier de 1904, employé par les anciens classeurs Macintosh.
_EPOCH_1904 = dt.datetime(1904, 1, 1)

#: Numéro de série du 29 février 1900, jour qui n'a jamais existé. Excel le
#: porte pour rester compatible avec un défaut de Lotus 1-2-3, et aucune date
#: réelle ne lui correspond.
EXCEL_1900_PHANTOM_SERIAL: Final[int] = 60


@dataclass(frozen=True, eq=False)
class Sheet:
    """Une feuille lue, réduite à son nom et à sa grille de valeurs.

    Attributes:
        name: le nom de l'onglet, tel que le classeur l'écrit.
        rows: les lignes, chacune un tuple de valeurs. Une cellule vide vaut
            ``None``. Les lignes sont complétées à la largeur de la plus large,
            si bien que toutes ont la même longueur.
    """

    name: str
    rows: tuple[tuple[object, ...], ...]

    def __len__(self) -> int:
        """Rend le nombre de lignes de la feuille."""
        return len(self.rows)

    @property
    def n_columns(self) -> int:
        """Rend le nombre de colonnes, zéro pour une feuille vide."""
        return len(self.rows[0]) if self.rows else 0


@dataclass(frozen=True, eq=False)
class Workbook:
    """Un classeur lu, ses feuilles dans l'ordre du document.

    Attributes:
        sheets: les feuilles, dans l'ordre où le classeur les déclare.
        date1904: vrai si le classeur compte ses dates depuis 1904.
    """

    sheets: tuple[Sheet, ...]
    date1904: bool = False

    @property
    def names(self) -> tuple[str, ...]:
        """Rend les noms des feuilles, dans l'ordre du document."""
        return tuple(sheet.name for sheet in self.sheets)

    def sheet(self, name: str) -> Sheet:
        """Rend une feuille par son nom.

        Args:
            name: le nom de l'onglet, comparé sans tenir compte des espaces de
                bord ni de la casse.

        Returns:
            La feuille demandée.

        Raises:
            KeyError: si aucune feuille ne porte ce nom.
        """
        cible = name.strip().casefold()
        for sheet in self.sheets:
            if sheet.name.strip().casefold() == cible:
                return sheet
        raise KeyError(f"feuille « {name} » absente ; disponibles : {', '.join(self.names)}")

    def __getitem__(self, name: str) -> Sheet:
        """Rend une feuille par son nom."""
        return self.sheet(name)

    def __iter__(self) -> Iterator[Sheet]:
        """Parcourt les feuilles dans l'ordre du document."""
        return iter(self.sheets)

    def __len__(self) -> int:
        """Rend le nombre de feuilles."""
        return len(self.sheets)


def excel_serial_to_datetime(serial: float, *, date1904: bool = False) -> dt.datetime:
    r"""Convertit un numéro de série Excel en date, jour fantôme refusé.

    (1) Le problème : une cellule de date d'un classeur ne contient pas une
    date, elle contient un nombre de jours depuis une origine, et l'origine
    dépend du classeur. (2) L'intuition : ajouter ce nombre de jours à
    l'origine, en tenant compte d'un défaut historique. (3) La règle, pour le
    calendrier de 1900 :

    .. math::

        d(s) = \begin{cases}
            \text{1899-12-31} + s \text{ jours} & \text{si } s < 60,\\
            \text{1899-12-30} + s \text{ jours} & \text{si } s \geq 61.
        \end{cases}

    (4) Les variables : :math:`s` est le numéro de série lu dans la cellule, et
    :math:`d(s)` la date qu'il désigne. (5) L'hypothèse : le classeur suit l'un
    des deux calendriers d'Excel, et aucun autre.

    **Le jour fantôme.** Excel tient le 29 février 1900 pour un jour valide, ce
    que le calendrier grégorien dément, 1900 n'étant pas bissextile. Le défaut
    vient de Lotus 1-2-3 et n'a jamais été corrigé, par compatibilité. Ce sont
    les deux origines qui absorbent le décalage de part et d'autre.

    **Le jour fantôme dure un jour entier.** L'intervalle refusé est
    :math:`[60, 61)` et non le seul entier 60, la partie décimale portant
    l'heure. Sans cette borne, le numéro 60,5 tombait sous la seconde branche et
    rendait le 28 février 1900 à midi. Le numéro 59,5 rend le même instant, si
    bien que deux numéros distincts se confondaient, et qu'un jour inexistant
    était présenté comme réel.

    Args:
        serial: le numéro de série, éventuellement fractionnaire, la partie
            décimale portant l'heure.
        date1904: vrai si le classeur compte depuis le 1er janvier 1904, ce que
            l'élément ``workbookPr`` déclare.

    Returns:
        La date et l'heure désignées.

    Raises:
        DataQualityError: si le numéro tombe dans l'intervalle :math:`[60, 61)`
            sous le calendrier de 1900, ou s'il est négatif.

    Note:
        Provenance (6) : la norme ECMA-376, partie 1, section 18.17.4, décrit
        les deux calendriers. Limites (7) : la conversion ignore le fuseau,
        ce qui convient à des dates de fin de mois sans heure. Alternatives
        (8) : ``openpyxl`` et ``pandas.read_excel`` font le même calcul, au prix
        d'une dépendance que le projet ne déclare pas. Choix (9) : la formule
        tient en six lignes, et l'écrire ici évite un moteur Excel entier.
        Vérification (10) : le numéro 31078 doit rendre le 31 janvier 1985,
        valeur lue en clair dans « Time-Series-Momentum-Factors-Monthly.xlsx »,
        cellule A19 de la feuille « TSMOM Factors ».
    """
    if serial < 0:
        raise DataQualityError(f"numéro de série Excel négatif : {serial}")
    if date1904:
        return _EPOCH_1904 + dt.timedelta(days=float(serial))
    if EXCEL_1900_PHANTOM_SERIAL <= serial < EXCEL_1900_PHANTOM_SERIAL + 1:
        raise DataQualityError(
            f"le numéro de série {serial} tombe le 29 février 1900, jour qui n'existe pas ; "
            "Excel le porte par compatibilité avec Lotus 1-2-3"
        )
    origine = _EPOCH_1900 if serial > EXCEL_1900_PHANTOM_SERIAL else _EPOCH_1900_BEFORE_BUG
    return origine + dt.timedelta(days=float(serial))


def _column_index(reference: str) -> int:
    """Rend l'indice de colonne, compté à zéro, d'une référence comme « AB19 ».

    Les colonnes d'Excel sont numérotées en base vingt-six sans zéro, si bien
    que « A » vaut 1, « Z » vaut 26 et « AA » vaut 27.
    """
    total = 0
    for caractere in reference:
        if not caractere.isalpha():
            break
        total = total * 26 + (ord(caractere.upper()) - ord("A") + 1)
    return total - 1


def _text_of(element: ElementTree.Element) -> str:
    """Rend le texte d'un élément ``si`` ou ``is``, morceaux mis bout à bout.

    Une chaîne partagée est soit un ``t`` unique, soit une suite de ``r``,
    chacun portant son ``t``. Les éléments ``rPh`` portent une transcription
    phonétique japonaise, qui double le texte au lieu de le prolonger, et le
    parcours les saute.
    """
    morceaux: list[str] = []
    for enfant in element:
        if enfant.tag == f"{_MAIN_NS}t":
            morceaux.append(enfant.text or "")
        elif enfant.tag == f"{_MAIN_NS}r":
            for petit in enfant:
                if petit.tag == f"{_MAIN_NS}t":
                    morceaux.append(petit.text or "")
    return "".join(morceaux)


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    """Rend la table des chaînes partagées, vide si le classeur n'en a pas."""
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    racine = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return [_text_of(item) for item in racine.findall(f"{_MAIN_NS}si")]


def _is_date_format(code: str) -> bool:
    """Dit si un code de format personnalisé décrit une date ou une heure.

    Les littéraux sont retirés avant l'examen : le texte entre guillemets, les
    caractères précédés d'une barre oblique inverse et les sections entre
    crochets, qui portent une langue ou une couleur. Ce qui reste ne contient
    de lettre de date que si le format en est un.

    Example:
        Le code « 0.00% » ne contient aucune lettre de date, alors que
        « mm/dd/yyyy » en contient trois.
    """
    nettoye: list[str] = []
    dans_guillemets = False
    dans_crochets = False
    echappe = False
    for caractere in code:
        if echappe:
            echappe = False
            continue
        if caractere == "\\":
            echappe = True
            continue
        if caractere == '"':
            dans_guillemets = not dans_guillemets
            continue
        if not dans_guillemets and caractere == "[":
            dans_crochets = True
            continue
        if not dans_guillemets and caractere == "]":
            dans_crochets = False
            continue
        if not dans_guillemets and not dans_crochets:
            nettoye.append(caractere.lower())
    return any(lettre in _DATE_FORMAT_LETTERS for lettre in nettoye)


def _date_styles(archive: zipfile.ZipFile) -> frozenset[int]:
    """Rend les indices de style dont le format est une date.

    Le style d'une cellule est un indice dans ``cellXfs``, et chaque entrée
    porte un ``numFmtId``. Un identifiant natif se lit dans
    :data:`_BUILTIN_DATE_FORMATS` ; un identifiant personnalisé, à partir de
    164, se lit dans la table ``numFmts`` du même fichier.
    """
    if "xl/styles.xml" not in archive.namelist():
        return frozenset()
    racine = ElementTree.fromstring(archive.read("xl/styles.xml"))
    personnalises: dict[int, str] = {}
    for bloc in racine.findall(f"{_MAIN_NS}numFmts"):
        for fmt in bloc.findall(f"{_MAIN_NS}numFmt"):
            identifiant = fmt.get("numFmtId")
            code = fmt.get("formatCode")
            if identifiant is not None and code is not None:
                personnalises[int(identifiant)] = code
    dates: set[int] = set()
    for bloc in racine.findall(f"{_MAIN_NS}cellXfs"):
        for rang, xf in enumerate(bloc.findall(f"{_MAIN_NS}xf")):
            identifiant = int(xf.get("numFmtId", "0"))
            code = personnalises.get(identifiant)
            if identifiant in _BUILTIN_DATE_FORMATS or (code is not None and _is_date_format(code)):
                dates.add(rang)
    return frozenset(dates)


def _sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    """Rend les couples nom de feuille et chemin d'archive, dans l'ordre.

    L'ordre du document est celui de ``workbook.xml``, et non celui des noms de
    fichiers. Le fichier ``sheet1.xml`` n'est pas toujours la première feuille,
    et se fier au numéro rendrait les onglets dans le désordre.
    """
    classeur = ElementTree.fromstring(archive.read(_WORKBOOK_PATH))
    relations: dict[str, str] = {}
    if _WORKBOOK_RELS_PATH in archive.namelist():
        for relation in ElementTree.fromstring(archive.read(_WORKBOOK_RELS_PATH)):
            if relation.tag == f"{_PKG_REL_NS}Relationship":
                identifiant = relation.get("Id")
                cible = relation.get("Target")
                if identifiant is not None and cible is not None:
                    relations[identifiant] = cible.lstrip("/")
    sorties: list[tuple[str, str]] = []
    for bloc in classeur.findall(f"{_MAIN_NS}sheets"):
        for feuille in bloc.findall(f"{_MAIN_NS}sheet"):
            nom = feuille.get("name", "")
            identifiant = feuille.get(f"{_DOC_REL_NS}id")
            cible = relations.get(identifiant or "")
            if cible is None:
                log.warning("feuille sans relation, ignorée", extra={"sheet": nom})
                continue
            chemin = cible if cible.startswith("xl/") else f"xl/{cible}"
            if chemin not in archive.namelist():
                log.warning("feuille absente de l'archive", extra={"sheet": nom, "path": chemin})
                continue
            sorties.append((nom, chemin))
    return sorties


def _cell_value(
    cellule: ElementTree.Element,
    *,
    chaines: Sequence[str],
    styles_date: frozenset[int],
    date1904: bool,
) -> object:
    """Rend la valeur d'une cellule, décodée selon son type et son format."""
    type_cellule = cellule.get("t", "n")
    if type_cellule == "inlineStr":
        interne = cellule.find(f"{_MAIN_NS}is")
        return _text_of(interne) if interne is not None else None
    noeud = cellule.find(f"{_MAIN_NS}v")
    brut = noeud.text if noeud is not None else None
    if brut is None or brut == "":
        return None
    if type_cellule == "s":
        rang = int(brut)
        return chaines[rang] if 0 <= rang < len(chaines) else None
    if type_cellule in {"str", "e"}:
        return brut
    if type_cellule == "b":
        return brut.strip() == "1"
    nombre = float(brut)
    style = int(cellule.get("s", "-1"))
    if style in styles_date:
        return excel_serial_to_datetime(nombre, date1904=date1904)
    return nombre


def read_workbook(payload: bytes) -> Workbook:
    """Lit un classeur XLSX et rend ses feuilles, sans moteur Excel externe.

    **Ce que la fonction fait.** Un fichier XLSX est une archive ZIP de
    documents XML. La fonction ouvre l'archive, lit la table des chaînes
    partagées, lit les styles pour savoir quelles cellules numériques sont des
    dates, puis parcourt chaque feuille et rend une grille rectangulaire.

    **Ce que la fonction ne fait pas.** Elle ne calcule aucune formule et rend
    la dernière valeur mise en cache par Excel. Elle ignore les cellules
    fusionnées, dont seule la première porte la valeur. Elle ignore aussi les
    images, ce qui a une conséquence mesurée. L'onglet « Disclosures » des cinq
    classeurs d'AQR ne contient qu'une image au format WMF. Il ressort donc
    VIDE, et les avertissements ne sont pas lisibles par programme.

    Args:
        payload: les octets du classeur.

    Returns:
        Le classeur lu, feuilles dans l'ordre du document.

    Raises:
        DataQualityError: si les octets ne forment pas une archive lisible, ou
            si l'archive ne porte pas de classeur.

    Note:
        Vérification : sur le fichier TSMOM, la feuille « TSMOM Factors » doit
        porter 1 209 lignes et 20 colonnes, et sa cellule A19 doit valoir le
        31 janvier 1985. Ces trois nombres sont mesurés le 2026-09-02.
    """
    if not payload.startswith(XLSX_SIGNATURE):
        raise DataQualityError(f"la réponse n'est pas un classeur XLSX ; premiers octets : {payload[:16]!r}")
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise DataQualityError(f"archive XLSX illisible : {exc}") from exc
    with archive:
        if _WORKBOOK_PATH not in archive.namelist():
            raise DataQualityError(f"archive sans « {_WORKBOOK_PATH} », ce n'est pas un classeur")
        racine = ElementTree.fromstring(archive.read(_WORKBOOK_PATH))
        proprietes = racine.find(f"{_MAIN_NS}workbookPr")
        date1904 = bool(proprietes is not None and proprietes.get("date1904") in {"1", "true"})
        chaines = _shared_strings(archive)
        styles_date = _date_styles(archive)
        feuilles: list[Sheet] = []
        for nom, chemin in _sheet_targets(archive):
            feuilles.append(
                Sheet(
                    name=nom,
                    rows=_read_sheet_rows(
                        archive.read(chemin),
                        chaines=chaines,
                        styles_date=styles_date,
                        date1904=date1904,
                    ),
                )
            )
    log.info(
        "classeur XLSX lu",
        extra={"sheets": len(feuilles), "bytes": len(payload), "names": ",".join(s.name for s in feuilles)},
    )
    return Workbook(sheets=tuple(feuilles), date1904=date1904)


def _read_sheet_rows(
    contenu: bytes,
    *,
    chaines: Sequence[str],
    styles_date: frozenset[int],
    date1904: bool,
) -> tuple[tuple[object, ...], ...]:
    """Rend la grille d'une feuille, lignes et colonnes creuses comblées.

    Une feuille XLSX est creuse : une ligne sans valeur peut manquer, et une
    cellule vide aussi. Les indices ``r`` des lignes et des cellules donnent
    leur position réelle, et c'est sur eux que la grille se reconstruit.

    **Quand l'indice manque.** L'attribut ``r`` est facultatif, et un écrivain
    en flux peut l'omettre sur une ligne comme sur une cellule. Le rang de repli
    est alors celui qui suit la ligne précédente, ce que la lecture des cellules
    faisait déjà par sa position dans le document. Sans ce repli, une ligne sans
    ``r`` prenait le rang moins un et disparaissait SANS un mot, ce qui retire
    une observation d'une série de rendements.
    """
    racine = ElementTree.fromstring(contenu)
    par_ligne: dict[int, dict[int, object]] = {}
    largeur = 0
    suivant = 0
    for donnees in racine.findall(f"{_MAIN_NS}sheetData"):
        for ligne in donnees.findall(f"{_MAIN_NS}row"):
            declare = ligne.get("r")
            rang = int(declare) - 1 if declare is not None else suivant
            if rang < 0:
                continue
            suivant = rang + 1
            cellules: dict[int, object] = {}
            for position, cellule in enumerate(ligne.findall(f"{_MAIN_NS}c")):
                reference = cellule.get("r")
                colonne = _column_index(reference) if reference else position
                valeur = _cell_value(cellule, chaines=chaines, styles_date=styles_date, date1904=date1904)
                if valeur is not None:
                    cellules[colonne] = valeur
                    largeur = max(largeur, colonne + 1)
            par_ligne[rang] = cellules
    if not par_ligne:
        return ()
    hauteur = max(par_ligne) + 1
    return tuple(
        tuple(par_ligne.get(rang, {}).get(colonne) for colonne in range(largeur)) for rang in range(hauteur)
    )


# --------------------------------------------------------------------------- #
# Mise en page propre à AQR
# --------------------------------------------------------------------------- #


def parse_date_cell(value: object, *, formats: Sequence[str] = TEXT_DATE_FORMATS) -> pd.Timestamp | None:
    """Rend la date d'une cellule, ou ``None`` si la cellule n'en porte pas.

    **Les deux formes rencontrées.** Un objet ``datetime``, quand la cellule
    portait un numéro de série mis en forme en date, ce que fait TSMOM. Une
    chaîne « MM/DD/YYYY », ce que font BAB, QMJ, VME et HML Devil.

    **Pourquoi le mois vient d'abord.** La première ligne de « BAB Factors »
    écrit « 12/31/1930 », dont le 31 ne peut pas être un mois. La convention
    américaine est donc prouvée par les données, et non supposée.

    Args:
        value: la valeur de la cellule, telle que :func:`read_workbook` la rend.
        formats: les formats de date acceptés pour une cellule en texte, dans
            l'ordre d'essai.

    Returns:
        La date, ou ``None`` si la valeur n'est ni une date ni une chaîne qui en
        porte une.

    Example:
        >>> parse_date_cell("12/31/1930")
        Timestamp('1930-12-31 00:00:00')
        >>> parse_date_cell("EQUITIES") is None
        True
    """
    if isinstance(value, dt.datetime):
        return pd.Timestamp(value)
    if isinstance(value, dt.date):
        return pd.Timestamp(value)
    if not isinstance(value, str):
        return None
    texte = value.strip()
    if not texte:
        return None
    for forme in formats:
        try:
            return pd.Timestamp(dt.datetime.strptime(texte, forme))
        except ValueError:
            continue
    return None


def detect_header_row(rows: Sequence[Sequence[object]]) -> int:
    """Rend l'indice de la ligne d'en-tête, compté à zéro.

    **Le problème.** Le rang de l'en-tête change d'un classeur à l'autre, et le
    coder en dur casse au premier fichier nouveau. Mesuré le 2026-09-02, il vaut
    19 pour BAB, QMJ et HML Devil, 22 pour VME et 18 pour TSMOM, comptés à
    partir de un.

    **La règle.** La première ligne dont la première cellule se lit comme une
    date ouvre les données. La ligne d'en-tête est celle qui la précède
    immédiatement. La règle ne cherche pas le mot « DATE », et c'est ce qui la
    fait tenir sur TSMOM, dont la cellule d'en-tête de la colonne des dates est
    vide.

    Args:
        rows: la grille de la feuille, telle que :class:`Sheet` la porte.

    Returns:
        L'indice de la ligne d'en-tête, compté à zéro.

    Raises:
        InsufficientDataError: si aucune cellule de la première colonne ne se
            lit comme une date, ce qui est le cas des onglets de définitions et
            de sources.
        DataQualityError: si la première ligne de données est la toute première
            ligne de la feuille, cas où aucun en-tête ne la précède.

    Example:
        Sur une feuille dont la troisième ligne porte « DATE » puis la quatrième
        une date, la fonction rend 2.
    """
    for rang, ligne in enumerate(rows):
        if ligne and parse_date_cell(ligne[0]) is not None:
            if rang == 0:
                raise DataQualityError(
                    "la première ligne de la feuille porte déjà une date, aucun en-tête ne la précède"
                )
            return rang - 1
    raise InsufficientDataError(
        "aucune ligne de cette feuille ne commence par une date, elle ne porte pas de tableau daté"
    )


def _clean_column_names(header: Sequence[object]) -> list[tuple[int, str]]:
    """Rend les colonnes gardées : leur position et leur nom, en-tête vide exclu.

    La première colonne est celle des dates et ne figure jamais dans la sortie.
    Les colonnes sans nom sont écartées avec leurs valeurs, et les classeurs
    d'AQR en portent au moins une, tout à droite de la plage déclarée.

    **Pourquoi un nom répété est refusé.** Deux colonnes de même nom donnent un
    tableau où ``frame["USA"]`` rend deux colonnes au lieu d'une série. Le calcul
    qui suit ne lève pas : une moyenne mélange les deux séries, et un ratio de
    Sharpe se calcule sur le mélange. Les cinq classeurs mesurés le 2026-09-02
    n'ont aucun doublon, sur 29 colonnes pour les trois classeurs d'actions et 22
    pour VME, mais un millésime qui en introduirait un corromprait en silence.

    Raises:
        DataQualityError: si deux colonnes portent le même nom.
    """
    gardees: list[tuple[int, str]] = []
    vus: set[str] = set()
    for position, brut in enumerate(header):
        if position == 0:
            continue
        nom = str(brut).strip() if brut is not None else ""
        if not nom:
            continue
        if nom in vus:
            raise DataQualityError(
                f"la ligne d'en-tête porte deux colonnes nommées « {nom} », "
                "et les valeurs des deux se mélangeraient sans rien signaler"
            )
        vus.add(nom)
        gardees.append((position, nom))
    return gardees


def _assert_dates_strictement_croissantes(dates: Sequence[pd.Timestamp], header_row: int) -> None:
    """Refuse une date répétée ou qui recule sous un même en-tête.

    **Le problème.** Une feuille qui empile deux tableaux sous le même en-tête
    rend un index où chaque date paraît deux fois. La lecture ne lève pas, et
    rien en aval ne s'en aperçoit : un rééquilibrage compte le mois deux fois, et
    un ``asof`` retient l'une des deux valeurs sans dire laquelle. Le second bloc
    peut de plus porter des chiffres RÉVISÉS, donc postérieurs, attachés à une
    date antérieure. C'est une fuite temporelle qui entre par la mise en page.

    **La règle.** Sous un en-tête unique, une série mensuelle est strictement
    croissante. Les cinq classeurs d'AQR le sont, mesuré le 2026-09-02 sur les
    huit feuilles de rendement et sur « ME(t-1) ».

    Args:
        dates: les dates lues, dans l'ordre du fichier.
        header_row: l'indice de la ligne d'en-tête, compté à zéro, pour situer
            l'erreur dans le fichier.

    Raises:
        DataQualityError: à la première date qui répète ou qui recule.
    """
    for rang in range(1, len(dates)):
        if dates[rang] > dates[rang - 1]:
            continue
        relation = "répète" if dates[rang] == dates[rang - 1] else "recule sur"
        raise DataQualityError(
            f"sous l'en-tête de la ligne {header_row + 1}, la date {dates[rang].date()} "
            f"{relation} la précédente {dates[rang - 1].date()} ; deux tableaux empilés "
            "donneraient des observations comptées deux fois"
        )


def sheet_to_frame(
    rows: Sequence[Sequence[object]],
    *,
    header_row: int | None = None,
    date_formats: Sequence[str] = TEXT_DATE_FORMATS,
) -> pd.DataFrame:
    """Rend le tableau daté d'une feuille, en-tête détecté et lignes vides retirées.

    **Ce qui est retiré.** Tout ce qui précède l'en-tête, soit quinze à vingt et
    une lignes de prose et une ou deux lignes de titres de groupe. Tout ce qui
    suit la dernière ligne datée, soit des centaines de lignes vides, mesuré à
    3 764 lignes de queue sur la feuille « BAB Factors ». Les colonnes dont
    l'en-tête est vide.

    **Ce qui est conservé.** Les valeurs telles qu'elles sont stockées, sans
    remise à l'échelle. Les trous restent des ``NaN`` visibles, et le fichier en
    porte : la ligne de janvier 1972 de « VME Factors » a une valeur pour
    « MOM^SS » et rien pour « VAL^SS ».

    **Ce qui est refusé.** Un nom de colonne répété et une date qui répète ou qui
    recule. Les deux corrompent en silence, l'un en mélangeant deux séries sous
    un même nom, l'autre en comptant deux fois le même mois.

    Args:
        rows: la grille de la feuille.
        header_row: l'indice de la ligne d'en-tête, compté à zéro. Sans valeur,
            il est détecté par :func:`detect_header_row`.
        date_formats: les formats acceptés pour une date écrite en texte.

    Returns:
        Un tableau indexé par un ``DatetimeIndex`` nommé « date », colonnes en
        ``float``.

    Raises:
        InsufficientDataError: si la feuille ne porte aucune ligne datée, ou
            aucune colonne nommée.
        DataQualityError: si une cellule de données porte un texte qui n'est ni
            vide ni un nombre, si deux colonnes portent le même nom, ou si une
            date répète la précédente ou recule sur elle.

    Note:
        Une ligne non datée intercalée entre deux lignes datées est ignorée, et
        le journal la signale. Aucune des cinq feuilles de facteurs n'en porte,
        mesuré le 2026-09-02, mais une note de bas de tableau en introduirait
        une.
    """
    rang_entete = detect_header_row(rows) if header_row is None else int(header_row)
    if not 0 <= rang_entete < len(rows):
        raise DataQualityError(f"ligne d'en-tête {rang_entete} hors de la feuille, {len(rows)} lignes")
    colonnes = _clean_column_names(rows[rang_entete])
    if not colonnes:
        raise InsufficientDataError(
            f"la ligne d'en-tête {rang_entete + 1} ne porte aucun nom de colonne exploitable"
        )
    dates: list[pd.Timestamp] = []
    valeurs: list[list[float]] = []
    ignorees = 0
    for ligne in rows[rang_entete + 1 :]:
        if not ligne:
            continue
        horodate = parse_date_cell(ligne[0], formats=date_formats)
        if horodate is None:
            if any(cellule not in (None, "") for cellule in ligne):
                ignorees += 1
            continue
        dates.append(horodate)
        valeurs.append(
            [_to_float(ligne[position] if position < len(ligne) else None) for position, _ in colonnes]
        )
    if not dates:
        raise InsufficientDataError(f"aucune ligne datée sous l'en-tête de la ligne {rang_entete + 1}")
    _assert_dates_strictement_croissantes(dates, rang_entete)
    if ignorees:
        log.warning(
            "lignes non datées ignorées sous l'en-tête",
            extra={"header_row": rang_entete + 1, "skipped": ignorees},
        )
    index = pd.DatetimeIndex(dates, name="date")
    return pd.DataFrame(np.array(valeurs, dtype=float), index=index, columns=[nom for _, nom in colonnes])


def _to_float(value: object) -> float:
    """Convertit une cellule de données en flottant, le vide devenant ``NaN``.

    Aucun séparateur de milliers n'est retiré avant la conversion. Un texte
    « 1,234.56 » échoue donc bruyamment, ce qui vaut mieux que de le lire 1,23
    ou 123 456 selon la convention supposée. Les cinq classeurs mesurés
    n'écrivent aucune cellule de données en texte.

    Raises:
        DataQualityError: si la cellule porte un texte qui n'est pas un nombre.
    """
    if value is None:
        return float("nan")
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    texte = str(value).strip()
    if not texte:
        return float("nan")
    try:
        return float(texte)
    except ValueError as exc:
        raise DataQualityError(f"cellule de données non numérique : « {texte[:40]} »") from exc


def percent_scale_suspected(frame: pd.DataFrame, *, threshold: float = RETURN_ABS_MAX_DECIMAL) -> bool:
    """Dit si les valeurs d'une feuille de rendement semblent être en pourcentage.

    **Pourquoi ce contrôle.** Les cellules d'AQR portent un format d'affichage
    en pourcentage, « 0.00% » pour BAB, alors que la valeur stockée est une
    décimale. La confusion coûte un facteur cent, et elle ne lève aucune
    exception. Si un millésime futur passait vraiment au pourcentage, un
    rendement mensuel de 5 % s'écrirait 5,0 au lieu de 0,05, et le maximum
    absolu de la feuille dépasserait le seuil.

    Args:
        frame: un tableau de rendements.
        threshold: le seuil au-dessus duquel le soupçon se lève. Sa valeur par
            défaut est mesurée, voir :data:`RETURN_ABS_MAX_DECIMAL`.

    Returns:
        Vrai si la plus grande valeur absolue dépasse le seuil.

    Note:
        Le contrôle ne s'applique pas à une feuille de niveaux, ainsi
        « ME(t-1) », dont les capitalisations montent à 1,2e8 millions de
        dollars. La fiche de chaque feuille porte son genre.
    """
    valeurs = np.abs(frame.to_numpy(dtype=float))
    if valeurs.size == 0 or not bool(np.isfinite(valeurs).any()):
        return False
    return float(np.nanmax(valeurs)) > float(threshold)


# --------------------------------------------------------------------------- #
# Le registre des cinq jeux, mesuré
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AqrSheetSpec:
    """La fiche d'une feuille de données d'un classeur.

    Attributes:
        name: le nom de l'onglet.
        header_row: le rang de la ligne d'en-tête, compté à partir de un, tel
            qu'il est mesuré le 2026-09-02. Le lecteur ne s'en sert pas, il le
            détecte ; le champ sert de contrôle et de documentation.
        kind: « returns » pour une feuille de rendements en décimales, « level »
            pour une feuille de niveaux.
        unit: l'unité des valeurs, en clair.
        n_rows: le nombre de lignes datées mesuré le 2026-09-02.
        description: ce que la feuille contient, en une phrase.
    """

    name: str
    header_row: int
    kind: str
    unit: str
    n_rows: int
    description: str


@dataclass(frozen=True, slots=True)
class AqrDatasetSpec:
    """La fiche d'un classeur d'AQR.

    Attributes:
        key: la clé courte du jeu, celle que l'appelant emploie.
        filename: le nom du fichier sur le site.
        file_bytes: la taille du fichier mesurée le 2026-09-02.
        factor_sheet: la feuille qui porte la série de référence de l'étude.
        sheet_names: TOUS les onglets du classeur, dans l'ordre du document,
            mesurés en ouvrant le fichier.
        data_sheets: les fiches des onglets qui portent un tableau daté.
        columns: les colonnes de la feuille de référence, mesurées.
        first_period: la première date de la feuille de référence.
        last_period: la dernière date de la feuille de référence.
        citation: la référence de l'article que le jeu accompagne.
        description: ce que le jeu contient, en une phrase.
    """

    key: str
    filename: str
    file_bytes: int
    factor_sheet: str
    sheet_names: tuple[str, ...]
    data_sheets: tuple[AqrSheetSpec, ...]
    columns: tuple[str, ...]
    first_period: dt.date
    last_period: dt.date
    citation: str
    description: str

    @property
    def copyright_notice(self) -> str:
        """Rend la mention de droit d'auteur recopiée du classeur."""
        return COPYRIGHT_BY_DATASET.get(self.key, "")

    def sheet(self, name: str) -> AqrSheetSpec:
        """Rend la fiche d'une feuille de données par son nom.

        Raises:
            KeyError: si aucune feuille de données ne porte ce nom.
        """
        cible = name.strip().casefold()
        for fiche in self.data_sheets:
            if fiche.name.strip().casefold() == cible:
                return fiche
        connues = ", ".join(fiche.name for fiche in self.data_sheets)
        raise KeyError(f"feuille de données « {name} » absente de « {self.key} » ; connues : {connues}")


#: Les 24 marchés et les 5 agrégats de la feuille de facteurs des trois
#: classeurs d'actions, mesurés le 2026-09-02. Les 24 sont les États-Unis et
#: les 23 marchés internationaux que la ligne 8 du classeur annonce ; les 5
#: agrégats sont Global, Global Ex USA, Europe, North America et Pacific.
_EQUITY_COLUMNS: Final[tuple[str, ...]] = (
    "AUS",
    "AUT",
    "BEL",
    "CAN",
    "CHE",
    "DEU",
    "DNK",
    "ESP",
    "FIN",
    "FRA",
    "GBR",
    "GRC",
    "HKG",
    "IRL",
    "ISR",
    "ITA",
    "JPN",
    "NLD",
    "NOR",
    "NZL",
    "PRT",
    "SGP",
    "SWE",
    "USA",
    "Global",
    "Global Ex USA",
    "Europe",
    "North America",
    "Pacific",
)

#: Les onglets communs aux trois classeurs d'actions, dans l'ordre du document.
_EQUITY_SHEET_NAMES: Final[tuple[str, ...]] = (
    "Definition",
    "Data Sources",
    "--> Additional Global Factors",
    "MKT",
    "SMB",
    "HML FF",
    "HML Devil",
    "UMD",
    "ME(t-1)",
    "RF",
    "Sources and Definitions",
    "Disclosures",
)


def _auxiliary_sheets(*, avec_hml_devil: bool) -> tuple[AqrSheetSpec, ...]:
    """Rend les fiches des feuilles annexes communes aux classeurs d'actions.

    Args:
        avec_hml_devil: garde la feuille « HML Devil », que le classeur du même
            nom porte comme feuille PRINCIPALE et non comme annexe.
    """
    fiches = [
        AqrSheetSpec(
            "MKT", 19, "returns", "décimales", 1200, "Le rendement de marché en excès du taux sans risque."
        ),
        AqrSheetSpec("SMB", 19, "returns", "décimales", 1200, "Le facteur de taille, petites moins grandes."),
        AqrSheetSpec(
            "HML FF", 19, "returns", "décimales", 1200, "Le facteur de valeur au sens de Fama et French."
        ),
        AqrSheetSpec(
            "HML Devil", 19, "returns", "décimales", 1200, "Le facteur de valeur au ratio actualisé."
        ),
        AqrSheetSpec(
            "UMD", 19, "returns", "décimales", 1194, "Le facteur de momentum, gagnantes moins perdantes."
        ),
        AqrSheetSpec(
            "ME(t-1)",
            19,
            "level",
            "millions de dollars américains",
            1201,
            "La capitalisation du marché au mois précédent.",
        ),
        AqrSheetSpec(
            "RF",
            19,
            "returns",
            "décimales",
            1201,
            "Le taux sans risque mensuel des bons du Trésor américain.",
        ),
    ]
    return tuple(f for f in fiches if avec_hml_devil or f.name != "HML Devil")


_DATASETS: Final[Mapping[str, AqrDatasetSpec]] = MappingProxyType(
    {
        spec.key: spec
        for spec in (
            AqrDatasetSpec(
                key="bab",
                filename="Betting-Against-Beta-Equity-Factors-Monthly.xlsx",
                file_bytes=2_500_092,
                factor_sheet="BAB Factors",
                sheet_names=("BAB Factors", *_EQUITY_SHEET_NAMES),
                data_sheets=(
                    AqrSheetSpec(
                        "BAB Factors",
                        19,
                        "returns",
                        "décimales",
                        1147,
                        "Les facteurs pari contre le bêta, par marché et par agrégat.",
                    ),
                    *_auxiliary_sheets(avec_hml_devil=True),
                ),
                columns=_EQUITY_COLUMNS,
                first_period=dt.date(1930, 12, 31),
                last_period=dt.date(2026, 6, 30),
                citation=(
                    "Frazzini, A. et Pedersen, L. H. (2014), « Betting Against Beta », "
                    "Journal of Financial Economics 111(1), 1-25"
                ),
                description="Les facteurs BAB, longs sur bêta faible et courts sur bêta élevé.",
            ),
            AqrDatasetSpec(
                key="qmj",
                filename="Quality-Minus-Junk-Factors-Monthly.xlsx",
                file_bytes=2_260_674,
                factor_sheet="QMJ Factors",
                sheet_names=("QMJ Factors", *_EQUITY_SHEET_NAMES),
                data_sheets=(
                    AqrSheetSpec(
                        "QMJ Factors",
                        19,
                        "returns",
                        "décimales",
                        828,
                        "Les facteurs qualité moins pacotille, par marché et par agrégat.",
                    ),
                    *_auxiliary_sheets(avec_hml_devil=True),
                ),
                columns=_EQUITY_COLUMNS,
                first_period=dt.date(1957, 7, 31),
                last_period=dt.date(2026, 6, 30),
                citation=(
                    "Asness, C. S., Frazzini, A. et Pedersen, L. H. (2019), « Quality Minus Junk », "
                    "Review of Accounting Studies 24(1), 34-112"
                ),
                description="Les facteurs QMJ, longs sur les sociétés de qualité et courts sur les autres.",
            ),
            AqrDatasetSpec(
                key="hml_devil",
                filename="The-Devil-in-HMLs-Details-Factors-Monthly.xlsx",
                file_bytes=1_943_770,
                factor_sheet="HML Devil",
                sheet_names=("HML Devil", *(n for n in _EQUITY_SHEET_NAMES if n != "HML Devil")),
                data_sheets=(
                    AqrSheetSpec(
                        "HML Devil",
                        19,
                        "returns",
                        "décimales",
                        1200,
                        "Les facteurs de valeur au ratio actualisé, par marché et par agrégat.",
                    ),
                    *_auxiliary_sheets(avec_hml_devil=False),
                ),
                columns=_EQUITY_COLUMNS,
                first_period=dt.date(1926, 7, 31),
                last_period=dt.date(2026, 6, 30),
                citation=(
                    "Asness, C. et Frazzini, A. (2013), « The Devil in HML's Details », "
                    "Journal of Portfolio Management 39(4), 49-68"
                ),
                description="Le facteur de valeur bâti sur une capitalisation du mois courant.",
            ),
            AqrDatasetSpec(
                key="vme",
                filename="Value-and-Momentum-Everywhere-Factors-Monthly.xlsx",
                file_bytes=255_052,
                factor_sheet="VME Factors",
                sheet_names=("VME Factors", "Definitions", "Data Sources", "Disclosures"),
                data_sheets=(
                    AqrSheetSpec(
                        "VME Factors",
                        22,
                        "returns",
                        "décimales",
                        654,
                        "La valeur et le momentum dans huit classes d'actifs et trois moyennes.",
                    ),
                ),
                columns=(
                    "VAL",
                    "MOM",
                    "VAL^SS",
                    "MOM^SS",
                    "VAL^AA",
                    "MOM^AA",
                    "VALLS_VME_US90",
                    "MOMLS_VME_US90",
                    "VALLS_VME_UK90",
                    "MOMLS_VME_UK90",
                    "VALLS_VME_ROE90",
                    "MOMLS_VME_ROE90",
                    "VALLS_VME_JP90",
                    "MOMLS_VME_JP90",
                    "VALLS_VME_EQ",
                    "MOMLS_VME_EQ",
                    "VALLS_VME_FX",
                    "MOMLS_VME_FX",
                    "VALLS_VME_FI",
                    "MOMLS_VME_FI",
                    "VALLS_VME_COM",
                    "MOMLS_VME_COM",
                ),
                first_period=dt.date(1972, 1, 31),
                last_period=dt.date(2026, 6, 30),
                citation=(
                    "Asness, C. S., Moskowitz, T. J. et Pedersen, L. H. (2013), "
                    "« Value and Momentum Everywhere », Journal of Finance 68(3), 929-985"
                ),
                description="La valeur et le momentum, quatre marchés d'actions et quatre classes d'actifs.",
            ),
            AqrDatasetSpec(
                key="tsmom",
                filename="Time-Series-Momentum-Factors-Monthly.xlsx",
                file_bytes=139_830,
                factor_sheet="TSMOM Factors",
                sheet_names=("TSMOM Factors", "Definitions", "Data Sources", "Disclosures"),
                data_sheets=(
                    AqrSheetSpec(
                        "TSMOM Factors",
                        18,
                        "returns",
                        "décimales",
                        497,
                        "Le momentum temporel, toutes classes puis quatre classes d'actifs.",
                    ),
                ),
                columns=("TSMOM", "TSMOM^CM", "TSMOM^EQ", "TSMOM^FI", "TSMOM^FX"),
                first_period=dt.date(1985, 1, 31),
                last_period=dt.date(2026, 5, 29),
                citation=(
                    "Moskowitz, T. J., Ooi, Y. H. et Pedersen, L. H. (2012), « Time Series Momentum », "
                    "Journal of Financial Economics 104(2), 228-250"
                ),
                description="Le momentum temporel sur douze mois, détention d'un mois.",
            ),
        )
    }
)


def available_datasets() -> Mapping[str, AqrDatasetSpec]:
    """Rend les cinq classeurs connus, avec leurs onglets réellement présents.

    Returns:
        Un dictionnaire en lecture seule, de la clé courte vers sa fiche.

    Note:
        Les cinq noms de fichier répondent 200 sur :data:`BASE_URL`, et leurs
        tailles sont celles de :attr:`AqrDatasetSpec.file_bytes`, mesurées le
        2026-09-02. Les noms d'onglets sont ceux que l'ouverture des cinq
        fichiers rend, et non ceux que la page du site annonce.

        Deux points comptent pour l'usage. Les trois classeurs d'actions
        portent les mêmes onglets annexes, MKT, SMB, HML FF, UMD, ME(t-1) et
        RF, si bien que l'un d'eux suffit pour les récupérer. TSMOM s'arrête un
        mois plus tôt que les quatre autres, en mai 2026 contre juin 2026.
    """
    return _DATASETS


def resolve_dataset(name: str) -> AqrDatasetSpec:
    """Rend la fiche d'un jeu, désigné par sa clé courte ou par son nom de fichier.

    Args:
        name: la clé courte, ainsi « tsmom », ou le nom du fichier, avec ou sans
            le suffixe « .xlsx ».

    Returns:
        La fiche du jeu.

    Raises:
        ConfigError: si le nom est vide, ou ne désigne aucun des cinq jeux.

    Example:
        >>> resolve_dataset("Time-Series-Momentum-Factors-Monthly.xlsx").key
        'tsmom'
    """
    if not name or not name.strip():
        raise ConfigError("le nom du jeu de données est vide")
    cible = name.strip().casefold()
    for spec in _DATASETS.values():
        if cible in {
            spec.key.casefold(),
            spec.filename.casefold(),
            spec.filename.casefold()[: -len(".xlsx")],
        }:
            return spec
    raise ConfigError(f"jeu « {name} » inconnu ; choisir parmi {sorted(_DATASETS)}")


# --------------------------------------------------------------------------- #
# Le fournisseur
# --------------------------------------------------------------------------- #


class AqrProvider(BaseProvider):
    """Le fournisseur des jeux de facteurs d'AQR.

    Il hérite du socle commun, donc du client HTTP poli, du cache brut horodaté
    et de l'empreinte SHA-256 vérifiée à la relecture. Il n'ajoute que ce qui
    est propre à cette source : l'adresse des classeurs, la lecture du format
    XLSX et la détection de la ligne d'en-tête.

    **La règle d'usage.** Ces séries sont une cible de réplication, jamais un
    signal. Voir la documentation du module, qui l'explique en trois phrases.

    Args:
        client: le client HTTP. Sans valeur, il est créé au premier besoin.
        raw_root: la racine du cache brut. Sans valeur, ``data/raw/aqr/``. Les
            tests y passent un ``tmp_path``.
        now: fournisseur de l'horodatage, injectable.
        base_url: la racine des classeurs.

    Example:
        >>> AqrProvider().dataset_url("tsmom").endswith("Monthly.xlsx")
        True
    """

    #: Nom court du fournisseur, qui nomme aussi son dossier de cache brut.
    name: ClassVar[str] = "aqr"

    def __init__(
        self,
        *,
        client: HttpClient | None = None,
        raw_root: Path | str | None = None,
        now: Callable[[], dt.datetime] | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        horloge = {"now": now} if now is not None else {}
        super().__init__(client=client, raw_root=raw_root, **horloge)
        self.base_url = base_url

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #
    def dataset_url(self, dataset: str = DEFAULT_DATASET) -> str:
        """Rend l'adresse du classeur d'un jeu.

        Args:
            dataset: la clé courte du jeu, ou son nom de fichier.

        Returns:
            L'adresse complète du classeur.

        Raises:
            ConfigError: si le nom ne désigne aucun des cinq jeux.
        """
        return f"{self.base_url}{resolve_dataset(dataset).filename}"

    @staticmethod
    def available_datasets() -> Mapping[str, AqrDatasetSpec]:
        """Rend les jeux connus du module. Voir :func:`available_datasets`."""
        return available_datasets()

    # ------------------------------------------------------------------ #
    # Téléchargement
    # ------------------------------------------------------------------ #
    def raw_workbook(self, dataset: str = DEFAULT_DATASET, *, refresh: bool = False) -> RawResponse:
        """Rend la réponse brute portant le classeur, du cache ou du réseau.

        Le cache est la couche ``raw`` du lac, et il est immuable : un nouveau
        téléchargement crée un fichier horodaté de plus. AQR reconstruit toute
        son histoire à chaque mise à jour, si bien que garder l'octet reçu est
        la seule façon de rejouer une étude sur le millésime qui l'a produite.

        Args:
            dataset: la clé courte du jeu, ou son nom de fichier.
            refresh: force un nouveau téléchargement.

        Returns:
            La réponse brute, avec son empreinte et son horodatage.
        """
        spec = resolve_dataset(dataset)
        return self.fetch_cached(self.dataset_url(spec.key), label=spec.key, refresh=refresh)

    def workbook(self, dataset: str = DEFAULT_DATASET, *, refresh: bool = False) -> Workbook:
        """Rend le classeur lu d'un jeu.

        Args:
            dataset: la clé courte du jeu, ou son nom de fichier.
            refresh: force un nouveau téléchargement.

        Returns:
            Le classeur, feuilles dans l'ordre du document.

        Raises:
            DataQualityError: si la réponse n'est pas un classeur XLSX.
        """
        return read_workbook(self.raw_workbook(dataset, refresh=refresh).content)

    def sheet_names(self, dataset: str = DEFAULT_DATASET, *, refresh: bool = False) -> tuple[str, ...]:
        """Rend les noms d'onglets réellement présents dans un classeur.

        Args:
            dataset: la clé courte du jeu, ou son nom de fichier.
            refresh: force un nouveau téléchargement.

        Returns:
            Les noms, dans l'ordre du document.
        """
        return self.workbook(dataset, refresh=refresh).names

    # ------------------------------------------------------------------ #
    # Lecture
    # ------------------------------------------------------------------ #
    def fetch(
        self,
        dataset: str = DEFAULT_DATASET,
        sheet: str | None = None,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Rend une feuille datée d'un classeur, bornée à la période demandée.

        Args:
            dataset: la clé courte du jeu, ou son nom de fichier.
            sheet: l'onglet lu. Sans valeur, la feuille de référence de l'étude,
                donnée par :attr:`AqrDatasetSpec.factor_sheet`.
            start: première date gardée.
            end: dernière date gardée.
            refresh: force un nouveau téléchargement.

        Returns:
            Un tableau indexé par un ``DatetimeIndex`` nommé « date », valeurs
            telles qu'elles sont stockées, sans remise à l'échelle.

        Raises:
            KeyError: si l'onglet demandé n'existe pas dans le classeur.
            InsufficientDataError: si l'onglet ne porte aucun tableau daté, ce
                qui est le cas des onglets de définitions et de sources.

        Note:
            Une feuille de rendements dont le maximum absolu dépasse
            :data:`RETURN_ABS_MAX_DECIMAL` laisse un avertissement dans le
            journal de la session. Le contrôle attraperait un passage de la
            source au pourcentage, qui multiplierait toutes les valeurs par cent
            sans lever d'exception.
        """
        spec = resolve_dataset(dataset)
        nom_feuille = sheet or spec.factor_sheet
        frame = sheet_to_frame(self.workbook(spec.key, refresh=refresh)[nom_feuille].rows)
        self._check_scale(spec, nom_feuille, frame)
        return slice_period(frame, start, end)

    def _check_scale(self, spec: AqrDatasetSpec, sheet: str, frame: pd.DataFrame) -> None:
        """Signale une feuille de rendements dont l'échelle a changé."""
        try:
            fiche = spec.sheet(sheet)
        except KeyError:
            return
        if fiche.kind != "returns":
            return
        if percent_scale_suspected(frame):
            self._log.warning(
                "échelle inattendue sur une feuille de rendements",
                extra={"dataset": spec.key, "sheet": sheet, "threshold": RETURN_ABS_MAX_DECIMAL},
            )

    def tsmom_factors(
        self,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Rend le momentum temporel de Moskowitz, Ooi et Pedersen, par classe d'actif.

        Les cinq colonnes sont le facteur toutes classes confondues, puis les
        matières premières, les indices d'actions, les taux et les devises. La
        série commence en janvier 1985 et sa dernière date est un jour OUVRÉ de
        fin de mois, non un dernier jour calendaire.

        Args:
            start: première date gardée.
            end: dernière date gardée.
            refresh: force un nouveau téléchargement.

        Returns:
            Un tableau à cinq colonnes, en décimales.
        """
        return self.fetch("tsmom", None, start, end, refresh=refresh)

    def bab_factors(
        self,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Rend le pari contre le bêta de Frazzini et Pedersen, par pays.

        Les colonnes sont 24 marchés d'actions désignés par leur code ISO à
        trois lettres, puis cinq agrégats. La série commence en décembre 1930,
        mais la colonne « USA » est la seule renseignée avant 1984.

        Args:
            start: première date gardée.
            end: dernière date gardée.
            refresh: force un nouveau téléchargement.

        Returns:
            Un tableau à 29 colonnes, en décimales.
        """
        return self.fetch("bab", None, start, end, refresh=refresh)

    def qmj_factors(
        self,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Rend la qualité moins la pacotille d'Asness, Frazzini et Pedersen, par pays.

        Args:
            start: première date gardée.
            end: dernière date gardée.
            refresh: force un nouveau téléchargement.

        Returns:
            Un tableau à 29 colonnes, en décimales, à partir de juillet 1957.
        """
        return self.fetch("qmj", None, start, end, refresh=refresh)

    def vme_factors(
        self,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Rend la valeur et le momentum d'Asness, Moskowitz et Pedersen, par classe.

        Les colonnes vont par paires, valeur puis momentum, d'abord trois
        moyennes globales, puis quatre marchés d'actions et quatre classes
        d'actifs.

        Args:
            start: première date gardée.
            end: dernière date gardée.
            refresh: force un nouveau téléchargement.

        Returns:
            Un tableau à 22 colonnes, en décimales, à partir de janvier 1972.
        """
        return self.fetch("vme", None, start, end, refresh=refresh)

    def hml_devil_factors(
        self,
        start: dt.date | str | None = None,
        end: dt.date | str | None = None,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Rend le facteur de valeur d'Asness et Frazzini, par pays.

        Il diffère du HML de Fama et French par la capitalisation employée au
        dénominateur, celle du mois courant plutôt que celle de la date du
        bilan. Le classeur publie les deux, ce qui permet de mesurer l'écart
        directement, la feuille « HML FF » portant l'autre convention.

        Args:
            start: première date gardée.
            end: dernière date gardée.
            refresh: force un nouveau téléchargement.

        Returns:
            Un tableau à 29 colonnes, en décimales, à partir de juillet 1926.
        """
        return self.fetch("hml_devil", None, start, end, refresh=refresh)

    # ------------------------------------------------------------------ #
    # Provenance
    # ------------------------------------------------------------------ #
    def manifest(
        self,
        dataset: str = DEFAULT_DATASET,
        *,
        sheet: str | None = None,
        frame: pd.DataFrame | None = None,
        refresh: bool = False,
        **_: Any,
    ) -> DatasetManifest:
        """Décrit un jeu : origine, licence, révisions, point-in-time.

        Trois déclarations décident de ce qu'on a le droit de conclure.

        ``point_in_time=False``
            Deux raisons distinctes, et chacune suffit. La première est la
            révision : AQR reconstruit toute l'histoire à chaque mise à jour, et
            l'écrit en clair dans ses classeurs. Le rendement de juillet 1926 lu
            aujourd'hui n'est pas celui qu'on aurait lu il y a cinq ans. La
            seconde est le retard de publication, qui vaut 57 jours pour quatre
            des cinq classeurs au 2026-09-02, mesuré sur l'en-tête HTTP
            ``Last-Modified``. L'index est une fin de période, et la date de
            disponibilité n'est écrite nulle part dans ces fichiers. Voir
            :data:`PUBLICATION_LAG`.

        ``survivorship_free=None``
            AQR ne publie pas la règle d'entrée et de sortie de son univers, et
            ses onglets de sources nomment des bases commerciales sans décrire
            le traitement des radiations. Le point est cherché et non trouvé,
            donc le champ reste indéterminé plutôt que flatteur.

        ``license``
            Les conditions d'utilisation interdisent la redistribution sans
            accord écrit. Le cache brut ne se commite pas, et aucune de ces
            séries ne se republie.

        Args:
            dataset: la clé courte du jeu, ou son nom de fichier.
            sheet: l'onglet décrit, la feuille de référence par défaut.
            frame: un tableau déjà chargé, pour éviter de le relire.
            refresh: force un nouveau téléchargement.

        Returns:
            Le manifeste du jeu, empreinte et couverture comprises.

        Raises:
            InsufficientDataError: si le tableau décrit est vide, sa couverture
                étant alors indéterminée.

        Note:
            L'empreinte est celle du CLASSEUR téléchargé, pas de la feuille
            lue. C'est elle qui identifie le millésime, et deux lectures
            différentes du même fichier doivent porter la même empreinte.
        """
        spec = resolve_dataset(dataset)
        nom_feuille = sheet or spec.factor_sheet
        raw = self.raw_workbook(spec.key, refresh=refresh)
        decrit = frame if frame is not None else self.fetch(spec.key, nom_feuille)
        if len(decrit) == 0:
            raise InsufficientDataError(
                f"le tableau décrit de « {spec.key} », feuille « {nom_feuille} », est vide"
            )
        colonnes = tuple(str(colonne) for colonne in decrit.columns)
        notes = f"{spec.description} {spec.citation}. {spec.copyright_notice}. {PUBLICATION_LAG}."
        return DatasetManifest(
            dataset_id=f"aqr-{spec.key}-{nom_feuille.strip().replace(' ', '-').lower()}",
            source=SOURCE_NAME,
            provider=self.name,
            url=self.dataset_url(spec.key),
            download_timestamp=raw.fetched_at,
            data_start=decrit.index[0].date(),
            data_end=decrit.index[-1].date(),
            frequency=Frequency.MONTHLY,
            timezone=TIMEZONE,
            exchange=None,
            currency=CURRENCY,
            adjusted=True,
            point_in_time=False,
            survivorship_free=None,
            corporate_actions=CORPORATE_ACTIONS,
            revision_policy=REVISION_POLICY,
            license=LICENSE,
            license_url=LICENSE_URL,
            checksum_sha256=raw.sha256,
            n_rows=len(decrit),
            n_columns=len(colonnes),
            columns=colonnes,
            processing_version=PROCESSING_VERSION,
            layer=Layer.BRONZE,
            notes=notes,
        )
