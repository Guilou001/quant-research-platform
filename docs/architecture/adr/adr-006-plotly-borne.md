# ADR-006 : Plotly borné sous la version 7 tant que VectorBT ne suit pas

**Statut** : acceptée le 2026-09-01. À revoir dès que VectorBT publie un
correctif.

## Contexte

Mesuré le 2026-09-01 dans un environnement neuf : `import vectorbt` échoue avec
Plotly 7.0.0. L'erreur est nette.

```
ValueError: Invalid property specified for object of type
plotly.graph_objs.layout.template.Data: 'scattermapbox'
```

VectorBT 1.1.0 enregistre un gabarit Plotly qui déclare une trace
`scattermapbox`. Plotly a retiré les traces Mapbox en version 7, et l'accès à un
nom de trace inconnu lève à l'import, pas à l'usage. La bibliothèque est donc
inutilisable, pas seulement dégradée.

La borne haute a été cherchée, pas supposée. Quatre versions ont été installées
successivement et `import vectorbt` a été relancé après chacune :

| Plotly | `import vectorbt` |
|---|---|
| 5.24.1 | passe |
| 6.0.1 | passe |
| 6.3.1 | passe |
| 6.5.0 | passe |
| 7.0.0 | échoue |

## Décision

Les extras `research` et `figures` déclarent `plotly>=6.3,<7`. Le verrou
`uv.lock` fixe Plotly en 6.9.0.

La borne est écrite dans `pyproject.toml` avec un commentaire qui renvoie à
cette fiche, pour qu'un lecteur futur sache que la contrainte a une cause et une
condition de levée.

## Conséquences

Les nouveautés de Plotly 7 sont indisponibles. Aucune n'est nécessaire aux
figures prévues.

Le jour où VectorBT corrige son gabarit, la borne se retire en une ligne et
`uv lock` suffit. La condition de levée est explicite : que `import vectorbt`
passe avec Plotly 7, ce qui se vérifie en une commande.

## Options écartées

**Abandonner VectorBT.** Rejetée pour l'instant : le prototypage vectorisé et
les balayages de paramètres sont utiles à la phase de robustesse, et rien
d'équivalent n'existe en source ouverte avec la même maturité.

**Isoler VectorBT dans un environnement séparé.** Rejetée pour le coût : deux
environnements à synchroniser, deux verrous, et une frontière de plus à
franchir pour un gain nul tant que Plotly 6 suffit.

**Corriger le gabarit de VectorBT au chargement.** Rejetée pour la fragilité :
rustiner une bibliothèque tierce au moment de l'import rend le comportement
dépendant de l'ordre des imports, ce qui est exactement le genre de fragilité
qu'un laboratoire reproductible ne peut pas se permettre.
