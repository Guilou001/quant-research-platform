#set document(title: "Comprendre et vérifier une recherche en finance", author: "Guillaume Vaudescal")
#set page(
  paper: "a4",
  margin: (x: 2.2cm, y: 2.1cm),
  numbering: "1 / 1",
  footer: context [
    #set text(size: 8pt, fill: luma(90))
    #grid(columns: (1fr, auto), align: (left, right),
      [Comprendre et vérifier une recherche en finance], [#counter(page).display("1 / 1", both: true)])
  ],
)
#set text(font: ("Helvetica", "Arial", "DejaVu Sans"), size: 10pt, lang: "fr")
#set par(justify: true, leading: 0.46em, spacing: 0.75em)
#set heading(numbering: none)
#show table: it => block(breakable: false, it)

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
    #text(size: 18pt, weight: "bold")[Comprendre et vérifier une recherche en finance]
    #v(0.6em)
    #text(size: 10pt, fill: luma(70))[Guillaume Vaudescal · 13 septembre 2026 · #link("https://github.com/Guilou001/quant-research-platform")[github.com/Guilou001/quant-research-platform]]
  ]
]
#v(1.2em)
#line(length: 100%, stroke: 0.6pt + luma(190))
#v(0.8em)

Un cours appliqué et vingt et une études à lire avec leurs hypothèses.

Les exemples fictifs enseignent les calculs. Les études décrivent des résultats historiques.

Version pédagogique. Les expériences initiales sont conservées dans les annexes techniques.

#pagebreak(weak: true)
#pagebreak()
#outline(title: [Parcours de lecture], depth: 2)
#pagebreak()
== 01 Partir d'une question économique

Une stratégie est une règle qui transforme une information en positions. Avant de mesurer son rendement, il faut expliquer pourquoi quelqu'un pourrait être payé pour la suivre. Cette explication donne aussi une raison de chercher où la règle échoue.

Le momentum est un exemple. Il consiste à suivre une hausse ou une baisse passée. La question est de savoir si cette tendance renseigne encore sur les prochains rendements. Dire que « le prix monte parce qu'il montait » décrit la règle, sans expliquer le mécanisme.

=== Trois explications à départager

Une prime de risque rémunère une perte possible que d'autres investisseurs souhaitent éviter. Une erreur de prix peut venir d'une réaction lente ou excessive à une information. Une contrainte peut empêcher certains investisseurs de prendre une position, même si elle leur paraît intéressante.

Ces explications peuvent coexister. Une baisse après publication ne suffit pas à choisir entre elles. Les risques, les coûts, la concurrence et les conditions économiques ont aussi pu changer.

=== Un exemple fictif

Un contrat verse régulièrement un petit revenu, mais impose une grosse perte lors d'une crise. Un autre exploite une information mal comprise et cesse de rapporter quand elle devient connue.

Les deux peuvent afficher le même rendement moyen sur une période courte. Le premier rémunère éventuellement un risque rare. Le second dépend éventuellement d'une erreur qui peut disparaître. Pour les distinguer, il faut examiner les pertes, les dates et les expositions.

Le rendement moyen répond donc à une seule question, combien le placement a rapporté en moyenne dans cet échantillon. Il ne dit pas pourquoi, ni si la rémunération compense les risques.

=== Comment le laboratoire pose sa question

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/001_time_series_momentum.md")[étude 001] examine le suivi de tendance après publication. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/008_carry.md")[étude 008] s'intéresse au portage de devises. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/021_portefeuille_de_primes.md")[étude 021] combine plusieurs sources de rendement et étudie leurs risques communs.

Les articles proposent des mécanismes et des mesures. Le laboratoire distingue leurs résultats rapportés des calculs reproduits et des adaptations nécessaires aux données disponibles. Une ressemblance de chiffre ne suffit pas à reproduire tout un article.

=== La question à garder pour la suite

Avant un test, écrivez la règle, le mécanisme envisagé et le résultat qui vous ferait douter. Indiquez aussi le placement de comparaison. Une stratégie qui monte de 8 % lorsque son repère monte de 12 % n'a pas montré une supériorité par son seul rendement positif.

La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/moskowitz_ooi_pedersen_2012.md")[fiche de Moskowitz, Ooi et Pedersen] illustre ce travail préparatoire. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/02_donnees.md")[chapitre suivant] examine ce que les données permettent réellement de tester.

#pagebreak(weak: true)
== 02 Savoir ce que l'investisseur pouvait connaître

Une donnée financière possède plusieurs dates. La fin d'un trimestre indique la période décrite. Le dépôt du rapport indique quand son contenu devient accessible. Employer le chiffre dès la première date peut donner au modèle une information venue du futur.

Le terme *point-in-time* désigne ici une lecture qui respecte la disponibilité historique de l'information. Il faut également examiner les corrections apportées plus tard et la date à laquelle notre fournisseur les rend accessibles.

=== Un exemple fictif

Une entreprise clôture son trimestre le 31 mars et publie son bénéfice le 10 mai. Un portefeuille formé le 30 avril ne peut pas utiliser ce bénéfice. Celui formé après sa publication peut l'utiliser, sous réserve de la convention d'heure et d'exécution.

Le bénéfice est corrigé en août. Le test d'avril ne doit connaître ni le chiffre de mai, ni sa correction d'août. Conserver seulement la dernière version d'un fichier empêche parfois de restituer cette chronologie.

=== Une autre question indépendante

Quelles entreprises étaient accessibles à l'investisseur ? Prendre la liste des entreprises présentes aujourd'hui pour simuler 1996 utilise une sélection faite après 1996. Certaines entreprises disparues ont fait faillite. D'autres ont été acquises avec une prime.

Le *biais de survie* vient de cette sélection des observations conservées. Son effet dépend des entreprises manquantes et de la règle de placement. Il ne gonfle pas nécessairement tous les rendements ou tous les ratios de Sharpe.

#figure(image("../docs/guide/figures/survie_exemple.png", width: 100%), caption: [Capital final avec et sans les deux entreprises disparues dans un exemple fictif])

Dans cet exemple, cinq placements de 100 dollars deviennent 120, 110, 90, 0 et 0 dollars. Le portefeuille complet perd 36 %. Ne garder que les trois premiers fait apparaître un gain de 6,67 %. Les montants sont fictifs. Le graphique illustre un mécanisme possible, sans mesurer le biais du panel réel.

=== Lire les limites d'une source

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/013_cross_sectional_ml_long.md")[étude 013] montre pourquoi un historique plus long ne répare pas une sélection incomplète. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/015_univers_polygon.md")[étude 015] distingue une liste de titres radiés de leurs prix effectivement accessibles. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/020_meilleures_idees_13f.md")[étude 020] utilise la date de dépôt des déclarations de gestionnaires, mais reste limitée par les prix manquants.

Les facteurs publiés à partir de CRSP peuvent inclure les titres radiés. Ils ne restituent pas nécessairement toutes les versions historiques des données. Un univers complet et une information correctement datée sont deux qualités distinctes.

Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/data/point_in_time.md")[guide des données datées] décrit les champs employés par le code. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/03_calendrier.md")[chapitre suivant] organise les périodes du test.

#pagebreak(weak: true)
== 03 Séparer ce qui sert à apprendre de ce qui sert à juger

Un modèle apprend des relations sur des observations anciennes. Ses paramètres peuvent ensuite être choisis sur une période de validation. Une troisième période sert à évaluer le choix retenu, sans recommencer la sélection en regardant son résultat.

Ces trois rôles évitent une confusion courante. Un paramètre peut sembler bon parce qu'il a été choisi pour réussir précisément sur les données qui servent ensuite à le vanter.

=== Un calendrier fictif

On apprend sur janvier 2010 à décembre 2017. On choisit les paramètres sur 2018 et 2019. On évalue une fois le choix retenu sur 2020 à 2022.

Ces dates sont pédagogiques. Les études utilisent leurs propres fenêtres.

#figure(image("../docs/guide/figures/calendrier.png", width: 100%), caption: [Trois périodes séparées dans un calendrier fictif])

Le modèle peut être réestimé à chaque date selon une règle fixée d'avance. Il doit alors utiliser uniquement les observations devenues disponibles. Ce protocole est souvent appelé évaluation en fenêtre glissante ou croissante, selon les observations conservées.

=== Pourquoi une frontière ne suffit pas

Une observation formée fin décembre peut viser le rendement de janvier. Si janvier appartient à la période de test, cette étiquette de décembre contient déjà un morceau de la réponse future.

La *purge* retire les observations dont la cible chevauche la période évaluée. Un *embargo* ajoute une séparation temporelle selon le protocole. Ces précautions doivent correspondre à l'horizon réellement prévu, plutôt qu'à un délai choisi sans justification.

=== Le piège du meilleur réglage après coup

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/017_viser_devant_la_cible.md")[étude 017] choisit une vitesse de rééquilibrage avant la période finale. Un autre réglage aurait mieux fonctionné sur cette période. Le remplacer après lecture du résultat transformerait le test final en nouvelle période de sélection.

Ce diagnostic reste utile pour préparer une prochaine expérience. Il ne constitue pas une nouvelle preuve indépendante sur les mêmes dates.

Une période postérieure à un article est hors de son échantillon original. Elle n'est pas forcément inconnue du chercheur qui réalise le test aujourd'hui. L'expression « hors échantillon » doit toujours préciser par rapport à quel choix ou à quel modèle.

=== Retrouver la méthode dans le dépôt

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/validation/index.md")[découpages de validation] décrivent les procédures disponibles. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/011_cross_sectional_ml.md")[étude 011] montre leur emploi pour prévoir les rendements des actions.

Avant de comparer deux résultats, vérifiez qu'ils portent sur les mêmes mois. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/04_hasard.md")[chapitre suivant] explique pourquoi leur différence demande encore une mesure d'incertitude.

#pagebreak(weak: true)
== 04 Distinguer un résultat intéressant d'un gagnant chanceux

Un test statistique peut rejeter une hypothèse vraie par hasard. Un seuil de 5 % borne cette fréquence sous les hypothèses du test. Il ne signifie pas que chaque résultat déclaré significatif a 95 % de chances d'être vrai.

Le problème grandit lorsque l'on essaie beaucoup de variantes et que l'on ne présente que la meilleure.

=== Cent tests fictifs

Supposons cent tests indépendants, tous appliqués à des relations qui n'existent pas. Chaque test rejette à tort dans 5 % des cas. La probabilité d'au moins un rejet à tort vaut alors un moins la probabilité que les cent tests ne rejettent pas.

Le calcul donne « un moins 0,95 à la puissance 100 », soit 99,4 %. L'indépendance est une hypothèse de cet exemple. Des stratégies financières proches produisent des tests dépendants, qui demandent un traitement adapté.

=== Sélectionner parmi mille stratégies sans signal

Le graphique suivant simule mille séries de 360 rendements mensuels indépendants. Chaque rendement suit une loi normale de moyenne zéro et de dispersion 4 %. Le gagnant est celui dont la moyenne est la plus élevée dans cette première période.

#figure(image("../docs/guide/figures/selection_hasard.png", width: 100%), caption: [Le gagnant de la sélection confronté à une seconde période indépendante])

Sa moyenne mensuelle vaut 0,687 % pendant la sélection. Sur 360 nouveaux mois indépendants, elle vaut -0,097 %. Ce tirage fixé à l'avance illustre la sélection d'un résultat flatteur sans avantage véritable. Il ne prédit pas la performance d'une stratégie réelle, ni la valeur maximale garantie parmi mille essais.

=== Mesurer l'incertitude d'un écart

Le *bootstrap* construit des rééchantillonnages à partir des observations disponibles. Avec des données mensuelles, prendre des blocs de mois voisins peut préserver une partie de leur dépendance. Pour comparer deux stratégies, on rééchantillonne les mêmes dates pour les deux, puis on recalcule leur différence.

#figure(image("../docs/guide/figures/bootstrap.png", width: 100%), caption: [Distribution de moyennes obtenues par blocs sur douze mois fictifs])

Ici, douze rendements fictifs sont repris par blocs circulaires de trois mois, avec 2 000 tirages. L'intervalle entre les quantiles 2,5 % et 97,5 % contient zéro. Ces données ne séparent donc pas nettement leur moyenne de zéro selon cette procédure.

Douze observations ne constituent pas une démonstration de bonne couverture statistique. La longueur des blocs et les changements de régime peuvent modifier l'intervalle. Les études doivent déclarer ces choix et examiner leur sensibilité.

=== Deux outils, deux questions

Le *Deflated Sharpe Ratio*, abrégé DSR, compare un Sharpe observé à un repère tenant compte de la sélection parmi plusieurs essais. Son calcul utilise aussi la longueur de série et la forme de la distribution. Sa valeur n'est ni un Sharpe réduit, ni la probabilité de gagner de l'argent à l'avenir.

La *probabilité de surapprentissage*, abrégée PBO, mesure une fréquence de mauvais classement dans des découpages de validation. Elle dépend de la grille de candidats et du protocole. Ces outils ne corrigent pas des prix erronés ou un univers incomplet.

Les fiches #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/bailey_lopez_de_prado_2014_dsr.md")[DSR], #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/bailey_et_al_2016_pbo.md")[PBO] et #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/harvey_liu_zhu_2016.md")[tests multiples] détaillent leurs hypothèses. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/016_publication_decay_212.md")[étude 016] montre pourquoi une différence historique et une cause établie restent deux conclusions distinctes.

#pagebreak(weak: true)
== 05 Prévoir un nombre, classer des actions, construire un portefeuille

Ces trois tâches utilisent parfois le même modèle. Elles se jugent pourtant avec des mesures différentes. Une amélioration de l'une ne garantit pas une amélioration des autres.

=== Prévoir un rendement

Le modèle annonce une variation chiffrée pour le mois suivant. On peut mesurer l'écart entre cette prévision et le rendement observé. Mettre l'écart au carré pénalise davantage les grosses erreurs.

Le R² hors échantillon du laboratoire compare cette erreur à celle d'une prévision nulle du rendement excédentaire. Une valeur de 1 % indique une réduction de 1 % de la somme des erreurs au carré. Elle ne signifie pas que le modèle devine un mois sur cent.

=== Classer les actions

Un gestionnaire peut vouloir choisir les actions les plus prometteuses. Le classement importe alors, même si le modèle se trompe sur l'ampleur générale du mouvement.

Dans l'exemple fictif du graphique, le modèle préfère C à B, puis B à A. Les rendements observés placent A devant B, puis C. Le classement est entièrement inversé alors que la prévision améliore l'erreur par rapport à zéro.

#figure(image("../docs/guide/figures/prevision_classement.png", width: 100%), caption: [Prévisions proches des niveaux observés, mais préférences inversées])

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/011_cross_sectional_ml.md")[étude 011] déroule le calcul à la main. Son R² fictif vaut 72,4 %. Les gains mesurés dans l'étude réelle sont beaucoup plus petits.

=== Passer du classement aux positions

Un portefeuille peut acheter le groupe préféré et vendre le groupe le moins préféré. Les pondérations, les titres exclus, les coûts et la fréquence des échanges influencent ensuite le résultat. Les rendements des groupes extrêmes peuvent aussi différer du comportement du classement complet.

Le ratio de Sharpe compare un rendement excédentaire moyen à sa dispersion. Il complète les mesures de prévision, sans les remplacer. Il faut aussi regarder les pertes, la rotation et les périodes difficiles.

=== Ce que l'apprentissage automatique ajoute

Gu, Kelly et Xiu comparent des relations linéaires et des méthodes capables de représenter des interactions. Une relation peut dépendre d'une autre caractéristique. Une hausse récente n'a, par exemple, pas nécessairement la même signification pour un titre liquide et un titre difficile à négocier.

Cet exemple explique une possibilité de modélisation. Il n'affirme pas que notre expérience a identifié cette relation particulière. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/gu_kelly_xiu_2020.md")[fiche de l'article] sépare la méthode originale et notre adaptation.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/013_cross_sectional_ml_long.md")[étude 013] étend la période étudiée. Elle rappelle qu'un modèle plus sophistiqué ne restitue pas les entreprises absentes des données.

#pagebreak(weak: true)
== 06 Passer du rendement théorique au rendement après frais

Un test peut supposer que les positions s'échangent au prix affiché. Un ordre réel doit trouver une contrepartie. Les commissions, l'écart acheteur-vendeur et l'effet de l'ordre sur le prix peuvent réduire le rendement.

La *rotation* mesure la quantité de positions échangées relativement au capital. Il faut lire sa convention, car certaines mesures divisent la somme des achats et des ventes par deux.

=== Un exemple fictif de rotation

Un portefeuille de 1 000 dollars vend 200 dollars d'une action et achète 200 dollars d'une autre. Il échange 400 dollars. Avec un coût de dix points de base sur chaque montant négocié, il paie 0,40 dollar.

Dix points de base valent 0,10 %. Le coût représente donc 0,04 % du portefeuille dans cet exemple. Si une table appelle « rotation » les seuls 200 dollars remplacés, son coefficient de coût doit tenir compte des deux passages.

=== Un coût petit peut devenir important

Un aller-retour coûtant quatre points de base représente 0,04 % du montant échangé. Répété 250 fois sur un montant constant égal au capital initial, il coûte 10 % de ce capital. Cet exemple additionne les coûts sur un montant fixe et ignore la composition des rendements.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/018_nuit_contre_journee.md")[étude 018] explique pourquoi on ne peut pas appliquer ce calcul sans vérifier les positions réellement négociées. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/007_statistical_arbitrage.md")[étude 007] mesure le seuil de coût qui annule son propre rendement brut.

=== Le coût dépend aussi de la taille

Acheter pour 1 000 dollars et acheter pour 100 millions ne mobilise pas la même quantité de liquidité. L'*impact de marché* représente la variation de prix liée à l'exécution de l'ordre. Un coefficient supposé produit une estimation modélisée, pas un coût observé.

La *capacité* est le capital compatible avec les contraintes retenues. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/010_capacity.md")[étude 010] examine cette question sur deux stratégies dont les positions et les volumes sont disponibles. Un facteur publié sans détail des titres ne permet pas le même calcul.

=== Les frais que le mot net ne suffit pas à préciser

Une position vendue à découvert peut demander un emprunt de titres. Le levier peut nécessiter un financement. Les impôts et les frais de gestion constituent encore d'autres postes.

Chaque résultat net doit donc nommer les coûts inclus. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/analytics/index.md")[moteur analytique] décrit les conventions, et les annexes donnent les coefficients propres aux études.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/017_viser_devant_la_cible.md")[étude 017] pose ensuite une question pratique. Peut-on réduire les échanges sans perdre trop vite l'information du signal ?

#pagebreak(weak: true)
== 07 Comprendre ce que la diversification apporte

Deux stratégies peuvent perdre à des moments différents. Leur mélange peut alors réduire les fluctuations du portefeuille. La diversification dépend de ces mouvements communs, autant que du rendement moyen de chaque stratégie.

La *corrélation* résume une association linéaire. Une corrélation faible ne garantit pas une indépendance complète. Deux stratégies peuvent notamment partager des pertes lors d'événements rares.

=== Deux périodes fictives

La stratégie A gagne 10 %, puis perd 10 %. La stratégie B perd 2 %, puis gagne 8 %. Un portefeuille remis à parts égales avant chaque période gagne 4 %, puis perd 1 %.

Sur 100 dollars initiaux, A termine à 99 dollars et B à 105,84 dollars. Le mélange termine à 102,96 dollars. Il fluctue moins dans cet exemple, sans battre le capital final de B.

L'exemple montre aussi la composition des rendements. Gagner 10 %, puis perdre 10 %, ne ramène pas au point de départ. La perte de la seconde période s'applique aux 110 dollars obtenus après la première.

=== Ce que les données du laboratoire montrent

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/003_value_and_momentum.md")[étude 003] observe une corrélation négative entre valeur et momentum. Leur association historique améliore le rapport entre rendement moyen et dispersion. Les dates utilisées pour calculer les signaux influencent toutefois cette relation.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/009_multi_strategy.md")[étude 009] compare plusieurs règles d'allocation sur des séries brutes. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/012_multi_strategy_net.md")[étude 012] reprend l'exercice après les coûts propres aux stratégies. Les conclusions financières changent parce que les séries à combiner ont changé.

=== Trois choix qui ne disent pas la même chose

Une allocation à parts égales répartit le capital également. Une allocation inversement proportionnelle à la volatilité réduit le poids des stratégies qui fluctuent davantage. Une allocation fondée sur les contributions au risque tient aussi compte de leurs mouvements communs.

Ces règles exigent des estimations différentes. Une estimation de risque instable peut produire des poids instables et davantage de frais. Le repère simple aide à mesurer si cette complexité apporte assez.

=== Choisir la comparaison avant le résultat

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/021_portefeuille_de_primes.md")[étude 021] demande au mélange de dépasser sa meilleure composante selon un critère fixé. Le portefeuille ne satisfait pas ce critère sur la période complète. Son intérêt éventuel pour un investisseur ayant d'autres contraintes reste une question distincte.

Les références #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/markowitz_1952.md")[Markowitz], #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/demiguel_garlappi_uppal_2009.md")[DeMiguel et coauteurs] et #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/ledoit_wolf_2004.md")[Ledoit et Wolf] expliquent les choix de risque et d'estimation. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/08_conclusion.md")[dernier chapitre] aide à formuler ce que les preuves autorisent.

#pagebreak(weak: true)
== 08 Écrire une conclusion à la hauteur des preuves

Un résultat utile peut être négatif, incertain ou limité par les données. Sa valeur vient de ce que l'on a appris et de la possibilité de vérifier le raisonnement. Le lecteur doit pouvoir séparer le nombre observé de l'explication proposée.

=== Quatre statuts pour les chiffres

Un résultat *mesuré* vient d'un calcul sur les données indiquées. Un résultat *rapporté* provient d'une source citée. Un résultat *modélisé* dépend d'hypothèses telles qu'un coût de transaction supposé. Un résultat *non calculable* manque des données nécessaires.

Une hypothèse de coût peut être modélisée et le rendement correspondant calculé exactement. L'exactitude du calcul ne transforme pas l'hypothèse en coût réellement payé.

=== Un résultat non significatif reste informatif

Supposons, dans un exemple fictif, un gain estimé de deux points de pourcentage par an. Une procédure d'incertitude donne un intervalle allant de moins trois à plus sept points. L'estimation centrale est positive, mais zéro appartient à l'intervalle.

Ce résultat ne démontre ni une amélioration, ni une égalité parfaite. Il peut motiver davantage de données ou une expérience plus précise. Il ne justifie pas de présenter les deux méthodes comme interchangeables.

=== Lire les verdicts du logiciel

#table(
  columns: 2,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Verdict*],
    [*Lecture utile*],
    [REJECTED],
    [Les critères retenus pour cette étude ne sont pas satisfaits],
    [EXPERIMENTAL],
    [Une partie des preuves existe, avec des limites qui empêchent un statut supérieur],
    [REPLICATED],
    [Les contrôles de comparaison configurés passent, dans le périmètre déclaré],
    [ROBUST],
    [Les critères supplémentaires du laboratoire passent, sous leurs hypothèses],
)

Ces mots sont des catégories du moteur de décision. Ils ne remplacent pas la lecture des contrôles. Un critère absent doit être distingué d'un critère calculé qui échoue.

Dans l'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/021_portefeuille_de_primes.md")[étude 021], le contrôle nommé « réplication » compare en réalité le portefeuille à une composante. Son libellé ne prouve pas la reproduction d'un article. La présentation explique donc le contenu du contrôle avant son statut.

=== Refaire le raisonnement

Pour chaque conclusion, retrouvez la question, la période, l'univers, le repère et les coûts. Examinez ensuite l'incertitude et les explications concurrentes. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/documentation/publication_values.json")[registre des valeurs] relie les chiffres du cours aux fichiers de résultats.

Les textes des chapitres et des études ont une source éditoriale commune dans le dossier documentation. La construction publie le site, les README et le manuscrit du PDF. Le contrôle de fraîcheur échoue lorsqu'une source numérique change sans régénération des textes.

Les annexes conservent les détails de l'expérience historique. Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/research_journal/pedagogie-2026-09-13.md")[notes de relecture] expliquent les corrections d'interprétation. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/index.md")[catalogue des études] permet de poursuivre selon la question qui vous intéresse.

#pagebreak(weak: true)
== 001 Suivre une tendance après sa publication

Le suivi de tendance consiste à acheter un actif après une hausse passée, ou à prendre une position vendeuse après une baisse. L'étude demande si cette règle reste rémunérée après sa diffusion dans la littérature.

Le facteur des auteurs passe d'un Sharpe de 1,411 sur 1985-2009 à 0,337 après juin 2012, jusqu'en juin 2026. Il s'agit de la série publiée, avant les coûts d'une reconstruction négociable. Le ratio de Sharpe compare le rendement excédentaire moyen à sa dispersion.

=== Une intuition et un exemple fictif

Un actif a gagné 12 % pendant la période d'observation. La règle de tendance prend une position acheteuse pour la période suivante. Si l'actif perd alors 3 %, la position perd également 3 % avant levier et frais.

La règle ne sait pas que la tendance continuera. Elle parie sur une persistance moyenne, qui peut coexister avec des renversements coûteux.

=== Le lien avec l'article

Moskowitz, Ooi et Pedersen étudient des contrats à terme sur plusieurs classes d'actifs. Notre reconstruction utilise vingt-huit fonds négociés en bourse. Les expositions, les horaires, les frais et les possibilités de vente ne sont donc pas identiques.

La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/moskowitz_ooi_pedersen_2012.md")[fiche de littérature] présente aussi les explications concurrentes. Une partie du résultat peut venir du ciblage de volatilité ou d'une exposition acheteuse moyenne. Retrouver un rendement positif ne permet pas, seul, de les départager.

=== Ce qu'il faut retenir

L'affaiblissement du facteur publié est un constat historique. Il ne démontre pas que la publication est son unique cause. La reconstruction conserve des mouvements communs avec ce facteur, tout en obtenant un résultat différent après coûts.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/017_viser_devant_la_cible.md")[étude 017] demande ensuite si échanger moins souvent améliore ce résultat. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/lean/README.md")[comparaison avec LEAN] examine l'exécution dans un second moteur.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/001_time_series_momentum/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/001_time_series_momentum/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/001_time_series_momentum/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 002 Acheter les actions qui ont le plus monté

Le momentum transversal compare les actions entre elles. Il achète les gagnantes passées et vend les perdantes passées. Il diffère du suivi de tendance, qui examine chaque actif par rapport à son propre passé.

=== Un exemple fictif

A a gagné 15 %, B a gagné 5 % et C a perdu 10 %. Une règle simplifiée achète A et vend C. Si A gagne ensuite 2 % et C gagne 6 %, l'écart de rendement vaut moins quatre points de pourcentage.

Le marché peut donc monter pendant que la stratégie perd. Son résultat dépend de la différence entre les groupes, pas uniquement de la direction générale des actions.

=== La question posée à la littérature

Jegadeesh et Titman documentent cette stratégie en 1993. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/jegadeesh_titman_1993.md")[fiche de l'article] précise les périodes de formation, de détention et le délai entre les deux. Un décalage d'une semaine et un décalage d'un mois ne définissent pas le même test.

L'étude utilise notamment les portefeuilles triés de Kenneth French pour prolonger la comparaison. Elle distingue cette série de la reconstruction sur les entreprises encore présentes aujourd'hui.

=== Le résultat utile

L'écart gagnant moins perdant passe de 1,630 % par mois sur la fenêtre originale à 0,768 % sur 1994-2026, avant frais. La moyenne reste positive, mais son incertitude augmente relativement au gain mesuré. L'absence de significativité au seuil retenu ne signifie pas que le rendement véritable est exactement nul.

Dans la reconstruction sur survivants, le biais ne relève pas automatiquement la performance. La sélection modifie aussi le groupe vendu. Cet exemple réel justifie la prudence du #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/02_donnees.md")[chapitre sur les données].

=== La limite de la conclusion

Comparer deux périodes montre une évolution du résultat. Cela ne suffit pas à isoler la concurrence créée par la publication. Les changements de risque, de composition et de coûts restent des explications à examiner.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/002_cross_sectional_momentum/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/002_cross_sectional_momentum/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/002_cross_sectional_momentum/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 003 Pourquoi associer valeur et momentum ?

La valeur cherche des actifs peu chers relativement à une mesure économique. Le momentum cherche des actifs dont le prix a monté. Ces deux règles peuvent prendre des positions différentes au même moment.

=== Un exemple fictif

Le bénéfice d'une entreprise reste inchangé pendant que son prix passe de 100 à 120 dollars. Elle devient plus chère relativement à ce bénéfice. La hausse peut attirer une règle de momentum et éloigner une règle de valeur.

Cet exemple explique pourquoi les signaux peuvent s'opposer. Il ne prouve pas que leur opposition suffit à produire un rendement.

=== Le lien avec l'article

Asness, Moskowitz et Pedersen étudient la valeur et le momentum dans plusieurs classes d'actifs. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/asness_moskowitz_pedersen_2013.md")[fiche de littérature] précise les définitions et les comparaisons. Le laboratoire utilise leurs facteurs AQR, puis une construction alternative fondée sur Kenneth French.

L'exercice distingue le rendement de chaque composante et le gain associé à leurs mouvements communs.

=== Le résultat sur les facteurs publiés

#table(
  columns: 2,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Mesure*],
    [*Janvier 1972 à juin 2026*],
    [Corrélation valeur et momentum],
    [-0,577],
    [Sharpe du momentum seul],
    [0,593],
    [Sharpe du mélange à parts égales],
    [1,096],
)

Ces chiffres portent sur 654 mois et sont bruts de frais. Le mélange présente un meilleur rapport entre rendement moyen et dispersion dans cet échantillon. Cela ne constitue pas une promesse de domination future.

Une identité de variance vérifie le rôle arithmétique de la corrélation. Elle n'identifie pas, à elle seule, la cause économique de cette corrélation.

=== Pourquoi la date du signal compte

Un prix actuel et un prix retardé dans le ratio de valeur ne produisent pas les mêmes positions. La construction alternative montre une corrélation différente. Les conventions de mesure font donc partie du résultat, plutôt que d'un simple détail technique.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/012_multi_strategy_net.md")[étude 012] poursuit la question après les coûts.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/003_value_and_momentum/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/003_value_and_momentum/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/003_value_and_momentum/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 004 Peut-on reconstruire un placement fondé sur la qualité ?

Une entreprise rentable, stable et capable de financer son activité peut sembler de meilleure qualité. Cela ne suffit pas à en faire un bon placement. Le prix payé pour cette qualité compte aussi.

L'étude distingue deux questions. Retrouvons-nous les propriétés du facteur publié par AQR ? Pouvons-nous reconstruire un facteur comparable depuis les rapports publics des entreprises ?

=== Un exemple fictif

Deux entreprises produisent chacune dix dollars de bénéfice annuel. La première coûte 100 dollars et la seconde 250 dollars. Même si la seconde est plus stable, son bénéfice représente une part plus faible du prix payé.

L'exemple ne fournit pas une méthode de valorisation complète. Il explique seulement pourquoi qualité de l'entreprise et rendement attendu du placement ne se confondent pas.

=== Ce qui est repris de la littérature

La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/asness_frazzini_pedersen_2019_qmj.md")[fiche Quality Minus Junk] présente les composantes du score et les versions de l'article. Le laboratoire s'appuie sur la version de travail obtenue. La version publiée n'a pas été lue intégralement, et une différence sur le nombre de composantes reste déclarée.

Les données comptables de la SEC sont datées selon leur disponibilité. Cette précaution n'élargit pas automatiquement le panel aux entreprises disparues.

=== Le résultat de la reconstruction

La corrélation avec le facteur publié vaut 0,098 sur 132 mois communs, de juin 2015 à mai 2026. Elle reste sous le seuil de comparaison fixé à 0,50. Le Sharpe de notre construction vaut 0,152, avant les coûts d'une mise en œuvre complète.

Retrouver les statistiques d'une série fournie par ses auteurs est plus limité que reconstruire ses positions. L'étude réussit certaines comparaisons sur la série publiée, mais sa construction indépendante ne reproduit pas suffisamment ses mouvements.

=== Ce que l'écart apprend

L'univers, les variables disponibles et la version du score diffèrent. Ces écarts proposent des pistes explicatives, sans isoler une cause unique. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/data/index.md")[registre des données] aide à retrouver leurs limites.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/004_quality_minus_junk/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/004_quality_minus_junk/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/004_quality_minus_junk/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 005 Le choix d'un bêta peut changer tout un portefeuille

Le *bêta* mesure la sensibilité d'un placement aux mouvements du marché dans un modèle linéaire. Une stratégie dite « contre le bêta » achète des titres de faible sensibilité et vend des titres de forte sensibilité. Elle ajuste leurs tailles pour comparer les deux groupes à risque de marché estimé comparable.

=== Un exemple fictif

Une position dont le bêta est estimé à 0,5 reçoit un multiplicateur de deux pour viser une exposition de marché égale à un. Si l'estimation retenue devient 0,8, le multiplicateur descend à 1,25. Le choix de l'estimateur modifie donc directement le montant investi.

La *réduction vers une valeur de référence* rapproche une estimation incertaine d'un repère. Elle peut stabiliser les estimations, mais elle change aussi les poids.

=== Le lien avec Frazzini et Pedersen

Leur article relie cette stratégie aux contraintes qui limitent l'emprunt de certains investisseurs. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/frazzini_pedersen_2014_bab.md")[fiche de littérature] distingue cette explication des critiques portant sur la construction du facteur. Les cibles proviennent d'une version de travail, pas d'une lecture intégrale de la version publiée.

Le laboratoire compare la série AQR à des reconstructions sur déciles et sur titres.

=== Une sensibilité mesurée

Sur les titres, de janvier 2001 à juin 2026, le Sharpe passe de 0,394 sans réduction du bêta à -0,001 avec la réduction de référence. Ces comparaisons de construction précèdent la grille complète des coûts.

Le facteur publié et le facteur reconstruit ne donnent donc pas la même conclusion. Ce résultat montre une dépendance importante au réglage de l'estimateur. Il ne démontre pas que toute réduction statistique est mauvaise.

=== Comment lire le verdict

Le rejet porte sur les critères du portefeuille construit dans l'étude. Il ne réfute pas toute la théorie des contraintes d'emprunt. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/ledoit_wolf_2004.md")[discussion sur l'estimation du risque] explique pourquoi stabiliser une estimation exige une comparaison adaptée.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/005_betting_against_beta/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/005_betting_against_beta/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/005_betting_against_beta/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 006 Réduire l'exposition quand le marché devient agité

La volatilité mesure l'ampleur des fluctuations. Une gestion en volatilité réduit la position lorsque les variations récentes deviennent plus grandes. L'étude demande si cette règle améliore une performance réellement accessible avec l'information passée.

=== Un exemple fictif

Une règle simplifiée investit un montant inversement proportionnel à la variance récente. Si cette variance double, le montant investi est divisé par deux. Cela réduit l'exposition, mais peut aussi faire manquer une reprise rapide après une crise.

Le choix de la constante qui règle l'échelle du portefeuille compte. La calculer sur toutes les dates utilise des observations qui n'existaient pas encore au début du test.

=== Le lien avec Moreira et Muir

La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/moreira_muir_2017.md")[fiche de littérature] détaille la version de travail consultée. Le laboratoire retrouve un alpha de 4,743 % par an pour le marché sur août 1926 à avril 2015, avant frais. Cet *alpha* est la constante d'une régression après prise en compte de l'exposition au facteur de référence.

Un alpha estimé sur toute une période n'est pas automatiquement le rendement d'un portefeuille dont tous les poids étaient connus à chaque date.

=== Une comparaison qui change la lecture

Avec une mise à l'échelle estimée sur le passé, l'alpha mesuré sur août 1936 à juin 2026 vaut 2,438 % par an, avant frais. Il s'agit d'une analyse de validation sur une fenêtre différente, pas d'une comparaison toutes choses égales.

L'étude construit également une position couverte, avec un bêta de couverture estimé dans le temps. Son résultat net sur la période finale ne satisfait pas les critères. Les tableaux détaillés séparent bien cette position et la régression descriptive.

=== La leçon méthodologique

Une identité calculable après la dernière observation peut expliquer un résultat historique. Elle ne fournit pas forcément une décision réalisable avant cette observation. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/03_calendrier.md")[chapitre du calendrier] donne le vocabulaire pour distinguer ces deux usages.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/006_volatility_managed/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/006_volatility_managed/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/006_volatility_managed/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 007 Un retour à la moyenne paie-t-il les échanges nécessaires ?

L'arbitrage statistique cherche des écarts temporaires entre une action et les mouvements communs de son univers. Il achète un écart jugé trop bas et vend un écart jugé trop haut. Le mot arbitrage ne signifie pas ici un gain certain sans risque.

=== Un exemple fictif

Une action baisse de 3 % alors que son groupe comparable baisse de 1 %. Son écart relatif vaut moins deux points de pourcentage. Une règle de retour à la moyenne peut acheter cet écart en couvrant une partie du mouvement commun.

L'écart peut toutefois refléter une mauvaise nouvelle durable. La convergence attendue reste une hypothèse, et les échanges ont un coût même lorsqu'elle ne se réalise pas.

=== La méthode de référence

Avellaneda et Lee extraient des mouvements communs, puis modélisent les écarts résiduels. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/avellaneda_lee_2010.md")[fiche de l'article] explique les composantes principales et la règle de retour à la moyenne. Le laboratoire précise notamment si la couverture exige de négocier les titres sous-jacents.

Cette convention change la rotation et doit accompagner la comparaison.

=== Le chiffre qui aide à décider

Le seuil de coût qui annule le rendement brut vaut 3,916 points de base par unité négociée sur l'historique de la reconstruction. La période de comparaison avec l'article, de 1997 à 2007, donne un Sharpe brut de 1,461. Ces deux mesures portent sur des fenêtres différentes.

Un beau Sharpe brut ne suffit donc pas à payer les positions. Les variantes de couverture déplacent le seuil de coût, sans dépasser les cinq points de base retenus dans l'article.

=== Ce qui limite la portée du résultat

Les titres sont sélectionnés parmi ceux encore disponibles. Cette sélection empêche de présenter la reconstruction comme un univers historique complet. Le résultat net après publication reste défavorable dans les conventions étudiées.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/010_capacity.md")[étude 010] ajoute ensuite les contraintes de taille.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/007_statistical_arbitrage/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/007_statistical_arbitrage/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/007_statistical_arbitrage/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 008 Un taux plus élevé paie-t-il le risque de change ?

Le *portage* est le revenu associé au maintien d'une position si certaines conditions de prix restent inchangées. Sur les devises, un écart de taux peut inciter à emprunter dans la monnaie au taux faible pour placer dans celle au taux élevé. La variation du change peut effacer cet écart.

=== Un exemple fictif

Le placement rapporte 5 % dans une monnaie et son financement coûte 2 % dans l'autre. Sans variation du change, l'écart est voisin de trois points de pourcentage avant frais. Si la monnaie du placement perd 8 %, le placement converti rapporte environ moins 3,4 %, avant le coût du financement.

Le taux affiché n'est donc pas le rendement garanti dans la monnaie de l'investisseur. Il faut convertir le capital final et tenir compte du financement.

=== Ce que l'article examine

Koijen et ses coauteurs étudient le portage dans plusieurs classes d'actifs. Notre expérience porte sur les devises accessibles. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/koijen_moskowitz_pedersen_vrugt_2018.md")[fiche de littérature] explique pourquoi les autres classes ne sont pas reconstruites ici.

=== Le résultat et sa sensibilité

Sur novembre 1983 à septembre 2012, la régression donne un coefficient de 1,084 et une statistique t de 2,159. Le coefficient mesure une association entre le portage et le rendement futur, dans les unités et la spécification du modèle. La statistique t compare l'estimation à son erreur type.

La comparaison est proche du chiffre publié dans la convention principale. Retirer le dollar du classement modifie toutefois le coefficient et l'asymétrie des rendements. Le statut de comparaison réussie doit donc rester attaché à cette convention précise.

=== Ce qui reste après la fenêtre originale

Le pouvoir prédictif estimé devient plus faible et plus incertain sur octobre 2012 à juin 2026. Cela ne permet pas d'affirmer que tous les portages sont devenus nuls. L'étude souligne surtout la dépendance au numéraire, c'est-à-dire à la monnaie servant de référence.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/008_carry/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/008_carry/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/008_carry/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 009 Huit stratégies différentes font-elles un meilleur portefeuille ?

Le portefeuille rassemble les huit premières stratégies. Il compare plusieurs allocations, dont une référence choisie avant de lire les performances. La question porte sur l'amélioration du mélange relativement aux composantes, avec leurs données et leurs limites.

=== Un exemple fictif

Deux stratégies gagnent en moyenne autant. Si elles perdent exactement les mêmes mois, les combiner protège peu. Si leurs fluctuations se compensent en partie, le risque du mélange peut diminuer.

Cette intuition ne garantit pas qu'une allocation estimée battra une règle simple. Les corrélations et les volatilités doivent être estimées, puis converties en positions.

=== Le contexte de recherche

La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/grinold_1989.md")[loi fondamentale] relie la qualité des prévisions à la diversité effective des paris, sous des hypothèses. #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/demiguel_garlappi_uppal_2009.md")[DeMiguel et coauteurs] motivent la comparaison avec une allocation à parts égales. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/003_value_and_momentum.md")[étude 003] fournit un exemple de diversification observée.

=== Lire les fenêtres séparément

La référence en parité de risque présente un Sharpe de 1,031 avant la période finale et de 0,214 sur les 78 mois de janvier 2020 à juin 2026. Le portefeuille s'appuie sur des séries de stratégies brutes. Les coûts de réallocation ne remplacent pas les frais nécessaires à construire chaque composante.

Une autre allocation paraît meilleure dans certaines comparaisons. La désigner comme nouvelle référence après avoir vu son résultat constituerait un nouveau choix guidé par les données.

=== Ce que le rejet signifie

La référence ne satisfait pas le critère de supériorité fixé dans cette étude. La conclusion ne dit pas que diversifier est inutile. Elle dit que ce mélange et cette règle n'ont pas apporté la preuve demandée.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/012_multi_strategy_net.md")[étude 012] reprend la comparaison avec les coûts propres aux composantes. Elle permet de voir ce que la lecture des seules séries brutes masquait.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/009_multi_strategy/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/009_multi_strategy/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/009_multi_strategy/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 010 Combien de capital une stratégie peut-elle accueillir ?

Une stratégie peut être facile à exécuter avec une petite somme et devenir difficile avec un gros ordre. L'étude estime la taille compatible avec des hypothèses de coût et de participation au volume. Les résultats sont modélisés, faute d'observations d'exécution permettant de calibrer tous les paramètres.

=== Un exemple fictif

Un fonds échange pour un million de dollars dans une journée. Un ordre de 100 000 dollars représente 10 % de ce volume. Un ordre de 500 000 dollars en représente 50 %.

Fixer un plafond de participation à 10 % limite donc le premier ordre à 100 000 dollars dans cet exemple. Cela ne garantit pas qu'il pourra s'exécuter sans déplacer le prix.

=== Ce que l'étude peut calculer

Le suivi de tendance sur fonds cotés et l'arbitrage statistique disposent de positions et de volumes. Les six autres composantes sont principalement des séries de facteurs publiés. Leur capacité ne peut pas être calculée de la même façon sans les positions détaillées.

Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/almgren_chriss_2001.md")[contexte d'exécution] explique pourquoi taille, calendrier et impact sont liés. Cette étude n'est pas une réplication complète de ce modèle.

=== Le résultat principal

Pour le suivi de tendance, sur janvier 2007 à juin 2026, la contrainte de participation retient environ 84 940 dollars de capital. La valeur est beaucoup plus faible que certaines tailles de la grille illustrative. Elle correspond à la contrainte imposée aux rééquilibrages et aux volumes du jeu de données.

Ce nombre n'est pas une capacité commerciale mesurée. Changer le nombre de jours d'exécution, le plafond ou l'univers modifierait l'estimation.

=== Une limite peut intervenir avant une autre

L'arbitrage statistique ne couvre déjà pas les frais de base dans la convention retenue. Ajouter l'impact ne peut pas rétablir sa rentabilité. Pour le suivi de tendance, la participation limite la taille avant certains seuils d'annulation par l'impact.

La comparaison enseigne donc quel obstacle devient contraignant dans le modèle, avec ses hypothèses.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/010_capacity/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/010_capacity/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/010_capacity/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 011 Prévoir plus juste aide-t-il à choisir les bonnes actions ?

Les modèles étudiés améliorent une mesure de prévision, mais ils ne classent pas clairement les actions dans le bon ordre. Le portefeuille des arbres obtient un meilleur résultat observé que celui de la régression. L'expérience ne démontre toutefois pas que les arbres prévoient mieux sur les données disponibles.

Cette distinction organise l'étude. Une prévision sert à annoncer un rendement. Un classement sert à choisir entre plusieurs actions. Un portefeuille transforme ensuite ce choix en positions, avec des risques et des frais.

=== Trois actions suffisent pour comprendre le problème

L'exemple suivant est fictif. Les rendements sont exprimés au-delà d'un placement sans risque, pour un seul mois. Le modèle annonce une hausse pour chaque action.

#table(
  columns: 3,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Action*],
    [*Rendement prévu*],
    [*Rendement observé*],
    [A],
    [+2 %],
    [+4 %],
    [B],
    [+3 %],
    [+3 %],
    [C],
    [+4 %],
    [+2 %],
)

Le modèle se trompe de deux points de pourcentage sur A et C. Il prévoit exactement le rendement de B. La somme des erreurs au carré vaut donc #raw("2 × 2 + 0 + 2 × 2 = 8"). Prévoir zéro pour toutes les actions aurait donné #raw("4 × 4 + 3 × 3 + 2 × 2 = 29").

Le *R² hors échantillon* mesure ici la réduction de cette erreur par rapport à la prévision nulle. Il vaut #raw("1 - 8 / 29"), soit 72,4 %. Ce pourcentage ne compte pas les prévisions correctes. Il compare deux sommes d'erreurs au carré.

Le classement est pourtant entièrement inversé. Le modèle préfère C, qui monte de 2 %, à A, qui monte de 4 %. Acheter l'action préférée donne donc le moins bon des trois rendements. L'exemple prouve que précision et classement peuvent diverger. Il ne reproduit pas la taille des effets observés dans l'étude.

#figure(image("../docs/guide/figures/prevision_classement.png", width: 100%), caption: [Les trois actions prévues et observées])

Chaque paire de barres représente une action. Le bleu montre la prévision et l'orange le rendement observé, en pourcentage mensuel. De A à C, la barre bleue s'allonge pendant que la barre orange raccourcit. Le modèle annonce la hausse générale, mais inverse les préférences.

=== Pourquoi la littérature compare plusieurs méthodes

Gu, Kelly et Xiu étudient comment les caractéristiques des entreprises renseignent sur leurs rendements futurs. Une caractéristique peut être utile en combinaison avec une autre. Par exemple, une hausse récente pourrait avoir une portée différente selon la liquidité du titre, c'est-à-dire la facilité de le négocier. Cet exemple explique ce qu'est une interaction. Il ne prétend pas identifier le mécanisme causal des résultats du laboratoire.

Une régression linéaire additionne les effets selon une forme fixée. Un arbre découpe les observations en groupes et peut employer des règles différentes selon le groupe. Cette souplesse peut aider à représenter une relation. Elle peut aussi apprendre des particularités accidentelles du passé. #link("https://doi.org/10.1093/rfs/hhaa009")[L'article de 2020] compare ces méthodes sur un panel d'actions américaines.

=== Ce que nous reproduisons et ce que nous adaptons

#table(
  columns: 3,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Élément*],
    [*Article de référence*],
    [*Expérience du laboratoire*],
    [Univers],
    [Large historique américain fondé sur CRSP],
    [Grandes entreprises disponibles dans le panel construit pour l'étude 004],
    [Informations],
    [Caractéristiques des titres et variables macroéconomiques],
    [27 caractéristiques, sans les interactions macroéconomiques du papier],
    [Modèles],
    [Méthodes linéaires, arbres et réseaux],
    [Six méthodes, dont des arbres et des régressions, sans réseau dans la grille],
    [Comparaison financière],
    [Portefeuilles présentés dans le papier],
    [Décile acheté et décile vendu, avec frais proportionnels modélisés],
)

Ces différences empêchent de traiter un écart de performance comme une réfutation générale de l'article. La question locale est plus étroite. Les arbres apportent-ils une amélioration détectable dans notre panel et avec notre protocole ? La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/gu_kelly_xiu_2020.md")[fiche de littérature] détaille les spécifications et les versions consultées.

=== Comment le test avance dans le temps

Les informations comptables portent une date de disponibilité. Les prévisions visent le mois suivant. Le modèle apprend sur les premières années, puis ses paramètres sont choisis sur une période de validation antérieure au test. Une séparation d'un mois empêche les étiquettes voisines de franchir la frontière retenue.

L'opération recommence en avançant dans le calendrier. Les résultats présentés couvrent 72 mois, de juillet 2020 à juin 2026. Un *décile* contient un dixième des titres classés. Le portefeuille achète le décile préféré et vend le moins préféré. Les coûts supposés valent dix points de base par unité négociée. Dix points de base correspondent à 0,10 % du montant concerné.

=== Les trois mesures racontent des choses différentes

#table(
  columns: 4,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Modèle*],
    [*Réduction de l'erreur par rapport à zéro*],
    [*Corrélation moyenne du classement*],
    [*Sharpe du portefeuille net*],
    [Régression pénalisée],
    [0,41 %],
    [-0,022],
    [0,277],
    [Arbres amplifiés],
    [0,35 %],
    [-0,016],
    [0,663],
    [Forêt aléatoire],
    [0,48 %],
    [-0,019],
    [0,572],
)

La corrélation de classement compare l'ordre prévu à l'ordre observé chaque mois. Une valeur négative indique une association moyenne de sens opposé. Le *ratio de Sharpe* rapporte le rendement excédentaire moyen à sa dispersion. Il ne mesure pas directement la perte maximale.

La forêt réduit davantage l'erreur, tandis que les arbres amplifiés ont le meilleur Sharpe parmi les trois lignes. Les trois corrélations de classement sont négatives. Cela peut coexister avec un portefeuille profitable, car les déciles extrêmes ne résument pas tout le classement. Les écarts observés doivent encore être comparés à leur incertitude.

Les nombres proviennent des #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/011_cross_sectional_ml/results/tables/evaluation.csv")[erreurs et classements] et des #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/011_cross_sectional_ml/results/tables/portfolios.csv")[portefeuilles]. Les rendements de portefeuille sont nets des coûts de transaction retenus, mais pas de frais de gestion ou d'impôts.

=== Ce que le verdict permet de dire

Le test de comparaison des erreurs ne fournit pas de preuve suffisante en faveur des arbres amplifiés face à la régression de référence. Une absence de différence détectée n'établit pas l'égalité des méthodes. L'échantillon peut manquer de puissance, c'est-à-dire de capacité à détecter un petit effet.

Le panel contient aussi un biais de sélection des entreprises. Dater correctement leurs rapports ne restitue pas les titres absents du panel. L'expérience ne permet donc pas de conclure que les modèles complexes sont inutiles en général. Son verdict #raw("REJECTED") signifie que les critères de cette étude ne sont pas satisfaits.

=== Refaire l'exemple et lire la preuve complète

#raw("uv run python scripts/build_learning.py --check") vérifie les textes et les exemples hors réseau. Le test retrouve un R² de #raw("21 / 29") et un classement inversé. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/011_cross_sectional_ml/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les six modèles et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/013_cross_sectional_ml_long.md")[étude 013] prolonge l'historique sans résoudre la sélection des entreprises.

#pagebreak(weak: true)
== 012 Que reste-t-il du mélange après les frais de chaque stratégie ?

L'étude 009 combinait principalement des rendements bruts. Cette étude remplace les composantes par leurs séries après les coûts retenus dans chaque expérience. Elle pose une question simple, la diversification reste-t-elle avantageuse lorsque les positions doivent être négociées ?

=== Un exemple fictif

Une stratégie gagne 8 % avant frais et coûte 1 % du capital. Une autre gagne également 8 %, mais coûte 10 %. Leurs rendements nets simplifiés deviennent 7 % et moins 2 %.

Le mélange à parts égales donne alors 2,5 % dans cette unique période, avant d'autres frais. Combiner la seconde stratégie réduit ici la moyenne. Une éventuelle réduction du risque doit être évaluée séparément.

=== Le lien avec les travaux sur les portefeuilles

La comparaison reprend les références de l'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/009_multi_strategy.md")[étude 009]. Les coûts modifient les rendements à allouer. Ils peuvent aussi modifier leur dispersion et leurs corrélations lorsqu'ils varient dans le temps.

Il serait donc incorrect de supposer que le passage au net laisse toutes les corrélations inchangées.

=== Le résultat sur la période finale

Le Sharpe de la référence en parité de risque vaut -0,396 sur janvier 2020 à juin 2026. Le signe négatif indique un rendement excédentaire moyen négatif relativement à sa dispersion. Il ne signifie pas que toutes les allocations possibles sont mauvaises.

Sur la fenêtre d'allocation plus large, la référence ne dépasse pas non plus la meilleure composante selon le critère déclaré. L'arbitrage statistique, qui contribuait fortement au mélange brut, apporte une série nette beaucoup moins favorable.

=== Ce que la comparaison autorise

Le rejet concerne ces huit composantes, ces hypothèses de coût et cette règle de sélection. Les coûts sont des hypothèses publiées, pas un relevé de transactions réelles. Les données des composantes conservent également des qualités différentes.

Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/07_portefeuille.md")[chapitre sur la diversification] explique pourquoi réduire le risque et améliorer le rendement moyen sont deux objectifs distincts.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/012_multi_strategy_net/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/012_multi_strategy_net/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/012_multi_strategy_net/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 013 Un historique plus long peut-il rendre une erreur plus convaincante ?

Les modèles de cette étude obtiennent des performances positives sur un historique long. L'univers contient toutefois les entreprises encore présentes aujourd'hui, rejouées dans le passé. Les tests temporels ne corrigent pas cette sélection des entreprises.

=== Cinq entreprises, puis trois survivantes

L'exemple est fictif. Nous plaçons 100 dollars dans chacune de cinq entreprises au début d'une période. Le capital initial vaut donc 500 dollars.

#table(
  columns: 4,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Entreprise*],
    [*Capital initial*],
    [*Capital final*],
    [*Présente dans la sélection finale*],
    [A],
    [100 \$],
    [120 \$],
    [Oui],
    [B],
    [100 \$],
    [110 \$],
    [Oui],
    [C],
    [100 \$],
    [90 \$],
    [Oui],
    [D],
    [100 \$],
    [0 \$],
    [Non],
    [E],
    [100 \$],
    [0 \$],
    [Non],
)

Le capital final complet vaut 320 dollars. La perte du portefeuille initial est #raw("320 / 500 - 1"), soit 36 %. Si nous oublions D et E, nous comparons les mêmes 320 dollars à seulement 300 dollars de capital initial. Le calcul affiche alors un gain de 6,67 %.

Ce *biais de survie* vient du choix des entités après avoir observé ce qu'elles sont devenues. L'exemple montre un mécanisme possible. Toutes les radiations ne sont pas des faillites, et leur prix final ne vaut pas toujours zéro. L'effet sur une stratégie qui achète certains titres et en vend d'autres peut aussi changer de signe.

#figure(image("../docs/guide/figures/survie_exemple.png", width: 100%), caption: [Ce que l'oubli de deux entreprises change])

La première barre part du portefeuille réellement constitué dans l'exemple. La seconde ne conserve que les trois entreprises sélectionnées à la fin. Le gain apparent vient du dénominateur et des entités oubliées. Il ne vient pas d'une nouvelle décision de placement.

=== Pourquoi prolonger l'étude de Gu, Kelly et Xiu

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/011_cross_sectional_ml.md")[étude 011] dispose d'un historique court et de 27 caractéristiques. Nous prolongeons ici la durée avec des prix disponibles, mais conservons seulement cinq caractéristiques de prix. La question est de savoir si les arbres améliorent la prévision face à une régression dans cette autre expérience.

Cette modification change plusieurs éléments à la fois. L'historique est plus long, les caractéristiques sont différentes et la sélection des entreprises reste imparfaite. Un meilleur résultat ne permet donc pas d'identifier la seule contribution de la durée. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/gu_kelly_xiu_2020.md")[fiche Gu, Kelly et Xiu] explique le protocole de référence et ses différences avec nos données.

=== Ce qui est effectivement mesuré

L'étude utilise 502 entreprises retenues depuis un univers actuel, avec des prix remontant dans le passé. Les modèles apprennent sur les observations antérieures à leurs tests. Le panel de prix couvre 1986 à juin 2026. Les résultats de portefeuille commencent en février 1996 et finissent en juin 2026.

Le portefeuille achète un dixième des actions préférées et vend un dixième des moins préférées. Les coûts sont modélisés à dix points de base par unité négociée. Ce sont des résultats hors échantillon pour l'ajustement du modèle, mais pas pour la sélection de l'univers.

#table(
  columns: 4,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Modèle*],
    [*R² par rapport à la prévision nulle*],
    [*Corrélation moyenne du classement*],
    [*Sharpe du portefeuille net*],
    [Régression pénalisée],
    [1,64 %],
    [0,027],
    [0,601],
    [Arbres amplifiés],
    [1,56 %],
    [0,024],
    [0,849],
    [Forêt aléatoire],
    [1,69 %],
    [0,026],
    [0,807],
)

Les mesures sont positives, et les arbres présentent un meilleur Sharpe observé que la régression. Cela ne démontre ni une supériorité de prévision suffisamment précise, ni une stratégie disponible pour un investisseur historique. Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/013_cross_sectional_ml_long/results/tables/evaluation.csv")[erreurs de prévision] et les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/013_cross_sectional_ml_long/results/tables/portfolios.csv")[portefeuilles enregistrés] sont les sources du tableau.

=== Pourquoi des tests peuvent réussir malgré le problème

Un test de stabilité demande si un résultat se retrouve sur plusieurs périodes. Il ne demande pas automatiquement si les entreprises du panel étaient celles que l'investisseur pouvait choisir à l'époque. Une sélection persistante peut donc produire un résultat stable sur des données mal adaptées à la question.

Le laboratoire compare aussi des signaux simples aux portefeuilles de Kenneth French, construits avec les titres disparus. Ces comparaisons révèlent des différences de signe ou d'ampleur selon le signal. Elles ne constituent pas une mesure pure du biais de survie, car les univers et certaines définitions de signaux diffèrent également.

=== La conclusion et ses limites

Le résultat favorable doit être lu avec la sélection des entreprises au premier plan. On ne peut pas attribuer toute la différence à un modèle plus efficace, ni chiffrer une causalité unique avec cette comparaison. Un univers historique complet permettrait de refaire la même construction avec et sans les exclusions, en tenant les autres choix constants.

Le verdict #raw("REJECTED") conserve les critères de l'expérience initiale. Les résultats détaillés et les écarts de définition restent dans l'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/013_cross_sectional_ml_long/ANNEXE_TECHNIQUE.md")[annexe technique]. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/02_donnees.md")[chapitre sur les dates] explique pourquoi dater les informations et reconstruire l'univers sont deux contrôles différents.

#pagebreak(weak: true)
== 014 Les huit premières stratégies s'affaiblissent-elles après publication ?

L'étude compare la période de chaque article, la période suivante et la période après publication. Elle utilise les huit premières stratégies du laboratoire. Cet ensemble mélange plusieurs classes d'actifs et ne reproduit pas l'univers de l'article de référence.

=== Un exemple fictif

Une stratégie rapporte en moyenne 1 % par mois avant publication et 0,3 % après. Elle conserve 30 % de son rendement moyen initial, ce qui correspond à une baisse de 70 %. Elle ne perd pas pour autant 70 % de sa valeur.

Une autre passe de 0,1 % à 0,2 %. Elle double son rendement moyen malgré un faible changement absolu. Les rapports deviennent donc sensibles aux petites moyennes initiales.

=== Le contexte de McLean et Pontiff

Les auteurs examinent 97 caractéristiques d'actions. Notre comparaison porte sur huit séries de stratégies différentes. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/mclean_pontiff_2016.md")[fiche de littérature] indique les résultats obtenus depuis le résumé et les limites d'accès au texte complet.

Le laboratoire sépare la moyenne des rapports d'une régression. Ces deux calculs ne répondent pas exactement à la même question.

=== Le constat

Les huit séries présentent un rendement moyen plus faible après publication dans les fenêtres retenues. La baisse moyenne calculée par les rapports vaut 72,7 %, avant les coûts propres à une mise en œuvre. Les dates diffèrent selon les articles.

Huit séries constituent un petit ensemble, avec des dépendances entre certaines stratégies. Un rééchantillonnage de stratégies ne suffit pas à éliminer ces limites.

=== Ce que l'on ne peut pas en déduire

La publication peut attirer la concurrence, mais cette comparaison ne l'isole pas comme cause. Les conditions de marché et la sélection initiale des résultats changent également. Un intervalle contenant une valeur publiée n'établit pas une réplication exacte.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/016_publication_decay_212.md")[étude 016] élargit l'analyse à des portefeuilles d'actions américains et distingue plus précisément les mesures.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/014_publication_decay/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/014_publication_decay/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/014_publication_decay/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 015 Une liste de titres disparus suffit-elle pour refaire leur histoire ?

Pour tester un ancien portefeuille, il faut savoir quels titres existaient et retrouver leurs rendements. Une liste historique répond à la première question. Elle ne répond pas automatiquement à la seconde.

Cette étude mesure les accès obtenus avec le forfait utilisé au début de septembre 2026. Elle constitue un audit de source, pas une étude de performance ni une conclusion permanente sur l'offre du fournisseur.

=== Un exemple fictif

Un référentiel confirme qu'une entreprise cotait en 2008 et qu'elle a disparu en 2009. Sans son prix d'achat, ses distributions et sa valeur de sortie, on ne peut pas calculer le rendement du placement. La disparition pourrait venir d'une faillite ou d'une acquisition.

La connaître ne permet donc pas d'imposer arbitrairement une perte de 100 %.

=== Ce que les requêtes ont montré

L'extraction conserve 6 425 actions ordinaires radiées et datées depuis 2004. La requête de prix ancienne nécessaire à l'expérience n'a toutefois pas fourni l'historique attendu avec cet accès. Le référentiel est utile, mais les prix obtenus ne suffisent pas à construire l'univers demandé depuis 1996.

Les réponses, les dates et les paramètres appartiennent au résultat de l'audit. Un refus d'accès ponctuel ne doit pas être interprété comme une impossibilité définitive.

=== Pourquoi ce résultat est important

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/etudes/013_cross_sectional_ml_long.md")[étude 013] reste limitée par un panel de survivants. Ce référentiel permet de documenter l'étendue des absences. Il ne chiffre pas leur effet exact sur la performance faute de rendements complets.

Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/specs/001-univers-sans-biais-de-survie.md")[cahier de l'univers historique] définit ce que la source devait fournir. Le statut de rejet signifie que cette source, dans les conditions testées, ne satisfait pas cette demande.

=== La suite raisonnable

Une nouvelle extraction doit redater les accès et conserver les réponses. Elle doit aussi vérifier les acquisitions, les identifiants et les rendements de sortie. L'amélioration recherchée est une histoire des investissements possibles, au-delà d'une liste de symboles.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/015_univers_polygon/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/015_univers_polygon/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/015_univers_polygon/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 016 Que reste-t-il d'une stratégie après sa publication ?

Le rendement diminue après publication pour 82,7 % des 208 portefeuilles comparables de cette étude. Cette observation ne désigne pas, à elle seule, la cause de la baisse. La sélection initiale, l'évolution des marchés et l'exploitation de l'information peuvent produire des effets qui se superposent.

=== Une baisse de moitié ne signifie pas une perte de moitié

Prenons un exemple fictif. Une règle gagne en moyenne 1 % par mois dans l'échantillon qui a servi à la découvrir. Après publication, elle gagne 0,4 % par mois. Elle conserve #raw("0,4 / 1 = 40 %") de son rendement moyen antérieur. La baisse du rendement moyen vaut donc 60 %. Le portefeuille ne perd pas nécessairement 60 % de sa valeur.

Changeons maintenant le rendement initial. Une règle passe de 0,1 % à 0,2 % par mois. Son rendement double, mais l'amélioration en niveau n'est que de 0,1 point de pourcentage mensuel. Les rapports deviennent instables quand leur dénominateur est proche de zéro. Il faut regarder les niveaux et les proportions avant de résumer plusieurs stratégies ensemble.

=== Pourquoi McLean et Pontiff séparent les périodes

McLean et Pontiff étudient 97 variables auparavant associées aux rendements d'actions. Ils distinguent l'échantillon des recherches initiales, la période suivante et celle après publication. Leur résumé rapporte des baisses de 26 % hors échantillon et de 58 % après publication. Ces nombres concernent leur dispositif et leur ensemble de variables. #link("https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365")[Article de référence].

La séparation temporelle aide à examiner des explications concurrentes. Une découverte sélectionnée pour son résultat exceptionnel peut décevoir dès la période suivante, même si personne ne lit l'article. La diffusion de l'idée peut aussi modifier les prix. Une comparaison descriptive ne suffit pas à isoler cette seconde explication.

=== Comment le laboratoire construit sa comparaison

Les portefeuilles proviennent d'Open Source Asset Pricing, le projet de Chen et Zimmermann. Leurs séries sont construites depuis CRSP et comprennent les rendements de radiation des actions. Le fichier téléchargé contient 212 portefeuilles. Le minimum d'observations laisse 208 comparaisons après publication.

Chaque portefeuille possède ses propres dates. Une règle publiée en 1990 et une autre publiée en 2018 ne partagent pas la même période suivante. Les séries couvrent collectivement 1926 à 2024, avec des durées différentes selon les règles. Les rendements sont bruts de frais.

#table(
  columns: 3,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Élément*],
    [*Recherche source*],
    [*Adaptation du laboratoire*],
    [Ensemble étudié],
    [97 variables chez McLean et Pontiff],
    [Portefeuilles disponibles chez Chen et Zimmermann],
    [Dates],
    [Fenêtres des recherches et publication],
    [Publication connue à l'année dans les métadonnées utilisées],
    [Construction],
    [Dispositif des auteurs],
    [Séries déjà construites par le fournisseur universitaire],
    [Résumé],
    [Estimations du papier],
    [Moyenne, médiane et régression publiées séparément],
)

Le tableau décrit des différences de méthode. L'étude constitue une extension descriptive, avec des limites documentées, plutôt qu'une reproduction exacte des tables du papier. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/mclean_pontiff_2016.md")[fiche de littérature] conserve le statut de lecture des sources.

=== Lire ensemble la moyenne, la médiane et la régression

#table(
  columns: 2,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Mesure*],
    [*Résultat après publication*],
    [Rendement antérieur conservé, médiane des rapports],
    [41,9 %],
    [Rendement antérieur conservé, moyenne des rapports],
    [53,0 %],
    [Portefeuilles dont le rendement diminue],
    [82,7 %],
    [Baisse estimée par la régression retenue],
    [36,4 %],
    [Statistique t de cette baisse dans la régression],
    [-1,20],
)

La *médiane* partage les rapports en deux groupes de même taille. La moyenne additionne les rapports et divise par leur nombre. Quelques rapports extrêmes peuvent déplacer fortement la moyenne. Leur désaccord n'est donc pas une erreur de calcul.

La régression emploie encore une autre pondération et une autre mesure d'incertitude. Sa statistique t rapporte le coefficient à son erreur type. Sa taille ne permet pas ici de distinguer nettement l'estimation de zéro aux seuils usuels. Un grand nombre de baisses individuelles ne garantit pas que toute estimation agrégée sera précise. Sources numériques dans les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/016_publication_decay_212/results/tables/windows.csv")[fenêtres individuelles] et les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/016_publication_decay_212/results/metrics.json")[résultats enregistrés].

#figure(image("../docs/guide/figures/publication_distribution.png", width: 100%), caption: [Les rapports avant et après publication])

Chaque point représente un portefeuille et indique la part de rendement moyen conservée. La ligne verticale à 100 % marque l'absence de baisse. Le panneau central montre les valeurs courantes. Le panneau séparé conserve les valeurs extrêmes et leurs étiquettes. Aucune valeur n'est remplacée par la borne de l'axe.

=== Ce que nous ne pouvons pas attribuer à la publication

Les portefeuilles récemment publiés ont une période suivante plus courte et exposée à des conditions de marché différentes. La date de publication n'est pas assignée au hasard. Les différences par décennie ne constituent donc pas une expérience causale.

Les historiques téléchargés sont également une version récente des données. Inclure les actions disparues ne garantit pas que toutes les informations soient celles disponibles à chaque date historique. Ces deux problèmes doivent être examinés séparément.

=== Vérifier et poursuivre

Le vérificateur relit chaque rapport dans le fichier des fenêtres. Les champs des textes sont calculés depuis les sorties enregistrées. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/016_publication_decay_212/ANNEXE_TECHNIQUE.md")[annexe technique] contient les autres regroupements et les conventions. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/04_hasard.md")[chapitre sur le hasard] explique comment la sélection initiale peut rendre une découverte trop favorable.

#pagebreak(weak: true)
== 017 Échanger moins permet-il de gagner davantage après frais ?

Un signal propose une position cible. La rejoindre immédiatement coûte des échanges. S'en approcher progressivement économise parfois des frais, mais retarde aussi la prise de position.

=== Un exemple fictif

Le portefeuille détient 20 dollars et le signal demande d'en détenir 100. Rejoindre toute la cible exige un achat de 80 dollars. Parcourir la moitié du chemin demande un achat de 40 dollars et laisse une position de 60 dollars.

Si le signal persiste, la seconde règle pourra continuer à s'en approcher. S'il change rapidement, le retard peut faire perdre une partie de son intérêt.

=== Le lien avec l'article

Gârleanu et Pedersen étudient une décision dynamique avec rendements prévisibles et coûts. Leur cible tient compte de l'évolution attendue des signaux. Notre règle simplifiée avance d'une fraction fixe vers la cible courante du suivi de tendance.

Cette expérience n'est donc pas une réplication de toute la solution optimale. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/garleanu_pedersen_2013.md")[fiche de littérature] explique la différence.

=== La comparaison retenue

La vitesse de moitié est choisie sur la période antérieure à la publication. Sur les 169 mois suivants, jusqu'en juin 2026, les résultats nets sont les suivants.

#table(
  columns: 3,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Règle*],
    [*Rotation annuelle en fois le capital*],
    [*Sharpe net*],
    [Rejoindre la moitié du chemin],
    [5,75],
    [0,162],
    [Rejoindre toute la cible],
    [9,15],
    [0,176],
)

Les coûts sont modélisés et comprennent les hypothèses détaillées dans l'annexe. La rotation diminue, mais la performance ajustée de sa dispersion ne s'améliore pas dans cette comparaison.

=== Le meilleur réglage observé ne devient pas la règle retenue

Un réglage plus lent gagne dans la période finale. Le choisir après coup ne fournirait pas une preuve indépendante sur cette période. Il peut servir d'hypothèse pour un prochain test, avec un nouveau protocole.

Cette distinction est le sujet du #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/03_calendrier.md")[chapitre sur le calendrier].

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/017_viser_devant_la_cible/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/017_viser_devant_la_cible/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/017_viser_devant_la_cible/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 018 À quel moment de la journée les rendements apparaissent-ils ?

Dans cette décomposition historique, le momentum temporel gagne pendant la nuit et perd pendant la séance. Les calculs portent sur des rendements bruts et sur les positions de l'étude 001. Ils ne mesurent pas encore la performance nette d'une stratégie qui négocierait tous les soirs et tous les matins.

=== Suivre le prix sur une seule séance

Prenons un exemple fictif, sans dividende ni division d'action. Le titre clôture à 100 dollars, ouvre le lendemain à 102 dollars, puis clôture à 101 dollars.

#table(
  columns: 3,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Moment*],
    [*Prix*],
    [*Calcul du rendement*],
    [Clôture précédente],
    [100 \$],
    [Point de départ],
    [Ouverture suivante],
    [102 \$],
    [Nuit, #raw("102 / 100 - 1 = 2 %")],
    [Nouvelle clôture],
    [101 \$],
    [Séance, #raw("101 / 102 - 1 = -0,9804 %")],
)

Sur la période entière, le rendement vaut #raw("101 / 100 - 1 = 1 %"). Additionner les deux pourcentages donne environ 1,0196 %, ce qui n'est pas le bon calcul. Il faut composer les facteurs de croissance, #raw("1,02 × (101 / 102) = 1,01"). La différence vient du montant sur lequel le second rendement s'applique.

=== Ce que la littérature cherche à distinguer

Lou, Polk et Skouras étudient séparément les rendements de nuit et de séance pour des stratégies sur actions. Des populations d'investisseurs et des contraintes différentes peuvent intervenir à ces moments. Le partage du rendement aide à décrire où se situe une régularité. Il ne permet pas, seul, de désigner les investisseurs responsables. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/lou_polk_skouras_2019.md")[fiche de l'article] présente les stratégies et les limites de la transposition.

Le laboratoire applique cette question à une stratégie de momentum temporel et à cinq fonds cotés. Un *momentum temporel* choisit le sens d'une position selon le passé du même actif. Il diffère d'un classement des actions les unes contre les autres.

=== Comment la décomposition est construite

Pour chaque fonds, le code sépare l'ouverture et la clôture quotidiennes. Il applique un ajustement des prix afin de tenir compte des événements sur les titres. Cet ajustement est exact pour une division, mais son emploi pour les dividendes reste une approximation déclarée.

Les parts quotidiennes sont ensuite composées dans le mois. Les mêmes poids de portefeuille, décidés avec un décalage d'un mois, sont appliqués au total et aux deux parts. Le résultat concerne 234 mois, de janvier 2007 à juin 2026, sur 28 fonds.

=== Lire le résultat sans oublier le terme de composition

#table(
  columns: 2,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Composante de la stratégie*],
    [*Rendement moyen annualisé*],
    [Nuit],
    [10,21 %],
    [Séance],
    [-2,97 %],
    [Résidu de la décomposition retenue],
    [-0,75 %],
    [Total excédentaire],
    [6,49 %],
)

Ces nombres viennent de la section #raw("strategy") des #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/018_nuit_contre_journee/results/metrics.json")[résultats enregistrés]. Le résidu conserve l'écart entre le total excédentaire et les deux composantes calculées. La composition et les conventions de soustraction du taux sans risque doivent rester cohérentes pour l'interpréter.

#figure(image("../docs/guide/figures/nuit_journee.png", width: 100%), caption: [Décomposer le résultat de nuit et de séance])

Les barres montrent les contributions mesurées selon les conventions de l'étude. Le résidu est visible au lieu d'être absorbé dans l'une des périodes. Le bleu positif et l'orange négatif indiquent où les gains et les pertes sont observés, avant frais.

=== Pourquoi cela ne donne pas directement une règle profitable

Détenir seulement la nuit demanderait une entrée et une sortie fréquentes. Dans un exemple fictif, un aller-retour coûtant 0,04 % répété 250 fois représente 10 % du capital initial en coûts additionnés. Ce calcul suppose un montant négocié constant. Il ne mesure pas le coût réel des positions variables du laboratoire.

Il faut également tenir compte des prix d'exécution et des risques entre la clôture et l'ouverture. Le résultat brut ne prouve donc pas que la stratégie de nuit domine après frais. Inversement, on ne peut pas affirmer que les frais l'annulent sans calculer les montants réellement négociés.

=== Ce que l'étude laisse ouvert

La même décomposition devrait être examinée sur plusieurs sous-périodes et avec des conventions de dividendes contrôlées. Une règle négociable de nuit demanderait son propre protocole, ses prix d'exécution et ses coûts. Ces expériences ne sont pas remplacées par le graphique de décomposition.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/018_nuit_contre_journee/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les cinq fonds et les contrôles d'identité. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/lean/README.md")[comparaison avec LEAN] examine séparément ce que change un autre calendrier d'exécution.

#pagebreak(weak: true)
== 019 Les facteurs des cryptomonnaies paient-ils leur rotation ?

L'étude construit trois séries à partir de prix publics. Le marché représente l'exposition générale aux monnaies suivies. La taille compare les petites et grandes capitalisations, tandis que le momentum compare leurs rendements passés.

=== Un exemple fictif

Un portefeuille de 1 000 dollars échange pour 2 000 dollars pendant une semaine. Avec un coût de 50 points de base par montant négocié, il paie dix dollars. Cela représente 1 % de son capital avant les autres coûts.

Un rendement hebdomadaire brut positif peut donc devenir négatif. Cette arithmétique dépend du montant réellement échangé et de la convention de coût.

=== Le lien avec la littérature

Liu, Tsyvinski et Wu étudient des facteurs communs sur un univers plus large. Le texte intégral n'a pas été consulté dans l'expérience initiale. Il faut donc lire ce travail comme une adaptation documentée, sans revendiquer une réplication intégrale.

La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/specs/005-cryptomonnaies-coin-metrics.md")[spécification] décrit les données communautaires Coin Metrics. Les fichiers conservent certains actifs disparus, mais seuls 139 actifs possèdent un prix dans l'extraction. Ce n'est pas l'ensemble des cryptomonnaies ayant existé.

=== Le résultat après publication

Le momentum présente un Sharpe net de -0,600 sur 213 semaines après avril 2022, jusqu'au 24 mai 2026. Le coût de base vaut 50 points de base par unité négociée. La rotation moyenne publiée pour l'ensemble de l'historique vaut 2,04 fois le capital par semaine.

Cette moyenne de rotation ne doit pas être appliquée comme si elle appartenait à chaque sous-période. Les calculs nets utilisent les échanges datés.

=== Ce qui reste à examiner

La qualité des prix, l'emprunt des positions vendues et les différences entre plateformes limitent une interprétation investissable. Le résultat rejette cette construction selon les hypothèses retenues. Il ne démontre pas que tout facteur de cryptomonnaies est dépourvu d'information.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/019_facteurs_crypto/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/019_facteurs_crypto/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/019_facteurs_crypto/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 020 Copier les plus grosses positions des gestionnaires aide-t-il ?

Les déclarations 13F indiquent certaines positions détenues par de grands gestionnaires. Elles décrivent une fin de trimestre, mais deviennent publiques plus tard. Le laboratoire choisit des positions seulement après le délai de formation déclaré.

=== Un exemple fictif

Un gestionnaire possède 20 % de son portefeuille dans A au 31 mars. Il dépose sa déclaration le 12 mai. Un investisseur qui lit ce dépôt ne peut pas prétendre avoir copié cette information le 1er avril.

La position peut aussi avoir changé entre mars et mai. La déclaration révèle une détention passée, pas nécessairement la conviction actuelle du gestionnaire.

=== La question inspirée de la littérature

Le document de Cohen, Polk et Silli motive l'idée de regarder les positions les plus importantes. Le texte intégral n'a pas été lu dans l'expérience initiale. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/cohen_polk_silli_2010.md")[fiche de littérature] déclare cette limite.

Notre règle sélectionne la plus grosse position de gestionnaires répondant à des seuils de concentration. Elle forme le portefeuille au quarante-sixième jour après la fin du trimestre, avec les dépôts alors reçus.

=== Le résultat et son unité

Sur 157 mois, de 2013 à août 2026, la série des écarts mensuels au marché produit un rendement composé annualisé de 0,27 % avant frais. Il devient -0,05 % après dix points de base par unité négociée selon la convention de l'étude.

Composer les différences mensuelles ne revient pas à soustraire les rendements annualisés des deux placements. L'annexe publie aussi ces rendements séparés et la régression contre le marché. La supériorité n'est pas suffisamment établie dans les tests retenus.

=== La limite qui pèse sur l'interprétation

28,9 % des idées formées n'ont pas de prix dans la source utilisée. Dater correctement les dépôts ne restitue pas ces observations manquantes. La plus grosse position peut également refléter une hausse passée, des contraintes ou un mandat, plutôt qu'une information privée.

Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/02_donnees.md")[chapitre sur les données] distingue ces problèmes.

=== Vérifier le résultat

Les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/020_meilleures_idees_13f/results/metrics.json")[mesures enregistrées] donnent les nombres et leurs fenêtres. L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/020_meilleures_idees_13f/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les tableaux, les hypothèses, les limites et les commandes de calcul. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/020_meilleures_idees_13f/run.py")[script de l'étude] relie ces choix aux fonctions du laboratoire.

#pagebreak(weak: true)
== 021 Pourquoi refuser un portefeuille qui gagne de l'argent ?

Le portefeuille étudié obtient un Sharpe net de 0,629, mais ne remplit pas tous les critères fixés pour le retenir. Son meilleur composant seul obtient 0,696 sur la même période. Le refus porte sur une règle de décision et une hypothèse précises. Il ne signifie pas que tous les rendements observés sont négatifs.

=== Trois sources de rendement dans un même portefeuille

Une première composante suit les tendances. Une deuxième combine la valeur et le momentum. La troisième vend des options de vente, qui obligent leur vendeur à acheter à un prix convenu si leur détenteur exerce ce droit. La prime reçue rémunère une exposition aux pertes, parfois importantes, lorsque les prix baissent fortement.

Ces composantes peuvent perdre à des moments différents. Les mélanger cherche à rendre le risque plus régulier, mais ne garantit pas de battre chaque composante sur toute mesure. Une protection utile dans une crise peut avoir un coût pendant le reste de l'historique.

=== Un exemple de diversification qui coûte quelque chose

L'exemple est fictif et comporte deux périodes. Le placement A gagne 10 % puis perd 10 %. Le placement B perd 2 % puis gagne 8 %. À parts égales rééquilibrées avant chaque période, leur mélange gagne 4 % puis perd 1 %.

#table(
  columns: 4,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Placement*],
    [*Première période*],
    [*Deuxième période*],
    [*Gain composé*],
    [A],
    [+10 %],
    [-10 %],
    [-1 %],
    [B],
    [-2 %],
    [+8 %],
    [+5,84 %],
    [Mélange à parts égales],
    [+4 %],
    [-1 %],
    [+2,96 %],
)

Le mélange évite les variations extrêmes de A, mais gagne moins que B sur cet exemple. Le qualifier de meilleur demande donc de préciser le critère retenu. Le rendement final, la perte maximale et la régularité ne répondent pas à la même question.

=== Comment les articles conduisent à la question locale

Les travaux sur la tendance, la valeur et le momentum motivent les composantes. Les indices du Cboe fournissent une référence pour la vente d'options. Les recherches sur la diversification et le contrôle de volatilité motivent la règle de combinaison. Il s'agit d'une construction inspirée de plusieurs travaux, avec des substituts de données et des coûts modélisés.

Les références sont #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/hurst_ooi_pedersen_2017.md")[Hurst, Ooi et Pedersen], #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/asness_moskowitz_pedersen_2013.md")[Asness, Moskowitz et Pedersen] et #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/literature/moreira_muir_2017.md")[Moreira et Muir]. La #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/specs/007-indices-cboe-et-empilement.md")[spécification initiale] décrit les choix écrits avant les calculs de cette étude.

=== La règle retenue avant de regarder

Les composantes les moins volatiles reçoivent davantage de poids. La *volatilité* mesure la dispersion des rendements, pas toutes les formes de risque. L'allocation vise une volatilité annuelle de 10 %, mais l'exposition totale est plafonnée à 1,5 fois le capital.

Dépasser une fois le capital exige un financement. Le coût supposé dépasse le taux court de 0,50 point de pourcentage annuel. Ce choix est une hypothèse de l'expérience, et non un tarif garanti pour un investisseur. Les autres coûts portent sur les transactions et le renouvellement des options.

Le test couvre 187 mois, de décembre 2010 à juin 2026. Les 78 derniers mois constituent la période finale réservée dans le protocole local. Cette réservation locale ne rend pas l'histoire économique inconnue du chercheur et n'efface pas les études déjà consultées.

=== Comparer le résultat aux critères

#table(
  columns: 3,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Mesure*],
    [*Résultat enregistré*],
    [*Lecture*],
    [Sharpe du portefeuille net],
    [0,629],
    [Rendement excédentaire rapporté à sa dispersion],
    [Sharpe du meilleur composant seul],
    [0,696],
    [Le portefeuille ne le dépasse pas sur ce critère],
    [Sharpe dans la période finale],
    [0,884],
    [Résultat positif dans la fenêtre réservée],
    [Statistique t dans la période finale],
    [2,30],
    [Sous le seuil de 3 fixé dans le protocole],
    [Pire repli depuis un sommet],
    [-16,0 %],
    [Perte historique maximale de la courbe retenue],
)

Les deux Sharpes du début sont calculés sur la même fenêtre. La comparaison ne suffit pas à prouver que leur différence est statistiquement distincte de zéro. Le critère initial demandait toutefois que le portefeuille dépasse son meilleur composant. La valeur observée n'y satisfait pas. Source dans les #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/021_portefeuille_de_primes/results/metrics.json")[résultats de référence].

#figure(image("../docs/guide/figures/verdict_portefeuille.png", width: 100%), caption: [Les critères de décision du portefeuille])

Le graphique distingue la comparaison des Sharpes et le seuil statistique. Les axes sont séparés, car un Sharpe et une statistique t n'ont pas la même signification. Un résultat positif peut rester sous la barre de décision choisie.

=== Le libellé automatique demande une traduction

Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/021_portefeuille_de_primes/results/tables/verdict_reasons.csv")[fichier de verdict] appelle « réplication » la comparaison avec le meilleur composant. Dans ce cas, la référence est une autre sortie du laboratoire, pas un chiffre reproduit depuis un article. La corrélation avec un portefeuille existant y est aussi indiquée comme non mesurée. Elle constitue une preuve manquante, et non une corrélation défavorable observée.

Cette lecture distingue un critère échoué d'un contrôle absent. Elle empêche le mot #raw("REJECTED") de masquer la nature du problème. Les seuils de 3 ou de 0,95 sont des choix du protocole, pas des lois universelles de l'investissement.

=== Pourquoi ne pas retirer immédiatement la composante décevante

L'analyse détaillée montre qu'enlever la tendance améliorerait le Sharpe dans cet historique. Ce diagnostic peut motiver une nouvelle hypothèse. Il ne peut pas être utilisé pour annoncer que la règle initiale avait réussi. La nouvelle règle demanderait une nouvelle évaluation et une déclaration du nombre d'essais supplémentaires.

L'#link("https://github.com/Guilou001/quant-research-platform/blob/main/studies/021_portefeuille_de_primes/ANNEXE_TECHNIQUE.md")[annexe technique] conserve les variantes, les retraits de composantes et les coûts. Le #link("https://github.com/Guilou001/quant-research-platform/blob/main/docs/guide/08_conclusion.md")[chapitre sur le verdict] donne une grille pour lire les autres études avec la même distinction.
