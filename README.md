# Portfolio Lab

A reproducible historical portfolio study for an **EUR-based investor**. It compares economic asset returns, constructs simplified daily-reset leveraged exposures and finds long-only portfolios that maximize historical compounded growth under annualized volatility ceilings. This is an in-sample research tool: it does not estimate future expected returns or provide an execution strategy.

The notebook is an orchestration layer. Configuration, data validation, FX normalization, calculations, solvers and reporting live in the installed Python package. The original notebook is retained unchanged in `notebooks/archive/draft.ipynb` as audit evidence; it is not the runnable analysis entry point.

## Repository

```text
portfolio-optimization/
  notebooks/
    portfolio_analysis.ipynb       Lightweight study entry point
    portfolio_robustness.ipynb     Subperiod stability and walk-forward out-of-sample validation
    archive/draft.ipynb            Original notebook, for regression audit
  src/portfolio_lab/
    assets.py                     Central ticker catalogue and metadata resolution
    config.py                     Immutable study parameters and universe selection
    data.py                       Provider protocol, Yahoo/CSV, snapshots, alignment
    currency.py                   Explicit USD-per-EUR conversion
    returns.py                    Price validation and observed interval returns
    leverage.py                   Native-session daily-reset synthetic NAV
    metrics.py                    Calendar CAGR and performance statistics
    optimization.py               SLSQP growth frontier, Sharpe and volatility caps
    plotting.py                   Charts and display allocations
    reporting.py                  CSV evidence and independent numerical checks
    robustness.py                 Subperiod re-estimation, annual walk-forward OOS, turnover, HHI
  tests/                          Offline pytest fixtures and legacy regression
  outputs/                        Executed notebook, tables, figures and audit logs
  run.py                          Fresh-kernel execution with repository-local caches
  scripts/check_regression.py      Equal-input original/new optimization comparison
  pyproject.toml                  Installable src package and dependency metadata
  requirements.txt                Runtime installation (-e .)
  requirements-dev.txt            Runtime plus pytest and notebook execution
  .gitignore
```

## Installation and execution

Python 3.10 or newer is required. Start a terminal in this repository. PowerShell commands:

```powershell
New-Item -ItemType Directory -Force tmp,.cache | Out-Null
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path (Get-Location) '.cache/pip'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# For tests and automated clean-kernel notebook execution:
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run.py --test
.\.venv\Scripts\python.exe run.py
```

`requirements.txt` installs the project and all runtime dependencies through `pyproject.toml`; there are no undeclared analysis dependencies. `requirements-dev.txt` adds pytest, nbconvert and nbclient. The verified environment's exact installed versions are recorded in `outputs/dependencies-lock.txt`; declared ranges permit later compatible updates, while snapshots and the version record identify this run.

For interactive use, after one `run.py` invocation has created the local kernelspec:

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location) '.cache/matplotlib'
$env:IPYTHONDIR = Join-Path (Get-Location) '.cache/ipython'
$env:JUPYTER_CONFIG_DIR = Join-Path (Get-Location) '.cache/jupyter/config'
$env:JUPYTER_DATA_DIR = Join-Path (Get-Location) '.cache/jupyter/data'
$env:JUPYTER_RUNTIME_DIR = Join-Path (Get-Location) '.cache/jupyter/runtime'
.\.venv\Scripts\python.exe -m jupyter lab notebooks/portfolio_analysis.ipynb
```

Select the **Portfolio Lab** kernel. Run all cells. Automatic execution uses that same interpreter in a fresh kernel, fails on any cell error and writes `outputs/portfolio_analysis.executed.ipynb`. `run.py` configures all runtime/cache paths inside the repository. Offline tests require no market-data network access. For a literal `pytest -q`, configure the same runtime environment and activate the venv; the provided wrapper calls pytest with `-q` and a repository-local temporary directory.

## Configuration

`load_config()` in `config.py` retains sensible project defaults. The notebook's **User configuration** cell contains only an `assets` mapping of display name to ticker and a `leveraged_assets` mapping of name to leverage factor. `configure_universe(load_config(project_dir), assets, leveraged_assets)` resolves the selected tickers into the single effective immutable configuration passed to every analytical step. The notebook intentionally avoids duplicating technical metadata.

Financial metadata is centrally registered in `ASSET_CATALOGUE` in `src/portfolio_lab/assets.py`: symbol, listing currency, instrument, return classification, distribution treatment, limitations and reference URL. Changing a ticker resolves its own metadata; it never inherits the old instrument's metadata. Supported return types are `Price Return`, `Total Return`, `Gross Return`, `Net Return`, `Net Total Return` and `Adjusted price`. Each entry also names its data `provider` (`"yahoo"` by default, `"msci"` for official MSCI index levels), so selecting a symbol in the notebook routes it to the right source automatically. EUR assets need no FX conversion; USD entries automatically request the configured EURUSD series and convert upstream. Yahoo's existing provider uses adjusted prices only for `Adjusted price`; gross-return index levels are not dividend-adjusted again. Unsupported currencies fail explicitly.

For example, edit the notebook configuration before its `configure_universe(...)` call:

```python
del assets["Dow Jones"]
assets["iShares Core MSCI World"] = "IWDA.AS"  # Already registered; Amsterdam EUR ETF listing.
config = configure_universe(load_config(project_dir), assets, leveraged_assets)
```

Selecting, renaming, adding or removing a registered ticker needs no package edits. Unknown symbols raise `Unknown asset symbol 'XYZ'. Register its metadata in src/portfolio_lab/assets.py.` before downloading data. To register a new symbol, add an `Asset(...)` entry to the catalogue's tuple in `assets.py`, verifying its listing currency, return treatment and source first. For example, the existing CAC entry is:

```python
Asset("CAC 40", "PX1GR.PA", "CAC 40 Gross Return Index", "EUR", "Gross Return",
      "Gross dividends reinvested in index levels; no additional dividend adjustment",
      "Yahoo daily history has missing observations; inspect raw valid end and missing counts before interpreting coverage.",
      reference="https://live.euronext.com/en/product/indices/QS0011131834-XPAR"),
```

The catalogue and its entries are immutable at runtime. New registration happens in the package, keeping the normal notebook workflow short and the metadata auditable. IWDA's listing currency is EUR even though the fund's base currency is USD; this does not imply currency hedging. Its listing and accumulating treatment are documented by [iShares](https://www.ishares.com/uk/individual/en/products/251882/ishares-core-msci-world-ucits-etf-usd-acc). Its Yahoo history is short, so the default MSCI World exposure is the official index `MSCI:990100:NETR` instead (see below).

Run **all cells** after an edit so no old notebook outputs remain in memory. To remove Apple, also remove `leveraged_assets["Apple"]`; otherwise validation explains that its leveraged underlying is missing before any download starts. The exported `effective-config.json` records the exact notebook configuration used, including assets, leverage and study parameters. The optional archived-engine regression script reads this export rather than independently reloading default assets.

Use `dataclasses.replace(config, ...)` in the same cell for target volatility profiles, risk-free rate, trading-days convention, frontier resolution, provider, snapshot location and exclusive end date. The recorded end date remains exclusive and deliberately excludes the current incomplete session.

Six of the default economic exposures originate in the old notebook: Apple, Nasdaq 100, S&P 500, Dow Jones, CAC 40 and gold; MSCI World (official NETR index) was added since. AAPL remains the primary US listing. There is no leverage by default: `leveraged_assets = {}` (or `None`) gives a fully unleveraged study and clears any leverage already on the config, and a factor of `1` is the plain asset. Only explicit factors above 1, e.g. `{"Apple": 1.5, "Nasdaq 100": 2.0}`, create synthetic daily-reset series (`Apple x1.5`, `Nasdaq 100 x2`), which replace their unleveraged exposures in the optimization universe when `include_leveraged_in_frontier=True`; both versions still appear in asset statistics. Turning the switch off changes only the optimization universe.

## Total investor return and provenance

These series are deliberately distinguished:

* **Price Return** indices omit cash dividends. `^NDX`, `^GSPC`, `^DJI` and `^FCHI` in the original notebook are not transformed into TR indices merely by `auto_adjust=True`.
* **Total Return** includes distributions and reinvestment under a specified benchmark convention.
* **Gross Return** reinvests gross dividends before withholding tax.
* **Net Return** reinvests dividends after the benchmark's assumed withholding tax, which need not equal a particular investor's actual tax.
* **Net Total Return** is MSCI's NETR variant (e.g. MSCI World, index code 990100): net dividends reinvested after MSCI's withholding-tax assumptions. It is an index level, not an ETF adjusted price: its `pct_change()` already is the total return, so no dividend or Yahoo adjustment is ever applied. Levels are USD and unhedged; EUR conversion uses the same EURUSD path as other USD assets.
* **Adjusted price** for equities/ETFs uses Yahoo's split and dividend adjustment, as a practical reinvestment proxy. It is not claimed to be an independently audited gross/net benchmark. ETF adjustments inherit fees and tracking behavior of that ETF.
* **Gold futures quotation** produces no dividends but its percentage price changes are not the total return of a rolling futures investment. Roll yield, collateral income and financing are absent.

Metadata for every configured exposure includes provider, symbol, instrument, currency, return classification, distribution treatment, source references and limitations. `outputs/provenance.csv` also records actually observed raw start/end, counts, missing values, FX omissions and the final common calendar. The synthetic rows explicitly inherit the underlying provenance and identify the native-currency daily reset.

Genuine TR benchmark sources are preferred when their histories are accessible and usable. If a history is absent, the provider fails explicitly: **there is no automatic switch to a price index or ETF**. Any deliberately chosen adjusted ETF proxy is configured and disclosed with its own shorter history, expenses and benchmark mismatch. A future provider can supply the desired benchmark without changing the engine.

Benchmark references: [Nasdaq XNDX](https://indexes.nasdaqomx.com/Index/Overview/xndx), [S&P 500](https://www.spglobal.com/spdji/en/indices/equity/sp-500/), [Dow Jones Industrial Average](https://www.spglobal.com/spdji/en/indices/equity/dow-jones-industrial-average/) and [CAC 40 GR](https://live.euronext.com/en/product/indices/QS0011131834-XPAR). See the executed provenance table for the configured Yahoo symbols and actual available dates.

## Robustness and out-of-sample validation

`notebooks/portfolio_robustness.ipynb` asks a different question than the main notebook: how stable is the optimized portfolio through time, and how does it perform out of sample? It starts from the same `load_config()` defaults (universe, providers, EUR conversion, leverage, engine settings); all logic is in `portfolio_lab.robustness`, which calls the engine's `PortfolioOptimizer.core_portfolios()` (Minimum Volatility, Maximum CAGR, multi-start Maximum Sharpe) rather than re-implementing it.

* **Full-sample optimization** (main notebook) is descriptive and in-sample.
* **Subperiod stability** re-estimates the engine independently on 2001–2010, 2011–2020 and 2021–latest (actual common dates). It is still in-sample within each period and is **not** an out-of-sample test. Per-asset mean/min/max/sample-std weight and the share of near-zero (< 1e-4) weights summarize stability.
* **Walk-forward** is the out-of-sample test. For each calendar test year, Maximum Sharpe and Minimum Volatility are estimated on the previous 10 full calendar years only, frozen, and applied to that year only. Folds come from the actual common history (a training window needs an observation before its first year as its return base); the final year can be incomplete and is flagged. Equal Weight uses the same optimizer universe; MSCI World is its realized EUR return. The OOS curve is the chronological concatenation of test-year returns only, and its CAGR/volatility/Sharpe/drawdown come from `compute_asset_metrics`.

Weights follow the engine's convention: constant targets rebalanced at every common observation; walk-forward re-estimates the targets annually. Turnover is `0.5 × Σ|w_t − w_{t−1}|` between consecutive annual targets (the first allocation has none; within-year rebalancing to target is not counted). Concentration is `HHI = Σ w²` and effective number of assets `1 / HHI`; it is diagnostic only, with no weight caps imposed. OOS results are for evaluation and are not used to tune anything; they are not evidence of future performance.

## Data layer and reproducibility

`Provider.history(asset, end)` returns a named pandas Series with an ordered, unique, timezone-free DatetimeIndex of exchange-local session dates. Observed values must be finite and strictly positive. Missing observations are allowed in raw history and are reported; duplicates, bad prices, unexpected names and bad calendars fail validation. `YahooProvider` is the only module that imports/calls yfinance; `MSCIProvider` is the only one that calls `msci-data` (`msci.get_levels(code, ..., variant=...)` for symbols of the form `MSCI:<index code>:<variant>`, rejecting non-numeric levels, conflicting duplicate dates, or a currency/variant mismatch, and failing if no data is returned); `CSVProvider` accepts one `Date,Value` CSV per configured symbol. `load_market_data(config)` routes each asset by its catalogued `provider` and fetches EURUSD from Yahoo. For tests, pass either a single provider (serves every series) or a mapping such as `{"yahoo": ..., "msci": ...}`. The provenance table's `Source detail` column records the MSCI index code, variant and native currency. MSCI snapshots live in `<cache_dir>/msci` with the same hash manifests as Yahoo.

Yahoo downloads use explicit daily frequency, exclusive end, adjustment based on return classification, no repair, no filling and retained actions. The snapshot directory stores value CSVs, original returned source frames and JSON manifests with download parameters, UTC download timestamp, vendor currency and SHA256 hash. Repeated runs use and verify those same snapshots. Pass `YahooProvider(config.cache_dir, refresh=True)` explicitly to download again. CSV snapshots preserve full precision. Vendor data can be revised and is not exchange-grade or independently audited; timezone alignment, dividend corrections, index coverage and futures contract stitching remain vendor risks. Licensing and redistribution restrictions must be assessed for another use of the data.

## EUR normalization and dates

EUR/USD comes from FRED series **`DEXUSEU`** ("U.S. Dollars to One Euro", Federal Reserve noon buying rates, from 1999-01-04), fetched by `FREDProvider` from the public `fredgraph.csv` endpoint (no API key) and snapshotted in `<cache_dir>/fred` like other sources. It replaced Yahoo `EURUSD=X`, whose history only starts on 2003-12-01 and used to truncate the common window. `Config.fx_provider`/`fx_symbol` record the choice; the notebook needs no FX code. FRED leaves US holidays blank; those dates are dropped (never filled), so USD assets lose those sessions, as reported in `FX missing on observed sessions`. Provenance shows `FX provider`, `FX series used`, `FX convention` and `FX start date`.

The quote is **USD per EUR** and is used as published, never inverted. If one EUR buys two USD, USD 100 is EUR 50:

```text
Value_EUR(t) = Value_USD(t) / EURUSD(t)
```

EUR assets are unchanged. Conversion occurs before returns, covariance, statistics and optimization; converting final USD metrics would be incorrect. The sample in `outputs/fx-validation.csv` is independently checked to floating-point tolerance.

Only same-date observed asset/FX quotes are used: a missing FX date creates a missing EUR observation, not an interpolated/stale value. Converted asset series are intersected across all configured assets, with at least three common observations required. No forward/backward filling occurs. Dates are local exchange session labels; daily closes and Yahoo FX observations are not synchronized intraday. This convention is appropriate for a transparent daily study but cannot eliminate non-synchronous-close effects. It should not be used to simulate executable simultaneous trades.

The next common return aggregates all intermediate underlying moves (including weekends for a possible crypto configuration). Mean and volatility retain the original **252 common-observation** convention; irregular multi-session intervals are not time-rescaled. CAGR uses actual elapsed calendar days. Availability records distinguish omitted FX sessions, raw missing observations and the final common sample; absent calendar dates are not counted as raw NaNs, because holidays cannot be inferred from a sparse provider Series.

## Daily-reset leverage

For each actual native underlying session:

```text
r(t) = P(t) / P(t-1) - 1
NAV(t) = NAV(t-1) * max(0, 1 + L * r(t))
```

Reset/compounding happens on every observed underlying session inside the study interval **before** common-calendar sampling. A zero NAV is absorbing and return after zero/zero is defined as zero; the wipeout interval itself returns -100%. Nonpositive leverage, invalid prices and numerical overflow fail clearly.

For USD exposures, this native-currency synthetic NAV is then divided by EURUSD. FX itself is not leveraged, matching an EUR investor holding an unhedged USD daily-reset product. Applying leverage to EUR-converted asset returns would describe a different EUR-reset exposure and is intentionally not the default. Missing FX on intermediate dates does not skip native reset sessions.

Synthetic leverage excludes financing/borrowing costs, ETF fees, tracking error, transaction costs, taxes, liquidity and implementation constraints, and intraday rebalancing. It is an educational exposure model, not a reconstruction of a traded leveraged ETF.

## Metric definitions

For common price observations `P[0..n]`:

```text
years = (last_date - first_date).days / 365.25
CAGR = (P[n] / P[0]) ** (1 / years) - 1
Annualized Mean Return = mean(simple interval returns) * 252
Annualized Volatility = std(simple interval returns, ddof=1) * sqrt(252)
Drawdown(t) = P(t) / running_max(P)(t) - 1
Max Drawdown = min(Drawdown)
Sharpe = (Annualized Mean Return - annual risk_free_rate) / Annualized Volatility
Calmar = CAGR / abs(Max Drawdown)
```

Initial NAV is included in the running maximum. The first price has no return observation. CAGR at terminal zero is -100%. Zero-volatility Sharpe and zero-drawdown Calmar are undefined (NaN), not infinite; these are intentional ratio edge cases, whereas final return matrices must contain **no NaN/inf**. The arithmetic risk-free convention is unchanged from the original; there is no separate compounding of a risk-free investment. Internally values retain full precision; presentation rounding does not change weights or objective inputs.

## Portfolio optimization

The portfolio holds long-only weights in `[0,1]` with sum one, rebalanced at every common observation. Each interval return is `r_p(t) = sum_i w_i r_i(t)`, rather than a weighted sum of asset CAGRs. Portfolio NAV compounds these returns.

The optimizer's risk model is one covariance estimate, `portfolio_lab.covariance.estimate_covariance`, selected by `Config.covariance_method`: `"ledoit_wolf"` (default; scikit-learn `LedoitWolf` with its data-driven shrinkage intensity) or `"sample"` (pandas `ddof=1`, which reproduces the earlier engine exactly). It is fitted on the daily returns of the prices being optimized (in walk-forward, each training window only) and annualized once by `trading_days`. Minimum volatility, the Sharpe denominator, volatility ceilings, the frontier grid and dominance use this risk model, reported as `Estimated volatility = sqrt(w.T @ Sigma @ w)`. `Volatility`, `Sharpe`, CAGR and drawdown remain realized historical metrics: volatility is the sample standard deviation of the weighted return series. With `"sample"` both volatilities coincide. The estimator and its shrinkage intensity are printed by the notebooks and recorded in `sanity-checks.json`.

Expected returns are used only by the Maximum Sharpe objective; Minimum Volatility uses covariance only, and Maximum CAGR, the frontier and named risk profiles maximize realized historical log growth. One estimator, `portfolio_lab.expected_returns.estimate_expected_returns`, is selected by `Config.expected_return_method`: `"sample"` (default; arithmetic mean of daily returns × `trading_days`, the project's reference behavior) or `"bayes_stein"`. Bayes-Stein is Jorion (1986, *JFQA* 21(3), 279–292), computed in daily units from the optimized window only: `Σ = S·(T−1)/(T−N−2)`, target `μ0 = 1′Σ⁻¹m / 1′Σ⁻¹1` (the minimum-variance portfolio mean), intensity `w = (N+2) / ((N+2) + T·(m−μ0)′Σ⁻¹(m−μ0))` in (0, 1] by construction, `μ_BS = (1−w)m + wμ0`, annualized once. No intensity is chosen by hand; walk-forward fits it per training window. It is reported as `Estimated return`; `Mean return annualized` and `Sharpe` stay realized historical metrics. Only Jorion's mean estimator is used; the covariance remains the configured covariance estimator.

**Pre-specified Bayes-Stein experiment (2026-10-08).** The estimator above was fixed before its out-of-sample result was computed, run once on the annual 10-year walk-forward (Ledoit-Wolf covariance, data through 2026-10-02) and not modified afterwards; no parameter was tuned on OOS performance. Fold intensities ranged 0.29–0.57 (mean 0.45). Maximum Sharpe OOS, sample mean → Bayes-Stein: CAGR 16.01% → 13.86%, volatility 17.36% → 14.88%, Sharpe 0.953 → 0.958, max drawdown −35.12% → −34.88%, mean turnover 16.0% → 17.7%, mean effective assets 2.49 → 2.81; years beating Equal Weight 10/16 → 8/16, mean annual excess +2.2% → −0.3%, worst year 2013 (−27.9% → −29.2%). Minimum Volatility, Equal Weight and MSCI World are unaffected. Conclusion: no robustness improvement versus Equal Weight. The default stays `"sample"` to preserve the reference behavior; `"bayes_stein"` remains available for comparison.

SLSQP first solves minimum variance and unrestricted maximum historical log growth. The upper frontier maximizes `mean(log(1 + r_p)) * 252` under volatility **ceilings**, spanning minimum risk to the maximum-growth endpoint. The growth objective has the same optimum as calendar CAGR because study duration is fixed. Each named target solves the same problem; a ceiling below minimum achievable volatility is reported as infeasible with missing weights. Above the maximum-growth risk, it reuses that optimum and reports unused risk allowance. Target risk is not an equality.

Maximum Sharpe uses arithmetic mean excess return and deterministic starts at equal weights, minimum risk, maximum growth and all asset vertices. With nonpositive excess returns this objective is not globally quasiconcave: multiple starts reduce sensitivity but do not constitute a universal global-optimality proof. With zero sample volatility, numerical denominator floors keep optimization evaluable; the reported ratio remains undefined if variance is exactly zero.

The solver uses explicit gradients, scaled risk constraints and a documented fallback from `ftol=1e-10` to `1e-7`, with at most 1000 iterations each. Every attempted status, message, raw weight sum and raw minimum weight is recorded. Weight cleanup is limited to tolerated numerical errors, followed by actual risk-ceiling validation (tolerance `1e-7`). Failures raise exceptions. Frontier monotonicity and dominance over each single asset at its exact risk are checked, alongside covariance PSD, weighted-return risk and independently compounded CAGR. Numerical floors affect boundary solver evaluation only; reported wipeout CAGR is exact.

This frontier maximizes realized growth in-sample and can be sensitive to the historical interval, vendor data and extreme returns. The default study does not include walk-forward validation, estimation uncertainty, out-of-sample selection, portfolio costs or future forecasts. These should be added before treating historical optimal weights as an investment process.

## Review evidence and regression

`outputs/review.md` prints provenance, real FX samples, asset performance, all optimized portfolios and full weights, all frontier points, exact-risk asset dominance, solver attempts and numerical sanity checks. Corresponding CSVs retain precision and allow independent review. `sanity-checks.json` contains all weight sums and their maximum error, maximum risk-ceiling violation, minimum weight, invalid return count, common dates/count, covariance minimum eigenvalue and solver success counts. `study-coverage.json` distinguishes the latest raw-asset start, EUR-normalized availability, FX limitations and any delay from the intersection of observed calendars. Charts and the fully executed notebook are also saved.

`pytest` covers deterministic schema/calendar rejection, availability metadata, FX direction and independent FX moves, returns without filling, leverage wipeout and pre-alignment compounding, independent metric expected values, analytic minimum-risk weights, independent portfolio compounding/risk, infeasible targets, universe selection and Sharpe with negative excess returns. Regression tests extract and execute only the original notebook's pure leverage and performance functions on identical inputs: those calculations must agree. They do not execute the original network cells.

After running the notebook, `.\.venv\Scripts\python.exe scripts/check_regression.py` also executes the archived optimization/target cells on exactly the same exported EUR prices. It validates the archived safeguards and compares portfolio metrics/weights with the new engine. `outputs/engine-regression.csv` records the differences; this comparison deliberately excludes source/FX changes.

The CAC 40 uses **`PX1GR.PA`**, Yahoo's actual CAC 40 Gross Return Index in EUR, with gross dividends already reinvested in the index level. Its available raw history starts on 1987-12-31. It is classified as `Gross Return`, so the provider requests `auto_adjust=False`: no dividend adjustment or FX conversion is added. There is no ETF-inception filter. The actual raw counts and end dates are measured at execution; the exclusive end remains unchanged, so this run excludes the 2026-10-05 session.

The live Yahoo source audit found **7,076 valid completed-session CAC closes ending on 2015-12-18**, followed by missing closes and an isolated 2026-10-05 quote when the current session is included. A first/last date and a nonmissing count alone can conceal that gap: `keepna=True` exposes 2,930 missing daily rows within the requested historical range. `outputs/cac-source-audit.log` records both bounded/unbounded requests and a recent-period request that returns no usable history. No prices are filled and no alternative series is silently substituted. Consequently, the executed common study is **2003-12-01 through 2015-12-18, 2,970 price observations**. EURUSD availability determines the common start; Gold has the latest raw asset start (2000-08-30), and CAC 40 determines the common end. This extends the beginning and observation count relative to the previous 2019-09-05 through 2026-10-02 study (1,763 observations), but loses its recent coverage. A complete updated CAC GR history requires a better source or corrected Yahoo data.

S&P 500 likewise uses a genuine gross-return benchmark, `^SP500TR`. QQQ and DIA remain explicit adjusted ETF proxies for the Nasdaq-100 and Dow Jones exposures; tested Yahoo `^XNDX` and `^DJITR` histories were unavailable. Those tested symbols do not establish that every Yahoo spelling or another provider lacks TR data. The current benchmark availability and provenance reports show the actual configured sources.

Architectural changes alone preserve formulas. Methodological changes intentionally alter final results: dividend-inclusive benchmark/proxy selection, EUR translation, available histories/common calendar and explicit unlevered FX for USD synthetic products. No assertion requires new investment metrics to match the old mixed-currency price-index study. The detailed run evidence describes any inaccessible benchmark and selected proxy without concealing the exposure change.
