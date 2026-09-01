"""La configuration : aucun paramètre important ne vit dans le code.

**Le problème.** Un nombre écrit en dur dans une fonction est un nombre que
personne ne retrouvera. Six mois après, la question « avec quelle fenêtre ce
résultat a-t-il été produit ? » n'a plus de réponse, et l'expérience n'est plus
reproductible même si le code n'a pas bougé.

**Le remède.** Tout paramètre de recherche vit dans un fichier YAML versionné,
validé par Pydantic au chargement. Une clé inconnue est une erreur, pas un
avertissement : c'est ainsi qu'une faute de frappe dans ``lookback_month`` cesse
de passer pour un paramètre par défaut silencieux.

Deux niveaux se distinguent :

- les **réglages d'environnement** (:class:`Settings`), qui changent d'une
  machine à l'autre et ne sont jamais commités : chemins, en-tête HTTP, clés ;
- les **configurations de recherche** (:class:`ExperimentConfig` et ses parties),
  qui décrivent une expérience et sont commitées avec elle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from quantlab.core.errors import ConfigError
from quantlab.core.types import Frequency


class StrictModel(BaseModel):
    """Modèle de base : toute clé inconnue est refusée.

    ``extra="forbid"`` est le réglage qui fait le travail. Sans lui, une
    configuration qui contient ``lookbak_months: 12`` se charge sans bruit, la
    faute de frappe passe inaperçue, et l'expérience tourne avec la valeur par
    défaut sans que rien ne le signale.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class Settings(BaseSettings):
    """Les réglages d'environnement, lus dans ``.env`` ou l'environnement.

    Ces valeurs ne décrivent aucune décision de recherche : elles disent où sont
    les fichiers et comment se présenter aux serveurs. Elles ne se commitent
    jamais.
    """

    model_config = SettingsConfigDict(env_prefix="QUANTLAB_", env_file=".env", extra="ignore", frozen=True)

    #: Identification envoyée aux serveurs qui l'exigent. La SEC refuse les
    #: requêtes sans en-tête d'identification, et son refus est un 403 muet.
    user_agent: str = "quantlab research (contact: set QUANTLAB_USER_AGENT)"
    #: Clé FRED, facultative : l'export CSV de fredgraph fonctionne sans clé.
    fred_api_key: str | None = None
    #: Pause minimale entre deux requêtes vers un même hôte, en secondes.
    request_delay_s: float = 0.2
    #: Nombre de relances sur erreur réseau transitoire.
    max_retries: int = 3
    log_level: str = "INFO"


class DataConfig(StrictModel):
    """Quelles données, sur quelle période, à quelle fréquence."""

    provider: str = Field(description="Nom du fournisseur, par exemple « yahoo ».")
    universe: list[str] = Field(description="Les identifiants demandés au fournisseur.")
    start: str = Field(description="Première date incluse, au format ISO.")
    end: str = Field(description="Dernière date incluse, au format ISO.")
    frequency: Frequency = Frequency.DAILY
    calendar: str = Field(default="XNYS", description="Calendrier d'échange de référence.")
    price_field: str = Field(default="adj_close", description="Colonne de prix retenue.")

    @field_validator("universe")
    @classmethod
    def _universe_non_vide(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("l'univers ne peut pas être vide")
        if len(set(v)) != len(v):
            raise ValueError("l'univers contient des doublons")
        return v

    @model_validator(mode="after")
    def _dates_ordonnees(self) -> DataConfig:
        if self.start >= self.end:
            raise ValueError(f"start ({self.start}) doit précéder end ({self.end})")
        return self


class CostConfig(StrictModel):
    """Les hypothèses de coût, en points de base sauf mention contraire.

    Chaque composante est séparée et désactivable. Un backtest qui ne dit pas
    quelles composantes il a activées est un backtest dont le rendement net ne
    veut rien dire.
    """

    commission_bps: float = Field(default=0.0, ge=0, description="Commission par côté négocié.")
    spread_bps: float = Field(default=0.0, ge=0, description="Demi-écart acheteur-vendeur payé.")
    slippage_bps: float = Field(default=0.0, ge=0, description="Glissement fixe supplémentaire.")
    impact_model: str | None = Field(default=None, description="« sqrt » ou rien.")
    impact_coefficient: float = Field(default=1.0, ge=0, description="Coefficient du modèle d'impact.")
    borrow_bps_annual: float = Field(default=0.0, ge=0, description="Coût d'emprunt de titre annuel.")
    financing_spread_bps_annual: float = Field(
        default=0.0, ge=0, description="Écart de financement au-dessus du taux sans risque."
    )


class RiskConfig(StrictModel):
    """Les contraintes de risque, toutes déclarées, aucune implicite."""

    vol_target_annual: float | None = Field(default=None, gt=0, description="Volatilité cible.")
    leverage_cap: float = Field(default=1.0, gt=0, description="Levier brut maximal.")
    leverage_floor: float = Field(default=0.0, ge=0, description="Levier brut minimal.")
    max_position: float | None = Field(default=None, gt=0, description="Poids absolu maximal.")
    max_gross_exposure: float | None = Field(default=None, gt=0)
    max_net_exposure: float | None = Field(default=None, ge=0)
    max_adv_participation: float | None = Field(
        default=None, gt=0, description="Part maximale du volume quotidien moyen."
    )

    @model_validator(mode="after")
    def _bornes_coherentes(self) -> RiskConfig:
        if self.leverage_floor > self.leverage_cap:
            raise ValueError("leverage_floor dépasse leverage_cap")
        return self


class ValidationConfig(StrictModel):
    """Le découpage du temps, et la frontière de la preuve.

    ``final_holdout_start`` marque la limite au-delà de laquelle les données ne
    doivent jamais servir à choisir un paramètre. Un chiffre calculé après avoir
    regardé cet échantillon n'est plus hors échantillon, et le laboratoire tient
    le compte du nombre de fois où il a été consulté.
    """

    train_end: str
    validation_end: str
    final_holdout_start: str | None = None
    embargo_periods: int = Field(default=0, ge=0)
    purge_periods: int = Field(default=0, ge=0)
    n_folds: int = Field(default=10, ge=2)
    n_test_folds: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def _ordre_du_temps(self) -> ValidationConfig:
        if self.train_end >= self.validation_end:
            raise ValueError("train_end doit précéder validation_end")
        if self.final_holdout_start and self.final_holdout_start < self.validation_end:
            raise ValueError("le holdout final ne peut pas empiéter sur la validation")
        if self.n_test_folds >= self.n_folds:
            raise ValueError("n_test_folds doit être strictement inférieur à n_folds")
        return self


class ExperimentConfig(StrictModel):
    """La configuration complète d'une expérience reproductible."""

    name: str
    hypothesis: str = Field(description="L'hypothèse économique, en une phrase falsifiable.")
    paper: str | None = Field(default=None, description="La référence académique répliquée.")
    seed: int = Field(default=20260901, description="Graine des tirages aléatoires.")
    data: DataConfig
    costs: CostConfig = CostConfig()
    risk: RiskConfig = RiskConfig()
    validation: ValidationConfig | None = None
    params: dict[str, Any] = Field(default_factory=dict, description="Paramètres propres à l'étude.")


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Lit un YAML et rend un dictionnaire, ou lève une :class:`ConfigError`."""
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"configuration introuvable : {p}")
    try:
        content = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML illisible dans {p} : {exc}") from exc
    if content is None:
        raise ConfigError(f"configuration vide : {p}")
    if not isinstance(content, dict):
        raise ConfigError(f"la racine de {p} doit être un dictionnaire, pas {type(content).__name__}")
    return content


def load_config[T: BaseModel](path: str | Path, model: type[T]) -> T:
    """Charge un YAML et le valide contre un modèle Pydantic.

    Args:
        path: le chemin du fichier.
        model: la classe attendue, par exemple :class:`ExperimentConfig`.

    Returns:
        L'instance validée, gelée.

    Raises:
        ConfigError: si le fichier manque, si le YAML est illisible, ou si une
            clé est inconnue, manquante ou du mauvais type.
    """
    raw = load_yaml(path)
    try:
        return model.model_validate(raw)
    except Exception as exc:
        raise ConfigError(f"configuration invalide dans {path} :\n{exc}") from exc


def get_settings() -> Settings:
    """Rend les réglages d'environnement du processus."""
    return Settings()
