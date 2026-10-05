# Vérification finale

Toutes les modifications et tous les environnements, caches et résultats locaux se trouvent dans le dossier Draft.

## Installation

Environnement .venv créé depuis zéro avec Python 3.10. Installation réussie de `requirements-dev.txt`, qui inclut `requirements.txt` et ses dépendances déclarées dans pyproject.toml. Voir dependency-install.log. `pip check`: No broken requirements found. Versions exactes: dependencies-lock.txt.

## Tests

Commande: `.venv/Scripts/pytest.exe -q` (TEMP/TMP et MPLCONFIGDIR dirigés vers le dépôt).

```text
............................................................             [100%]
60 passed in 1.52s
```

## Notebook

Commande: `.venv/Scripts/python.exe run.py`. Exécution complète dans un nouveau noyau, aucune intervention manuelle. Résultat: portfolio_analysis.executed.ipynb. L'avertissement ipykernel sur le transport TCP local sans chiffrement est consigné dans notebook-execution.log; aucun avertissement de calcul ou de données et aucune cellule en erreur.

## Provenance complète

| Asset | Provider | Symbol | Instrument / benchmark | Return type | Native currency | Converted to | FX series used | Raw start date | Raw end date | Raw observations | Final common start | Final common end | Final common observations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Apple | Yahoo Finance | AAPL | Primary US equity | Adjusted price | USD | EUR | EURUSD=X | 1980-12-12 | 2026-10-02 | 11544 | 2019-09-05 | 2026-10-02 | 1763 |
| Nasdaq 100 | Yahoo Finance | QQQ | Invesco QQQ ETF; Nasdaq-100 exposure proxy | Adjusted price | USD | EUR | EURUSD=X | 1999-03-10 | 2026-10-02 | 6935 | 2019-09-05 | 2026-10-02 | 1763 |
| S&P 500 | Yahoo Finance | ^SP500TR | S&P 500 Total Return index | Gross Return | USD | EUR | EURUSD=X | 1988-01-04 | 2026-10-02 | 9761 | 2019-09-05 | 2026-10-02 | 1763 |
| Dow Jones | Yahoo Finance | DIA | State Street SPDR Dow Jones Industrial Average ETF proxy | Adjusted price | USD | EUR | EURUSD=X | 1998-01-20 | 2026-10-02 | 7221 | 2019-09-05 | 2026-10-02 | 1763 |
| CAC 40 | Yahoo Finance | CACC.PA | Amundi CAC 40 UCITS ETF Acc; FR0013380607 proxy | Adjusted price | EUR | EUR |  | 2018-12-13 | 2026-10-02 | 1998 | 2019-09-05 | 2026-10-02 | 1763 |
| Gold | Yahoo Finance | GC=F | Yahoo continuous COMEX gold futures quotation | Price Return | USD | EUR | EURUSD=X | 2000-08-30 | 2026-10-02 | 6548 | 2019-09-05 | 2026-10-02 | 1763 |
| Apple x1.5 | Synthetic from Yahoo Finance | AAPL | 1.5x daily reset of Primary US equity | Synthetic daily-reset NAV | USD | EUR | EURUSD=X | 2019-09-05 | 2026-10-02 | 1779 | 2019-09-05 | 2026-10-02 | 1763 |
| Nasdaq 100 x2 | Synthetic from Yahoo Finance | QQQ | 2x daily reset of Invesco QQQ ETF; Nasdaq-100 exposure proxy | Synthetic daily-reset NAV | USD | EUR | EURUSD=X | 2019-09-05 | 2026-10-02 | 1779 | 2019-09-05 | 2026-10-02 | 1763 |

Les observations brutes des synthétiques correspondent aux séances du NAV effectivement construit, pas à toute l'historique de son sous-jacent. Les snapshots bruts d'origine sont conservés dans .cache/market avec leurs manifestes.

## Limites des séries

| Asset | Distributions | Limitation |
| --- | --- | --- |
| Apple | Yahoo split/dividend adjustment; reinvestment proxy before investor tax | Adjusted prices are a vendor proxy, not an independently audited TR index. |
| Nasdaq 100 | Yahoo dividend/split adjustments; distributions assumed reinvested | Exact Nasdaq-100 TR unavailable from tested Yahoo ^XNDX. QQQ is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark. |
| S&P 500 | Gross dividends reinvested by index methodology |  |
| Dow Jones | Yahoo dividend/split adjustments; distributions assumed reinvested | Exact Dow Jones TR unavailable from tested Yahoo ^DJITR. DIA is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark. |
| CAC 40 | Accumulating share class reinvests within fund; Yahoo adjusted close | Exact CAC 40 GR unavailable from tested Yahoo ^PX1GR. ETF proxy includes fees/tracking effects. Vendor history before issuer-reported 2019-09-05 share-class creation is excluded from the study; lineage discrepancy unresolved. |
| Gold | No dividends; quoted futures price changes only | Not spot gold or an investable futures total-return index: roll, collateral yield and contract stitching are unmodeled. |
| Apple x1.5 | Inherited from underlying; native-currency daily reset, then unlevered FX | Financing, fees, tracking error, trading costs and tax excluded. Adjusted prices are a vendor proxy, not an independently audited TR index. |
| Nasdaq 100 x2 | Inherited from underlying; native-currency daily reset, then unlevered FX | Financing, fees, tracking error, trading costs and tax excluded. Exact Nasdaq-100 TR unavailable from tested Yahoo ^XNDX. QQQ is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark. |

## Conversion EUR: exemple réel

| Date | USD value | EURUSD | Computed EUR value |
| --- | --- | --- | --- |
| 2019-09-05 | 51.166751861572266 | 1.10349702835083 | 46.36782025416115 |
| 2019-09-06 | 51.16194915771485 | 1.1036310195922852 | 46.35783903266477 |
| 2019-09-09 | 51.38027191162109 | 1.1020619869232178 | 46.62194370306398 |
| 2019-09-10 | 51.98723602294922 | 1.1048381328582764 | 47.0541652001596 |
| 2019-09-11 | 53.64017105102539 | 1.1050333976745603 | 48.54167409229994 |

Validation indépendante: valeur EUR = valeur USD / EURUSD (rtol=1e-12, atol=1e-12).

## Performances

| Asset | CAGR | Mean return annualized | Volatility annualized | Max Drawdown | Sharpe | Calmar |
| --- | --- | --- | --- | --- | --- | --- |
| Apple x1.5 | 0.4324331700656709 | 0.4739593130071135 | 0.4697980658958195 | -0.486864238395291 | 1.008857522866467 | 0.8882007261222854 |
| Apple | 0.2999471328164857 | 0.315998113273752 | 0.3179957523825083 | -0.3626955086453707 | 0.9937180321001476 | 0.8269943400643601 |
| Nasdaq 100 | 0.2166181437150203 | 0.2309092780810235 | 0.2545733261925095 | -0.3086610746154563 | 0.9070442749622908 | 0.7017993570614397 |
| Nasdaq 100 x2 | 0.398012819421774 | 0.4617612940758495 | 0.4937908642482999 | -0.5958869896115105 | 0.9351353528558916 | 0.6679333940169748 |
| Gold | 0.1503806484508294 | 0.1612617529896071 | 0.1970613583664647 | -0.2294694923546796 | 0.8183326976246508 | 0.6553404851673856 |
| S&P 500 | 0.1585014315067609 | 0.1711410060274334 | 0.2105434632312853 | -0.331650559695 | 0.8128535714235511 | 0.4779169727695489 |
| Dow Jones | 0.1128113395915597 | 0.1288174901590161 | 0.2027144348455889 | -0.3574610256653587 | 0.6354628384364371 | 0.3155906000705357 |
| CAC 40 | 0.0786668616186054 | 0.0947251601625148 | 0.1898349298667099 | -0.3864702397048093 | 0.4989869895336169 | 0.2035521847133486 |

## Portefeuilles et statuts

| Portfolio | CAGR | Mean return annualized | Volatility | Max Drawdown | Sharpe | Calmar | Success | Solver status | Status | Risk ceiling | Main Allocation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Minimum Volatility | 0.1269185327877741 | 0.1304936334167043 | 0.1381359353386987 | -0.2633590444941871 | 0.9446754973406734 | 0.4819220582742335 | True | 0 | Optimization terminated successfully |  | Gold 42.4% · CAC 40 38.7% · Dow Jones 16.3% · S&P 500 2.6% |
| Maximum CAGR | 0.4376569920434996 | 0.4707237418658027 | 0.454282971103516 | -0.4677372512931075 | 1.0361905944269707 | 0.9356898361923324 | True | 0 | Optimization terminated successfully |  | Apple x1.5 73.5% · Nasdaq 100 x2 26.5% |
| Maximum Sharpe | 0.2569486131898903 | 0.2517289611205574 | 0.2011273368299016 | -0.2359272492126741 | 1.251589988154871 | 1.0891010430010426 | True | 0 | Optimization terminated successfully |  | Gold 56.8% · Apple x1.5 25.3% · CAC 40 11.6% · Nasdaq 100 x2 6.4% |
| Prudent | 0.1725620158912543 | 0.172396062318325 | 0.1500000000007422 | -0.2403322356307176 | 1.14930708211648 | 0.7180144412936948 | True | 0 | Optimization terminated successfully | 0.15 | Gold 48.7% · CAC 40 30.1% · S&P 500 11.5% · Apple x1.5 9.6% |
| Modéré | 0.2554736015945527 | 0.2503142783830828 | 0.2000000000091245 | -0.2357484431698709 | 1.251571391858314 | 1.083670365578909 | True | 0 | Optimization terminated successfully | 0.2 | Gold 56.7% · Apple x1.5 25.1% · CAC 40 12.0% · Nasdaq 100 x2 6.2% |
| Dynamique | 0.3551418839125241 | 0.3526488079992413 | 0.3000000000003046 | -0.3119133799662732 | 1.1754960266629442 | 1.1385913741530584 | True | 0 | Optimization terminated successfully | 0.3 | Apple x1.5 44.0% · Gold 38.1% · Nasdaq 100 x2 17.9% |
| Agressif | 0.4145751826051081 | 0.4311438085457771 | 0.4000000000004333 | -0.412476343988622 | 1.0778595213632751 | 1.005088385423975 | True | 0 | Optimization terminated successfully | 0.4 | Apple x1.5 60.5% · Nasdaq 100 x2 26.8% · Gold 12.6% |
| Très agressif | 0.4376569920434996 | 0.4707237418658027 | 0.454282971103516 | -0.4677372512931075 | 1.0361905944269707 | 0.9356898361923324 | True | 0 | Maximum CAGR reached; unused risk allowance | 0.5 | Apple x1.5 73.5% · Nasdaq 100 x2 26.5% |

## Poids complets

| Portfolio | Apple x1.5 | Nasdaq 100 x2 | S&P 500 | Dow Jones | CAC 40 | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| Minimum Volatility | 4.805371683185928e-17 | 0.0 | 0.0258804498667192 | 0.1628930156056439 | 0.3868375908754305 | 0.4243889436522062 |
| Maximum CAGR | 0.7347461780848664 | 0.2652538219151336 | 8.267210971791423e-17 | 0.0 | 0.0 | 0.0 |
| Maximum Sharpe | 0.252941786204562 | 0.0635210469329088 | 7.286759747432727e-18 | 6.96468605715112e-17 | 0.1159529871689093 | 0.5675841796936197 |
| Prudent | 0.0960135884229919 | 1.4815903266678196e-17 | 0.1154853233058196 | 1.3058767828312632e-16 | 0.301034564285872 | 0.4874665239853162 |
| Modéré | 0.2511116017064527 | 0.0616986137823935 | 0.0 | 1.5415999640028266e-18 | 0.1203828530911059 | 0.5668069314200479 |
| Dynamique | 0.4397554083335234 | 0.17929016338756 | 0.0 | 3.247286091756572e-17 | 2.6577088088202165e-17 | 0.3809544282789165 |
| Agressif | 0.6052681011877346 | 0.2682739443359071 | 5.747224426238833e-17 | 4.820485678647904e-17 | 0.0 | 0.1264579544763581 |
| Très agressif | 0.7347461780848664 | 0.2652538219151336 | 8.267210971791423e-17 | 0.0 | 0.0 | 0.0 |

## Contrôles numériques

```json
{
  "portfolio_weight_sums": {
    "Minimum Volatility": 1.0,
    "Maximum CAGR": 1.0,
    "Maximum Sharpe": 1.0,
    "Prudent": 1.0,
    "Modéré": 1.0,
    "Dynamique": 1.0,
    "Agressif": 1.0,
    "Très agressif": 1.0,
    "Frontier 0": 1.0,
    "Frontier 1": 1.0,
    "Frontier 2": 1.0,
    "Frontier 3": 1.0,
    "Frontier 4": 1.0,
    "Frontier 5": 1.0,
    "Frontier 6": 1.0,
    "Frontier 7": 1.0,
    "Frontier 8": 1.0,
    "Frontier 9": 1.0,
    "Frontier 10": 1.0,
    "Frontier 11": 1.0,
    "Frontier 12": 1.0,
    "Frontier 13": 1.0,
    "Frontier 14": 1.0,
    "Frontier 15": 1.0,
    "Frontier 16": 1.0,
    "Frontier 17": 1.0,
    "Frontier 18": 1.0,
    "Frontier 19": 1.0,
    "Frontier 20": 1.0,
    "Frontier 21": 1.0,
    "Frontier 22": 1.0,
    "Frontier 23": 1.0,
    "Frontier 24": 1.0,
    "Frontier 25": 1.0,
    "Frontier 26": 1.0,
    "Frontier 27": 1.0,
    "Frontier 28": 1.0,
    "Frontier 29": 0.9999999999999999,
    "Frontier 30": 1.0,
    "Frontier 31": 1.0,
    "Frontier 32": 1.0,
    "Frontier 33": 1.0,
    "Frontier 34": 1.0,
    "Frontier 35": 1.0,
    "Frontier 36": 0.9999999999999999,
    "Frontier 37": 1.0,
    "Frontier 38": 1.0,
    "Frontier 39": 1.0,
    "Frontier 40": 1.0,
    "Frontier 41": 1.0,
    "Frontier 42": 1.0,
    "Frontier 43": 0.9999999999999999,
    "Frontier 44": 1.0,
    "Frontier 45": 1.0,
    "Frontier 46": 1.0,
    "Frontier 47": 1.0,
    "Frontier 48": 1.0,
    "Frontier 49": 1.0
  },
  "minimum_portfolio_weight": 0.0,
  "largest_volatility_ceiling_violation": 1.5762224858661966e-11,
  "nonfinite_final_returns": 0,
  "common_observations": 1763,
  "return_observations": 1762,
  "common_start": "2019-09-05",
  "common_end": "2026-10-02",
  "covariance_minimum_eigenvalue": 0.0006830652416355062,
  "solver_attempts": 67,
  "unsuccessful_solver_attempts": 0
}
```

Tous les 67 appels au solveur ont réussi au premier essai, statut 0. Les 8 portefeuilles nommés et les 50 points de frontière sont validés. Tous les poids totalisent 1 à une erreur maximale de 1.110e-16.

## Régression avant/après

Les tests vérifient les anciennes fonctions de levier et de métriques sur des données identiques. Les cellules originales d'optimisation sont aussi exécutées sur les mêmes nouvelles données EUR: 19 validations originales passent. Écart maximal par métrique:

| Metric | Difference |
| --- | --- |
| CAGR | 4.996003610813204e-16 |
| Sharpe | 1.1102230246251563e-15 |
| Volatility | 1.942890293094024e-16 |

Changements architecturaux: extraction en modules, paramètres immuables, snapshots vérifiés, notebook léger et tests. Les formules historiques sont conservées. L'évaluation de la variance près d'une couverture parfaite est stabilisée sans changer sa définition. La dérivée log-growth utilise un plancher fini 1e-15 aux frontières de faillite; les CAGR rapportés restent exacts.

Changements méthodologiques: ^GSPC remplacé par ^SP500TR; ^NDX/^DJI/^FCHI remplacés explicitement par QQQ/DIA/CACC.PA avec revenus inclus; conversion USD/EUR en amont; FX non soumis au levier; calendrier commun modifié. Les données CACC.PA précédant la création de part indiquée par Amundi au 2019-09-05 sont exclues, tout en conservant les données brutes. La date de début commune est donc 2019-09-05. Aucune égalité avec les anciens résultats mixtes prix/devises n'est exigée.

## Fichiers

Créés: README.md, requirements.txt, requirements-dev.txt, pyproject.toml, .gitignore, run.py, scripts/check_regression.py, notebooks/portfolio_analysis.ipynb, src/portfolio_lab/*.py, tests/*.py et outputs/*.csv/json/md/png/log/ipynb. Notebook original déplacé sans réécriture vers notebooks/archive/draft.ipynb. Aucun fichier utilisateur supprimé. Environnement .venv et caches .cache/tmp locaux ignorés.

Hypothèses: 252 observations/an, 365.25 jours/an pour CAGR, taux sans risque 0, long-only avec rééquilibrage aux observations communes, aucun remplissage des cours, levier quotidien natif et FX sans levier, frais/financement/taxes exclus du modèle synthétique. Limites non résolues: approximations ETF des benchmarks TR absents, données ajustées fournisseur non auditées, historique/ascendance CACC.PA incohérents avant exclusion, GC=F non assimilable à un investissement futures TR, cours de clôture non synchronisés, optimisation historique sans validation hors échantillon.
