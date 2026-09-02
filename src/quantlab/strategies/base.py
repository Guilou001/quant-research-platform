"""La classe de base d'une stratégie, et le registre des alphas.

**Le problème.** Une idée de stratégie se raconte en une phrase, et cette phrase
disparaît dès que le code existe. Six mois plus tard, il reste un backtest et un
ratio de Sharpe, mais plus personne ne sait quel mécanisme économique était
censé produire le rendement. Sans ce mécanisme, un résultat flatteur ne se
distingue plus d'un accident de fouille : les deux ont la même tête.

**Le remède.** Une stratégie n'entre dans le laboratoire qu'accompagnée d'une
fiche, et la fiche nomme au moins un mécanisme. Le champ ``economic_rationale``
ne peut pas être vide, et ses valeurs sont prises dans un ensemble déclaré. Le
choix de fermer cet ensemble est délibéré : un champ libre accepterait
« le marché est inefficient », qui n'est pas un mécanisme mais un constat.

Les quatre mécanismes admis viennent de la littérature de réplication, en
particulier de Harvey, Liu et Zhu (2016), qui montrent que le nombre de facteurs
publiés dépasse ce qu'un contrôle de tests multiples autorise :

``prime de risque``
    Le rendement paie un risque que quelqu'un refuse de porter.
``biais comportemental``
    Le prix s'écarte de la valeur par une erreur systématique de jugement.
``contrainte institutionnelle``
    Une règle interdit à un intervenant l'arbitrage qui refermerait l'écart.
``friction``
    Le coût de l'arbitrage dépasse le gain qu'il rapporterait.

**Le second garde-fou.** ``AlphaRegistry.update_status`` refuse de poser
``ROBUST`` ou ``PORTFOLIO_CANDIDATE`` sans identifiant d'expérience. Un verdict
se déduit des contrôles qui ont tourné, et l'identifiant est le lien vers ces
contrôles dans ``quantlab.experiments``. Les trois autres verdicts se posent
sans preuve attachée, parce qu'ils n'en promettent aucune.

Un exemple de fiche complète, celle du momentum de série temporelle :

.. code-block:: yaml

    name: tsmom_moskowitz_2012
    family: momentum

    paper: "Moskowitz, Ooi et Pedersen (2012), « Time Series Momentum », JFE 104(2)"

    asset_classes:
      - equity_index
      - bond
      - fx
      - commodity

    horizon: "formation 12 mois, détention 1 mois"

    economic_rationale:
      - contrainte institutionnelle
      - biais comportemental

    inputs:
      - prix de clôture ajustés quotidiens
      - volatilité réalisée à 60 jours

    known_risks:
      - retournement brutal de tendance
      - concentration du risque sur une seule classe d'actif

    validation_status: EXPERIMENTAL
    verdict_experiment_id: null

    created: 2026-09-01
    last_modified: 2026-09-02

    notes: "Réplication non commencée au 2026-09-02."

Les fiches vivent dans ``configs/strategies/``, une par fichier, nommées d'après
le champ ``name``. Elles se versionnent avec le code, se relisent dans une revue,
et n'exigent aucun serveur.
"""

from __future__ import annotations

import datetime as dt
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import yaml
from pydantic import Field, field_validator

from quantlab.core.config import StrictModel, load_config
from quantlab.core.errors import (
    ConfigError,
    DataQualityError,
    InsufficientDataError,
    NotReplicatedError,
    QuantLabError,
)
from quantlab.core.logging import get_logger
from quantlab.core.paths import configs_dir, ensure
from quantlab.core.types import AssetClass, Verdict, WeightFrame

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "ECONOMIC_RATIONALES",
    "EVIDENCE_BACKED_VERDICTS",
    "REGISTRY_DIRNAME",
    "AlphaMetadata",
    "AlphaRegistry",
    "Strategy",
    "load_registry",
    "save_registry",
]

_log = get_logger(__name__)

#: Les quatre mécanismes économiques admis dans une fiche d'alpha. La liste est
#: fermée pour empêcher le champ libre, qui accepterait une reformulation du
#: résultat à la place de sa cause.
ECONOMIC_RATIONALES: frozenset[str] = frozenset(
    {
        "prime de risque",
        "biais comportemental",
        "contrainte institutionnelle",
        "friction",
    }
)

#: Les verdicts qui affirment qu'un contrôle a tourné, donc ceux qui exigent un
#: identifiant d'expérience pour être posés.
EVIDENCE_BACKED_VERDICTS: frozenset[Verdict] = frozenset({Verdict.ROBUST, Verdict.PORTFOLIO_CANDIDATE})

#: Le sous-répertoire de ``configs/`` où vivent les fiches.
REGISTRY_DIRNAME = "strategies"

#: Le nom d'une fiche sert de nom de fichier. Le restreindre évite qu'un nom
#: porteur de « ../ » écrive hors du registre. L'ancre de fin est ``\Z`` et non
#: ``$`` : en Python, ``$`` matche aussi devant un saut de ligne final, si bien
#: que le nom « tsmom\n » passerait et écrirait un fichier « tsmom\n.yaml ».
_NOM_VALIDE = re.compile(r"\A[a-z0-9][a-z0-9_]*\Z")

#: Les champs dont la valeur est une liste, aplatis en texte par ``to_frame``.
_CHAMPS_LISTES = ("asset_classes", "economic_rationale", "inputs", "known_risks")

#: Le séparateur employé pour aplatir ces listes dans un tableau de lecture.
_SEPARATEUR_LISTE = " ; "


class AlphaMetadata(StrictModel):
    """La fiche d'un alpha : ce qu'il prétend capter, et sur quelle preuve.

    Le modèle est gelé et refuse toute clé inconnue, comme tout descendant de
    :class:`~quantlab.core.config.StrictModel`. Une fiche mal orthographiée ne
    se charge pas, plutôt que de se charger avec des valeurs par défaut que
    personne ne verra.

    La contrainte qui décide de tout porte sur ``economic_rationale``. Elle
    tient en trois règles. La liste ne peut pas être vide. Chaque entrée
    appartient à :data:`ECONOMIC_RATIONALES`. Les doublons sont refusés, parce
    que citer deux fois le même mécanisme n'en fait pas deux.

    **Pourquoi cette contrainte ici.** Le tri d'une idée coûte quelques minutes
    avant d'écrire le code, et plusieurs jours après. Nommer le mécanisme est le
    seul contrôle du parcours qui ne demande aucune donnée, donc le premier à
    poser.

    **Sa limite.** Elle n'établit pas que le mécanisme existe, seulement qu'un
    mécanisme a été nommé. Une fiche peut invoquer une prime de risque absente
    des données, et seule l'étude le dira. Le filtre est nécessaire, jamais
    suffisant.

    **Comment vérifier.** Construire une fiche sans mécanisme lève une erreur de
    validation Pydantic, et le test ``test_fiche_sans_mecanisme_refusee`` le
    fixe.

    Attributes:
        name: l'identifiant, en minuscules et souligné, qui sert de nom de
            fichier dans le registre.
        family: la famille de l'alpha, par exemple ``momentum`` ou ``value``.
        paper: la référence académique répliquée, ou ``None`` pour une idée
            propre au laboratoire.
        asset_classes: les classes d'actif visées, au moins une.
        horizon: l'horizon de formation et de détention, en clair.
        economic_rationale: les mécanismes invoqués, au moins un.
        inputs: les données consommées, décrites pour un lecteur humain.
        known_risks: ce qui peut faire échouer la stratégie, connu d'avance.
        validation_status: le verdict courant, au sens de
            :class:`~quantlab.core.types.Verdict`.
        verdict_experiment_id: l'expérience qui a produit le verdict courant.
            Reste ``None`` tant qu'aucun contrôle n'a tourné.
        created: la date de création de la fiche.
        last_modified: la date de sa dernière modification.
        notes: le reste, en texte libre.
    """

    name: str = Field(description="Identifiant en minuscules, souligné autorisé.")
    family: str = Field(min_length=1, description="Famille de l'alpha.")
    paper: str | None = Field(default=None, description="Référence académique répliquée.")
    asset_classes: list[AssetClass] = Field(min_length=1, description="Classes d'actif visées.")
    horizon: str = Field(min_length=1, description="Horizon de formation et de détention.")
    economic_rationale: list[str] = Field(min_length=1, description="Mécanismes invoqués.")
    inputs: list[str] = Field(default_factory=list, description="Données consommées.")
    known_risks: list[str] = Field(default_factory=list, description="Risques connus d'avance.")
    validation_status: Verdict = Field(default=Verdict.EXPERIMENTAL, description="Verdict courant.")
    verdict_experiment_id: str | None = Field(
        default=None, description="Expérience qui a produit le verdict courant."
    )
    created: dt.date = Field(description="Date de création de la fiche.")
    last_modified: dt.date = Field(description="Date de dernière modification.")
    notes: str = Field(default="", description="Texte libre.")

    @field_validator("name")
    @classmethod
    def _nom_utilisable_comme_fichier(cls, v: str) -> str:
        """Refuse un nom qui ne peut pas servir de nom de fichier sans risque."""
        if not _NOM_VALIDE.match(v):
            raise ValueError(f"nom invalide : « {v} », attendu en minuscules, chiffres et soulignés")
        return v

    @field_validator("economic_rationale")
    @classmethod
    def _mecanismes_declares(cls, v: list[str]) -> list[str]:
        """Vérifie que chaque mécanisme appartient à l'ensemble déclaré."""
        normalises = [m.strip().lower() for m in v]
        inconnus = sorted(set(normalises) - ECONOMIC_RATIONALES)
        if inconnus:
            admis = ", ".join(sorted(ECONOMIC_RATIONALES))
            raise ValueError(f"mécanisme non déclaré : {inconnus}, admis : {admis}")
        if len(set(normalises)) != len(normalises):
            raise ValueError("le même mécanisme est cité deux fois")
        return normalises

    @field_validator("asset_classes")
    @classmethod
    def _classes_sans_doublon(cls, v: list[AssetClass]) -> list[AssetClass]:
        """Refuse deux fois la même classe d'actif dans une fiche."""
        if len(set(v)) != len(v):
            raise ValueError("la même classe d'actif est citée deux fois")
        return v

    def to_yaml(self) -> str:
        """Rend la fiche en YAML, dans l'ordre de déclaration des champs.

        **Le problème.** YAML 1.1 range trois caractères parmi les fins de
        ligne, dont ``U+0085``. PyYAML écrit ce caractère tel quel quand
        ``allow_unicode`` vaut vrai, puis le relit comme une espace. Une note
        qui en porte un revient donc changée, sans que rien ne le signale.

        **Le remède.** La méthode relit ce qu'elle vient d'écrire et compare.
        Une perte lève :class:`~quantlab.core.errors.ConfigError` au lieu de
        passer inaperçue. Le contrôle coûte une analyse YAML par fiche, sur un
        registre qui en compte quelques dizaines.

        **Comment vérifier.** Le test ``test_note_non_relisible_refusee`` pose
        une note réduite à ``U+0085`` et attend le refus.

        Returns:
            Le texte YAML, encodable en UTF-8, que
            :meth:`AlphaRegistry.register` écrit tel quel sur le disque.

        Raises:
            ConfigError: si la relecture du texte produit ne redonne pas les
                mêmes valeurs, cas d'une perte de caractère à l'écriture.
        """
        payload = self.model_dump(mode="json")
        texte = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False)
        if yaml.safe_load(texte) != payload:
            raise ConfigError(
                f"la fiche « {self.name} » ne survit pas à son écriture en YAML : "
                "un champ porte un caractère que la relecture change"
            )
        return texte


class Strategy(ABC):
    """La classe de base d'une stratégie, et rien de plus.

    Elle porte trois choses : un nom, une fiche, et deux méthodes à écrire. Elle
    ne télécharge rien, ne connaît aucun fournisseur, et n'importe ni
    ``yfinance`` ni ``requests``. La règle est vérifiée mécaniquement par
    ``tests/unit/test_architecture.py``, et c'est elle qui rend une stratégie
    rejouable sur une autre source dans dix ans.

    Le partage du travail entre les deux méthodes abstraites suit ADR-003.
    :meth:`generate_signal` rend une prévision ordonnée, sans unité de position.
    :meth:`to_weights` la convertit en poids, donc décide du levier, de la
    neutralité et du dimensionnement. Confondre les deux revient à cacher une
    décision de portefeuille dans un modèle d'alpha.

    La classe satisfait le protocole
    :class:`~quantlab.core.protocols.AlphaModel` grâce à :meth:`predict`, qui
    rend la dernière ligne du signal. Le protocole est structurel, donc aucune
    stratégie n'a besoin d'hériter de quoi que ce soit pour le satisfaire.

    Args:
        metadata: la fiche de l'alpha, dont le nom devient celui de l'instance.

    Example:
        Une stratégie minimale se réduit à ses deux méthodes.

        .. code-block:: python

            class ToujoursLong(Strategy):
                def generate_signal(self, data):
                    return data.notna().astype(float)

                def to_weights(self, signal):
                    return signal.div(signal.sum(axis=1), axis=0)
    """

    def __init__(self, metadata: AlphaMetadata) -> None:
        self.metadata = metadata
        #: Le nom exigé par le protocole ``AlphaModel``, repris de la fiche.
        self.name: str = metadata.name

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> pd.DataFrame:
        """Rend le signal de la stratégie, lignes = dates, colonnes = actifs.

        Args:
            data: les données d'entrée, indexées par la date d'observation.

        Returns:
            Un tableau de scores. Un score n'est pas une position : son échelle
            est libre, seul son ordre compte.
        """

    @abstractmethod
    def to_weights(self, signal: pd.DataFrame) -> WeightFrame:
        """Convertit le signal en poids de portefeuille.

        Args:
            signal: la sortie de :meth:`generate_signal`.

        Returns:
            Les poids par date. Ils ne somment pas nécessairement à un : un
            portefeuille long-short à somme nulle est légitime.
        """

    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Rend le score par actif à la dernière date disponible.

        C'est la méthode du protocole :class:`~quantlab.core.protocols.AlphaModel`.
        Elle appelle :meth:`generate_signal` et n'en garde que la dernière ligne,
        celle de la date la plus récente.

        **Pourquoi le tri est vérifié ici.** La méthode identifie la dernière
        date par la dernière POSITION. Les deux ne coïncident que sur un index
        trié. Un tableau rendu du plus récent au plus ancien, forme courante
        chez plusieurs fournisseurs, ferait rendre la plus vieille observation
        du lot sous le nom d'une prévision courante.

        Le tri n'est pas une garantie d'absence d'information future : une
        stratégie concrète qui centre une moyenne mobile fuit malgré un index
        trié. Le contrôle ferme un chemin, pas tous.

        Args:
            features: les caractéristiques, indexées par la date.

        Returns:
            La série des scores, indexée par actif, nommée d'après la date.

        Raises:
            InsufficientDataError: si le signal ne porte aucune ligne. Un
                ``NaN`` rendu ici ressortirait en fin de chaîne sans que
                personne sache où il est né.
            DataQualityError: si l'index du signal n'est pas croissant, cas où
                la dernière ligne n'est pas la plus récente.
        """
        signal = self.generate_signal(features)
        if len(signal.index) == 0:
            raise InsufficientDataError(f"la stratégie « {self.name} » ne rend aucune ligne de signal")
        if not signal.index.is_monotonic_increasing:
            raise DataQualityError(
                f"le signal de « {self.name} » n'est pas trié dans le temps : "
                "la dernière ligne ne serait pas la plus récente"
            )
        derniere = signal.index[-1]
        return signal.iloc[-1].rename(derniere)


class AlphaRegistry:
    """Le registre des alphas, adossé à des fichiers YAML versionnés.

    Une fiche par fichier, nommée ``<name>.yaml``, sous ``configs/strategies/``.
    Le choix du fichier plutôt que d'une base de données suit ADR-009 : rien à
    démarrer, rien à synchroniser, et un changement de verdict se lit dans un
    diff.

    Args:
        root: le répertoire des fiches. Par défaut ``configs/strategies/`` sous
            la racine rendue par
            :func:`~quantlab.core.paths.project_root`, qui obéit à la variable
            d'environnement ``QUANTLAB_ROOT``.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else configs_dir() / REGISTRY_DIRNAME

    def path_for(self, name: str) -> Path:
        """Rend le chemin de la fiche portant ce nom, existante ou non.

        Le nom est validé ici, et pas seulement dans
        :class:`AlphaMetadata`. La validation du modèle protège l'ÉCRITURE,
        puisque le nom écrit vient d'une fiche validée. Elle ne protège pas la
        LECTURE : ``get`` reçoit une chaîne quelconque, et sans ce contrôle
        ``get("../secrets")`` lirait un fichier hors du registre.

        Args:
            name: le champ ``name`` cherché.

        Raises:
            ConfigError: si le nom ne peut pas servir de nom de fichier.
        """
        if not _NOM_VALIDE.match(name):
            raise ConfigError(f"nom invalide : « {name} », attendu en minuscules, chiffres et soulignés")
        return self.root / f"{name}.yaml"

    def register(self, metadata: AlphaMetadata, *, overwrite: bool = False) -> Path:
        """Écrit une fiche dans le registre.

        Args:
            metadata: la fiche validée.
            overwrite: autorise l'écrasement d'une fiche du même nom. Faux par
                défaut, pour qu'un second enregistrement distrait ne remplace
                pas un historique de verdicts.

        Returns:
            Le chemin du fichier écrit.

        Raises:
            ConfigError: si une fiche du même nom existe et que
                ``overwrite`` vaut faux.
        """
        cible = self.path_for(metadata.name)
        if cible.exists() and not overwrite:
            raise ConfigError(f"fiche déjà enregistrée : {cible}, passer overwrite=True pour l'écraser")
        ensure(self.root)
        cible.write_text(metadata.to_yaml(), encoding="utf-8")
        _log.info(
            "fiche d'alpha enregistrée",
            extra={"name": metadata.name, "family": metadata.family, "path": str(cible)},
        )
        return cible

    def get(self, name: str) -> AlphaMetadata:
        """Relit une fiche par son nom.

        Args:
            name: le champ ``name`` de la fiche cherchée.

        Returns:
            La fiche validée.

        Raises:
            QuantLabError: si aucune fiche ne porte ce nom.
            ConfigError: si le fichier existe mais ne valide pas.
        """
        cible = self.path_for(name)
        if not cible.is_file():
            raise QuantLabError(f"alpha inconnu du registre : « {name} » (cherché dans {self.root})")
        return load_config(cible, AlphaMetadata)

    def list(self) -> list[AlphaMetadata]:
        """Rend toutes les fiches du registre, triées par nom.

        Returns:
            La liste des fiches. Vide quand le répertoire n'existe pas encore,
            ce qui est l'état d'un dépôt frais et non une erreur.

        Le nom du fichier doit répéter le champ ``name``. Sans ce contrôle, une
        fiche déposée à la main sous un autre nom de fichier apparaîtrait dans
        cette liste alors que :meth:`get` la déclarerait inconnue, et le
        registre se contredirait selon la méthode appelée.

        Raises:
            ConfigError: si l'une des fiches présentes ne valide pas, ou si son
                nom de fichier ne répète pas son champ ``name``. Le registre
                échoue en entier plutôt que de rendre une vue partielle.
        """
        if not self.root.is_dir():
            return []
        fiches: list[AlphaMetadata] = []
        for chemin in sorted(self.root.glob("*.yaml")):
            fiche = load_config(chemin, AlphaMetadata)
            if chemin.stem != fiche.name:
                raise ConfigError(
                    f"nom de fichier trompeur : {chemin.name} porte la fiche « {fiche.name} », "
                    "que le registre chercherait ailleurs"
                )
            fiches.append(fiche)
        return sorted(fiches, key=lambda f: f.name)

    def by_family(self, family: str) -> list[AlphaMetadata]:
        """Rend les fiches d'une famille, triées par nom.

        Args:
            family: la famille cherchée, comparée sans tenir compte de la casse.
        """
        cible = family.strip().lower()
        return [f for f in self.list() if f.family.strip().lower() == cible]

    def by_status(self, status: Verdict | str) -> list[AlphaMetadata]:
        """Rend les fiches portant un verdict donné, triées par nom.

        Args:
            status: le verdict cherché, sous forme d'énumération ou de chaîne.

        Raises:
            ValueError: si la chaîne ne correspond à aucun verdict.
        """
        cible = Verdict(status)
        return [f for f in self.list() if f.validation_status is cible]

    def update_status(
        self,
        name: str,
        status: Verdict | str,
        *,
        experiment_id: str | None = None,
        today: dt.date | None = None,
    ) -> AlphaMetadata:
        """Change le verdict d'une fiche, et exige une preuve quand il en promet une.

        **La règle.** ``ROBUST`` et ``PORTFOLIO_CANDIDATE`` affirment qu'un
        contrôle a tourné : coûts, sous-périodes et hors échantillon pour le
        premier, apport au portefeuille existant pour le second. Les poser sans
        identifiant d'expérience reviendrait à déclarer le résultat plutôt qu'à
        le mesurer, donc le registre refuse.

        **Ce que la règle n'attrape pas.** Elle vérifie qu'un identifiant est
        fourni, pas que l'expérience correspondante conclut dans ce sens. Le
        lien vers ``quantlab.experiments`` reste à la charge de l'appelant, et
        la fiche garde l'identifiant pour que la vérification soit possible.

        Args:
            name: la fiche à modifier.
            status: le nouveau verdict.
            experiment_id: l'expérience qui l'établit. Obligatoire pour les
                verdicts de :data:`EVIDENCE_BACKED_VERDICTS`.
            today: la date portée dans ``last_modified``. Le jour courant par
                défaut, l'argument existant pour rendre les tests déterministes.

        Returns:
            La fiche mise à jour, telle qu'elle vient d'être écrite.

        Raises:
            NotReplicatedError: si un verdict adossé à une preuve est posé sans
                identifiant d'expérience.
            QuantLabError: si la fiche est inconnue.
        """
        verdict = Verdict(status)
        if verdict in EVIDENCE_BACKED_VERDICTS and not experiment_id:
            raise NotReplicatedError(
                f"poser {verdict.value} sur « {name} » exige un identifiant d'expérience : "
                "un verdict se déduit des contrôles qui ont tourné"
            )
        fiche = self.get(name)
        payload = fiche.model_dump(mode="json")
        payload["validation_status"] = verdict.value
        payload["verdict_experiment_id"] = experiment_id
        payload["last_modified"] = (today or dt.date.today()).isoformat()
        mise_a_jour = AlphaMetadata.model_validate(payload)
        self.register(mise_a_jour, overwrite=True)
        _log.info(
            "verdict mis à jour",
            extra={"name": name, "verdict": verdict.value, "experiment_id": experiment_id},
        )
        return mise_a_jour

    def to_frame(self) -> pd.DataFrame:
        """Rend le registre sous forme de tableau, une ligne par fiche.

        Les champs de type liste sont aplatis en texte, séparés par un point
        virgule, parce que ce tableau sert à lire et à filtrer. Le tableau
        gardé pour un calcul se reconstruit depuis :meth:`list`.

        Returns:
            Un tableau indexé par le nom de la fiche. Vide, mais muni de ses
            colonnes, quand le registre ne contient rien.
        """
        colonnes = [c for c in AlphaMetadata.model_fields if c != "name"]
        lignes: list[dict[str, object]] = []
        for fiche in self.list():
            payload = fiche.model_dump(mode="json")
            for champ in _CHAMPS_LISTES:
                payload[champ] = _SEPARATEUR_LISTE.join(payload[champ])
            lignes.append(payload)
        frame = pd.DataFrame(lignes, columns=["name", *colonnes])
        return frame.set_index("name")


def load_registry(root: Path | str | None = None) -> dict[str, AlphaMetadata]:
    """Charge toutes les fiches du registre, indexées par leur nom.

    Args:
        root: le répertoire des fiches. Par défaut ``configs/strategies/``.

    Returns:
        Le dictionnaire des fiches. Vide quand le registre n'existe pas encore.

    Raises:
        ConfigError: si l'une des fiches ne valide pas.
    """
    return {fiche.name: fiche for fiche in AlphaRegistry(root).list()}


def save_registry(
    fiches: Iterable[AlphaMetadata],
    root: Path | str | None = None,
) -> list[Path]:
    """Écrit une collection de fiches dans le registre, en écrasant les homonymes.

    L'écrasement est ici le comportement voulu, à l'inverse de
    :meth:`AlphaRegistry.register` : la fonction sert à réécrire un registre
    entier après une transformation, et non à en ajouter une fiche.

    Args:
        fiches: les fiches à écrire.
        root: le répertoire cible. Par défaut ``configs/strategies/``.

    Returns:
        Les chemins écrits, dans l'ordre de passage.

    Raises:
        ConfigError: si deux fiches portent le même nom, cas où la seconde
            effacerait la première en silence.
    """
    registre = AlphaRegistry(root)
    chemins: list[Path] = []
    vus: set[str] = set()
    for fiche in fiches:
        if fiche.name in vus:
            raise ConfigError(f"deux fiches portent le nom « {fiche.name} »")
        vus.add(fiche.name)
        chemins.append(registre.register(fiche, overwrite=True))
    return chemins
