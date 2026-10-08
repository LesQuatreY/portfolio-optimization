"""Optional investor max-weight constraints: off by default, generic, and always compared with the reference."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.config import Asset, with_max_weights
from portfolio_lab.optimization import PortfolioOptimizer, compare_investor_constraints, optimize_frontier
from portfolio_lab.reporting import validate_study
from portfolio_lab.robustness import walk_forward


@pytest.fixture(scope="module")
def prices():
    dates = pd.bdate_range("2009-12-30", "2013-12-31")
    rng = np.random.default_rng(8)
    # "Gold" has the best risk/return trade-off, so the unconstrained optimizer loves it.
    returns = rng.normal([.0012, .0004, .0003, .0002], [.010, .015, .012, .009], (len(dates), 4))
    return pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=dates, columns=["Gold", "A", "B", "C"])


@pytest.fixture
def cfg(config):
    return replace(config, assets=tuple(Asset(n, n, "synthetic", "EUR", "Gross Return", "x")
                                        for n in ["Gold", "A", "B", "C"]))


def all_weights(result):
    rows = [p["weights"] for p in result.portfolios.values() if p["weights"] is not None]
    rows += [w for w in result.frontier["weights"] if w is not None]
    return pd.DataFrame(rows)


def test_default_and_empty_limits_reproduce_the_unconstrained_engine_exactly(cfg, prices):
    assert cfg.max_weights == ()
    reference = optimize_frontier(prices, cfg)
    for limits in ({}, None, {"Gold": 1.0}):
        result = optimize_frontier(prices, with_max_weights(cfg, limits))
        pd.testing.assert_frame_equal(result.summary, reference.summary, check_exact=True)
        pd.testing.assert_frame_equal(result.weights, reference.weights, check_exact=True)
        pd.testing.assert_frame_equal(result.frontier.drop(columns="weights"),
                                      reference.frontier.drop(columns="weights"), check_exact=True)
        pd.testing.assert_frame_equal(result.dominance, reference.dominance, check_exact=True)


def test_gold_cap_is_never_exceeded_and_other_assets_stay_free(cfg, prices):
    reference = optimize_frontier(prices, cfg)
    assert reference.weights.loc["Maximum Sharpe", "Gold"] > .5
    constrained_cfg = with_max_weights(cfg, {"Gold": .10})
    optimizer = PortfolioOptimizer(prices, constrained_cfg)
    np.testing.assert_array_equal(optimizer.upper, [.10, 1., 1., 1.])
    result = optimizer.run()
    weights = all_weights(result)
    assert (weights["Gold"] <= .10).all()
    np.testing.assert_allclose(weights.sum(axis=1), 1, atol=1e-12)
    assert (weights >= 0).all().all()
    sharpe = result.weights.loc["Maximum Sharpe"]
    assert sharpe["Gold"] == pytest.approx(.10, abs=1e-6)
    assert sharpe.drop("Gold").max() > .10
    # Capped assets have no feasible 100% portfolio, so they leave the dominance check.
    assert "Gold" not in result.dominance.index and len(result.dominance) == 3
    validate_study(prices, result, constrained_cfg)


def test_multiple_limits(cfg, prices):
    limits = {"Gold": .10, "A": .25, "C": .40}
    result = optimize_frontier(prices, with_max_weights(cfg, limits))
    weights = all_weights(result)
    for name, cap in limits.items():
        assert (weights[name] <= cap).all()
    np.testing.assert_allclose(weights.sum(axis=1), 1, atol=1e-12)
    assert weights["B"].max() > .25


@pytest.mark.parametrize("limits,match", [
    ({"Silver": .1}, "'Silver': not a configured asset"),
    ({"Gold": 0}, "0 < weight <= 1"),
    ({"Gold": -.1}, "0 < weight <= 1"),
    ({"Gold": 1.5}, "0 < weight <= 1"),
    ({"Gold": np.nan}, "0 < weight <= 1"),
    ({"Gold": True}, "0 < weight <= 1"),
    ({"Gold": "0.1"}, "0 < weight <= 1"),
])
def test_invalid_limits_fail_clearly(cfg, limits, match):
    with pytest.raises(ValueError, match=match):
        with_max_weights(cfg, limits)


def test_non_mapping_and_duplicates_fail_clearly(cfg):
    with pytest.raises(ValueError, match="mapping of asset name"):
        with_max_weights(cfg, [("Gold", .1)])
    with pytest.raises(ValueError, match="Duplicate"):
        replace(cfg, max_weights=(("Gold", .1), ("Gold", .2)))


def test_infeasible_limits_fail_before_optimizing(cfg, prices):
    limits = {"Gold": .1, "A": .3, "B": .3, "C": .2}
    with pytest.raises(ValueError, match="infeasible.*90.00% < 100%"):
        optimize_frontier(prices, with_max_weights(cfg, limits))
    with pytest.raises(ValueError, match="infeasible"):
        compare_investor_constraints(prices, cfg, limits)


def test_limit_on_an_asset_outside_the_optimizer_universe_fails(cfg, prices):
    leveraged = replace(cfg, leverage=(("A", 2.0),), max_weights=(("A", .2),))
    with pytest.raises(ValueError, match="do not match optimizer assets"):
        optimize_frontier(prices.assign(**{"A x2": prices["A"]}), leveraged)


def test_comparison_keeps_the_unconstrained_optimum_visible(cfg, prices):
    comparison = compare_investor_constraints(prices, cfg, {"Gold": .10})
    reference = optimize_frontier(prices, cfg)
    pd.testing.assert_frame_equal(comparison.unconstrained.weights, reference.weights, check_exact=True)
    sharpe = comparison.weights.loc["Maximum Sharpe"]
    assert sharpe.loc["Gold", "Unconstrained"] == reference.weights.loc["Maximum Sharpe", "Gold"]
    assert sharpe.loc["Gold", "Constrained"] <= .10 and sharpe.loc["Gold", "Investor limit"] == .10
    assert sharpe["Investor limit"].drop("Gold").isna().all()
    np.testing.assert_allclose(sharpe["Difference"], sharpe["Constrained"] - sharpe["Unconstrained"])
    cost = comparison.cost
    assert list(cost.index.get_level_values("Metric").unique()) == ["CAGR", "Volatility", "Sharpe", "Max Drawdown"]
    np.testing.assert_allclose(cost["Difference"], cost["Constrained"] - cost["Unconstrained"])
    assert cost.loc[("Maximum Sharpe", "CAGR"), "Unconstrained"] == reference.summary.loc["Maximum Sharpe", "CAGR"]
    table, weights = comparison.formatted()
    assert table.loc[("Maximum Sharpe", "Sharpe"), "Difference"].startswith(("+", "-"))
    assert weights.loc[("Maximum Sharpe", "Gold"), "Investor limit"] == "10.00%"
    with pytest.raises(ValueError, match="No investor max weights"):
        compare_investor_constraints(prices, cfg, {})


def test_walk_forward_uses_limits_only_when_configured(cfg, prices):
    free = walk_forward(prices, cfg, train_years=2, benchmark="C")
    assert free.weights["Maximum Sharpe"]["Gold"].max() > .10
    capped = walk_forward(prices, with_max_weights(cfg, {"Gold": .10}), train_years=2, benchmark="C")
    for name in ("Maximum Sharpe", "Minimum Volatility"):
        assert (capped.weights[name]["Gold"] <= .10).all()
        np.testing.assert_allclose(capped.weights[name].sum(axis=1), 1, atol=1e-12)


def test_frontier_chart_shows_investor_constrained_portfolios(cfg, prices):
    import matplotlib.pyplot as plt
    from portfolio_lab.metrics import compute_asset_metrics
    from portfolio_lab.plotting import plot_frontier
    comparison = compare_investor_constraints(prices, cfg, {"Gold": .10})
    stats = compute_asset_metrics(prices)
    plain = plot_frontier(stats, comparison.unconstrained)
    figure = plot_frontier(stats, comparison.unconstrained, investor=comparison)
    labels = [line.get_label() for line in figure.axes[0].lines]
    assert "Investor-constrained frontier (Gold ≤ 10%)" in labels
    assert not any("Investor" in line.get_label() for line in plain.axes[0].lines)
    marker = next(c for c in figure.axes[0].collections if c.get_label().startswith("Investor-constrained portfolios"))
    expected = [[comparison.constrained.portfolios[n]["Volatility"], comparison.constrained.portfolios[n]["CAGR"]]
                for n in ("Maximum Sharpe", "Minimum Volatility", "Maximum CAGR")]
    np.testing.assert_allclose(marker.get_offsets(), expected)
    assert any(t.get_text() == "Maximum Sharpe (Gold ≤ 10%)" for t in figure.axes[0].texts)
    plt.close("all")


@pytest.mark.parametrize("limits,label", [
    ({"Gold": .10}, "Gold ≤ 10%"),
    ({"Gold": .125}, "Gold ≤ 12.5%"),
    ({"Gold": .25, "A": .3}, "Gold ≤ 25%, A ≤ 30%"),
])
def test_chart_labels_follow_the_configured_limits(cfg, prices, limits, label):
    import matplotlib.pyplot as plt
    from portfolio_lab.metrics import compute_asset_metrics
    from portfolio_lab.optimization import sharpe_weight_profile
    from portfolio_lab.plotting import plot_frontier, plot_weight_profile
    comparison = compare_investor_constraints(prices, cfg, limits)
    figure = plot_frontier(compute_asset_metrics(prices), comparison.unconstrained, investor=comparison)
    texts = [line.get_label() for line in figure.axes[0].lines] + [t.get_text() for t in figure.axes[0].texts]
    assert f"Investor-constrained frontier ({label})" in texts
    assert f"Maximum Sharpe ({label})" in texts
    assert not any("Gold ≤ 10%" in t for t in texts) or label.startswith("Gold ≤ 10%")
    profile = sharpe_weight_profile(prices, with_max_weights(cfg, limits), "Gold", [0., .5, 1.])
    gold = f"{round(limits['Gold'] * 100, 2):g}%"
    lines = [line.get_label() for line in plot_weight_profile(profile).axes[0].lines]
    assert f"Investor limit ({gold})" in lines
    plt.close("all")
