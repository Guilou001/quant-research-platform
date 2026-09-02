"""Contrôles du module ``quantlab.reporting.study``.

Règle 10 du laboratoire, appliquée sans exception : aucune valeur attendue ne
vient de la sortie du code. Chaque test dit d'où sort la sienne, parmi quatre
sources.

(a) un calcul à la main, écrit dans le commentaire, chiffres visibles ;
(b) une identité mathématique ou la définition écrite dans la spécification ;
(c) une valeur publiée, citée ;
(d) une implémentation indépendante sur le même intrant.

Le cœur du fichier est la table des huit frontières de verdict. Chaque jeu de
preuves est écrit à la main, un seul critère est dégradé à la fois, et le
verdict attendu se lit dans la définition de l'échelle et non dans le code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from quantlab.core.errors import ConfigError
from quantlab.core.types import CostBasis, SampleTag, Verdict
from quantlab.reporting.study import (
    DEFAULT_MAX_PBO,
    DEFAULT_MAX_PORTFOLIO_CORRELATION,
    DEFAULT_MIN_COST_MULTIPLE,
    DEFAULT_MIN_DSR,
    DEFAULT_MIN_OOS_SHARPE,
    DEFAULT_MIN_POSITIVE_SUBPERIOD_SHARE,
    DEFAULT_MIN_TSTAT,
    DEFAULT_REPLICATION_TOLERANCE,
    REPORT_SECTIONS,
    VERDICT_LADDER,
    MetricLabel,
    ReplicationCheck,
    ReportFigure,
    ReportTable,
    StudyReport,
    VerdictCriteria,
    VerdictEvidence,
    decide_verdict,
    generate_report,
    metrics_table,
    replication_table,
    section_keys,
)

# --------------------------------------------------------------------------- #
# Les briques écrites à la main
# --------------------------------------------------------------------------- #

#: Le contrôle de réplication de référence. Valeur publiée 0,80, la nôtre 0,74.
#: Écart absolu 0,06 et écart relatif 0,06 / 0,80 = 0,075, calculés à la main.
#: La tolérance par défaut vaut 0,10, donc ce contrôle passe.
CHECK_QUI_PASSE = ReplicationCheck(
    quantity="ratio de Sharpe du facteur",
    published=0.80,
    ours=0.74,
    source="table 2, page 12",
)

#: Le même contrôle dégradé. Valeur publiée 0,80, la nôtre 0,50. Écart absolu
#: 0,30 et écart relatif 0,30 / 0,80 = 0,375, calculés à la main. La tolérance
#: vaut 0,10, donc ce contrôle échoue.
CHECK_QUI_ECHOUE = ReplicationCheck(
    quantity="ratio de Sharpe du facteur",
    published=0.80,
    ours=0.50,
    source="table 2, page 12",
)


def _preuves_completes(**derogations: object) -> VerdictEvidence:
    """Rend une preuve qui passe tous les critères, sauf les dérogations.

    Les valeurs de base sont posées au-dessus des seuils par défaut, avec de la
    marge, pour qu'un test qui dégrade un seul critère isole bien ce critère.
    """
    base: dict[str, object] = {
        "hypothesis_supported": True,
        "replication_checks": (CHECK_QUI_PASSE,),
        # 0,70 contre un minimum de 0,50.
        "oos_sharpe": 0.70,
        # 3,40 contre un minimum de 3,00, seuil de Harvey, Liu et Zhu (2016).
        "tstat_after_multiplicity": 3.40,
        # 0,97 contre un minimum de 0,95.
        "deflated_sharpe": 0.97,
        # 0,20 contre un maximum de 0,50.
        "pbo": 0.20,
        # 0,75 contre un minimum de 0,60.
        "positive_subperiod_share": 0.75,
        # 3,0 contre un minimum de 2,0.
        "surviving_cost_multiple": 3.0,
        # 0,30 contre un maximum de 0,60.
        "portfolio_correlation": 0.30,
    }
    base.update(derogations)
    return VerdictEvidence(**base)  # type: ignore[arg-type]


def _raison(raisons: list[str], fragment: str) -> str:
    """Rend l'unique raison qui contient le fragment demandé."""
    trouvees = [r for r in raisons if fragment in r]
    assert len(trouvees) == 1, f"« {fragment} » attendu une fois, trouvé {len(trouvees)} fois"
    return trouvees[0]


# --------------------------------------------------------------------------- #
# ReplicationCheck : l'écart calculé à la main
# --------------------------------------------------------------------------- #


def test_ecart_relatif_calcule_a_la_main() -> None:
    """L'écart d'un contrôle se calcule à la main, sans lire le code.

    Source (a). Valeur publiée 0,80, la nôtre 0,74. La soustraction donne
    0,74 moins 0,80, soit -0,06, et sa valeur absolue 0,06. La division par
    0,80 donne 0,075, c'est-à-dire 7,5 %.
    """
    check = ReplicationCheck(quantity="Sharpe", published=0.80, ours=0.74)
    assert check.absolute_error == pytest.approx(0.06, abs=1e-12)
    assert check.relative_error == pytest.approx(0.075, abs=1e-12)
    # La tolérance par défaut vaut 0,10, et 0,075 est plus petit.
    assert check.passed is True
    assert check.verdict == "répliqué"
    # À 5 % de tolérance, 0,075 dépasse, donc le contrôle échoue.
    serre = ReplicationCheck(quantity="Sharpe", published=0.80, ours=0.74, tolerance=0.05)
    assert serre.passed is False
    assert serre.verdict == "écart"


def test_tolerance_absolue_pour_une_valeur_publiee_nulle() -> None:
    """Un alpha publié nul se contrôle en absolu, jamais en relatif.

    Source (b). L'écart relatif divise par la valeur publiée : à zéro, le
    quotient n'existe pas et vaut l'infini par convention du module.
    """
    relatif = ReplicationCheck(quantity="alpha", published=0.0, ours=0.001)
    assert relatif.relative_error == float("inf")
    assert relatif.passed is False
    # En absolu, 0,001 tient dans une tolérance de 0,002 posée à la main.
    absolu = ReplicationCheck(
        quantity="alpha", published=0.0, ours=0.001, tolerance=0.002, tolerance_kind="absolute"
    )
    assert absolu.absolute_error == pytest.approx(0.001, abs=1e-15)
    assert absolu.passed is True


def test_un_controle_sans_nom_ou_a_tolerance_negative_leve() -> None:
    """Un contrôle anonyme ou à tolérance négative ne se construit pas."""
    with pytest.raises(ConfigError):
        ReplicationCheck(quantity="   ", published=1.0, ours=1.0)
    with pytest.raises(ConfigError):
        ReplicationCheck(quantity="Sharpe", published=1.0, ours=1.0, tolerance=-0.01)


def test_tableau_de_replication() -> None:
    """Le tableau papier contre réplication porte ses neuf colonnes.

    Source (a) pour les nombres, repris du test précédent : 0,06 et 0,075.
    """
    table = replication_table([CHECK_QUI_PASSE, CHECK_QUI_ECHOUE])
    assert list(table.columns) == [
        "quantity",
        "published",
        "ours",
        "absolute_error",
        "relative_error",
        "tolerance",
        "tolerance_kind",
        "verdict",
        "source",
    ]
    assert len(table) == 2
    assert float(table.loc[0, "relative_error"]) == pytest.approx(0.075, abs=1e-12)
    # 0,30 / 0,80 = 0,375, calculé à la main.
    assert float(table.loc[1, "relative_error"]) == pytest.approx(0.375, abs=1e-12)
    assert list(table["verdict"]) == ["répliqué", "écart"]


def test_tableau_de_replication_vide_garde_ses_colonnes() -> None:
    """Cas limite : aucune ligne, mais le tableau reste écrivable."""
    table = replication_table([])
    assert len(table) == 0
    assert "relative_error" in table.columns


# --------------------------------------------------------------------------- #
# Les huit frontières de verdict
# --------------------------------------------------------------------------- #


def test_frontiere_1_rejet_par_le_signe_de_l_hypothese() -> None:
    """Le signe économique attendu manque, donc l'étude est rejetée.

    Source (b), la définition de l'échelle : ``REJECTED`` veut dire que
    l'hypothèse ne survit pas aux données. Tous les autres critères passent, et
    ils ne rachètent rien.
    """
    verdict, raisons = decide_verdict(_preuves_completes(hypothesis_supported=False))
    assert verdict is Verdict.REJECTED
    assert _raison(raisons, "hypothèse économique").startswith("ÉCHOUÉ")
    assert _raison(raisons, "signe attendu NON retrouvé")
    # Les raisons restent complètes : le rapport montre aussi ce qui passait.
    assert _raison(raisons, "Sharpe dégonflé").startswith("RÉUSSI")
    assert raisons[-1] == "VERDICT | REJECTED"


def test_frontiere_2_rejet_par_un_sharpe_hors_echantillon_negatif() -> None:
    """Un Sharpe hors échantillon négatif réfute, il ne met pas en attente.

    Source (b). Le seuil de rejet vaut 0,000 et la mesure vaut -0,300, donc la
    raison porte « -0,300 mesuré, rejet à 0,000 ou moins ».
    """
    verdict, raisons = decide_verdict(_preuves_completes(oos_sharpe=-0.30))
    assert verdict is Verdict.REJECTED
    ligne = _raison(raisons, "signe du Sharpe hors échantillon")
    assert ligne == "ÉCHOUÉ | signe du Sharpe hors échantillon : -0,300 mesuré, rejet à 0,000 ou moins"


def test_frontiere_3_experimental_faute_de_controle_de_replication() -> None:
    """Sans un seul chiffre confronté à l'article, l'étude reste expérimentale.

    Source (b). ``REPLICATED`` exige des contrôles chiffrés ; il n'y en a aucun.
    """
    verdict, raisons = decide_verdict(_preuves_completes(replication_checks=()))
    assert verdict is Verdict.EXPERIMENTAL
    assert _raison(raisons, "aucun contrôle chiffré fourni").startswith("ÉCHOUÉ")


def test_frontiere_4_experimental_par_un_controle_hors_tolerance() -> None:
    """Un contrôle à 37,5 % d'écart bloque la réplication.

    Source (a) pour l'écart : 0,50 contre 0,80 publié, soit 0,30 / 0,80 =
    0,375, à comparer à la tolérance de 0,100.
    """
    verdict, raisons = decide_verdict(_preuves_completes(replication_checks=(CHECK_QUI_ECHOUE,)))
    assert verdict is Verdict.EXPERIMENTAL
    ligne = _raison(raisons, "réplication de « ratio de Sharpe du facteur »")
    assert ligne.startswith("ÉCHOUÉ")
    assert "0,500 contre 0,800 publié" in ligne
    assert "écart relatif 0,375" in ligne
    assert "tolérance 0,100" in ligne
    assert _raison(raisons, "0 contrôle(s) sur 1").startswith("ÉCHOUÉ")


def test_frontiere_5_replique_par_une_probabilite_de_surapprentissage_trop_haute() -> None:
    """Une PBO de 0,70 arrête l'étude à ``REPLICATED``.

    Source (c) pour le seuil : Bailey, Borwein, Lopez de Prado et Zhu (2017)
    retiennent 0,5. La mesure de 0,70 le dépasse, donc la robustesse échoue.
    """
    verdict, raisons = decide_verdict(_preuves_completes(pbo=0.70))
    assert verdict is Verdict.REPLICATED
    ligne = _raison(raisons, "probabilité de surapprentissage")
    assert ligne == "ÉCHOUÉ | probabilité de surapprentissage : 0,700 mesuré, maximum 0,500"
    # La réplication, elle, a bien passé.
    assert _raison(raisons, "1 contrôle(s) sur 1").startswith("RÉUSSI")


def test_frontiere_6_replique_par_un_sharpe_hors_echantillon_insuffisant() -> None:
    """Un Sharpe hors échantillon de 0,30 ne rejette pas, mais ne suffit pas.

    Source (b). 0,30 est au-dessus du seuil de rejet de 0,000, donc l'étude
    n'est pas rejetée. Il est sous le minimum de 0,500, donc elle n'est pas
    robuste.
    """
    verdict, raisons = decide_verdict(_preuves_completes(oos_sharpe=0.30))
    assert verdict is Verdict.REPLICATED
    assert _raison(raisons, "signe du Sharpe hors échantillon").startswith("RÉUSSI")
    assert "ÉCHOUÉ | Sharpe hors échantillon : 0,300 mesuré, minimum 0,500" in raisons


def test_frontiere_7_robuste_par_une_correlation_trop_haute() -> None:
    """Une corrélation de 0,85 avec le portefeuille détenu arrête à ``ROBUST``.

    Source (b). Le passage à ``PORTFOLIO_CANDIDATE`` exige un apport, et une
    stratégie corrélée à 0,85 répète ce qui est déjà détenu.
    """
    verdict, raisons = decide_verdict(_preuves_completes(portfolio_correlation=0.85))
    assert verdict is Verdict.ROBUST
    ligne = _raison(raisons, "corrélation absolue")
    assert ligne == (
        "ÉCHOUÉ | corrélation absolue avec le portefeuille existant : 0,850 mesurée, maximum 0,600"
    )


def test_frontiere_8_candidat_au_portefeuille() -> None:
    """Tous les critères passent, donc le plus haut verdict est atteint.

    Source (b). C'est le seul jeu de preuves du fichier où aucune raison ne
    porte la marque d'échec.
    """
    verdict, raisons = decide_verdict(_preuves_completes())
    assert verdict is Verdict.PORTFOLIO_CANDIDATE
    assert not [r for r in raisons if r.startswith("ÉCHOUÉ")]
    # Deux raisons de rejet, une par contrôle, une synthèse, six de robustesse,
    # une de corrélation et la ligne de verdict, soit 2 + 1 + 1 + 6 + 1 + 1.
    assert len(raisons) == 12


def test_une_correlation_negative_forte_bloque_aussi() -> None:
    """La corrélation se juge en valeur absolue, donc -0,85 bloque comme 0,85.

    Source (b). Une stratégie qui reproduit l'inverse du portefeuille détenu
    n'apporte pas une source de rendement de plus.
    """
    verdict, raisons = decide_verdict(_preuves_completes(portfolio_correlation=-0.85))
    assert verdict is Verdict.ROBUST
    assert "0,850 mesurée" in _raison(raisons, "corrélation absolue")


# --------------------------------------------------------------------------- #
# Ce qu'un beau Sharpe ne rachète pas
# --------------------------------------------------------------------------- #


def test_un_sharpe_superieur_a_un_ne_suffit_a_aucun_niveau() -> None:
    """Un Sharpe de 3,0 sans réplication reste ``EXPERIMENTAL``.

    Source (b), la règle écrite du laboratoire. Aucun seuil de Sharpe ne donne
    seul un verdict, et le test le vérifie au chiffre le plus flatteur.
    """
    verdict, _ = decide_verdict(_preuves_completes(oos_sharpe=3.0, replication_checks=()))
    assert verdict is Verdict.EXPERIMENTAL


def test_une_preuve_absente_fait_echouer_son_critere() -> None:
    """Un contrôle qui n'a pas tourné ne passe pas par défaut.

    Source (b). La preuve vaut ``None``, donc la raison porte « non mesuré » et
    le critère échoue, ce qui arrête l'étude à ``REPLICATED``.
    """
    verdict, raisons = decide_verdict(_preuves_completes(deflated_sharpe=None))
    assert verdict is Verdict.REPLICATED
    assert _raison(raisons, "Sharpe dégonflé") == ("ÉCHOUÉ | Sharpe dégonflé : non mesuré, minimum 0,950")


def test_une_tolerance_elargie_apres_coup_ne_replique_pas() -> None:
    """Un contrôle plus laxiste que la tolérance déclarée de l'étude échoue.

    Source (a). L'écart relatif vaut 0,375 et le contrôle se donne 0,50 de
    tolérance, donc il passe pour lui-même. La tolérance déclarée de l'étude
    vaut 0,10, donc le verdict refuse l'élargissement.
    """
    large = ReplicationCheck(quantity="Sharpe", published=0.80, ours=0.50, tolerance=0.50)
    assert large.passed is True
    verdict, raisons = decide_verdict(_preuves_completes(replication_checks=(large,)))
    assert verdict is Verdict.EXPERIMENTAL
    assert "plus large que la tolérance déclarée 0,100" in _raison(raisons, "réplication de « Sharpe »")


def test_les_seuils_se_configurent() -> None:
    """Des seuils plus permissifs changent le verdict, et se lisent.

    Source (b). En abaissant le minimum de Sharpe hors échantillon à 0,20, la
    mesure de 0,30 passe, et l'étude franchit le niveau de robustesse.
    """
    seuils = VerdictCriteria(min_oos_sharpe=0.20)
    verdict, raisons = decide_verdict(_preuves_completes(oos_sharpe=0.30), seuils)
    assert verdict is Verdict.PORTFOLIO_CANDIDATE
    assert "0,300 mesuré, minimum 0,200" in _raison(raisons, "RÉUSSI | Sharpe hors échantillon")


def test_les_seuils_par_defaut_sont_ceux_qui_sont_documentes() -> None:
    """Les valeurs par défaut du modèle sont celles des constantes publiées.

    Source (c) pour trois d'entre elles : 3,0 vient de Harvey, Liu et Zhu
    (2016), 0,95 de Bailey et Lopez de Prado (2014), 0,5 de Bailey, Borwein,
    Lopez de Prado et Zhu (2017).
    """
    seuils = VerdictCriteria()
    assert seuils.min_tstat == DEFAULT_MIN_TSTAT == 3.0
    assert seuils.min_dsr == DEFAULT_MIN_DSR == 0.95
    assert seuils.max_pbo == DEFAULT_MAX_PBO == 0.5
    assert seuils.replication_tolerance == DEFAULT_REPLICATION_TOLERANCE == 0.10
    assert seuils.min_oos_sharpe == DEFAULT_MIN_OOS_SHARPE == 0.5
    assert seuils.min_positive_subperiod_share == DEFAULT_MIN_POSITIVE_SUBPERIOD_SHARE == 0.60
    assert seuils.min_cost_multiple == DEFAULT_MIN_COST_MULTIPLE == 2.0
    assert seuils.max_portfolio_correlation == DEFAULT_MAX_PORTFOLIO_CORRELATION == 0.60


def test_un_seuil_inconnu_leve() -> None:
    """Une faute de frappe dans un seuil lève au lieu de passer inaperçue."""
    with pytest.raises(Exception, match=r"extra_forbidden|Extra inputs"):
        VerdictCriteria(min_oos_sharp=0.5)  # type: ignore[call-arg]


def test_l_echelle_a_cinq_barreaux_dans_l_ordre() -> None:
    """L'échelle des verdicts est celle du ``README``, dans l'ordre croissant."""
    assert VERDICT_LADDER == (
        Verdict.REJECTED,
        Verdict.EXPERIMENTAL,
        Verdict.REPLICATED,
        Verdict.ROBUST,
        Verdict.PORTFOLIO_CANDIDATE,
    )


# --------------------------------------------------------------------------- #
# Le tableau des métriques
# --------------------------------------------------------------------------- #


def test_metrics_table_porte_l_echantillon_et_la_base() -> None:
    """Chaque ligne du tableau porte son échantillon et sa base de coût.

    Source (b), la règle 5 du laboratoire. Le test vérifie les quatre colonnes
    et le report exact des deux étiquettes.
    """
    table = metrics_table(
        {"sharpe": 1.20, "max_drawdown": -0.35},
        {
            "sharpe": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
            "max_drawdown": (SampleTag.IN_SAMPLE, CostBasis.GROSS),
        },
    )
    assert list(table.columns) == ["metric", "value", "sample", "cost_basis"]
    assert list(table["sample"]) == ["OOS", "IS"]
    assert list(table["cost_basis"]) == ["net", "gross"]
    assert float(table.loc[0, "value"]) == pytest.approx(1.20, abs=1e-12)


def test_metrics_table_leve_sans_etiquette() -> None:
    """Une métrique sans étiquette ne s'écrit pas : la fonction lève."""
    with pytest.raises(ConfigError, match="étiquette d'échantillon"):
        metrics_table(
            {"sharpe": 1.20, "calmar": 0.4},
            {"sharpe": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET)},
        )


def test_metrics_table_leve_sur_une_etiquette_orpheline() -> None:
    """Une étiquette sans métrique signale une faute de frappe, donc lève."""
    with pytest.raises(ConfigError, match="aucune métrique"):
        metrics_table(
            {"sharpe": 1.20},
            {
                "sharpe": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET),
                "sharp": MetricLabel(SampleTag.IN_SAMPLE, CostBasis.GROSS),
            },
        )


def test_metrics_table_leve_sur_une_etiquette_illisible() -> None:
    """Une étiquette qui ne porte pas les deux mentions lève."""
    with pytest.raises(ConfigError, match="illisible"):
        metrics_table({"sharpe": 1.20}, {"sharpe": SampleTag.OUT_OF_SAMPLE})  # type: ignore[dict-item]


def test_metrics_table_vide() -> None:
    """Cas limite : aucune métrique, le tableau garde ses quatre colonnes."""
    table = metrics_table({}, {})
    assert len(table) == 0
    assert list(table.columns) == ["metric", "value", "sample", "cost_basis"]


# --------------------------------------------------------------------------- #
# Le rapport écrit
# --------------------------------------------------------------------------- #


@pytest.fixture
def figure_png(tmp_path: Path) -> Path:
    """Écrit une image minimale sur disque et rend son chemin.

    Le contenu n'est jamais décodé par le module, qui se borne à recopier le
    fichier. Huit octets suffisent donc à jouer le rôle d'une figure.
    """
    chemin = tmp_path / "source" / "cumulative.png"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(b"\x89PNG\r\n\x1a\n")
    return chemin


@pytest.fixture
def rapport_complet(figure_png: Path) -> StudyReport:
    """Rend un rapport garni : métriques, tableau, figure et configuration."""
    return StudyReport(
        study_name="tsmom",
        experiment_id="exp-0123456789ab",
        hypothesis="Le rendement passé sur douze mois prédit le rendement du mois suivant.",
        paper="Moskowitz, Ooi et Pedersen (2012), Journal of Financial Economics 104(2).",
        evidence=_preuves_completes(),
        sections={
            "hypothesis": "La tendance persiste sur douze mois.",
            "limitations": "Aucun coût de marché intrajournalier n'est modélisé.",
        },
        metrics=metrics_table(
            {"sharpe": 0.70},
            {"sharpe": MetricLabel(SampleTag.OUT_OF_SAMPLE, CostBasis.NET)},
        ),
        tables=(
            ReportTable(
                name="sous_periodes",
                section="robustness",
                frame=pd.DataFrame({"periode": ["2008", "2020"], "sharpe": [0.4, 0.9]}),
                caption="La performance par sous-période.",
            ),
        ),
        figures=(
            ReportFigure(
                name="richesse_cumulee",
                section="performance",
                path=figure_png,
                caption="La richesse cumulée, en dollars canadiens.",
            ),
        ),
        config={"lookback_months": 12, "universe": ["ES", "CL"]},
        dataset_manifests=({"dataset_id": "yahoo-es", "checksum_sha256": "ab" * 32},),
    )


def test_le_rapport_ecrit_les_six_choses_annoncees(tmp_path: Path, rapport_complet: StudyReport) -> None:
    """Le répertoire de sortie porte les fichiers et les deux sous-dossiers.

    Source (b), la spécification du module : ``report.html``, ``metrics.json``,
    ``config.yaml``, ``figures/``, ``tables/`` et ``data_manifest.json``.
    """
    sortie = generate_report(tmp_path, rapport_complet)
    assert sortie == tmp_path / "reports" / "tsmom" / "exp-0123456789ab"
    for nom in ("report.html", "metrics.json", "config.yaml", "data_manifest.json"):
        assert (sortie / nom).is_file(), nom
    assert (sortie / "figures" / "richesse_cumulee.png").is_file()
    assert (sortie / "tables" / "sous_periodes.csv").is_file()


def test_le_rapport_porte_les_quinze_sections(tmp_path: Path, rapport_complet: StudyReport) -> None:
    """Les quinze sections du plan sont présentes, dans l'ordre imposé.

    Source (b), la liste écrite dans la spécification, de l'hypothèse au
    verdict. Le test vérifie la présence et l'ordre des ancres.
    """
    sortie = generate_report(tmp_path, rapport_complet)
    page = (sortie / "report.html").read_text(encoding="utf-8")
    attendues = [
        "hypothesis",
        "paper",
        "methodology",
        "data",
        "implementation",
        "assumptions",
        "replication",
        "performance",
        "costs",
        "robustness",
        "out_of_sample",
        "statistical_tests",
        "factor_attribution",
        "limitations",
        "verdict",
    ]
    assert [cle for cle, _ in REPORT_SECTIONS] == attendues
    assert len(attendues) == 15
    positions = [page.find(f'<section id="{cle}">') for cle in attendues]
    assert all(p >= 0 for p in positions), "section absente de la page"
    assert positions == sorted(positions), "sections dans le désordre"


def test_le_rapport_est_autonome(tmp_path: Path, rapport_complet: StudyReport) -> None:
    """La page ne demande rien au réseau : aucune adresse distante.

    Source (b). Une page qui charge une police ou une feuille de style à
    distance cesse de s'afficher le jour où le service disparaît.
    """
    sortie = generate_report(tmp_path, rapport_complet)
    page = (sortie / "report.html").read_text(encoding="utf-8")
    assert "http://" not in page
    assert "https://" not in page
    assert "<style>" in page
    # La figure est référencée par un chemin relatif, écrit à côté de la page.
    assert 'src="figures/richesse_cumulee.png"' in page


def test_le_rapport_porte_le_verdict_et_ses_raisons(tmp_path: Path, rapport_complet: StudyReport) -> None:
    """Le verdict et chaque raison se lisent dans la page et dans le JSON.

    Source (b). Le jeu de preuves est celui qui passe tout, donc le verdict
    attendu est ``PORTFOLIO_CANDIDATE``.
    """
    sortie = generate_report(tmp_path, rapport_complet)
    page = (sortie / "report.html").read_text(encoding="utf-8")
    assert "PORTFOLIO_CANDIDATE" in page

    metriques = json.loads((sortie / "metrics.json").read_text(encoding="utf-8"))
    assert metriques["verdict"] == "PORTFOLIO_CANDIDATE"
    assert metriques["reasons"][-1] == "VERDICT | PORTFOLIO_CANDIDATE"
    assert len(metriques["reasons"]) == 12
    assert metriques["metrics"][0]["sample"] == "OOS"
    assert metriques["metrics"][0]["cost_basis"] == "net"
    assert metriques["criteria"]["max_pbo"] == 0.5
    assert metriques["replication"][0]["relative_error"] == pytest.approx(0.075, abs=1e-12)


def test_la_configuration_et_les_manifestes_se_relisent(tmp_path: Path, rapport_complet: StudyReport) -> None:
    """La configuration et les manifestes écrits se relisent à l'identique."""
    sortie = generate_report(tmp_path, rapport_complet)
    config = yaml.safe_load((sortie / "config.yaml").read_text(encoding="utf-8"))
    assert config == {"lookback_months": 12, "universe": ["ES", "CL"]}
    manifeste = json.loads((sortie / "data_manifest.json").read_text(encoding="utf-8"))
    assert manifeste["datasets"][0]["dataset_id"] == "yahoo-es"


def test_une_section_inconnue_leve(tmp_path: Path, rapport_complet: StudyReport) -> None:
    """Une clé de section hors du plan lève, plutôt que d'être ignorée."""
    casse = StudyReport(
        study_name="tsmom",
        experiment_id="exp-1",
        hypothesis="x",
        paper="y",
        sections={"conclusion": "hors plan"},
    )
    with pytest.raises(ConfigError, match="sections inconnues"):
        generate_report(tmp_path, casse)


def test_une_figure_absente_leve(tmp_path: Path) -> None:
    """Une figure qui ne pointe sur aucun fichier lève avant toute écriture."""
    casse = StudyReport(
        study_name="tsmom",
        experiment_id="exp-1",
        hypothesis="x",
        paper="y",
        figures=(ReportFigure(name="f", section="performance", path=tmp_path / "absent.png"),),
    )
    with pytest.raises(ConfigError, match="aucun fichier"):
        generate_report(tmp_path, casse)


def test_un_tableau_de_metriques_sans_etiquette_leve(tmp_path: Path) -> None:
    """Un tableau de métriques construit à la main sans étiquette lève."""
    casse = StudyReport(
        study_name="tsmom",
        experiment_id="exp-1",
        hypothesis="x",
        paper="y",
        metrics=pd.DataFrame({"metric": ["sharpe"], "value": [1.2]}),
    )
    with pytest.raises(ConfigError, match="colonnes absentes"):
        generate_report(tmp_path, casse)


def test_un_gabarit_sans_champ_de_corps_leve(tmp_path: Path, rapport_complet: StudyReport) -> None:
    """Un gabarit qui n'accueille pas le corps du rapport lève."""
    with pytest.raises(ConfigError, match="body"):
        generate_report(tmp_path, rapport_complet, template="<html>rien</html>")


def test_un_gabarit_fourni_est_employe(tmp_path: Path, rapport_complet: StudyReport) -> None:
    """Le gabarit du chercheur remplace celui du laboratoire."""
    sortie = generate_report(tmp_path, rapport_complet, template="<article>{title}|{body}</article>")
    page = (sortie / "report.html").read_text(encoding="utf-8")
    assert page.startswith("<article>tsmom (exp-0123456789ab)|")
    assert page.endswith("</article>")
    assert '<section id="verdict">' in page


def test_un_rapport_vide_s_ecrit_quand_meme(tmp_path: Path) -> None:
    """Cas limite : aucune métrique, aucune figure, aucun tableau.

    Le verdict attendu est ``EXPERIMENTAL``. Sans aucune mesure, le Sharpe hors
    échantillon vaut ``None``, donc rien ne réfute l'hypothèse et le rejet
    n'est pas prononcé. La réplication, elle, n'a aucun contrôle chiffré, donc
    l'échelle s'arrête au premier barreau au-dessus du rejet. Source (b) pour
    ce raisonnement.
    """
    nu = StudyReport(study_name="essai", experiment_id="exp-0", hypothesis="x", paper="y")
    sortie = generate_report(tmp_path, nu)
    page = (sortie / "report.html").read_text(encoding="utf-8")
    assert page.count("Section non renseignée.") == 15
    verdict, _ = nu.verdict()
    assert verdict is Verdict.EXPERIMENTAL


def test_section_keys_donne_quinze_cles_uniques() -> None:
    """Les quinze clés de section sont distinctes."""
    cles = section_keys()
    assert len(cles) == 15
    assert len(set(cles)) == 15


# --------------------------------------------------------------------------- #
# Propriétés
# --------------------------------------------------------------------------- #


@given(
    published=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
    ours=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200, deadline=None)
def test_propriete_identite_des_deux_ecarts(published: float, ours: float) -> None:
    """L'écart relatif multiplié par la valeur publiée redonne l'écart absolu.

    Source (b), identité mathématique. Elle ne vaut pas à valeur publiée nulle,
    cas traité à part par le module et par son test dédié. Elle ne vaut pas non
    plus sur les dénormaux, où le quotient déborde.
    """
    check = ReplicationCheck(quantity="q", published=published, ours=ours)
    assert check.absolute_error == pytest.approx(abs(ours - published), abs=1e-12)
    # La reconstruction n'est testée qu'au-dessus de 0,001 en valeur absolue.
    # En deçà, le quotient déborde en virgule flottante et l'identité cesse de
    # tenir dans la machine, sans que le module y soit pour rien.
    assume(abs(published) > 1e-3)
    reconstruit = check.relative_error * abs(published)
    assert reconstruit == pytest.approx(check.absolute_error, rel=1e-9, abs=1e-12)


@given(sharpe=st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False))
@settings(max_examples=100, deadline=None)
def test_propriete_aucun_sharpe_ne_remplace_la_replication(sharpe: float) -> None:
    """Aucune valeur de Sharpe hors échantillon ne fait franchir la réplication.

    Source (b), la règle écrite du laboratoire. La propriété est testée sur six
    ordres de grandeur, de 0,01 à un million.
    """
    verdict, _ = decide_verdict(_preuves_completes(oos_sharpe=sharpe, replication_checks=()))
    assert verdict is Verdict.EXPERIMENTAL


# --------------------------------------------------------------------------- #
# La tolérance absolue, et la porte qu'elle ouvrait
# --------------------------------------------------------------------------- #


def test_une_tolerance_absolue_large_n_echappe_pas_a_la_tolerance_declaree() -> None:
    """Une tolérance absolue démesurée ne fait pas passer un écart de 87,5 %.

    Source (a), calcul à la main. La valeur publiée vaut 0,80 et la nôtre 0,10,
    donc l'écart relatif vaut 0,70 / 0,80 = 0,875. Une tolérance absolue de
    10,0 équivaut à 10,0 / 0,80 = 12,5 en relatif, soit 125 fois la tolérance
    déclarée de 0,10. Le contrôle doit donc échouer.
    """
    evasif = ReplicationCheck(
        quantity="Sharpe", published=0.80, ours=0.10, tolerance=10.0, tolerance_kind="absolute"
    )
    # Pris isolément, le contrôle se croit conforme à sa propre tolérance.
    assert evasif.passed is True
    verdict, raisons = decide_verdict(_preuves_completes(replication_checks=(evasif,)))
    assert verdict is Verdict.EXPERIMENTAL
    ligne = _raison(raisons, "réplication de « Sharpe »")
    assert ligne.startswith("ÉCHOUÉ")
    assert "soit 12,500 en relatif" in ligne
    assert "plus large que la tolérance déclarée 0,100" in ligne


def test_une_tolerance_absolue_serree_reste_valable() -> None:
    """Une tolérance absolue étroite passe, parce que son équivalent relatif passe.

    Source (a). Valeur publiée 0,80, la nôtre 0,76, écart absolu 0,04. La
    tolérance absolue de 0,05 vaut 0,05 / 0,80 = 0,0625 en relatif, sous la
    tolérance déclarée de 0,10, donc le contrôle passe.
    """
    serre = ReplicationCheck(
        quantity="Sharpe", published=0.80, ours=0.76, tolerance=0.05, tolerance_kind="absolute"
    )
    verdict, raisons = decide_verdict(_preuves_completes(replication_checks=(serre,)))
    assert verdict is Verdict.PORTFOLIO_CANDIDATE
    assert "soit 0,062 en relatif" in _raison(raisons, "réplication de « Sharpe »")


def test_une_tolerance_absolue_sur_une_valeur_publiee_nulle_se_signale() -> None:
    """Un alpha publié nul n'a pas d'équivalent relatif, et la raison le dit.

    Source (b). La division par la valeur publiée n'existe pas à zéro, donc
    aucune comparaison à la tolérance déclarée n'est possible. Le contrôle
    passe et la raison avertit le lecteur, qui vérifie à la main.
    """
    zero = ReplicationCheck(
        quantity="alpha", published=0.0, ours=0.001, tolerance=0.002, tolerance_kind="absolute"
    )
    verdict, raisons = decide_verdict(_preuves_completes(replication_checks=(zero,)))
    assert verdict is Verdict.PORTFOLIO_CANDIDATE
    assert "sans équivalent relatif car la valeur publiée est nulle" in _raison(
        raisons, "réplication de « alpha »"
    )


# --------------------------------------------------------------------------- #
# Les noms de pièces, qui fabriquent des fichiers
# --------------------------------------------------------------------------- #


def test_deux_figures_de_meme_nom_levent(tmp_path: Path, figure_png: Path) -> None:
    """Deux figures homonymes s'écraseraient, donc le rapport refuse de s'écrire.

    Source (b). Le nom sert à fabriquer ``figures/<nom>.png`` : deux fois le
    même nom laisse un seul fichier, et la page l'affiche sous deux légendes.
    """
    casse = StudyReport(
        study_name="tsmom",
        experiment_id="exp-1",
        hypothesis="x",
        paper="y",
        figures=(
            ReportFigure(name="fig", section="performance", path=figure_png),
            ReportFigure(name="fig", section="costs", path=figure_png),
        ),
    )
    with pytest.raises(ConfigError, match="portent le nom"):
        generate_report(tmp_path, casse)


def test_deux_tableaux_de_meme_nom_levent(tmp_path: Path) -> None:
    """Deux tableaux homonymes ne laisseraient qu'un seul fichier CSV."""
    cadre = pd.DataFrame({"x": [1]})
    casse = StudyReport(
        study_name="tsmom",
        experiment_id="exp-1",
        hypothesis="x",
        paper="y",
        tables=(
            ReportTable(name="t", section="costs", frame=cadre),
            ReportTable(name="t", section="data", frame=cadre),
        ),
    )
    with pytest.raises(ConfigError, match="portent le nom"):
        generate_report(tmp_path, casse)


@pytest.mark.parametrize("nom", ["../../evade", "sous/dossier", "  "])
def test_un_nom_de_figure_irrecevable_leve(tmp_path: Path, figure_png: Path, nom: str) -> None:
    """Un nom qui porte un chemin, ou qui est vide, ne fabrique pas de fichier.

    Source (b). Mesuré avant correction : le nom ``../../evade`` écrivait le
    fichier deux niveaux au-dessus du répertoire du rapport.
    """
    casse = StudyReport(
        study_name="tsmom",
        experiment_id="exp-1",
        hypothesis="x",
        paper="y",
        figures=(ReportFigure(name=nom, section="performance", path=figure_png),),
    )
    with pytest.raises(ConfigError, match=r"porte un chemin|nom vide"):
        generate_report(tmp_path, casse)


# --------------------------------------------------------------------------- #
# Le gabarit du chercheur
# --------------------------------------------------------------------------- #


def test_un_gabarit_avec_des_accolades_de_style_est_employe_tel_quel(
    tmp_path: Path, rapport_complet: StudyReport
) -> None:
    """Un gabarit qui porte du CSS garde ses accolades, il ne les fait pas lire.

    Source (b). Les accolades de CSS ne sont pas des champs de gabarit. Mesuré
    avant correction : ce gabarit levait ``KeyError: ' margin'``, une erreur
    que rien ne rattachait à sa cause.
    """
    gabarit = "<html><head><style>body { margin: 0 }</style></head><body>{body}</body></html>"
    sortie = generate_report(tmp_path, rapport_complet, template=gabarit)
    page = (sortie / "report.html").read_text(encoding="utf-8")
    assert "body { margin: 0 }" in page
    assert '<section id="verdict">' in page


def test_le_corps_du_rapport_n_est_pas_relu_comme_un_gabarit(tmp_path: Path) -> None:
    """Un champ écrit dans la prose du chercheur reste du texte.

    Source (b). La substitution se fait en une passe sur le seul gabarit, donc
    le texte ``{title}`` écrit dans une section survit tel quel.
    """
    piege = StudyReport(
        study_name="essai",
        experiment_id="exp-0",
        hypothesis="x",
        paper="y",
        sections={"limitations": "Le champ {title} est ici du texte."},
    )
    sortie = generate_report(tmp_path, piege, template="<main>{body}</main>")
    page = (sortie / "report.html").read_text(encoding="utf-8")
    assert "Le champ {title} est ici du texte." in page
    assert page.count("essai (exp-0)") == 0


# --------------------------------------------------------------------------- #
# Le verdict contre une implémentation indépendante
# --------------------------------------------------------------------------- #


def _verdict_de_reference(evidence: VerdictEvidence, criteria: VerdictCriteria) -> Verdict:
    """Rend le verdict d'après la définition écrite, sans appeler le module.

    Source (d) pour les tests qui s'en servent. Les quatre groupes sont
    réécrits ici en clair, à partir de la seule définition de l'échelle, sans
    partager une ligne avec :func:`decide_verdict`.
    """

    def au_moins(valeur: float | None, seuil: float) -> bool:
        return valeur is not None and valeur >= seuil

    def au_plus(valeur: float | None, seuil: float) -> bool:
        return valeur is not None and valeur <= seuil

    sharpe = evidence.oos_sharpe
    non_rejete = bool(evidence.hypothesis_supported) and not (sharpe is not None and sharpe <= 0.0)

    checks = tuple(evidence.replication_checks)
    equivalents = [
        c.tolerance
        if c.tolerance_kind == "relative"
        else (None if c.published == 0.0 else c.tolerance / abs(c.published))
        for c in checks
    ]
    replique = bool(checks) and all(
        c.passed and not (e is not None and e > criteria.replication_tolerance)
        for c, e in zip(checks, equivalents, strict=True)
    )

    robuste = (
        au_moins(sharpe, criteria.min_oos_sharpe)
        and au_moins(evidence.tstat_after_multiplicity, criteria.min_tstat)
        and au_moins(evidence.deflated_sharpe, criteria.min_dsr)
        and au_plus(evidence.pbo, criteria.max_pbo)
        and au_moins(evidence.positive_subperiod_share, criteria.min_positive_subperiod_share)
        and au_moins(evidence.surviving_cost_multiple, criteria.min_cost_multiple)
    )

    correlation = evidence.portfolio_correlation
    apporte = correlation is not None and abs(correlation) <= criteria.max_portfolio_correlation

    if not non_rejete:
        return Verdict.REJECTED
    if not replique:
        return Verdict.EXPERIMENTAL
    if not robuste:
        return Verdict.REPLICATED
    if not apporte:
        return Verdict.ROBUST
    return Verdict.PORTFOLIO_CANDIDATE


_CHECKS_POSSIBLES = (
    (),
    (CHECK_QUI_PASSE,),
    (CHECK_QUI_ECHOUE,),
    (CHECK_QUI_PASSE, CHECK_QUI_ECHOUE),
    (ReplicationCheck("Sharpe", 0.80, 0.10, tolerance=10.0, tolerance_kind="absolute"),),
    (ReplicationCheck("Sharpe", 0.80, 0.76, tolerance=0.05, tolerance_kind="absolute"),),
)


@given(
    hypothesis_supported=st.booleans(),
    replication_checks=st.sampled_from(_CHECKS_POSSIBLES),
    oos_sharpe=st.sampled_from([None, -0.30, 0.0, 0.30, 0.50, 0.70]),
    tstat_after_multiplicity=st.sampled_from([None, 1.90, 3.0, 3.40]),
    deflated_sharpe=st.sampled_from([None, 0.50, 0.95, 0.97]),
    pbo=st.sampled_from([None, 0.20, 0.50, 0.70]),
    positive_subperiod_share=st.sampled_from([None, 0.50, 0.60, 0.75]),
    surviving_cost_multiple=st.sampled_from([None, 1.0, 2.0, 3.0]),
    portfolio_correlation=st.sampled_from([None, -0.85, 0.30, 0.60, 0.85]),
)
@settings(max_examples=400, deadline=None)
def test_propriete_verdict_contre_une_implementation_independante(**champs: object) -> None:
    """Le verdict du module suit la définition écrite, sur tout le treillis.

    Source (d). La référence est réécrite dans ce fichier depuis la seule
    définition de l'échelle. Les tirages couvrent les six jeux de contrôles de
    réplication et toutes les combinaisons de mesures absentes.
    """
    evidence = VerdictEvidence(**champs)  # type: ignore[arg-type]
    seuils = VerdictCriteria()
    verdict, _ = decide_verdict(evidence, seuils)
    assert verdict is _verdict_de_reference(evidence, seuils)


def test_propriete_la_degradation_d_un_critere_ne_remonte_jamais_le_verdict() -> None:
    """Dégrader un seul critère ne fait jamais monter le verdict.

    Source (b), la monotonie de l'échelle. Chaque dégradation est écrite à la
    main, une par critère, et le rang du verdict obtenu se compare au rang du
    jeu complet dans ``VERDICT_LADDER``.
    """
    rang_complet = VERDICT_LADDER.index(decide_verdict(_preuves_completes())[0])
    degradations: dict[str, object] = {
        "hypothesis_supported": False,
        "replication_checks": (CHECK_QUI_ECHOUE,),
        "oos_sharpe": 0.30,
        "tstat_after_multiplicity": 1.90,
        "deflated_sharpe": 0.50,
        "pbo": 0.70,
        "positive_subperiod_share": 0.50,
        "surviving_cost_multiple": 1.0,
        "portfolio_correlation": 0.85,
    }
    for champ, valeur in degradations.items():
        verdict, _ = decide_verdict(_preuves_completes(**{champ: valeur}))
        assert VERDICT_LADDER.index(verdict) < rang_complet, champ


def test_un_ecart_exactement_egal_a_la_tolerance_passe_des_deux_cotes() -> None:
    """Deux écarts vrais de 10 % rendent le même verdict, quelles que soient
    leurs décimales.

    Source (a), calcul à la main. 0,80 moins 0,72 fait 0,08, et 0,08 / 0,80
    vaut 0,10. 2,0 moins 1,8 fait 0,2, et 0,2 / 2,0 vaut 0,10 aussi. Les deux
    couples valent donc exactement la tolérance de 0,10 et doivent passer.
    Mesuré avant correction : le premier rendait 0,10000000000000009 et
    échouait, le second rendait 0,09999999999999998 et passait.
    """
    assert ReplicationCheck(quantity="q", published=0.80, ours=0.72, tolerance=0.10).passed is True
    assert ReplicationCheck(quantity="q", published=2.0, ours=1.8, tolerance=0.10).passed is True
    # La marge d'arrondi ne sauve aucun écart réel : 0,10 / 0,80 vaut 0,125.
    assert ReplicationCheck(quantity="q", published=0.80, ours=0.70, tolerance=0.10).passed is False


def test_une_tolerance_nulle_exige_l_egalite() -> None:
    """Cas limite : la marge d'arrondi est multiplicative, donc zéro reste zéro.

    Source (b). Une tolérance de 0,0 multipliée par ``1 + 1e-12`` vaut 0,0,
    donc seule l'égalité exacte passe.
    """
    assert ReplicationCheck(quantity="q", published=0.80, ours=0.80, tolerance=0.0).passed is True
    assert ReplicationCheck(quantity="q", published=0.80, ours=0.8000001, tolerance=0.0).passed is False
