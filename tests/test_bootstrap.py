"""Stationary-bootstrap frontier uncertainty: deterministic, aligned, and separate from the optimizer."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from arch.bootstrap import optimal_block_length
from portfolio_lab.bootstrap import (bootstrap_frontier, bootstrap_indices, resampled_prices,
                                     stationary_block_length)
from portfolio_lab.config import Asset
from portfolio_lab.optimization import PortfolioOptimizer, optimize_frontier
from portfolio_lab.plotting import plot_frontier
from portfolio_lab.returns import simple_returns


@pytest.fixture(scope="module")
def prices():
    dates = pd.bdate_range("2019-12-31", periods=400)
    rng = np.random.default_rng(13)
    returns = rng.normal([.0009, .0004, .0002], [.012, .015, .008], (len(dates), 3))
    return pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=dates, columns=["Gold", "A", "B"])


@pytest.fixture
def cfg(config):
    return replace(config, assets=tuple(Asset(n, n, "synthetic", "EUR", "Gross Return", "x") for n in ["Gold", "A", "B"]))


@pytest.fixture
def result(cfg, prices):
    return bootstrap_frontier(prices, cfg, replications=12, seed=0, grid_points=7, workers=1)


def test_block_length_rule(prices):
    returns = simple_returns(prices)
    expected = optimal_block_length(returns.to_numpy())["stationary"].mean()
    assert stationary_block_length(returns) == pytest.approx(max(1., expected))


def test_indices_shape_reproducibility_and_range():
    first = bootstrap_indices(300, 5., 4, seed=7)
    assert first.shape == (4, 300) and first.dtype.kind == "i"
    assert first.min() >= 0 and first.max() < 300
    np.testing.assert_array_equal(first, bootstrap_indices(300, 5., 4, seed=7))
    assert not np.array_equal(first, bootstrap_indices(300, 5., 4, seed=8))
    with pytest.raises(ValueError):
        bootstrap_indices(300, .5, 4, seed=0)


def test_block_structure_matches_expected_block_length():
    indices = bootstrap_indices(5000, 10., 20, seed=1)
    # Within a block the next row follows the previous one (circularly); blocks restart with prob 1/L.
    continues = indices[:, 1:] == (indices[:, :-1] + 1) % 5000
    assert continues.mean() == pytest.approx(1 - 1 / 10., abs=.01)
    iid_like = bootstrap_indices(5000, 1., 5, seed=1)
    assert ((iid_like[:, 1:] == (iid_like[:, :-1] + 1) % 5000).mean()) < .01


def test_resampled_prices_reproduce_resampled_returns(prices):
    rows = bootstrap_indices(len(prices) - 1, 4., 1, seed=3)[0]
    sample = resampled_prices(prices, rows)
    assert sample.index.equals(prices.index) and list(sample.columns) == list(prices.columns)
    pd.testing.assert_series_equal(sample.iloc[0], prices.iloc[0])
    np.testing.assert_allclose(simple_returns(sample).to_numpy(), simple_returns(prices).to_numpy()[rows], rtol=1e-10)


def test_reproducible_with_fixed_seed_and_independent_of_workers(cfg, prices, result):
    again = bootstrap_frontier(prices, cfg, replications=12, seed=0, grid_points=7, workers=1)
    pd.testing.assert_frame_equal(again.frontier, result.frontier)
    pd.testing.assert_frame_equal(again.sharpe_weights, result.sharpe_weights)
    parallel = bootstrap_frontier(prices, cfg, replications=12, seed=0, grid_points=7, workers=2)
    pd.testing.assert_frame_equal(parallel.frontier, result.frontier)
    pd.testing.assert_frame_equal(parallel.sharpe_weights, result.sharpe_weights)
    other = bootstrap_frontier(prices, cfg, replications=12, seed=1, grid_points=7, workers=1)
    assert not other.sharpe_weights.equals(result.sharpe_weights)


def test_frontier_alignment_and_observed_point(cfg, prices, result):
    assert result.frontier.shape == (12, 7)
    np.testing.assert_array_equal(result.frontier.columns.to_numpy(), result.grid)
    observed = PortfolioOptimizer(prices, cfg)
    core = observed.core_portfolios()
    assert result.grid[0] == core["Minimum Volatility"]["Estimated volatility"]
    assert result.grid[-1] == core["Maximum CAGR"]["Estimated volatility"]
    expected = [observed.target(float(g), core["Minimum Volatility"], core["Maximum CAGR"], "t")["CAGR"]
                for g in result.grid]
    np.testing.assert_allclose(result.observed.to_numpy(), expected)
    pd.testing.assert_series_equal(result.point_weights, core["Maximum Sharpe"]["weights"], check_names=False)


def test_replications_use_the_configured_engine(cfg, prices, result):
    rows = bootstrap_indices(len(prices) - 1, result.block_length, 12, seed=0)
    optimizer = PortfolioOptimizer(resampled_prices(prices, rows[4]), cfg)
    core = optimizer.core_portfolios()
    np.testing.assert_allclose(result.sharpe_weights.iloc[4], core["Maximum Sharpe"]["weights"])
    max_point = optimizer.target(float(result.grid[-1]), core["Minimum Volatility"], core["Maximum CAGR"], "t")
    assert result.frontier.iloc[4, -1] == pytest.approx(max_point["CAGR"])


def test_percentiles_bands_and_nesting(result):
    values = result.frontier.to_numpy()
    feasible = np.isfinite(values)
    np.testing.assert_allclose(result.bands["Feasible share"], feasible.mean(axis=0))
    for p in (2.5, 10, 50, 90, 97.5):
        np.testing.assert_allclose(result.bands[f"P{p:g}"], np.nanpercentile(values, p, axis=0))
    inner, outer = result.band(.80), result.band(.95)
    assert (result.bands.loc[inner.index, "Feasible share"] >= .95).all()
    assert (outer["Lower"] <= inner["Lower"] + 1e-15).all() and (inner["Upper"] <= outer["Upper"] + 1e-15).all()
    assert np.isfinite(inner[["Lower", "Upper"]].to_numpy()).all()
    with pytest.raises(ValueError, match="Band level"):
        result.band(.9)


def test_weight_percentiles(result):
    weights = result.sharpe_weights
    assert np.isfinite(weights.to_numpy()).all()
    np.testing.assert_allclose(weights.sum(axis=1), 1, atol=1e-8)
    table = result.weight_uncertainty
    assert list(table.columns) == ["Point estimate", "P5", "P25", "Median", "P75", "P95"]
    for column, p in (("P5", 5), ("P25", 25), ("Median", 50), ("P75", 75), ("P95", 95)):
        np.testing.assert_allclose(table[column], np.percentile(weights.to_numpy(), p, axis=0))
    assert (table["P5"] <= table["P25"]).all() and (table["P75"] <= table["P95"]).all()
    assert result.formatted_weights().loc["Gold", "Median"].endswith("%")


def test_infeasible_ceilings_are_nan_not_values(result):
    values = result.frontier.to_numpy()
    assert not np.isinf(values).any()
    # Only ceilings below a replication's own minimum volatility may be missing.
    first_valid = np.argmax(np.isfinite(values), axis=1)
    for row, start in zip(values, first_valid):
        assert np.isfinite(row[start:]).all()


def test_optimizer_and_default_chart_unchanged(cfg, prices, result):
    import matplotlib.pyplot as plt
    before = optimize_frontier(prices, cfg)
    bootstrap_frontier(prices, cfg, replications=3, seed=0, grid_points=4, workers=1)
    after = optimize_frontier(prices, cfg)
    pd.testing.assert_frame_equal(before.summary, after.summary, check_exact=True)
    pd.testing.assert_frame_equal(before.weights, after.weights, check_exact=True)
    stats = pd.DataFrame({"Volatility annualized": [.1], "CAGR": [.05]}, index=["X"])
    plain = plot_frontier(stats, before)
    assert not plain.axes[0].collections[0].get_label().startswith("Bootstrap")
    banded = plot_frontier(stats, before, band=result.band(.8))
    assert banded.axes[0].collections[0].get_label() == "Bootstrap uncertainty band (80%)"
    plt.close("all")


def test_invalid_replications(cfg, prices):
    with pytest.raises(ValueError, match="positive integer"):
        bootstrap_frontier(prices, cfg, replications=0)
