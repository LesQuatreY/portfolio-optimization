# Phase 5 research plan (written before any phase-5 computation)

Central question: *Pour chaque niveau de risque que je suis prêt à accepter, quel portefeuille semble
offrir la meilleure croissance composée à long terme, sans que cette conclusion repose uniquement sur
un heureux hasard historique ?*

## Investor decision recorded first

The investor removed leveraged products from the main research universe **after** seeing 2013-2019
results involving the synthetic Nasdaq 100 x2. The decision is informed by validation results; it is
recorded as such in the registry (`kind: decision`, `informed_by_validation: true`). Leverage code,
tests, documentation and every past registry entry are kept; only `leverage` in research.yaml is
emptied. Removing leverage removes product leverage, not equity concentration: the unleveraged Nasdaq
100 (QQQ), Apple, S&P 500, Dow Jones and MSCI World remain heavily overlapping US large-cap exposures.

## Evidence status

The unleveraged complet universe with the baseline method is exactly the phase-4 variant "Nasdaq 100
sans levier" (registry `20261011T210354Z-110c4b`): its 2013-2019 results are already known. Every
2013-2019 figure in this phase is exploratory, previously exposed evidence. Registry before the phase:
16 distinct evaluations, 150 distinct strategy-level evaluations.

## Selected methods (two families, chosen from Phase 4 *weight* diagnostics, not from performance)

Phase 4 showed that, apart from Minimum Volatility, the fitted weights are poorly identified by ten
years of data (training-only bootstrap distance 13-23%), and that the policies depending most on
expected returns were the least stable. Both selected families attack that source directly.

**A. Expected-return shrinkage applied to the whole frontier (Bayes-Stein drift).**
The existing Jorion (1986) Bayes-Stein estimator (`expected_returns.py`) is reused, not re-implemented:
mean shrunk toward the minimum-variance portfolio's mean with the data-driven intensity
`w = (N+2) / ((N+2) + T (m - mu0)' Sigma^-1 (m - mu0))`, computed on each training window only. Today
it only affects Maximum Sharpe; the frontier and risk profiles maximize historical log growth, which
embeds the raw sample means. New, minimal extension (`growth_drift: estimated`): the growth objective
is evaluated on training returns re-centred on the configured expected returns,
`r~_t = r_t - m + mu_BS`, so volatility, correlation and the path shape are unchanged and only the
noisy drift is shrunk. Realized metrics still use actual returns. No free parameter.
Addresses: sensitivity of the profiles' and Maximum Sharpe's weights to noisy mean differences.
Caveat: Bayes-Stein was compared once in 2026 on data that included the now-locked holdout (Maximum
Sharpe only; README). Its estimator was fixed then and is not modified.

**B. Risk-based allocation: equal risk contribution (ERC) under the investor bounds.**
Uses the training covariance only (Ledoit-Wolf), no expected returns. Unconstrained: the unique
long-only portfolio with `w_i (Sigma w)_i = w' Sigma w / n` (Spinu's convex formulation). When the
investor bounds bind (Gold <= 10%, Apple <= 40%), exact ERC is infeasible; the policy is then the
bounded portfolio minimizing the squared deviations of relative risk contributions from 1/n
(deterministic SLSQP from the projected unconstrained solution). No free parameter. One portfolio,
not a frontier. Caveat: risk is equalized across *assets*, not economic exposures, so overlapping US
equity series jointly receive a large share of risk.

Not selected: turnover penalty (addresses fold-to-fold changes, which were already moderate, and needs
a penalty parameter that cannot be credibly chosen on 10-year inner samples); concentration penalty
(caps already bind and it needs a parameter).

## Fixed settings

Unchanged from phase 4 except `leverage: {}`: rolling 10-year walk-forward 2013-2019, 1-session lag,
annual rebalancing, 10 bp, Ledoit-Wolf, historical point-in-time rates, index holding costs, caps
Gold <= 10% and Apple <= 40%, risk profiles 15/20/30/40/50% (unchanged; infeasible ceilings are
reported, never replaced). Rolling window primary, expanding a diagnostic.

## Planned evaluations (limited)

1. Baseline (sample drift) + ERC on the unleveraged complet universe, rolling and expanding.
2. Method A (Bayes-Stein drift) on the same universe, rolling and expanding.
3. Baseline method on the unleveraged universe variants Sans Apple, Sans Nasdaq 100, Sans Or (ERC and
   method A not run on variants, to limit looks).
4. Training-only stationary bootstrap (40 resamples per fold, seed 0) for baseline, A and ERC.

## Hypotheses (registered before evaluation)

* H1 (A): compared with the sample drift, Bayes-Stein drift lowers the training-bootstrap weight
  dispersion and the rolling-vs-expanding weight distance of Maximum Sharpe and of the feasible risk
  profiles. The effect on CAGR, volatility and drawdown is not predicted.
* H2 (B): ERC has a bootstrap dispersion and fold-to-fold target change of the same order as Minimum
  Volatility and well below the profiles, with more effective assets than Minimum Volatility; its
  realized volatility lies between Minimum Volatility and the constrained equal weight.
* H3 (universe): without leverage, ceilings of 30% and above are unreachable (the profiles coincide with
  Maximum CAGR); this is reported as infeasibility, not as distinct portfolios.

No composite score; no method is selected by its 2013-2019 CAGR; disappointing outcomes are reported.
