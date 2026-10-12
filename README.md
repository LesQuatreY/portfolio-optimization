# Portfolio Lab

A reproducible research system for an **EUR-based investor** (10-20 year horizon) looking for portfolio *selection methods* that generalize, across risk levels and configurable asset universes. It estimates long-only frontiers and risk-profiled allocations, then evaluates the same policies **out of sample** with a strictly chronological annual walk-forward.

It is a research tool: it provides no forecast, no investment advice and no execution strategy. Historical optima, in-sample or out-of-sample, are not future optima.

## Central research question

> Pour chaque niveau de risque que je suis prêt à accepter, quel portefeuille semble offrir la meilleure croissance composée à long terme, sans que cette conclusion repose uniquement sur un heureux hasard historique ?

Every modelling and research decision is judged against this question. Realized CAGR is the primary growth measure, annualized volatility the primary risk axis and maximum drawdown an essential complementary risk measure; investor constraints and the eligible universe are configurable. The estimated optimization frontier (expected arithmetic return and covariance), the weights chosen from it, realized historical performance and chronological out-of-sample performance are four different things and are always labelled as such.

Two research constraints have equal, primary priority:

* **A. Prevent overfitting.** Historical optimization performance is never evidence of future performance. Look-ahead, leakage, universe-selection bias, multiple testing and repeated use of the 2013-2019 validation years are controlled by the holdout lock, the walk-forward protocol and the experiment registry ([docs/RESEARCH_PROTOCOL.md](docs/RESEARCH_PROTOCOL.md)).
* **B. Model and portfolio stability.** A construction method is not attractive merely because it occasionally produces a high CAGR. Fold-to-fold target-weight changes, traded turnover, concentration, sensitivity of the weights to the training sample (training-only bootstrap) and to the estimation window, dependence on single years and on one volatile or synthetic asset are measured (`src/portfolio_lab/stability.py`) and must shape conclusions (findings: docs/PHASE5_RESULTS.md, docs/PHASE6_RESULTS.md, docs/PHASE7B_RESULTS.md). Exposure stability is measured in risk units, `sqrt(dw' Sigma dw)` with a fixed 2001-2012 covariance, next to instrument weights: switching between highly correlated series changes weights much more than exposure. Market volatility and model instability are different things, and legitimate adaptation is not penalized as such. No composite growth-plus-stability score is computed; comparisons are multi-criteria and transparent.

## Research protocol (read first)

All boundaries are exclusive upper bounds (`date < boundary`) and are defined in `src/portfolio_lab/protocol.py`.

| Period | Dates | Use |
|---|---|---|
| Development | before 2013-01-01 (data start 2000-12-29) | exploration, in-sample frontier analysis (default window of `portfolio_analysis.ipynb`) |
| Validation | test years 2013-2019 | walk-forward evaluation only (`portfolio_robustness.ipynb`) |
| Final holdout | from 2020-01-01 | **locked**, technically inaccessible |

**Holdout lock.** No research configuration can end after 2020-01-01 (`Config`, `config/research.yaml`), every provider refuses such a request and rejects returned rows on or after the boundary, `validate_prices` (the choke point of every return, metric, optimizer, walk-forward and bootstrap computation) rejects them, exported files and executed notebooks are scanned for holdout dates after writing, and tests check that the active notebooks contain none. There is no flag that lifts the lock: a final evaluation must be a separate, explicitly authorized change of `protocol.py`.

**Known prior exposure.** Results covering 2020-2026 were produced and read before this lock existed (see [docs/HOLDOUT_EXPOSURE.md](docs/HOLDOUT_EXPOSURE.md)). The holdout is a reserved period with known information exposure, **not** a pristine out-of-sample test. A genuinely prospective evaluation needs future data.

**Validation overfitting.** Each walk-forward run is appended to `experiments/registry.jsonl` (configuration actually evaluated, evaluated universe and walk-forward settings, git commit plus a hash of uncommitted engine changes, declared category and hypothesis, results; identical reruns are marked as reruns, reruns on changed code as superseding). Plans and decisions are logged before the results they govern. Exposure (whether an evaluation, and which of its strategies, had already been seen) is recomputed chronologically from normalized result-determining inputs (`exposure_history`). The selection rules are in [docs/RESEARCH_PROTOCOL.md](docs/RESEARCH_PROTOCOL.md). Choosing the best policy, universe, constraint or estimator by its 2013-2019 result biases that result upward; seven years say little about rare regimes or worst drawdowns.

## Repository

```text
portfolio-optimization/
  config/research.yaml           Single shared research configuration (universe, leverage, constraints, protocol)
  notebooks/
    portfolio_analysis.ipynb     In-sample analysis: frontier, allocations, sensitivity, bootstrap (French UI)
    portfolio_robustness.ipynb   Out-of-sample walk-forward 2013-2019, universe comparison, registry (French UI)
    archive/draft.ipynb          Original notebook, regression evidence only (not a research entry point)
  src/portfolio_lab/
    protocol.py                  Date boundaries, holdout lock, output scanners
    research.py                  research.yaml loader, the single data path of both notebooks
    config.py                    Immutable engine Config, eligibility, constraints, walk-forward settings
    assets.py                    Central ticker catalogue and metadata
    data.py                      Providers (Yahoo, MSCI, FRED, CSV), snapshots, alignment
    currency.py / returns.py     USD -> EUR conversion, observed interval returns
    leverage.py                  Native-session daily-reset synthetic NAV with fee/financing drag
    metrics.py                   Calendar CAGR and performance statistics
    covariance.py / expected_returns.py   Ledoit-Wolf / sample covariance, sample / Bayes-Stein means
    optimization.py              SLSQP growth frontier, Maximum Sharpe, volatility ceilings, investor bounds
    robustness.py                Walk-forward, universe comparison, OOS uncertainty, subperiods
    simulation.py                Wealth simulation of target weights (annual drift / constant mix, costs)
    rates.py                     Point-in-time historical short rates (risk-free EUR, financing per currency)
    stability.py                 Allocation-stability diagnostics (target changes, turnover, concentration, bootstrap)
    diagnostics.py               Mean uncertainty, correlation PCA, risk contributions, exposure (risk) distance
    bootstrap.py                 Stationary-bootstrap frontier uncertainty (in-sample)
    experiments.py               Append-only experiment registry
    charts.py                    Plotly charts (French labels); plotting.py keeps the legacy matplotlib charts
    reporting.py                 CSV evidence, numerical checks, export safety checks
  experiments/registry.jsonl     Recorded validation experiments (tracked)
  tests/                         Offline pytest suite (synthetic data, all dated before 2020)
  outputs/                       Executed notebooks, CSV/HTML exports (git-ignored)
  run.py                         Fresh-kernel notebook execution (outputs safety-checked) or tests
```

## Installation and execution

Python 3.10 or newer. PowerShell, from the repository root:

```powershell
New-Item -ItemType Directory -Force tmp,.cache | Out-Null
$env:TEMP = Join-Path (Get-Location) 'tmp'; $env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path (Get-Location) '.cache/pip'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run.py --test          # offline test suite
.\.venv\Scripts\python.exe run.py                 # both notebooks, fresh kernels -> outputs/*.executed.ipynb
.\.venv\Scripts\python.exe run.py portfolio_robustness
```

`run.py` refuses to write an executed notebook whose outputs mention a holdout date. For interactive use, start JupyterLab after one `run.py` call (it registers the **Portfolio Lab** kernel), open a notebook and *Run All*. Market data are read from integrity-checked snapshots in `.cache/market`; a missing snapshot is downloaded once (always with an end before 2020-01-01).

## Configuring the study: `config/research.yaml`

Both notebooks call `load_research_study()`, which reads only this file; notebooks contain no study parameter. Every value is validated (unknown keys, unknown assets, infeasible bounds and any end after 2020-01-01 fail with an explicit message).

* **`universe`**: assets eligible for **direct** allocation (`display name: registered symbol`). Eligible does not mean held: the optimizer may give any eligible asset exactly 0%, and no minimum weight is implied. Comment out a line to make an asset ineligible: it can then never receive a direct weight (nor can its leveraged version). Indirect exposure is unaffected: Apple remains inside Nasdaq 100, S&P 500 and MSCI World.
* **Eight-asset universe (investor decision, phase 7B).** The seven historical assets plus **Emerging Markets**: the official MSCI Emerging Markets Net Total Return index (code 891800, USD, unhedged, converted to EUR), with a 0.20%/yr tracker holding cost (assumption). Index codes come from msci.com, never from the `msci-data` docstring (which mislabels 891800 and 664185; docs/PHASE7A_DATA_AUDIT.md). The decision followed exposure to 2013-2019 results, so the expanded universe is not an untouched hypothesis. The previous seven-asset universe stays reproducible as the `universe_variants` entry *Univers historique (7 actifs)*. Global listed real estate is not included: no free, reproducible series covers 2001-2019.
* **`benchmark`**: passive reference (default MSCI World NETR in EUR). It is always loaded, even if not eligible. Equal Weight over the eligible universe is always reported too.
* **Main universe without leverage (investor decision, phase 5).** `leverage: {}` in research.yaml. The decision was taken after 2013-2019 results involving the synthetic Nasdaq 100 x2 had been viewed and is recorded as such in the registry (`kind: decision`). Leverage support, its tests and every past result are preserved and can be re-enabled in a separate configuration. Removing product leverage does not remove equity concentration: Nasdaq 100, Apple, S&P 500, Dow Jones and MSCI World overlap heavily.
* **`leverage`** and **`leverage_costs`**: synthetic daily-reset exposures (`{Nasdaq 100: 2.0}` creates `Nasdaq 100 x2`, which replaces its underlying in the optimizer) and their running cost, `annual_fee + (L - 1) * (short_rate + financing_spread)`, accrued on calendar days.
* **`rates`**: economically distinct roles, each a constant or a registered FRED series used point in time (`src/portfolio_lab/rates.py`): `risk_free` = EUR cash reference of Sharpe ratios and of the Maximum Sharpe objective (mean over each training window / evaluation period; default the OECD euro-area 3-month rate); `financing_base` = short rate of the leveraged product's own currency (default USD 3-month T-bill for Nasdaq 100 x2); `financing_spread` = borrowing spread (0.4%, assumption). No cash position is held, so no interest is credited.
* **`holding_costs`**: annual cost turning an *index* series into an investable exposure (tracker TER, withholding suffered by a UCITS fund), accrued on calendar days: MSCI World 0.20%, S&P 500 0.35%, Gold 0.25%, Emerging Markets 0.20% (assumptions, see docs/DATA_AUDIT.md; the NETR indices are already net of withholding tax, so no further dividend adjustment). Stocks and ETFs priced by adjusted closes keep their embedded fees only.
* **`constraints`**: investor `max_weights` / `min_weights` (fractions; names may be leveraged labels) and a mandatory `provenance` note. Current investor-declared preferences: **Gold <= 10%, Apple <= 40%, Coca-Cola <= 10%** (Gold and Apple confirmed in phase 3, Coca-Cola in phase 7B; all after earlier validation results had been seen; not pre-registered, not optimized). No minimum weight: 0% Emerging Markets is a valid allocation. Edit the numbers, keep the note truthful, *Run All*: they apply to **every** optimized portfolio, frontier point, risk profile, walk-forward fold and to the constrained equal-weight benchmark; infeasible bounds (e.g. caps of the eligible assets summing below 100%) fail explicitly, nothing is relaxed. The unconstrained optimum is shown only as a labelled research comparison.
* **`estimation`**: covariance (`ledoit_wolf` | `sample`), `covariance_frequency` (`daily` | `weekly`, default research setting `weekly` since phase 7B: the last common close of each Friday-ending week, annualized x 52; it limits the downward bias of asynchronous closes on correlations, e.g. MSCI EM vs MSCI World 0.70 daily vs 0.80 weekly over 2001-2012; only the risk model changes), expected returns (`sample` | `bayes_stein`), and `growth_drift` (`sample` | `estimated`): with `estimated`, the growth objective of the frontier and risk profiles uses training returns re-centred on the expected-return estimate (`r - mean(r) + mu`), so risk and path shape are unchanged. `method_variants` lists pre-registered estimation variants compared on the main universe.
* **Anchored expected returns** (`expected_returns: anchored`, phase 6): Black-Litterman posterior with a neutral equilibrium prior implied by the window's ERC portfolio (`pi = delta Sigma w_ERC`, `delta` set so the anchor's implied return equals its sample mean), sample means as views with their sampling uncertainty (`diag(Sigma)/T`) and `tau = 1/T`. It changes *relative* expected returns (unlike a common shrinkage target); used with `growth_drift: estimated`. Limits: a binding volatility ceiling with two active long-only assets is pinned by the constraint whatever the means, and the equilibrium prior rewards covariance with the anchor (it favours high-volatility equities).
* **Resampled efficiency** (`resampling_draws: N`, phase 6): every policy is the average of its optimal weights over N stationary-bootstrap resamples of the training window (Michaud); deterministic seed from the training end date; averaged weights stay within the investor bounds.
* **Equal risk contribution (ERC)** is available as a policy (`walk_forward(..., risk_parity=True)`, `PortfolioOptimizer.equal_risk_contribution`): no expected returns; exact ERC when the investor bounds do not bind, otherwise the bounded portfolio closest to equal relative risk contributions. It is one portfolio, not a frontier.
* **`risk_profiles`**: ceilings on **estimated** annualized volatility. They are not drawdown limits.
* **`protocol`**: `study_end` (<= 2020-01-01), `development_end`, and `analysis_window` (`development` = in-sample analysis before 2013, recommended; `research` = all data before 2020, which overlaps the validation years and is descriptive only).
* **`walk_forward`**: `rolling` | `expanding`, training years, test years 2013-2019, `annual` (buy and hold within the year) | `daily` (legacy constant mix) rebalancing, decision lag, transaction costs in basis points.
* **`universe_variants`**: pre-specified universe comparisons as exclusions (`Sans Apple: [Apple]`). Keep the list short.

To register a new symbol, add an `Asset(...)` entry to `ASSET_CATALOGUE` in `src/portfolio_lab/assets.py` (verified currency, return treatment and source), then reference it in the YAML. `load_config()` / `configure_universe()` remain as package-level APIs for scripts and tests, with legacy defaults; research notebooks must not use them.

## Portfolio accounting (`src/portfolio_lab/simulation.py`)

The optimizer **estimates target weights** from daily return observations. The observation frequency is not a trading frequency: Minimum Volatility and Maximum Sharpe use one-period moments of a static target, while the Maximum CAGR / frontier / risk-profile objective maximizes the historical log growth of a *constant mix* (weights reset at every common observation). The in-sample "model" CAGR, volatility and drawdown shown on the frontier describe that constant mix without costs; they are labelled as such.

How the targets are *implemented* is a separate, explicit convention shared by the in-sample "implemented" metrics (`implemented_metrics`) and the walk-forward:

* **Annual rebalancing (baseline, fixed on economic grounds before measuring):** at the close of the last session of each calendar year the portfolio is traded to its targets; holdings are then fixed and weights drift with prices until the next year-end close.
* **Costs:** `transaction_cost_bps` one-way per unit of traded notional: `cost = c * sum_i |w_target,i - w_drifted,i|`, i.e. every buy and every sell pays c. The first allocation is bought from cash (traded notional 1). The cost is deducted at the rebalance close and booked in the first return after it; the neglected self-financing term is O(c^2).
* **Fully invested, no cash:** weights must sum to one; nothing earns or pays interest except the synthetic leverage financing inside the leveraged NAV.
* `daily` (constant mix) remains available as a labelled model reference; its intra-year trading is not costed, so it is not an investable result.

The remaining gap between the optimizer's constant-mix growth objective and the annually rebalanced implementation (the within-year rebalancing effect) is reported, not hidden: the analysis notebook shows "model" and "implemented" columns side by side.

## Walk-forward methodology (`portfolio_robustness.ipynb`)

For each test year Y in 2013-2019 (strict mode: every requested year must yield a complete fold with >= 200 common sessions in every training and test year, otherwise an explicit error):

1. Training window: the 10 calendar years before Y (rolling), or all history since the data start (expanding check), always preceded by one return-base observation; no history is ever inferred before an asset existed.
2. Expected returns, Ledoit-Wolf covariance, Bayes-Stein intensity (if selected) and all optimizations are fitted on that window only. With `decision_lag_sessions = 1` the final session before Y is excluded from estimation: the decision uses the previous close, the trade happens at the last close before Y.
3. Policies: Maximum Sharpe, Minimum Volatility and each risk profile (maximum historical log growth under the estimated-volatility ceiling; pre-specified fallback to Minimum Volatility when the ceiling is infeasible in a window, flagged in `train_metrics`).
4. Weights are frozen, then held through Y with `annual` rebalancing (they drift with prices). Costs = `transaction_cost_bps` x traded notional, against the drifted holdings (the first allocation is bought from cash), booked on the first test-year return. Equal Weight follows identical rules; the passive benchmark is bought once.
5. The OOS series is the chronological concatenation of test-year returns; CAGR (calendar days), volatility, Sharpe, maximum drawdown, CAGR excluding the best year, gross CAGR and turnover are computed on it, never by averaging annual CAGRs.
6. Uncertainty (descriptive): `(1 + CAGR_policy) / (1 + CAGR_reference) - 1` with a stationary bootstrap of date-paired daily log-differences under three block lengths fixed in advance (automatic Politis-White, 21 and 63 sessions, all reported), plus a leave-one-year-out table. Realized weights are held fixed, so the ranges describe daily sampling noise under stationarity, not regime risk; with seven years they are not significance tests.

Execution timing, precisely: estimation uses observations up to the close of the second-to-last session of year Y-1 (`train_end`); the order is executed at the close of the last session of Y-1 (`rebalance_date`, a next-close execution, not same-close); the return of that session is still earned by the previous holdings; the new holdings earn from the first session of Y. FX for USD assets is the FRED noon fixing of the same date, known before the close.

Design choices: rolling 10-year windows are the primary method; the expanding window is one pre-specified robustness check. Nested walk-forward is **not** implemented: the engine has no tuned hyperparameter, and adding model selection would be the moment to add it. Purged/embargoed CV is unnecessary here (annual, non-overlapping targets with no event labels). Blocked K-fold CV would train on the future and is rejected for a sequential investment decision.

**Universe comparison** runs the identical walk-forward for each pre-specified variant on the same prices and dates; only eligibility changes. Asset subsets are a research choice made with hindsight (e.g. Apple's inclusion), so these comparisons are descriptive, not a search.

**In-sample diagnostics** (frontier, sensitivity map, bootstrap bands, subperiod stability on 2001-2006 / 2007-2012) never use validation years by default and are labelled in-sample everywhere.

## Total investor return and provenance

These series are deliberately distinguished:

* **Price Return** indices omit cash dividends. `^NDX`, `^GSPC`, `^DJI` and `^FCHI` in the original notebook are not transformed into TR indices merely by `auto_adjust=True`.
* **Total Return** includes distributions and reinvestment under a specified benchmark convention.
* **Gross Return** reinvests gross dividends before withholding tax.
* **Net Return** reinvests dividends after the benchmark's assumed withholding tax, which need not equal a particular investor's actual tax.
* **Net Total Return** is MSCI's NETR variant (e.g. MSCI World, index code 990100): net dividends reinvested after MSCI's withholding-tax assumptions. It is an index level, not an ETF adjusted price: its `pct_change()` already is the total return, so no dividend or Yahoo adjustment is ever applied. Levels are USD and unhedged; EUR conversion uses the same EURUSD path as other USD assets.
* **Adjusted price** for equities/ETFs uses Yahoo's split and dividend adjustment, as a practical reinvestment proxy. It is not claimed to be an independently audited gross/net benchmark. ETF adjustments inherit fees and tracking behavior of that ETF.
* **Gold futures quotation** (`GC=F`): Yahoo's continuous front-month series, not back-adjusted, tracks the nearby contract, i.e. approximately spot gold. Audited against GLD over 2004-2019 (docs/DATA_AUDIT.md, criteria written before the comparison): +0.42%/yr versus GLD's 0.40% fee, monthly correlation 0.995, daily discrepancies that reverse (settlement timing), a small roll sawtooth netting out over the year. It is kept as a spot proxy with a 0.25%/yr physical-ETC holding cost; no collateral yield is added (it would double count the carry).

Metadata for every configured exposure includes provider, symbol, instrument, currency, return classification, distribution treatment, source references and limitations. `outputs/provenance.csv` also records actually observed raw start/end, counts, missing values, FX omissions and the final common calendar. The synthetic rows explicitly inherit the underlying provenance and identify the native-currency daily reset.

Genuine TR benchmark sources are preferred when their histories are accessible and usable. If a history is absent, the provider fails explicitly: **there is no automatic switch to a price index or ETF**. Any deliberately chosen adjusted ETF proxy is configured and disclosed with its own shorter history, expenses and benchmark mismatch. A future provider can supply the desired benchmark without changing the engine.

Benchmark references: [Nasdaq XNDX](https://indexes.nasdaqomx.com/Index/Overview/xndx), [S&P 500](https://www.spglobal.com/spdji/en/indices/equity/sp-500/), [Dow Jones Industrial Average](https://www.spglobal.com/spdji/en/indices/equity/dow-jones-industrial-average/) and [CAC 40 GR](https://live.euronext.com/en/product/indices/QS0011131834-XPAR). See the executed provenance table for the configured Yahoo symbols and actual available dates.

## Benchmark comparability

* **Constrained Equal Weight (investable, primary reference):** the feasible portfolio closest (Euclidean) to 1/n under exactly the investor bounds and eligibility of the policies (`constrained_equal_weights`, deterministic, parameter-free); same annual rebalancing, execution timing and costs.
* **Equal Weight (unconstrained, descriptive):** 1/n over the optimizer universe (it includes the synthetic leveraged series when one replaces its underlying) and ignores investor caps, so it may be non-investable under the investor's policy.
* **Passive benchmark (MSCI World NETR in EUR):** net-dividend index made investable with a 0.20%/yr tracker holding cost; bought once at the first rebalance close (one cost), then held.
* Index series (S&P 500 gross TR, MSCI World net TR, gold spot proxy) carry explicit holding costs; stocks and ETFs keep their adjusted-close basis (pre-tax). Remaining basis differences are documented in docs/DATA_AUDIT.md.
* All series are converted to EUR before returns; all comparisons share the same dates, currency, execution convention and Sharpe risk-free rate.

## Investor constraints

Configured in `config/research.yaml` (`constraints`), `Config.max_weights` / `Config.min_weights` become SLSQP bounds for every portfolio, frontier point, risk profile and walk-forward fold; infeasible combinations (caps summing below 100%, floors above 100% or above a cap) fail before optimizing. Bounds on an asset excluded by eligibility are moot and ignored; any other unknown name fails. Assets whose 100% position is outside the bounds leave the single-asset dominance check. `compare_investor_constraints(prices, config)` shows the unconstrained reference next to the constrained optimum on the same data (difference = constrained - unconstrained): the in-sample historical cost of a personal policy, not evidence that either portfolio is superior. Equal Weight stays 1/n even when it violates a cap (it is a benchmark, not a policy).

### Sensitivity to one asset's weight

`sharpe_weight_profile(prices, config, "Gold")` is a descriptive, in-sample diagnostic: it fixes one optimizer asset at 0%–100% (1% steps, plus the exact unconstrained optimum, which it recovers) and re-optimizes all other weights for Maximum Sharpe at each point. It reports CAGR, volatility, realized Sharpe and the optimizer's own Sharpe objective, the loss versus the unconstrained optimum and the share of optimal Sharpe retained, plus the weight ranges retaining ≥ 99%, 98% and 95% of it. Investor limits are not applied to the map (an asset's limit is only marked on the chart from `plot_weight_profile`). The ranges are never used as constraints and are not chosen with out-of-sample results; `portfolio_analysis.ipynb` shows the table and chart.

### Bootstrap uncertainty of the frontier (in-sample)

`portfolio_lab.bootstrap.bootstrap_frontier(prices, config, replications=500, seed=0)` asks how much the *estimated* frontier and Maximum Sharpe weights move when the historical sample is perturbed. The methodology was fixed before any result was inspected and is not tuned: a stationary bootstrap (Politis & Romano 1994) of whole daily return rows, with expected block length from Politis & White (2004) as corrected by Patton, Politis & White (2009) (`arch.bootstrap.optimal_block_length`, mean of the per-asset values, at least 1), 500 replications and seed 0. Each replication rebuilds prices on the original dates and runs the engine with the configured estimators (Minimum Volatility, Maximum CAGR, multi-start Maximum Sharpe, and the frontier rule at 25 common estimated-volatility ceilings). Bands are percentiles over replications where a ceiling is feasible (80%: 10th–90th, 95%: 2.5th–97.5th), drawn only where ≥ 95% of replications are feasible; Maximum Sharpe weights get 5th/25th/50th/75th/95th percentiles. Replications run in parallel processes (one BLAS thread each) from indices drawn up front, so results do not depend on the worker count. These are *bootstrap uncertainty bands*, an in-sample diagnostic distinct from the near-optimal map (flatness of the objective around one estimate) and from the walk-forward (out-of-sample).

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

With `leverage_costs`, each interval also pays `(annual_fee + (L - 1) * financing_rate) * calendar_days / 365.25`, so `NAV(t) = NAV(t-1) * max(0, 1 + L * r(t) - drag(t))`. The research configuration uses a constant 0.6% fee and 1.5% financing rate (2.1% per year for x2): a crude average, since actual short rates varied from about 0% to 5% over 2001-2019. Tracking error, taxes, liquidity, intraday rebalancing and the variance drag of real products beyond the daily-reset formula are not modelled. It is an exposure model, not a reconstruction of a traded leveraged ETF.

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

The optimizer's risk model is one covariance estimate, `portfolio_lab.covariance.estimate_covariance`, selected by `Config.covariance_method`: `"ledoit_wolf"` (default; scikit-learn `LedoitWolf` with its data-driven shrinkage intensity) or `"sample"` (pandas `ddof=1`, which reproduces the earlier engine exactly). It is fitted on the returns of the prices being optimized (in walk-forward, each training window only), sampled according to `Config.covariance_frequency`: daily returns annualized by `trading_days`, or weekly returns (`covariance.weekly_returns`: last common close of each W-FRI week, a holiday Friday falls back to the last common close of that week, a week without a common close is skipped and never filled) annualized by 52 (`estimate_covariance_from_prices`). Expected returns, the growth objective and all realized metrics stay daily. Minimum volatility, the Sharpe denominator, volatility ceilings, the frontier grid and dominance use this risk model, reported as `Estimated volatility = sqrt(w.T @ Sigma @ w)`. `Volatility`, `Sharpe`, CAGR and drawdown remain realized historical metrics: volatility is the sample standard deviation of the weighted return series. With `"sample"` and daily sampling both volatilities coincide. The estimator and its shrinkage intensity are printed by the notebooks and recorded in `sanity-checks.json`.

Expected returns are used only by the Maximum Sharpe objective; Minimum Volatility uses covariance only, and Maximum CAGR, the frontier and named risk profiles maximize realized historical log growth. One estimator, `portfolio_lab.expected_returns.estimate_expected_returns`, is selected by `Config.expected_return_method`: `"sample"` (default; arithmetic mean of daily returns × `trading_days`, the project's reference behavior) or `"bayes_stein"`. Bayes-Stein is Jorion (1986, *JFQA* 21(3), 279–292), computed in daily units from the optimized window only: `Σ = S·(T−1)/(T−N−2)`, target `μ0 = 1′Σ⁻¹m / 1′Σ⁻¹1` (the minimum-variance portfolio mean), intensity `w = (N+2) / ((N+2) + T·(m−μ0)′Σ⁻¹(m−μ0))` in (0, 1] by construction, `μ_BS = (1−w)m + wμ0`, annualized once. No intensity is chosen by hand; walk-forward fits it per training window. It is reported as `Estimated return`; `Mean return annualized` and `Sharpe` stay realized historical metrics. Only Jorion's mean estimator is used; the covariance remains the configured covariance estimator.

**Bayes-Stein experiment (2026-10-08, superseded).** An earlier one-off walk-forward comparison of the sample mean and Bayes-Stein estimators used data through 2026 and therefore the now-locked holdout; its figures are deliberately not reproduced here (see docs/HOLDOUT_EXPOSURE.md). The default remains `"sample"`; any new comparison must use the 2013-2019 protocol and be recorded in the registry.

SLSQP first solves minimum variance and unrestricted maximum historical log growth. The upper frontier maximizes `mean(log(1 + r_p)) * 252` under volatility **ceilings**, spanning minimum risk to the maximum-growth endpoint. The growth objective has the same optimum as calendar CAGR because study duration is fixed. Each named target solves the same problem; a ceiling below minimum achievable volatility is reported as infeasible with missing weights. Above the maximum-growth risk, it reuses that optimum and reports unused risk allowance. Target risk is not an equality.

Maximum Sharpe uses arithmetic mean excess return and deterministic starts at equal weights, minimum risk, maximum growth and all asset vertices. With nonpositive excess returns this objective is not globally quasiconcave: multiple starts reduce sensitivity but do not constitute a universal global-optimality proof. With zero sample volatility, numerical denominator floors keep optimization evaluable; the reported ratio remains undefined if variance is exactly zero.

The solver uses explicit gradients, scaled risk constraints and a documented fallback from `ftol=1e-10` to `1e-7`, with at most 1000 iterations each. Every attempted status, message, raw weight sum and raw minimum weight is recorded. Weight cleanup is limited to tolerated numerical errors, followed by actual risk-ceiling validation (tolerance `1e-7`). Failures raise exceptions. Frontier monotonicity and dominance over each single asset at its exact risk are checked, alongside covariance PSD, weighted-return risk and independently compounded CAGR. Numerical floors affect boundary solver evaluation only; reported wipeout CAGR is exact.

This frontier maximizes realized growth in-sample and is sensitive to the historical interval, vendor data and extreme returns. The `CAGR` of a frontier point is a realized historical CAGR of a daily-rebalanced constant mix, not an expected CAGR; `Estimated return` is an arithmetic expected return. Out-of-sample evidence comes only from the walk-forward.

## Review evidence and regression

`outputs/review.md` prints provenance, real FX samples, asset performance, all optimized portfolios and full weights, all frontier points, exact-risk asset dominance, solver attempts and numerical sanity checks. Corresponding CSVs retain precision and allow independent review. `sanity-checks.json` contains all weight sums and their maximum error, maximum risk-ceiling violation, minimum weight, invalid return count, common dates/count, covariance minimum eigenvalue and solver success counts. `study-coverage.json` distinguishes the latest raw-asset start, EUR-normalized availability, FX limitations and any delay from the intersection of observed calendars. Charts and the fully executed notebook are also saved.

`pytest` covers deterministic schema/calendar rejection, availability metadata, FX direction and independent FX moves, returns without filling, leverage wipeout and pre-alignment compounding, independent metric expected values, analytic minimum-risk weights, independent portfolio compounding/risk, infeasible targets, universe selection and Sharpe with negative excess returns. Regression tests extract and execute only the original notebook's pure leverage and performance functions on identical inputs: those calculations must agree. They do not execute the original network cells.

After running the analysis notebook, `.\.venv\Scripts\python.exe scripts/check_regression.py` also executes the archived optimization/target cells on exactly the same exported EUR prices, and re-runs the refactored engine with the archived assumptions (sample covariance, sample mean, no investor bounds, all assets eligible) instead of comparing against the research configuration. It validates the archived safeguards and compares portfolio metrics/weights with the new engine. `outputs/engine-regression.csv` records the differences; this comparison deliberately excludes source/FX changes.

The CAC 40 entry uses **`PX1GR.PA`**, Yahoo's CAC 40 Gross Return Index in EUR (gross dividends already in the level, so `auto_adjust=False`). A past source audit found that Yahoo's valid daily closes for this symbol stop on 2015-12-18, so any universe containing it is truncated there and cannot support the 2013-2019 walk-forward; the strict fold check fails explicitly in that case. It is not in the default universe.

S&P 500 likewise uses a genuine gross-return benchmark, `^SP500TR`. QQQ and DIA remain explicit adjusted ETF proxies for the Nasdaq-100 and Dow Jones exposures; tested Yahoo `^XNDX` and `^DJITR` histories were unavailable. Those tested symbols do not establish that every Yahoo spelling or another provider lacks TR data. The current benchmark availability and provenance reports show the actual configured sources.

Architectural changes alone preserve formulas. Methodological changes intentionally alter final results: dividend-inclusive benchmark/proxy selection, EUR translation, available histories/common calendar and explicit unlevered FX for USD synthetic products. No assertion requires new investment metrics to match the old mixed-currency price-index study. The detailed run evidence describes any inaccessible benchmark and selected proxy without concealing the exposure change.
