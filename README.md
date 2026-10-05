# Portfolio Lab

A reproducible historical portfolio study for an **EUR-based investor**. It compares economic asset returns, constructs simplified daily-reset leveraged exposures and finds long-only portfolios that maximize historical compounded growth under annualized volatility ceilings. This is an in-sample research tool: it does not estimate future expected returns or provide an execution strategy.

The notebook is an orchestration layer. Configuration, data validation, FX normalization, calculations, solvers and reporting live in the installed Python package. The original notebook is retained unchanged in `notebooks/archive/draft.ipynb` as audit evidence; it is not the runnable analysis entry point.

## Repository

```text
Draft/
  notebooks/
    portfolio_analysis.ipynb       Lightweight study entry point
    archive/draft.ipynb            Original notebook, for regression audit
  src/portfolio_lab/
    config.py                     Immutable asset metadata and study parameters
    data.py                       Provider protocol, Yahoo/CSV, snapshots, alignment
    currency.py                   Explicit USD-per-EUR conversion
    returns.py                    Price validation and observed interval returns
    leverage.py                   Native-session daily-reset synthetic NAV
    metrics.py                    Calendar CAGR and performance statistics
    optimization.py               SLSQP growth frontier, Sharpe and volatility caps
    plotting.py                   Charts and display allocations
    reporting.py                  CSV evidence and independent numerical checks
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

`load_config()` in `config.py` is the only default configuration. The notebook can explicitly use `dataclasses.replace(config, ...)` to change study parameters. Configure assets (symbols, currency, instrument and return type), leverage, target volatility profiles, risk-free rate, trading-days convention, frontier resolution, provider, snapshot location and exclusive end date here. The implementation currently supports EUR base currency and EUR/USD asset quotes, rejecting unsupported currencies rather than inferring a conversion. The recorded end date is exclusive and deliberately excludes the current incomplete session.

The default six economic exposures originate in the old notebook: Apple, Nasdaq 100, S&P 500, Dow Jones, CAC 40 and gold. AAPL remains the primary US listing. Apple x1.5 and Nasdaq 100 x2 replace their unleveraged exposures in the optimization universe when `include_leveraged_in_frontier=True`; both versions still appear in asset statistics. Turning the switch off changes only the optimization universe.

## Total investor return and provenance

These series are deliberately distinguished:

* **Price Return** indices omit cash dividends. `^NDX`, `^GSPC`, `^DJI` and `^FCHI` in the original notebook are not transformed into TR indices merely by `auto_adjust=True`.
* **Total Return** includes distributions and reinvestment under a specified benchmark convention.
* **Gross Return** reinvests gross dividends before withholding tax.
* **Net Return** reinvests dividends after the benchmark's assumed withholding tax, which need not equal a particular investor's actual tax.
* **Adjusted price** for equities/ETFs uses Yahoo's split and dividend adjustment, as a practical reinvestment proxy. It is not claimed to be an independently audited gross/net benchmark. ETF adjustments inherit fees and tracking behavior of that ETF.
* **Gold futures quotation** produces no dividends but its percentage price changes are not the total return of a rolling futures investment. Roll yield, collateral income and financing are absent.

Metadata for every configured exposure includes provider, symbol, instrument, currency, return classification, distribution treatment, source references and limitations. `outputs/provenance.csv` also records actually observed raw start/end, counts, missing values, FX omissions and the final common calendar. The synthetic rows explicitly inherit the underlying provenance and identify the native-currency daily reset.

Genuine TR benchmark sources are preferred when their histories are accessible and usable. If a history is absent, the provider fails explicitly: **there is no automatic switch to a price index or ETF**. Any deliberately chosen adjusted ETF proxy is configured and disclosed with its own shorter history, expenses and benchmark mismatch. A future provider can supply the desired benchmark without changing the engine.

Benchmark references: [Nasdaq XNDX](https://indexes.nasdaqomx.com/Index/Overview/xndx), [S&P 500](https://www.spglobal.com/spdji/en/indices/equity/sp-500/), [Dow Jones Industrial Average](https://www.spglobal.com/spdji/en/indices/equity/dow-jones-industrial-average/) and [CAC 40 GR](https://live.euronext.com/en/product/indices/QS0011131834-XPAR). See the executed provenance table for the configured Yahoo symbols and actual available dates.

## Data layer and reproducibility

`Provider.history(asset, end)` returns a named pandas Series with an ordered, unique, timezone-free DatetimeIndex of exchange-local session dates. Observed values must be finite and strictly positive. Missing observations are allowed in raw history and are reported; duplicates, bad prices, unexpected names and bad calendars fail validation. `YahooProvider` is the only module that imports/calls yfinance; `CSVProvider` accepts one `Date,Value` CSV per configured symbol. An injected provider can replace either directly.

Yahoo downloads use explicit daily frequency, exclusive end, adjustment based on return classification, no repair, no filling and retained actions. The snapshot directory stores value CSVs, original returned source frames and JSON manifests with download parameters, UTC download timestamp, vendor currency and SHA256 hash. Repeated runs use and verify those same snapshots. Pass `YahooProvider(config.cache_dir, refresh=True)` explicitly to download again. CSV snapshots preserve full precision. Vendor data can be revised and is not exchange-grade or independently audited; timezone alignment, dividend corrections, index coverage and futures contract stitching remain vendor risks. Licensing and redistribution restrictions must be assessed for another use of the data.

## EUR normalization and dates

Yahoo `EURUSD=X` is **USD per EUR**. If one EUR buys two USD, USD 100 is EUR 50:

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

The portfolio holds long-only weights in `[0,1]` with sum one, rebalanced at every common observation. Each interval return is `r_p(t) = sum_i w_i r_i(t)`, rather than a weighted sum of asset CAGRs. Portfolio NAV compounds these returns; volatility is both `sqrt(w.T @ annual_covariance @ w)` and independently checked against the sample standard deviation of the weighted return series.

SLSQP first solves minimum variance and unrestricted maximum historical log growth. The upper frontier maximizes `mean(log(1 + r_p)) * 252` under volatility **ceilings**, spanning minimum risk to the maximum-growth endpoint. The growth objective has the same optimum as calendar CAGR because study duration is fixed. Each named target solves the same problem; a ceiling below minimum achievable volatility is reported as infeasible with missing weights. Above the maximum-growth risk, it reuses that optimum and reports unused risk allowance. Target risk is not an equality.

Maximum Sharpe uses arithmetic mean excess return and deterministic starts at equal weights, minimum risk, maximum growth and all asset vertices. With nonpositive excess returns this objective is not globally quasiconcave: multiple starts reduce sensitivity but do not constitute a universal global-optimality proof. With zero sample volatility, numerical denominator floors keep optimization evaluable; the reported ratio remains undefined if variance is exactly zero.

The solver uses explicit gradients, scaled risk constraints and a documented fallback from `ftol=1e-10` to `1e-7`, with at most 1000 iterations each. Every attempted status, message, raw weight sum and raw minimum weight is recorded. Weight cleanup is limited to tolerated numerical errors, followed by actual risk-ceiling validation (tolerance `1e-7`). Failures raise exceptions. Frontier monotonicity and dominance over each single asset at its exact risk are checked, alongside covariance PSD, weighted-return risk and independently compounded CAGR. Numerical floors affect boundary solver evaluation only; reported wipeout CAGR is exact.

This frontier maximizes realized growth in-sample and can be sensitive to the historical interval, vendor data and extreme returns. The default study does not include walk-forward validation, estimation uncertainty, out-of-sample selection, portfolio costs or future forecasts. These should be added before treating historical optimal weights as an investment process.

## Review evidence and regression

`outputs/review.md` prints provenance, real FX samples, asset performance, all optimized portfolios and full weights, all frontier points, exact-risk asset dominance, solver attempts and numerical sanity checks. Corresponding CSVs retain precision and allow independent review. `sanity-checks.json` contains all weight sums, maximum risk-ceiling violation, minimum weight, invalid return count, common dates/count and the covariance minimum eigenvalue. Charts and the fully executed notebook are also saved.

`pytest` covers deterministic schema/calendar rejection, availability metadata, FX direction and independent FX moves, returns without filling, leverage wipeout and pre-alignment compounding, independent metric expected values, analytic minimum-risk weights, independent portfolio compounding/risk, infeasible targets, universe selection and Sharpe with negative excess returns. Regression tests extract and execute only the original notebook's pure leverage and performance functions on identical inputs: those calculations must agree. They do not execute the original network cells.

After running the notebook, `.\.venv\Scripts\python.exe scripts/check_regression.py` also executes the archived optimization/target cells on exactly the same exported EUR prices. It validates the archived safeguards and compares portfolio metrics/weights with the new engine. `outputs/engine-regression.csv` records the differences; this comparison deliberately excludes source/FX changes.

For this run, Yahoo returned usable `^SP500TR`, but no usable history for the tested `^XNDX`, `^DJITR` and `^PX1GR` symbols (see `outputs/benchmark-availability.log`). Defaults explicitly select QQQ, DIA and CACC.PA as adjusted/accumulating ETF proxies. The absence of those tested symbols does not prove that all Yahoo spellings or other providers lack TR data. CACC.PA history starts on 2018-12-13 in Yahoo, while the cited November 2025 Amundi factsheet lists a share-class creation date of 2019-09-05. Raw history is retained for audit, but `Asset.usable_start="2019-09-05"` excludes the earlier observations from the default study. The provenance table records both raw availability and the excluded count. The fund lineage discrepancy remains unresolved; the conservative exclusion prevents these observations from influencing reported metrics.

Architectural changes alone preserve formulas. Methodological changes intentionally alter final results: dividend-inclusive benchmark/proxy selection, EUR translation, available histories/common calendar and explicit unlevered FX for USD synthetic products. No assertion requires new investment metrics to match the old mixed-currency price-index study. The detailed run evidence describes any inaccessible benchmark and selected proxy without concealing the exposure change.
