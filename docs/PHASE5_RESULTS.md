# Phase 5 results (exploratory; 2013-2019 previously exposed)

Plan: docs/PHASE5_RESEARCH_PLAN.md, registered (`20261011T213838Z-plan`) after the investor decision
(`20261011T213837Z-decision`, informed by validation results) and before any phase-5 computation.
Registry after the phase: 22 distinct evaluations, 202 distinct strategy-level evaluations (the
strategy count is conservative: an unchanged benchmark under a different window counts again).
The unleveraged baseline repeats the phase-4 "Nasdaq 100 sans levier" evaluation except for the new
ERC policy. A fingerprint defect (field added later) was found and corrected; exposure flags are now
recomputed from snapshots (`20261011T215644Z-decision`).

## Risk feasibility without leverage (H3: confirmed)

Per fold, estimated minimum volatility 12.2-14.6% and maximum-growth volatility 20.0-25.0%. The 30%,
40% and 50% ceilings never bind: Dynamique, Agressif and Très agressif are the same Maximum CAGR
portfolio in all 7 folds; they are reported as one boundary portfolio. The 15% Prudent ceiling is
infeasible on the 2001-2012 in-sample window and feasible in every walk-forward fold.

## Stability (training-only diagnostics; rolling 10-year)

| Policy (method) | Target change | Traded turnover | Effective assets | 0/large switches | Rolling vs expanding distance | Bootstrap distance |
|---|---|---|---|---|---|---|
| Minimum Volatility | 1.0% | 2.5% | 2.14 | 0 | 2.3% | 2.4% |
| **ERC (new)** | **0.5%** | **3.0%** | **6.65** | 0 | **2.0%** | **0.7%** |
| Prudent (reference = Bayes-Stein) | 9.8% | 10.1% | 3.04 | 0 | 18.0% | 13.4% |
| Maximum Sharpe (reference) | 7.5% | 9.5% | 2.93 | 0 | 14.5% | 22.0% |
| Maximum Sharpe (Bayes-Stein) | 10.3% | 11.8% | 3.13 | 0 | 16.4% | 24.7% |
| Modéré (reference / Bayes-Stein) | 12.4% | 14.2% / 14.7% | 2.97 / 2.92 | 0 | 23.8% / 23.6% | 19.7% / 19.8% |
| Max CAGR boundary (reference) | 16.6% | 19.0% | 2.27 | 1 | 48.8% | 25.3% |
| Max CAGR boundary (Bayes-Stein) | 16.3% | 18.9% | 2.70 | 3 | 35.8% | 26.4% |
| Constrained equal weight | 0% | 3.2% | 6.90 | 0 | - | - |

**H1 (Bayes-Stein drift more stable): not supported.** Bootstrap dispersion did not fall (Maximum
Sharpe 22.0% -> 24.7%, boundary 25.3% -> 26.4%); only the boundary portfolio's rolling/expanding
distance fell (48.8% -> 35.8%), while its zero/large switches rose (1 -> 3). Prudent and Modéré are
(nearly) unchanged. Mechanism: Bayes-Stein shrinks every mean toward one common value,
`mu~ = (1 - w) mu + w c`. For fully invested weights `mu~'x = (1 - w) mu'x + w c`, an increasing affine
transform of the objective, so a portfolio maximizing expected growth under a *binding* volatility
ceiling is unchanged; only problems where risk is free (Maximum Sharpe through its intercept, the
unconstrained maximum-growth portfolio through the variance term) move, and the ranking noise of the
means remains. Shrinkage toward a common mean does not address the instability observed.

**H2 (ERC): supported.** ERC is the most stable policy measured: bootstrap 0.7%, fold-to-fold 0.5%,
window distance 2.0%, 6.65 effective assets (Minimum Volatility: 2.14). Gold is held at its 10% cap
(binding); the other weights are 11-19% each (Apple 11%, Nasdaq 100 13%, S&P 500 14%, Dow Jones 15%,
MSCI World 19%, Coca-Cola 19%). Four of the seven assets are overlapping US large-cap equity series,
so ERC equalizes risk across series, not across economic exposures.

The unleveraged boundary portfolio is unstable: Nasdaq 100 goes 50%, 48%, 5%, 15%, 60%, 60%, 60%
and Coca-Cola 0%, 2%, 45%, 45%, 0% across folds.

## Performance (exploratory, net of costs, EUR, 2013-2019)

| Policy | CAGR | Volatility | Max drawdown | vs constrained EW | Sign flips when one year removed | Expanding-window CAGR |
|---|---|---|---|---|---|---|
| Minimum Volatility | 11.7% | 11.4% | -16.0% | -4.3% | 0 (always negative) | 11.7% |
| Prudent | 14.9% | 12.4% | -16.9% | -1.6% | 0 (always negative) | 12.6% |
| **ERC** | 15.8% | 13.2% | -17.1% | -0.8% | 0 (always negative, -0.5 to -0.9%) | 15.6% |
| Equal weight (unconstrained) | 16.0% | 13.1% | -17.4% | -0.7% | - | 16.0% |
| **Constrained equal weight** | 16.7% | 13.7% | -17.6% | 0 | - | 16.7% |
| Maximum Sharpe (reference) | 17.8% | 15.7% | -20.1% | +1.0% | 1 (without 2019) | 17.4% |
| Maximum Sharpe (Bayes-Stein) | 16.7% | 14.8% | -18.6% | 0.0% | - | 17.3% |
| Modéré | 18.9% | 16.2% | -20.8% | +1.9% | 1 (without 2019) | 16.9% |
| Max CAGR boundary (reference) | 21.9% | 18.5% | -26.9% | +4.5% | 0 (+2.6% to +5.8%) | 18.0% |
| Max CAGR boundary (Bayes-Stein) | 20.3% | 17.4% | -25.4% | +3.1% | 0 | 17.6% |
| MSCI World | 12.9% | 12.9% | -22.2% | -5.6% | - | 12.9% |

Realized volatility was below the training estimate in 6 of 7 years for every policy, ERC included.

Universes (reference method; Sans Apple and Sans Or are new evaluations, Sans Nasdaq 100 repeats phase 4):
Sans Apple - Maximum Sharpe 16.8% / 14.2% / -14.6%, boundary 20.2% / 16.8% / -19.8%, constrained EW
14.9% / 12.9% / -16.2%; Sans Nasdaq 100 - boundary 16.6% / 16.9% / -24.9%, constrained EW 15.9%;
Sans Or - boundary 23.3% / 18.9% / -26.9%, constrained EW 18.3% / 15.0% / -18.4%.

## Reading

* ERC trades about 0.9 point of CAGR against the constrained equal weight (and 0.5 point of
  volatility) for no stability gain over it: both are already stable. Against Minimum Volatility it
  adds 4.1 points of CAGR for 1.7 points of volatility with similar stability and three times the
  effective diversification.
* Policies that beat the constrained equal weight (Maximum Sharpe, Modéré, boundary) do so with
  weights that are poorly determined (bootstrap 20-25%) and window-sensitive (15-49%); only the
  boundary portfolio's lead survives removing any single year, and it shrinks from +4.5% to about
  +1.1% under the expanding window (18.0% vs 16.7%).
* No method demonstrated a credible improvement in stability *and* growth over the constrained equal
  weight on this reused interval.
