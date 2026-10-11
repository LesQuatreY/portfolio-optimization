# Financial data audit (phase 3)

All checks use data before 2020-01-01 only. Decisions are driven by financial correctness and data
quality, never by their effect on portfolio results.

## Gold (`GC=F`) - acceptance criteria, written before the comparison was computed

`GC=F` (Yahoo, COMEX gold, unadjusted) is compared with GLD (SPDR Gold Shares, physically backed,
NAV net of its 0.40% expense ratio, no distributions) in USD over their common history
(GLD starts 2004-11-18). GLD is used as an audit reference only.

The `GC=F` proxy is kept if all of the following hold:

1. Annualized log-return difference `GC=F - GLD` within [-0.5%, +1.5%] per year (GLD pays a 0.40%
   fee that `GC=F` does not; roll carry and settlement timing may add or subtract a little).
2. Correlation of monthly (month-end) returns >= 0.98 (daily returns are compared only for
   diagnosis: COMEX settles at 13:30 ET, GLD closes at 16:00 ET).
3. No cluster of large daily discrepancies attributable to contract rolls: on days where
   `|r_GC - r_GLD| > 1.5%`, the mean signed difference must not exceed 0.25% (an unadjusted
   front-month roll into contango shows up as positive one-day jumps).

If a criterion fails, the proxy is corrected or replaced with a documented series, and the
consequence for the walk-forward history is stated.

### Result (computed after the criteria above were written)

Common history 2004-11-18 to 2019-12-31 (3,794 sessions), USD, pre-2020 snapshots only.

| Check | Result | Criterion | Verdict |
|---|---|---|---|
| Annualized log return GC=F - GLD | +0.42%/yr (GC=F 8.16%, GLD 7.74%) | [-0.5%, +1.5%] | pass: equals GLD's 0.40% fee |
| Monthly return correlation | 0.995 | >= 0.98 | pass |
| Days with daily gap > 1.5% | 84 days, mean signed gap -0.03% (41 up, 43 down) | mean <= 0.25% | pass |

Daily correlation is only 0.876 and the daily gap has a lag-1 autocorrelation of -0.52: the
discrepancies reverse the next day, the signature of settlement timing (COMEX 13:30 ET vs NYSE close
16:00 ET), not of roll jumps. The mean gap by calendar month shows a small sawtooth (positive in most
odd months, when Yahoo rolls into the next active contract) of roughly +/-0.2% per month that nets out
over a year, consistent with a carry jump at each roll and convergence in between.

Snapshot facts (pre-2020): no dividends or splits, 81 missing closes, 42 unchanged closes,
491 zero-volume days concentrated in 2000-2007, no gap longer than 5 days, largest moves on genuine
events (2008-09-17 +9.0%, 2013-04-15 -9.4%).

**Decision.** `GC=F` is kept as a *spot-gold proxy before product fees*: it preserves the 2001+
history required by the 2013 fold (GLD would push the first feasible fold to 2015), and over
2004-2019 it matches a physically backed fund once that fund's fee is accounted for. A holding cost
of 0.25%/yr (physical gold ETC fee, assumption) is deducted to make it investable. No collateral
yield is added: a collateralized futures roller earns roughly spot minus the lease rate, so adding
cash interest to a spot-like series would double count the carry. Limitations: daily covariance with
assets closing later is measured with timing noise; the roll sawtooth adds small spurious intra-year
moves; 2001-2004 quality (zero volume) cannot be cross-checked against GLD.

## Other series

| Series | Facts verified on pre-2020 snapshots | Basis | Treatment |
|---|---|---|---|
| Apple (AAPL) | splits 2000, 2005, 2014 (7:1) and 65 dividends absorbed by Yahoo's adjustment; no artificial jump; extreme moves are genuine (2000-09-29 -51.9%) | adjusted close, gross dividends, no fee | direct holding; taxes out of scope |
| Nasdaq 100 (QQQ) | 2000 split and 63 dividends absorbed | US ETF, gross dividends, 0.20% TER embedded | not buyable by EU retail (PRIIPs): a UCITS tracker costs ~0.1-0.2%/yr more (not modelled) |
| Nasdaq 100 x2 | rebuilt daily from QQQ in USD, then converted | synthetic | fee 0.6% + (L-1) x (historical T-bill + 0.4% spread); QQQ's own 0.20% TER is also inside (slightly conservative) |
| S&P 500 (^SP500TR) | index, no gaps | gross-dividend TR index, no fee | holding cost 0.35%/yr (UCITS TER + withholding suffered by the fund; assumption) |
| MSCI World (NETR) | official MSCI levels from 2000-12-29 | net TR index (MSCI withholding assumptions), no fee | holding cost 0.20%/yr (UCITS TER; assumption); used as asset and passive benchmark |
| Dow Jones (DIA), Coca-Cola (KO) | dividends and KO's splits absorbed | adjusted close, gross dividends | unchanged |
| EUR/USD (FRED DEXUSEU) | 1999-2019, US holidays blank, never filled | USD per EUR noon fixing | unchanged |

Basis decision: index series are turned into investable exposures with explicit holding costs;
stock and ETF adjusted prices are kept pre-tax. Investor taxation (PEA/CTO, treaty credits) is out of
scope and identical across strategies.

## Common history

The intersection of observed sessions is kept. All configured series start by 2000-12-29 (MSCI World
is the binding start), so no history is lost for the 2013 fold; non-synchronous holidays only merge
two sessions into one multi-day return, which loses no compounded information. Alternatives (per-asset
histories, pairwise covariance) would mix different sample periods in one covariance matrix and make
universes incomparable; they are not adopted. Asset histories are never inferred before inception: a
universe whose assets start later fails the strict fold check explicitly.

Non-synchronous closes remain a known estimation bias: over 2001-2012 the daily correlation of MSCI
World with the S&P 500 is 0.913 against 0.958 on weekly returns (MSCI World includes earlier-closing
markets). Gold-equity correlations are near zero at both frequencies. A weekly covariance estimator is
a candidate pre-registered experiment, not a silent change of the baseline.

## Short rates

| Role | Series (FRED) | Point-in-time rule | 2001-2012 mean | 2013-2019 mean |
|---|---|---|---|---|
| Risk-free (EUR, Sharpe) | IR3TIB01EZM156N, OECD euro area 3-month interbank, monthly average | usable from the 1st day of the 2nd following month | 2.52% (2.58% over trading days) | -0.12% |
| Financing base (USD) | DTB3, 3-month T-bill, daily | usable the next calendar day | 1.78% | 0.77% |

The former constant 1.5% overstated the validation-period risk-free rate by about 1.6 points and the
validation-period USD financing cost by about 0.7 points per unit of borrowed exposure.
