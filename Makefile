.PHONY: help install lint format test test-all cov docs docs-serve clean lock

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Installe l'environnement complet
	uv sync --all-extras --dev

lock:  ## Regénère uv.lock
	uv lock

format:  ## Met le code au format
	uv run ruff format .
	uv run ruff check --fix .

lint:  ## Vérifie le format et le lint sans rien modifier
	uv run ruff format --check .
	uv run ruff check .

test:  ## Tests hors réseau
	uv run pytest -m "not network"

test-all:  ## Tous les tests, réseau compris
	uv run pytest

cov:  ## Tests avec couverture
	uv run pytest -m "not network" --cov --cov-report=term-missing --cov-report=html

docs:  ## Construit le site de documentation
	uv run mkdocs build --strict

docs-serve:  ## Sert la documentation en local
	uv run mkdocs serve

clean:  ## Efface les caches
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage site
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
