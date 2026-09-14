# 001 Suivre une tendance après sa publication

Le suivi de tendance consiste à acheter un actif après une hausse passée, ou à prendre une position vendeuse après une baisse.
L'étude demande si cette règle reste rémunérée après sa diffusion dans la littérature.

Le facteur des auteurs passe d'un Sharpe de {{s001_before}} sur 1985-2009 à {{s001_after}} après juin 2012, jusqu'en juin 2026.
Il s'agit de la série publiée, avant les coûts d'une reconstruction négociable.
Le ratio de Sharpe compare le rendement excédentaire moyen à sa dispersion.

## Une intuition et un exemple fictif

Un actif a gagné 12 % pendant la période d'observation.
La règle de tendance prend une position acheteuse pour la période suivante.
Si l'actif perd alors 3 %, la position perd également 3 % avant levier et frais.

La règle ne sait pas que la tendance continuera.
Elle parie sur une persistance moyenne, qui peut coexister avec des renversements coûteux.

## Le lien avec l'article

Moskowitz, Ooi et Pedersen étudient des contrats à terme sur plusieurs classes d'actifs.
Notre reconstruction utilise vingt-huit fonds négociés en bourse.
Les expositions, les horaires, les frais et les possibilités de vente ne sont donc pas identiques.

La [fiche de littérature](repo:docs/literature/moskowitz_ooi_pedersen_2012.md) présente aussi les explications concurrentes.
Une partie du résultat peut venir du ciblage de volatilité ou d'une exposition acheteuse moyenne.
Retrouver un rendement positif ne permet pas, seul, de les départager.

## Ce qu'il faut retenir

L'affaiblissement du facteur publié est un constat historique.
Il ne démontre pas que la publication est son unique cause.
La reconstruction conserve des mouvements communs avec ce facteur, tout en obtenant un résultat différent après coûts.

L'[étude 017](repo:docs/etudes/017_viser_devant_la_cible.md) demande ensuite si échanger moins souvent améliore ce résultat.
La [comparaison avec LEAN](repo:lean/README.md) examine l'exécution dans un second moteur.

## Vérifier le résultat

Les [mesures enregistrées](repo:studies/001_time_series_momentum/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](repo:studies/001_time_series_momentum/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](repo:studies/001_time_series_momentum/run.py) relie ces choix aux fonctions du laboratoire.
