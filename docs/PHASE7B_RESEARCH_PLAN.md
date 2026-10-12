# Phase 7B research plan (written before any phase-7B evaluation on 2013-2019)

Central question: *Pour chaque niveau de risque que je suis prêt à accepter, quel portefeuille semble
offrir la meilleure croissance composée à long terme, sans que cette conclusion repose uniquement sur
un heureux hasard historique ?*

## Status of the evidence

* The decision to study emerging markets was taken after phases 1-6 results had been viewed
  (`20261012T101845Z-decision`). The 8-asset universe is **not** an untouched hypothesis.
* The Coca-Cola <= 10% cap was confirmed by the investor after results had been viewed
  (`20261012T103002Z-decision`); it changes the 7-asset universe too, so phase-6 numbers are not the
  7-asset baseline any more. They stay in the registry and `docs/PHASE6_RESULTS.md` as history.
* 2013-2019 has been evaluated many times: every number produced here is **exploratory**, recorded as
  a new configuration in the registry, never an independent confirmation. 2020+ stays locked.

## Fixed choices (none tuned on results)

| Item | Value | Basis |
|---|---|---|
| EM series | MSCI Emerging Markets Net Total Return, code 891800, USD -> EUR (DEXUSEU) | phase 7A audit |
| EM holding cost | 0.20% per year, calendar-day accrual; NETR already net of withholding tax | low-cost UCITS MSCI EM tracker fee (assumption) |
| Caps | Apple <= 40%, Gold <= 10%, Coca-Cola <= 10% in every optimized and reference portfolio | investor |
| EM minimum | none (0% is a valid allocation) | protocol |
| Risk model | Ledoit-Wolf on weekly returns (last common close of each W-FRI week, x52) | phase 7A asynchrony finding (`20261012T103003Z-decision`) |
| Expected returns, growth objective, accounting | daily, unchanged | only the risk model changes |
| Walk-forward | rolling 10 years, test 2013-2019, annual rebalance with drift, 1-session lag, 10 bp | phases 1-6 |
| Training bootstrap | 40 replications per fold, seed 0 | phase-4 plan |
| Risk distance | sqrt(dw' Sigma dw), Sigma fixed 2001-2012, weekly Ledoit-Wolf, 8 assets (7-asset results use the same matrix restricted) | phase-6 convention, weekly frequency |

## Comparisons (all pre-specified; one variable at a time)

The 2x2 design separates the estimator effect from the universe effect:

| | daily covariance | weekly covariance |
|---|---|---|
| A: 7 assets (phase 1-6 universe + Coca-Cola cap) | A-daily | A-weekly |
| B: 8 assets (+ Emerging Markets) | B-daily | **B-weekly (main configuration)** |

* Estimator effect: A-daily vs A-weekly (and B-daily vs B-weekly).
* Universe effect: A-weekly vs B-weekly (B-daily is reported to show how much of an apparent EM
  benefit would come from the daily asynchrony bias).
* Cap effect (descriptive only): phase-6 reference (no Coca-Cola cap, daily) vs A-daily.
* Policies in every cell: constrained equal weight, Minimum Volatility, ERC, Maximum Sharpe, Prudent
  (15%), Modéré (20%), and the boundary (Maximum CAGR = Dynamique/Agressif/Très agressif profiles,
  flagged "ceiling not binding").
* Michaud resampling (50 draws): A-weekly and B-weekly only (no other method).
* Diagnostics: expanding-window control and training bootstrap for B-weekly and A-weekly; the daily
  cells get walk-forward only.

## Training-only diagnostics (no test-year data)

Daily vs weekly correlations of EM with the other assets, PCA of the 8 assets, risk contributions of
the constrained equal weight and ERC, feasible volatility range per fold, EM weight per fold and
policy, bootstrap ranges of the EM weight.

## Hypotheses

* H1 (estimator): weekly sampling raises estimated correlations involving EM and Gold (non-US closes),
  so it changes allocations of risk-based policies (ERC, Minimum Volatility) more than growth
  policies, whose allocation is driven by expected returns.
* H2 (diversification): EM adds a partly distinct but equity-dominated risk: PCA PC1 still explains
  most variance; ERC and constrained equal weight hold EM by construction, Minimum Volatility holds it
  only if its weekly covariance makes it useful.
* H3 (allocation): growth policies give EM a small or zero weight in most folds (its 2001-2012 mean is
  not distinguishable from the others); a large EM weight in some folds would be a stability warning,
  not evidence of value.
* H4 (stability): adding EM does not make fold-to-fold risk distances or bootstrap dispersion of the
  high-risk policies materially smaller; the binding caps and noisy means remain the dominant cause.

No decision rule maps results to a choice: there is no composite score, no winner, no parameter
search. The investor decides on the universe with the stability and risk evidence side by side.
