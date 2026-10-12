# Phase 6 results (exploratory; 2013-2019 previously exposed)

Plan registered before evaluation: `20261011T230504Z-plan` (docs/PHASE6_RESEARCH_PLAN.md).
Instrument distance = 0.5 * sum|dw|; risk distance = sqrt(dw' Sigma dw) with the fixed 2001-2012
Ledoit-Wolf covariance (annualized tracking volatility). Boundary = Maximum CAGR portfolio, identical to
the 30/40/50% profiles in every fold (ceilings never bind without leverage).

## Stability (training-only diagnostics, rolling 10-year), instrument / risk distance

| Policy | Reference | Anchored (BL, ERC) | Resampled (Michaud 50) |
|---|---|---|---|
| Fold-to-fold, Maximum Sharpe | 7.5% / 1.8% | 10.6% / 1.8% | 9.9% / 1.8% |
| Fold-to-fold, Modéré | 12.4% / 2.9% | 15.4% / 2.7% | 12.9% / 2.7% |
| Fold-to-fold, boundary | 16.6% / 4.7% | 1.7% / 0.6% | 9.1% / 2.0% |
| Bootstrap, Maximum Sharpe | 22.0% / 5.1% | 20.5% / 4.4% | 20.1% / 4.2% |
| Bootstrap, Modéré | 19.7% / 4.2% | 18.4% / 3.3% | 18.4% / 3.7% |
| Bootstrap, boundary | 25.3% / 6.5% | 11.9% / 3.2% | 20.3% / 4.6% |
| Rolling vs expanding, boundary | 48.8% / 9.6% | 9.8% / 3.1% | 22.4% / 3.7% |
| Effective assets, boundary | 2.27 | 1.99 | 3.26 |
| Effective assets, Maximum Sharpe | 2.93 | 4.06 | 3.53 |

References: ERC 0.5% / 0.1% fold-to-fold, bootstrap 0.7% / 0.1%; Minimum Volatility 1.0% / 0.2%,
bootstrap 2.4% / 0.5%.

* Instrument distances are 4-6 times larger than risk distances: much of the weight movement is
  substitution among correlated series (overlap matters for weight stability), but the boundary's
  Nasdaq <-> Coca-Cola switches (12% risk distance) are genuine exposure changes.
* H1 (anchored) partly supported: the boundary becomes very stable, but only because the equilibrium
  prior rewards covariance with the anchor, so maximum growth is always Apple 40% (cap) + Nasdaq 100
  60% (1.99 effective assets): stability by assumption, a concentrated high-beta rule. Bootstrap risk
  distances fall moderately for the other policies; their fold-to-fold instrument changes rise.
* H2 (resampled) partly supported: the boundary is diversified (Apple 35-40%, Nasdaq 21-51%, Coca-Cola
  9-31%, Gold 1-7%), fold changes and window sensitivity roughly halve, bootstrap dispersion falls
  modestly; Maximum Sharpe and Modéré are almost unchanged.

## Performance (net, EUR, 2013-2019; previously exposed, exploratory)

| Policy | CAGR | Volatility | Max DD | vs constrained EW | Expanding CAGR |
|---|---|---|---|---|---|
| Boundary, reference | 21.9% | 18.5% | -26.9% | +4.5% (min +2.6% one year removed) | 18.0% |
| Boundary, anchored | 23.5% | 19.9% | -26.9% | +5.9% (min +4.2%) | 21.9% |
| Boundary, resampled | 20.7% | 17.3% | -22.0% | +3.4% (min +1.7%) | 19.0% |
| Maximum Sharpe ref / anchored / resampled | 17.8 / 17.6 / 17.6% | 15.7 / 15.4 / 15.1% | -20.1 / -18.9 / -18.7% | +1.0 / +0.8 / +0.7% | 17.4 / 18.7 / 17.7% |
| Modéré ref / anchored / resampled | 18.9 / 18.7 / 18.4% | 16.2 / 16.2 / 15.7% | -20.8 / -21.5 / -18.8% | +1.9 / +1.8 / +1.5% | 16.9 / 17.0 / 16.8% |
| Constrained equal weight | 16.7% | 13.7% | -17.6% | - | 16.7% |
| ERC | 15.8% | 13.2% | -17.1% | -0.8% | 15.6% |
| Minimum Volatility | 11.7% | 11.4% | -16.0% | -4.3% | 11.7% |

Higher CAGR goes with higher volatility in every case; no method dominates at matched risk. The
resampled boundary gives up about 1.2 points of CAGR versus the reference boundary for 1.2 points
less volatility, a 5-point smaller drawdown and markedly more stable, more diversified weights.

## Governance and engineering notes

* Registry after the phase: 26 distinct evaluations, 242 distinct strategy-level evaluations
  (conservative count). New in phase 6: only the anchored and resampled methods (rolling and
  expanding); the baseline, expanding check and universe variants repeat phase-5 evaluations. A second
  legacy-field fingerprint issue (`resampling_draws`) was corrected (`20261012T003637Z-decision`).
* Frontier sanity checks (monotonicity, single-asset dominance) now test the optimized objective
  (model growth) instead of realized CAGR: identical ordering with the sample drift, required with an
  estimated drift. Bootstrap worker pools are capped at 4 processes (virtual-memory exhaustion on this
  machine); results do not depend on the worker count. Git output is decoded as UTF-8 in the registry.
