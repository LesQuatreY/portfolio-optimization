"""Subperiod stability (in-sample) and annual walk-forward out-of-sample evaluation.

Timing convention (walk-forward). For each calendar test year Y:

* Estimation uses common observations from the training window only, ending at
  ``train_end``. With ``decision_lag_sessions = k`` the last k sessions before Y are
  excluded from estimation: the decision is made on the close of ``train_end`` and
  executed at the close of ``rebalance_date`` (the last session before Y), using no
  price observed after ``train_end``.
* Test returns are the returns ending inside Y, the first one measured from the
  ``rebalance_date`` close. No observation of Y can influence Y's weights.

Holding convention. ``rebalance="annual"`` trades once to the new targets at the
rebalance close and lets weights drift with prices during Y (buy and hold within the
year). ``rebalance="daily"`` is the legacy constant mix, rebalanced back to target at
every common observation (intra-year trading is then not costed). Transaction costs
are ``transaction_cost_bps`` per unit of traded notional, charged at the rebalance
close against the drifted holdings (the first allocation is bought from cash) and
booked in the first test-year return.

Returns are indexed by the end date of their interval. A window's returns are those
ending inside it; the first one starts from the last observation before the window
(the "return base"), which always precedes the window and is never a test date.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
import numpy as np
import pandas as pd
from .config import Config, WalkForwardSettings, eligible_names, with_eligible
from .covariance import COVARIANCE_METHODS
from .expected_returns import EXPECTED_RETURN_METHODS
from .metrics import compute_asset_metrics
from .optimization import PortfolioOptimizer, constrained_equal_weights, select_frontier_assets
from .protocol import assert_dates_before_holdout
from .returns import simple_returns
from .simulation import hold_returns

OPTIMIZED = ("Maximum Sharpe", "Minimum Volatility")
# Unconstrained descriptive reference: 1/n over the optimizer universe, ignoring investor bounds
# (it may therefore be non-investable under the investor's policy).
EQUAL_WEIGHT = "Equal Weight"
# Investable baseline: feasible weights closest to 1/n under the same bounds as every policy.
CONSTRAINED_EQUAL_WEIGHT = "Constrained Equal Weight"
REFERENCES = (CONSTRAINED_EQUAL_WEIGHT, EQUAL_WEIGHT)
# In-sample subperiods inside the development period only (validation years stay unseen).
DEFAULT_PERIODS = (("2001-01-01", "2006-12-31"), ("2007-01-01", "2012-12-31"))
# Weights below this are treated as "effectively zero" in stability diagnostics.
ZERO_TOLERANCE = 1e-4
# Strict folds require at least this many common sessions in every training and test year.
MIN_SESSIONS_PER_YEAR = 200
_FROM_CONFIG = object()


def window_prices(prices: pd.DataFrame, start, end=None) -> pd.DataFrame:
    """Observations in [start, end], preceded by the last earlier observation if one exists."""
    start = pd.Timestamp(start)
    end = prices.index[-1] if end is None else pd.Timestamp(end)
    before = prices.loc[prices.index < start]
    inside = prices.loc[(prices.index >= start) & (prices.index <= end)]
    return pd.concat([before.iloc[-1:], inside]) if len(before) else inside


def optimize_weights(train_prices: pd.DataFrame, config: Config,
                     portfolios: Sequence[str] = OPTIMIZED) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    """Engine portfolios estimated on exactly these prices (and nothing else), including the covariance fit."""
    optimizer = PortfolioOptimizer(train_prices, config)
    core = optimizer.core_portfolios()
    weights = {name: core[name]["weights"] for name in portfolios}
    keys = ("CAGR", "Volatility", "Estimated volatility", "Sharpe", "Max Drawdown")
    metrics = pd.DataFrame({name: {k: core[name][k] for k in keys} for name in portfolios}).T
    for column, shrinkage in (("Covariance shrinkage", optimizer.estimate.shrinkage),
                              ("Expected-return shrinkage", optimizer.expected.shrinkage)):
        metrics[column] = np.nan if shrinkage is None else shrinkage
    return weights, metrics


EQUAL_RISK = "Equal Risk Contribution"


def fit_policies(train_prices: pd.DataFrame, config: Config, risk_profiles: bool = False,
                 risk_parity: bool = False) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    """Every evaluated policy fitted on training prices only.

    Risk profiles maximize historical log growth under their estimated-volatility ceiling
    (the frontier rule). Pre-specified fallback: when a ceiling is below the training
    window's minimum achievable volatility, the policy holds Minimum Volatility (flagged).
    With `config.resampling_draws > 0`, every policy is the average of its weights over that many
    stationary-bootstrap resamples of the training window (resampled efficiency, Michaud).
    """
    if config.resampling_draws:
        return _resampled_policies(train_prices, config, risk_profiles, risk_parity)
    optimizer = PortfolioOptimizer(train_prices, config)
    core = optimizer.core_portfolios()
    fitted = {name: core[name] for name in OPTIMIZED}
    fallback = {name: False for name in OPTIMIZED}
    unused = {name: False for name in OPTIMIZED}
    minimum, maximum = core["Minimum Volatility"], core["Maximum CAGR"]
    if risk_profiles:
        for name, ceiling in config.targets:
            point = optimizer.target(ceiling, minimum, maximum, name)
            fallback[name] = point["weights"] is None
            # Ceiling above the maximum-growth portfolio's risk: the profile IS Maximum CAGR (not binding).
            unused[name] = (not fallback[name]) and ceiling >= maximum["Estimated volatility"]
            fitted[name] = minimum if fallback[name] else point
    if risk_parity:
        fitted[EQUAL_RISK] = optimizer.equal_risk_contribution()
        fallback[EQUAL_RISK] = unused[EQUAL_RISK] = False
    keys = ("CAGR", "Volatility", "Estimated volatility", "Sharpe", "Max Drawdown")
    metrics = pd.DataFrame({name: {k: p[k] for k in keys} for name, p in fitted.items()}).T
    metrics["Fallback to Minimum Volatility"] = pd.Series(fallback)
    metrics["Ceiling not binding (Maximum CAGR)"] = pd.Series(unused)
    # Feasible estimated-risk range of the training window (same for every row).
    metrics["Feasible minimum volatility"] = minimum["Estimated volatility"]
    metrics["Maximum-growth volatility"] = maximum["Estimated volatility"]
    for column, shrinkage in (("Covariance shrinkage", optimizer.estimate.shrinkage),
                              ("Expected-return shrinkage", optimizer.expected.shrinkage)):
        metrics[column] = np.nan if shrinkage is None else shrinkage
    return {name: p["weights"] for name, p in fitted.items()}, metrics


def _resampled_policies(train_prices: pd.DataFrame, config: Config, risk_profiles: bool, risk_parity: bool):
    """Average each policy's optimal weights over stationary-bootstrap resamples of the training window.

    Whole dates are resampled jointly (Politis-White block length of the training returns). The seed is
    the training end date (YYYYMMDD), so a given window always gives the same draws. The averaged weights
    stay within the investor bounds (convex set). Reported metrics are those of the averaged weights on
    the actual training data; boolean flags become the share of resamples in which they occurred.
    """
    from .bootstrap import bootstrap_indices, resampled_prices, stationary_block_length
    base = replace(config, resampling_draws=0)
    returns = simple_returns(train_prices)
    seed = int(train_prices.index[-1].strftime("%Y%m%d"))
    indices = bootstrap_indices(len(returns), stationary_block_length(returns), config.resampling_draws, seed)
    point_weights, point_metrics = fit_policies(train_prices, base, risk_profiles, risk_parity)
    sums = {name: np.zeros(train_prices.shape[1]) for name in point_weights}
    flags = {column: pd.Series(0., index=point_metrics.index) for column in
             ("Fallback to Minimum Volatility", "Ceiling not binding (Maximum CAGR)")}
    used = 0
    for row in indices:
        try:
            weights, metrics = fit_policies(resampled_prices(train_prices, row), base, risk_profiles, risk_parity)
        except (RuntimeError, ValueError):
            continue
        used += 1
        for name in sums:
            sums[name] += weights[name].reindex(train_prices.columns).to_numpy()
        for column in flags:
            flags[column] += metrics[column].astype(float)
    if not used:
        raise RuntimeError("Every resampled optimization failed.")
    optimizer = PortfolioOptimizer(train_prices, base)
    averaged = {name: pd.Series(total / used, index=train_prices.columns) for name, total in sums.items()}
    keys = ("CAGR", "Volatility", "Estimated volatility", "Sharpe", "Max Drawdown")
    metrics = pd.DataFrame({name: {k: optimizer.metrics(w.to_numpy())[k] for k in keys}
                            for name, w in averaged.items()}).T
    for column, total in flags.items():
        metrics[column] = total / used
    for column in ("Feasible minimum volatility", "Maximum-growth volatility", "Covariance shrinkage",
                   "Expected-return shrinkage"):
        if column in point_metrics:
            metrics[column] = point_metrics[column]
    metrics["Resamples used"] = used
    return averaged, metrics


def hhi(weights: pd.DataFrame) -> pd.Series:
    """Herfindahl-Hirschman concentration, sum of squared weights (1/n equal weight .. 1 single asset)."""
    return (weights ** 2).sum(axis=1)


def concentration(weights: pd.DataFrame) -> pd.DataFrame:
    index = hhi(weights)
    return pd.DataFrame({"HHI": index, "Effective assets": 1 / index})


def turnover(weights: pd.DataFrame) -> pd.Series:
    """One-way turnover between consecutive target allocations: 0.5 * sum(|w_t - w_{t-1}|).

    The first allocation has no predecessor (NaN). Within-period drift and rebalancing are
    not included; see WalkForwardResult.trading for the turnover actually traded.
    """
    return 0.5 * weights.diff().abs().sum(axis=1, min_count=1)


def weight_stability(weights: pd.DataFrame, zero_tolerance: float = ZERO_TOLERANCE) -> pd.DataFrame:
    """Per-asset weight statistics across estimation windows (rows); std is the sample std (ddof=1)."""
    return pd.DataFrame({"Mean weight": weights.mean(), "Min weight": weights.min(),
                         "Max weight": weights.max(), "Std weight": weights.std(ddof=1),
                         "Zero-weight share": (weights.abs() < zero_tolerance).mean()}).rename_axis("Asset")


def growth_metrics(returns: pd.DataFrame, base_date: pd.Timestamp, config: Config) -> pd.DataFrame:
    """Engine metric conventions on NAVs compounded from returns, starting at 1 on base_date."""
    nav = pd.concat([pd.DataFrame(1., index=[base_date], columns=returns.columns), (1 + returns).cumprod()])
    metrics = compute_asset_metrics(nav, config.trading_days, config.risk_free_rate, config.calendar_days_per_year)
    return metrics.loc[returns.columns]


@dataclass
class SubperiodResult:
    periods: pd.DataFrame
    weights: pd.DataFrame
    metrics: pd.DataFrame
    stability: pd.DataFrame


def subperiod_stability(prices: pd.DataFrame, config: Config,
                        periods: Sequence[tuple[str, str | None]] = DEFAULT_PERIODS,
                        portfolios: Sequence[str] = OPTIMIZED,
                        zero_tolerance: float = ZERO_TOLERANCE) -> SubperiodResult:
    """Re-run the engine independently on each period. In-sample in every period: NOT out-of-sample."""
    prices = prices[select_frontier_assets(config)]
    rows, weights, metrics = [], {}, {}
    for start, end in periods:
        window = window_prices(prices, start, end)
        inside = window.loc[window.index >= pd.Timestamp(start)]
        if len(inside) < 2:
            raise ValueError(f"Period {start} - {end or 'latest'} has no usable common history.")
        label = f"{inside.index[0]:%Y-%m-%d} - {inside.index[-1]:%Y-%m-%d}"
        rows.append({"Period": label, "First date": inside.index[0], "Last date": inside.index[-1],
                     "Return base date": window.index[0], "Returns": len(window) - 1})
        selected, summary = optimize_weights(window, config, portfolios)
        for name in portfolios:
            weights[(name, label)] = selected[name]
            metrics[(name, label)] = summary.loc[name]
    weights = pd.DataFrame(weights).T.rename_axis(["Portfolio", "Period"])
    metrics = pd.DataFrame(metrics).T.rename_axis(["Portfolio", "Period"])
    stability = pd.concat({name: weight_stability(weights.loc[name], zero_tolerance) for name in portfolios},
                          names=["Portfolio"])
    return SubperiodResult(pd.DataFrame(rows).set_index("Period"), weights, metrics, stability)


@dataclass(frozen=True)
class WalkForwardFold:
    test_year: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    return_base: pd.Timestamp
    train_returns: int
    test_returns: int
    complete_test_year: bool
    # Close at which the new targets are traded (last session before the test year).
    rebalance_date: pd.Timestamp | None = None
    window: str = "rolling"


def walk_forward_folds(index: pd.DatetimeIndex, train_years: int = 10, *,
                       first_test_year: int | None = None, last_test_year: int | None = None,
                       window: str = "rolling", decision_lag: int = 0, end_exclusive=None,
                       include_partial_final_year: bool = True,
                       min_sessions_per_year: int = 0) -> list[WalkForwardFold]:
    """Calendar-year folds: train on the `train_years` full years before each test year.

    A rolling fold needs a full training window, i.e. an observation before its first
    training year to serve as the return base. An expanding fold trains on all history
    since the first observation but is only formed for the same years as the rolling
    design, so both are comparable.

    Without explicit test years, infeasible years are skipped (legacy behaviour) and the
    last test year is flagged incomplete when the data stop inside it. When
    `first_test_year`/`last_test_year` are given, every requested year must yield a
    valid fold, otherwise a ValueError explains why: nothing is silently dropped.
    A final year counts as complete when the data continue after it, or when the
    exclusive study end is the next 1 January and the data reach late December.
    """
    if not isinstance(train_years, int) or train_years < 1:
        raise ValueError("Training window must be a positive whole number of years.")
    if window not in ("rolling", "expanding"):
        raise ValueError(f"Unknown walk-forward window '{window}'.")
    if not isinstance(decision_lag, int) or decision_lag < 0:
        raise ValueError("Decision lag must be a nonnegative whole number of sessions.")
    if not isinstance(index, pd.DatetimeIndex) or not len(index) or not index.is_monotonic_increasing \
            or not index.is_unique:
        raise ValueError("Walk-forward needs a sorted, unique, nonempty DatetimeIndex.")
    assert_dates_before_holdout(index, "Walk-forward calendar")
    years = sorted(set(index.year))
    requested = None
    if first_test_year is not None or last_test_year is not None:
        low = years[0] if first_test_year is None else first_test_year
        high = years[-1] if last_test_year is None else last_test_year
        if low > high:
            raise ValueError("First test year must not be after the last test year.")
        requested = list(range(low, high + 1))
    sessions = pd.Series(1, index=index).groupby(index.year).sum()
    folds = []
    for test_year in requested or years:
        first_train = pd.Timestamp(year=test_year - train_years, month=1, day=1)
        year_start = pd.Timestamp(year=test_year, month=1, day=1)
        next_start = pd.Timestamp(year=test_year + 1, month=1, day=1)
        test = index[(index >= year_start) & (index < next_start)]
        prior = index[index < year_start]
        problem = None
        if index[0] >= first_train:
            problem = (f"needs an observation before {first_train.date()} to start a {train_years}-year "
                       "training window (no history is ever inferred before an asset existed)")
        elif not len(test):
            problem = "has no observations"
        elif len(prior) < decision_lag + 2:
            problem = "has too little history before it"
        if problem is None:
            rebalance = prior[-1]
            train_end = prior[-1 - decision_lag]
            return_base = index[index < first_train][-1] if window == "rolling" else index[0]
            train = index[(index > return_base) & (index <= train_end)]
            complete = bool(index[-1] > test[-1]) or (
                end_exclusive is not None and pd.Timestamp(end_exclusive) <= next_start
                and test[-1] >= pd.Timestamp(year=test_year, month=12, day=20))
            sparse = [year for year in range(first_train.year, test_year + 1)
                      if sessions.get(year, 0) < min_sessions_per_year]
            if len(train) < 2:
                problem = "has fewer than two training returns"
            elif not complete and not include_partial_final_year:
                problem = f"is incomplete (data end on {index[-1].date()})"
            elif sparse:
                problem = f"has fewer than {min_sessions_per_year} common sessions in {sparse}"
        if problem is not None:
            if requested is not None:
                raise ValueError(f"Walk-forward test year {test_year} {problem}.")
            continue
        folds.append(WalkForwardFold(test_year, train[0], train_end, test[0], test[-1], return_base,
                                     len(train), len(test), complete, rebalance, window))
    if not folds:
        raise ValueError(f"Common history is too short for a {train_years}-year training window.")
    return folds


@dataclass
class WalkForwardResult:
    folds: list[WalkForwardFold]
    weights: dict[str, pd.DataFrame]
    oos_returns: pd.DataFrame
    nav: pd.DataFrame
    metrics: pd.DataFrame
    train_metrics: pd.DataFrame
    turnover: pd.DataFrame
    concentration: pd.DataFrame
    stability: pd.DataFrame
    covariance_estimator: str = "Sample"
    expected_return_estimator: str = "Sample mean"
    # Returns before transaction costs (identical to oos_returns when costs are zero).
    gross_returns: pd.DataFrame | None = None
    gross_metrics: pd.DataFrame | None = None
    # One-way turnover actually traded at each rebalance (drifted -> target; first year from cash).
    trading: pd.DataFrame | None = None
    costs: pd.DataFrame | None = None
    settings: WalkForwardSettings | None = None
    strategies: tuple[str, ...] = (*OPTIMIZED, CONSTRAINED_EQUAL_WEIGHT, EQUAL_WEIGHT)
    benchmark: str | None = None
    universe: tuple[str, ...] = ()
    # The exact configuration evaluated (variant, method or check), for the experiment registry.
    config: Config | None = None

    @property
    def fold_table(self) -> pd.DataFrame:
        return pd.DataFrame([vars(f) for f in self.folds]).set_index("test_year")

    @property
    def policies(self) -> list[str]:
        """Fitted (optimized) policies, excluding the Equal Weight and passive benchmarks."""
        return [name for name in self.strategies if name not in REFERENCES]

    @property
    def benchmarks(self) -> list[str]:
        return [name for name in REFERENCES if name in self.strategies] + ([self.benchmark] if self.benchmark else [])

    def annual_comparison(self, strategy: str = "Maximum Sharpe",
                          benchmarks: Sequence[str] | None = None) -> "RelativePerformance":
        """Calendar-year OOS comparison of one strategy with the benchmarks (default: Equal Weight + passive)."""
        benchmarks = [c for c in self.benchmarks if c in self.oos_returns] if benchmarks is None else list(benchmarks)
        complete = {f.test_year: f.complete_test_year for f in self.folds}
        return relative_annual_performance(self.oos_returns[[strategy, *benchmarks]], strategy, benchmarks,
                                           complete)

    def annual_returns(self) -> pd.DataFrame:
        return calendar_year_returns(self.oos_returns)

    def summary(self) -> pd.DataFrame:
        """Net OOS metrics plus year concentration, gross CAGR and mean traded turnover."""
        table = self.metrics[["CAGR", "Volatility annualized", "Sharpe", "Max Drawdown", "Calmar"]].copy()
        annual = self.annual_returns()
        best = annual.idxmax()
        rest = {name: float((1 + annual[name].drop(best[name])).prod()) for name in annual}
        years = (self.nav.index[-1] - self.nav.index[0]).days / 365.25
        dropped = years - 1
        table["CAGR excluding best year"] = pd.Series(
            {name: value ** (1 / dropped) - 1 if dropped > 0 else np.nan for name, value in rest.items()})
        table["Best year"] = best.astype(int)
        table["Worst year return"] = annual.min()
        if self.gross_metrics is not None:
            table["Gross CAGR (before costs)"] = self.gross_metrics["CAGR"]
        if self.trading is not None:
            # Annual rebalances only: the initial purchase from cash is excluded from the mean.
            later = self.trading.iloc[1:]
            table["Mean traded turnover"] = later.mean() if len(later) else np.nan
        return table.loc[self.oos_returns.columns]


def calendar_year_returns(returns: pd.DataFrame) -> pd.DataFrame:
    """Compound returns ending in each calendar year: prod(1 + r) - 1."""
    return (1 + returns).groupby(returns.index.year).prod().sub(1).rename_axis("Year")


@dataclass
class RelativePerformance:
    """Year-by-year strategy vs benchmark results; excess = strategy - benchmark annual return."""
    strategy: str
    annual_returns: pd.DataFrame
    excess: pd.DataFrame
    complete: pd.Series
    summary: pd.DataFrame

    def year_labels(self) -> list[str]:
        return [str(year) if done else f"{year} YTD" for year, done in self.complete.items()]

    @property
    def table(self) -> pd.DataFrame:
        table = pd.concat([self.annual_returns, self.excess.add_prefix("vs ")], axis=1)
        return table.set_axis(self.year_labels()).rename_axis("Year")

    def formatted(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Display copies: returns/excess as signed percentages, counts as 'k / N'."""
        table = self.table.map(lambda value: f"{value:+.1%}")
        summary = self.summary.copy()
        for column in ("Wins", "Losses", "Ties"):
            summary[column] = [f"{k} / {n}" for k, n in zip(summary[column], summary["Years"])]
        for column in ("Win rate", "Mean excess", "Median excess", "Mean excess ex best year",
                       "Best excess", "Worst excess"):
            summary[column] = summary[column].map(lambda value: f"{value:+.1%}" if "excess" in column
                                                  else f"{value:.0%}")
        return table, summary.drop(columns="Years")


def relative_annual_performance(returns: pd.DataFrame, strategy: str, benchmarks: Sequence[str],
                                complete: Mapping[int, bool] | None = None, *,
                                tie_tolerance: float = 1e-12) -> RelativePerformance:
    """Annual OOS returns and consistency statistics of `strategy` against each benchmark.

    Every calendar year present is kept, including an incomplete final year (flagged via
    `complete`). |excess| <= tie_tolerance is a tie, reported separately; win rate is
    wins / all years. Best/worst years are the largest/smallest annual excess returns.
    """
    annual = calendar_year_returns(returns[[strategy, *benchmarks]])
    excess = pd.DataFrame({name: annual[strategy] - annual[name] for name in benchmarks})
    flags = pd.Series({year: True if complete is None else bool(complete.get(year, True))
                       for year in annual.index}, name="Complete").rename_axis("Year")
    labels = dict(zip(annual.index, [str(y) if flags[y] else f"{y} YTD" for y in annual.index]))
    rows = {}
    for name in benchmarks:
        diff = excess[name]
        ties = diff.abs() <= tie_tolerance
        best, worst = diff.idxmax(), diff.idxmin()
        rows[name] = {"Years": len(diff), "Wins": int((diff > tie_tolerance).sum()),
                      "Losses": int((diff < -tie_tolerance).sum()), "Ties": int(ties.sum()),
                      "Win rate": float((diff > tie_tolerance).mean()),
                      "Mean excess": float(diff.mean()), "Median excess": float(diff.median()),
                      "Mean excess ex best year": float(diff.drop(best).mean()) if len(diff) > 1 else np.nan,
                      "Best year": labels[best], "Best excess": float(diff[best]),
                      "Worst year": labels[worst], "Worst excess": float(diff[worst])}
    summary = pd.DataFrame(rows).T.rename_axis(f"{strategy} vs")
    return RelativePerformance(strategy, annual, excess, flags, summary)


def walk_forward(prices: pd.DataFrame, config: Config, *, train_years: int | None = None,
                 benchmark=_FROM_CONFIG, include_partial_final_year: bool | None = None,
                 zero_tolerance: float = ZERO_TOLERANCE, settings: WalkForwardSettings | None = None,
                 risk_profiles: bool = False, rates=None, risk_parity: bool = False) -> WalkForwardResult:
    """Annual walk-forward: estimate on train years only, freeze, apply to the next year only.

    Strategies: the engine's Maximum Sharpe and Minimum Volatility (plus the configured risk
    profiles when `risk_profiles=True`), Equal Weight over the same eligible universe (same
    holding and cost conventions), and the passive benchmark series (buy and hold; only the
    initial purchase is costed). Every reported return is a test return; no observation of a
    test year enters the estimation of its own weights.

    `settings` defaults to config.walk_forward; `train_years` overrides its training length.
    `benchmark` defaults to config.benchmark (None = no passive benchmark).
    `rates` (portfolio_lab.rates.Rates): when given, each fold's Maximum Sharpe objective uses the mean
    risk-free rate published over its training window, and OOS Sharpe ratios use the mean over the test
    period; otherwise config.risk_free_rate is used throughout.
    """
    settings = config.walk_forward if settings is None else settings
    if train_years is not None:
        settings = replace(settings, train_years=train_years)
    benchmark = config.benchmark if benchmark is _FROM_CONFIG else benchmark
    strict = settings.first_test_year is not None or settings.last_test_year is not None
    if include_partial_final_year is None:
        include_partial_final_year = not strict
    universe = prices[select_frontier_assets(config)]
    if benchmark is not None and benchmark not in prices:
        raise ValueError(f"Benchmark '{benchmark}' is not in the configured price data.")
    folds = walk_forward_folds(universe.index, settings.train_years, first_test_year=settings.first_test_year,
                               last_test_year=settings.last_test_year, window=settings.window,
                               decision_lag=settings.decision_lag_sessions, end_exclusive=config.end,
                               include_partial_final_year=include_partial_final_year,
                               min_sessions_per_year=MIN_SESSIONS_PER_YEAR if strict else 0)
    policies = [*OPTIMIZED, *([name for name, _ in config.targets] if risk_profiles else []),
                *([EQUAL_RISK] if risk_parity else [])]
    strategies = [*policies, CONSTRAINED_EQUAL_WEIGHT, EQUAL_WEIGHT]
    # Same bounds as every policy; infeasible bounds fail here rather than being relaxed.
    investable = constrained_equal_weights(universe.columns, config)
    cost_rate = settings.transaction_cost_bps / 1e4
    weights = {name: {} for name in strategies}
    held = {name: pd.Series(0., index=universe.columns) for name in strategies}
    gross_parts, net_parts, train_metrics = [], [], {}
    trading = {name: {} for name in strategies + ([benchmark] if benchmark else [])}
    costs = {name: {} for name in trading}
    for position, fold in enumerate(folds):
        train = universe.loc[(universe.index >= fold.return_base) & (universe.index <= fold.train_end)]
        if train.index[-1] > fold.rebalance_date or train.index[-1] >= fold.test_start:
            raise RuntimeError(f"{fold.test_year}: training data reach the rebalance or test period.")
        fold_config = config if rates is None else replace(config, risk_free_rate=rates.mean_risk_free(train.index))
        selected, summary = fit_policies(train, fold_config, risk_profiles, risk_parity)
        summary["Risk-free rate (training mean)"] = fold_config.risk_free_rate
        selected[CONSTRAINED_EQUAL_WEIGHT] = investable
        selected[EQUAL_WEIGHT] = pd.Series(1 / universe.shape[1], index=universe.columns)
        # Test prices start at the rebalance close; the weights above are already frozen.
        test = prices.loc[(prices.index >= fold.rebalance_date) & (prices.index <= fold.test_end)]
        test_returns = simple_returns(test)
        if test_returns.index[0] <= fold.rebalance_date or test_returns.index[0] != fold.test_start:
            raise RuntimeError(f"{fold.test_year}: test returns overlap the training window.")
        gross, net = {}, {}
        for name in strategies:
            period, drifted = hold_returns(test_returns[universe.columns], selected[name], settings.rebalance)
            traded = float((selected[name] - held[name]).abs().sum())
            cost = cost_rate * traded
            gross[name] = period
            net[name] = period.copy()
            net[name].iloc[0] = (1 + period.iloc[0]) * (1 - cost) - 1
            held[name] = drifted
            weights[name][fold.test_year] = selected[name]
            trading[name][fold.test_year] = traded / 2
            costs[name][fold.test_year] = cost
        if benchmark is not None:
            gross[benchmark] = test_returns[benchmark]
            net[benchmark] = test_returns[benchmark].copy()
            cost = cost_rate if position == 0 else 0.
            net[benchmark].iloc[0] = (1 + net[benchmark].iloc[0]) * (1 - cost) - 1
            trading[benchmark][fold.test_year] = .5 if position == 0 else 0.
            costs[benchmark][fold.test_year] = cost
        gross_parts.append(pd.DataFrame(gross))
        net_parts.append(pd.DataFrame(net))
        for name in policies:
            train_metrics[(name, fold.test_year)] = summary.loc[name]
    oos, gross_oos = pd.concat(net_parts), pd.concat(gross_parts)
    if not oos.index.is_unique or not oos.index.is_monotonic_increasing:
        raise RuntimeError("Out-of-sample periods overlap or are out of order.")
    if len(set(f.test_year for f in folds)) != len(folds):
        raise RuntimeError("A test year is duplicated.")
    weights = {name: pd.DataFrame(table).T.rename_axis("Test year") for name, table in weights.items()}
    base = folds[0].rebalance_date
    nav = pd.concat([pd.DataFrame(1., index=[base], columns=oos.columns), (1 + oos).cumprod()])
    # Sharpe ratios of the OOS series use the mean risk-free rate published over the test dates.
    metric_config = config if rates is None else replace(config, risk_free_rate=rates.mean_risk_free(oos.index))
    return WalkForwardResult(
        folds=folds, weights=weights, oos_returns=oos, nav=nav,
        metrics=growth_metrics(oos, base, metric_config),
        train_metrics=pd.DataFrame(train_metrics).T.rename_axis(["Portfolio", "Test year"]),
        turnover=pd.DataFrame({name: turnover(weights[name]) for name in strategies}),
        concentration=pd.concat({name: concentration(weights[name]) for name in strategies}, axis=1),
        stability=pd.concat({name: weight_stability(weights[name], zero_tolerance) for name in policies},
                            names=["Portfolio"]),
        covariance_estimator=COVARIANCE_METHODS[config.covariance_method],
        expected_return_estimator=EXPECTED_RETURN_METHODS[config.expected_return_method],
        gross_returns=gross_oos, gross_metrics=growth_metrics(gross_oos, base, metric_config),
        trading=pd.DataFrame(trading).rename_axis("Test year"),
        costs=pd.DataFrame(costs).rename_axis("Test year"), settings=settings,
        strategies=tuple(strategies), benchmark=benchmark, universe=tuple(universe.columns), config=config)


@dataclass
class UniverseComparison:
    """Walk-forward results of pre-specified eligible universes under one identical protocol."""
    variants: dict[str, tuple[str, ...]]
    results: dict[str, WalkForwardResult]
    summary: pd.DataFrame
    common_dates: tuple[pd.Timestamp, pd.Timestamp] = field(default=(None, None))


def variant_config(config: Config, excluded: Sequence[str] = (), unlevered: Sequence[str] = ()) -> Config:
    """The configuration of one universe variant: only eligibility and the named leverage change."""
    base = eligible_names(config)
    unknown = [name for name in excluded if name not in base]
    if unknown:
        raise ValueError(f"Variant excludes {unknown}, which are not eligible assets {base}.")
    eligible = [name for name in base if name not in set(excluded)]
    if not eligible:
        raise ValueError("Variant leaves no eligible asset.")
    levered = dict(config.leverage)
    missing = [name for name in unlevered if name not in levered]
    if missing:
        raise ValueError(f"Variant unlevers {missing}, which have no configured leverage.")
    return replace(with_eligible(config, eligible),
                   leverage=tuple((n, f) for n, f in config.leverage if n not in set(unlevered)))


def compare_universes(prices: pd.DataFrame, config: Config, variants: Mapping, *,
                      risk_profiles: bool = False, settings: WalkForwardSettings | None = None,
                      rates=None, risk_parity: bool = False) -> UniverseComparison:
    """Same walk-forward for each variant; a variant changes eligibility (and optionally leverage) only.

    `variants` maps a label to the asset names it excludes from the configured eligible universe
    ({"Sans Apple": ["Apple"]}) or to {"exclude": [...], "unlevered": [...]}, where `unlevered`
    replaces a synthetic leveraged series by its unleveraged underlying (which must be in `prices`).
    Prices, dates, estimators, costs, constraints and benchmark are identical across variants.
    """
    results, rows, described = {}, [], {}
    for label, spec in variants.items():
        if isinstance(spec, Mapping):
            excluded, unlevered = tuple(spec.get("exclude", ())), tuple(spec.get("unlevered", ()))
        else:
            excluded, unlevered = tuple(spec), ()
        try:
            variant = variant_config(config, excluded, unlevered)
        except ValueError as exc:
            raise ValueError(f"Variant '{label}': {exc}") from exc
        result = walk_forward(prices, variant, settings=settings, risk_profiles=risk_profiles, rates=rates,
                              risk_parity=risk_parity)
        results[label] = result
        described[label] = excluded + tuple(f"{name} (sans levier)" for name in unlevered)
        table = result.summary()
        for name, row in table.iterrows():
            rows.append({"Universe": label, "Strategy": name, **row.to_dict()})
    first = next(iter(results.values()))
    return UniverseComparison(described, results, pd.DataFrame(rows).set_index(["Universe", "Strategy"]),
                              (first.nav.index[0], first.nav.index[-1]))


@dataclass
class GrowthDifference:
    strategy: str
    reference: str
    observed: float
    lower: float
    upper: float
    level: float
    probability_positive: float
    block_length: float
    replications: int


def relative_growth_interval(returns: pd.DataFrame, strategy: str, reference: str, base_date, *,
                             replications: int = 2000, seed: int = 0, level: float = .90,
                             calendar_days_per_year: float = 365.25,
                             block_length: float | None = None) -> GrowthDifference:
    """Stationary-bootstrap interval of the annualized relative wealth growth of two OOS series.

    Statistic: exp(sum(log(1 + r_s) - log(1 + r_ref)) / years) - 1, i.e. (1 + CAGR_s) / (1 + CAGR_ref) - 1
    on the same dates, with years measured from `base_date` (the NAV start) like CAGR. Paired rows are resampled together (Politis-Romano), expected block length
    from Politis-White / Patton-Politis-White on the log-difference series unless `block_length` is
    given. Weights are taken as realized (the annual decisions are not re-simulated), so the interval
    reflects daily-return sampling noise under stationarity within the period, not regime risk or
    uncertainty about future periods.
    """
    from arch.bootstrap import StationaryBootstrap, optimal_block_length
    pair = returns[[strategy, reference]]
    if (pair <= -1).any().any():
        raise ValueError("Relative growth needs returns above -100%.")
    diff = (np.log1p(pair[strategy]) - np.log1p(pair[reference])).to_numpy()
    base_date = pd.Timestamp(base_date)
    if base_date >= returns.index[0]:
        raise ValueError("The base date must precede the first return.")
    years = (returns.index[-1] - base_date).days / calendar_days_per_year
    block = (max(1., float(optimal_block_length(diff)["stationary"].iloc[0])) if block_length is None
             else float(block_length))
    if not block >= 1:
        raise ValueError("Expected block length must be at least one observation.")
    sampler = StationaryBootstrap(block, diff, seed=seed)
    draws = np.array([np.expm1(data[0][0].sum() / years) for data in sampler.bootstrap(replications)])
    alpha = (1 - level) / 2
    observed = float(np.expm1(diff.sum() / years))
    return GrowthDifference(strategy, reference, observed, float(np.quantile(draws, alpha)),
                            float(np.quantile(draws, 1 - alpha)), level, float((draws > 0).mean()),
                            block, replications)


# Pre-specified sensitivity panel (fixed before any result was computed): automatic block length,
# about one month and about one quarter of sessions. All are reported; none is selected.
SENSITIVITY_BLOCKS = (None, 21, 63)


def relative_growth_panel(result, policies: Sequence[str] | None = None, references: Sequence[str] | None = None,
                          *, blocks: Sequence[float | None] = SENSITIVITY_BLOCKS, replications: int = 2000,
                          seed: int = 0, level: float = .90) -> pd.DataFrame:
    """Relative growth of each policy vs each reference under several block lengths (descriptive)."""
    policies = result.policies if policies is None else list(policies)
    references = result.benchmarks if references is None else list(references)
    rows = []
    for policy in policies:
        for reference in references:
            for block in blocks:
                g = relative_growth_interval(result.oos_returns, policy, reference, result.nav.index[0],
                                             replications=replications, seed=seed, level=level,
                                             block_length=block)
                rows.append({"Policy": policy, "Reference": reference,
                             "Block rule": "automatic" if block is None else f"{block:g} sessions",
                             "Expected block length": g.block_length, "Observed": g.observed,
                             "Lower": g.lower, "Upper": g.upper, "Share of draws > 0": g.probability_positive})
    return pd.DataFrame(rows).set_index(["Policy", "Reference", "Block rule"])


def leave_one_year_out(result, strategy: str, reference: str) -> pd.DataFrame:
    """Annualized relative growth of `strategy` vs `reference` with each test year removed in turn.

    Removing a year drops its returns from both series and its length from the horizon, which
    shows how much the conclusion depends on a single year (7 years = 7 values, not a sample).
    """
    annual = result.annual_returns()[[strategy, reference]]
    complete = {f.test_year: f for f in result.folds}
    lengths = pd.Series({year: (fold.test_end - (result.folds[i - 1].test_end if i else fold.rebalance_date)).days
                         for i, (year, fold) in enumerate(complete.items())}) / 365.25
    log_ratio = np.log1p(annual[strategy]) - np.log1p(annual[reference])
    rows = {"Toutes les années": np.expm1(log_ratio.sum() / lengths.sum())}
    for year in annual.index:
        rows[f"Sans {year}"] = np.expm1(log_ratio.drop(year).sum() / lengths.drop(year).sum())
    return pd.Series(rows, name=f"{strategy} vs {reference}").to_frame()
