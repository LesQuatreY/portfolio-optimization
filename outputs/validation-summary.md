# Targeted CAC Gross Return and notebook configuration update

All changes are inside portfolio-optimization. The leverage, return, metrics and optimization engines retain their existing definitions and numerical tolerances.

## A. Changed files

```text
portfolio-optimization/
  README.md
  notebooks/portfolio_analysis.ipynb
  src/portfolio_lab/config.py
  src/portfolio_lab/data.py
  src/portfolio_lab/reporting.py
  scripts/check_regression.py
  tests/test_reporting.py
  tests/test_notebook_config.py (new)
  outputs/ (regenerated tables, charts, notebook, logs and review)
    effective-config.json (new)
    study-coverage.json (new)
    cac-source-audit.log (new)
    validation-summary.md
```

## B. Exact notebook configuration cell

```python
# Study universe: edit these metadata entries, then Run All.
assets = {'Apple': {'symbol': 'AAPL',
           'instrument': 'Primary US equity',
           'currency': 'USD',
           'return_type': 'Adjusted price',
           'distributions': 'Yahoo split/dividend adjustment; reinvestment proxy before investor tax',
           'limitation': 'Adjusted prices are a vendor proxy, not an independently audited TR index.',
           'reference': ''},
 'Nasdaq 100': {'symbol': 'QQQ',
                'instrument': 'Invesco QQQ ETF; Nasdaq-100 exposure proxy',
                'currency': 'USD',
                'return_type': 'Adjusted price',
                'distributions': 'Yahoo dividend/split adjustments; distributions assumed reinvested',
                'limitation': 'Exact Nasdaq-100 TR unavailable from tested Yahoo ^XNDX. QQQ is an ETF proxy '
                              'with fund fees/tracking differences, not the gross TR benchmark.',
                'reference': 'https://www.invesco.com/qqq-etf/en/home.html'},
 'S&P 500': {'symbol': '^SP500TR',
             'instrument': 'S&P 500 Total Return index',
             'currency': 'USD',
             'return_type': 'Gross Return',
             'distributions': 'Gross dividends reinvested by index methodology',
             'limitation': '',
             'reference': 'https://www.spglobal.com/spdji/en/indices/equity/sp-500/'},
 'Dow Jones': {'symbol': 'DIA',
               'instrument': 'State Street SPDR Dow Jones Industrial Average ETF proxy',
               'currency': 'USD',
               'return_type': 'Adjusted price',
               'distributions': 'Yahoo dividend/split adjustments; distributions assumed reinvested',
               'limitation': 'Exact Dow Jones TR unavailable from tested Yahoo ^DJITR. DIA is an ETF proxy '
                             'with fund fees/tracking differences, not the gross TR benchmark.',
               'reference': 'https://www.ssga.com/us/en/individual/etfs/state-street-spdr-dow-jones-industrial-average-etf-trust-dia'},
 'CAC 40': {'symbol': 'PX1GR.PA',
            'instrument': 'CAC 40 Gross Return Index',
            'currency': 'EUR',
            'return_type': 'Gross Return',
            'distributions': 'Gross dividends reinvested in index levels; no additional dividend adjustment',
            'limitation': 'Yahoo daily history has missing observations; inspect raw valid end and missing '
                          'counts before interpreting coverage.',
            'reference': 'https://live.euronext.com/en/product/indices/QS0011131834-XPAR'},
 'Gold': {'symbol': 'GC=F',
          'instrument': 'Yahoo continuous COMEX gold futures quotation',
          'currency': 'USD',
          'return_type': 'Price Return',
          'distributions': 'No dividends; quoted futures price changes only',
          'limitation': 'Not spot gold or an investable futures total-return index: roll, collateral yield '
                        'and contract stitching are unmodeled.',
          'reference': ''}}

# Leverage entries must reference names present in assets.
leveraged_assets = {"Apple": 1.5, "Nasdaq 100": 2.0}

# Examples (uncomment, adjust metadata, then Run All):
# del assets["Dow Jones"]
# assets["Apple"]["symbol"] = "AAPL"
# assets["MSCI World"] = dict(symbol="IWDA.AS", currency="EUR",
#     return_type="Adjusted price", instrument="iShares Core MSCI World UCITS ETF",
#     distributions="Accumulating ETF; income reinvested within the fund")
# If removing Apple: del assets["Apple"]; del leveraged_assets["Apple"]

config = configure_universe(load_config(project_dir), assets, leveraged_assets)
# Optional study overrides, applied to the same effective configuration:
# config = replace(config, risk_free_rate=0.02, frontier_points=75)
```

Every stage consumes this config. Removing an underlying without removing its leverage entry raises a clear validation error before any download. Metadata is explicit; no previous ticker metadata is silently inherited. The regression script reads the executed effective-config.json export.

## C. Provenance

| Asset | Provider | Symbol | Instrument / benchmark | Return type | Native currency | FX series used | Raw start date | Raw end date | Raw observations | Raw missing observations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Apple | Yahoo Finance | AAPL | Primary US equity | Adjusted price | USD | EURUSD=X | 1980-12-12 | 2026-10-02 | 11544 | 0 |
| Nasdaq 100 | Yahoo Finance | QQQ | Invesco QQQ ETF; Nasdaq-100 exposure proxy | Adjusted price | USD | EURUSD=X | 1999-03-10 | 2026-10-02 | 6935 | 0 |
| S&P 500 | Yahoo Finance | ^SP500TR | S&P 500 Total Return index | Gross Return | USD | EURUSD=X | 1988-01-04 | 2026-10-02 | 9761 | 0 |
| Dow Jones | Yahoo Finance | DIA | State Street SPDR Dow Jones Industrial Average ETF proxy | Adjusted price | USD | EURUSD=X | 1998-01-20 | 2026-10-02 | 7221 | 0 |
| CAC 40 | Yahoo Finance | PX1GR.PA | CAC 40 Gross Return Index | Gross Return | EUR |  | 1987-12-31 | 2015-12-18 | 7076 | 2930 |
| Gold | Yahoo Finance | GC=F | Yahoo continuous COMEX gold futures quotation | Price Return | USD | EURUSD=X | 2000-08-30 | 2026-10-02 | 6548 | 83 |
| Apple x1.5 | Synthetic from Yahoo Finance | AAPL | 1.5x daily reset of Primary US equity | Synthetic daily-reset NAV | USD | EURUSD=X | 2003-12-01 | 2015-12-18 | 3035 | 0 |
| Nasdaq 100 x2 | Synthetic from Yahoo Finance | QQQ | 2x daily reset of Invesco QQQ ETF; Nasdaq-100 exposure proxy | Synthetic daily-reset NAV | USD | EURUSD=X | 2003-12-01 | 2015-12-18 | 3035 | 0 |

CAC 40 uses the actual Gross Return index in EUR, no FX and auto_adjust=False. Synthetic raw rows describe constructed NAV sessions within the study, not the full history of their underlying. Source snapshots and integrity manifests remain preserved.

## D. Common-period result and source audit

```json
{
  "common_start": "2003-12-01",
  "common_end": "2015-12-18",
  "common_observations": 2970,
  "latest_raw_asset_start": "2000-08-30",
  "raw_start_limiting_assets": [
    "Gold"
  ],
  "earliest_raw_asset_end": "2015-12-18",
  "raw_end_limiting_assets": [
    "CAC 40"
  ],
  "latest_eur_asset_start": "2003-12-01",
  "eur_start_limiting_assets": [
    "Apple",
    "Nasdaq 100",
    "S&P 500",
    "Dow Jones",
    "Gold"
  ],
  "start_limiting_series": [
    "EURUSD=X"
  ],
  "fx_start": "2003-12-01",
  "first_common_date_delayed_by_calendar": false
}
```

Previous period: 2019-09-05 through 2026-10-02, 1,763 observations. New period: 2003-12-01 through 2015-12-18, 2,970 observations (+1,207). The beginning moves back because the CAC index history starts in 1987, with no ETF-based exclusion. Gold has the latest raw asset start, 2000-08-30, but EURUSD starts on 2003-12-01 and determines the normalized common start. CAC 40 now limits the end, not the start.

Important source finding: including the live 2026-10-05 session reproduces the user's 7,077 valid values and last date. Keeping missing rows reveals 2,930 NaN closes, with no observed completed-session close after 2015-12-18 and one isolated quote on 2026-10-05. The unchanged exclusive end policy omits that current session. First/last dates alone therefore do not establish continuous usable coverage through 2026. There is no filling, fabricated history or automatic substitute. The study gains earlier coverage but loses recent coverage; a complete current benchmark history requires another source or a vendor correction.

```text
PARAMETERS {'period': 'max'}
COUNT 10007 START 1987-12-31 00:00:00+01:00 END 2026-10-05 00:00:00+02:00
VALID CLOSES 7077 MISSING CLOSES 2930 LAST VALID 2026-10-05 00:00:00+02:00
                                  Close
Date
2026-09-24 00:00:00+02:00           NaN
2026-09-25 00:00:00+02:00           NaN
2026-09-28 00:00:00+02:00           NaN
2026-09-29 00:00:00+02:00           NaN
2026-09-30 00:00:00+02:00           NaN
2026-10-01 00:00:00+02:00           NaN
2026-10-02 00:00:00+02:00           NaN
2026-10-05 00:00:00+02:00  26048.070312
ROWS SINCE 2016 2755
PARAMETERS {'period': 'max', 'end': '2026-10-05'}
COUNT 10006 START 1987-12-31 00:00:00+01:00 END 2026-10-02 00:00:00+02:00
VALID CLOSES 7076 MISSING CLOSES 2930 LAST VALID 2015-12-18 00:00:00+01:00
                           Close
Date
2026-09-23 00:00:00+02:00    NaN
2026-09-24 00:00:00+02:00    NaN
2026-09-25 00:00:00+02:00    NaN
2026-09-28 00:00:00+02:00    NaN
2026-09-29 00:00:00+02:00    NaN
2026-09-30 00:00:00+02:00    NaN
2026-10-01 00:00:00+02:00    NaN
2026-10-02 00:00:00+02:00    NaN
ROWS SINCE 2016 2754
PARAMETERS {'start': '2020-01-01', 'end': '2026-10-05'}
YFPricesMissingError $PX1GR.PA: possibly delisted; no price data found  (1d 2020-01-01 -> 2026-10-05)
```

## E. EUR asset statistics

| Asset | CAGR | Mean return annualized | Volatility annualized | Max Drawdown | Sharpe | Calmar |
| --- | --- | --- | --- | --- | --- | --- |
| Apple x1.5 | 0.642908688335811 | 0.6555506380628958 | 0.5436965232482474 | -0.7597856502183892 | 1.2057289499413937 | 0.8461711380716604 |
| Apple | 0.4402456855969947 | 0.443106226796299 | 0.374333297110842 | -0.565253090274062 | 1.1837211122180589 | 0.7788470212229045 |
| Gold | 0.0930704223128442 | 0.1133559855203503 | 0.211526779148851 | -0.3738956743383519 | 0.5358942540347666 | 0.2489208319340474 |
| Nasdaq 100 | 0.1151516319891097 | 0.139345166909569 | 0.2362596564256215 | -0.4680357805519762 | 0.5897967051071084 | 0.2460316855546942 |
| Nasdaq 100 x2 | 0.1817509581460179 | 0.260737155357406 | 0.4239577378953011 | -0.7917468670752064 | 0.6150074218524973 | 0.2295569022172761 |
| Dow Jones | 0.0804928787397625 | 0.1011610245788646 | 0.2096249514882438 | -0.4669807798469822 | 0.4825810279771867 | 0.1723687188285093 |
| S&P 500 | 0.0843110400269864 | 0.1067310809730955 | 0.2186807708260129 | -0.5129417345998756 | 0.4880679749295974 | 0.1643676744157968 |
| CAC 40 | 0.0601696660948698 | 0.0852247363429509 | 0.2259219732800888 | -0.5708324749035251 | 0.3772308426028698 | 0.1054068728395996 |

## F. Optimized portfolios

| Portfolio | CAGR | Mean return annualized | Volatility | Max Drawdown | Sharpe | Calmar | Success | Solver status | Status | Risk ceiling | Main Allocation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Minimum Volatility | 0.0927200257924675 | 0.1012808102664326 | 0.1456548343187434 | -0.2319250965457839 | 0.6953480860428911 | 0.3997843578526391 | True | 0 | Optimization terminated successfully |  | Gold 43.4% · CAC 40 32.5% · Dow Jones 24.1% |
| Maximum CAGR | 0.6429086883358115 | 0.6555506380628957 | 0.5436965232482472 | -0.7597856502183891 | 1.2057289499413937 | 0.8461711380716613 | True | 0 | Optimization terminated successfully |  | Apple x1.5 100.0% |
| Maximum Sharpe | 0.3657630098198325 | 0.3568934863788808 | 0.2760564531103878 | -0.4191643476016997 | 1.2928279066027428 | 0.872600477384564 | True | 0 | Optimization terminated successfully |  | Gold 46.8% · Apple x1.5 45.3% · CAC 40 7.9% |
| Prudent | 0.1232881791055167 | 0.1301374346814398 | 0.1500000000000482 | -0.2461241969148084 | 0.8675828978759866 | 0.5009185632739342 | True | 0 | Optimization terminated successfully | 0.15 | Gold 45.4% · CAC 40 31.4% · Dow Jones 18.1% · Apple x1.5 5.1% |
| Modéré | 0.2501464532007593 | 0.2483288100937722 | 0.2000000000000002 | -0.3192807936808858 | 1.2416440504688595 | 0.7834685272386763 | True | 0 | Optimization terminated successfully | 0.2 | Gold 49.4% · Apple x1.5 26.2% · CAC 40 24.4% |
| Dynamique | 0.3975623589251625 | 0.3873224781269979 | 0.3000000000018688 | -0.4471477240593215 | 1.2910749270819504 | 0.8891074191678527 | True | 0 | Optimization terminated successfully | 0.3 | Apple x1.5 50.7% · Gold 46.1% · CAC 40 3.2% |
| Agressif | 0.513954988650968 | 0.5041163306130577 | 0.4000000000000003 | -0.5864115843437057 | 1.2602908265326431 | 0.8764407156556621 | True | 0 | Optimization terminated successfully | 0.4 | Apple x1.5 72.1% · Gold 27.9% |
| Très agressif | 0.60766570620853 | 0.6105457988630217 | 0.4999999999999999 | -0.715314706905374 | 1.2210915977260437 | 0.8495081959623619 | True | 0 | Optimization terminated successfully | 0.5 | Apple x1.5 91.7% · Gold 8.3% |

| Portfolio | Apple x1.5 | Nasdaq 100 x2 | S&P 500 | Dow Jones | CAC 40 | Gold |
| --- | --- | --- | --- | --- | --- | --- |
| Minimum Volatility | 1.384167250040056e-17 | 0.0 | 0.0 | 0.2414892362008239 | 0.3245580526155474 | 0.4339527111836285 |
| Maximum CAGR | 0.9999999999999996 | 0.0 | 0.0 | 2.2204460492503126e-16 | 0.0 | 0.0 |
| Maximum Sharpe | 0.4532576707414493 | 2.3212090886556837e-17 | 2.3884635046676758e-17 | 6.630573911106662e-18 | 0.0787872741589354 | 0.467955055099615 |
| Prudent | 0.0513196118723367 | 3.667911072834482e-17 | 1.217135887187064e-18 | 0.1806179144617221 | 0.3142818684909348 | 0.4537806051750064 |
| Modéré | 0.2616054653103525 | 1.343180107624488e-16 | 0.0 | 0.0 | 0.2441505441313164 | 0.494243990558331 |
| Dynamique | 0.506957443468944 | 1.4424677277187156e-16 | 0.0 | 6.611383320895433e-17 | 0.032103882168846 | 0.4609386743622098 |
| Agressif | 0.7207012154404175 | 0.0 | 0.0 | 1.7618241627753094e-16 | 0.0 | 0.2792987845595822 |
| Très agressif | 0.916995051521017 | 1.4771379478569834e-17 | 0.0 | 5.640474289878202e-17 | 8.935916772177253e-19 | 0.0830049484789828 |

## G. Test and notebook execution

Command: `.venv/Scripts/python.exe -m pytest -q` (repository-local TEMP/TMP and matplotlib cache).

```text
...................................................................      [100%]
67 passed in 1.90s
```

Command: `.venv/Scripts/python.exe run.py`. All 8 code cells executed in sequence in a fresh kernel; zero error outputs and two embedded PNG charts. The local TCP transport warning from ipykernel is recorded; there are no failed cells. An existing installed environment is used, with a fresh kernel per execution.

## H. Numerical sanity checks

```json
{
  "portfolio_weight_sums": {
    "Minimum Volatility": 1.0,
    "Maximum CAGR": 1.0,
    "Maximum Sharpe": 0.9999999999999998,
    "Prudent": 1.0,
    "Modéré": 1.0,
    "Dynamique": 1.0,
    "Agressif": 1.0,
    "Très agressif": 1.0,
    "Frontier 0": 1.0,
    "Frontier 1": 1.0,
    "Frontier 2": 1.0000000000000002,
    "Frontier 3": 1.0,
    "Frontier 4": 1.0,
    "Frontier 5": 1.0,
    "Frontier 6": 1.0,
    "Frontier 7": 1.0,
    "Frontier 8": 1.0,
    "Frontier 9": 1.0,
    "Frontier 10": 1.0,
    "Frontier 11": 1.0,
    "Frontier 12": 1.0,
    "Frontier 13": 1.0,
    "Frontier 14": 1.0,
    "Frontier 15": 1.0,
    "Frontier 16": 1.0,
    "Frontier 17": 1.0,
    "Frontier 18": 0.9999999999999999,
    "Frontier 19": 1.0,
    "Frontier 20": 1.0,
    "Frontier 21": 1.0,
    "Frontier 22": 1.0,
    "Frontier 23": 1.0,
    "Frontier 24": 1.0,
    "Frontier 25": 1.0,
    "Frontier 26": 1.0,
    "Frontier 27": 1.0,
    "Frontier 28": 0.9999999999999998,
    "Frontier 29": 0.9999999999999999,
    "Frontier 30": 1.0,
    "Frontier 31": 1.0,
    "Frontier 32": 1.0,
    "Frontier 33": 1.0,
    "Frontier 34": 1.0,
    "Frontier 35": 0.9999999999999999,
    "Frontier 36": 1.0,
    "Frontier 37": 1.0,
    "Frontier 38": 1.0,
    "Frontier 39": 1.0,
    "Frontier 40": 1.0,
    "Frontier 41": 1.0,
    "Frontier 42": 1.0,
    "Frontier 43": 1.0,
    "Frontier 44": 1.0,
    "Frontier 45": 1.0,
    "Frontier 46": 0.9999999999999999,
    "Frontier 47": 0.9999999999999999,
    "Frontier 48": 0.9999999999999999,
    "Frontier 49": 1.0
  },
  "minimum_portfolio_weight": 0.0,
  "maximum_weight_sum_error": 2.220446049250313e-16,
  "largest_volatility_ceiling_violation": 4.5522753344684475e-09,
  "nonfinite_final_returns": 0,
  "common_observations": 2970,
  "return_observations": 2969,
  "common_start": "2003-12-01",
  "common_end": "2015-12-18",
  "covariance_minimum_eigenvalue": 0.0009843410428964077,
  "solver_attempts": 70,
  "successful_solver_attempts": 69,
  "optimizer_solve_count": 69,
  "optimizer_success_count": 69,
  "unsuccessful_solver_attempts": 1
}
```

All 69 optimizer solves finish successfully, status 0. There are 70 attempts: Frontier 48 initially returns status 8 (positive directional derivative), then succeeds via the pre-existing ftol=1e-7 fallback. That initial attempt is fully disclosed in solver-log.csv. All named portfolios and frontier points pass weight, growth and risk-ceiling validation; the maximum risk violation is below the unchanged 1e-7 tolerance.

## Equal-input engine regression

```text
frontier_assets (include_leveraged_in_frontier=False): ['Apple', 'Nasdaq 100', 'S&P 500', 'Dow Jones', 'CAC 40', 'Gold']
frontier_assets (include_leveraged_in_frontier=True): ['Apple x1.5', 'Nasdaq 100 x2', 'S&P 500', 'Dow Jones', 'CAC 40', 'Gold']
Frontier universe: Apple x1.5, Nasdaq 100 x2, S&P 500, Dow Jones, CAC 40, Gold
50 optimized frontier points; 13 validation checks passed.
5 configured profiles; 5 feasible; 19 validation checks passed.
         Portfolio     Metric  Archived engine  Refactored engine    Difference
Minimum Volatility       CAGR         0.092720           0.092720 -3.330669e-16
Minimum Volatility Volatility         0.145655           0.145655 -2.775558e-17
Minimum Volatility     Sharpe         0.695348           0.695348 -1.110223e-16
      Maximum CAGR       CAGR         0.642909           0.642909 -2.220446e-16
      Maximum CAGR Volatility         0.543697           0.543697  1.110223e-16
      Maximum CAGR     Sharpe         1.205729           1.205729 -2.220446e-16
    Maximum Sharpe       CAGR         0.365763           0.365763  3.885781e-16
    Maximum Sharpe Volatility         0.276056           0.276056  4.440892e-16
    Maximum Sharpe     Sharpe         1.292828           1.292828 -4.440892e-16
           Prudent       CAGR         0.123288           0.123288  5.134781e-16
           Prudent Volatility         0.150000           0.150000 -2.775558e-17
           Prudent     Sharpe         0.867583           0.867583 -4.440892e-16
            Modéré       CAGR         0.250146           0.250146  8.881784e-16
            Modéré Volatility         0.200000           0.200000  8.326673e-17
            Modéré     Sharpe         1.241644           1.241644 -8.881784e-16
         Dynamique       CAGR         0.397562           0.397562  2.220446e-16
         Dynamique Volatility         0.300000           0.300000  5.551115e-17
         Dynamique     Sharpe         1.291075           1.291075 -4.440892e-16
          Agressif       CAGR         0.513955           0.513955  0.000000e+00
          Agressif Volatility         0.400000           0.400000 -1.665335e-16
          Agressif     Sharpe         1.260291           1.260291 -4.440892e-16
     Très agressif       CAGR         0.607666           0.607666 -8.881784e-16
     Très agressif Volatility         0.500000           0.500000 -2.220446e-16
     Très agressif     Sharpe         1.221092           1.221092  0.000000e+00
Archived optimization validations passed: 19
Equal-input engine regression passed; source/FX methodological changes are intentionally excluded.
```

The archived engine's 19 validations pass on exactly the new exported EUR input series. Changes in investment metrics come from the benchmark and study window, not a rewritten portfolio engine.
