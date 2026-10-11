# Phase 4 research plan (written before any phase-4 result was computed)

Central question: *Pour chaque niveau de risque que je suis prêt à accepter, quel portefeuille semble
offrir la meilleure croissance composée à long terme, sans que cette conclusion repose uniquement sur
un heureux hasard historique ?*

## Status of the evidence

The baseline configuration (`df1848a08ea5`: research.yaml of phase 3) and the four universe variants
(complet, sans Apple, sans Nasdaq 100, sans Or) plus the expanding-window check were already evaluated
on 2013-2019 in phase 3. 15 distinct configurations had been evaluated before this phase. Every
2013-2019 figure below is therefore **previously exposed exploratory evidence**, not confirmation.
Only one variant is new (Q4b). Weight-stability diagnostics are new analyses of the same runs; the
training-only bootstrap uses no validation observation.

## Fixed settings (unchanged, not tuned)

Rolling 10-year window, test years 2013-2019, annual rebalancing, 1-session decision lag, 10 bp costs,
Ledoit-Wolf covariance, sample-mean expected returns, risk profiles 15/20/30/40/50% estimated
volatility, investor caps Gold <= 10% and Apple <= 40%, historical point-in-time rates, index holding
costs. Primary investable reference: constrained equal weight of each universe; context: MSCI World.

## Questions

* **Q1 Allocation stability (baseline, rolling).** Per policy: target-weight change between consecutive
  folds `D_t = 0.5 * sum_i |w_i,t - w_i,t-1|`; traded turnover against drifted weights (separately);
  maximum single weight, HHI, effective number of assets per fold; largest changes; persistent holdings;
  zero/large switches.
* **Q2 Weight sensitivity to the training sample (training data only).** For each fold, 40 stationary
  bootstrap resamples of the fold's training returns (whole dates resampled jointly; expected block
  length = mean Politis-White length of the training returns; seed 0). Each resample is refitted with
  the unchanged policy. Reported: mean distance `0.5 * sum_i |w_b - w_hat|` to the fold's point
  estimate, and per-asset 5th-95th percentile weight ranges. No test-year data is used.
* **Q3 Estimation-window sensitivity.** Rolling (primary) vs expanding (check): per year and policy,
  weight distance `0.5 * sum_i |w_roll - w_exp|`, Nasdaq x2 weight, concentration, and the OOS metrics
  (already exposed). Performance sensitivity and weight sensitivity are reported separately.
* **Q4 Universes (one variable at a time).** Variants on the same prices, dates, costs and caps:
  (a) complet; (b) sans Apple (`Apple` ineligible); (c) **Nasdaq 100 sans levier** - NEW: the synthetic
  `Nasdaq 100 x2` is replaced by the unleveraged `Nasdaq 100` (QQQ), nothing else changes;
  (d) sans Nasdaq 100 (no direct Nasdaq exposure at any leverage; already exposed);
  (e) sans Or (`Gold` ineligible). Each universe is compared with its own constrained equal weight.
  Infeasible risk targets are reported, never replaced.
* **Q5 Leverage dependence.** From Q1/Q4: Nasdaq x2 weight per profile and fold; (a) vs (c).
* **Q6 Year dependence.** Leave-one-year-out relative growth vs the constrained equal weight.
* **Q7 Predicted vs realized risk.** Training ex-ante estimated volatility vs realized test-year volatility.

## Descriptive conventions (fixed now; counting rules, not quality thresholds)

* A **zero/large switch**: an asset at <= 1% in one fold and >= 20% in the next, or the reverse.
* A **persistent major holding**: >= 10% in every fold.
* No composite score combining growth and stability is computed. No candidate is selected by its
  2013-2019 CAGR. The assessment is a transparent multi-criteria reading.

## Hypothesis for the new variant (Q4c)

Replacing the synthetic Nasdaq 100 x2 by the unleveraged Nasdaq 100 lowers the realized volatility and
drawdown of the aggressive profiles (Dynamique, Agressif, Très agressif) and makes some volatility
ceilings unreachable (Maximum CAGR then binds); the effect on CAGR is not predicted.
