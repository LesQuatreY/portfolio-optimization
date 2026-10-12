"""Phase 6: anchored expected returns, resampled policies, exposure (risk-distance) diagnostics."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import portfolio_lab.robustness as robustness
from portfolio_lab.assets import Asset
from portfolio_lab.config import Config
from portfolio_lab.diagnostics import (exposure_changes, mean_uncertainty, principal_components, risk_contributions,
                                       risk_distance)
from portfolio_lab.expected_returns import anchored_expected_returns
from portfolio_lab.optimization import PortfolioOptimizer
from portfolio_lab.research import load_research_config

ROOT = Path(__file__).resolve().parents[1]


def assets(*names):
    return tuple(Asset(n, n, "s", "EUR", "Gross Return", "x") for n in names)


def prices_from(returns, columns, start="2001-01-02"):
    dates = pd.bdate_range(start, periods=len(returns) + 1)
    return pd.DataFrame(100 * np.vstack([np.ones(returns.shape[1]), np.cumprod(1 + returns, axis=0)]),
                        index=dates, columns=columns)


@pytest.fixture(scope="module")
def correlated_market():
    """A and B share one factor (corr ~0.95) with different sample means; C is independent."""
    rng = np.random.default_rng(3)
    n = 2500
    common = rng.standard_normal(n) * .010
    a = common + rng.standard_normal(n) * .0033 + .0008
    b = common + rng.standard_normal(n) * .0033 + .0002
    c = rng.standard_normal(n) * .008 + .0003
    return prices_from(np.column_stack([a, b, c]), ["A", "B", "C"])


def cfg(columns, **kwargs):
    return Config(assets=assets(*columns), covariance_method="sample", frontier_points=4,
                  targets=(("Low", .08), ("High", .5)), **kwargs)


# --- Anchored (Black-Litterman) expected returns ----------------------------------------------------

def test_posterior_equals_the_data_when_the_data_match_equilibrium():
    sigma = pd.DataFrame([[.04, .01], [.01, .09]], index=["X", "Y"], columns=["X", "Y"])
    anchor = pd.Series({"X": .6, "Y": .4})
    delta = 2.
    pi_daily = delta * (sigma.to_numpy() / 252) @ anchor.to_numpy()
    rng = np.random.default_rng(0)
    raw = rng.standard_normal((5000, 2))
    raw = (raw - raw.mean(0)) / raw.std(0)
    returns = pd.DataFrame(raw * 1e-4 + pi_daily, columns=["X", "Y"])  # sample means exactly pi
    estimate = anchored_expected_returns(returns, sigma, anchor)
    np.testing.assert_allclose(estimate.values, pi_daily * 252, rtol=1e-10)
    assert estimate.shrinkage == pytest.approx(delta, rel=1e-8)


def test_noisy_gap_between_correlated_assets_is_pulled_to_equilibrium(correlated_market):
    optimizer = PortfolioOptimizer(correlated_market, cfg(["A", "B", "C"], expected_return_method="anchored",
                                                          growth_drift="estimated"))
    sample = optimizer.realized_mean
    anchored = optimizer.mu
    sample_gap = sample[0] - sample[1]
    anchored_gap = anchored[0] - anchored[1]
    assert sample_gap > .1                      # ~15%/yr gap in the sample
    assert abs(anchored_gap) < .35 * abs(sample_gap)
    assert optimizer.expected.method == "anchored"
    np.testing.assert_allclose(optimizer.R_objective.mean(axis=0) * 252, anchored, rtol=1e-10)


def test_uncorrelated_posterior_is_the_average_of_equilibrium_and_data():
    sigma = pd.DataFrame(np.diag([.04, .0225, .01]), index=list("XYZ"), columns=list("XYZ"))
    rng = np.random.default_rng(4)
    returns = pd.DataFrame(rng.standard_normal((3000, 3)) * .01 + np.array([.0010, .0002, .0005]), columns=list("XYZ"))
    anchor = pd.Series({"X": .2, "Y": .3, "Z": .5})
    estimate = anchored_expected_returns(returns, sigma, anchor)
    m = returns.mean().to_numpy() * 252
    d = sigma.to_numpy()
    delta = float(m @ anchor.to_numpy()) / float(anchor @ d @ anchor)
    pi = delta * d @ anchor.to_numpy()
    np.testing.assert_allclose(estimate.values, (pi + m) / 2, rtol=1e-10)  # equal precision when Sigma is diagonal
    assert float(estimate.values @ anchor) == pytest.approx(float(m @ anchor), rel=1e-10)


def test_anchoring_changes_mean_dependent_portfolios_and_sparse_ceilings_stay_pinned():
    rng = np.random.default_rng(9)
    raw = rng.standard_normal((2500, 3)) * np.array([.012, .010, .008]) + np.array([.0010, .0002, .0005])
    market = prices_from(raw, ["X", "Y", "Z"])
    base = replace(cfg(["X", "Y", "Z"]), targets=(("Mid", .13),))
    anchored_cfg = replace(base, expected_return_method="anchored", growth_drift="estimated")
    plain_sharpe = PortfolioOptimizer(market, base).core_portfolios()["Maximum Sharpe"]["weights"]
    anchored_sharpe = PortfolioOptimizer(market, anchored_cfg).core_portfolios()["Maximum Sharpe"]["weights"]
    assert 0.5 * (plain_sharpe - anchored_sharpe).abs().sum() > .05
    # Documented limit: a binding ceiling with two active long-only assets pins the mix whatever the means.
    plain_w, metrics = robustness.fit_policies(market, base, risk_profiles=True)
    anchored_w = robustness.fit_policies(market, anchored_cfg, risk_profiles=True)[0]
    assert not metrics.loc["Mid", ["Fallback to Minimum Volatility", "Ceiling not binding (Maximum CAGR)"]].any()
    assert (plain_w["Mid"] > 1e-6).sum() == 2
    np.testing.assert_allclose(plain_w["Mid"], anchored_w["Mid"], atol=1e-6)


def test_near_redundant_corner_is_not_broken_by_anchoring(correlated_market):
    """Documented limit: with two near-identical assets the constrained optimum is a corner that only depends
    on the sign of their mean gap; anchoring shrinks the gap but keeps its sign, so the corner remains."""
    base = replace(cfg(["A", "B", "C"]), targets=(("Mid", .12),))
    plain = robustness.fit_policies(correlated_market, base, risk_profiles=True)[0]["Mid"]
    anchored = robustness.fit_policies(correlated_market, replace(base, expected_return_method="anchored",
                                                                  growth_drift="estimated"), risk_profiles=True)[0]["Mid"]
    assert plain["B"] < 1e-6 and anchored["B"] < 1e-6
    np.testing.assert_allclose(plain, anchored, atol=1e-6)


def test_anchored_requires_an_anchor_outside_the_optimizer(correlated_market):
    from portfolio_lab.expected_returns import estimate_expected_returns
    with pytest.raises(ValueError, match="anchor"):
        estimate_expected_returns(correlated_market.pct_change().dropna(), "anchored")


# --- Resampled efficiency --------------------------------------------------------------------------

def test_resampled_policies_are_deterministic_bounded_and_fully_invested(correlated_market):
    config = cfg(["A", "B", "C"], max_weights=(("A", .5),), resampling_draws=6)
    first, metrics = robustness.fit_policies(correlated_market, config, risk_profiles=True, risk_parity=True)
    second, _ = robustness.fit_policies(correlated_market, config, risk_profiles=True, risk_parity=True)
    for name, w in first.items():
        pd.testing.assert_series_equal(w, second[name])
        assert w.sum() == pytest.approx(1) and (w >= -1e-12).all() and w["A"] <= .5 + 1e-9
    assert ((metrics["Fallback to Minimum Volatility"] >= 0) & (metrics["Fallback to Minimum Volatility"] <= 1)).all()
    assert (metrics["Resamples used"] == 6).all()


def test_resampling_averages_away_corner_solutions(correlated_market):
    plain = robustness.fit_policies(correlated_market, cfg(["A", "B", "C"]), risk_profiles=True)[0]["High"]
    averaged = robustness.fit_policies(correlated_market, cfg(["A", "B", "C"], resampling_draws=8),
                                       risk_profiles=True)[0]["High"]
    assert (plain ** 2).sum() >= (averaged ** 2).sum() - 1e-9  # averaging cannot concentrate more


def test_invalid_resampling_rejected():
    with pytest.raises(ValueError):
        Config(assets=assets("A"), resampling_draws=-1)


# --- Diagnostics ------------------------------------------------------------------------------------

def test_mean_standard_error_is_annual_volatility_over_root_years():
    rng = np.random.default_rng(1)
    returns = rng.standard_normal((2520, 1)) * .01
    prices = prices_from(returns, ["X"])
    table = mean_uncertainty(prices)
    annual_vol = np.std(returns[:, 0], ddof=1) * np.sqrt(252)
    assert table.loc["X", "Standard error"] == pytest.approx(annual_vol / np.sqrt(2520 / 252), rel=1e-10)


def test_risk_distance_separates_substitution_from_exposure_change():
    sigma = pd.DataFrame([[.04, .0399, 0.], [.0399, .04, 0.], [0., 0., .04]], index=list("ABC"), columns=list("ABC"))
    swap = risk_distance(pd.Series({"A": 1., "B": 0., "C": 0.}), pd.Series({"A": 0., "B": 1., "C": 0.}), sigma)
    change = risk_distance(pd.Series({"A": 1., "B": 0., "C": 0.}), pd.Series({"A": 0., "B": 0., "C": 1.}), sigma)
    assert swap == pytest.approx(np.sqrt(2 * (.04 - .0399)))
    assert change == pytest.approx(np.sqrt(.08)) and change > 10 * swap
    weights = pd.DataFrame({"A": [1., 0.], "B": [0., 1.], "C": [0., 0.]}, index=[2013, 2014])
    table = exposure_changes(weights, sigma)
    assert table.loc[2014, "Instrument distance"] == 1 and table.loc[2014, "Risk distance"] == pytest.approx(swap)


def test_risk_contributions_and_pca_shares():
    sigma = pd.DataFrame(np.diag([.01, .04]), index=["X", "Y"], columns=["X", "Y"])
    rc = risk_contributions(pd.Series({"X": .5, "Y": .5}), sigma)
    np.testing.assert_allclose(rc, [.2, .8])
    rng = np.random.default_rng(2)
    factor = rng.standard_normal(3000)
    returns = np.column_stack([factor + .1 * rng.standard_normal(3000), factor + .1 * rng.standard_normal(3000),
                               rng.standard_normal(3000)]) * .01
    pca = principal_components(prices_from(returns, ["P", "Q", "R"]))
    assert pca.loc["Explained share", "PC1"] > .6 and pca.loc["Explained share"].sum() == pytest.approx(1)


def test_shared_config_keeps_reference_and_michaud_active_without_leverage():
    research = load_research_config(ROOT)
    methods = research.methods()
    assert research.config.leverage == ()
    kinds = {(c.expected_return_method, c.growth_drift, c.resampling_draws) for c in methods.values()}
    # Phase 7B: reference and Michaud active; the anchored method stays available (tested above).
    assert kinds == {("sample", "sample", 0), ("sample", "sample", 50)}
    assert dict(research.config.max_weights) == {"Gold": .10, "Apple": .40, "Coca-Cola": .10}


def test_frontier_checks_use_the_optimized_objective_with_an_estimated_drift(correlated_market):
    from portfolio_lab.optimization import optimize_frontier
    anchored = cfg(["A", "B", "C"], expected_return_method="anchored", growth_drift="estimated")
    result = optimize_frontier(correlated_market, anchored)   # must not fail on realized-CAGR monotonicity
    optimizer = PortfolioOptimizer(correlated_market, anchored)
    growth = [optimizer.model_growth(w) for w in result.frontier["weights"]]
    assert all(b >= a - 1e-7 for a, b in zip(growth, growth[1:]))


def test_resampling_field_added_later_does_not_make_old_evaluations_look_new():
    from portfolio_lab.experiments import evaluation_fingerprint
    old = {"config": {"assets": ["a"], "max_weights": []}, "evaluated_universe": ["A"], "policies": ["P"],
           "benchmark": None, "walk_forward_used": {}}
    new = {**old, "config": {**old["config"], "resampling_draws": 0}}
    assert evaluation_fingerprint(old) == evaluation_fingerprint(new)
    assert evaluation_fingerprint(old) != evaluation_fingerprint({**old, "config": {**old["config"], "resampling_draws": 50}})


# --- Phase 7A data-quality diagnostics ----------------------------------------------------------

def test_series_quality_flags_jumps_gaps_and_stale_closes():
    from portfolio_lab.diagnostics import series_quality
    dates = pd.bdate_range("2010-01-04", periods=8)
    s = pd.Series([100, 100, 101, 145, 102, 103, np.nan, 104.], index=dates, name="X")
    q = series_quality(s.drop(dates[5]))
    assert q["Missing in raw"] == 1 and q["Unchanged closes"] == 1
    assert q["|daily return| > 10%"] == 2 and q["Largest daily move"] == pytest.approx(.4356, abs=1e-3)
    assert q["Max gap (days)"] == 5   # Friday 8 -> Wednesday 13 (Monday dropped, Tuesday missing)


def test_asynchrony_detects_a_one_day_lag():
    from portfolio_lab.diagnostics import asynchrony
    rng = np.random.default_rng(5)
    dates = pd.bdate_range("2005-01-03", periods=1500)
    shocks = rng.standard_normal(1500) * .01
    early = pd.Series(100 * np.cumprod(1 + shocks), index=dates)
    late = pd.Series(100 * np.cumprod(1 + np.r_[0, shocks[:-1]]), index=dates)   # same moves, one day later
    out = asynchrony(early, late)
    assert out["Daily correlation"] < .1 and out["Weekly correlation"] > .7
