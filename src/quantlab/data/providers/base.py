r"""Le socle commun des fournisseurs : HTTP poli, cache brut, provenance.

**Le problème.** Un téléchargement mal élevé se fait couper, et un téléchargement
non conservé se perd. Les deux détruisent la même chose, la reproductibilité.
Une étude qui ne garde pas l'octet exact reçu ce jour-là ne peut plus prouver ce
que la source disait. Une source qui bannit l'adresse, elle, ne rend plus rien
du tout.

**Le remède.** Trois règles tenues par ce module.

1. Une seule porte de sortie réseau, :class:`HttpClient`, qui s'identifie,
   espace ses requêtes par hôte, relance les pannes transitoires et journalise
   chaque appel avec son code, sa durée et sa taille.
2. Une seule copie de vérité, le fichier brut de ``data/raw/<fournisseur>/``,
   écrit avant tout parsage. Il ne se réécrit jamais en silence : un nouveau
   téléchargement crée un nouveau fichier horodaté, et une réécriture de contenu
   différent au même instant lève une erreur.
3. Une empreinte SHA-256 sur chaque réponse, vérifiée à la relecture. Un fichier
   altéré se signale au lieu de se propager.

**Pourquoi la SEC répond 403 sans en-tête d'identification.** Le service EDGAR
exige un ``User-Agent`` nominatif portant une adresse de courriel, et refuse par
un 403 les requêtes qui n'en portent pas. Le refus ne dit jamais laquelle de ses
règles a joué, ce qui rend le diagnostic difficile.

Faits mesurés depuis cet environnement. Le 2026-08-29, tout le domaine
``sec.gov`` répondait 403 « Request Rate Threshold Exceeded », ``data.sec.gov``
compris, avec un en-tête d'identification, sur sept relances en vingt minutes.
Le 2026-09-01, l'adresse ``https://www.sec.gov/robots.txt`` répond selon
l'en-tête envoyé, chaque essai espacé de deux à trois secondes :

- en-tête laissé au défaut de la bibliothèque cliente : 403 ;
- ``Mozilla/5.0`` : 403 ;
- ``quantlab research (https://github.com/Guilou001/...)`` : 403 ;
- ``quantlab research (contact@example.com)`` : 200 ;
- ``quantlab research (contact@uqam.ca)`` : 200 ;
- ``quantlab research (a+b@example.com)`` : 200 ;
- ``quantlab research (contact@github.com)`` : 403 ;
- ``quantlab research (contact@users.noreply.github.com)`` : 403.

Trois conclusions en sortent. La première : le blocage du 2026-08-29 était un
débit et non une politique visant l'adresse, puisque la même machine obtient un
200 aujourd'hui. La deuxième : une adresse web ne suffit pas, il faut un
courriel, et ce module ne l'exige qu'à la demande, par l'argument
``require_email``. La troisième n'est annoncée par aucune documentation. Le
refus dépend du DOMAINE du courriel envoyé : ``github.com`` et
``users.noreply.github.com`` reçoivent un 403 là où ``example.com`` et
``uqam.ca`` reçoivent un 200. Les en-têtes ne différaient que par ce domaine, et
chaque cas a été refait deux fois. La cause de ce tri n'est pas publiée, et elle
est déclarée non trouvée.

La règle opérationnelle qui en découle : s'identifier par un courriel dont le
domaine répond, et espacer les requêtes par défaut.

Statut des chiffres de ce module : les huit codes ci-dessus sont mesurés le
2026-09-01 par appels directs depuis cet environnement, et le 403 du 2026-08-29
est rapporté depuis le journal du portefeuille. Les valeurs par défaut de pause
et de relance sont des préceptes, repris des usages de client HTTP, sans mesure
derrière.

Example:
    .. code-block:: python

        client = HttpClient(settings=get_settings())
        raw = client.get("https://www.sec.gov/robots.txt")
        empreinte, taille = raw.sha256, raw.size_bytes
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlsplit

import requests

from quantlab.core.config import Settings, get_settings
from quantlab.core.errors import ConfigError, DataQualityError, QuantLabError
from quantlab.core.logging import get_logger
from quantlab.core.paths import Layer, data_dir, ensure

if TYPE_CHECKING:
    import pandas as pd

    from quantlab.data.manifest import DatasetManifest

__all__ = [
    "DEFAULT_BACKOFF_BASE_S",
    "DEFAULT_BACKOFF_CAP_S",
    "DEFAULT_TIMEOUT_S",
    "RETAINED_HEADERS",
    "RETRYABLE_STATUSES",
    "BaseProvider",
    "HostThrottle",
    "HttpClient",
    "ProviderError",
    "RateLimitError",
    "RawResponse",
    "SourceUnavailableError",
    "cache_key",
    "check_user_agent",
    "throttle",
]

_log = get_logger(__name__)

#: Délai d'attente d'une requête, en secondes. Précepte : au-delà, une source
#: qui ne répond pas est traitée comme indisponible plutôt qu'attendue.
DEFAULT_TIMEOUT_S: float = 30.0

#: Base de la pause exponentielle entre deux tentatives, en secondes. Précepte.
DEFAULT_BACKOFF_BASE_S: float = 0.5

#: Plafond de la pause exponentielle, en secondes. Précepte.
DEFAULT_BACKOFF_CAP_S: float = 60.0

#: Codes HTTP considérés comme transitoires, donc relançables. 429 est la
#: limitation de débit, les quatre autres sont des pannes de serveur ou de
#: passerelle. Un 403 n'y figure pas : il se corrige par l'en-tête, pas par
#: l'attente.
RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

#: En-têtes conservés dans la provenance. Les autres sont écartés parce qu'ils
#: décrivent la connexion plutôt que la donnée.
RETAINED_HEADERS: tuple[str, ...] = (
    "content-type",
    "content-length",
    "date",
    "etag",
    "last-modified",
)

#: Marqueur du ``User-Agent`` par défaut de :class:`Settings`, qui n'identifie
#: personne et doit être remplacé avant toute sortie réseau.
_PLACEHOLDER_MARKER = "set QUANTLAB_USER_AGENT"

#: Motif d'une adresse de courriel : du texte, une arobase, un domaine pointé.
#: Contrôle de forme, pas de validité RFC 5322, qu'aucune expression régulière
#: raisonnable ne couvre.
_EMAIL_PATTERN = re.compile(r"[^\s@<>()\[\]]+@[^\s@<>()\[\],]+\.[A-Za-z]{2,}")

#: Longueur minimale d'un ``User-Agent`` jugé identifiant. Seuil de forme, pas
#: de contenu : il écarte « q » et « test », pas une adresse plausible.
_MIN_USER_AGENT_LENGTH = 10

_SAFE_SLUG_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_.")

#: Longueur du préfixe lisible d'une clé de cache.
_SLUG_MAX_LENGTH = 40

#: Longueur de l'empreinte tronquée qui distingue deux requêtes dans une clé.
_KEY_DIGEST_LENGTH = 16

#: Longueur de l'empreinte tronquée qui distingue deux contenus dans un nom de
#: fichier. Huit caractères hexadécimaux donnent 4,3 milliards de valeurs, assez
#: pour départager deux téléchargements de la même microseconde.
_FILE_DIGEST_LENGTH = 8

#: Format de l'horodatage écrit dans le nom d'un fichier brut. La microseconde y
#: figure pour une raison mesurée : à la seconde près, deux téléchargements
#: séparés d'une demi-seconde recevaient le même horodatage, et le tri par nom
#: retombait alors sur l'empreinte, donc sur un ordre sans rapport avec le temps.
#: La relecture rendait le plus ancien des deux.
_STAMP_FORMAT = "%Y%m%dT%H%M%S%fZ"


# --------------------------------------------------------------------------- #
# Erreurs
# --------------------------------------------------------------------------- #


class ProviderError(QuantLabError):
    """Un fournisseur n'a pas pu rendre la donnée demandée.

    Attributes:
        url: l'adresse appelée, quand elle est connue.
        status_code: le code HTTP reçu, quand il y en a un.
    """

    def __init__(self, message: str, *, url: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class RateLimitError(ProviderError):
    """La source limite le débit et refuse encore après toutes les relances.

    Elle se distingue de :class:`SourceUnavailableError` parce que la correction
    est différente : ralentir plutôt que réessayer plus tard.
    """


class SourceUnavailableError(ProviderError):
    """La source est en panne, ou injoignable, après toutes les relances."""


# --------------------------------------------------------------------------- #
# Identification
# --------------------------------------------------------------------------- #


def check_user_agent(user_agent: str, *, require_email: bool = False) -> str:
    """Rend l'en-tête d'identification s'il identifie quelqu'un, et lève sinon.

    (1) Le problème : une requête anonyme se fait refuser par les services
    publics, et le refus est muet. (2) L'intuition : mieux vaut échouer sur la
    machine du chercheur, avec un message clair, que sur un 403 dont personne ne
    devinera la cause. (3) La règle appliquée, faute de formule : la chaîne fait
    au moins dix caractères, ne porte pas le marqueur du réglage par défaut, et
    contient un contact, soit une arobase, soit une adresse ``http``.

    Args:
        user_agent: la valeur de l'en-tête ``User-Agent``.
        require_email: exige une adresse de courriel plutôt qu'un contact
            quelconque. La SEC l'impose, mesuré le 2026-09-01 : un en-tête qui
            ne porte qu'une adresse web reçoit un 403. La valeur par défaut
            reste ``False``, la plupart des sources se contentant d'un contact.

    Returns:
        La même chaîne, débarrassée de ses espaces de bord.

    Raises:
        ConfigError: si la chaîne n'identifie personne. Le message dit quoi
            poser dans ``QUANTLAB_USER_AGENT``.

    Note:
        Hypothèses (5) : un contact lisible suffit à la plupart des services,
        la SEC exigeant en plus un courriel, d'où ``require_email``.
        Provenance (6) : la page « Accessing EDGAR Data » de la SEC exige un
        ``User-Agent`` nominatif avec adresse de courriel, et la mesure du
        2026-09-01 rapportée en tête de module le confirme. Limites (7) : le
        contrôle est syntaxique, une adresse inventée passe. Alternatives (8) :
        une vérification par appel réel à la source, écartée parce qu'elle
        exigerait le réseau au démarrage. Choix (9) : le contrôle syntaxique
        attrape le cas réel, qui est l'oubli du réglage. Vérification (10) : les
        tests couvrent la valeur par défaut de :class:`Settings`, une chaîne
        courte, une chaîne sans contact et le refus d'une adresse web sous
        ``require_email``.
    """
    candidate = (user_agent or "").strip()
    if _PLACEHOLDER_MARKER in candidate:
        raise ConfigError(
            "le User-Agent est resté à sa valeur par défaut. Posez "
            'QUANTLAB_USER_AGENT="prenom nom (courriel@exemple.ca)" avant toute requête.'
        )
    if len(candidate) < _MIN_USER_AGENT_LENGTH:
        raise ConfigError(
            f"User-Agent trop court ({len(candidate)} caractères, minimum "
            f"{_MIN_USER_AGENT_LENGTH}) : il doit nommer un responsable joignable."
        )
    if require_email:
        if not _EMAIL_PATTERN.search(candidate):
            raise ConfigError(
                "cette source exige une adresse de courriel dans le User-Agent. Mesuré le "
                "2026-09-01 : la SEC répond 403 à un en-tête qui ne porte qu'une adresse web."
            )
        return candidate
    if "@" not in candidate and "http" not in candidate.lower():
        raise ConfigError(
            "le User-Agent doit porter un contact, une adresse de courriel ou une adresse web. "
            "La SEC refuse par un 403 les requêtes qui n'en portent pas."
        )
    return candidate


# --------------------------------------------------------------------------- #
# Limitation de débit par hôte
# --------------------------------------------------------------------------- #


class HostThrottle:
    r"""Espace les requêtes vers un même hôte, sans ralentir les autres.

    (1) Le problème : une rafale vers un seul serveur se fait couper, et la
    coupure porte parfois sur l'adresse entière. (2) L'intuition : garder la
    date du dernier départ vers chaque hôte, et dormir de ce qui manque.
    (3) La formule, où :math:`t_k` est l'instant de départ de la requête
    :math:`k` vers un hôte donné et :math:`d` la pause exigée :

    .. math::

        w_k = \max\left(0,\; d - (t_k - t_{k-1})\right)

    (4) Les variables : :math:`w_k` est l'attente en secondes avant la requête
    :math:`k`, et :math:`t_k` la lecture de l'horloge monotone à cet instant.
    :math:`t_{k-1}` est celle du départ précédent vers le même hôte, et
    :math:`d` la valeur de ``delay_s``. (5) Les hypothèses : l'horloge est monotone, et
    l'espacement se mesure de départ à départ, non de fin à départ.

    Args:
        delay_s: pause minimale entre deux départs vers le même hôte, en
            secondes. Une valeur nulle désactive l'espacement.
        clock: lecture de l'horloge monotone, injectable pour les tests.
        sleeper: fonction d'attente, injectable pour les tests.

    Raises:
        ConfigError: si ``delay_s`` est négatif.

    Note:
        Provenance (6) : aucune source académique, c'est de l'hygiène de client
        HTTP. Limites (7) : la mesure part du départ de la requête, donc deux
        requêtes lentes vers le même hôte peuvent se suivre de plus loin que
        prévu, ce qui est le sens conservateur. La limitation vit dans le
        processus, donc deux processus parallèles doublent le débit réel.
        Alternatives (8) : un seau à jetons, qui autorise des rafales, écarté
        parce que la rafale est précisément ce que les services publics
        sanctionnent. Choix (9) : l'espacement fixe est le comportement le plus
        prévisible, et le seul dont un test puisse prédire la valeur à la main.
        Vérification (10) : avec une horloge factice, trois appels au même hôte
        et une pause de 0,5 s doivent produire les attentes 0,0 puis 0,5 puis
        0,5, et deux hôtes différents ne s'attendent jamais.
    """

    def __init__(
        self,
        delay_s: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if delay_s < 0:
            raise ConfigError(f"delay_s ne peut pas être négatif, reçu {delay_s}")
        self.delay_s = float(delay_s)
        self._clock = clock
        self._sleeper = sleeper
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> float:
        """Attend ce qu'il faut avant de partir vers ``host``, et rend l'attente.

        Args:
            host: le nom d'hôte, comparé tel quel. Utilisez :func:`host_of`.

        Returns:
            Le nombre de secondes réellement attendues, nul pour un premier
            départ ou un hôte déjà refroidi.
        """
        with self._lock:
            waited = 0.0
            previous = self._last.get(host)
            if previous is not None and self.delay_s > 0:
                remaining = self.delay_s - (self._clock() - previous)
                if remaining > 0:
                    self._sleeper(remaining)
                    waited = remaining
            self._last[host] = self._clock()
            return waited

    def last_departure(self, host: str) -> float | None:
        """Rend la lecture d'horloge du dernier départ vers ``host``, ou ``None``."""
        with self._lock:
            return self._last.get(host)


def host_of(url: str) -> str:
    """Rend le nom d'hôte d'une adresse, en minuscules, sans le port."""
    return urlsplit(url).hostname or ""


@contextmanager
def throttle(url: str, *, limiter: HostThrottle) -> Iterator[float]:
    """Encadre un appel réseau par l'espacement dû à son hôte.

    Args:
        url: l'adresse sur le point d'être appelée.
        limiter: le limiteur qui tient les dates de départ.

    Yields:
        Le nombre de secondes attendues avant d'entrer dans le bloc.

    Example:
        .. code-block:: python

            limiter = HostThrottle(0.2)
            with throttle("https://www.sec.gov/robots.txt", limiter=limiter) as waited:
                response = session.get(url, timeout=30)
    """
    yield limiter.wait(host_of(url))


# --------------------------------------------------------------------------- #
# La réponse brute
# --------------------------------------------------------------------------- #


def _utc_now() -> dt.datetime:
    """Rend l'instant courant en temps universel, avec son fuseau."""
    return dt.datetime.now(dt.UTC)


@dataclass(frozen=True)
class RawResponse:
    """Ce que la source a répondu, tel quel, avec de quoi le retrouver.

    Le contenu reste binaire parce que le décodage est déjà une décision. Une
    réponse dont l'encodage est mal deviné se corrige en relisant les octets,
    à condition de les avoir gardés.

    Attributes:
        content: les octets reçus, sans transformation.
        url: l'adresse finale, redirections comprises.
        fetched_at: l'instant du téléchargement, en temps universel.
        headers: les en-têtes retenus, clés en minuscules.
        status_code: le code HTTP de la réponse.
        sha256: l'empreinte du contenu. Calculée si elle n'est pas fournie,
            vérifiée si elle l'est.

    Raises:
        DataQualityError: si ``sha256`` est fourni et ne correspond pas au
            contenu. C'est le contrôle qui attrape un cache altéré.

    Note:
        La classe est figée mais pas hachable : ``headers`` est un dictionnaire,
        donc ``hash`` lève ``TypeError``. Comparez les objets par leur champ
        ``sha256`` plutôt que de les ranger dans un ensemble.
    """

    content: bytes
    url: str
    fetched_at: dt.datetime = field(default_factory=_utc_now)
    headers: Mapping[str, str] = field(default_factory=dict)
    status_code: int = 200
    sha256: str = ""

    def __post_init__(self) -> None:
        digest = hashlib.sha256(self.content).hexdigest()
        if not self.sha256:
            object.__setattr__(self, "sha256", digest)
        elif self.sha256 != digest:
            raise DataQualityError(
                f"empreinte SHA-256 démentie pour {self.url} : annoncée {self.sha256}, calculée {digest}"
            )
        object.__setattr__(self, "headers", dict(self.headers))

    @property
    def size_bytes(self) -> int:
        """Rend la taille du contenu, en octets."""
        return len(self.content)

    def text(self, encoding: str = "utf-8") -> str:
        """Rend le contenu décodé, l'encodage étant déclaré par l'appelant."""
        return self.content.decode(encoding)

    def json(self, encoding: str = "utf-8") -> Any:
        """Rend le contenu interprété comme du JSON.

        Raises:
            ProviderError: si le contenu n'est pas du JSON valide.
        """
        try:
            return json.loads(self.content.decode(encoding))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProviderError(f"réponse non JSON depuis {self.url} : {exc}", url=self.url) from exc


# --------------------------------------------------------------------------- #
# Le client HTTP
# --------------------------------------------------------------------------- #


class HttpClient:
    r"""Une porte de sortie réseau unique, polie, relancée et journalisée.

    (1) Le problème : chaque fournisseur qui appelle ``requests`` directement
    réinvente l'identification, la pause et la relance, et se trompe une fois
    sur deux. (2) L'intuition : un seul objet tient ces trois règles, et les
    fournisseurs n'ont plus qu'à demander une adresse. (3) La pause entre la
    tentative :math:`k` et la suivante suit une croissance géométrique bornée :

    .. math::

        p_k = \min\left(c,\; b \cdot 2^{k}\right), \qquad k = 0, 1, 2, \dots

    (4) Les variables : :math:`p_k` est la pause en secondes après la tentative
    de rang :math:`k` comptée depuis zéro, :math:`b` la base
    ``backoff_base_s``, et :math:`c` le plafond ``backoff_cap_s``. Un en-tête
    ``Retry-After`` lisible en secondes remplace :math:`p_k` par la valeur
    annoncée, parce que la source connaît sa propre fenêtre mieux que le client.
    Il est lu sur tout code relançable, non sur le seul 429, ce que la RFC 9110
    autorise pour les réponses 503 comme pour les 429.

    (5) Les hypothèses : un code de :data:`RETRYABLE_STATUSES` est transitoire,
    un autre ne l'est pas ; l'horloge est monotone ; la session rend un objet
    portant ``status_code``, ``content``, ``headers`` et ``url``.

    Args:
        settings: les réglages d'environnement. Sans valeur, ils sont lus par
            :func:`get_settings`.
        session: la session HTTP. Sans valeur, une ``requests.Session`` est
            créée. Toute session factice portant ``get`` convient, et c'est ce
            qui rend ce client testable hors réseau.
        timeout_s: délai d'attente d'une requête, en secondes.
        backoff_base_s: base de la pause exponentielle, en secondes.
        backoff_cap_s: plafond de la pause exponentielle, en secondes.
        retryable_statuses: les codes jugés transitoires.
        retained_headers: les en-têtes conservés dans la provenance.
        require_email_contact: exige un courriel dans le ``User-Agent``. À poser
            pour la SEC, qui répond 403 sans lui, mesuré le 2026-09-01.
        clock: lecture de l'horloge monotone, injectable.
        sleeper: fonction d'attente, injectable.
        now: fournisseur de l'horodatage, injectable.

    Raises:
        ConfigError: si le ``User-Agent`` des réglages n'identifie personne.

    Note:
        Provenance (6) : la relance exponentielle est un usage de client HTTP,
        décrit entre autres par la RFC 9110 pour ``Retry-After`` ; aucun article
        académique derrière. Limites (7) : la pause ne porte aucune gigue, donc
        deux processus qui démarrent ensemble relancent en phase et refont la
        rafale qu'ils voulaient éviter. Déclaré et non corrigé, la
        parallélisation n'étant pas prévue ici. Le client ne
        respecte pas ``robots.txt``, la vérification restant à la charge de
        l'appelant. Une valeur de ``Retry-After`` n'est bornée par aucun
        plafond : une source qui annonce une heure fait dormir le processus une
        heure. C'est délibéré, écourter l'attente demandée invitant un second
        refus, et c'est le comportement qu'un test épingle.
        Alternatives (8) : l'adaptateur ``urllib3.util.Retry``, qui relance mais
        ne journalise rien d'exploitable ni n'espace par hôte.
        Choix (9) : la relance écrite ici rend chaque tentative visible dans le
        journal, ce qui est la seule façon de savoir après coup si un résultat
        vient d'une source qui bégayait. Vérification (10) : les tests
        vérifient trois tentatives sur 503, les pauses 0,5 puis 1,0 seconde, le
        respect d'un ``Retry-After`` de 7 secondes, et l'espacement par hôte.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session: Any | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
        backoff_cap_s: float = DEFAULT_BACKOFF_CAP_S,
        retryable_statuses: frozenset[int] = RETRYABLE_STATUSES,
        retained_headers: Sequence[str] = RETAINED_HEADERS,
        require_email_contact: bool = False,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        now: Callable[[], dt.datetime] = _utc_now,
    ) -> None:
        self.settings = settings if settings is not None else get_settings()
        self.require_email_contact = bool(require_email_contact)
        self.user_agent = check_user_agent(self.settings.user_agent, require_email=self.require_email_contact)
        self.timeout_s = float(timeout_s)
        self.backoff_base_s = float(backoff_base_s)
        self.backoff_cap_s = float(backoff_cap_s)
        self.retryable_statuses = frozenset(retryable_statuses)
        self.retained_headers = tuple(h.lower() for h in retained_headers)
        self.max_retries = int(self.settings.max_retries)
        self._sleeper = sleeper
        self._clock = clock
        self._now = now
        self._owns_session = session is None
        self._session = session if session is not None else requests.Session()
        self.limiter = HostThrottle(self.settings.request_delay_s, clock=clock, sleeper=sleeper)

    # ---------------------------------------------------------------- API --

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> RawResponse:
        """Télécharge une adresse et rend la réponse brute.

        Args:
            url: l'adresse appelée.
            params: les paramètres de requête, ajoutés à l'adresse.
            headers: des en-têtes supplémentaires. Un ``User-Agent`` fourni
                ici remplace celui du client, quelle que soit la casse de la
                clé, et passe par le même contrôle d'identification.

        Returns:
            La réponse brute, avec son horodatage et son empreinte.

        Raises:
            ConfigError: si l'appelant fournit un ``User-Agent`` qui n'identifie
                personne.
            RateLimitError: si la source répond 429 jusqu'à la dernière
                tentative.
            SourceUnavailableError: si la source répond 5xx, ou ne répond pas,
                jusqu'à la dernière tentative.
            ProviderError: pour tout autre code d'échec, 403 compris. Le message
                d'un 403 rappelle que l'identification est peut-être en cause.
        """
        sent = {str(k): str(v) for k, v in (headers or {}).items()}
        supplied = next((k for k in sent if k.lower() == "user-agent"), None)
        if supplied is None:
            sent["User-Agent"] = self.user_agent
        else:
            sent[supplied] = check_user_agent(sent[supplied], require_email=self.require_email_contact)
        host = host_of(url)
        last_status: int | None = None
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            with throttle(url, limiter=self.limiter):
                started = self._clock()
                try:
                    response = self._session.get(
                        url, params=dict(params) if params else None, headers=sent, timeout=self.timeout_s
                    )
                except requests.RequestException as exc:
                    last_error = exc
                    _log.warning(
                        "requête HTTP échouée",
                        extra={
                            "host": host,
                            "attempt": attempt,
                            "duration_s": round(self._clock() - started, 4),
                            "error": repr(exc),
                        },
                    )
                    if self._pause_before_retry(attempt, retry_after=None):
                        continue
                    raise SourceUnavailableError(f"aucune réponse de {host} : {exc}", url=url) from exc

                status = int(response.status_code)
                content = bytes(response.content or b"")
                duration_s = round(self._clock() - started, 4)
                _log.info(
                    "requête HTTP",
                    extra={
                        "host": host,
                        "status": status,
                        "duration_s": duration_s,
                        "bytes": len(content),
                        "attempt": attempt,
                    },
                )

            if 200 <= status < 300:
                return RawResponse(
                    content=content,
                    url=str(getattr(response, "url", url) or url),
                    fetched_at=self._now(),
                    headers=self._keep(getattr(response, "headers", {}) or {}),
                    status_code=status,
                )

            last_status = status
            if status in self.retryable_statuses and self._pause_before_retry(
                attempt, retry_after=self._retry_after(getattr(response, "headers", {}) or {})
            ):
                continue
            break

        return self._raise(url=url, host=host, status=last_status, error=last_error)

    def close(self) -> None:
        """Ferme la session, si ce client l'a créée."""
        if self._owns_session:
            closer = getattr(self._session, "close", None)
            if callable(closer):
                closer()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------ interne --

    def backoff_s(self, attempt: int) -> float:
        """Rend la pause après la tentative de rang ``attempt``, comptée à zéro.

        Example:
            Avec la base 0,5 seconde et le plafond 60, les trois premières
            pauses valent 0,5 puis 1,0 puis 2,0 seconde.
        """
        return min(self.backoff_cap_s, self.backoff_base_s * (2.0**attempt))

    def _pause_before_retry(self, attempt: int, *, retry_after: float | None) -> bool:
        """Dort avant la tentative suivante, et dit s'il en reste une."""
        if attempt >= self.max_retries:
            return False
        pause = self.backoff_s(attempt) if retry_after is None else retry_after
        if pause > 0:
            self._sleeper(pause)
        return True

    def _retry_after(self, headers: Mapping[str, str]) -> float | None:
        """Lit un en-tête ``Retry-After`` exprimé en secondes, s'il est lisible.

        La forme date HTTP, également permise par la RFC 9110, n'est pas lue :
        elle rend ``None``, et la pause exponentielle reprend la main. La valeur
        rendue n'est pas plafonnée, la source étant tenue pour mieux informée
        que le client sur sa propre fenêtre.
        """
        for key, value in headers.items():
            if key.lower() == "retry-after":
                try:
                    return max(0.0, float(str(value).strip()))
                except ValueError:
                    return None
        return None

    def _keep(self, headers: Mapping[str, str]) -> dict[str, str]:
        """Rend les seuls en-têtes de provenance, clés en minuscules."""
        return {k.lower(): str(v) for k, v in headers.items() if k.lower() in self.retained_headers}

    def _raise(self, *, url: str, host: str, status: int | None, error: Exception | None) -> RawResponse:
        """Lève l'erreur qui correspond au dernier échec observé."""
        attempts = self.max_retries + 1
        if status == 429:
            raise RateLimitError(
                f"{host} limite le débit et refuse encore après {attempts} tentatives",
                url=url,
                status_code=status,
            )
        if status is not None and status >= 500:
            raise SourceUnavailableError(
                f"{host} répond {status} après {attempts} tentatives", url=url, status_code=status
            )
        if status == 403:
            raise ProviderError(
                f"{host} répond 403. Trois causes possibles, que le code ne distingue pas : "
                "un User-Agent sans courriel, un courriel dont le domaine est refusé, ou un "
                "débit jugé trop élevé. Mesuré le 2026-09-01 sur www.sec.gov : « contact@uqam.ca » "
                "obtient un 200 là où « contact@github.com » obtient un 403. "
                f"En-tête envoyé : « {self.user_agent} ».",
                url=url,
                status_code=status,
            )
        if status is not None:
            raise ProviderError(f"{host} répond {status}", url=url, status_code=status)
        raise SourceUnavailableError(f"aucune réponse de {host} : {error!r}", url=url)


# --------------------------------------------------------------------------- #
# Le cache brut
# --------------------------------------------------------------------------- #


def _slug(text: str) -> str:
    """Rend une chaîne utilisable dans un nom de fichier, en minuscules."""
    kept = "".join(c if c in _SAFE_SLUG_CHARS else "-" for c in text.lower())
    return kept.strip("-")[:_SLUG_MAX_LENGTH]


def cache_key(url: str, params: Mapping[str, Any] | None = None, label: str | None = None) -> str:
    r"""Rend la clé de cache d'une requête : un préfixe lisible et une empreinte.

    (1) Le problème : deux requêtes différentes rangées au même endroit se
    relisent l'une pour l'autre, et l'étude tourne sur la mauvaise période sans
    rien signaler. (2) L'intuition : faire dépendre le nom du dossier de tout ce
    qui distingue une requête, l'adresse et les paramètres. (3) La règle, où
    :math:`D` est le document JSON canonique de la requête :

    .. math::

        k = \mathrm{slug}(\ell) \; \Vert \; \text{« - »} \; \Vert \;
            \mathrm{SHA\text{-}256}(D)_{[0:16]}

    (4) Les variables : :math:`\ell` est le préfixe lisible, imposé par
    ``label`` ou déduit du dernier segment du chemin. :math:`D` est le document
    ``{"params": …, "url": …}`` écrit clés triées. L'indice ``[0:16]`` désigne
    les seize premiers caractères hexadécimaux. (5) Les hypothèses : les
    paramètres sont sérialisables en JSON, et seize caractères hexadécimaux
    suffisent à séparer les requêtes d'une étude.

    Deux requêtes ne partagent une clé que si leur adresse et leurs paramètres
    coïncident. L'empreinte porte les deux, donc un paramètre changé range la
    réponse ailleurs, ce qui évite de relire le fichier d'une autre période.

    Args:
        url: l'adresse appelée.
        params: les paramètres de requête, triés avant l'empreinte pour que
            l'ordre d'écriture n'entre pas dans la clé.
        label: un préfixe lisible imposé. Sans valeur, il est déduit du dernier
            segment du chemin, ou du nom d'hôte.

    Returns:
        Une clé de la forme ``prefixe-abcdef0123456789``.

    Note:
        Provenance (6) : SHA-256 est la fonction du standard FIPS 180-4 du NIST,
        publié en 2015. Limites (7) : une valeur non sérialisable en JSON entre
        dans l'empreinte par son écriture textuelle, donc la date
        ``datetime.date(2024, 1, 1)`` et la chaîne ``"2024-01-01"`` donnent la
        même clé. Seize caractères hexadécimaux offrent 1,8e19 valeurs, ce qui
        rend une collision négligeable à l'échelle d'une étude, sans être
        impossible. Alternatives (8) : l'adresse encodée telle quelle, écartée
        parce qu'elle dépasse la longueur permise à un nom de dossier et qu'elle
        rend le chemin illisible. Choix (9) : le préfixe lisible garde le dossier
        navigable à la main, et l'empreinte fait le travail de séparation.
        Vérification (10) : un test écrit le document JSON en toutes lettres et
        le fait hacher par ``hashlib``, sans réutiliser la recette de ce module.
    """
    payload = json.dumps(
        {"url": url, "params": {str(k): params[k] for k in sorted(params)} if params else {}},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:_KEY_DIGEST_LENGTH]
    parts = urlsplit(url)
    fallback = parts.path.rsplit("/", 1)[-1] or parts.hostname or "reponse"
    prefix = _slug(label or fallback)
    return f"{prefix}-{digest}" if prefix else digest


class BaseProvider(ABC):
    """Le socle d'un fournisseur : un nom, un client, un cache brut, un manifeste.

    La classe tient le protocole :class:`quantlab.core.protocols.DataProvider`.
    Une sous-classe fournit ``name``, ``fetch`` et ``manifest``, et hérite du
    reste.

    **La règle du cache brut.** ``fetch_cached`` écrit la réponse dans
    ``data/raw/<fournisseur>/<clé>/<horodatage>-<empreinte>.bin`` avant tout
    parsage, avec un fichier compagnon ``.meta.json`` qui porte l'adresse, les
    en-têtes retenus, le code et l'empreinte. L'horodatage descend à la
    microseconde, ce qui garantit que le tri des noms est le tri du temps. Ce fichier est la seule copie de ce
    que la source a répondu. Il ne se réécrit jamais en silence : un nouveau
    téléchargement crée un nouveau fichier horodaté, et deux contenus différents
    qui viseraient le même nom lèvent une :class:`ProviderError`.

    Args:
        client: le client HTTP. Sans valeur, il est créé au premier besoin.
        raw_root: la racine du cache brut. Sans valeur,
            ``data/raw/<fournisseur>/``. Les tests y passent un ``tmp_path``.
        now: fournisseur de l'horodatage, injectable.

    Raises:
        ConfigError: si la sous-classe ne déclare pas de ``name``.

    Note:
        Limites (7) : le cache ignore ``ETag`` et ``Last-Modified``, donc une
        relecture ne sait pas si la source a changé. ``refresh=True`` est le
        seul moyen de le vérifier, et il coûte un téléchargement entier.
        Vérification (10) : les tests écrivent dans un ``tmp_path``, relisent
        sans toucher à la session, et vérifient qu'un contenu différent au même
        horodatage lève plutôt que d'écraser.
    """

    #: Nom court du fournisseur, en minuscules, qui nomme aussi son dossier brut.
    name: ClassVar[str] = ""

    def __init__(
        self,
        *,
        client: HttpClient | None = None,
        raw_root: Path | str | None = None,
        now: Callable[[], dt.datetime] = _utc_now,
    ) -> None:
        if not self.name:
            raise ConfigError(
                f"{type(self).__name__} ne déclare pas de « name ». Le nom du fournisseur "
                "nomme son dossier de cache brut, il ne peut pas être vide."
            )
        self._client = client
        self._raw_root = Path(raw_root) if raw_root is not None else data_dir(Layer.RAW) / self.name
        self._now = now
        self._log = get_logger(f"quantlab.data.providers.{self.name}")

    # ---------------------------------------------------------- protocole --

    @abstractmethod
    def fetch(self, *, start: dt.date, end: dt.date, **kwargs: Any) -> pd.DataFrame:
        """Télécharge la donnée brute de la période demandée."""

    @abstractmethod
    def manifest(self, **kwargs: Any) -> DatasetManifest:
        """Décrit ce qui vient d'être téléchargé : source, licence, empreinte."""

    # ------------------------------------------------------------- outils --

    @property
    def client(self) -> HttpClient:
        """Rend le client HTTP du fournisseur, créé au premier appel."""
        if self._client is None:
            self._client = HttpClient()
        return self._client

    @property
    def raw_root(self) -> Path:
        """Rend la racine du cache brut de ce fournisseur."""
        return self._raw_root

    def cached_paths(self, key: str) -> list[Path]:
        """Rend les fichiers bruts déjà téléchargés pour une clé, du plus ancien au plus récent.

        Le tri est celui des noms, et il coïncide avec le tri chronologique
        parce que l'horodatage est écrit en format ISO compact à la
        microseconde, qui se compare caractère par caractère.

        Note:
            La microseconde n'est pas un ornement. Avec un horodatage à la
            seconde, deux téléchargements séparés d'une demi-seconde portaient
            le même préfixe, et le tri retombait sur l'empreinte du contenu.
            Mesuré le 2026-09-01 sur ce module : « version 2 » puis
            « version 3 » écrits à 0,5 seconde d'intervalle donnaient les
            empreintes ``f4761aa0`` et ``791cad8c``. Le tri plaçait donc le plus
            ancien en dernier, et la relecture rendait « version 2 ».
        """
        directory = self._raw_root / key
        if not directory.is_dir():
            return []
        return sorted(directory.glob("*.bin"))

    def fetch_cached(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        label: str | None = None,
        refresh: bool = False,
    ) -> RawResponse:
        """Rend la réponse brute, relue du cache ou téléchargée puis écrite.

        Args:
            url: l'adresse appelée.
            params: les paramètres de requête, qui entrent dans la clé de cache.
            headers: des en-têtes supplémentaires, qui n'entrent pas dans la clé.
            label: un préfixe lisible pour le dossier de cache.
            refresh: force un nouveau téléchargement, qui crée un nouveau
                fichier horodaté sans toucher aux précédents.

        Returns:
            La réponse brute, avec l'horodatage de son téléchargement d'origine
            quand elle vient du cache.

        Raises:
            DataQualityError: si le fichier relu dément son empreinte.
            ProviderError: si deux contenus différents visent le même nom de
                fichier, ce qui signalerait une réécriture.
        """
        key = cache_key(url, params, label)
        if not refresh:
            existing = self.cached_paths(key)
            if existing:
                latest = existing[-1]
                raw = self._read_cached(latest)
                self._log.info(
                    "réponse brute relue",
                    extra={"path": str(latest), "bytes": raw.size_bytes, "key": key},
                )
                return raw

        raw = self.client.get(url, params=params, headers=headers)
        path = self._write_cached(key, raw)
        self._log.info(
            "réponse brute écrite",
            extra={"path": str(path), "bytes": raw.size_bytes, "key": key, "status": raw.status_code},
        )
        return raw

    # ------------------------------------------------------------ interne --

    def _write_cached(self, key: str, raw: RawResponse) -> Path:
        """Écrit la réponse et son manifeste, sans jamais écraser un autre contenu."""
        directory = ensure(self._raw_root / key)
        stamp = raw.fetched_at.astimezone(dt.UTC).strftime(_STAMP_FORMAT)
        path = directory / f"{stamp}-{raw.sha256[:_FILE_DIGEST_LENGTH]}.bin"
        if path.exists():
            if path.read_bytes() != raw.content:
                raise ProviderError(
                    f"le cache brut {path} existe avec un contenu différent. "
                    "Un fichier brut ne se réécrit pas.",
                    url=raw.url,
                )
            return path
        path.write_bytes(raw.content)
        meta = {
            "url": raw.url,
            "fetched_at": raw.fetched_at.astimezone(dt.UTC).isoformat(),
            "status_code": raw.status_code,
            "headers": dict(raw.headers),
            "sha256": raw.sha256,
            "size_bytes": raw.size_bytes,
            "provider": self.name,
        }
        path.with_suffix(".meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        return path

    def _read_cached(self, path: Path) -> RawResponse:
        """Relit une réponse du cache, empreinte vérifiée."""
        meta_path = path.with_suffix(".meta.json")
        if not meta_path.is_file():
            raise DataQualityError(f"manifeste absent pour le fichier brut {path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return RawResponse(
            content=path.read_bytes(),
            url=str(meta["url"]),
            fetched_at=dt.datetime.fromisoformat(str(meta["fetched_at"])),
            headers=dict(meta.get("headers", {})),
            status_code=int(meta.get("status_code", 200)),
            sha256=str(meta["sha256"]),
        )
