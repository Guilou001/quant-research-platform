# Le journal de recherche

Un laboratoire qui ne garde que ses réussites ne sait plus, six mois plus tard,
combien de fois il a essayé. Ce nombre est pourtant l'intrant du ratio de Sharpe
dégonflé : le cacher fausse précisément le test qui sert à détecter le
surapprentissage.

Le journal existe aussi contre le biais rétrospectif. Écrire ce qu'on attendait
**avant** de mesurer empêche de se souvenir après coup qu'on l'avait prévu.

## Le gabarit d'une entrée

Chaque décision de recherche donne une entrée, dans un fichier daté
`AAAA-MM-JJ-sujet.md` :

```
Date
Question           la tension entre deux faits, pas une demande d'information
Hypothèse          une phrase affirmative qui pourrait être fausse
Expérience         ce qui a été fait, avec la configuration et la graine
Résultat           ce qui est sorti, chiffres et statut de chaque chiffre
Décision           ce qu'on retient, ce qu'on abandonne
Question suivante  ce que ce résultat ouvre
```

La ligne « Hypothèse » s'écrit avant de lancer l'expérience. C'est la seule
règle du journal qui ne se rattrape pas après coup.

## Les entrées

| Date | Sujet | Décision |
|---|---|---|
| [2026-09-01](2026-09-01-fondations.md) | choix du socle technique et des sources | socle mesuré, SEC débloquée, Plotly borné |
| [2026-09-01](2026-09-01-restatements-apple.md) | ce que le point-in-time change, mesuré | règle conservée, révision de 11,8 % trouvée |
| [2026-09-02](2026-09-02-phase-4.md) | huit réplications, aucune retenue | le parcours de validation est conservé |
| [2026-09-02](2026-09-02-phases-5-7.md) | huit stratégies rejetées, combinées | la diversification travaille, la référence déclarée tient |
| [2026-09-02](2026-09-02-phase-6-capacite.md) | la capacité des deux stratégies chiffrables, et dix fonds fermés | phase 6 close, capacité bornée par la participation ou nulle |
| [2026-09-02](2026-09-02-phase-8-apprentissage.md) | arbres contre régression, après coûts | phase 8 close, le linéaire est gardé |
| [2026-09-03](2026-09-03-phase-10-tableau-de-bord.md) | tableau de bord et rapport engendrés depuis les fichiers | phase 10 close, `quant report` en une commande |
| [2026-09-03](2026-09-03-dettes-avril-2020-et-series-nettes.md) | un mois de taux manquant, et le portefeuille sur séries nettes | chiffres de 008 et 009 relus, étude 012 `REJECTED`, la diversification ne paie pas net |
| [2026-09-03](2026-09-03-quarante-ans-de-survivants.md) | arbres contre régression sur quarante ans de survivants | `REJECTED` ; le biais de survie fabrique deux renversements, mesuré contre Kenneth French |
| [2026-09-03](2026-09-03-phase-9-lean.md) | le même momentum dans deux moteurs | phase 9 close, LEAN retrouve le laboratoire à 4e-6 par mois, une séance de retard coûte 71 pb/an |
| [2026-09-03](2026-09-03-phase-11-publication.md) | ce que la publication laisse, huit stratégies ensemble | `EXPERIMENTAL` ; 67 à 73 % de baisse après publication contre 58 % publié, rien avant |
| [2026-09-03](2026-09-03-audit-des-phases-9-et-11.md) | l'audit des phases 9 et 11 | 33 constats corrigés, l'ouverture réelle coûte 25 pb/an, ADR-016 |
| [2026-09-04](2026-09-04-chantier-1-polygon.md) | la porte de Polygon, ouverte sur le référentiel, fermée sur les prix | 015 `REJECTED` ; deux ans de prix, 6 425 radiations datées, la moitié des actions de 2014 disparues |
| [2026-09-04](2026-09-04-chantiers-2-3-4.md) | la largeur, la rotation et la nuit | 016 `EXPERIMENTAL`, 017 `REJECTED`, 018 `EXPERIMENTAL` ; le momentum gagne la nuit, la publication laisse la moitié à tous |
| [2026-09-04](2026-09-04-chantier-6-crypto.md) | les facteurs des cryptomonnaies, quatre ans après leur article | 019 `REJECTED` ; les cinq sixièmes du rendement disparus, le momentum tourne 204 % par semaine |
| [2026-09-04](2026-09-04-chantier-5-13f.md) | les meilleures idées des gestionnaires, lues à leur date de dépôt | 020 `REJECTED` ; +0,27 %/an sur le marché, t 0,26, bêta 1,08 ; 28,9 % des idées sans prix, la valeur 13F en milliers jusqu'en 2022 |

## Les idées rejetées

Les échecs vivent dans [rejected_ideas.md](rejected_ideas.md), et ils comptent
autant que le reste. Une stratégie qui ne fonctionne pas est une information
publiable ; la taire est ce qui produit le biais de publication de la
littérature financière.
