"""Tests du socle des fournisseurs, tous hors réseau sauf un, marqué « network ».

Règle tenue ici : aucune valeur attendue ne vient de la sortie du code. Chaque
assertion porte en commentaire la source de sa valeur, parmi
(a) un calcul à la main, (b) une identité mathématique, (c) une valeur publiée,
(d) une implémentation indépendante.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
import requests
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from quantlab.core.config import Settings
from quantlab.core.errors import ConfigError, DataQualityError, QuantLabError
from quantlab.core.protocols import DataProvider
from quantlab.data.providers import base as base_module
from quantlab.data.providers.base import (
    BaseProvider,
    HostThrottle,
    HttpClient,
    ProviderError,
    RateLimitError,
    RawResponse,
    SourceUnavailableError,
    cache_key,
    check_user_agent,
    host_of,
    throttle,
)

# ---------------------------------------------------------------------------
# Doublures : horloge, réponse et session. Aucune ne sort sur le réseau.
# ---------------------------------------------------------------------------

#: Un en-tête d'identification valide, sans adresse personnelle.
GOOD_AGENT = "quantlab research (https://github.com/Guilou001/quant-research-platform)"

#: La valeur par défaut du champ « user_agent » de quantlab.core.config.Settings,
#: recopiée depuis la source de ce module. Source (c).
PLACEHOLDER_AGENT = "quantlab research (contact: set QUANTLAB_USER_AGENT)"


class FakeClock:
    """Horloge monotone factice : dormir avance le temps, sans attendre."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start
        self.start = start
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds

    def now(self) -> dt.datetime:
        base = dt.datetime(2026, 9, 1, 12, 0, 0, tzinfo=dt.UTC)
        return base + dt.timedelta(seconds=self.t - self.start)


class FakeResponse:
    """La forme minimale qu'un client HTTP attend d'une réponse."""

    def __init__(
        self,
        status_code: int,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
        url: str = "https://exemple.test/donnee.csv",
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.url = url


class FakeSession:
    """Session factice : rend les réponses données, la dernière se répétant."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def get(self, url: str, *, params: Any = None, headers: Any = None, timeout: Any = None) -> Any:
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        item = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


def make_settings(**overrides: Any) -> Settings:
    """Rend des réglages explicites, sans dépendre de l'environnement du poste."""
    base: dict[str, Any] = {
        "user_agent": GOOD_AGENT,
        "request_delay_s": 0.0,
        "max_retries": 3,
        "log_level": "INFO",
    }
    base.update(overrides)
    return Settings(**base)


def make_client(
    responses: list[Any], clock: FakeClock | None = None, **overrides: Any
) -> tuple[HttpClient, FakeSession, FakeClock]:
    """Monte un client branché sur une session factice et une horloge factice."""
    clock = clock or FakeClock()
    session = FakeSession(responses)
    client = HttpClient(
        settings=make_settings(**overrides),
        session=session,
        clock=clock.monotonic,
        sleeper=clock.sleep,
        now=clock.now,
    )
    return client, session, clock


class DummyProvider(BaseProvider):
    """Fournisseur minimal, juste assez pour exercer le socle."""

    name = "dummy"

    def fetch(self, *, start: dt.date, end: dt.date, **kwargs: Any) -> Any:
        raise NotImplementedError

    def manifest(self, **kwargs: Any) -> Any:
        raise NotImplementedError


class NamelessProvider(BaseProvider):
    """Fournisseur sans nom, qui doit être refusé à la construction."""

    def fetch(self, *, start: dt.date, end: dt.date, **kwargs: Any) -> Any:
        raise NotImplementedError

    def manifest(self, **kwargs: Any) -> Any:
        raise NotImplementedError


def make_provider(
    tmp_path: Path, responses: list[Any], **overrides: Any
) -> tuple[DummyProvider, FakeSession, FakeClock]:
    """Monte un fournisseur dont le cache brut vit dans tmp_path."""
    client, session, clock = make_client(responses, **overrides)
    provider = DummyProvider(client=client, raw_root=tmp_path / "raw" / "dummy", now=clock.now)
    return provider, session, clock


# ---------------------------------------------------------------------------
# RawResponse et son empreinte
# ---------------------------------------------------------------------------


def test_sha256_reproduit_le_vecteur_publie_de_fips_180_4() -> None:
    """Source (c) : vecteur d'essai publié pour SHA-256 sur la chaîne « abc »."""
    raw = RawResponse(content=b"abc", url="https://exemple.test/abc")
    assert raw.sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sha256_de_la_reponse_vide_est_le_vecteur_publie() -> None:
    """Cas limite du contenu vide. Source (c) : empreinte publiée de la chaîne vide."""
    raw = RawResponse(content=b"", url="https://exemple.test/vide")
    assert raw.sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert raw.size_bytes == 0


def test_empreinte_dementie_leve_une_erreur_de_qualite() -> None:
    """Source (b) : l'identité « empreinte annoncée = empreinte calculée » doit tenir."""
    with pytest.raises(DataQualityError, match="SHA-256"):
        RawResponse(content=b"abc", url="https://exemple.test/abc", sha256="0" * 64)


def test_json_invalide_leve_une_erreur_de_fournisseur() -> None:
    raw = RawResponse(content=b"pas du json", url="https://exemple.test/x")
    with pytest.raises(ProviderError):
        raw.json()


def test_json_valide_est_relu() -> None:
    """Source (a) : le document écrit à la main dans le test est celui qui ressort."""
    raw = RawResponse(content=b'{"a": 1}', url="https://exemple.test/x")
    assert raw.json() == {"a": 1}


# ---------------------------------------------------------------------------
# Identification
# ---------------------------------------------------------------------------


def test_le_user_agent_par_defaut_est_refuse() -> None:
    """Source (c) : la valeur par défaut publiée dans core/config.py porte le marqueur."""
    with pytest.raises(ConfigError, match="valeur par défaut"):
        check_user_agent(PLACEHOLDER_AGENT)


@pytest.mark.parametrize("agent", ["", "   ", "quantlab", "abc"])
def test_un_user_agent_trop_court_est_refuse(agent: str) -> None:
    """Source (a) : ces chaînes font moins de dix caractères une fois rognées."""
    with pytest.raises(ConfigError, match="trop court"):
        check_user_agent(agent)


def test_un_user_agent_sans_contact_est_refuse() -> None:
    """Source (a) : « laboratoire quantitatif » fait 23 caractères et ne porte ni « @ » ni « http »."""
    with pytest.raises(ConfigError, match="contact"):
        check_user_agent("laboratoire quantitatif")


@pytest.mark.parametrize(
    "agent",
    [
        "Guillaume Vaudescal (exemple@exemple.ca)",
        "quantlab (https://exemple.test/quantlab)",
    ],
)
def test_un_user_agent_avec_contact_est_accepte(agent: str) -> None:
    assert check_user_agent(f"  {agent}  ") == agent


@pytest.mark.parametrize(
    ("agent", "accepte"),
    [
        ("quantlab research (contact@example.com)", True),
        ("quantlab research (a+b@example.com)", True),
        ("quantlab research (contact@uqam.ca)", True),
        ("quantlab research (https://exemple.test/quantlab)", False),
        ("Guillaume Vaudescal, laboratoire", False),
    ],
)
def test_require_email_exige_une_adresse_de_courriel(agent: str, accepte: bool) -> None:
    """Source (a) : les trois premières chaînes portent « texte@domaine.tld », les
    deux dernières n'en portent aucune. La SEC répond 200 aux trois premières et
    403 à la quatrième, mesuré le 2026-09-01 sur www.sec.gov/robots.txt."""
    if accepte:
        assert check_user_agent(agent, require_email=True) == agent
    else:
        with pytest.raises(ConfigError, match="courriel"):
            check_user_agent(agent, require_email=True)


def test_sans_require_email_une_adresse_web_suffit() -> None:
    """Source (b) : le défaut est permissif, l'exigence de courriel est optionnelle."""
    agent = "quantlab research (https://exemple.test/quantlab)"
    assert check_user_agent(agent) == agent


def test_le_client_qui_exige_un_courriel_refuse_une_adresse_web() -> None:
    session = FakeSession([FakeResponse(200, b"ok")])
    with pytest.raises(ConfigError, match="courriel"):
        HttpClient(settings=make_settings(), session=session, require_email_contact=True)
    assert session.calls == []


def test_le_client_refuse_de_partir_sans_identification() -> None:
    """Le contrôle a lieu à la construction, avant toute sortie réseau."""
    session = FakeSession([FakeResponse(200, b"ok")])
    with pytest.raises(ConfigError):
        HttpClient(settings=make_settings(user_agent=PLACEHOLDER_AGENT), session=session)
    assert session.calls == []


def test_un_user_agent_fourni_par_lappelant_est_controle() -> None:
    """Source (b) : un contrôle d'identification qui se contourne ne contrôle rien.

    L'appelant peut imposer son propre en-tête, mais il passe alors par la même
    règle que celui du client. Sans cela, la promesse « une seule porte de
    sortie, qui s'identifie » serait fausse dès la première requête sur mesure.
    """
    client, session, _ = make_client([FakeResponse(200, b"ok")])
    with pytest.raises(ConfigError, match="valeur par défaut"):
        client.get("https://exemple.test/a", headers={"User-Agent": PLACEHOLDER_AGENT})
    with pytest.raises(ConfigError, match="trop court"):
        client.get("https://exemple.test/a", headers={"user-agent": "abc"})
    assert session.calls == []


def test_un_user_agent_fourni_en_minuscules_ne_se_dedouble_pas() -> None:
    """Source (a) : une seule clé d'identification doit sortir.

    Deux clés « User-Agent » et « user-agent » dans le même dictionnaire se
    fondent en une seule chez requests, et laquelle survit n'est pas décidable
    depuis ce module. Le client n'en écrit donc jamais une seconde.
    """
    client, session, _ = make_client([FakeResponse(200, b"ok")])
    agent = "quantlab bench (contact@exemple.ca)"
    client.get("https://exemple.test/a", headers={"user-agent": agent})
    envoyes = session.calls[0]["headers"]
    assert [k for k in envoyes if k.lower() == "user-agent"] == ["user-agent"]
    assert envoyes["user-agent"] == agent


def test_le_user_agent_part_dans_les_en_tetes() -> None:
    client, session, _ = make_client([FakeResponse(200, b"ok")])
    client.get("https://exemple.test/a")
    assert session.calls[0]["headers"]["User-Agent"] == GOOD_AGENT
    # Source (a) : DEFAULT_TIMEOUT_S vaut 30.0 dans le module, et rien ne le change ici.
    assert session.calls[0]["timeout"] == 30.0


# ---------------------------------------------------------------------------
# Relances
# ---------------------------------------------------------------------------


def test_deux_503_puis_un_200_donnent_trois_appels_et_les_pauses_attendues() -> None:
    """Source (a) : pauses min(60, 0,5 x 2^k) pour k = 0 puis 1, soit 0,5 s puis 1,0 s."""
    responses = [FakeResponse(503), FakeResponse(503), FakeResponse(200, b"contenu")]
    client, session, clock = make_client(responses)
    raw = client.get("https://exemple.test/a")
    assert len(session.calls) == 3
    assert raw.content == b"contenu"
    assert clock.sleeps == [0.5, 1.0]


def test_503_persistant_leve_source_indisponible_apres_les_relances() -> None:
    """Source (a) : max_retries = 2 donne 3 tentatives et 2 pauses, 0,5 s puis 1,0 s."""
    client, session, clock = make_client([FakeResponse(503)], max_retries=2)
    with pytest.raises(SourceUnavailableError) as excinfo:
        client.get("https://exemple.test/a")
    assert len(session.calls) == 3
    assert clock.sleeps == [0.5, 1.0]
    assert excinfo.value.status_code == 503


def test_429_persistant_leve_une_erreur_de_debit() -> None:
    """Source (b) : 429 et 5xx appellent des corrections différentes, donc deux classes."""
    client, _, _ = make_client([FakeResponse(429)], max_retries=1)
    with pytest.raises(RateLimitError):
        client.get("https://exemple.test/a")


def test_le_retry_after_du_429_remplace_la_pause_calculee() -> None:
    """Source (c) : la RFC 9110 donne « Retry-After » en secondes, ici 7."""
    responses = [FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, b"ok")]
    client, _, clock = make_client(responses)
    client.get("https://exemple.test/a")
    assert clock.sleeps == [7.0]


def test_un_retry_after_geant_est_honore_sans_plafond() -> None:
    """Source (a) : la source annonce 3600 s, le client dort 3600 s.

    Le plafond de 60 s borne la pause exponentielle, pas l'attente demandée par
    la source. Le choix est délibéré, écourter l'attente annoncée invitant un
    second refus. Ce test épingle le comportement pour qu'il ne change pas en
    silence.
    """
    responses = [FakeResponse(429, headers={"Retry-After": "3600"}), FakeResponse(200, b"ok")]
    client, _, clock = make_client(responses)
    client.get("https://exemple.test/a")
    assert clock.sleeps == [3600.0]


def test_le_retry_after_est_lu_aussi_sur_un_503() -> None:
    """Source (c) : la RFC 9110 autorise « Retry-After » sur 503 comme sur 429."""
    responses = [FakeResponse(503, headers={"Retry-After": "4"}), FakeResponse(200, b"ok")]
    client, _, clock = make_client(responses)
    client.get("https://exemple.test/a")
    assert clock.sleeps == [4.0]


def test_un_retry_after_illisible_retombe_sur_la_pause_exponentielle() -> None:
    """Source (a) : sans nombre lisible, la pause de rang 0 vaut 0,5 s."""
    responses = [
        FakeResponse(429, headers={"Retry-After": "Wed, 01 Sep 2026 12:00:00 GMT"}),
        FakeResponse(200, b"ok"),
    ]
    client, _, clock = make_client(responses)
    client.get("https://exemple.test/a")
    assert clock.sleeps == [0.5]


def test_le_403_nest_pas_relance_et_son_message_parle_didentification() -> None:
    """Source (b) : un 403 se corrige par l'en-tête, l'attente n'y change rien."""
    client, session, clock = make_client([FakeResponse(403)])
    with pytest.raises(ProviderError, match="403") as excinfo:
        client.get("https://exemple.test/a")
    assert len(session.calls) == 1
    assert clock.sleeps == []
    assert "User-Agent" in str(excinfo.value)
    assert excinfo.value.status_code == 403


def test_le_404_nest_pas_relance() -> None:
    client, session, _ = make_client([FakeResponse(404)])
    with pytest.raises(ProviderError):
        client.get("https://exemple.test/a")
    assert len(session.calls) == 1


def test_une_panne_de_connexion_est_relancee_puis_declaree_indisponible() -> None:
    """Source (a) : max_retries = 2 donne 3 tentatives, pauses 0,5 s puis 1,0 s."""
    client, session, clock = make_client([requests.ConnectionError("réseau coupé")], max_retries=2)
    with pytest.raises(SourceUnavailableError):
        client.get("https://exemple.test/a")
    assert len(session.calls) == 3
    assert clock.sleeps == [0.5, 1.0]


def test_le_plafond_borne_la_pause_exponentielle() -> None:
    """Source (a) : 0,5 x 2^10 fait 512 s, au-dessus du plafond de 60 s."""
    client, _, _ = make_client([FakeResponse(200, b"ok")])
    assert client.backoff_s(0) == 0.5
    assert client.backoff_s(1) == 1.0
    assert client.backoff_s(2) == 2.0
    assert client.backoff_s(10) == 60.0


def test_les_erreurs_du_module_descendent_de_la_racine_du_paquet() -> None:
    """Source (b) : attraper QuantLabError doit attraper tout ce que le module lève."""
    assert issubclass(ProviderError, QuantLabError)
    assert issubclass(RateLimitError, ProviderError)
    assert issubclass(SourceUnavailableError, ProviderError)


# ---------------------------------------------------------------------------
# Limitation par hôte
# ---------------------------------------------------------------------------


def test_lespacement_suit_le_calcul_a_la_main() -> None:
    """Source (a) : d = 0,5 s. Départs à t = 100, puis immédiat, puis immédiat.

    Attente 1 : premier départ, donc 0,0 et t reste 100.
    Attente 2 : 0,5 - (100 - 100) = 0,5, donc t devient 100,5.
    Attente 3 : 0,5 - (100,5 - 100,5) = 0,5, donc t devient 101,0.
    """
    clock = FakeClock(start=100.0)
    limiter = HostThrottle(0.5, clock=clock.monotonic, sleeper=clock.sleep)
    assert limiter.wait("a.test") == 0.0
    assert limiter.wait("a.test") == 0.5
    assert limiter.wait("a.test") == 0.5
    assert clock.t == 101.0


def test_deux_hotes_ne_sattendent_pas() -> None:
    """Source (b) : la limitation est indexée par hôte, donc indépendante d'un hôte à l'autre."""
    clock = FakeClock(start=100.0)
    limiter = HostThrottle(0.5, clock=clock.monotonic, sleeper=clock.sleep)
    assert limiter.wait("a.test") == 0.0
    assert limiter.wait("b.test") == 0.0
    assert clock.sleeps == []


def test_une_pause_nulle_desactive_lespacement() -> None:
    clock = FakeClock()
    limiter = HostThrottle(0.0, clock=clock.monotonic, sleeper=clock.sleep)
    assert [limiter.wait("a.test") for _ in range(5)] == [0.0] * 5


def test_une_pause_negative_est_refusee() -> None:
    with pytest.raises(ConfigError):
        HostThrottle(-1.0)


def test_le_contexte_de_limitation_rend_lattente() -> None:
    clock = FakeClock(start=100.0)
    limiter = HostThrottle(0.25, clock=clock.monotonic, sleeper=clock.sleep)
    with throttle("https://a.test/x", limiter=limiter) as waited:
        assert waited == 0.0
    with throttle("https://a.test/y", limiter=limiter) as waited:
        # Source (a) : 0,25 - 0 = 0,25 seconde.
        assert waited == 0.25


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.SEC.gov/files/x.json", "www.sec.gov"),
        ("https://exemple.test:8443/a", "exemple.test"),
        ("fichier-sans-hote", ""),
    ],
)
def test_lhote_est_extrait_en_minuscules_sans_port(url: str, expected: str) -> None:
    """Source (c) : urllib.parse.urlsplit documente hostname en minuscules, sans port."""
    assert host_of(url) == expected


def test_le_client_espace_deux_requetes_vers_le_meme_hote() -> None:
    """Source (a) : avec request_delay_s = 0,2 s, la deuxième requête attend 0,2 s."""
    client, _, clock = make_client([FakeResponse(200, b"ok")], request_delay_s=0.2)
    client.get("https://a.test/1")
    client.get("https://a.test/2")
    assert clock.sleeps == [0.2]


def test_le_client_nespace_pas_deux_hotes_differents() -> None:
    client, _, clock = make_client([FakeResponse(200, b"ok")], request_delay_s=0.2)
    client.get("https://a.test/1")
    client.get("https://b.test/1")
    assert clock.sleeps == []


@given(
    delay=st.floats(min_value=0.0, max_value=5.0, allow_nan=False),
    hosts=st.lists(st.sampled_from(["a.test", "b.test", "c.test"]), min_size=1, max_size=25),
)
@hyp_settings(max_examples=100, deadline=None)
def test_propriete_lespacement_minimal_est_toujours_tenu(delay: float, hosts: list[str]) -> None:
    """Source (b) : par construction, deux départs consécutifs vers un même hôte
    sont séparés d'au moins « delay » sur l'horloge, et l'attente rendue n'est
    jamais négative ni supérieure à « delay »."""
    clock = FakeClock(start=0.0)
    limiter = HostThrottle(delay, clock=clock.monotonic, sleeper=clock.sleep)
    last: dict[str, float] = {}
    for host in hosts:
        waited = limiter.wait(host)
        assert 0.0 <= waited <= delay + 1e-9
        departure = clock.t
        if host in last:
            assert departure - last[host] >= delay - 1e-9
        last[host] = departure


# ---------------------------------------------------------------------------
# Clé de cache
# ---------------------------------------------------------------------------


def test_la_cle_de_cache_est_stable_et_lisible() -> None:
    """Source (b) : la clé est déterministe, donc deux appels identiques coïncident."""
    first = cache_key("https://exemple.test/prix.csv", {"ticker": "SPY"})
    second = cache_key("https://exemple.test/prix.csv", {"ticker": "SPY"})
    assert first == second
    assert first.startswith("prix.csv-")


def test_lordre_des_parametres_nentre_pas_dans_la_cle() -> None:
    """Source (b) : les paramètres sont triés, donc l'ordre d'écriture est sans effet."""
    assert cache_key("https://exemple.test/x", {"a": 1, "b": 2}) == cache_key(
        "https://exemple.test/x", {"b": 2, "a": 1}
    )


def test_un_parametre_different_range_ailleurs() -> None:
    """Source (b) : deux requêtes différentes ne doivent pas partager un fichier."""
    assert cache_key("https://exemple.test/x", {"an": 2024}) != cache_key(
        "https://exemple.test/x", {"an": 2025}
    )


def test_la_cle_verifie_lempreinte_publiee_du_document_de_requete() -> None:
    """Sources (a) et (d) : le document est écrit à la main, hashlib le hache.

    Le document canonique d'une requête sans paramètre s'écrit clés triées, donc
    « params » avant « url ». Aucune ligne de ce test n'appelle la recette
    d'écriture du module : la chaîne est posée en toutes lettres, et seule
    hashlib, bibliothèque indépendante, en calcule l'empreinte.
    """
    url = "https://exemple.test/x"
    document = '{"params": {}, "url": "https://exemple.test/x"}'
    expected = hashlib.sha256(document.encode("utf-8")).hexdigest()[:16]
    assert expected == "df560ee5fd30f79d"  # Source (a) : mesuré le 2026-09-01 par hashlib.
    assert cache_key(url) == f"x-{expected}"


# ---------------------------------------------------------------------------
# BaseProvider et le cache brut
# ---------------------------------------------------------------------------


def test_le_fournisseur_tient_le_protocole_dataprovider(tmp_path: Path) -> None:
    """Source (b) : le protocole exige « name », « fetch » et « manifest »."""
    provider, _, _ = make_provider(tmp_path, [FakeResponse(200, b"ok")])
    assert isinstance(provider, DataProvider)


def test_un_fournisseur_sans_nom_est_refuse() -> None:
    with pytest.raises(ConfigError, match="name"):
        NamelessProvider()


def test_le_cache_brut_est_ecrit_avant_tout_parsage(tmp_path: Path) -> None:
    """Source (a) pour l'horodatage, source (d) pour l'empreinte.

    L'horloge factice est posée au 2026-09-01 12:00:00,000000 UTC, donc le nom
    du fichier commence par « 20260901T120000000000Z ». L'empreinte attendue est
    recalculée par hashlib sur les mêmes octets, jamais lue dans la sortie du
    code. « b65d9bb6 » est le début de SHA-256(« colonne\\n1\\n »), mesuré le
    2026-09-01 par un appel direct à hashlib.
    """
    contenu = b"colonne\n1\n"
    empreinte = hashlib.sha256(contenu).hexdigest()
    assert empreinte.startswith("b65d9bb6")
    provider, _, _ = make_provider(tmp_path, [FakeResponse(200, contenu)])
    provider.fetch_cached("https://exemple.test/prix.csv", params={"ticker": "SPY"})
    key = cache_key("https://exemple.test/prix.csv", {"ticker": "SPY"})
    directory = tmp_path / "raw" / "dummy" / key
    files = sorted(p.name for p in directory.glob("*.bin"))
    assert files == ["20260901T120000000000Z-b65d9bb6.bin"]
    assert (directory / files[0]).read_bytes() == contenu
    meta = json.loads((directory / files[0]).with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert meta["sha256"] == empreinte
    assert meta["provider"] == "dummy"
    assert meta["size_bytes"] == 10  # Source (a) : « colonne\n1\n » compte dix octets.
    assert meta["fetched_at"] == "2026-09-01T12:00:00+00:00"  # Source (a) : l'horloge factice.


def test_la_relecture_ne_touche_pas_au_reseau(tmp_path: Path) -> None:
    """Source (b) : le cache est la seule copie, donc la deuxième demande le relit."""
    provider, session, _ = make_provider(tmp_path, [FakeResponse(200, b"donnee")])
    first = provider.fetch_cached("https://exemple.test/a")
    second = provider.fetch_cached("https://exemple.test/a")
    assert len(session.calls) == 1
    assert second.content == b"donnee"  # Source (a) : les octets posés dans la doublure.
    assert second.content == first.content
    assert second.sha256 == first.sha256
    assert second.fetched_at == first.fetched_at


def test_les_en_tetes_retenus_survivent_a_la_relecture(tmp_path: Path) -> None:
    """Source (a) : « content-type » est dans RETAINED_HEADERS, « server » n'y est pas."""
    response = FakeResponse(200, b"x", headers={"Content-Type": "text/csv", "Server": "nginx"})
    provider, _, _ = make_provider(tmp_path, [response])
    provider.fetch_cached("https://exemple.test/a")
    relu = provider.fetch_cached("https://exemple.test/a")
    assert relu.headers == {"content-type": "text/csv"}


def test_un_rafraichissement_ajoute_un_fichier_sans_toucher_au_precedent(tmp_path: Path) -> None:
    """Source (b) : le cache brut ne se réécrit jamais, il s'accumule."""
    responses = [FakeResponse(200, b"version 1"), FakeResponse(200, b"version 2")]
    provider, session, clock = make_provider(tmp_path, responses, request_delay_s=60.0)
    provider.fetch_cached("https://exemple.test/a")
    clock.t += 3600.0  # une heure plus tard, donc un horodatage différent
    second = provider.fetch_cached("https://exemple.test/a", refresh=True)
    key = cache_key("https://exemple.test/a")
    files = sorted(p.name for p in (tmp_path / "raw" / "dummy" / key).glob("*.bin"))
    assert len(files) == 2
    assert len(session.calls) == 2
    assert second.content == b"version 2"
    # Le plus récent est le dernier par ordre alphabétique, l'horodatage étant en format compact.
    assert provider.cached_paths(key)[-1].read_bytes() == b"version 2"


def test_deux_telechargements_de_la_meme_seconde_restent_dans_lordre(tmp_path: Path) -> None:
    """Sources (a) et (d) : horodatages écrits à la main, empreintes par hashlib.

    Le contre-exemple qui motive ce test a été mesuré le 2026-09-01 sur la
    version précédente du module. L'horodatage s'arrêtait à la seconde, donc
    « version 2 » et « version 3 » écrits à une demi-seconde d'intervalle
    portaient tous deux « 20260901T120000Z ». Le tri des noms retombait alors
    sur l'empreinte du contenu, et « 791cad8c » passait avant « f4761aa0 ». La
    relecture rendait « version 2 », c'est-à-dire le plus ancien des deux.
    """
    responses = [FakeResponse(200, b"version 2"), FakeResponse(200, b"version 3")]
    provider, session, clock = make_provider(tmp_path, responses)
    provider.fetch_cached("https://exemple.test/a")
    clock.t += 0.5  # une demi-seconde plus tard, dans la même seconde civile
    provider.fetch_cached("https://exemple.test/a", refresh=True)
    ancien = hashlib.sha256(b"version 2").hexdigest()[:8]
    recent = hashlib.sha256(b"version 3").hexdigest()[:8]
    assert (ancien, recent) == ("f4761aa0", "791cad8c")  # Source (a) : mesuré par hashlib.
    key = cache_key("https://exemple.test/a")
    noms = [chemin.name for chemin in provider.cached_paths(key)]
    assert noms == [
        f"20260901T120000000000Z-{ancien}.bin",
        f"20260901T120000500000Z-{recent}.bin",
    ]
    assert len(session.calls) == 2
    assert provider.fetch_cached("https://exemple.test/a").content == b"version 3"


def test_un_contenu_different_au_meme_horodatage_est_refuse(tmp_path: Path) -> None:
    """Source (b) : deux contenus ne peuvent pas partager un fichier brut."""
    provider, _, _ = make_provider(tmp_path, [FakeResponse(200, b"premier")])
    raw = provider.fetch_cached("https://exemple.test/a")
    key = cache_key("https://exemple.test/a")
    path = provider.cached_paths(key)[0]
    path.write_bytes(b"autre chose")
    with pytest.raises(ProviderError, match="ne se réécrit pas"):
        provider._write_cached(key, raw)


def test_un_fichier_altere_est_signale_a_la_relecture(tmp_path: Path) -> None:
    """Source (b) : l'empreinte du manifeste et celle du contenu doivent coïncider."""
    provider, _, _ = make_provider(tmp_path, [FakeResponse(200, b"donnee saine")])
    provider.fetch_cached("https://exemple.test/a")
    path = provider.cached_paths(cache_key("https://exemple.test/a"))[0]
    path.write_bytes(b"donnee altere")
    with pytest.raises(DataQualityError, match="SHA-256"):
        provider.fetch_cached("https://exemple.test/a")


def test_un_manifeste_absent_est_signale(tmp_path: Path) -> None:
    provider, _, _ = make_provider(tmp_path, [FakeResponse(200, b"x")])
    provider.fetch_cached("https://exemple.test/a")
    path = provider.cached_paths(cache_key("https://exemple.test/a"))[0]
    path.with_suffix(".meta.json").unlink()
    with pytest.raises(DataQualityError, match="manifeste"):
        provider.fetch_cached("https://exemple.test/a")


def test_deux_parametres_differents_donnent_deux_dossiers(tmp_path: Path) -> None:
    provider, session, _ = make_provider(tmp_path, [FakeResponse(200, b"x")])
    provider.fetch_cached("https://exemple.test/a", params={"an": 2024})
    provider.fetch_cached("https://exemple.test/a", params={"an": 2025})
    assert len(session.calls) == 2
    dossiers = sorted(p.name for p in (tmp_path / "raw" / "dummy").iterdir())
    assert len(dossiers) == 2


def test_le_cache_est_vide_avant_tout_telechargement(tmp_path: Path) -> None:
    """Cas limite : aucun fichier, aucun dossier."""
    provider, _, _ = make_provider(tmp_path, [FakeResponse(200, b"x")])
    assert provider.cached_paths("cle-inexistante") == []


def test_une_reponse_vide_est_mise_en_cache_et_relue(tmp_path: Path) -> None:
    """Cas limite du contenu vide, qui reste une réponse et se conserve."""
    provider, session, _ = make_provider(tmp_path, [FakeResponse(200, b"")])
    provider.fetch_cached("https://exemple.test/vide")
    relu = provider.fetch_cached("https://exemple.test/vide")
    assert relu.content == b""
    assert len(session.calls) == 1


@given(payload=st.binary(min_size=0, max_size=512))
@hyp_settings(max_examples=50, deadline=None)
def test_propriete_le_cache_rend_les_octets_recus(
    payload: bytes, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Source (b) : l'aller-retour par le cache est l'identité sur le contenu,
    et l'empreinte relue est celle que hashlib calcule sur ces mêmes octets."""
    root = tmp_path_factory.mktemp("cache")
    provider, _, _ = make_provider(root, [FakeResponse(200, payload)])
    ecrit = provider.fetch_cached("https://exemple.test/a")
    relu = provider.fetch_cached("https://exemple.test/a")
    assert relu.content == payload
    assert relu.sha256 == hashlib.sha256(payload).hexdigest()
    assert ecrit.sha256 == relu.sha256


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


def test_chaque_requete_est_journalisee_avec_ses_champs(caplog: pytest.LogCaptureFixture) -> None:
    """La consigne du module impose hôte, code, durée et taille sur chaque requête."""
    client, _, _ = make_client([FakeResponse(200, b"12345")])
    with caplog.at_level("INFO", logger="quantlab"):
        client.get("https://exemple.test/a")
    lignes = [r for r in caplog.records if r.getMessage() == "requête HTTP"]
    assert len(lignes) == 1
    record = lignes[0]
    assert record.host == "exemple.test"
    assert record.status == 200
    assert record.bytes == 5  # Source (a) : « 12345 » compte cinq octets.
    assert hasattr(record, "duration_s")


def test_une_session_fournie_de_lexterieur_nest_pas_fermee() -> None:
    """Source (b) : qui ouvre ferme. Le client n'a pas créé cette session."""
    session = FakeSession([FakeResponse(200, b"ok")])
    with HttpClient(settings=make_settings(), session=session):
        pass
    assert session.closed is False


def test_la_session_creee_par_le_client_est_fermee(monkeypatch: pytest.MonkeyPatch) -> None:
    """Source (b) : la règle inverse. Le client ferme ce qu'il a ouvert.

    La fabrique ``requests.Session`` est remplacée par la doublure, donc aucune
    connexion n'est ouverte et le test reste hors réseau.
    """
    session = FakeSession([FakeResponse(200, b"ok")])
    monkeypatch.setattr(base_module.requests, "Session", lambda: session)
    with HttpClient(settings=make_settings()):
        pass
    assert session.closed is True


# ---------------------------------------------------------------------------
# Le seul test réseau
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_la_sec_repond_200_avec_un_courriel_dans_len_tete() -> None:
    """Rejoue la mesure du 2026-09-01 avec le contact réel du poste.

    L'en-tête vient de ``QUANTLAB_USER_AGENT`` plutôt que d'une adresse écrite
    dans le dépôt : envoyer un contact inventé à un service public n'est pas
    acceptable. Sans ce réglage, le test est sauté et le dit.

    Mesuré le 2026-09-01 par appels directs, chaque cas refait deux fois :
    ``quantlab research (contact@uqam.ca)`` reçoit un 200 et
    ``quantlab research (contact@github.com)`` un 403, à en-tête identique par
    ailleurs. Le domaine du courriel décide, ce qu'aucune documentation
    n'annonce.
    """
    agent = os.environ.get("QUANTLAB_USER_AGENT", "")
    try:
        check_user_agent(agent, require_email=True)
    except ConfigError as exc:
        pytest.skip(f"QUANTLAB_USER_AGENT absent ou sans courriel : {exc}")
    client = HttpClient(
        settings=make_settings(user_agent=agent, request_delay_s=1.0),
        require_email_contact=True,
    )
    raw = client.get("https://www.sec.gov/robots.txt")
    client.close()
    assert raw.status_code == 200
    assert raw.size_bytes > 0
    assert raw.sha256 == hashlib.sha256(raw.content).hexdigest()
