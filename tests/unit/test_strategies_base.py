"""Contrôles de ``quantlab.strategies.base``.

Aucune valeur attendue de ce fichier ne vient de la sortie du code. Chacune
porte sa source en commentaire : (a) calcul à la main, (b) identité ou contrat
déclaré, (c) valeur publiée et citée, (d) implémentation indépendante.

Le module ne calcule presque rien : il pose des contraintes. Les contrôles
portent donc sur ce qu'il REFUSE, et la source des valeurs attendues est le plus
souvent (b), le contrat déclaré dans la docstring du module.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import get_origin

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytest
import yaml
from hypothesis import given, settings
from pydantic import ValidationError

from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    NotReplicatedError,
    QuantLabError,
)
from quantlab.core.protocols import AlphaModel
from quantlab.core.types import AssetClass, Verdict
from quantlab.strategies.base import _CHAMPS_LISTES as CHAMPS_LISTES
from quantlab.strategies.base import (
    ECONOMIC_RATIONALES,
    EVIDENCE_BACKED_VERDICTS,
    REGISTRY_DIRNAME,
    AlphaMetadata,
    AlphaRegistry,
    Strategy,
    load_registry,
    save_registry,
)

#: Le caractère « next line » d'Unicode. YAML 1.1 le range parmi les fins de
#: ligne, et PyYAML le relit comme une espace : un aller-retour le perd.
NEXT_LINE = "\u0085"

# Deux dates fixes, pour que rien ne dépende du jour où le test tourne.
CREATION = dt.date(2026, 9, 1)
MODIFICATION = dt.date(2026, 9, 2)


def fiche(name: str = "tsmom_moskowitz_2012", **override: object) -> AlphaMetadata:
    """Construit une fiche valide, que chaque test déforme à sa guise."""
    champs: dict[str, object] = {
        "name": name,
        "family": "momentum",
        "paper": "Moskowitz, Ooi et Pedersen (2012), « Time Series Momentum », JFE 104(2)",
        "asset_classes": [AssetClass.EQUITY_INDEX, AssetClass.BOND],
        "horizon": "formation 12 mois, détention 1 mois",
        "economic_rationale": ["contrainte institutionnelle", "biais comportemental"],
        "inputs": ["prix de clôture ajustés quotidiens"],
        "known_risks": ["retournement brutal de tendance"],
        "created": CREATION,
        "last_modified": MODIFICATION,
    }
    champs.update(override)
    return AlphaMetadata(**champs)  # type: ignore[arg-type]


@pytest.fixture
def registre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AlphaRegistry:
    """Rend un registre vide dont la racine est déplacée par ``QUANTLAB_ROOT``."""
    monkeypatch.setenv("QUANTLAB_ROOT", str(tmp_path))
    return AlphaRegistry()


# --------------------------------------------------------------------------
# La contrainte qui compte : pas de mécanisme, pas de fiche
# --------------------------------------------------------------------------


def test_fiche_sans_mecanisme_refusee() -> None:
    """(b) Contrat déclaré : ``economic_rationale`` ne peut pas être vide.

    La liste vide viole ``min_length=1``, et Pydantic lève avant qu'aucune
    donnée n'ait été touchée.
    """
    with pytest.raises(ValidationError, match="economic_rationale"):
        fiche(economic_rationale=[])


def test_fiche_sans_champ_mecanisme_refusee() -> None:
    """(b) Contrat déclaré : le champ est obligatoire, pas seulement non vide."""
    champs = fiche().model_dump(mode="json")
    del champs["economic_rationale"]
    with pytest.raises(ValidationError, match="economic_rationale"):
        AlphaMetadata.model_validate(champs)


def test_mecanisme_hors_de_l_ensemble_declare_refuse() -> None:
    """(b) Contrat déclaré : l'ensemble des mécanismes admis est fermé.

    « le marché est inefficient » est un constat, pas un mécanisme, et c'est
    exactement ce que la fermeture de l'ensemble sert à écarter.
    """
    with pytest.raises(ValidationError, match="mécanisme non déclaré"):
        fiche(economic_rationale=["le marché est inefficient"])


def test_les_quatre_mecanismes_admis_sont_ceux_du_module() -> None:
    """(b) Contrat déclaré : quatre mécanismes, ceux de la docstring du module."""
    attendus = {
        "prime de risque",
        "biais comportemental",
        "contrainte institutionnelle",
        "friction",
    }
    assert attendus == ECONOMIC_RATIONALES


@pytest.mark.parametrize("mecanisme", sorted(ECONOMIC_RATIONALES))
def test_chaque_mecanisme_admis_passe(mecanisme: str) -> None:
    """(b) Chacun des quatre mécanismes déclarés construit une fiche valide."""
    assert fiche(economic_rationale=[mecanisme]).economic_rationale == [mecanisme]


def test_mecanisme_normalise_en_minuscules() -> None:
    """(b) La casse et les espaces de bord ne changent pas le mécanisme cité."""
    assert fiche(economic_rationale=["  Prime De Risque "]).economic_rationale == ["prime de risque"]


def test_mecanisme_cite_deux_fois_refuse() -> None:
    """(b) Citer deux fois le même mécanisme n'en fait pas deux."""
    with pytest.raises(ValidationError, match="deux fois"):
        fiche(economic_rationale=["friction", "friction"])


def test_classe_d_actif_citee_deux_fois_refusee() -> None:
    """(b) Même règle sur les classes d'actif, pour la même raison."""
    with pytest.raises(ValidationError, match="deux fois"):
        fiche(asset_classes=[AssetClass.BOND, AssetClass.BOND])


def test_liste_de_classes_vide_refusee() -> None:
    """(b) Une fiche qui ne vise aucune classe d'actif ne vise rien."""
    with pytest.raises(ValidationError, match="asset_classes"):
        fiche(asset_classes=[])


@pytest.mark.parametrize("mauvais", ["../evil", "Tsmom", "tsmom-2012", "2/3", "", "_tsmom"])
def test_nom_non_utilisable_comme_fichier_refuse(mauvais: str) -> None:
    """(b) Le nom sert de nom de fichier, donc il est restreint.

    Sans cette restriction, un nom porteur de « ../ » écrirait hors du registre.
    """
    with pytest.raises(ValidationError, match="nom invalide"):
        fiche(name=mauvais)


def test_nom_avec_saut_de_ligne_final_refuse() -> None:
    """(a) Contre-exemple à la main sur l'ancre de fin de l'expression régulière.

    En Python, ``$`` matche aussi devant un saut de ligne final. Une règle
    ancrée par ``$`` accepterait donc le nom « tsmom » suivi d'un saut de ligne,
    et le registre écrirait un fichier dont le nom porte ce saut. L'ancre
    correcte est ``\\Z``, et ce test la fixe.
    """
    with pytest.raises(ValidationError, match="nom invalide"):
        fiche(name="tsmom\n")


def test_cle_inconnue_refusee() -> None:
    """(b) ``StrictModel`` interdit les clés inconnues, donc les fautes de frappe."""
    champs = fiche().model_dump(mode="json")
    champs["econimic_rationale"] = ["friction"]
    with pytest.raises(ValidationError):
        AlphaMetadata.model_validate(champs)


def test_la_fiche_est_gelee() -> None:
    """(b) ``StrictModel`` gèle ses instances : un verdict ne se pose pas en place."""
    with pytest.raises(ValidationError):
        fiche().validation_status = Verdict.ROBUST  # type: ignore[misc]


# --------------------------------------------------------------------------
# L'aller-retour d'écriture et de lecture
# --------------------------------------------------------------------------


def test_racine_du_registre_suit_quantlab_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(b) Contrat de ``core.paths`` : ``QUANTLAB_ROOT`` l'emporte sur le paquet."""
    monkeypatch.setenv("QUANTLAB_ROOT", str(tmp_path))
    attendu = tmp_path.resolve() / "configs" / REGISTRY_DIRNAME
    assert AlphaRegistry().root == attendu


def test_aller_retour_d_une_fiche(registre: AlphaRegistry) -> None:
    """(b) Identité d'aller-retour : écrire puis relire rend la même fiche."""
    origine = fiche()
    chemin = registre.register(origine)

    assert chemin.name == "tsmom_moskowitz_2012.yaml"
    assert registre.get("tsmom_moskowitz_2012") == origine


def test_le_fichier_ecrit_est_du_yaml_lisible(registre: AlphaRegistry) -> None:
    """(a) Lecture à la main du YAML écrit, sans passer par le modèle.

    Le fichier doit être relisible par un humain et par ``yaml.safe_load``,
    faute de quoi le registre ne se revoit pas dans une revue de code.
    """
    registre.register(fiche())
    brut = yaml.safe_load(registre.path_for("tsmom_moskowitz_2012").read_text(encoding="utf-8"))

    assert brut["name"] == "tsmom_moskowitz_2012"
    assert brut["family"] == "momentum"
    assert brut["asset_classes"] == ["equity_index", "bond"]
    assert brut["economic_rationale"] == ["contrainte institutionnelle", "biais comportemental"]
    assert brut["validation_status"] == "EXPERIMENTAL"
    assert brut["verdict_experiment_id"] is None
    # (a) Les dates sont écrites en ISO, sous forme de chaîne, et Pydantic les
    # reconvertit à la lecture. La forme sur le disque reste lisible à l'œil.
    assert brut["created"] == "2026-09-01"
    assert AlphaMetadata.model_validate(brut).created == dt.date(2026, 9, 1)


def test_note_non_relisible_refusee() -> None:
    """(a) Contre-exemple mesuré : PyYAML rend une espace là où le texte portait U+0085.

    ``yaml.safe_dump({"n": "\\u0085"}, allow_unicode=True)`` écrit le caractère
    tel quel, et ``yaml.safe_load`` du même texte rend une espace. La perte est
    silencieuse, donc ``to_yaml`` refuse plutôt que de la laisser passer.
    """
    # (a) La perte est d'abord constatée sur PyYAML seul, hors du module.
    dump = yaml.safe_dump({"n": NEXT_LINE}, allow_unicode=True, sort_keys=False)
    assert yaml.safe_load(dump)["n"] == " "

    with pytest.raises(ConfigError, match="ne survit pas"):
        fiche(notes=NEXT_LINE).to_yaml()


def test_note_avec_saut_de_ligne_et_tabulation_survit() -> None:
    """(a) Contrôle discriminant : les fins de ligne ordinaires, elles, survivent.

    Sans ce contrôle, le refus précédent pourrait venir d'un rejet trop large,
    qui interdirait toute note sur plusieurs lignes.
    """
    note = "deux\nlignes\tet une tabulation"
    relue = AlphaMetadata.model_validate(yaml.safe_load(fiche(notes=note).to_yaml()))
    assert relue.notes == note


def test_aller_retour_du_registre_entier(registre: AlphaRegistry) -> None:
    """(b) Identité d'aller-retour sur trois fiches : ``load`` défait ``save``."""
    fiches = [fiche("alpha_un"), fiche("alpha_deux"), fiche("alpha_trois")]
    chemins = save_registry(fiches, registre.root)

    assert len(chemins) == 3
    relues = load_registry(registre.root)
    assert set(relues) == {"alpha_un", "alpha_deux", "alpha_trois"}
    assert relues == {f.name: f for f in fiches}


def test_load_registry_suit_aussi_quantlab_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(b) Sans argument, les deux fonctions visent la racine de l'environnement."""
    monkeypatch.setenv("QUANTLAB_ROOT", str(tmp_path))
    save_registry([fiche("alpha_un")])
    assert set(load_registry()) == {"alpha_un"}


def test_registre_vide_rend_une_liste_vide(registre: AlphaRegistry) -> None:
    """(b) Cas limite : un dépôt frais n'a pas de répertoire de fiches."""
    assert registre.list() == []
    assert load_registry(registre.root) == {}


def test_enregistrer_deux_fois_le_meme_nom_refuse(registre: AlphaRegistry) -> None:
    """(b) Contrat déclaré : ``register`` n'écrase pas sans le dire."""
    registre.register(fiche())
    with pytest.raises(ConfigError, match="déjà enregistrée"):
        registre.register(fiche())


def test_enregistrer_avec_overwrite_remplace(registre: AlphaRegistry) -> None:
    """(b) L'écrasement explicite passe, et la nouvelle fiche est celle relue."""
    registre.register(fiche())
    registre.register(fiche(family="tendance"), overwrite=True)
    assert registre.get("tsmom_moskowitz_2012").family == "tendance"


def test_save_registry_refuse_deux_fiches_homonymes(registre: AlphaRegistry) -> None:
    """(b) Deux fiches du même nom : la seconde effacerait la première en silence."""
    with pytest.raises(ConfigError, match="deux fiches"):
        save_registry([fiche("alpha_un"), fiche("alpha_un")], registre.root)


def test_alpha_inconnu(registre: AlphaRegistry) -> None:
    """(b) Une fiche absente lève, plutôt que de rendre ``None``."""
    with pytest.raises(QuantLabError, match="alpha inconnu"):
        registre.get("alpha_fantome")


def test_fiche_illisible_sur_le_disque(registre: AlphaRegistry) -> None:
    """(b) Une fiche présente mais invalide fait échouer la lecture du registre.

    Le registre échoue en entier plutôt que de rendre une vue partielle, parce
    qu'une vue partielle se prend pour une vue complète.
    """
    registre.root.mkdir(parents=True)
    (registre.root / "casse.yaml").write_text("name: casse\nfamily: momentum\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        registre.list()


@pytest.mark.parametrize("mauvais", ["../evil", "sous/dossier", "Tsmom", "tsmom\n"])
def test_path_for_refuse_un_nom_qui_sort_du_registre(registre: AlphaRegistry, mauvais: str) -> None:
    """(b) Contrat déclaré : la lecture est protégée comme l'écriture.

    La validation du modèle protège l'écriture, dont le nom vient d'une fiche
    validée. Elle ne protège pas ``get``, qui reçoit une chaîne quelconque.
    """
    with pytest.raises(ConfigError, match="nom invalide"):
        registre.path_for(mauvais)


def test_get_refuse_un_nom_qui_sort_du_registre(registre: AlphaRegistry) -> None:
    """(a) Contre-exemple à la main : sans ce refus, ``get`` lirait hors du registre.

    Le chemin visé serait ``configs/strategies/../evil.yaml``, soit
    ``configs/evil.yaml``, un fichier que le registre n'a jamais écrit.
    """
    with pytest.raises(ConfigError, match="nom invalide"):
        registre.get("../evil")


def test_nom_de_fichier_trompeur_refuse(registre: AlphaRegistry) -> None:
    """(a) Contre-exemple à la main : le registre se contredirait selon la méthode.

    Une fiche nommée « tsmom_moskowitz_2012 » déposée dans « autre_nom.yaml »
    apparaîtrait dans ``list`` alors que ``get`` la déclarerait inconnue.
    """
    registre.root.mkdir(parents=True)
    (registre.root / "autre_nom.yaml").write_text(fiche().to_yaml(), encoding="utf-8")
    with pytest.raises(ConfigError, match="trompeur"):
        registre.list()


def test_fiche_sans_mecanisme_sur_le_disque_refusee(registre: AlphaRegistry) -> None:
    """(b) La contrainte tient aussi au chargement, et pas seulement en mémoire."""
    payload = fiche().model_dump(mode="json")
    payload["economic_rationale"] = []
    registre.root.mkdir(parents=True)
    registre.path_for("tsmom_moskowitz_2012").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="economic_rationale"):
        registre.get("tsmom_moskowitz_2012")


# --------------------------------------------------------------------------
# Le verdict ne se déclare pas à la main
# --------------------------------------------------------------------------


def test_les_verdicts_adosses_a_une_preuve_sont_les_deux_derniers() -> None:
    """(b) Contrat déclaré : seuls ROBUST et PORTFOLIO_CANDIDATE exigent une preuve.

    Les trois autres ne promettent aucun contrôle, donc n'en exigent aucun.
    """
    attendus = {Verdict.ROBUST, Verdict.PORTFOLIO_CANDIDATE}
    assert attendus == EVIDENCE_BACKED_VERDICTS


@pytest.mark.parametrize("verdict", sorted(EVIDENCE_BACKED_VERDICTS))
def test_update_status_refuse_sans_experience(registre: AlphaRegistry, verdict: Verdict) -> None:
    """(b) Contrat déclaré : poser ces verdicts sans expérience est refusé."""
    registre.register(fiche())
    with pytest.raises(NotReplicatedError, match="identifiant d'expérience"):
        registre.update_status("tsmom_moskowitz_2012", verdict)


@pytest.mark.parametrize("vide", [None, ""])
def test_update_status_refuse_un_identifiant_vide(registre: AlphaRegistry, vide: str | None) -> None:
    """(b) Une chaîne vide n'est pas un identifiant, et ne passe pas non plus."""
    registre.register(fiche())
    with pytest.raises(NotReplicatedError):
        registre.update_status("tsmom_moskowitz_2012", Verdict.ROBUST, experiment_id=vide)


def test_le_refus_precede_la_lecture_de_la_fiche(registre: AlphaRegistry) -> None:
    """(b) Le garde-fou se déclenche avant tout accès disque, donc sur fiche absente."""
    with pytest.raises(NotReplicatedError):
        registre.update_status("alpha_fantome", Verdict.ROBUST)


@pytest.mark.parametrize("verdict", [Verdict.REJECTED, Verdict.EXPERIMENTAL, Verdict.REPLICATED])
def test_update_status_sans_preuve_accepte_les_trois_autres(
    registre: AlphaRegistry, verdict: Verdict
) -> None:
    """(b) Les verdicts qui ne promettent pas de contrôle se posent sans preuve."""
    registre.register(fiche())
    mise_a_jour = registre.update_status("tsmom_moskowitz_2012", verdict, today=MODIFICATION)
    assert mise_a_jour.validation_status is verdict


def test_update_status_avec_experience_persiste(registre: AlphaRegistry) -> None:
    """(b) Le verdict et son identifiant sont relus depuis le disque, pas de la mémoire."""
    registre.register(fiche())
    registre.update_status(
        "tsmom_moskowitz_2012",
        Verdict.ROBUST,
        experiment_id="exp_20260902_abcd",
        today=dt.date(2026, 9, 3),
    )
    relue = registre.get("tsmom_moskowitz_2012")

    assert relue.validation_status is Verdict.ROBUST
    assert relue.verdict_experiment_id == "exp_20260902_abcd"
    # (a) La date passée en argument est celle qui est écrite, sans le jour courant.
    assert relue.last_modified == dt.date(2026, 9, 3)
    assert relue.created == CREATION


def test_update_status_efface_un_identifiant_devenu_faux(registre: AlphaRegistry) -> None:
    """(b) Rétrograder un verdict sans preuve efface le lien vers l'ancien contrôle.

    Un identifiant conservé pointerait vers une expérience qui ne dit plus la
    même chose que la fiche.
    """
    registre.register(fiche())
    registre.update_status("tsmom_moskowitz_2012", Verdict.ROBUST, experiment_id="exp_un")
    registre.update_status("tsmom_moskowitz_2012", Verdict.EXPERIMENTAL)
    assert registre.get("tsmom_moskowitz_2012").verdict_experiment_id is None


def test_update_status_accepte_une_chaine(registre: AlphaRegistry) -> None:
    """(b) ``Verdict`` est une ``StrEnum``, donc la chaîne publiée est acceptée."""
    registre.register(fiche())
    mise_a_jour = registre.update_status("tsmom_moskowitz_2012", "REPLICATED")
    assert mise_a_jour.validation_status is Verdict.REPLICATED


def test_update_status_refuse_un_verdict_inconnu(registre: AlphaRegistry) -> None:
    """(b) Un verdict hors de l'énumération n'existe pas."""
    registre.register(fiche())
    with pytest.raises(ValueError, match="PRESQUE_BON"):
        registre.update_status("tsmom_moskowitz_2012", "PRESQUE_BON")


# --------------------------------------------------------------------------
# Les vues du registre
# --------------------------------------------------------------------------


def _trois_fiches(registre: AlphaRegistry) -> None:
    """Pose trois fiches : deux familles, trois verdicts distincts."""
    save_registry(
        [
            fiche("tsmom_moskowitz_2012", family="momentum", validation_status=Verdict.REPLICATED),
            fiche("xsmom_jegadeesh_1993", family="momentum", validation_status=Verdict.EXPERIMENTAL),
            fiche("bab_frazzini_2014", family="portage", validation_status=Verdict.REJECTED),
        ],
        registre.root,
    )


def test_list_trie_par_nom(registre: AlphaRegistry) -> None:
    """(a) Tri alphabétique des trois noms posés : b avant t avant x."""
    _trois_fiches(registre)
    assert [f.name for f in registre.list()] == [
        "bab_frazzini_2014",
        "tsmom_moskowitz_2012",
        "xsmom_jegadeesh_1993",
    ]


def test_by_family(registre: AlphaRegistry) -> None:
    """(a) Comptage à la main : deux fiches de momentum, une de portage."""
    _trois_fiches(registre)

    assert [f.name for f in registre.by_family("momentum")] == [
        "tsmom_moskowitz_2012",
        "xsmom_jegadeesh_1993",
    ]
    assert [f.name for f in registre.by_family("portage")] == ["bab_frazzini_2014"]
    assert registre.by_family("valeur") == []


def test_by_family_ignore_la_casse(registre: AlphaRegistry) -> None:
    """(b) La famille est une étiquette de lecture, la casse n'y change rien."""
    _trois_fiches(registre)
    assert len(registre.by_family("  MOMENTUM ")) == 2


def test_by_status(registre: AlphaRegistry) -> None:
    """(a) Comptage à la main : une fiche par verdict sur les trois posés."""
    _trois_fiches(registre)

    assert [f.name for f in registre.by_status(Verdict.REPLICATED)] == ["tsmom_moskowitz_2012"]
    assert [f.name for f in registre.by_status("EXPERIMENTAL")] == ["xsmom_jegadeesh_1993"]
    assert [f.name for f in registre.by_status(Verdict.REJECTED)] == ["bab_frazzini_2014"]
    assert registre.by_status(Verdict.ROBUST) == []


def test_les_trois_vues_partitionnent_le_registre(registre: AlphaRegistry) -> None:
    """(b) Identité de partition : les vues par verdict recouvrent le registre.

    Chaque fiche porte un verdict et un seul, donc la somme des vues rend le
    compte total, sans recouvrement.
    """
    _trois_fiches(registre)
    total = sum(len(registre.by_status(v)) for v in Verdict)
    assert total == len(registre.list()) == 3


def test_to_frame(registre: AlphaRegistry) -> None:
    """(a) Trois lignes, indexées par le nom, listes aplaties en texte."""
    _trois_fiches(registre)
    frame = registre.to_frame()

    assert frame.index.name == "name"
    assert list(frame.index) == [
        "bab_frazzini_2014",
        "tsmom_moskowitz_2012",
        "xsmom_jegadeesh_1993",
    ]
    assert frame.loc["bab_frazzini_2014", "family"] == "portage"
    # (a) Les deux mécanismes de la fiche type, joints par le séparateur déclaré.
    assert (
        frame.loc["tsmom_moskowitz_2012", "economic_rationale"]
        == "contrainte institutionnelle ; biais comportemental"
    )
    assert frame.loc["tsmom_moskowitz_2012", "asset_classes"] == "equity_index ; bond"
    assert frame.loc["xsmom_jegadeesh_1993", "validation_status"] == "EXPERIMENTAL"


def test_les_champs_listes_aplatis_sont_tous_ceux_du_modele() -> None:
    """(b) Contrat déclaré : ``to_frame`` aplatit toute liste, et rien d'autre.

    La liste des champs aplatis est écrite à la main dans le module. Un champ
    de type liste ajouté plus tard sans y être inscrit ressortirait du tableau
    sous forme d'objet Python, et le contrôle le voit.
    """
    attendus = {
        nom for nom, champ in AlphaMetadata.model_fields.items() if get_origin(champ.annotation) is list
    }
    assert attendus == set(CHAMPS_LISTES)


def test_to_frame_vide_garde_ses_colonnes(registre: AlphaRegistry) -> None:
    """(b) Cas limite : un registre vide rend un tableau vide, mais typé.

    Sans les colonnes, tout code de lecture en aval échouerait sur le cas du
    dépôt frais, qui est le premier qu'il rencontre.
    """
    frame = registre.to_frame()

    assert len(frame) == 0
    assert frame.index.name == "name"
    assert "validation_status" in frame.columns
    assert "economic_rationale" in frame.columns


# --------------------------------------------------------------------------
# La classe de base d'une stratégie
# --------------------------------------------------------------------------


class SigneDuRendement(Strategy):
    """Stratégie factice : le signe du rendement, réparti à parts égales."""

    def generate_signal(self, data: pd.DataFrame) -> pd.DataFrame:
        """Rend le signe de chaque rendement observé."""
        return np.sign(data)

    def to_weights(self, signal: pd.DataFrame) -> pd.DataFrame:
        """Répartit un levier brut de un sur les positions non nulles."""
        brut = signal.abs().sum(axis=1)
        return signal.div(brut.where(brut != 0), axis=0).fillna(0.0)


# Quatre séances, deux actifs. Les signes sont lisibles à l'œil.
RENDEMENTS = pd.DataFrame(
    {
        "SPY": [0.01, -0.02, 0.03, -0.04],
        "TLT": [-0.01, -0.01, 0.02, 0.00],
    },
    index=pd.date_range("2026-01-05", periods=4, freq="B"),
)


def test_strategie_satisfait_le_protocole_alpha_model() -> None:
    """(b) Contrat structurel : le protocole exige ``name`` et ``predict``."""
    strategie = SigneDuRendement(fiche())
    assert isinstance(strategie, AlphaModel)


def test_un_objet_sans_predict_ne_satisfait_pas_le_protocole() -> None:
    """(b) Le contrôle du protocole discrimine, donc le test précédent dit quelque chose."""
    assert not isinstance(object(), AlphaModel)


def test_le_nom_de_la_strategie_vient_de_la_fiche() -> None:
    """(b) Le nom du protocole et le nom de la fiche sont le même."""
    strategie = SigneDuRendement(fiche())
    assert strategie.name == "tsmom_moskowitz_2012"
    assert strategie.metadata.family == "momentum"


def test_strategy_est_abstraite() -> None:
    """(b) Les deux méthodes sont abstraites, donc la classe ne s'instancie pas."""
    with pytest.raises(TypeError, match="abstract"):
        Strategy(fiche())  # type: ignore[abstract]


def test_predict_rend_la_derniere_ligne_du_signal() -> None:
    """(a) Calcul à la main sur la dernière séance du tableau de rendements.

    Le 8 janvier 2026, SPY rend -0,04 et TLT rend 0,00. Les signes valent donc
    -1 et 0, et la série porte le nom de la date.
    """
    scores = SigneDuRendement(fiche()).predict(RENDEMENTS)

    assert list(scores.index) == ["SPY", "TLT"]
    assert scores["SPY"] == pytest.approx(-1.0)
    assert scores["TLT"] == pytest.approx(0.0)
    assert scores.name == pd.Timestamp("2026-01-08")


def test_predict_refuse_un_index_desordonne() -> None:
    """(a) Contre-exemple à la main sur un tableau rendu du plus récent au plus ancien.

    Retourné, le tableau met le 5 janvier en dernière position. Sans contrôle,
    ``predict`` rendrait les signes de cette séance, soit +1 et -1, sous le nom
    d'une prévision courante, alors que la dernière séance donne -1 et 0.
    """
    a_l_envers = RENDEMENTS.iloc[::-1]
    # (a) La dernière ligne du tableau retourné porte bien la plus vieille date.
    assert a_l_envers.index[-1] == pd.Timestamp("2026-01-05")

    with pytest.raises(DataQualityError, match="trié"):
        SigneDuRendement(fiche()).predict(a_l_envers)


def test_predict_sur_signal_vide() -> None:
    """(b) Cas limite : aucune ligne, donc une erreur nommée plutôt qu'un NaN."""
    vide = RENDEMENTS.iloc[:0]
    with pytest.raises(InsufficientDataError, match="aucune ligne"):
        SigneDuRendement(fiche()).predict(vide)


def test_to_weights_a_la_main() -> None:
    """(a) Calcul à la main sur la première séance : deux positions actives.

    SPY vaut +1 et TLT vaut -1, donc le brut vaut 2, et les poids ressortent à
    +0,5 et -0,5. Le levier brut vaut alors exactement un.
    """
    strategie = SigneDuRendement(fiche())
    poids = strategie.to_weights(strategie.generate_signal(RENDEMENTS))

    assert poids.iloc[0]["SPY"] == pytest.approx(0.5)
    assert poids.iloc[0]["TLT"] == pytest.approx(-0.5)
    # (a) Troisième séance : les deux rendements sont positifs, donc +0,5 chacun.
    assert poids.iloc[2]["SPY"] == pytest.approx(0.5)
    assert poids.iloc[2]["TLT"] == pytest.approx(0.5)
    # (b) Identité : le levier brut vaut un sur toute séance où une position existe.
    assert poids.abs().sum(axis=1).to_numpy() == pytest.approx([1.0, 1.0, 1.0, 1.0])


def test_to_weights_sur_signal_nul() -> None:
    """(b) Cas limite : un signal entièrement nul rend des poids nuls, pas des NaN."""
    strategie = SigneDuRendement(fiche())
    plat = pd.DataFrame(0.0, index=RENDEMENTS.index, columns=RENDEMENTS.columns)
    poids = strategie.to_weights(strategie.generate_signal(plat))

    assert not poids.isna().to_numpy().any()
    assert poids.to_numpy() == pytest.approx(np.zeros((4, 2)))


# --------------------------------------------------------------------------
# Propriété
# --------------------------------------------------------------------------

_NOMS = st.from_regex(r"\A[a-z0-9][a-z0-9_]{0,20}\Z")
_MECANISMES = st.lists(st.sampled_from(sorted(ECONOMIC_RATIONALES)), min_size=1, unique=True)
_CLASSES = st.lists(st.sampled_from(sorted(AssetClass)), min_size=1, unique=True)

#: Les notes tirées excluent les caractères de contrôle et les deux séparateurs
#: de ligne d'Unicode. La raison est mesurée, pas préventive : PyYAML relit
#: U+0085 comme une espace, et ``to_yaml`` refuse désormais une telle note.
#: ``test_note_non_relisible_refusee`` couvre ce cas, hors de la propriété.
_NOTES = st.text(
    alphabet=st.characters(exclude_categories=("Cc", "Cs", "Zl", "Zp")),
    max_size=60,
)


@given(
    name=_NOMS,
    mecanismes=_MECANISMES,
    classes=_CLASSES,
    verdict=st.sampled_from(sorted(Verdict)),
    notes=_NOTES,
)
@settings(max_examples=60, deadline=None)
def test_propriete_aller_retour_yaml(
    name: str,
    mecanismes: list[str],
    classes: list[AssetClass],
    verdict: Verdict,
    notes: str,
) -> None:
    """(b) Identité d'aller-retour : ``model_validate(safe_load(to_yaml(f))) == f``.

    La propriété tient pour toute fiche valide, quels que soient le nom, les
    mécanismes, les classes visées, le verdict et les notes.
    """
    origine = fiche(
        name=name,
        economic_rationale=mecanismes,
        asset_classes=classes,
        validation_status=verdict,
        notes=notes,
    )
    relue = AlphaMetadata.model_validate(yaml.safe_load(origine.to_yaml()))
    assert relue == origine
