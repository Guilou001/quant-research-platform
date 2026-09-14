# 017 Échanger moins permet-il de gagner davantage après frais ?

Un signal propose une position cible.
La rejoindre immédiatement coûte des échanges.
S'en approcher progressivement économise parfois des frais, mais retarde aussi la prise de position.

## Un exemple fictif

Le portefeuille détient 20 dollars et le signal demande d'en détenir 100.
Rejoindre toute la cible exige un achat de 80 dollars.
Parcourir la moitié du chemin demande un achat de 40 dollars et laisse une position de 60 dollars.

Si le signal persiste, la seconde règle pourra continuer à s'en approcher.
S'il change rapidement, le retard peut faire perdre une partie de son intérêt.

## Le lien avec l'article

Gârleanu et Pedersen étudient une décision dynamique avec rendements prévisibles et coûts.
Leur cible tient compte de l'évolution attendue des signaux.
Notre règle simplifiée avance d'une fraction fixe vers la cible courante du suivi de tendance.

Cette expérience n'est donc pas une réplication de toute la solution optimale.
La [fiche de littérature](../literature/garleanu_pedersen_2013.md) explique la différence.

## La comparaison retenue

La vitesse de moitié est choisie sur la période antérieure à la publication.
Sur les 169 mois suivants, jusqu'en juin 2026, les résultats nets sont les suivants.

| Règle | Rotation annuelle en fois le capital | Sharpe net |
|---|---:|---:|
| Rejoindre la moitié du chemin | 5,75 | 0,162 |
| Rejoindre toute la cible | 9,15 | 0,176 |

Les coûts sont modélisés et comprennent les hypothèses détaillées dans l'annexe.
La rotation diminue, mais la performance ajustée de sa dispersion ne s'améliore pas dans cette comparaison.

## Le meilleur réglage observé ne devient pas la règle retenue

Un réglage plus lent gagne dans la période finale.
Le choisir après coup ne fournirait pas une preuve indépendante sur cette période.
Il peut servir d'hypothèse pour un prochain test, avec un nouveau protocole.

Cette distinction est le sujet du [chapitre sur le calendrier](../guide/03_calendrier.md).

## Vérifier le résultat

Les [mesures enregistrées](https://github.com/Guilou001/quant-research-platform/blob/main/studies/017_viser_devant_la_cible/results/metrics.json) donnent les nombres et leurs fenêtres.
L'[annexe technique](https://github.com/Guilou001/quant-research-platform/blob/main/studies/017_viser_devant_la_cible/ANNEXE_TECHNIQUE.md) conserve les tableaux, les hypothèses, les limites et les commandes de calcul.
Le [script de l'étude](https://github.com/Guilou001/quant-research-platform/blob/main/studies/017_viser_devant_la_cible/run.py) relie ces choix aux fonctions du laboratoire.
