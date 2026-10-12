# Phase 7A data feasibility audit: Emerging Markets and Global Listed Real Estate

Scope: data feasibility only. No optimization, no walk-forward, no change to the research universe.
Every data request used the project providers with an exclusive end of 2020-01-01; return-based
diagnostics use the development period only (before 2013-01-01). The decision to investigate these
exposures was taken after phases 1-6 results had been viewed (registry `20261012T101845Z-decision`):
any expanded universe is not an untouched hypothesis.

## Index identity (verified on msci.com)

* MSCI Emerging Markets = index code **891800** ([MSCI](https://www.msci.com/indexes/index/891800)).
* MSCI ACWI = 892400 ([MSCI](https://www.msci.com/indexes/index/892400)).
* MSCI World Real Estate = **132085** ([MSCI](https://www.msci.com/indexes/index/132085)).
* The `msci-data` package docstring is wrong on two codes: it labels 891800 "ACWI" and 664185
  "Emerging Markets", while 664185 is the MSCI World IMI ([MSCI](https://www.msci.com/indexes/index/664185)).
  Codes must never be taken from that docstring.

## Coverage (verified on provider data, requests ending 2019-12-31)

| Series | Provider | Type | Currency | First observation | Dev obs 2001-2012 | Data quality |
|---|---|---|---|---|---|---|
| MSCI EM NETR (891800) | MSCI | Net TR index | USD | 2000-12-29 | 3,131 (full) | clean: max gap 3 days, 2 moves > 10% (2008) |
| MSCI EM GRTR (891800) | MSCI | Gross TR index | USD | 2000-12-29 | 3,131 (full) | clean; +0.30%/yr over NETR (withholding) |
| EEM | Yahoo | ETF adjusted close | USD | 2003-04-14 | 2,447 | clean; 2 splits absorbed; US-listed (not UCITS) |
| VWO | Yahoo | ETF adjusted close | USD | 2005-03-10 | 1,967 | clean; FTSE EM methodology (South Korea treated as developed) |
| MSCI World Real Estate (132085) | MSCI | Net/Gross TR index | USD | **2016-09-01** | 0 | API serves history only since the GICS Real Estate sector (2016) |
| IWDP.AS | Yahoo | ETF adjusted close | EUR | 2008-01-02 | 1,282 | **defective**: +43% (2011-06-28), +36% (2009-01-06) one-day jumps, 270 zero-volume days |
| RWX (international ex-US RE) | Yahoo | ETF adjusted close | USD | 2006-12-19 | 1,518 | clean; excludes US |
| IFGL (developed ex-US RE) | Yahoo | ETF adjusted close | USD | 2007-11-19 | 1,288 | clean; excludes US |
| RWO (global RE incl. US) | Yahoo | ETF adjusted close | USD | 2008-05-22 | 1,161 | clean; roughly half US |
| VNQI (ex-US RE) | Yahoo | ETF adjusted close | USD | 2010-11-01 | 545 | clean; too short |
| IYR, ICF (US REITs) | Yahoo | ETF adjusted close | USD | 2000-06 / 2001-02 | ~3,000 | clean; US only, not a global proxy |

Not accessible with the project's free tooling: FTSE EPRA Nareit Developed / Global indices (FTSE
Russell licence), S&P / Dow Jones global real-estate indices, and the pre-2016 MSCI real-estate history.

## ETF versus index fidelity (development period, USD)

* EEM vs MSCI EM NETR (2003-04 to 2012-12): annual log-return gap -0.14%; daily correlation 0.62 but
  weekly 0.92. VWO: -0.35%, daily 0.64, weekly 0.93. The daily gap is closing-time asynchrony (index
  closes with Asian markets, ETFs at the New York close), not data error.
* IWDP.AS vs RWO (both EUR, global developed RE, 2008-2012): tracking error 65% and correlation 0.26
  confirm that the Yahoo IWDP.AS history is unusable (catalogue limitation updated).

## Diversification diagnostics (EUR, development period only)

Weekly return correlations (daily in brackets, lower because of asynchronous closes):

| Series (coverage) | MSCI World | Nasdaq 100 | S&P 500 | Gold |
|---|---|---|---|---|
| MSCI EM NETR (2001-2012) | 0.80 (0.70) | 0.64 (0.43) | 0.69 (0.49) | 0.09 |
| RWX, ex-US RE (2007-2012) | 0.89 (0.84) | 0.72 | 0.81 | -0.07 |
| IFGL, ex-US developed RE (2008-2012) | 0.87 (0.81) | 0.73 | 0.82 | -0.11 |
| RWO, global RE (2008-2012) | 0.86 (0.77) | 0.76 | 0.85 | -0.09 |
| IYR, US REITs (2001-2012) | 0.69 (0.63) | 0.52 | 0.72 | -0.03 |

* MSCI EM vs MSCI World: 0.76 (2001-2006) and 0.83 (2007-2012), weekly; vs Gold 0.17 then 0.05.
* EM vs global/ex-US RE: 0.76-0.79 weekly on common dates.
* Annualized weekly volatility (EUR): MSCI EM 22%, RWX 25%, IFGL 25%, RWO 30%.
* Interpretation: emerging markets add a partly distinct equity exposure (lower correlation with the
  Nasdaq 100 and the S&P 500 than those have with each other, 0.91-0.97), but they remain an equity
  exposure strongly tied to global markets. Listed real estate behaved as equity in 2007-2012, a period
  dominated by the financial crisis; no free series measures it before 2006, so its diversification
  value in calmer regimes is not measurable here.

## Handling incomplete history (compared, not implemented)

Rolling 10-year folds need data from 1 January of (test year - 10), preceded by one observation.

| Series start | First feasible rolling fold | Effect |
|---|---|---|
| MSCI EM index 2000-12-29 | 2013 | full protocol |
| RWX 2006-12 | 2017 | 3 of 7 folds |
| IFGL 2007-11 | 2018 | 2 of 7 folds |
| RWO 2008-05 | 2019 | 1 of 7 folds |

* **A. Common shorter history:** a common start in 2008 removes the 2001-2003 bear market, the
  2001-2007 estimation data and every fold before 2019 under the 10-year rule: incompatible with the
  protocol and with the stability diagnostics.
* **B. Index proxy before ETF inception:** sound for emerging markets (MSCI EM NETR covers everything;
  no splice needed if the index itself is used with an implementation cost, exactly as for MSCI World).
  Not possible for global real estate with free data; a splice of US REITs onto a global series would
  change the exposure and is rejected.
* **C. Asset-specific availability:** keeps the protocol; an asset enters a fold only when its full
  training window exists. Global real estate would enter in 2017 (RWX) or later, so universes differ
  across folds, Equal Weight and ERC change composition mid-sample, and stability diagnostics compare
  different universes: comparable only within the folds where the asset exists.

Recommendation: **B for Emerging Markets** (MSCI EM NETR, code 891800, EUR-converted, holding cost of
a UCITS MSCI EM tracker, about 0.18-0.20%/yr, documented as an assumption). **Global listed real
estate cannot be represented over 2001-2019 with the free, reproducible sources available**: either
the investor obtains licensed index history (FTSE EPRA Nareit Developed TR, daily, USD or EUR), or real
estate is studied separately under approach C with an explicitly shorter window - a protocol decision.

## Integration design (for phase 7B, not implemented)

1. Register `MSCI:891800:NETR` in the asset catalogue (Net Total Return, USD, provider msci) and add
   `Emerging Markets: MSCI:891800:NETR` to the universe in a separate, registered universe variant
   first; holding cost in `holding_costs`.
2. Estimate covariance on weekly returns (or apply an explicit asynchrony correction) for any universe
   containing emerging markets: daily data understate EM correlations (0.70 vs 0.80 with MSCI World),
   which would overstate diversification. Pre-register this as an estimation change.
3. Global real estate: only after a data decision (licensed index, or an approach-C study).

## Diagnostics to rerun after the universe changes (no new software needed)

Reuse existing functions only: feasible risk range and ceiling flags (`fit_policies` metadata),
`diagnostics.mean_uncertainty`, `principal_components`, `risk_contributions`, `exposure_changes`,
`stability.training_bootstrap` (with `sigma`), `window_sensitivity`, `research_summary`,
`leave_one_year_out`, constrained equal weight and ERC references.

## Anti-overfitting note

The new assets were chosen after previous results were known; 2013-2019 is already exposed. Any
expanded-universe result on 2013-2019 is exploratory and must be recorded as a new configuration in
the registry; the candidate series were chosen here on coverage, data quality and representativeness,
not on returns.
