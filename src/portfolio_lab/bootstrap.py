"""In-sample estimation uncertainty of the efficient frontier and of Maximum Sharpe weights.

Pre-specified methodology (fixed before any bootstrap result was inspected):

* Stationary bootstrap (Politis & Romano 1994, JASA 89, 1303-1313) of whole rows of the
  daily EUR return matrix, so cross-asset dependence and some local time dependence are
  kept; implementation: arch.bootstrap.StationaryBootstrap (circular, geometric blocks).
* Expected block length: Politis & White (2004) automatic selection with the Patton,
  Politis & White (2009) correction (arch.bootstrap.optimal_block_length), computed per
  asset on the full-sample daily returns; the mean of the per-asset "stationary" values,
  floored at 1, is used for the joint resampling.
* 500 replications by default, seed 0. Each replication rebuilds prices on the original
  dates (same CAGR horizon) and runs the engine's PortfolioOptimizer with the configured
  estimators: Minimum Volatility, Maximum CAGR, multi-start Maximum Sharpe, and the
  engine's frontier rule (maximum log growth under an estimated-volatility ceiling) on a
  common grid of 25 ceilings spanning the observed frontier. No smoothing.
* Bands are percentiles over replications for which a ceiling is feasible (80%: 10th-90th,
  95%: 2.5th-97.5th); they are drawn only where >= 95% of replications are feasible.

This is a descriptive in-sample diagnostic ("bootstrap uncertainty bands"), separate from
the walk-forward out-of-sample analysis; nothing here feeds back into the optimizer.
"""
from concurrent.futures import ProcessPoolExecutor
import os
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .config import Config
from .optimization import PortfolioOptimizer, select_frontier_assets
from .returns import simple_returns

BAND_LEVELS = {0.80: (10., 90.), 0.95: (2.5, 97.5)}
WEIGHT_PERCENTILES = (5, 25, 50, 75, 95)
MIN_FEASIBLE_SHARE = .95


def stationary_block_length(returns: pd.DataFrame) -> float:
    """Mean of per-asset Politis-White / Patton-Politis-White stationary block lengths, at least 1."""
    from arch.bootstrap import optimal_block_length
    lengths = optimal_block_length(returns.to_numpy(dtype=float))["stationary"].to_numpy()
    if not np.isfinite(lengths).all():
        raise ValueError("Block-length selection returned non-finite values.")
    return max(1., float(lengths.mean()))


def bootstrap_indices(n_obs: int, block_length: float, replications: int, seed: int) -> np.ndarray:
    """(replications, n_obs) row indices drawn by the stationary bootstrap."""
    from arch.bootstrap import StationaryBootstrap
    if replications < 1 or n_obs < 2 or not block_length >= 1:
        raise ValueError("Need at least one replication, two observations and a block length >= 1.")
    sampler = StationaryBootstrap(block_length, np.arange(n_obs), seed=seed)
    return np.vstack([positional[0] for positional, _ in sampler.bootstrap(replications)])


def resampled_prices(prices: pd.DataFrame, indices: np.ndarray) -> pd.DataFrame:
    """Prices compounded from resampled return rows, on the original dates and base prices."""
    returns = simple_returns(prices).to_numpy()[indices]
    path = prices.iloc[0].to_numpy() * np.vstack([np.ones(prices.shape[1]), np.cumprod(1 + returns, axis=0)])
    return pd.DataFrame(path, index=prices.index, columns=prices.columns)


def _frontier_on_grid(optimizer: PortfolioOptimizer, core: dict, grid: np.ndarray) -> np.ndarray:
    """Engine frontier rule at each ceiling; NaN where the ceiling is below the minimum volatility."""
    minimum, maximum = core["Minimum Volatility"], core["Maximum CAGR"]
    points = [optimizer.target(float(ceiling), minimum, maximum, "Bootstrap frontier") for ceiling in grid]
    return np.array([np.nan if point["weights"] is None else point["CAGR"] for point in points])


def _frontier_and_sharpe(prices: pd.DataFrame, config: Config, grid: np.ndarray):
    optimizer = PortfolioOptimizer(prices, config)
    core = optimizer.core_portfolios()
    return _frontier_on_grid(optimizer, core, grid), core["Maximum Sharpe"]["weights"].to_numpy()


def _single_threaded_worker() -> None:
    # One BLAS thread per worker process; otherwise every process starts one per CPU and they contend.
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)


def _replicate_chunk(prices: pd.DataFrame, config: Config, grid: np.ndarray, rows: np.ndarray):
    return [_frontier_and_sharpe(resampled_prices(prices, row), config, grid) for row in rows]


@dataclass
class FrontierBootstrap:
    block_length: float
    replications: int
    seed: int
    grid: np.ndarray
    observed: pd.Series
    frontier: pd.DataFrame
    bands: pd.DataFrame
    point_weights: pd.Series
    sharpe_weights: pd.DataFrame
    weight_uncertainty: pd.DataFrame

    def band(self, level: float = .80) -> pd.DataFrame:
        """Lower/upper CAGR on the volatility grid, only where >= 95% of replications are feasible."""
        if level not in BAND_LEVELS:
            raise ValueError(f"Band level must be one of {sorted(BAND_LEVELS)}.")
        low, high = BAND_LEVELS[level]
        shown = self.bands.loc[self.bands["Feasible share"] >= MIN_FEASIBLE_SHARE]
        return pd.DataFrame({"Lower": shown[f"P{low:g}"], "Upper": shown[f"P{high:g}"]}).assign(Level=level)

    def summary(self) -> pd.Series:
        return pd.Series({"Method": "Stationary bootstrap (Politis-Romano 1994)",
                          "Block length rule": "Politis-White (2004) / Patton-Politis-White (2009), mean over assets",
                          "Expected block length (days)": round(self.block_length, 2),
                          "Replications": self.replications, "Seed": self.seed,
                          "Frontier grid points": len(self.grid)}, name="Bootstrap uncertainty")

    def formatted_weights(self) -> pd.DataFrame:
        return self.weight_uncertainty.map(lambda value: f"{value:.1%}")


def bootstrap_frontier(prices: pd.DataFrame, config: Config, replications: int = 500, seed: int = 0,
                       grid_points: int = 25, workers: int | None = None) -> FrontierBootstrap:
    """Stationary-bootstrap uncertainty of the frontier and Maximum Sharpe weights (in-sample)."""
    if not isinstance(replications, int) or replications < 1:
        raise ValueError("Replications must be a positive integer.")
    prices = prices[select_frontier_assets(config)]
    returns = simple_returns(prices)
    block = stationary_block_length(returns)
    observed = PortfolioOptimizer(prices, config)
    core = observed.core_portfolios()
    grid = np.linspace(core["Minimum Volatility"]["Estimated volatility"],
                       core["Maximum CAGR"]["Estimated volatility"], grid_points)
    observed_cagr = _frontier_on_grid(observed, core, grid)
    point = core["Maximum Sharpe"]["weights"].to_numpy()
    indices = bootstrap_indices(len(returns), block, replications, seed)
    # Indices are drawn up front from one seed, so results do not depend on the worker count.
    workers = 1 if replications < 8 else (workers or os.cpu_count() or 1)
    chunks = np.array_split(indices, min(workers, replications))
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers, initializer=_single_threaded_worker) as pool:
            parts = list(pool.map(_replicate_chunk, *zip(*[(prices, config, grid, chunk) for chunk in chunks])))
    else:
        parts = [_replicate_chunk(prices, config, grid, chunk) for chunk in chunks]
    results = [item for part in parts for item in part]
    frontier = pd.DataFrame([cagr for cagr, _ in results], columns=pd.Index(grid, name="Estimated volatility"))
    frontier.index.name = "Replication"
    weights = pd.DataFrame([w for _, w in results], columns=prices.columns).rename_axis("Replication")
    if not np.isfinite(weights.to_numpy()).all() or not np.allclose(weights.sum(axis=1), 1, atol=1e-8):
        raise RuntimeError("Bootstrap Maximum Sharpe weights are invalid.")
    values = frontier.to_numpy()
    feasible = np.isfinite(values)
    if np.isinf(values).any():
        raise RuntimeError("Bootstrap frontier contains infinite values.")
    bands = pd.DataFrame({"Observed": observed_cagr, "Feasible share": feasible.mean(axis=0)},
                         index=frontier.columns)
    for percentile in sorted({p for pair in BAND_LEVELS.values() for p in pair} | {50.}):
        column = np.full(len(grid), np.nan)
        usable = feasible.any(axis=0)
        column[usable] = np.nanpercentile(values[:, usable], percentile, axis=0)
        bands[f"P{percentile:g}"] = column
    point_weights = pd.Series(point, index=prices.columns, name="Point estimate")
    uncertainty = pd.DataFrame({"Point estimate": point_weights,
                                **{("Median" if p == 50 else f"P{p}"): np.percentile(weights, p, axis=0)
                                   for p in WEIGHT_PERCENTILES}}, index=prices.columns).rename_axis("Asset")
    return FrontierBootstrap(block, replications, seed, grid, pd.Series(observed_cagr, index=frontier.columns,
                                                                         name="Observed CAGR"),
                             frontier, bands, point_weights, weights, uncertainty)
