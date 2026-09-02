"""Tests du lecteur des jeux de facteurs d'AQR.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chacune
annonce sa source dans le commentaire du test. Les sources sont au nombre de
quatre.

(a) un calcul à la main, chiffres visibles dans le commentaire ;
(b) une identité mathématique ou une propriété structurelle ;
(c) une valeur lue dans les fichiers réels d'AQR, téléchargés le 2026-09-02, ou
    dans la norme ECMA-376 qui décrit le format XLSX ;
(d) une implémentation indépendante, ici ``openpyxl`` lorsqu'il est installé.

**Comment la mise en page est reproduite hors réseau.** Le format XLSX est une
archive ZIP de documents XML, et :func:`_ecrire_xlsx` en fabrique un depuis la
bibliothèque standard. Le classeur produit porte les mêmes traits que ceux
d'AQR. En tête, de la prose libre, une ou deux lignes de titres de groupe, puis
la ligne d'en-tête. Dans les données, des dates tantôt en texte et tantôt en
numéro de série, et un format d'affichage en pourcentage sur des valeurs
décimales. Sur les bords, des colonnes sans nom et des lignes vides en queue.

**Pourquoi un écrivain maison plutôt que ``pandas.ExcelWriter``.** Le projet ne
déclare aucun moteur Excel dans ``pyproject.toml``, vérifié le 2026-09-02, si
bien qu'un ``ExcelWriter`` lèverait ``ImportError`` sur une installation propre.
Le test :func:`test_le_lecteur_maison_dit_la_meme_chose_que_pandas` ferme la
boucle quand ``openpyxl`` se trouve installé : il relit le même classeur par
``pandas.read_excel`` et compare cellule à cellule.
"""

from __future__ import annotations

import datetime as dt
import io
import zipfile
from collections.abc import Mapping, Sequence
from email.utils import parsedate_to_datetime
from xml.sax.saxutils import escape, quoteattr

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from quantlab.core.config import Settings
from quantlab.core.errors import ConfigError, DataQualityError, InsufficientDataError
from quantlab.core.protocols import DataProvider
from quantlab.core.types import Frequency
from quantlab.data.providers.aqr import (
    BASE_URL,
    PUBLICATION_LAG,
    RETURN_ABS_MAX_DECIMAL,
    AqrProvider,
    available_datasets,
    detect_header_row,
    excel_serial_to_datetime,
    parse_date_cell,
    percent_scale_suspected,
    read_workbook,
    resolve_dataset,
    sheet_to_frame,
)
from quantlab.data.providers.base import HttpClient, RawResponse, cache_key

# --------------------------------------------------------------------------- #
# Un écrivain XLSX minimal, sur la bibliothèque standard
# --------------------------------------------------------------------------- #

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

#: Indices des styles écrits par :func:`_styles_xml`, dans l'ordre de
#: ``cellXfs``. Source (c) : les identifiants 0, 14 et 10 sont les formats
#: natifs « General », « mm-dd-yy » et « 0.00% » de la norme ECMA-376. Le
#: quatrième est un format personnalisé de date, identifiant 164.
STYLE_GENERAL = 0
STYLE_DATE_NATIVE = 1
STYLE_POURCENT = 2
STYLE_DATE_PERSONNALISE = 3

#: Source (a) : le 30 décembre 1899 est l'origine du calendrier de 1900 une fois
#: absorbé le jour fantôme du 29 février 1900. Le calcul du numéro de série est
#: écrit ici à la main, sans appeler le module sous test.
_ORIGINE_1900 = dt.datetime(1899, 12, 30)


def _serial(moment: dt.datetime | dt.date) -> float:
    """Rend le numéro de série Excel d'une date, calculé à la main.

    Le calcul ne passe pas par le module sous test : c'est une soustraction de
    dates, valable pour toute date au-delà du 1er mars 1900.
    """
    if not isinstance(moment, dt.datetime):
        moment = dt.datetime(moment.year, moment.month, moment.day)
    return (moment - _ORIGINE_1900).total_seconds() / 86400.0


def _styles_xml() -> str:
    """Rend un ``styles.xml`` portant quatre styles, dont deux de date."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{_MAIN}">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd"/></numFmts>'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="4">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="10" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _lettre_colonne(index: int) -> str:
    """Rend la lettre de colonne d'un indice compté à zéro, « A » pour 0."""
    lettres = ""
    reste = index + 1
    while reste:
        reste, rang = divmod(reste - 1, 26)
        lettres = chr(ord("A") + rang) + lettres
    return lettres


def _cellule_xml(
    reference: str,
    valeur: object,
    *,
    chaines: list[str],
    style_date: int,
    style_nombre: int,
) -> str:
    """Rend le XML d'une cellule, chaînes partagées alimentées au passage."""
    if valeur is None:
        return ""
    if isinstance(valeur, dt.datetime | dt.date):
        return f'<c r="{reference}" s="{style_date}"><v>{_serial(valeur):.10f}</v></c>'
    if isinstance(valeur, bool):
        return f'<c r="{reference}" t="b"><v>{int(valeur)}</v></c>'
    if isinstance(valeur, int | float):
        return f'<c r="{reference}" s="{style_nombre}"><v>{valeur!r}</v></c>'
    texte = str(valeur)
    if texte not in chaines:
        chaines.append(texte)
    return f'<c r="{reference}" t="s"><v>{chaines.index(texte)}</v></c>'


def _ecrire_xlsx(
    feuilles: Mapping[str, Sequence[Sequence[object]]],
    *,
    style_date: int = STYLE_DATE_NATIVE,
    style_nombre: int = STYLE_POURCENT,
) -> bytes:
    """Fabrique un classeur XLSX depuis la bibliothèque standard.

    Args:
        feuilles: le contenu, du nom d'onglet vers sa grille. Une valeur
            ``None`` laisse la cellule absente, comme le font les vrais
            fichiers.
        style_date: le style appliqué aux cellules de type date, natif par
            défaut, personnalisé sur demande.
        style_nombre: le style appliqué aux cellules numériques, un format
            d'affichage en pourcentage par défaut, comme chez AQR.

    Returns:
        Les octets du classeur.
    """
    chaines: list[str] = []
    parties_feuilles: list[tuple[str, str]] = []
    for rang, grille in enumerate(feuilles.values(), start=1):
        lignes: list[str] = []
        for numero, ligne in enumerate(grille, start=1):
            cellules = "".join(
                _cellule_xml(
                    f"{_lettre_colonne(colonne)}{numero}",
                    valeur,
                    chaines=chaines,
                    style_date=style_date,
                    style_nombre=style_nombre,
                )
                for colonne, valeur in enumerate(ligne)
            )
            if cellules:
                lignes.append(f'<row r="{numero}">{cellules}</row>')
        contenu = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<worksheet xmlns="{_MAIN}"><sheetData>{"".join(lignes)}</sheetData></worksheet>'
        )
        parties_feuilles.append((f"xl/worksheets/sheet{rang}.xml", contenu))

    declarations = "".join(
        f'<sheet name={quoteattr(nom)} sheetId="{rang}" r:id="rId{rang}"/>'
        for rang, nom in enumerate(feuilles, start=1)
    )
    classeur = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{_MAIN}" xmlns:r="{_DOC_REL}"><sheets>{declarations}</sheets></workbook>'
    )
    n = len(feuilles)
    relations = "".join(
        f'<Relationship Id="rId{rang}" Type="{_DOC_REL}/worksheet" Target="worksheets/sheet{rang}.xml"/>'
        for rang in range(1, n + 1)
    )
    relations += (
        f'<Relationship Id="rId{n + 1}" Type="{_DOC_REL}/styles" Target="styles.xml"/>'
        f'<Relationship Id="rId{n + 2}" Type="{_DOC_REL}/sharedStrings" Target="sharedStrings.xml"/>'
    )
    partages = "".join(f'<si><t xml:space="preserve">{escape(t)}</t></si>' for t in chaines)
    types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{rang}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for rang in range(1, n + 1)
        )
        + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>"
    )
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr(
            "_rels/.rels",
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{_PKG_REL}">'
            f'<Relationship Id="rId1" Type="{_DOC_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        )
        archive.writestr("xl/workbook.xml", classeur)
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_PKG_REL}">{relations}</Relationships>',
        )
        archive.writestr("xl/styles.xml", _styles_xml())
        archive.writestr(
            "xl/sharedStrings.xml",
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<sst xmlns="{_MAIN}" count="{len(chaines)}" uniqueCount="{len(chaines)}">{partages}</sst>',
        )
        for chemin, contenu in parties_feuilles:
            archive.writestr(chemin, contenu)
    return tampon.getvalue()


# --------------------------------------------------------------------------- #
# Trois mises en page, recopiées de la structure des fichiers réels
# --------------------------------------------------------------------------- #
# Source (c) : les lignes de prose, le rang des lignes de groupe et le rang de
# l'en-tête sont ceux mesurés le 2026-09-02 dans les classeurs d'AQR. Les
# valeurs numériques, elles, sont inventées : elles doivent seulement rester
# des décimales, comme celles du fichier.
# --------------------------------------------------------------------------- #

_PROSE_BAB = [
    ["AQR Capital Management, LLC, Betting Against Beta: Equity Factors, Monthly"],
    [None],
    ["This file contains monthly self-financing excess returns of long/short equity BAB factors."],
    ["The portfolios are an updated and extended version of the equity portfolios used in the paper."],
    ["The portfolio construction is based on Frazzini and Pedersen (2014)."],
    [None],
    ["BAB factors are portfolios that are long low-beta securities and short high-beta securities."],
    ["Here we construct BAB factors for U.S. equities and 23 international equity markets."],
    ["Not all available data may be displayed below based on the user's selection."],
    [None],
    ["Data are updated and maintained by AQR, www.aqr.com."],
    ["Data are updated as they become available. AQR reconstructs the full history."],
    ["Copyright 2014 Andrea Frazzini and Lasse Heje Pedersen"],
    [None],
    ["Please see disclosures on the Disclosures tab."],
    [None],
    [None],
]


def _mise_en_page_bab() -> list[list[object]]:
    """Rend une feuille au format de « BAB Factors » : en-tête à la ligne 19.

    Dix-sept lignes de prose, une ligne de groupe, l'en-tête, puis quatre lignes
    de données datées en TEXTE, puis trois lignes vides.
    """
    lignes: list[list[object]] = [list(ligne) for ligne in _PROSE_BAB]
    lignes.append([None, "EQUITIES", None, None, None])
    lignes.append(["DATE", "AUS", "CAN", "USA", None])
    lignes.append(["12/31/1930", None, None, 0.0135, None])
    lignes.append(["01/31/1931", 0.0200, -0.0100, 0.0300, None])
    lignes.append(["02/28/1931", -0.0050, None, 0.0100, None])
    lignes.append(["03/31/1931", 0.0075, 0.0025, -0.0225, None])
    lignes.extend([[None] * 5 for _ in range(3)])
    return lignes


def _mise_en_page_tsmom() -> list[list[object]]:
    """Rend une feuille au format de « TSMOM Factors » : en-tête à la ligne 18.

    La cellule d'en-tête de la colonne des dates est VIDE, et les dates sont des
    numéros de série mis en forme en date.
    """
    lignes: list[list[object]] = [[None] for _ in range(17)]
    lignes[0] = ["AQR Capital Management, LLC, Time Series Momentum: Factors, Monthly"]
    lignes[2] = ["This file contains the excess returns of the long/short TSMOM factors."]
    lignes[12] = ["Copyright 2012 Tobias Moskowitz, Yao Hua Ooi, and Lasse Heje Pedersen"]
    lignes.append([None, "TSMOM", "TSMOM^CM", "TSMOM^EQ"])
    lignes.append(
        [dt.datetime(1985, 1, 31), 0.043456226781221075, -0.013041584236260083, 0.15337570278299956]
    )
    lignes.append([dt.datetime(1985, 2, 28), 0.03765215356737468, 0.0100, 0.0200])
    lignes.append([dt.datetime(1985, 3, 29), -0.05196998546310775, -0.0100, -0.0200])
    lignes.extend([[None] * 4 for _ in range(2)])
    return lignes


def _mise_en_page_vme() -> list[list[object]]:
    """Rend une feuille au format de « VME Factors » : DEUX lignes de groupe.

    L'en-tête tombe à la ligne 22, ce qu'une règle codée en dur sur 19 raterait.
    """
    lignes: list[list[object]] = [[None] for _ in range(19)]
    lignes[0] = ["AQR Capital Management, LLC, Value and Momentum Everywhere: Factors, Monthly"]
    lignes.append([None, "Global Average", None, "Stock Selection"])
    lignes.append([None, "EVERYWHERE", None, "U.S. EQUITIES (US)"])
    lignes.append(["DATE", "VAL", "MOM", "VALLS_VME_US90"])
    lignes.append(["01/31/1972", 0.010064601239131863, -0.012954785120272138, None])
    lignes.append(["02/29/1972", 0.0100, 0.0200, 0.0300])
    return lignes


def _feuille_definitions() -> list[list[object]]:
    """Rend un onglet de prose seule, comme « Definitions », sans aucune date."""
    return [
        ["For more information, please see the paper."],
        [None],
        ["VAL", "Value factor"],
        ["MOM", "Momentum factor"],
    ]


def _classeur_complet() -> bytes:
    """Rend un classeur portant les trois mises en page et un onglet de prose."""
    return _ecrire_xlsx(
        {
            "BAB Factors": _mise_en_page_bab(),
            "TSMOM Factors": _mise_en_page_tsmom(),
            "VME Factors": _mise_en_page_vme(),
            "Definitions": _feuille_definitions(),
        }
    )


# --------------------------------------------------------------------------- #
# La lecture du format XLSX
# --------------------------------------------------------------------------- #


def test_le_classeur_rend_ses_feuilles_dans_lordre_du_document() -> None:
    """Source (b) : l'ordre est celui de « workbook.xml », pas celui des noms."""
    classeur = read_workbook(_classeur_complet())
    assert classeur.names == ("BAB Factors", "TSMOM Factors", "VME Factors", "Definitions")
    assert len(classeur) == 4
    assert classeur["BAB Factors"].name == "BAB Factors"
    # La recherche par nom ignore la casse et les espaces de bord.
    assert classeur["  bab factors "].name == "BAB Factors"
    with pytest.raises(KeyError, match="absente"):
        classeur["Feuille inexistante"]


def test_la_grille_est_rectangulaire_et_les_trous_valent_none() -> None:
    """Source (a) : la feuille BAB fabriquée s'arrête à sa vingt-troisième ligne.

    Le compte : 17 lignes de prose, 1 ligne de groupe, 1 ligne d'en-tête et
    4 lignes de données font 23. Les 3 lignes vides de queue ne portent aucune
    cellule, donc elles ne figurent pas dans la grille.

    Le compte des colonnes : la grille en déclare 5, mais la cinquième est vide
    partout, donc la largeur réelle tombe à 4.
    """
    feuille = read_workbook(_classeur_complet())["BAB Factors"]
    assert feuille.n_columns == 4
    assert len(feuille) == 23
    assert all(len(ligne) == 4 for ligne in feuille.rows)
    # Ligne 20 du classeur, indice 19 : la première date, deux trous, une valeur.
    assert feuille.rows[19][0] == "12/31/1930"
    assert feuille.rows[19][1] is None
    assert feuille.rows[19][3] == pytest.approx(0.0135)


def test_le_numero_de_serie_31078_est_le_31_janvier_1985() -> None:
    """Source (c) : cellule A19 de « TSMOM Factors », valeur 31078 lue le 2026-09-02.

    Source (a) pour les trois autres. Le numéro 1 est le 1er janvier 1900 par
    définition du calendrier d'Excel, et 59 est le 28 février 1900. Le numéro 61
    est le 1er mars 1900, le numéro 60 étant occupé par un jour inexistant.
    """
    assert excel_serial_to_datetime(31078) == dt.datetime(1985, 1, 31)
    assert excel_serial_to_datetime(1) == dt.datetime(1900, 1, 1)
    assert excel_serial_to_datetime(59) == dt.datetime(1900, 2, 28)
    assert excel_serial_to_datetime(61) == dt.datetime(1900, 3, 1)


def test_le_jour_fantome_du_29_fevrier_1900_est_refuse() -> None:
    """Source (b) : 1900 n'est pas bissextile, le numéro 60 ne désigne rien."""
    with pytest.raises(DataQualityError, match="29 février 1900"):
        excel_serial_to_datetime(60)
    with pytest.raises(DataQualityError, match="négatif"):
        excel_serial_to_datetime(-1)


def test_le_jour_fantome_occupe_un_jour_entier_et_non_un_instant() -> None:
    """Source (a) : le jour fantôme couvre l'intervalle [60, 61), heures comprises.

    Le calcul à la main : la partie décimale d'un numéro de série porte l'heure,
    donc 60,5 est le 29 février 1900 à midi, tout autant que 60,0 est ce même
    jour à minuit. Une borne posée sur le seul entier laissait passer 60,5, qui
    prenait alors l'origine du 30 décembre 1899 et rendait 1899-12-30 + 60,5
    jours, soit le 28 février 1900 à midi. Or 59,5 rend le même instant, par
    1899-12-31 + 59,5 jours. Deux numéros distincts pour une même heure, et un
    jour qui n'existe pas rendu comme s'il existait.
    """
    assert excel_serial_to_datetime(59.5) == dt.datetime(1900, 2, 28, 12)
    with pytest.raises(DataQualityError, match="29 février 1900"):
        excel_serial_to_datetime(60.5)
    with pytest.raises(DataQualityError, match="29 février 1900"):
        excel_serial_to_datetime(60.999)
    # La borne haute est exclue : 61,0 est le 1er mars 1900 à minuit.
    assert excel_serial_to_datetime(61.0) == dt.datetime(1900, 3, 1)


def test_le_calendrier_de_1904_est_decale_de_1462_jours() -> None:
    """Source (a) : du 1er janvier 1900 au 1er janvier 1904, il y a 1 460 jours.

    Le compte : 365 jours en 1900, 365 en 1901, 365 en 1902 et 365 en 1903.
    Aucune de ces quatre années n'est bissextile, 1900 comprise, ce qui est
    justement la cause du jour fantôme d'Excel.

    Le numéro de série du 1er janvier 1904 dans le calendrier de 1900 vaut donc
    1 462, l'origine de ce calendrier tombant le 30 décembre 1899, soit deux
    jours avant le 1er janvier 1900.
    """
    assert (dt.date(1904, 1, 1) - dt.date(1899, 12, 30)).days == 1462
    assert (dt.date(1904, 1, 1) - dt.date(1900, 1, 1)).days == 1460
    assert excel_serial_to_datetime(0, date1904=True) == dt.datetime(1904, 1, 1)
    assert excel_serial_to_datetime(1462, date1904=False) == dt.datetime(1904, 1, 1)


def test_un_format_de_pourcentage_nest_pas_un_format_de_date() -> None:
    """Source (c) : les cellules de « BAB Factors » portent le format natif 10.

    Ce format affiche « 1,35 % » là où le fichier stocke 0,0135. Le lire comme
    une date en ferait le 5 janvier 1900, et le diviser par cent coûterait un
    facteur cent. Le classeur fabriqué ici applique ce même format 10 à toutes
    ses valeurs numériques.
    """
    feuille = read_workbook(_classeur_complet())["BAB Factors"]
    valeur = feuille.rows[19][3]
    assert isinstance(valeur, float)
    assert valeur == pytest.approx(0.0135, rel=1e-12)


def test_un_format_de_date_personnalise_est_reconnu() -> None:
    """Source (b) : le code « yyyy-mm-dd » porte trois lettres de date.

    Le module ne peut pas se contenter des identifiants natifs : un classeur
    peut définir son propre format de date à partir de l'identifiant 164.
    """
    octets = _ecrire_xlsx(
        {"F": [["DATE", "X"], [dt.datetime(2020, 3, 15), 0.5]]},
        style_date=STYLE_DATE_PERSONNALISE,
    )
    feuille = read_workbook(octets)["F"]
    assert feuille.rows[1][0] == dt.datetime(2020, 3, 15)
    assert feuille.rows[1][1] == pytest.approx(0.5)


def test_les_chaines_partagees_a_plusieurs_morceaux_sont_recollees() -> None:
    """Source (b) : une chaîne enrichie s'écrit en plusieurs ``r``, et se relit d'un bloc."""
    octets = _ecrire_xlsx({"F": [["DATE", "X"], ["01/31/2020", 1.0]]})
    tampon = io.BytesIO(octets)
    with zipfile.ZipFile(tampon) as source:
        pieces = {nom: source.read(nom) for nom in source.namelist()}
    # L'écrivain range ses chaînes dans l'ordre de première apparition, soit
    # « DATE », « X » puis « 01/31/2020 ». Le remplacement garde les trois, et
    # coupe la première et la troisième en morceaux.
    pieces["xl/sharedStrings.xml"] = (
        f'<sst xmlns="{_MAIN}" count="3" uniqueCount="3">'
        "<si><r><t>DA</t></r><r><t>TE</t></r></si>"
        "<si><t>X</t></si>"
        '<si><r><t>01/31/</t></r><r><t>2020</t></r><rPh sb="0" eb="1"><t>ZZZ</t></rPh></si>'
        "</sst>"
    ).encode()
    refait = io.BytesIO()
    with zipfile.ZipFile(refait, "w", zipfile.ZIP_DEFLATED) as sortie:
        for nom, contenu in pieces.items():
            sortie.writestr(nom, contenu)
    feuille = read_workbook(refait.getvalue())["F"]
    assert feuille.rows[0][0] == "DATE"
    assert feuille.rows[1][0] == "01/31/2020"


def test_des_octets_qui_ne_sont_pas_un_classeur_sont_refuses() -> None:
    """Source (b) : une page HTML ne commence pas par la signature « PK »."""
    with pytest.raises(DataQualityError, match="classeur XLSX"):
        read_workbook(b"<html>Not found</html>")


def test_une_archive_sans_classeur_est_refusee() -> None:
    """Source (b) : une archive ZIP sans « xl/workbook.xml » n'est pas un classeur."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("lisez-moi.txt", "rien")
    with pytest.raises(DataQualityError, match="workbook"):
        read_workbook(tampon.getvalue())


def test_une_archive_tronquee_est_refusee() -> None:
    """Source (b) : les octets « PK » seuls ne forment pas une archive lisible."""
    with pytest.raises(DataQualityError, match="illisible"):
        read_workbook(b"PK\x03\x04 tronque")


# --------------------------------------------------------------------------- #
# La détection de l'en-tête et la mise en tableau
# --------------------------------------------------------------------------- #


def test_lentete_est_la_ligne_au_dessus_de_la_premiere_date() -> None:
    """Source (c) : l'en-tête de « BAB Factors » est à la ligne 19, mesuré le 2026-09-02.

    Comptée à zéro, cette ligne porte l'indice 18.
    """
    feuille = read_workbook(_classeur_complet())["BAB Factors"]
    assert detect_header_row(feuille.rows) == 18


def test_lentete_se_trouve_sans_chercher_le_mot_date() -> None:
    """Source (c) : l'en-tête de « TSMOM Factors » est à la ligne 18, cellule A vide.

    Une recherche du mot « DATE » descendrait jusqu'à la première ligne de
    données et prendrait une date pour un nom de colonne.
    """
    feuille = read_workbook(_classeur_complet())["TSMOM Factors"]
    rang = detect_header_row(feuille.rows)
    assert rang == 17
    assert feuille.rows[rang][0] is None
    assert feuille.rows[rang][1] == "TSMOM"


def test_lentete_de_vme_descend_a_la_vingt_deuxieme_ligne() -> None:
    """Source (c) : « VME Factors » porte DEUX lignes de groupe, en-tête à la ligne 22."""
    feuille = read_workbook(_classeur_complet())["VME Factors"]
    rang = detect_header_row(feuille.rows)
    assert rang == 21
    assert feuille.rows[rang][0] == "DATE"
    assert feuille.rows[rang - 1][1] == "EVERYWHERE"


def test_une_feuille_sans_aucune_date_ne_porte_pas_de_tableau() -> None:
    """Source (b) : un onglet de définitions n'a pas de colonne de dates."""
    feuille = read_workbook(_classeur_complet())["Definitions"]
    with pytest.raises(InsufficientDataError, match="aucune ligne"):
        detect_header_row(feuille.rows)


def test_une_feuille_qui_commence_par_une_date_na_pas_dentete() -> None:
    """Source (b) : sans ligne au-dessus, il n'y a pas de noms de colonnes."""
    octets = _ecrire_xlsx({"F": [["01/31/2020", 0.5]]})
    with pytest.raises(DataQualityError, match="aucun en-tête"):
        detect_header_row(read_workbook(octets)["F"].rows)


def test_le_tableau_bab_garde_ses_quatre_lignes_et_trois_colonnes() -> None:
    """Source (a) : la feuille fabriquée porte 4 dates et 3 colonnes nommées.

    La quatrième colonne du classeur n'a pas de nom dans l'en-tête, donc elle
    disparaît avec ses valeurs. Les trois lignes vides de queue disparaissent
    aussi.
    """
    frame = sheet_to_frame(read_workbook(_classeur_complet())["BAB Factors"].rows)
    assert frame.shape == (4, 3)
    assert list(frame.columns) == ["AUS", "CAN", "USA"]
    assert frame.index.name == "date"
    assert frame.index[0] == pd.Timestamp("1930-12-31")
    assert frame.index[-1] == pd.Timestamp("1931-03-31")


def test_les_valeurs_ne_sont_pas_remises_a_lechelle() -> None:
    """Source (c) : les fichiers d'AQR stockent des DÉCIMALES sous un format en pourcentage.

    La cellule vaut 0,0135 dans le classeur fabriqué, comme dans le vrai. La
    diviser par cent la ramènerait à 1,35e-4, la multiplier par cent à 1,35.
    """
    frame = sheet_to_frame(read_workbook(_classeur_complet())["BAB Factors"].rows)
    assert float(frame.loc["1930-12-31", "USA"]) == pytest.approx(0.0135, rel=1e-12)
    assert float(frame.loc["1931-01-31", "CAN"]) == pytest.approx(-0.0100, rel=1e-12)


def test_une_cellule_absente_devient_nan() -> None:
    """Source (c) : le fichier VME laisse « VALLS_VME_US90 » vide en janvier 1972."""
    frame = sheet_to_frame(read_workbook(_classeur_complet())["VME Factors"].rows)
    assert np.isnan(float(frame.loc["1972-01-31", "VALLS_VME_US90"]))
    assert float(frame.loc["1972-01-31", "VAL"]) == pytest.approx(0.010064601239131863, rel=1e-12)
    assert int(frame.isna().to_numpy().sum()) == 1


def test_les_dates_en_numero_de_serie_sont_typees_comme_les_autres() -> None:
    """Source (c) : TSMOM date au dernier jour OUVRÉ, ainsi le 29 mars 1985.

    Le 31 mars 1985 tombe un dimanche, ce qui explique la date du fichier. Le
    tableau rendu doit porter les trois dates sans qu'aucune convention ne les
    ramène à une fin de mois calendaire.
    """
    frame = sheet_to_frame(read_workbook(_classeur_complet())["TSMOM Factors"].rows)
    assert list(frame.columns) == ["TSMOM", "TSMOM^CM", "TSMOM^EQ"]
    assert list(frame.index) == [
        pd.Timestamp("1985-01-31"),
        pd.Timestamp("1985-02-28"),
        pd.Timestamp("1985-03-29"),
    ]
    assert float(frame.iloc[0]["TSMOM"]) == pytest.approx(0.043456226781221075, rel=1e-12)


def test_une_ligne_non_datee_intercalee_est_ignoree() -> None:
    """Source (b) : une note de bas de tableau n'est pas une observation."""
    grille = [
        ["DATE", "X"],
        ["01/31/2020", 1.0],
        ["Source: AQR", None],
        ["02/29/2020", 2.0],
    ]
    frame = sheet_to_frame(read_workbook(_ecrire_xlsx({"F": grille}))["F"].rows)
    assert len(frame) == 2
    assert list(frame["X"]) == [1.0, 2.0]


def test_deux_tableaux_empiles_sont_refuses() -> None:
    """Source (b) : une série mensuelle sous un en-tête unique croît strictement.

    Le contre-exemple est celui d'une feuille où un second tableau reprend sous
    le premier, sans nouvel en-tête. Les dates lues sont alors janvier 2020,
    février 2020, janvier 2020, février 2020, et les valeurs 1, 2, 9 et 8. Sans
    refus, janvier 2020 vaut à la fois 1 et 9 : une moyenne mensuelle en tire 5,
    un rééquilibrage passe deux fois le même mois, et rien ne le signale.
    """
    grille = [
        ["DATE", "X"],
        ["01/31/2020", 1.0],
        ["02/29/2020", 2.0],
        [None, None],
        ["01/31/2020", 9.0],
        ["02/29/2020", 8.0],
    ]
    with pytest.raises(DataQualityError, match="recule sur"):
        sheet_to_frame(read_workbook(_ecrire_xlsx({"F": grille}))["F"].rows)


def test_une_date_repetee_est_refusee() -> None:
    """Source (b) : deux lignes du même mois sont deux observations d'un seul mois."""
    grille = [["DATE", "X"], ["01/31/2020", 1.0], ["01/31/2020", 9.0]]
    with pytest.raises(DataQualityError, match="répète"):
        sheet_to_frame(read_workbook(_ecrire_xlsx({"F": grille}))["F"].rows)


def test_deux_colonnes_de_meme_nom_sont_refusees() -> None:
    """Source (b) : sous un nom unique, deux colonnes ne forment plus une série.

    Le contre-exemple : un en-tête « DATE, X, X » et une ligne 1,0 et 5,0. Sans
    refus, ``frame["X"]`` rend deux colonnes, et le calcul qui suit prend la
    moyenne des deux, soit 3,0, sans jamais lever.
    """
    grille = [["DATE", "X", "X"], ["01/31/2020", 1.0, 5.0]]
    with pytest.raises(DataQualityError, match="deux colonnes nommées"):
        sheet_to_frame(read_workbook(_ecrire_xlsx({"F": grille}))["F"].rows)


def _sans_attribut_r(octets: bytes, cible: str) -> bytes:
    """Rend le même classeur, l'attribut ``r`` retiré d'une ligne de la feuille 1."""
    tampon = io.BytesIO(octets)
    with zipfile.ZipFile(tampon) as source:
        pieces = {nom: source.read(nom) for nom in source.namelist()}
    chemin = "xl/worksheets/sheet1.xml"
    contenu = pieces[chemin].decode()
    assert cible in contenu
    pieces[chemin] = contenu.replace(cible, "<row>").encode()
    refait = io.BytesIO()
    with zipfile.ZipFile(refait, "w", zipfile.ZIP_DEFLATED) as sortie:
        for nom, morceau in pieces.items():
            sortie.writestr(nom, morceau)
    return refait.getvalue()


def test_une_ligne_sans_indice_de_rang_nest_pas_perdue() -> None:
    """Source (b) : l'attribut ``r`` d'une ligne est facultatif dans le format.

    La lecture des CELLULES tolère déjà l'absence de référence et retombe sur la
    position dans le document. Les lignes doivent faire de même. Sans ce repli,
    la ligne de février 2020 recevait le rang moins un et disparaissait sans
    avertissement. Deux lignes lues sur trois, une observation de rendement
    effacée, et un tableau qui garde l'air correct.
    """
    grille = [["DATE", "X"], ["01/31/2020", 1.0], ["02/29/2020", 2.0]]
    octets = _sans_attribut_r(_ecrire_xlsx({"F": grille}), '<row r="3">')
    feuille = read_workbook(octets)["F"]
    assert len(feuille) == 3
    frame = sheet_to_frame(feuille.rows)
    assert list(frame.index) == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-29")]
    assert list(frame["X"]) == [1.0, 2.0]


def test_une_cellule_de_donnees_non_numerique_est_refusee() -> None:
    """Source (b) : un texte dans une colonne de valeurs n'a pas de conversion sûre."""
    grille = [["DATE", "X"], ["01/31/2020", "n/d"]]
    with pytest.raises(DataQualityError, match="non numérique"):
        sheet_to_frame(read_workbook(_ecrire_xlsx({"F": grille}))["F"].rows)


def test_un_entete_sans_aucun_nom_de_colonne_est_refuse() -> None:
    """Source (b) : sans nom de colonne, aucune valeur n'est identifiable."""
    grille = [["DATE", None], ["01/31/2020", 1.0]]
    with pytest.raises(InsufficientDataError, match="aucun nom de colonne"):
        sheet_to_frame(read_workbook(_ecrire_xlsx({"F": grille}))["F"].rows)


def test_un_rang_dentete_hors_de_la_feuille_est_refuse() -> None:
    """Source (b) : un rang imposé doit désigner une ligne existante."""
    feuille = read_workbook(_classeur_complet())["BAB Factors"]
    with pytest.raises(DataQualityError, match="hors de la feuille"):
        sheet_to_frame(feuille.rows, header_row=999)


def test_parse_date_cell_lit_le_mois_avant_le_jour() -> None:
    """Source (c) : « 12/31/1930 » est la première date de « BAB Factors ».

    Le 31 ne peut pas être un mois, donc la convention américaine est prouvée
    par la donnée. Le test contrôle aussi le cas ambigu « 01/02/1972 », qui doit
    se lire 2 janvier et non 1er février.
    """
    assert parse_date_cell("12/31/1930") == pd.Timestamp("1930-12-31")
    assert parse_date_cell("01/02/1972") == pd.Timestamp("1972-01-02")
    assert parse_date_cell(dt.datetime(1985, 1, 31)) == pd.Timestamp("1985-01-31")
    assert parse_date_cell(dt.date(1985, 1, 31)) == pd.Timestamp("1985-01-31")
    assert parse_date_cell("EQUITIES") is None
    assert parse_date_cell("   ") is None
    assert parse_date_cell(None) is None
    assert parse_date_cell(0.5) is None


def test_le_soupcon_de_pourcentage_se_leve_au_dela_du_seuil() -> None:
    """Source (a) : le seuil vaut 1,0, mesuré au plus à 0,799 sur les vrais fichiers.

    Un rendement mensuel de 3,5 % écrit en décimales vaut 0,035 et passe ; le
    même écrit en pourcentage vaut 3,5 et déclenche le soupçon.
    """
    assert RETURN_ABS_MAX_DECIMAL == 1.0
    decimales = pd.DataFrame({"a": [0.035, -0.79]})
    pourcentages = pd.DataFrame({"a": [3.5, -79.0]})
    assert percent_scale_suspected(decimales) is False
    assert percent_scale_suspected(pourcentages) is True
    assert percent_scale_suspected(pd.DataFrame({"a": []})) is False
    # Source (b) : une feuille entièrement manquante n'apporte aucune preuve.
    assert percent_scale_suspected(pd.DataFrame({"a": [np.nan, np.nan]})) is False


# --------------------------------------------------------------------------- #
# Propriété : ce qui est écrit se relit
# --------------------------------------------------------------------------- #


@hyp_settings(max_examples=40, deadline=None)
@given(
    valeurs=st.lists(
        st.floats(min_value=-0.9, max_value=0.9, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=12,
    ),
    decalage=st.integers(min_value=0, max_value=25),
)
def test_propriete_un_tableau_ecrit_se_relit_identique(valeurs: list[float], decalage: int) -> None:
    """Source (b) : la lecture est l'inverse de l'écriture, quel que soit le décalage.

    Le décalage est le nombre de lignes de prose placées avant l'en-tête. La
    propriété tient exactement ce que le module promet : le rang de l'en-tête
    n'entre pas dans le résultat.
    """
    grille: list[list[object]] = [[f"prose {i}"] for i in range(decalage)]
    grille.append(["DATE", "X"])
    debut = dt.date(2000, 1, 31)
    for rang, valeur in enumerate(valeurs):
        grille.append([(debut + dt.timedelta(days=31 * rang)).strftime("%m/%d/%Y"), valeur])
    frame = sheet_to_frame(read_workbook(_ecrire_xlsx({"F": grille}))["F"].rows)
    assert len(frame) == len(valeurs)
    assert list(frame.columns) == ["X"]
    assert frame["X"].to_numpy() == pytest.approx(np.array(valeurs), rel=0, abs=0)


# --------------------------------------------------------------------------- #
# Contre-vérification par une bibliothèque indépendante
# --------------------------------------------------------------------------- #


def test_le_lecteur_maison_dit_la_meme_chose_que_pandas() -> None:
    """Source (d) : ``pandas.read_excel`` relit le même classeur, cellule à cellule.

    Le test ferme la boucle que l'écrivain de ce fichier ouvrirait sinon : un
    défaut symétrique entre écriture et lecture passerait inaperçu si les deux
    venaient du même auteur. Il est sauté quand ``openpyxl`` n'est pas installé,
    ce qui est le cas d'une installation propre du projet.
    """
    pytest.importorskip("openpyxl", reason="aucun moteur Excel n'est déclaré dans pyproject.toml")
    octets = _classeur_complet()
    maison = read_workbook(octets)
    for nom in maison.names:
        attendu = pd.read_excel(io.BytesIO(octets), sheet_name=nom, header=None, engine="openpyxl")
        obtenu = maison[nom].rows
        assert len(obtenu) == len(attendu)
        for rang in range(len(attendu)):
            for colonne in range(min(maison[nom].n_columns, attendu.shape[1])):
                gauche = obtenu[rang][colonne]
                droite = attendu.iloc[rang, colonne]
                if gauche is None:
                    assert pd.isna(droite)
                elif isinstance(gauche, float):
                    assert float(droite) == pytest.approx(gauche, rel=1e-12)
                elif isinstance(gauche, dt.datetime):
                    assert pd.Timestamp(droite) == pd.Timestamp(gauche)
                else:
                    assert str(droite) == gauche


# --------------------------------------------------------------------------- #
# Le registre des cinq jeux
# --------------------------------------------------------------------------- #


def test_les_cinq_jeux_portent_leurs_tailles_et_leurs_onglets_mesures() -> None:
    """Source (c) : cinq réponses 200 le 2026-09-02, tailles et onglets relevés."""
    jeux = available_datasets()
    assert set(jeux) == {"bab", "qmj", "hml_devil", "vme", "tsmom"}
    assert jeux["tsmom"].file_bytes == 139_830
    assert jeux["bab"].file_bytes == 2_500_092
    assert jeux["qmj"].file_bytes == 2_260_674
    assert jeux["vme"].file_bytes == 255_052
    assert jeux["hml_devil"].file_bytes == 1_943_770
    assert jeux["tsmom"].sheet_names == ("TSMOM Factors", "Definitions", "Data Sources", "Disclosures")
    assert jeux["vme"].sheet_names == ("VME Factors", "Definitions", "Data Sources", "Disclosures")
    # Source (c) : le classeur HML Devil porte la feuille en PRINCIPALE, donc il
    # ne la répète pas dans ses annexes, contrairement à BAB et QMJ.
    assert jeux["hml_devil"].sheet_names.count("HML Devil") == 1
    assert jeux["bab"].sheet_names.count("HML Devil") == 1
    assert len(jeux["bab"].sheet_names) == 13
    assert len(jeux["hml_devil"].sheet_names) == 12
    assert AqrProvider.available_datasets() is jeux


def test_les_rangs_dentete_mesures_different_dun_fichier_a_lautre() -> None:
    """Source (c) : 19 pour BAB, QMJ et HML Devil, 22 pour VME, 18 pour TSMOM."""
    jeux = available_datasets()
    assert jeux["bab"].sheet("BAB Factors").header_row == 19
    assert jeux["qmj"].sheet("QMJ Factors").header_row == 19
    assert jeux["hml_devil"].sheet("HML Devil").header_row == 19
    assert jeux["vme"].sheet("VME Factors").header_row == 22
    assert jeux["tsmom"].sheet("TSMOM Factors").header_row == 18
    # Source (c) : « ME(t-1) » est la seule feuille de niveaux des cinq fichiers.
    genres = {fiche.kind for spec in jeux.values() for fiche in spec.data_sheets if fiche.name != "ME(t-1)"}
    assert genres == {"returns"}
    assert jeux["bab"].sheet("ME(t-1)").kind == "level"
    with pytest.raises(KeyError, match="absente"):
        jeux["tsmom"].sheet("ME(t-1)")


def test_chaque_jeu_porte_la_mention_de_droit_dauteur_de_son_classeur() -> None:
    """Source (c) : mentions relues dans les cinq fichiers réels le 2026-09-02.

    Elles se trouvent à la ligne 13 pour BAB, QMJ, HML Devil et TSMOM, et à la
    ligne 16 pour VME, dont la prose compte trois lignes de plus. Le fichier
    écrit « Copyright ©2012 Tobias Moskowitz, Yao Hua Ooi, and Lasse Heje
    Pedersen », symbole compris, et une citation qui perd un caractère n'est
    plus une citation.
    """
    jeux = available_datasets()
    assert jeux["tsmom"].copyright_notice == (
        "Copyright ©2012 Tobias Moskowitz, Yao Hua Ooi, and Lasse Heje Pedersen"
    )
    assert jeux["vme"].copyright_notice == (
        "Copyright ©2013 Cliff Asness, Tobias Moskowitz and Lasse Heje Pedersen"
    )
    # Le symbole est dans les cinq fichiers, donc dans les cinq fiches.
    assert all("©" in spec.copyright_notice for spec in jeux.values())
    assert "Frazzini" in jeux["bab"].copyright_notice
    assert "Asness" in jeux["hml_devil"].copyright_notice


def test_resolve_dataset_accepte_la_cle_et_le_nom_de_fichier() -> None:
    """Source (b) : trois écritures du même jeu doivent rendre la même fiche."""
    par_cle = resolve_dataset("tsmom")
    assert resolve_dataset("Time-Series-Momentum-Factors-Monthly.xlsx") is par_cle
    assert resolve_dataset("time-series-momentum-factors-monthly") is par_cle
    with pytest.raises(ConfigError, match="vide"):
        resolve_dataset("   ")
    with pytest.raises(ConfigError, match="inconnu"):
        resolve_dataset("bab-daily")


# --------------------------------------------------------------------------- #
# Le fournisseur
# --------------------------------------------------------------------------- #


class _ClientFaux:
    """Client HTTP de test : il rend une réponse préparée, sans réseau.

    Le socle des fournisseurs ne connaît de son client qu'une méthode ``get``
    rendant une :class:`RawResponse`, si bien que ce double suffit.
    """

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get(self, url: str, *, params=None, headers=None) -> RawResponse:
        """Rend la charge préparée et note l'adresse appelée."""
        self.calls.append(url)
        return RawResponse(content=self.payload, url=url)


def _provider(tmp_path, client: _ClientFaux) -> AqrProvider:
    """Un fournisseur branché sur un cache jetable et un client de test."""
    return AqrProvider(client=client, raw_root=tmp_path / "aqr")


def _classeur_de_jeu(spec_key: str) -> bytes:
    """Rend un classeur dont la feuille de référence porte le nom attendu."""
    nom = available_datasets()[spec_key].factor_sheet
    mises_en_page = {
        "tsmom": _mise_en_page_tsmom(),
        "vme": _mise_en_page_vme(),
    }
    return _ecrire_xlsx(
        {nom: mises_en_page.get(spec_key, _mise_en_page_bab()), "Definitions": _feuille_definitions()}
    )


def test_ladresse_du_classeur_est_celle_du_site() -> None:
    """Source (c) : adresse vérifiée le 2026-09-02, réponse 200 et 139 830 octets."""
    provider = AqrProvider()
    assert provider.dataset_url("tsmom") == (f"{BASE_URL}Time-Series-Momentum-Factors-Monthly.xlsx")
    assert provider.dataset_url("bab").endswith("Betting-Against-Beta-Equity-Factors-Monthly.xlsx")
    with pytest.raises(ConfigError):
        provider.dataset_url("  ")


def test_le_fournisseur_satisfait_le_protocole() -> None:
    """Source (b) : le protocole est structurel, l'instance doit le remplir."""
    assert isinstance(AqrProvider(), DataProvider)
    assert AqrProvider.name == "aqr"


def test_fetch_rend_la_feuille_de_reference_du_jeu(tmp_path) -> None:
    """Source (a) : la feuille BAB fabriquée porte 4 lignes et 3 colonnes."""
    provider = _provider(tmp_path, _ClientFaux(_classeur_de_jeu("bab")))
    frame = provider.fetch("bab")
    assert frame.shape == (4, 3)
    assert list(frame.columns) == ["AUS", "CAN", "USA"]
    assert float(frame.loc["1930-12-31", "USA"]) == pytest.approx(0.0135, rel=1e-12)


def test_fetch_ne_decale_aucune_valeur_par_rapport_a_sa_date(tmp_path) -> None:
    """Source (a) : chaque valeur reste sur la ligne où le classeur l'écrit.

    La feuille fabriquée porte quatre lignes, et la colonne « USA » y vaut
    0,0135, 0,0300, 0,0100 puis -0,0225. Un décalage d'un cran vers le haut,
    la fuite temporelle classique, ferait remonter 0,0300 au 31 décembre 1930 et
    donnerait un signal qui connaît le mois suivant. Un décalage vers le bas
    donnerait un retard silencieux. Le test épingle les quatre couples, donc les
    deux sens tombent.
    """
    provider = _provider(tmp_path, _ClientFaux(_classeur_de_jeu("bab")))
    usa = provider.fetch("bab")["USA"]
    attendu = {
        "1930-12-31": 0.0135,
        "1931-01-31": 0.0300,
        "1931-02-28": 0.0100,
        "1931-03-31": -0.0225,
    }
    assert [d.strftime("%Y-%m-%d") for d in usa.index] == list(attendu)
    for date, valeur in attendu.items():
        assert float(usa.loc[date]) == pytest.approx(valeur, rel=1e-12)


def test_fetch_borne_la_periode_aux_deux_extremites(tmp_path) -> None:
    """Source (a) : sur quatre mois, deux bornes internes en gardent deux."""
    provider = _provider(tmp_path, _ClientFaux(_classeur_de_jeu("bab")))
    frame = provider.fetch("bab", None, "1931-01-01", "1931-02-28")
    assert len(frame) == 2
    assert frame.index[0] == pd.Timestamp("1931-01-31")
    assert frame.index[-1] == pd.Timestamp("1931-02-28")


def test_les_raccourcis_pointent_la_feuille_de_leur_etude(tmp_path) -> None:
    """Source (b) : chaque raccourci lit la feuille nommée par sa fiche."""
    provider = _provider(tmp_path, _ClientFaux(_classeur_de_jeu("tsmom")))
    frame = provider.tsmom_factors()
    assert list(frame.columns) == ["TSMOM", "TSMOM^CM", "TSMOM^EQ"]
    assert frame.index[0] == pd.Timestamp("1985-01-31")
    vme = _provider(tmp_path / "b", _ClientFaux(_classeur_de_jeu("vme"))).vme_factors()
    assert list(vme.columns) == ["VAL", "MOM", "VALLS_VME_US90"]
    for nom, cle in (
        ("bab_factors", "bab"),
        ("qmj_factors", "qmj"),
        ("hml_devil_factors", "hml_devil"),
    ):
        client = _ClientFaux(_classeur_de_jeu(cle))
        raccourci = getattr(_provider(tmp_path / cle, client), nom)
        assert raccourci().shape == (4, 3)
        assert client.calls[0].endswith(available_datasets()[cle].filename)


def test_les_onglets_reellement_presents_sont_lisibles(tmp_path) -> None:
    """Source (b) : le fournisseur rend les noms du fichier, pas ceux de sa fiche."""
    provider = _provider(tmp_path, _ClientFaux(_classeur_de_jeu("tsmom")))
    assert provider.sheet_names("tsmom") == ("TSMOM Factors", "Definitions")


def test_un_onglet_sans_tableau_leve_insufficient_data(tmp_path) -> None:
    """Source (b) : l'onglet de définitions ne porte aucune ligne datée."""
    provider = _provider(tmp_path, _ClientFaux(_classeur_de_jeu("tsmom")))
    with pytest.raises(InsufficientDataError):
        provider.fetch("tsmom", "Definitions")
    with pytest.raises(KeyError, match="absente"):
        provider.fetch("tsmom", "Onglet inexistant")


def test_le_classeur_est_mis_en_cache_et_relu_sans_reseau(tmp_path) -> None:
    """Source (b) : le second appel ne doit toucher aucun client."""
    client = _ClientFaux(_classeur_de_jeu("bab"))
    provider = _provider(tmp_path, client)
    provider.fetch("bab")
    assert len(client.calls) == 1
    provider.fetch("bab")
    assert len(client.calls) == 1
    cle = cache_key(provider.dataset_url("bab"), None, "bab")
    assert len(provider.cached_paths(cle)) == 1


def test_une_reponse_qui_nest_pas_un_classeur_est_refusee(tmp_path) -> None:
    """Source (b) : une page d'erreur arrive avec un code 200 et n'est pas un ZIP."""
    provider = _provider(tmp_path, _ClientFaux(b"<html>Not found</html>"))
    with pytest.raises(DataQualityError, match="classeur XLSX"):
        provider.fetch("bab")


def test_une_echelle_en_pourcentage_est_signalee(tmp_path, caplog) -> None:
    """Source (b) : des rendements au-dessus du seuil valent un avertissement.

    Le contrôle ne lève pas : une source peut publier une valeur extrême sans
    changer d'unité. Il laisse une trace, qui est ce qu'un journal sert à faire.
    """
    grille = _mise_en_page_bab()
    grille[20][3] = 13.5
    octets = _ecrire_xlsx({"BAB Factors": grille})
    provider = _provider(tmp_path, _ClientFaux(octets))
    with caplog.at_level("WARNING"):
        provider.fetch("bab")
    assert any("échelle inattendue" in enregistrement.message for enregistrement in caplog.records)


def test_le_manifeste_declare_ce_qui_decide_dun_backtest(tmp_path) -> None:
    """Source (c) : AQR reconstruit son histoire entière à chaque mise à jour.

    La phrase est lue à la ligne 12 de la feuille de facteurs de chaque
    classeur, le 2026-09-02 : « AQR reconstructs the full history each time the
    portfolios are updated. »
    """
    import hashlib

    provider = _provider(tmp_path, _ClientFaux(_classeur_de_jeu("bab")))
    manifeste = provider.manifest("bab")
    assert manifeste.point_in_time is False
    # Source (c) : la règle d'univers d'AQR n'est publiée nulle part, cherché le
    # 2026-09-02 sur la page du jeu et sur les onglets de sources.
    assert manifeste.survivorship_free is None
    assert manifeste.provider == "aqr"
    assert manifeste.frequency is Frequency.MONTHLY
    assert manifeste.url.endswith("Betting-Against-Beta-Equity-Factors-Monthly.xlsx")
    assert manifeste.n_rows == 4
    assert manifeste.columns == ("AUS", "CAN", "USA")
    assert manifeste.n_columns == 3
    assert manifeste.data_start == dt.date(1930, 12, 31)
    assert manifeste.data_end == dt.date(1931, 3, 31)
    assert manifeste.dataset_id == "aqr-bab-bab-factors"
    # Source (c) : la clause exacte des conditions d'utilisation, lue le 2026-09-02.
    assert "without AQR's express prior written consent" in manifeste.license
    assert manifeste.license_url == "https://www.aqr.com/Terms-of-Use"
    assert "Frazzini" in manifeste.notes
    # Source (c) : le retard mesuré sur « Last-Modified » voyage avec le jeu.
    assert PUBLICATION_LAG in manifeste.notes
    # Source (d) : l'empreinte est celle que hashlib calcule sur les mêmes octets.
    attendu = hashlib.sha256(provider.raw_workbook("bab").content).hexdigest()
    assert manifeste.checksum_sha256 == attendu


def test_le_manifeste_ne_manque_que_de_sa_lignee(tmp_path) -> None:
    """Source (b) : un jeu téléchargé n'a pas de parent, tout le reste est rempli."""
    provider = _provider(tmp_path, _ClientFaux(_classeur_de_jeu("bab")))
    assert provider.manifest("bab").missing_for_gold() == ("parent_datasets",)


def test_le_manifeste_refuse_un_tableau_vide(tmp_path) -> None:
    """Source (b) : sans ligne, la période couverte est indéterminée."""
    provider = _provider(tmp_path, _ClientFaux(_classeur_de_jeu("bab")))
    vide = provider.fetch("bab", None, "2100-01-01", "2100-12-31")
    with pytest.raises(InsufficientDataError, match="vide"):
        provider.manifest("bab", frame=vide)


# --------------------------------------------------------------------------- #
# Le réseau, facultatif
# --------------------------------------------------------------------------- #
def _client_reseau() -> HttpClient:
    """Un client identifié par un courriel, comme le socle l'exige."""
    return HttpClient(settings=Settings(user_agent="quantlab research (vaudescal.guillaumepro@gmail.com)"))


@pytest.mark.network
def test_reseau_le_classeur_tsmom_a_la_forme_annoncee(tmp_path) -> None:
    """Source (c) : 139 830 octets, quatre onglets, première date le 31 janvier 1985.

    Le plus petit des cinq fichiers est retenu pour que le test réseau reste
    court. La première date est celle de l'échantillon de Moskowitz, Ooi et
    Pedersen (2012), et elle ne bouge pas d'un millésime à l'autre.
    """
    provider = AqrProvider(client=_client_reseau(), raw_root=tmp_path / "aqr")
    brut = provider.raw_workbook("tsmom")
    assert brut.size_bytes == 139_830
    assert provider.sheet_names("tsmom") == ("TSMOM Factors", "Definitions", "Data Sources", "Disclosures")
    frame = provider.tsmom_factors()
    assert list(frame.columns) == ["TSMOM", "TSMOM^CM", "TSMOM^EQ", "TSMOM^FI", "TSMOM^FX"]
    assert frame.index[0] == pd.Timestamp("1985-01-31")
    # Source (c) : les valeurs sont des décimales, pas des pourcentages. Le
    # maximum absolu mesuré le 2026-09-02 vaut 0,348.
    assert float(np.nanmax(np.abs(frame.to_numpy()))) < RETURN_ABS_MAX_DECIMAL
    # Source (b) : le facteur toutes classes est une moyenne des quatre classes,
    # donc il ne peut pas sortir de leur intervalle.
    par_classe = frame[["TSMOM^CM", "TSMOM^EQ", "TSMOM^FI", "TSMOM^FX"]]
    assert bool((frame["TSMOM"] <= par_classe.max(axis=1) + 1e-9).all())
    assert bool((frame["TSMOM"] >= par_classe.min(axis=1) - 1e-9).all())


@pytest.mark.network
def test_reseau_les_dates_en_texte_du_classeur_bab(tmp_path) -> None:
    """Source (c) : « BAB Factors » commence le 31 décembre 1930, date écrite en TEXTE.

    Le contraste avec TSMOM est la raison d'être de la détection : ce fichier
    stocke ses dates en chaînes « MM/DD/YYYY » alors que TSMOM stocke des
    numéros de série. Le manifeste doit rendre la même première date que la
    fiche mesurée le 2026-09-02.
    """
    provider = AqrProvider(client=_client_reseau(), raw_root=tmp_path / "aqr")
    frame = provider.bab_factors()
    assert frame.index[0] == pd.Timestamp("1930-12-31")
    assert len(frame.columns) == 29
    assert "USA" in frame.columns
    manifeste = provider.manifest("bab", frame=frame)
    assert manifeste.data_start == available_datasets()["bab"].first_period


@pytest.mark.network
def test_reseau_la_fiche_dit_bien_ce_que_le_fichier_contient(tmp_path) -> None:
    """Source (c) : la fiche du registre est confrontée au fichier, pas à elle-même.

    Sans ce test, les assertions du registre comparent une constante à la même
    constante recopiée, et aucune ne peut échouer. Ici la taille, les onglets,
    le rang d'en-tête, le nombre de lignes datées, les noms de colonnes et les
    deux bornes de période sont relus dans le classeur téléchargé.
    """
    provider = AqrProvider(client=_client_reseau(), raw_root=tmp_path / "aqr")
    for cle in ("tsmom", "bab"):
        spec = available_datasets()[cle]
        brut = provider.raw_workbook(cle)
        classeur = read_workbook(brut.content)
        assert brut.size_bytes == spec.file_bytes
        assert classeur.names == spec.sheet_names
        for fiche in spec.data_sheets:
            lignes = classeur[fiche.name].rows
            assert detect_header_row(lignes) + 1 == fiche.header_row
            assert len(sheet_to_frame(lignes)) == fiche.n_rows
        reference = sheet_to_frame(classeur[spec.factor_sheet].rows)
        assert tuple(reference.columns) == spec.columns
        assert reference.index[0].date() == spec.first_period
        assert reference.index[-1].date() == spec.last_period
        # Source (b) : sous un en-tête unique, la série mensuelle croît strictement.
        assert bool(reference.index.is_monotonic_increasing) and bool(reference.index.is_unique)


@pytest.mark.network
def test_reseau_la_derniere_ligne_est_publiee_des_semaines_apres_sa_periode(tmp_path) -> None:
    """Source (c) : la date de période n'est pas la date de disponibilité.

    L'en-tête HTTP ``Last-Modified`` donne la seule date de publication que la
    source expose. Deux mesures du 2026-09-02. La dernière ligne de BAB porte le
    2026-06-30 dans un fichier modifié le 2026-08-26, soit 57 jours plus tard.
    Celle de TSMOM porte le 2026-05-29 dans un fichier modifié le 2026-06-26,
    soit 28 jours plus tard.

    Le test n'épingle pas ces deux nombres, qui bougent à chaque mise à jour. Il
    épingle le fait qui décide d'un backtest. Au jour du téléchargement, le
    dernier mois disponible est vieux d'au moins trente jours. Agir sur la ligne
    d'un mois à la fin de ce mois emploie donc un chiffre qui n'existe pas.
    """
    provider = AqrProvider(client=_client_reseau(), raw_root=tmp_path / "aqr")
    for cle in ("tsmom", "bab"):
        brut = provider.raw_workbook(cle)
        derniere = provider.fetch(cle).index[-1].date()
        retard = (brut.fetched_at.date() - derniere).days
        assert retard >= 30, f"{cle} : dernière ligne {derniere}, retard {retard} jours"
        publie = parsedate_to_datetime(brut.headers["last-modified"]).date()
        # La publication suit la période décrite, jamais l'inverse.
        assert publie > derniere, f"{cle} : publié le {publie}, dernière ligne {derniere}"
