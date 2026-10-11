# Phase 4 results (exploratory; 2013-2019 previously exposed)

Plan: docs/PHASE4_RESEARCH_PLAN.md, registered as `20261011T204514Z-plan` before any computation.
Registry after the phase: 16 distinct evaluations (15 before + "Nasdaq 100 sans levier"). All figures
are net of costs, EUR, rolling 10-year walk-forward 2013-2019 unless stated. None is a confirmation.

## Q1 Allocation stability (complet universe)

| Policy | Mean target change | Mean traded turnover | Mean max weight | Effective assets | Zero/large switches | Mean x2 weight |
|---|---|---|---|---|---|---|
| Maximum Sharpe | 5.7% | 8.6% | 44% | 2.8 | 0 | 3% |
| Minimum Volatility | 1.0% | 2.5% | 61% | 2.1 | 0 | 0% |
| Prudent (15%) | 8.8% | 9.0% | 45% | 3.0 | 0 | 0% |
| Modéré (20%) | 9.1% | 11.5% | 43% | 3.0 | 1 | 4% |
| Dynamique (30%) | 3.9% | 6.3% | 44% | 2.8 | 0 | 44% |
| Agressif / Très agressif | 8.3% | 11.7% | 61% | 2.0 | 1 (2019: Apple 40% -> 0%, x2 -> 100%) | 61% |
| Constrained equal weight | 0% | 4.3% | 15% | 6.9 | 0 | 15% |

Fold-to-fold target changes are moderate for all policies; the Apple cap (40%) and Gold cap (10%)
bind in most folds (persistent holdings: Apple and Coca-Cola for Maximum Sharpe/Modéré; MSCI World and
Coca-Cola for Minimum Volatility/Prudent; Apple and Nasdaq 100 x2 for Dynamique).

## Q2 Training-only bootstrap (40 resamples per fold, seed 0, 0 failures)

Mean distance of refitted weights to the fold's estimate: Minimum Volatility 2.4%; Prudent 12.7%;
Modéré 18.1%; Dynamique 19.0%; Maximum Sharpe 20.7%; Agressif 23.4%. Typical 5-95% ranges: Maximum
Sharpe Coca-Cola 5-60%, MSCI World 0-34%; Dynamique Nasdaq x2 8-55%; Agressif Nasdaq x2 9-77%.
Interpretation: apart from Minimum Volatility, the weights are poorly determined by ten years of data
even when consecutive folds look similar: low fold-to-fold change is not evidence of well-identified
weights (overlapping windows share nine of ten years).

## Q3 Rolling vs expanding

Mean weight distance: Minimum Volatility 2%, Maximum Sharpe 14%, Prudent 17%, Modéré 20%, Dynamique 37%,
Agressif 53%. CAGR rolling/expanding: Dynamique 29.7%/19.1%, Agressif 32.5%/19.1%, Maximum Sharpe
18.2%/17.4%, Minimum Volatility 11.7%/11.7%. Mean x2 weight: Dynamique 44% vs 8.5%. Cause (development
data): Nasdaq 100 x2 lost 67% (2001) and 73% (2002) in EUR; its CAGR is -10.3%/yr over 2001-2012 but
+11.4%/yr over 2003-2012. The expanding window keeps the crash, the rolling window drops it from the
2013 fold on. The aggressive profiles' allocation therefore depends on whether one historical episode
is in the sample: weight instability with a clear cause, not noise.

## Q4 Universes (each vs its own constrained equal weight)

| Universe | Max Sharpe CAGR / vol / MDD | Dynamique CAGR / vol / MDD | Constrained EW CAGR / vol / MDD |
|---|---|---|---|
| Complet | 18.2% / 16.1% / -20.5% | 29.7% / 24.5% / -33.0% | 19.6% / 15.8% / -19.0% |
| Sans Apple | 22.6% / 18.5% / -18.4% | 30.5% / 24.8% / -26.1% | 18.4% / 15.4% / -17.8% |
| Nasdaq 100 sans levier (new) | 17.8% / 15.7% / -20.1% | 21.9% / 18.5% / -26.9% | 16.7% / 13.7% / -17.6% |
| Sans Nasdaq 100 | 17.4% / 15.4% / -18.5% | 16.6% / 16.9% / -24.9% | 15.9% / 13.3% / -18.0% |
| Sans Or | 19.5% / 17.4% / -22.6% | 29.9% / 24.3% / -31.8% | 21.5% / 17.4% / -20.7% |

Hypothesis Q4c (registered): confirmed for volatility and drawdown (aggressive profiles: vol 24.5-28.1%
-> 18.5%, MDD -33.0/-36.6% -> -26.9%) and for unreachable ceilings (Dynamique, Agressif and Très
agressif all become the Maximum CAGR portfolio, estimated vol about 23%). CAGR 29.7-32.5% -> 21.9%.
Without leverage the aggressive weights move more between folds (mean target change 16.6% vs 3.9-8.3%).
Sans Apple: Maximum Sharpe shifts to 36% x2 and aggressive profiles to 66-90% x2. Sans Or: Prudent falls
back to Minimum Volatility in one fold.

## Q6 Year dependence (relative growth vs constrained equal weight)

Dynamique +8.4% and Agressif +10.8%: positive whichever single year is removed (+5.5% / +8.3% without
2019). Maximum Sharpe -1.2% and Modéré -0.4%: the sign flips when 2013 (and 2016 for Modéré) is removed:
no robust difference. Minimum Volatility -6.6% and Prudent -3.8%: negative in every case.

## Q7 Predicted vs realized risk

Realized test-year volatility was below the training estimate in 6 of 7 years for every policy
(Dynamique: 30% ceiling, 23.9% mean realized; Agressif: 34.9% estimated, 27.5% realized). The 2013-2019
period was calmer than the training windows (which contain 2008); ceilings were not binding risk
forecasts. Every policy exceeded its estimate in one year (2018 for Agressif and Dynamique, 2015 for the
others).
