"""Tests du fournisseur FRED et ALFRED, tous hors réseau sauf deux, marqués « network ».

Règle tenue ici : aucune valeur attendue ne vient de la sortie du code. Chaque
assertion porte en commentaire la source de sa valeur, parmi quatre. (a) Un
calcul à la main, chiffres visibles dans le commentaire. (b) Une identité
mathématique. (c) Une valeur publiée par la source, citée avec sa date de
mesure. (d) Une implémentation indépendante.

Les extraits de CSV recopiés ci-dessous sont des morceaux exacts des fichiers
téléchargés le 2026-09-01 depuis ``fredgraph.csv`` et ``alfredgraph.csv``. Ils
servent de vérité connue pour les tests hors réseau.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    LookAheadError,
)
from quantlab.core.protocols import DataProvider, PointInTimeDataset
from quantlab.core.types import Frequency
from quantlab.data.providers.base import RawResponse
from quantlab.data.providers.fred import (
    OBSERVATION_DATE,
    PANEL_SCHEMA,
    VALUE,
    VINTAGE_DATE,
    AlfredProvider,
    FredProvider,
    VintagePanel,
    as_of,
    build_vintage_panel,
    check_vintage_ordering,
    combine_checksums,
    empty_panel,
    infer_frequency,
    parse_fred_csv,
    series_id_from_header,
)

# ---------------------------------------------------------------------------
# Vérités connues : extraits mesurés le 2026-09-01. Source (c).
# ---------------------------------------------------------------------------

#: Les six premières lignes de ``fredgraph.csv?id=DGS10``, taux du Trésor
#: américain à dix ans. Mesuré le 2026-09-01, fichier de 16 870 lignes.
DGS10_DEBUT = (
    "observation_date,DGS10\n"
    "1962-01-02,4.06\n"
    "1962-01-03,4.03\n"
    "1962-01-04,3.99\n"
    "1962-01-05,4.02\n"
    "1962-01-08,4.03\n"
)

#: La semaine du 4 juillet 2025 dans le même fichier. La séance du 4 juillet est
#: fériée et sa cellule est VIDE, mesuré le 2026-09-01. Aucun point n'apparaît
#: dans les 16 869 observations, contrairement à la convention historique.
DGS10_FERIE = (
    "observation_date,DGS10\n"
    "2025-07-01,4.26\n"
    "2025-07-02,4.30\n"
    "2025-07-03,4.35\n"
    "2025-07-04,\n"
    "2025-07-07,4.40\n"
    "2025-07-08,4.42\n"
)

#: La même semaine réécrite avec la convention historique du point. Statut :
#: rapporté, cette écriture n'a pas été observée le 2026-09-01 sur cette série.
DGS10_FERIE_POINT = DGS10_FERIE.replace("2025-07-04,\n", "2025-07-04,.\n")

#: PIB réel américain, millésime du 2008-04-30, trois derniers trimestres
#: publiés. Mesuré le 2026-09-01 sur ``alfredgraph.csv?id=GDPC1``.
GDPC1_MILLESIME_2008 = (
    "observation_date,GDPC1_20080430\n2007-07-01,11658.9\n2007-10-01,11675.7\n2008-01-01,11693.1\n"
)

#: Les mêmes trois trimestres, millésime du 2026-08-01. Les niveaux ont changé
#: d'année de référence, seules les croissances se comparent. Mesuré le
#: 2026-09-01.
GDPC1_MILLESIME_2026 = (
    "observation_date,GDPC1_20260801\n2007-07-01,16809.587\n2007-10-01,16915.191\n2008-01-01,16843.003\n"
)


# ---------------------------------------------------------------------------
# Doublures : un client HTTP factice, aucune sortie réseau.
# ---------------------------------------------------------------------------


class FakeClient:
    """Client factice : rend un contenu choisi selon les paramètres reçus.

    Il porte la seule méthode que :meth:`BaseProvider.fetch_cached` appelle, et
    garde la trace des appels pour que les tests vérifient les paramètres
    envoyés et le nombre de requêtes.
    """

    def __init__(self, bodies: dict[str, str]) -> None:
        self.bodies = bodies
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> RawResponse:
        sent = dict(params or {})
        self.calls.append({"url": url, "params": sent})
        cle = f"{sent.get('id', '')}|{sent.get('vintage_date', '')}"
        if cle not in self.bodies:
            raise AssertionError(f"le test n'a pas prévu de réponse pour « {cle} »")
        return RawResponse(
            content=self.bodies[cle].encode("utf-8"),
            url=url,
            fetched_at=dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.UTC),
            status_code=200,
        )


def _fred(tmp_path: Path, bodies: dict[str, str]) -> tuple[FredProvider, FakeClient]:
    """Construit un fournisseur FRED branché sur un client factice."""
    client = FakeClient(bodies)
    return FredProvider(client=client, raw_root=tmp_path / "fred"), client


def _alfred(tmp_path: Path, bodies: dict[str, str]) -> tuple[AlfredProvider, FakeClient]:
    """Construit un fournisseur ALFRED branché sur un client factice."""
    client = FakeClient(bodies)
    return AlfredProvider(client=client, raw_root=tmp_path / "alfred"), client


def _croissance_annualisee(niveau_t: float, niveau_precedent: float) -> float:
    """Rend la croissance trimestrielle annualisée, en pourcentage.

    Implémentation indépendante du module testé, écrite ici pour que le test ne
    se contente pas de recopier une sortie. Source (b) : la formule
    ``(Y_t / Y_{t-1})**4 - 1`` est celle du BEA pour un taux annualisé.
    """
    return ((niveau_t / niveau_precedent) ** 4 - 1.0) * 100.0


# ---------------------------------------------------------------------------
# Analyse du CSV
# ---------------------------------------------------------------------------


def test_parse_rend_les_valeurs_publiees() -> None:
    """Les cinq premières valeurs de DGS10 sont celles publiées par FRED."""
    serie = parse_fred_csv(DGS10_DEBUT)
    # Source (c) : les cinq lignes de l'export, mesurées le 2026-09-01.
    assert serie.index[0] == pd.Timestamp("1962-01-02")
    assert float(serie.iloc[0]) == 4.06
    assert float(serie.iloc[4]) == 4.03
    assert len(serie) == 5
    assert serie.name == "DGS10"
    assert str(serie.dtype) == "float64"
    # Source (b) : une seule unité temporelle dans tout le laboratoire.
    assert str(serie.index.dtype) == "datetime64[ns]"
    assert serie.index.name == OBSERVATION_DATE


def test_parse_cellule_vide_devient_nan() -> None:
    """Le 4 juillet 2025 est férié, sa cellule est vide, et sa valeur est NaN."""
    serie = parse_fred_csv(DGS10_FERIE)
    # Source (c) : ligne « 2025-07-04, » de l'export, mesurée le 2026-09-01.
    assert bool(serie.isna().loc[pd.Timestamp("2025-07-04")])
    assert serie.isna().sum() == 1
    assert float(serie.loc[pd.Timestamp("2025-07-03")]) == 4.35


def test_parse_point_devient_nan() -> None:
    """Un point est l'écriture historique d'une absence, et devient NaN aussi."""
    serie = parse_fred_csv(DGS10_FERIE_POINT)
    # Source (c) : convention publiée par FRED pour ses fichiers texte.
    assert bool(serie.isna().loc[pd.Timestamp("2025-07-04")])
    # Source (b) : les deux écritures décrivent la même absence, donc les deux
    # séries doivent coïncider valeur par valeur.
    pd.testing.assert_series_equal(serie, parse_fred_csv(DGS10_FERIE))


def test_parse_refuse_une_date_en_double() -> None:
    """Deux fois la même date rend l'index ambigu, donc l'analyse échoue."""
    texte = "observation_date,DGS10\n2020-01-02,1.88\n2020-01-02,1.90\n"
    with pytest.raises(DataQualityError, match="double"):
        parse_fred_csv(texte)


def test_parse_refuse_une_valeur_qui_nest_pas_un_nombre() -> None:
    """Une valeur inconnue ne devient pas NaN en silence."""
    texte = "observation_date,DGS10\n2020-01-02,1.88\n2020-01-03,indisponible\n"
    with pytest.raises(DataQualityError, match="ni nombre ni absence"):
        parse_fred_csv(texte)


def test_parse_refuse_une_date_illisible() -> None:
    """Une date au mauvais format nomme sa ligne dans le message d'erreur."""
    texte = "observation_date,DGS10\n02/01/2020,1.88\n"
    with pytest.raises(DataQualityError, match="ligne 2"):
        parse_fred_csv(texte)


def test_parse_refuse_une_entete_inattendue() -> None:
    """Une première colonne qui n'est pas une date fait échouer l'analyse."""
    with pytest.raises(DataQualityError, match="première colonne"):
        parse_fred_csv("periode,DGS10\n2020-01-02,1.88\n")


def test_parse_refuse_plusieurs_series() -> None:
    """Un export à trois colonnes n'est pas une série unique."""
    with pytest.raises(DataQualityError, match="deux colonnes"):
        parse_fred_csv("observation_date,DGS10,DGS2\n2020-01-02,1.88,1.57\n")


def test_parse_csv_vide_leve() -> None:
    """Un fichier vide ne porte aucune observation."""
    with pytest.raises(InsufficientDataError):
        parse_fred_csv("")


def test_parse_entete_seule_leve() -> None:
    """Un fichier réduit à son en-tête ne porte aucune observation."""
    with pytest.raises(InsufficientDataError, match="aucune observation"):
        parse_fred_csv("observation_date,DGS10\n")


def test_parse_un_seul_point() -> None:
    """Une observation unique s'analyse, l'index en porte une."""
    serie = parse_fred_csv("observation_date,DGS10\n2020-01-02,1.88\n")
    # Source (a) : une ligne de données donne une observation.
    assert len(serie) == 1
    assert float(serie.iloc[0]) == 1.88


def test_parse_serie_constante() -> None:
    """Une série constante n'a rien de spécial, sa variance est nulle."""
    texte = "observation_date,X\n2020-01-02,2.0\n2020-01-03,2.0\n2020-01-06,2.0\n"
    serie = parse_fred_csv(texte)
    # Source (b) : la variance d'une constante vaut zéro.
    assert float(serie.var(ddof=0)) == 0.0


def test_parse_toutes_valeurs_absentes() -> None:
    """Une série entièrement absente rend des NaN, et ne lève pas."""
    serie = parse_fred_csv("observation_date,X\n2020-01-02,.\n2020-01-03,\n")
    # Source (a) : deux lignes, deux absences.
    assert len(serie) == 2
    assert int(serie.isna().sum()) == 2


def test_parse_trie_sans_deplacer_les_valeurs() -> None:
    """Un export à l'envers ressort trié, chaque valeur restant sur sa date.

    Le tri d'un index et le tri de ses valeurs sont deux opérations distinctes,
    et les séparer décale toute la série sans changer ni le nombre de lignes ni
    les colonnes. Ce test tient les couples ensemble.
    """
    texte = "observation_date,DGS10\n1962-01-04,3.99\n1962-01-02,4.06\n1962-01-03,4.03\n"
    serie = parse_fred_csv(texte)
    # Source (c) : les trois premières séances de DGS10, mesurées le 2026-09-01,
    # remises dans l'ordre du calendrier.
    assert serie.index.is_monotonic_increasing
    assert serie.loc[pd.Timestamp("1962-01-02")] == 4.06
    assert serie.loc[pd.Timestamp("1962-01-03")] == 4.03
    assert serie.loc[pd.Timestamp("1962-01-04")] == 3.99


def test_parse_nom_impose() -> None:
    """Le nom demandé l'emporte sur celui de l'en-tête."""
    serie = parse_fred_csv(GDPC1_MILLESIME_2008, series_id="PIB")
    assert serie.name == "PIB"


@pytest.mark.parametrize(
    ("entete", "attendu"),
    [
        # Source (c) : en-têtes mesurés le 2026-09-01 sur alfredgraph.csv et fredgraph.csv.
        ("GDPC1_20080430", ("GDPC1", dt.date(2008, 4, 30))),
        ("GDPC1_20260801", ("GDPC1", dt.date(2026, 8, 1))),
        ("DGS10", ("DGS10", None)),
        # Source (a) : huit chiffres qui ne forment pas une date restent dans le nom.
        ("SERIE_99999999", ("SERIE_99999999", None)),
        # Source (a) : un suffixe de six chiffres n'est pas un millésime.
        ("SERIE_200804", ("SERIE_200804", None)),
    ],
)
def test_series_id_from_header(entete: str, attendu: tuple[str, dt.date | None]) -> None:
    """L'identifiant et le millésime se lisent dans le nom de colonne."""
    assert series_id_from_header(entete) == attendu


def test_series_id_from_header_refuse_le_vide() -> None:
    """Une colonne sans nom fait échouer la lecture."""
    with pytest.raises(DataQualityError):
        series_id_from_header("   ")


# ---------------------------------------------------------------------------
# Déduction de fréquence
# ---------------------------------------------------------------------------


def test_infer_frequency_quotidien() -> None:
    """Cinq séances consécutives donnent un écart médian d'un jour."""
    index = pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"])
    # Source (a) : écarts de 1, 3 et 1 jour, médiane 1, donc sous le seuil de 4.
    assert infer_frequency(index) is Frequency.DAILY


def test_infer_frequency_mensuel() -> None:
    """Trois débuts de mois donnent des écarts de 31 et 29 jours."""
    index = pd.DatetimeIndex(["2020-01-01", "2020-02-01", "2020-03-01"])
    # Source (a) : janvier compte 31 jours, février 2020 en compte 29,
    # médiane 30, comprise entre 10 et 45.
    assert infer_frequency(index) is Frequency.MONTHLY


def test_infer_frequency_trimestriel() -> None:
    """Trois débuts de trimestre donnent des écarts de 91 jours."""
    index = pd.DatetimeIndex(["2008-01-01", "2008-04-01", "2008-07-01"])
    # Source (a) : janvier + février + mars 2008 font 31 + 29 + 31 = 91 jours,
    # avril + mai + juin font 30 + 31 + 30 = 91, médiane 91, entre 45 et 135.
    assert infer_frequency(index) is Frequency.QUARTERLY


def test_infer_frequency_annuel() -> None:
    """Trois 1er janvier donnent des écarts de 366 et 365 jours."""
    index = pd.DatetimeIndex(["2019-01-01", "2020-01-01", "2021-01-01"])
    # Source (a) : 2019 compte 365 jours, 2020 en compte 366, médiane 365,5,
    # au-delà du dernier seuil de 135.
    assert infer_frequency(index) is Frequency.ANNUAL


def test_infer_frequency_hebdomadaire() -> None:
    """Trois vendredis consécutifs donnent des écarts de sept jours."""
    index = pd.DatetimeIndex(["2020-01-03", "2020-01-10", "2020-01-17"])
    # Source (a) : une semaine fait 7 jours, médiane 7, entre les bornes 4 et 10.
    assert infer_frequency(index) is Frequency.WEEKLY


def test_infer_frequency_borne_ouverte_a_droite() -> None:
    """Un écart médian posé exactement sur une borne bascule dans la classe du dessus."""
    index = pd.DatetimeIndex(["2020-01-01", "2020-01-05", "2020-01-09"])
    # Source (a) : écarts de 4 et 4 jours, médiane 4, égale à la borne du
    # quotidien. La borne étant ouverte à droite, 4 n'est pas « moins de 4 »,
    # donc la déduction descend d'un cran et rend l'hebdomadaire.
    assert infer_frequency(index) is Frequency.WEEKLY


def test_infer_frequency_se_trompe_sur_un_index_repete() -> None:
    """Un index qui répète ses dates fait déduire « quotidien », limite déclarée.

    Le panneau de millésimes porte chaque trimestre autant de fois qu'il compte
    de millésimes. Ce test fixe la limite documentée par la fonction, et il est
    la raison pour laquelle le manifeste d'un panneau dédoublonne son index.
    """
    index = pd.DatetimeIndex(
        ["2007-07-01", "2007-07-01", "2007-10-01", "2007-10-01", "2008-01-01", "2008-01-01"]
    )
    # Source (a) : écarts 0, 92, 0, 92, 0 jours, donc une médiane de 0, sous la
    # borne de 4 jours. Juillet + août + septembre font 31 + 31 + 30 = 92.
    assert infer_frequency(index) is Frequency.DAILY
    # Source (a) : les mêmes dates sans doublon donnent 92 et 92, médiane 92.
    assert infer_frequency(pd.DatetimeIndex(index.unique())) is Frequency.QUARTERLY


def test_infer_frequency_refuse_un_point_unique() -> None:
    """Un écart n'existe pas sur une observation unique."""
    with pytest.raises(InsufficientDataError):
        infer_frequency(pd.DatetimeIndex(["2020-01-02"]))


# ---------------------------------------------------------------------------
# Le panneau de millésimes
# ---------------------------------------------------------------------------


def _panneau_gdp() -> pd.DataFrame:
    """Rend le panneau des deux millésimes mesurés de GDPC1."""
    return build_vintage_panel(
        {
            dt.date(2008, 4, 30): parse_fred_csv(GDPC1_MILLESIME_2008),
            dt.date(2026, 8, 1): parse_fred_csv(GDPC1_MILLESIME_2026),
        }
    )


def test_panneau_forme_et_tri() -> None:
    """Deux millésimes de trois trimestres donnent six lignes triées."""
    panneau = _panneau_gdp()
    # Source (a) : 2 millésimes multipliés par 3 observations font 6 lignes.
    assert len(panneau) == 6
    assert tuple(panneau.columns) == PANEL_SCHEMA
    assert panneau[OBSERVATION_DATE].is_monotonic_increasing
    assert str(panneau[VINTAGE_DATE].dtype) == "datetime64[ns]"


def test_panneau_conserve_les_deux_versions() -> None:
    """Le même trimestre porte deux valeurs, une par millésime."""
    panneau = _panneau_gdp()
    lignes = panneau.loc[panneau[OBSERVATION_DATE] == pd.Timestamp("2008-01-01")]
    # Source (c) : 11 693,1 au millésime d'avril 2008, 16 843,003 à celui d'août 2026.
    assert sorted(lignes[VALUE].tolist()) == [11693.1, 16843.003]


def test_panneau_refuse_un_millesime_en_double() -> None:
    """Deux clés qui désignent le même jour font un doublon, et le panneau lève."""
    serie = parse_fred_csv(GDPC1_MILLESIME_2008)
    with pytest.raises(DataQualityError, match="deux fois"):
        build_vintage_panel({"2008-04-30": serie, dt.date(2008, 4, 30): serie})


def test_panneau_refuse_un_index_non_temporel() -> None:
    """Une série indexée par des entiers n'est pas un millésime."""
    with pytest.raises(DataQualityError, match="DatetimeIndex"):
        build_vintage_panel({dt.date(2008, 4, 30): pd.Series([1.0, 2.0], index=[0, 1])})


def test_panneau_vide() -> None:
    """Aucun millésime rend un panneau vide, mais au bon schéma."""
    panneau = build_vintage_panel({})
    assert panneau.empty
    assert tuple(panneau.columns) == PANEL_SCHEMA
    assert tuple(empty_panel().columns) == PANEL_SCHEMA


def test_panneau_dropna_retire_les_absences() -> None:
    """L'option retire les lignes sans valeur, et elles seules."""
    serie = parse_fred_csv(DGS10_FERIE)
    plein = build_vintage_panel({dt.date(2026, 9, 1): serie})
    net = build_vintage_panel({dt.date(2026, 9, 1): serie}, dropna=True)
    # Source (a) : six lignes dont une absence, donc cinq lignes après retrait.
    assert len(plein) == 6
    assert len(net) == 5


# ---------------------------------------------------------------------------
# as_of : le contrôle qui empêche la fuite
# ---------------------------------------------------------------------------


def test_as_of_rend_la_valeur_publiee_a_lepoque() -> None:
    """Au 30 juin 2008, le PIB du premier trimestre vaut 11 693,1 et rien d'autre."""
    connu = as_of(_panneau_gdp(), "2008-06-30")
    # Source (c) : estimation avancée publiée le 2008-04-30, mesurée le 2026-09-01.
    assert float(connu.loc[pd.Timestamp("2008-01-01"), VALUE]) == 11693.1
    assert connu.loc[pd.Timestamp("2008-01-01"), VINTAGE_DATE] == pd.Timestamp("2008-04-30")
    # Source (b) : aucun millésime rendu ne peut suivre la date demandée.
    assert bool((connu[VINTAGE_DATE] <= pd.Timestamp("2008-06-30")).all())


def test_as_of_aujourdhui_rend_la_valeur_revisee() -> None:
    """Au 1er septembre 2026, le même trimestre vaut 16 843,003."""
    connu = as_of(_panneau_gdp(), "2026-09-01")
    # Source (c) : millésime du 2026-08-01, mesuré le 2026-09-01.
    assert float(connu.loc[pd.Timestamp("2008-01-01"), VALUE]) == 16843.003


def test_as_of_inclut_le_millesime_du_jour_demande() -> None:
    """Le jour de la publication, la publication est connue : la borne est inclusive.

    C'est la borne que la formule écrit, ``max{ s : s <= d }``, et c'est celle
    qui décide du sort de la journée de publication. Une borne stricte ferait
    disparaître l'estimation avancée du 30 avril 2008 pour qui interroge le
    30 avril 2008, et rendrait un tableau vide au lieu d'un chiffre publié.
    """
    connu = as_of(_panneau_gdp(), "2008-04-30")
    # Source (c) : estimation avancée publiée ce jour-là, mesurée le 2026-09-01.
    assert float(connu.loc[pd.Timestamp("2008-01-01"), VALUE]) == 11693.1
    assert connu.loc[pd.Timestamp("2008-01-01"), VINTAGE_DATE] == pd.Timestamp("2008-04-30")
    # Source (a) : la veille, rien n'est encore publié, donc le tableau est vide.
    assert as_of(_panneau_gdp(), "2008-04-29").empty


def test_as_of_avant_le_premier_millesime_rend_vide() -> None:
    """Avant toute publication, rien n'était connu, et le tableau est vide."""
    connu = as_of(_panneau_gdp(), "2007-01-01")
    assert connu.empty
    assert list(connu.columns) == [VALUE, VINTAGE_DATE]


def test_as_of_respecte_une_valeur_retiree() -> None:
    """Si le dernier millésime retire une valeur, as_of rend l'absence, pas l'ancienne valeur.

    Ce test garde contre un piège précis : une agrégation qui saute les valeurs
    absentes rendrait la publication précédente, donc une information que la
    source a cessé d'annoncer.
    """
    ancien = pd.Series([1.5], index=pd.DatetimeIndex(["2020-01-02"]), name="X")
    recent = pd.Series([float("nan")], index=pd.DatetimeIndex(["2020-01-02"]), name="X")
    panneau = build_vintage_panel({dt.date(2020, 2, 1): ancien, dt.date(2020, 3, 1): recent})
    connu = as_of(panneau, "2020-03-15")
    # Source (b) : la valeur connue au 15 mars est celle du millésime du 1er mars,
    # quelle qu'elle soit, et celle-ci est absente.
    assert bool(connu[VALUE].isna().all())
    assert connu.loc[pd.Timestamp("2020-01-02"), VINTAGE_DATE] == pd.Timestamp("2020-03-01")


def test_as_of_garde_la_derniere_valeur_dune_observation_non_reprise() -> None:
    """Un millésime qui cesse de lister une observation ne l'efface pas.

    La distinction porte sur deux gestes différents de la source. Publier une
    valeur absente dit « ce point n'existe plus ». Ne plus lister la ligne du
    tout dit seulement que le fichier s'arrête ailleurs, par exemple parce que
    la fenêtre demandée a changé. Le second cas laisse donc la dernière valeur
    publiée en place, ce que la définition de l'ensemble des millésimes écrit.
    """
    ancien = pd.Series(
        [1.0, 2.0], index=pd.DatetimeIndex(["2020-01-01", "2020-02-01"]), name="X", dtype="float64"
    )
    recent = pd.Series([3.0], index=pd.DatetimeIndex(["2020-01-01"]), name="X", dtype="float64")
    panneau = build_vintage_panel({dt.date(2020, 3, 1): ancien, dt.date(2020, 4, 1): recent})
    connu = as_of(panneau, "2020-05-01")
    # Source (a) : trois lignes au panneau, deux observations distinctes, donc
    # deux lignes rendues.
    assert len(connu) == 2
    # Source (b) : février n'est repris par aucun millésime postérieur, donc sa
    # dernière publication reste celle du 1er mars.
    assert float(connu.loc[pd.Timestamp("2020-02-01"), VALUE]) == 2.0
    assert connu.loc[pd.Timestamp("2020-02-01"), VINTAGE_DATE] == pd.Timestamp("2020-03-01")
    # Source (b) : janvier est repris, donc c'est la révision qui parle.
    assert float(connu.loc[pd.Timestamp("2020-01-01"), VALUE]) == 3.0


def test_as_of_refuse_un_panneau_incomplet() -> None:
    """Un tableau sans les colonnes du schéma n'est pas un panneau."""
    with pytest.raises(DataQualityError, match="colonnes"):
        as_of(pd.DataFrame({"a": [1]}), "2020-01-01")


def test_fuite_des_revisions_sur_le_pib_de_2008() -> None:
    """La règle « acheter quand le PIB accélère » change de signe selon le millésime.

    C'est l'exemple documenté par le module, refait ici sur les extraits mesurés.
    """
    panneau = _panneau_gdp()
    a_lepoque = as_of(panneau, "2008-06-30")[VALUE]
    aujourdhui = as_of(panneau, "2026-09-01")[VALUE]

    t1_2008 = pd.Timestamp("2008-01-01")
    t4_2007 = pd.Timestamp("2007-10-01")
    t3_2007 = pd.Timestamp("2007-07-01")

    # Source (a) : 11693,1 / 11675,7 = 1,0014903 ; à la puissance 4, 1,0059744 ;
    # soit +0,5974 %. Et 11675,7 / 11658,9 = 1,0014410 ; à la puissance 4,
    # 1,0057763 ; soit +0,5776 %. La tolérance vaut un dix-millième de point,
    # donc l'arithmétique du commentaire porte le test.
    croissance_vue_en_2008 = _croissance_annualisee(a_lepoque[t1_2008], a_lepoque[t4_2007])
    precedente_vue_en_2008 = _croissance_annualisee(a_lepoque[t4_2007], a_lepoque[t3_2007])
    assert croissance_vue_en_2008 == pytest.approx(0.5974, abs=1e-4)
    assert precedente_vue_en_2008 == pytest.approx(0.5776, abs=1e-4)
    # La règle achète : la croissance accélère de 0,58 % à 0,60 %.
    assert croissance_vue_en_2008 > precedente_vue_en_2008

    # Source (a) : 16843,003 / 16915,191 = 0,9957324 ; à la puissance 4,
    # 0,9830384 ; soit -1,6962 %. Et 16915,191 / 16809,587 = 1,0062824 ;
    # à la puissance 4, 1,0253673 ; soit +2,5367 %.
    croissance_revisee = _croissance_annualisee(aujourdhui[t1_2008], aujourdhui[t4_2007])
    precedente_revisee = _croissance_annualisee(aujourdhui[t4_2007], aujourdhui[t3_2007])
    assert croissance_revisee == pytest.approx(-1.6962, abs=1e-4)
    assert precedente_revisee == pytest.approx(2.5367, abs=1e-4)
    # La règle n'achète pas : la croissance décélère de +2,54 % à -1,70 %.
    assert croissance_revisee < precedente_revisee

    # Source (b) : le signe du signal s'inverse entre les deux jeux, ce qui est
    # la définition opérationnelle de la fuite.
    assert (croissance_vue_en_2008 > precedente_vue_en_2008) is not (croissance_revisee > precedente_revisee)


def test_check_vintage_ordering_leve_sur_une_observation_future() -> None:
    """Une observation datée après sa publication signale un panneau mal assemblé."""
    panneau = build_vintage_panel(
        {dt.date(2008, 1, 1): pd.Series([1.0], index=pd.DatetimeIndex(["2008-06-30"]), name="X")}
    )
    with pytest.raises(LookAheadError, match="millésime"):
        check_vintage_ordering(panneau)


def test_check_vintage_ordering_accepte_le_datage_de_fred() -> None:
    """Un trimestre daté du 1er janvier et publié le 30 avril passe le contrôle."""
    check_vintage_ordering(_panneau_gdp())
    check_vintage_ordering(empty_panel())


def test_check_vintage_ordering_accepte_une_publication_le_jour_meme() -> None:
    """Une observation datée du jour de sa publication ne devance rien.

    C'est la borne du contrôle : l'écart vaut zéro jour, et zéro ne dépasse pas
    la tolérance par défaut, elle aussi de zéro jour.
    """
    meme_jour = build_vintage_panel(
        {dt.date(2020, 3, 2): pd.Series([1.0], index=pd.DatetimeIndex(["2020-03-02"]), name="X")}
    )
    # Source (a) : 2020-03-02 moins 2020-03-02 fait 0 jour, et 0 > 0 est faux.
    check_vintage_ordering(meme_jour)
    # Source (a) : un jour d'avance dépasse la tolérance nulle, mais pas une
    # tolérance d'un jour.
    veille = build_vintage_panel(
        {dt.date(2020, 3, 2): pd.Series([1.0], index=pd.DatetimeIndex(["2020-03-03"]), name="X")}
    )
    with pytest.raises(LookAheadError):
        check_vintage_ordering(veille)
    check_vintage_ordering(veille, tolerance_days=1)


# ---------------------------------------------------------------------------
# VintagePanel
# ---------------------------------------------------------------------------


def test_vintage_panel_tient_le_protocole() -> None:
    """La classe satisfait le protocole point-in-time du laboratoire."""
    panneau = VintagePanel("GDPC1", _panneau_gdp())
    assert isinstance(panneau, PointInTimeDataset)
    assert float(panneau.as_of("2008-06-30").loc[pd.Timestamp("2008-01-01"), VALUE]) == 11693.1


def test_vintage_panel_revisions() -> None:
    """La suite des publications d'un même trimestre se lit dans l'ordre des millésimes."""
    revisions = VintagePanel("GDPC1", _panneau_gdp()).revisions("2008-01-01")
    # Source (c) : les deux valeurs mesurées, dans l'ordre des millésimes.
    assert revisions.index.tolist() == [pd.Timestamp("2008-04-30"), pd.Timestamp("2026-08-01")]
    assert revisions.tolist() == [11693.1, 16843.003]


def test_vintage_panel_dates() -> None:
    """Les dates de millésime et d'observation se rendent triées et sans doublon."""
    panneau = VintagePanel("GDPC1", _panneau_gdp())
    assert panneau.vintage_dates == (dt.date(2008, 4, 30), dt.date(2026, 8, 1))
    # Source (a) : trois trimestres distincts dans les deux millésimes.
    assert len(panneau.observation_dates) == 3
    vide = VintagePanel("X", empty_panel())
    assert vide.vintage_dates == ()
    assert len(vide.observation_dates) == 0


# ---------------------------------------------------------------------------
# Propriétés, avec hypothesis
# ---------------------------------------------------------------------------


@st.composite
def panneaux(draw: st.DrawFn) -> pd.DataFrame:
    """Tire un panneau de millésimes : quelques observations, quelques millésimes."""
    n_obs = draw(st.integers(min_value=1, max_value=5))
    n_vintages = draw(st.integers(min_value=1, max_value=4))
    origine = dt.date(2000, 1, 1)
    jours_obs = sorted(draw(st.lists(st.integers(0, 400), min_size=n_obs, max_size=n_obs, unique=True)))
    jours_vin = sorted(
        draw(st.lists(st.integers(401, 900), min_size=n_vintages, max_size=n_vintages, unique=True))
    )
    index = pd.DatetimeIndex([origine + dt.timedelta(days=j) for j in jours_obs])
    millesimes: dict[dt.date | str, pd.Series] = {}
    for rang, jour in enumerate(jours_vin):
        valeurs = draw(
            st.lists(
                st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
                min_size=n_obs,
                max_size=n_obs,
            )
        )
        millesimes[origine + dt.timedelta(days=jour)] = pd.Series(
            valeurs, index=index, name=f"S{rang}", dtype="float64"
        )
    return build_vintage_panel(millesimes)


@given(panneau=panneaux(), decalage=st.integers(min_value=-100, max_value=1000))
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_as_of_ne_devance_jamais_la_date(panneau: pd.DataFrame, decalage: int) -> None:
    """Aucun millésime rendu ne suit la date demandée, quelle que soit la date.

    Source (b) : c'est la définition même de l'information disponible à une date.
    """
    date = dt.date(2000, 1, 1) + dt.timedelta(days=decalage)
    connu = as_of(panneau, date)
    if connu.empty:
        return
    assert bool((connu[VINTAGE_DATE] <= pd.Timestamp(date)).all())
    # Source (b) : une observation rendue une seule fois, par son dernier millésime.
    assert connu.index.is_unique


@given(
    panneau=panneaux(),
    premier=st.integers(min_value=0, max_value=1000),
    ecart=st.integers(min_value=0, max_value=500),
)
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propriete_as_of_est_monotone(panneau: pd.DataFrame, premier: int, ecart: int) -> None:
    """Se placer plus tard ne rend jamais un millésime plus ancien.

    Source (b) : l'information disponible croît avec le temps, donc le millésime
    retenu pour une observation donnée est une fonction croissante de la date.
    """
    origine = dt.date(2000, 1, 1)
    tot = as_of(panneau, origine + dt.timedelta(days=premier))
    tard = as_of(panneau, origine + dt.timedelta(days=premier + ecart))
    if tot.empty:
        return
    communes = tot.index.intersection(tard.index)
    assert len(communes) == len(tot.index)
    assert bool((tard.loc[communes, VINTAGE_DATE] >= tot.loc[communes, VINTAGE_DATE]).all())


# ---------------------------------------------------------------------------
# Les fournisseurs, hors réseau
# ---------------------------------------------------------------------------


def test_fred_provider_hors_reseau(tmp_path: Path) -> None:
    """Le fournisseur analyse la réponse, borne la fenêtre et écrit le brut."""
    fournisseur, client = _fred(tmp_path, {"DGS10|": DGS10_DEBUT})
    tableau = fournisseur.fetch("dgs10", start="1962-01-03", end="1962-01-05")

    # Source (a) : trois lignes du 3 au 5 janvier 1962 dans l'extrait mesuré.
    assert list(tableau.columns) == ["DGS10"]
    assert len(tableau) == 3
    assert float(tableau.iloc[0, 0]) == 4.03
    # Source (a) : les bornes demandées sont envoyées à la source.
    assert client.calls[0]["params"] == {
        "id": "DGS10",
        "cosd": "1962-01-03",
        "coed": "1962-01-05",
    }
    # Source (b) : le brut est écrit avant tout parsage, donc un fichier existe.
    assert len(list(tmp_path.joinpath("fred").rglob("*.bin"))) == 1


def test_fred_provider_relit_le_cache(tmp_path: Path) -> None:
    """Un deuxième appel identique ne repart pas sur le réseau."""
    fournisseur, client = _fred(tmp_path, {"DGS10|": DGS10_DEBUT})
    fournisseur.fetch("DGS10")
    fournisseur.fetch("DGS10")
    # Source (b) : le cache brut rend la réponse, donc une seule requête.
    assert len(client.calls) == 1


def test_fred_provider_refuse_des_bornes_inversees(tmp_path: Path) -> None:
    """Une fenêtre qui se referme avant de s'ouvrir n'a pas de sens."""
    fournisseur, _ = _fred(tmp_path, {"DGS10|": DGS10_DEBUT})
    with pytest.raises(ValueError, match="suit end"):
        fournisseur.fetch("DGS10", start="2020-02-01", end="2020-01-01")


def test_fred_provider_fenetre_vide(tmp_path: Path) -> None:
    """Une fenêtre sans observation lève plutôt que de rendre un tableau vide."""
    fournisseur, _ = _fred(tmp_path, {"DGS10|": DGS10_DEBUT})
    with pytest.raises(InsufficientDataError):
        fournisseur.fetch("DGS10", start="1990-01-01", end="1990-12-31")


def test_alfred_provider_panneau_hors_reseau(tmp_path: Path) -> None:
    """Deux millésimes téléchargés forment le panneau attendu."""
    fournisseur, client = _alfred(
        tmp_path,
        {
            "GDPC1|2008-04-30": GDPC1_MILLESIME_2008,
            "GDPC1|2026-08-01": GDPC1_MILLESIME_2026,
        },
    )
    panneau = fournisseur.vintage_panel("GDPC1", ["2026-08-01", "2008-04-30"])

    # Source (a) : deux millésimes de trois trimestres font six lignes.
    assert len(panneau) == 6
    # Source (a) : un appel par millésime, avec la date en paramètre.
    assert [appel["params"]["vintage_date"] for appel in client.calls] == [
        "2008-04-30",
        "2026-08-01",
    ]
    # Source (c) : la valeur connue au 30 juin 2008 est l'estimation avancée.
    assert float(as_of(panneau, "2008-06-30").loc[pd.Timestamp("2008-01-01"), VALUE]) == 11693.1


def test_alfred_fetch_vintage_rend_une_serie(tmp_path: Path) -> None:
    """Un millésime seul rend une série nommée par l'identifiant."""
    fournisseur, _ = _alfred(tmp_path, {"GDPC1|2008-04-30": GDPC1_MILLESIME_2008})
    serie = fournisseur.fetch_vintage("GDPC1", dt.date(2008, 4, 30))
    # Source (c) : le dernier trimestre publié au 30 avril 2008.
    assert serie.name == "GDPC1"
    assert float(serie.iloc[-1]) == 11693.1


def test_alfred_fetch_passe_par_les_millesimes_demandes(tmp_path: Path) -> None:
    """La méthode du protocole rend le même panneau que l'appel nommé."""
    corps = {
        "GDPC1|2008-04-30": GDPC1_MILLESIME_2008,
        "GDPC1|2026-08-01": GDPC1_MILLESIME_2026,
    }
    fournisseur, _ = _alfred(tmp_path, corps)
    par_protocole = fournisseur.fetch("GDPC1", vintage_dates=["2008-04-30", "2026-08-01"])
    autre, _ = _alfred(tmp_path / "bis", corps)
    par_nom = autre.vintage_panel("GDPC1", ["2008-04-30", "2026-08-01"])
    # Source (b) : les deux chemins décrivent le même assemblage, donc le même
    # tableau ligne pour ligne.
    pd.testing.assert_frame_equal(par_protocole, par_nom)


def test_combine_checksums_est_reproductible_et_sensible() -> None:
    """L'empreinte d'un assemblage est stable, dépend de l'ordre, et change avec son contenu."""
    a, b = "a" * 64, "b" * 64
    # Source (d) : hashlib sur la chaîne que la docstring décrit.
    assert combine_checksums([a, b]) == hashlib.sha256(f"{a}|{b}".encode()).hexdigest()
    # Source (b) : une fonction rend deux fois la même chose sur la même entrée.
    assert combine_checksums([a, b]) == combine_checksums([a, b])
    # Source (b) : l'ordre fait partie de l'assemblage, donc il change l'empreinte.
    assert combine_checksums([a, b]) != combine_checksums([b, a])
    # Source (b) : changer un seul millésime change l'empreinte du tout.
    assert combine_checksums([a, b]) != combine_checksums([a, "c" * 64])
    # Source (a) : SHA-256 rend 256 bits, donc 64 caractères hexadécimaux.
    assert len(combine_checksums([a, b])) == 64
    # Source (b) : rien à assembler, rien à déclarer, plutôt qu'une empreinte
    # du vide qui passerait pour une empreinte de contenu.
    assert combine_checksums([]) == ""
    assert combine_checksums(["", ""]) == ""


def test_alfred_refuse_une_liste_vide(tmp_path: Path) -> None:
    """Un panneau sans millésime n'existe pas."""
    fournisseur, _ = _alfred(tmp_path, {})
    with pytest.raises(ValueError, match="aucune date de millésime"):
        fournisseur.vintage_panel("GDPC1", [])


# ---------------------------------------------------------------------------
# Les manifestes : la seule différence qui compte
# ---------------------------------------------------------------------------


def test_manifeste_fred_nest_pas_point_in_time(tmp_path: Path) -> None:
    """FRED déclare faux, parce qu'il ne sait pas ce qu'il disait hier."""
    fournisseur, _ = _fred(tmp_path, {"DGS10|": DGS10_DEBUT})
    fournisseur.fetch("DGS10")
    manifeste = fournisseur.manifest()
    # Source (c) : contrat du module, et propriété de la source.
    assert manifeste.point_in_time is False
    assert manifeste.dataset_id == "fred-dgs10"
    assert manifeste.columns == ("DGS10",)
    # Source (c) : première et dernière observation de l'extrait mesuré.
    assert manifeste.data_start == dt.date(1962, 1, 2)
    assert manifeste.data_end == dt.date(1962, 1, 8)
    assert manifeste.frequency is Frequency.DAILY
    assert manifeste.adjusted is False
    assert manifeste.survivorship_free is None
    assert len(manifeste.checksum_sha256) == 64


def test_manifeste_alfred_est_point_in_time(tmp_path: Path) -> None:
    """ALFRED déclare vrai, et c'est toute la différence entre les deux."""
    fournisseur, _ = _alfred(
        tmp_path,
        {
            "GDPC1|2008-04-30": GDPC1_MILLESIME_2008,
            "GDPC1|2026-08-01": GDPC1_MILLESIME_2026,
        },
    )
    fournisseur.vintage_panel("GDPC1", ["2008-04-30", "2026-08-01"])
    manifeste = fournisseur.manifest()
    assert manifeste.point_in_time is True
    assert manifeste.dataset_id == "alfred-gdpc1-2v"
    assert manifeste.columns == PANEL_SCHEMA
    # Source (a) : six lignes dans le panneau, comme au test de forme.
    assert manifeste.n_rows == 6
    assert "2008-04-30" in manifeste.notes


def test_manifeste_du_panneau_declare_une_frequence_trimestrielle(tmp_path: Path) -> None:
    """Un panneau de PIB est trimestriel, même vu deux fois par ses deux millésimes.

    Le panneau répète chaque trimestre une fois par millésime. Déduire la
    fréquence de cette colonne donne un écart médian nul, donc « quotidien »,
    et le manifeste annoncerait une série quotidienne là où la source publie
    quatre points par an.
    """
    fournisseur, _ = _alfred(
        tmp_path,
        {
            "GDPC1|2008-04-30": GDPC1_MILLESIME_2008,
            "GDPC1|2026-08-01": GDPC1_MILLESIME_2026,
        },
    )
    fournisseur.vintage_panel("GDPC1", ["2008-04-30", "2026-08-01"])
    manifeste = fournisseur.manifest()
    # Source (a) : trois trimestres distincts, écarts de 92 et 92 jours,
    # médiane 92, comprise entre les bornes 45 et 135.
    assert manifeste.frequency is Frequency.QUARTERLY
    # Source (c) : premier et dernier trimestre des extraits mesurés.
    assert manifeste.data_start == dt.date(2007, 7, 1)
    assert manifeste.data_end == dt.date(2008, 1, 1)


def test_manifeste_du_panneau_porte_lempreinte_des_millesimes(tmp_path: Path) -> None:
    """L'empreinte du panneau se recalcule depuis les octets des deux millésimes."""
    fournisseur, _ = _alfred(
        tmp_path,
        {
            "GDPC1|2008-04-30": GDPC1_MILLESIME_2008,
            "GDPC1|2026-08-01": GDPC1_MILLESIME_2026,
        },
    )
    fournisseur.vintage_panel("GDPC1", ["2008-04-30", "2026-08-01"])
    # Source (d) : hashlib appliqué aux deux corps de réponse, dans l'ordre des
    # millésimes, sans passer par le module testé.
    digests = [
        hashlib.sha256(GDPC1_MILLESIME_2008.encode("utf-8")).hexdigest(),
        hashlib.sha256(GDPC1_MILLESIME_2026.encode("utf-8")).hexdigest(),
    ]
    attendu = hashlib.sha256("|".join(digests).encode("utf-8")).hexdigest()
    assert fournisseur.manifest().checksum_sha256 == attendu


def test_manifeste_dun_millesime_seul(tmp_path: Path) -> None:
    """Un millésime seul se décrit aussi, avec sa fréquence trimestrielle."""
    fournisseur, _ = _alfred(tmp_path, {"GDPC1|2008-04-30": GDPC1_MILLESIME_2008})
    fournisseur.fetch_vintage("GDPC1", "2008-04-30")
    manifeste = fournisseur.manifest()
    # Source (a) : trois trimestres consécutifs, écart médian 91 jours.
    assert manifeste.frequency is Frequency.QUARTERLY
    assert manifeste.point_in_time is True


def test_manifeste_sans_telechargement_leve(tmp_path: Path) -> None:
    """Décrire une extraction qui n'a pas eu lieu est une erreur de configuration."""
    fournisseur, _ = _fred(tmp_path, {})
    with pytest.raises(ConfigError, match="téléchargement préalable"):
        fournisseur.manifest()


def test_manifeste_refuse_une_cle_inconnue(tmp_path: Path) -> None:
    """Une faute de frappe dans un remplacement ne passe pas en silence."""
    fournisseur, _ = _fred(tmp_path, {"DGS10|": DGS10_DEBUT})
    fournisseur.fetch("DGS10")
    with pytest.raises(ValueError, match="inconnues"):
        fournisseur.manifest(serie_id="DGS10")


def test_les_deux_fournisseurs_tiennent_le_protocole(tmp_path: Path) -> None:
    """Les deux classes satisfont le protocole de fournisseur de données."""
    fred, _ = _fred(tmp_path, {})
    alfred, _ = _alfred(tmp_path, {})
    assert isinstance(fred, DataProvider)
    assert isinstance(alfred, DataProvider)
    assert fred.name == "fred"
    assert alfred.name == "alfred"


# ---------------------------------------------------------------------------
# Réseau, exclu de l'intégration continue
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_reseau_premiere_observation_de_dgs10(tmp_path: Path) -> None:
    """La première observation publiée de DGS10 vaut 4,06 le 2 janvier 1962."""
    tableau = FredProvider(raw_root=tmp_path).fetch("DGS10", end="1962-01-31")
    # Source (c) : mesuré le 2026-09-01 sur fredgraph.csv?id=DGS10.
    assert tableau.index[0] == pd.Timestamp("1962-01-02")
    assert float(tableau.iloc[0, 0]) == 4.06


@pytest.mark.network
def test_reseau_deux_millesimes_du_pib(tmp_path: Path) -> None:
    """Le PIB du premier trimestre 2008 vaut 11 693,1 en avril 2008 et 16 843,003 en août 2026."""
    fournisseur = AlfredProvider(raw_root=tmp_path)
    panneau = fournisseur.vintage_panel(
        "GDPC1", ["2008-04-30", "2026-08-01"], start="2007-07-01", end="2008-01-01"
    )
    revisions = VintagePanel("GDPC1", panneau).revisions("2008-01-01")
    # Source (c) : les deux millésimes mesurés le 2026-09-01.
    assert revisions.tolist() == [11693.1, 16843.003]
    assert fournisseur.manifest().point_in_time is True
