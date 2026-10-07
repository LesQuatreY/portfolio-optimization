"""Subperiod stability (in-sample) and annual walk-forward out-of-sample evaluation.

Portfolio semantics are those of the main engine: constant target weights, rebalanced
back to target at every common observation, so a portfolio's return on each common
date is ``simple_returns(prices) @ w``. Walk-forward "annual rebalancing" means the
target weights are re-estimated once per calendar year, from training data only, and
then held as constant targets throughout the following test year.

Returns are indexed by the end date of their interval. A window's returns are those
ending inside it; the first one starts from the last observation before the window
(the "return base"), which always precedes the window and is never a test date.
"""
from collections.abc import Sequence
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .config import Config
from .metrics import compute_asset_metrics
from .optimization import PortfolioOptimizer, select_frontier_assets
from .returns import simple_returns

OPTIMIZED = ("Maximum Sharpe", "Minimum Volatility")
EQUAL_WEIGHT = "Equal Weight"
DEFAULT_PERIODS = (("2001-01-01", "2010-12-31"), ("2011-01-01", "2020-12-31"), ("2021-01-01", None))
# Weights below this are treated as "effectively zero" in stability diagnostics.
ZERO_TOLERANCE = 1e-4


def window_prices(prices: pd.DataFrame, start, end=None) -> pd.DataFrame:
    """Observations in [start, end], preceded by the last earlier observation if one exists."""
    start = pd.Timestamp(start)
    end = prices.index[-1] if end is None else pd.Timestamp(end)
    before = prices.loc[prices.index < start]
    inside = prices.loc[(prices.index >= start) & (prices.index <= end)]
    return pd.concat([before.iloc[-1:], inside]) if len(before) else inside


def optimize_weights(train_prices: pd.DataFrame, config: Config,
                     portfolios: Sequence[str] = OPTIMIZED) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    """Engine portfolios estimated on exactly these prices (and nothing else)."""
    core = PortfolioOptimizer(train_prices, config).core_portfolios()
    weights = {name: core[name]["weights"] for name in portfolios}
    metrics = pd.DataFrame({name: {k: core[name][k] for k in ("CAGR", "Volatility", "Sharpe", "Max Drawdown")}
                            for name in portfolios}).T
    return weights, metrics


def hhi(weights: pd.DataFrame) -> pd.Series:
    """Herfindahl-Hirschman concentration, sum of squared weights (1/n equal weight .. 1 single asset)."""
    return (weights ** 2).sum(axis=1)


def concentration(weights: pd.DataFrame) -> pd.DataFrame:
    index = hhi(weights)
    return pd.DataFrame({"HHI": index, "Effective assets": 1 / index})


def turnover(weights: pd.DataFrame) -> pd.Series:
    """One-way turnover between consecutive target allocations: 0.5 * sum(|w_t - w_{t-1}|).

    The first allocation has no predecessor (NaN). Within-period rebalancing back to the
    constant targets is not included.
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


def walk_forward_folds(index: pd.DatetimeIndex, train_years: int = 10, *,
                       include_partial_final_year: bool = True) -> list[WalkForwardFold]:
    """Calendar-year folds: train on the `train_years` full years before each test year.

    A fold needs a full training window, i.e. an observation before its first training
    year to serve as the return base. The last test year is marked incomplete when the
    data stop inside it; it is kept unless include_partial_final_year is False.
    """
    if not isinstance(train_years, int) or train_years < 1:
        raise ValueError("Training window must be a positive whole number of years.")
    folds = []
    for test_year in sorted(set(index.year)):
        first_train = pd.Timestamp(year=test_year - train_years, month=1, day=1)
        year_start = pd.Timestamp(year=test_year, month=1, day=1)
        if index[0] >= first_train:
            continue
        train = index[(index >= first_train) & (index < year_start)]
        test = index[(index >= year_start) & (index < pd.Timestamp(year=test_year + 1, month=1, day=1))]
        complete = bool(index[-1] > test[-1])
        if len(train) < 2 or not len(test) or (not complete and not include_partial_final_year):
            continue
        folds.append(WalkForwardFold(test_year, train[0], train[-1], test[0], test[-1],
                                     index[index < first_train][-1], len(train), len(test), complete))
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

    @property
    def fold_table(self) -> pd.DataFrame:
        return pd.DataFrame([vars(f) for f in self.folds]).set_index("test_year")


def walk_forward(prices: pd.DataFrame, config: Config, *, train_years: int = 10,
                 benchmark: str | None = "MSCI World", include_partial_final_year: bool = True,
                 zero_tolerance: float = ZERO_TOLERANCE) -> WalkForwardResult:
    """Annual walk-forward: estimate on train years only, freeze, apply to the next year only.

    Strategies: the engine's Maximum Sharpe and Minimum Volatility, Equal Weight over the
    same optimizer universe (same constant-weight convention, reset at the same annual
    boundaries), and the passive EUR benchmark series. Every reported return is a test
    return; no observation of a test year enters the estimation of its own weights.
    """
    universe = prices[select_frontier_assets(config)]
    if benchmark is not None and benchmark not in prices:
        raise ValueError(f"Benchmark '{benchmark}' is not in the configured price data.")
    folds = walk_forward_folds(universe.index, train_years, include_partial_final_year=include_partial_final_year)
    strategies = [*OPTIMIZED, EQUAL_WEIGHT]
    weights = {name: {} for name in strategies}
    returns, train_metrics = [], {}
    for fold in folds:
        train = universe.loc[(universe.index >= fold.return_base) & (universe.index <= fold.train_end)]
        selected, summary = optimize_weights(train, config)
        selected[EQUAL_WEIGHT] = pd.Series(1 / universe.shape[1], index=universe.columns)
        # Test prices start at the last training close; weights above are already frozen.
        test = prices.loc[(prices.index >= fold.train_end) & (prices.index <= fold.test_end)]
        test_returns = simple_returns(test)
        if test_returns.index[0] <= fold.train_end or test_returns.index[0] != fold.test_start:
            raise RuntimeError(f"{fold.test_year}: test returns overlap the training window.")
        realized = {name: test_returns[universe.columns] @ selected[name] for name in strategies}
        if benchmark is not None:
            realized[benchmark] = test_returns[benchmark]
        returns.append(pd.DataFrame(realized))
        for name in strategies:
            weights[name][fold.test_year] = selected[name]
        for name in OPTIMIZED:
            train_metrics[(name, fold.test_year)] = summary.loc[name]
    oos = pd.concat(returns)
    if not oos.index.is_unique or not oos.index.is_monotonic_increasing:
        raise RuntimeError("Out-of-sample periods overlap or are out of order.")
    weights = {name: pd.DataFrame(table).T.rename_axis("Test year") for name, table in weights.items()}
    base = folds[0].train_end
    nav = pd.concat([pd.DataFrame(1., index=[base], columns=oos.columns), (1 + oos).cumprod()])
    return WalkForwardResult(
        folds=folds, weights=weights, oos_returns=oos, nav=nav,
        metrics=growth_metrics(oos, base, config),
        train_metrics=pd.DataFrame(train_metrics).T.rename_axis(["Portfolio", "Test year"]),
        turnover=pd.DataFrame({name: turnover(weights[name]) for name in strategies}),
        concentration=pd.concat({name: concentration(weights[name]) for name in strategies}, axis=1),
        stability=pd.concat({name: weight_stability(weights[name], zero_tolerance) for name in OPTIMIZED},
                            names=["Portfolio"]))
