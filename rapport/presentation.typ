#set document(title: "Vérifier qu'une stratégie résiste à de nouveaux tests", author: "Guillaume Vaudescal")
#set page(
  paper: "a4",
  margin: (x: 2.2cm, y: 2.4cm),
  numbering: "1 / 1",
  footer: context [
    #set text(size: 8pt, fill: luma(90))
    #grid(columns: (1fr, auto), align: (left, right),
      [quant-research-platform], [#counter(page).display("1 / 1", both: true)])
  ],
)
#set text(font: ("Helvetica", "Arial", "DejaVu Sans"), size: 10pt, lang: "fr")
#set par(justify: true, leading: 0.68em, spacing: 1.1em)
#set heading(numbering: none)
#show heading.where(level: 2): it => block(above: 1.6em, below: 0.8em, text(size: 13pt, it))
#show heading.where(level: 3): it => block(above: 1.2em, below: 0.6em, text(size: 11pt, it))
#show raw.where(block: true): it => block(
  fill: luma(246), inset: 8pt, radius: 3pt, width: 100%, text(size: 8.5pt, it))
#show raw.where(block: false): it => text(size: 9pt, fill: rgb("#1a3f66"), it)
#show quote.where(block: true): it => block(
  inset: (left: 10pt), stroke: (left: 1.5pt + luma(180)),
  text(style: "italic", fill: luma(45), it.body))
// la table NE DOIT PAS être enfermée dans un par() : Typst 0.15 la supprime alors
// entièrement, sans erreur. Le réglage se pose donc dans la portée du bloc.
#show table: it => block(above: 1.1em, below: 1.1em,
  [#set par(justify: false); #text(size: 8.8pt, it)])
#show figure: it => block(above: 1.4em, below: 1.4em, it)
#show figure.caption: it => text(size: 8.5pt, fill: luma(70), it)
#show link: it => text(fill: rgb("#0072B2"), it)

#align(center)[
  #block(width: 100%)[
    #text(size: 18pt, weight: "bold")[Vérifier qu'une stratégie résiste à de nouveaux tests]
    #v(0.6em)
    #text(size: 10pt, fill: luma(70))[Guillaume Vaudescal · 2026-09-08 · #link("https://github.com/Guilou001/quant-research-platform")[Guilou001/quant-research-platform]]
  ]
]
#v(1.2em)
#line(length: 100%, stroke: 0.6pt + luma(190))
#v(0.8em)

Une stratégie peut réussir sur les données qui ont servi à la choisir, puis échouer dès qu'on change de période. Essayer beaucoup de variantes augmente aussi la chance de trouver un beau résultat par hasard.

Ce dépôt organise la recherche pour rendre ces pièges visibles. Chaque étude conserve ses données, ses hypothèses, ses essais et ses résultats.

*La plateforme sert à décider si les preuves sont suffisantes avant d'envisager une allocation. Elle ne transforme pas un bon test historique en promesse de rendement.*

== Choisir une porte d'entrée

#table(
  columns: 2,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Votre question*],
    [*Où regarder*],
    [Que montrent les études terminées ?],
    [#link("docs/dashboard/index.md")[Tableau de bord des résultats]],
    [Que reste-t-il après la publication d'une stratégie ?],
    [#link("studies/016_publication_decay_212/")[Étude des 212 portefeuilles]],
    [Que change l'oubli des actions disparues ?],
    [#link("studies/013_cross_sectional_ml_long/")[Étude du biais de survie]],
    [Le même calcul fonctionne-t-il dans un autre moteur ?],
    [#link("lean/README.md")[Comparaison avec LEAN]],
    [Comment les données et les tests sont-ils organisés ?],
    [#link("docs/architecture/index.md")[Architecture]],
)

Le #link("https://guilou001.github.io/quant-research-platform/")[site de documentation] et le #link("rapport/rapport.pdf")[rapport complet du tableau de bord] rassemblent les résultats détaillés.

== Un exemple de résultat qui perd de sa force

L'étude 016 compare le rendement de portefeuilles d'actions américaines avant et après la publication de la stratégie. La comparaison est calculable pour 208 des 212 portefeuilles disponibles.

#figure(image("../docs/figures/presentation_publication.png", width: 100%), caption: [Nombre de portefeuilles dont le rendement baisse après publication])

Sur ces 208 comparaisons, 172 montrent un rendement plus faible après publication. Les rendements sont mesurés avant frais. Chaque portefeuille utilise les dates de son article, au sein de données couvrant 1926 à 2024.

Le portefeuille médian conserve environ 42 % de son rendement antérieur. La moyenne des rapports en conserve environ 53 %. Ces deux statistiques répondent à des questions différentes.

Ce constat ne prouve pas que la publication cause la baisse. Il ne reproduit pas non plus, à lui seul, la régression de l'article de référence. #link("studies/016_publication_decay_212/results/metrics.json")[Mesures complètes].

== Ce que la plateforme vérifie

Elle sépare les périodes utilisées pour choisir une stratégie de celles utilisées pour l'évaluer. Elle compte les variantes essayées, estime les coûts et conserve la provenance des données.

Elle peut aussi comparer deux moteurs indépendants et rééchantillonner des blocs de dates pour mesurer l'incertitude.

== Ce qui limite les conclusions

Toutes les études n'ont pas des données de même qualité. Certaines utilisent les titres encore présents aujourd'hui, ce qui peut oublier les entreprises disparues.

L'étude des 212 portefeuilles évite ce biais de survie, mais utilise une version récente des historiques. Elle ne restitue pas nécessairement les données exactement telles qu'elles étaient connues à chaque date.

Le tableau de bord signale ces différences. Ses courbes ne constituent donc pas un classement uniforme de stratégies investissables.

== Explorer et vérifier le dépôt

#raw("uv sync --locked --all-extras --dev\nuv run quant info\nmake lint\nmake test\nmake docs", block: true, lang: "bash")

Ces commandes vérifient le socle et construisent la documentation. Les téléchargements et calculs propres à chaque étude ont leurs commandes séparées, indiquées dans son dossier. Le graphique de présentation se régénère hors réseau avec #raw("uv run python scripts/figure_presentation.py"), depuis les tableaux publiés.

== Pour aller plus loin

#link("ETUDE_DETAILLEE.md")[Méthodes, résultats complets et références] · #link("rapport/presentation.pdf")[Présentation en PDF] · #link("CITATION.cff")[Citer le projet] · #link("LICENSE")[Licence].

== English summary

A research platform tracks data, trials, costs and validation across investment studies. One study finds lower post-publication returns for 172 of 208 comparable US portfolios, before costs. Data quality varies across studies, so dashboard curves are not a uniform investable ranking.
