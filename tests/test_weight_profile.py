"""Descriptive Maximum Sharpe weight profile: one asset fixed, all others re-optimized."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.config import Asset, with_max_weights
from portfolio_lab.optimization import PortfolioOptimizer, optimize_frontier, sharpe_weight_profile

GRID = np.linspace(0, 1, 11)


@pytest.fixture(scope="module")
def prices():
    dates = pd.bdate_range("2009-12-30", "2013-12-31")
    rng = np.random.default_rng(8)
    returns = rng.normal([.0012, .0004, .0003, .0002], [.010, .015, .012, .009], (len(dates), 4))
    return pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=dates, columns=["Gold", "A", "B", "C"])


@pytest.fixture
def cfg(config):
    return replace(config, assets=tuple(Asset(n, n, "synthetic", "EUR", "Gross Return", "x")
                                        for n in ["Gold", "A", "B", "C"]))


@pytest.fixture
def profile(cfg, prices):
    return sharpe_weight_profile(prices, cfg, "Gold", GRID)


def test_fixed_weight_is_exact_and_weights_sum_to_one(profile):
    weights = profile.weights
    np.testing.assert_array_equal(weights["Gold"].to_numpy(), weights.index.to_numpy())
    np.testing.assert_allclose(weights.sum(axis=1), 1, atol=1e-12)
    assert (weights >= 0).all().all()
    assert set(GRID).issubset(profile.table.index) and profile.optimum_weight in profile.table.index


def test_unconstrained_optimum_is_recovered(profile, cfg, prices):
    reference = optimize_frontier(prices, cfg).weights.loc["Maximum Sharpe"]
    assert profile.optimum_weight == reference["Gold"]
    row = profile.table.loc[profile.optimum_weight]
    assert row["Loss vs optimum"] == pytest.approx(0, abs=1e-8)
    assert row["Sharpe retained"] == pytest.approx(1, abs=1e-8)
    np.testing.assert_allclose(profile.weights.loc[profile.optimum_weight], reference, atol=1e-5)


def test_no_fixed_weight_beats_the_unconstrained_optimum(profile):
    assert (profile.table["Objective Sharpe"] <= profile.optimum_objective + 1e-8).all()
    assert (profile.table["Sharpe retained"] <= 1 + 1e-8).all()
    assert profile.table.loc[0., "Loss vs optimum"] < -.01  # moving far from the optimum costs Sharpe


def test_remaining_weights_are_optimized(profile, cfg, prices):
    optimizer = PortfolioOptimizer(prices, cfg)
    rng = np.random.default_rng(0)
    for fixed in (.2, .5):
        best = profile.table.loc[fixed, "Objective Sharpe"]
        rest = rng.dirichlet(np.ones(3), 300) * (1 - fixed)
        for others in rest:
            assert optimizer.objective_sharpe(np.r_[fixed, others]) <= best + 1e-9


def test_generic_for_other_assets(cfg, prices):
    profile = sharpe_weight_profile(prices, cfg, "B", [0., .3, .6])
    np.testing.assert_array_equal(profile.weights["B"].to_numpy(), profile.weights.index.to_numpy())
    np.testing.assert_allclose(profile.weights.sum(axis=1), 1, atol=1e-12)
    assert (profile.table["Objective Sharpe"] <= profile.optimum_objective + 1e-8).all()


@pytest.mark.parametrize("weights", [[-.1], [1.2], [np.nan], [], [[.1, .2]]])
def test_invalid_fixed_weights_fail_clearly(cfg, prices, weights):
    with pytest.raises(ValueError, match="finite values in \\[0, 1\\]"):
        sharpe_weight_profile(prices, cfg, "Gold", weights)


def test_unknown_asset_fails_clearly(cfg, prices):
    with pytest.raises(ValueError, match="'Silver' is not an optimizer asset"):
        sharpe_weight_profile(prices, cfg, "Silver", GRID)


def test_near_optimal_ranges_are_nested_and_contain_the_optimum(profile):
    near = profile.near_optimal
    assert list(near.index) == [">= 99% of optimal Sharpe", ">= 98% of optimal Sharpe", ">= 95% of optimal Sharpe"]
    assert (near["Min weight"] <= profile.optimum_weight).all() and (near["Max weight"] >= profile.optimum_weight).all()
    assert near["Min weight"].is_monotonic_decreasing and near["Max weight"].is_monotonic_increasing
    inside = profile.table.index[profile.table["Sharpe retained"] >= .95]
    assert (near.loc[">= 95% of optimal Sharpe", "Min weight"], near.loc[">= 95% of optimal Sharpe", "Max weight"]) \
        == (inside.min(), inside.max())


def test_investor_limit_is_recorded_but_does_not_restrict_the_map(cfg, prices, profile):
    limited = sharpe_weight_profile(prices, with_max_weights(cfg, {"Gold": .10}), "Gold", GRID)
    assert limited.investor_limit == .10
    assert limited.optimum_weight == profile.optimum_weight > .10
    pd.testing.assert_frame_equal(limited.table, profile.table)


def test_summary_and_formatting(profile):
    summary = profile.summary(.5)
    assert set(summary.index) == {0., .5, 1., profile.optimum_weight}
    formatted = profile.formatted(.5)
    assert any(label.endswith("(optimum)") for label in formatted.index)
    assert list(formatted.columns) == ["CAGR", "Volatility", "Sharpe", "Objective Sharpe", "Loss vs optimum",
                                       "Sharpe retained"]
