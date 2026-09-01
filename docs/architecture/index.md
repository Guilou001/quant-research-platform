# L'architecture, et la raison de chaque frontière

L'architecture répond à une seule question : qu'est-ce qui devra être remplacé
un jour, et comment le remplacer sans réécrire le reste ? Trois choses le seront
avec certitude. La source de données, quand les données gratuites ne suffiront
plus. Le moteur de backtest, quand il faudra un modèle d'exécution réaliste. Le
modèle d'alpha, à chaque étude.

Tout le reste découle de là.

## La chaîne, de la donnée au verdict

```mermaid
flowchart TD
    S1[Sources gratuites<br/>Yahoo, SEC, FRED, ALFRED, Ken French, AQR] --> RAW[(raw<br/>immuable)]
    RAW --> BRONZE[(bronze<br/>parsé, typé)]
    BRONZE --> SILVER[(silver<br/>propre, actions traitées)]
    SILVER --> GOLD[(gold<br/>consommable + manifeste)]
    GOLD --> PIT[Point-in-time<br/>as_of]
    PIT --> FEAT[Caractéristiques]
    FEAT --> ALPHA[Modèle d'alpha]
    ALPHA --> SIG[Signal standardisé<br/>z-score, rang, neutralisation]
    SIG --> OPT[Optimiseur]
    RISK[Modèle de risque<br/>covariance, facteurs] --> OPT
    COST[Modèle de coût<br/>commission, écart, impact] --> OPT
    LIM[Contraintes<br/>levier, concentration, liquidité] --> OPT
    OPT --> BOOK[Portefeuille cible]
    BOOK --> EXEC[Exécution<br/>décalage, participation]
    EXEC --> BT[Moteur de backtest]
    BT --> AN[Analytique<br/>performance, risque, attribution]
    AN --> VAL{Moteur de validation}
    VAL -->|hors échantillon, coûts,<br/>DSR, PBO, régimes| VERD[Verdict]
    VERD --> PF[Portefeuille multi-stratégies]
```

Le point important de ce schéma est ce qui n'y figure pas. Aucune flèche ne
remonte : une étape ne consulte jamais une étape ultérieure, et c'est ce qui
interdit structurellement l'information future.

## Ce que chaque sous-paquet promet

| Sous-paquet | Ce qu'il fait | Ce qu'il ne fait jamais |
|---|---|---|
| `core` | contrats, configuration, calendrier, journal, déterminisme | connaître une source ou une bibliothèque de calcul |
| `data` | lac, provenance, point-in-time, qualité | décider d'une stratégie |
| `features` | transformer des données en caractéristiques | télécharger |
| `signals` | standardiser et neutraliser un signal | fabriquer des poids |
| `strategies` | assembler un signal en règle de portefeuille | connaître un fournisseur |
| `models` | apprentissage statistique | contourner la validation |
| `validation` | séparer un résultat d'une coïncidence | regarder le holdout final sans le compter |
| `portfolio` | covariance, contraintes, optimisation | ignorer les coûts |
| `risk` | contributions, queues, tension | se limiter à la variance |
| `execution` | coûts, impact, participation, capacité | supposer le levier gratuit |
| `backtest` | rejouer une suite de portefeuilles | inventer un prix |
| `analytics` | mesurer performance et risque | dupliquer une métrique |
| `reporting` | rapport d'étude, figures, tableaux | choisir le verdict |
| `experiments` | trace, registre, reproductibilité | oublier un essai |

## Les onze protocoles

Les frontières sont déclarées dans `quantlab.core.protocols` avec
`typing.Protocol`, donc structurelles : une classe satisfait un protocole en
portant les bonnes méthodes, sans hériter de rien.

```mermaid
classDiagram
    class DataProvider {
        +name: str
        +fetch(start, end) DataFrame
        +manifest() DatasetManifest
    }
    class PointInTimeDataset {
        +as_of(date) DataFrame
    }
    class AlphaModel {
        +name: str
        +predict(features) Series
    }
    class RiskModel {
        +covariance(returns) DataFrame
    }
    class CostModel {
        +cost(previous, target, context) float
    }
    class PortfolioOptimizer {
        +optimize(alpha, covariance, previous) Weights
    }
    class BacktestEngine {
        +run(weights, prices) ReturnSeries
    }
    AlphaModel ..> PortfolioOptimizer : alpha attendu
    RiskModel ..> PortfolioOptimizer : covariance
    CostModel ..> PortfolioOptimizer : pénalité de négociation
    PortfolioOptimizer ..> BacktestEngine : poids cibles
    DataProvider ..> PointInTimeDataset : quatre dates
```

Le détail du raisonnement vit dans [ADR-003](adr/adr-003-protocoles.md).

## L'architecture cible du fonds

Une fois plusieurs stratégies validées, elles ne s'additionnent pas : elles se
budgètent en risque.

```mermaid
flowchart TD
    subgraph SOURCES[Sources d'alpha]
        T[Tendance et macro<br/>TSMOM, portage]
        E[Facteurs actions<br/>valeur, momentum, qualité, BAB]
        A[Arbitrage statistique<br/>résidus d'ACP, retour à la moyenne]
    end
    T --> AE[Moteur d'alpha<br/>combinaison pondérée]
    E --> AE
    A --> AE
    AE --> RE[Moteur de risque]
    subgraph RISQUE[Ce que le moteur de risque tient]
        C1[Covariance et facteurs]
        C2[Risque de queue et drawdown]
        C3[Liquidité et capacité]
    end
    RE --- C1
    RE --- C2
    RE --- C3
    RE --> O[Optimisation]
    O --> CM[Modèle de coût]
    CM --> TB[Livre cible]
    TB --> X[Exécution]
    X --> AN[Analytique]
    AN -.rétroaction mesurée.-> AE
```

La question posée à chaque nouvelle stratégie n'est pas « rapporte-t-elle ? »
mais « apporte-t-elle quelque chose à ce que nous détenons déjà ? ». Une
stratégie de ratio de Sharpe 0,8 décorrélée des autres vaut mieux qu'une
stratégie de 1,5 qui répète une position existante.
