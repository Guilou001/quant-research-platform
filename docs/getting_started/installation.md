# Installation

## Ce qu'il faut avoir

| Outil | Version mesurée le 2026-09-01 | Pourquoi |
|---|---|---|
| Python | 3.12 ou plus | pandas 3 et numpy 2.5 l'exigent |
| uv | 0.12.5 | gestion de l'environnement et verrou reproductible |
| git | quelconque | l'empreinte de commit entre dans chaque expérience |

Sur macOS, `lightgbm` exige `libomp` : `brew install libomp`. Sans lui,
l'installation réussit et l'import échoue.

## Installer

```bash
git clone https://github.com/Guilou001/quant-research-platform
cd quant-research-platform
make install          # uv sync --all-extras --dev
```

Le verrou `uv.lock` est commité. La même commande sur une autre machine installe
les mêmes versions, ce qui est la première condition de la reproductibilité.

## Configurer

```bash
cp .env.example .env
```

Un seul champ compte vraiment :

```bash
QUANTLAB_USER_AGENT="Prénom Nom courriel@exemple.com"
```

La SEC refuse les requêtes sans identification, et son refus est un `403` sans
message explicite. Le reste est facultatif : l'export CSV de FRED fonctionne
sans clé.

## Vérifier que tout marche

```bash
make lint        # ruff format --check puis ruff check
make test        # pytest, tests réseau exclus
make docs        # mkdocs build --strict
```

Les trois doivent passer. `make test` n'a besoin d'aucun accès réseau : les
fournisseurs de données sont testés contre des réponses enregistrées dans les
tests.

Pour vérifier aussi les sources distantes :

```bash
uv run pytest -m network
```

## Les commandes du laboratoire

```bash
uv run quant --help
uv run quant info                 # versions, chemins, état du lac
uv run quant data list            # les jeux présents et leur étage
uv run quant data check <jeu>     # les contrôles de qualité
```

Les commandes des phases ultérieures (`quant study run`, `quant backtest run`,
`quant portfolio build`, `quant report generate`) apparaîtront avec leurs
phases.
