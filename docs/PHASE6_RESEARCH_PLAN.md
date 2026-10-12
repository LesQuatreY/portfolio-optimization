# Phase 6 research plan (written after training-only diagnostics, before any phase-6 evaluation)

Central question: *Pour chaque niveau de risque que je suis prêt à accepter, quel portefeuille semble
offrir la meilleure croissance composée à long terme, sans que cette conclusion repose uniquement sur
un heureux hasard historique ?*

## Stage A/B diagnostics (development period 2001-2012 and fold training windows only)

Computed with `portfolio_lab.diagnostics`; no test-year return was used.

* **Feasible risk (phase 5):** estimated minimum volatility 12.2-14.6%, maximum-growth volatility
  20.0-25.0% per fold. Ceilings of 30/40/50% never bind: they are one boundary portfolio.
* **Expected returns are mostly noise.** Relative to the constrained equal weight, the annualized mean
  of Nasdaq 100 has t-statistics between -1.3 and +1.7 across the seven rolling training windows;
  Coca-Cola -1.5 to -0.1; Gold -1.6 to +0.1. Only Apple is clearly different (t 1.9 to 4.0) - and Apple
  is a hindsight choice whose 40% cap binds in every growth portfolio.
* **The growth allocation follows that noise.** Maximum-growth weights: Apple always 40% (cap), Nasdaq
  100 50%, 48%, 5%, 15%, 60%, 60%, 60%, Coca-Cola 0%, 2%, 45%, 45%, 0%. The 2015 and 2017 switches move
  43-45% of the portfolio (instrument distance) and 12% annualized tracking volatility (risk distance,
  fixed 2001-2012 covariance): a genuine change between a defensive and a technology exposure, not a
  substitution between near-identical series.
* **Covariances are stable.** Pairwise correlations move by at most about 0.08 across windows
  (S&P 500/Dow Jones 0.97; Nasdaq 100/S&P 500 0.91-0.93; equity/Gold -0.05 to 0.08).
* **Few independent risks.** Correlation PCA (2001-2012): PC1 (equity) 64%, PC2 (Gold) 14%, PC3 (Apple vs
  Coca-Cola) 10%, the remaining four 12%. With Gold capped at 10%, equities carry about 99% of the
  variance of the constrained equal weight and of ERC.

Conclusion of the diagnosis: high-risk instability comes from expected-return differences that are
indistinguishable from noise, acting on a universe with few independent risk sources and binding caps;
covariance uncertainty is a minor contributor. The remedy must change *relative* expected returns
(phase 5 showed that a common shrinkage cannot) or average away the corner solutions.

## Selected methods (two; no free parameter chosen on results)

**A. Anchored expected returns (Black-Litterman with a neutral equilibrium).**
Prior: equilibrium returns implied by the ERC anchor of the same training window,
`pi = delta * Sigma * w_ERC`, with `delta = m' w_ERC / (w_ERC' Sigma w_ERC)` so that the anchor's implied
return equals its own sample mean (no external market premium). Views: the sample means `m`, with the
sampling uncertainty of each mean, `Omega = diag(Sigma) / T`. Prior uncertainty `tau * Sigma` with the
convention `tau = 1 / T`. Posterior: `mu = (Sigma^-1 + diag(Sigma)^-1)^-1 (Sigma^-1 pi + diag(Sigma)^-1 m)`
(T cancels). Used by Maximum Sharpe and, through `growth_drift: estimated`, by the frontier and the risk
profiles. Why it changes the solution where Bayes-Stein could not: the target differs by asset
(proportional to each asset's covariance with the anchor), and the prior precision `Sigma^-1` is very
large on differences between highly correlated assets, so noise-driven gaps between overlapping US
equity series are pulled toward their equilibrium gaps while the levels follow the data.
Neutral anchor; no investor view (a Nasdaq conviction would be an explicit, separately labelled view).
Limitation: `tau = 1/T` is a convention (equal weight to prior and data scale); not tuned.

**B. Resampled frontier (Michaud).**
Each policy (Maximum Sharpe, risk profiles, Maximum CAGR) is the average of its optimal weights over
R = 50 stationary-bootstrap resamples of the training window (whole dates resampled jointly;
Politis-White block length; deterministic seed from the training end date). Averaging keeps the
investor bounds and full investment (convex set). R is a Monte Carlo size fixed by computation, not a
tuning parameter. Limitation: the averaged portfolio's estimated volatility can sit below its ceiling
(reported); resampling reduces noise but cannot add information.

Not selected: robust mean-variance with an ellipsoidal set built on `Sigma / T` (its penalty is
proportional to portfolio volatility, hence constant at a binding ceiling - the phase-5 trap); turnover
or concentration penalties (need a strength parameter without credible training-only calibration).

## Fixed settings

Unleveraged universe and caps (Gold <= 10%, Apple <= 40%) unchanged; rolling 10-year walk-forward
2013-2019 primary, expanding diagnostic; costs, rates, holding costs, risk profiles unchanged.
New measurement: exposure stability = risk distance with the fixed 2001-2012 Ledoit-Wolf covariance
(development data), alongside instrument distance, for fold-to-fold changes, training-only bootstrap
and rolling vs expanding.

## Planned evaluations (limited, exploratory, 2013-2019 previously exposed)

1. Method A and method B on the main universe, rolling and expanding (one run each).
2. Training-only bootstrap (40 resamples per fold, seed 0) for A and B, compared with the phase-5
   reference, ERC and Minimum Volatility.
3. No universe variants and no other method versions.

## Hypotheses (registered before evaluation)

* H1 (A): compared with the reference (sample drift), anchored returns lower the instrument and risk
  distances of the growth-oriented policies (Maximum Sharpe, Modéré, the Maximum-CAGR boundary) under
  the training bootstrap and between rolling and expanding windows, and raise their effective number of
  assets. The estimated maximum-growth volatility may fall (smaller attainable high-risk range).
* H2 (B): resampling lowers the same distances relative to the reference, with more effective assets,
  and fewer zero/large switches.
* Performance effects are not predicted. No composite score; no winner is selected from 2013-2019.
