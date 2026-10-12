# Phase 7B results (exploratory; 2013-2019 previously exposed)

Plan registered before evaluation: `20261012T103528Z-plan` (docs/PHASE7B_RESEARCH_PLAN.md).
Decisions: EM universe and Coca-Cola cap (`20261012T103002Z-decision`, two entries sharing one id,
distinguished by label; see `20261012T103527Z-decision-fdea53`), weekly covariance (`20261012T103003Z-decision`).
A = 7 assets (phase 1-6 universe), B = 8 assets (+ MSCI Emerging Markets NETR); both with Apple <= 40%,
Gold <= 10%, Coca-Cola <= 10%. Boundary = Maximum CAGR = Dynamique/Agressif/Très agressif (ceilings
never bind in any fold). Risk distance = sqrt(dw' Sigma dw), Sigma fixed 2001-2012 weekly Ledoit-Wolf.

## Integration checks

* MSCI EM NETR 891800 enters the common calendar without loss: 4,722 sessions, 2000-12-29 to
  2019-12-31 (unchanged). 190 EM sessions lacked a same-day FX fixing (previous fixing used, as for
  MSCI World). EM holding cost 0.20%/yr, no withholding adjustment (NETR).
* Weekly sampling: last common close of each W-FRI week, x52; tests cover holidays, missing weeks,
  annualization scale, asynchrony removal and the optimizer using the same Sigma everywhere.

## Training-only diagnostics (2001-2012 and fold training windows)

* EM correlation daily -> weekly: MSCI World 0.70 -> 0.80, S&P 500 0.49 -> 0.69, Nasdaq 100 0.43 ->
  0.64, Apple 0.29 -> 0.42, Gold 0.08 -> 0.09. All other pairs move by <= 0.05 (US-US pairs barely move).
* Weekly PCA (8 assets): PC1 (equity, incl. EM loading 0.35) 61.5%, PC2 (Gold) 13.0%, PC3 (Apple vs
  Coca-Cola) 10.4%, PC4 (Apple vs EM) 7.4%. EM is a partly distinct, equity-dominated risk.
* EM mean 2001-2012: 11.4%/yr, t = 1.8; versus the constrained equal weight +1.2%, t = 0.2 (noise).
* Feasible estimated volatility (B-weekly): minimum 13.3-15.3%, maximum growth 20.9-23.7%. The Coca-Cola
  cap raised the minimum (phase 6: 12.2-14.6%), so Prudent (15%) is infeasible in 2 folds (2016,
  2017) and falls back to Minimum Volatility.
* Risk contributions (dev covariance, weekly): constrained equal weight EM 13.2% (daily 9.3%);
  ERC weights EM 14.8% (daily 18.8%).

## Estimator effect (daily -> weekly, same universe)

| EM target weight by fold, 2013..2019 | daily | weekly |
|---|---|---|
| Minimum Volatility | 14, 11, 12, 13, 14, 16, 18% | 0, 0, 2, 0, 0, 2, 5% |
| Prudent | 24, 22, 23, 14, 15, 13, 21% | 7, 9, 9, 0, 0, 2, 4% |
| ERC | 17-18% | 14-15% |
| Maximum Sharpe | 47, 40, 39, 11, 4, 0, 11% | 40, 28, 10, 0, 0, 0, 0% |
| Boundary | 50, 50, 0, 0, 0, 0, 0% | identical (no covariance in the objective) |

H1 supported: with daily data EM looks like a diversifier (asynchrony), and risk-based policies hold
11-24% of it; with weekly data they hold almost none. The boundary does not use the covariance and is
unchanged. Out of sample (exposed), weekly risk-based policies did slightly better: B Minimum Volatility
12.7% vs 10.8% CAGR, Prudent 14.1% vs 13.0%, similar volatility. A small, descriptive effect.

## Universe effect (A-weekly -> B-weekly)

### Stability

| Policy | fold-to-fold instrument / risk | bootstrap risk | rolling vs expanding risk | effective assets |
|---|---|---|---|---|
| Minimum Volatility | 3.4/0.3% -> 4.1/0.4% | 1.0 -> 1.2% | 1.1 -> 1.4% | 2.39 -> 2.52 |
| ERC | 0.5/0.1% -> 0.5/0.1% | 0.2 -> 0.2% | 0.3 -> 0.3% | 6.61 -> 7.78 |
| Maximum Sharpe | 13.1/1.9% -> 13.9/2.4% | 3.9 -> 4.1% | 3.2 -> 4.8% | 3.48 -> 3.53 |
| Prudent | 16.7/2.6% -> 18.9/2.7% | 3.0 -> 3.3% | 3.2 -> 3.3% | 3.03 -> 3.51 |
| Modéré | 11.5/1.7% -> 12.8/2.4% | 3.0 -> 3.5% | 4.6 -> 5.2% | 3.47 -> 3.49 |
| Boundary | 5.0/1.4% -> 11.7/2.6% (2 zero/large switches) | 3.0 -> 3.6% | 9.4 -> 8.5% | 2.30 -> 2.28 |

H4 supported, and stronger than expected: adding EM does not stabilize any policy. The boundary
becomes less stable: EM 50% in 2013-2014 then 0% (a corner switch of half the portfolio driven by the
2003-2012 EM rally entering and leaving the window). ERC and constrained equal weight stay stable by
construction. H3 supported: growth policies give EM large weights early and zero later.

### Performance (net, EUR, 2013-2019; previously exposed, exploratory)

| Policy | A-weekly CAGR / vol / max DD | B-weekly CAGR / vol / max DD |
|---|---|---|
| Constrained equal weight | 17.0 / 13.9 / -17.9% | 15.2 / 13.1 / -19.5% |
| ERC | 16.4 / 13.6 / -17.5% | 14.7 / 12.9 / -19.3% |
| Minimum Volatility | 12.7 / 11.8 / -17.1% | 12.7 / 11.8 / -17.3% |
| Prudent | 14.6 / 12.5 / -18.2% | 14.1 / 12.5 / -19.4% |
| Maximum Sharpe | 19.1 / 16.5 / -21.7% | 16.4 / 16.5 / -22.5% |
| Modéré | 20.3 / 17.1 / -23.5% | 17.6 / 16.9 / -23.5% |
| Boundary | 22.7 / 19.1 / -26.9% | 18.0 / 18.7 / -26.9% |
| MSCI World (benchmark) | 12.9 / 12.9 / -22.2% | same |

EM underperformed developed equities over 2013-2019, so every policy holding it lost growth, the
boundary most (it held 50% EM in 2013-2014). This is one exposed seven-year period; EM's relative
weakness then is not evidence about its future, and dropping EM because of this table would be
selection on validation results. Versus its own constrained equal weight, B's boundary is +2.4%/yr
(A: +4.9%); leave-one-year-out minimum 0.0% (A: +3.1%).

Estimated vs realized volatility: estimates exceed realized volatility for every policy (e.g. B
boundary 22.1% vs 18.4%, Minimum Volatility 14.6% vs 11.5%), as in previous phases (calm test years).

## Michaud resampling (50 draws), weekly

| | A-weekly ref -> Michaud | B-weekly ref -> Michaud |
|---|---|---|
| Boundary fold risk distance | 1.4 -> 1.2% | 2.6 -> 2.2% |
| Boundary bootstrap risk | 3.0% -> n/a | 3.6 -> 3.2% |
| Boundary rolling/expanding risk | 9.4% -> n/a | 8.5 -> 5.6% |
| Boundary effective assets | 2.30 -> 2.99 | 2.28 -> 3.03 |
| Boundary CAGR / vol / max DD | 22.7/19.1/-26.9 -> 22.1/18.4/-24.7% | 18.0/18.7/-26.9 -> 18.2/17.9/-25.2% |
| Boundary EM weight 2013..2019 | - | 50,50,0,0,0,0,0 -> 45,32,20,10,1,1,1% |

Resampling turns the boundary's EM corner switch into a gradual decline and lowers every stability
measure moderately, as in phase 6; it adds no information about EM's expected return.

## Cap effect (descriptive)

Phase 6 reference (no Coca-Cola cap, daily): boundary 21.9%, constrained equal weight 16.7%.
A-daily (Coca-Cola <= 10%): boundary 22.7%, constrained equal weight 17.0%. The cap removed the
boundary's Nasdaq <-> Coca-Cola switches (phase-6 boundary fold risk distance 4.7%, A-daily 1.4%):
the stability gain came from an investor constraint declared after results were seen.

## Governance

All runs are recorded by the robustness notebook (`kind` universe_variant / estimator_variant /
method_variant, category pre-registered, notes citing the plan); the A-weekly Michaud run, first
computed in an analysis script, was recorded separately (`20261012T105236Z-ef1649`). Registry after the
phase: 34 distinct evaluations (phase 6: 26), 327 distinct strategy-level evaluations. Two entries share
the id `20261012T105042Z-74b6e5` (baseline and the identical 8-asset universe variant, same second and
same fingerprint); exposure is keyed by id and label, so the rerun is correctly flagged. The regression
script now pins the archived engine's daily covariance explicitly. No winner, no composite score, no
parameter search. Whether to keep EM is an investor decision about economic exposure, not a
validation-period optimization.
