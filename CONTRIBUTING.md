# Contribuer

Le dépôt est d'abord un travail de recherche personnel. Les règles ci-dessous
valent donc autant pour son auteur que pour un contributeur extérieur : elles
existent pour empêcher un résultat faux d'entrer, pas pour filtrer les gens.

## Avant d'écrire une ligne

Lire [`CLAUDE.md`](CLAUDE.md), qui porte les quinze règles, puis
[`docs/architecture/adr/`](docs/architecture/adr/index.md), qui dit pourquoi les
frontières sont là où elles sont. Une brique qui ne respecte pas son protocole
n'est plus remplaçable, et c'est exactement ce que l'architecture cherche à
éviter.

## Le cycle

```bash
make install
make lint      # ruff format --check puis ruff check
make test      # pytest, tests réseau exclus
make docs      # mkdocs build --strict
```

Les trois doivent passer avant tout commit. `pre-commit install` les lance en
partie automatiquement.

## Les trois refus

**Un test dont la valeur attendue vient de la sortie du code.** Il verrouille le
bogue au lieu de l'attraper. Toute valeur attendue vient d'un calcul à la main
écrit en commentaire, d'une identité mathématique, d'une valeur publiée et
citée, ou d'une bibliothèque indépendante. Le commentaire dit laquelle.

**Une métrique financière implémentée une seconde fois.** Le ratio de Sharpe
vit dans `quantlab.analytics.ratios` et nulle part ailleurs.

**Un chiffre sans son statut.** Mesuré, rapporté, précepte, modélisé, ou non
trouvé. Une information absente s'écrit comme absente.

## Ajouter une étude

Une étude commence par sa fiche de littérature dans `docs/literature/`, pas par
du code. La fiche porte l'hypothèse économique, la méthodologie originale, les
résultats publiés qui serviront de cible, et les critiques connues.

Ensuite seulement vient `studies/NNN_nom/`, avec son README, sa configuration et
son point d'entrée. Le gabarit vit dans [`studies/README.md`](studies/README.md).

## Le style d'écriture

Français pour la prose, anglais pour le code. Pas de tiret cadratin. Aucune
phrase de prose au-dessus de trente-cinq mots. La réponse d'abord, le
raisonnement ensuite.

Ces règles ne sont pas des préférences : `tests/unit/test_architecture.py` les
vérifie mécaniquement, et la CI échoue si elles sont violées.
