"""Stability diagnostics: hand-computed values, training-only sensitivity, variants, plan registry."""
import numpy as np
import pandas as pd
import pytest

import portfolio_lab.robustness as robustness
from portfolio_lab.assets import Asset
from portfolio_lab.config import Config, WalkForwardSettings
from portfolio_lab.experiments import (distinct_configurations, evaluation_fingerprint, load_entries,
                                       record_experiment, register_plan)
from portfolio_lab.research import parse_research_config
from portfolio_lab.robustness import compare_universes, variant_config, walk_forward
from portfolio_lab.stability import (concentration_path, largest_changes, persistent_holdings, realized_risk,
                                     stability_table, target_changes, training_bootstrap, window_sensitivity,
                                     zero_large_switches)


def weights_table():
    return pd.DataFrame({"A": [.5, .5, .10, .30], "B": [.5, .5, .60, .00], "C": [0., 0., .30, .70]},
                        index=[2013, 2014, 2015, 2016])


def test_target_change_is_half_the_l1_distance():
    d = target_changes(weights_table())
    assert np.isnan(d.loc[2013])
    assert d.loc[2014] == 0                       # identical consecutive targets
    assert d.loc[2015] == pytest.approx(.5 * (.4 + .1 + .3))
    assert d.loc[2016] == pytest.approx(.5 * (.2 + .6 + .4))


def test_concentration_metrics():
    path = concentration_path(weights_table())
    assert path.loc[2013, "HHI"] == pytest.approx(.5) and path.loc[2013, "Effective assets"] == pytest.approx(2)
    assert path.loc[2016, "Max weight"] == pytest.approx(.7) and path.loc[2016, "Largest holding"] == "C"


def test_switches_largest_changes_and_persistence():
    w = weights_table()
    sw = zero_large_switches(w)
    assert set(zip(sw["Year"], sw["Asset"])) == {(2015, "C"), (2016, "B")}
    top = largest_changes(w, 2)
    assert sorted(top["Change"].abs().round(2)) == [.4, .6]
    assert persistent_holdings(w) == ["A"]          # A never falls below 10%
    assert persistent_holdings(w.assign(A=[.05, .2, .2, .2])) == []


def make_market():
    dates = pd.bdate_range("2000-12-29", "2019-12-31")
    rng = np.random.default_rng(11)
    r = rng.normal([.0005, .0003, .0002, .0003], [.015, .010, .006, .009], (len(dates), 4))
    prices = pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=dates, columns=["A", "B", "C", "M"])
    assets = tuple(Asset(n, n, "s", "EUR", "Gross Return", "x") for n in "ABCM")
    cfg = Config(assets=assets, eligible=("A", "B", "C"), benchmark="M", frontier_points=4,
                 targets=(("Low", .08), ("High", .30)), max_weights=(("A", .4),),
                 walk_forward=WalkForwardSettings(first_test_year=2016, last_test_year=2018, rebalance="annual",
                                                  decision_lag_sessions=1, transaction_cost_bps=10))
    return prices, cfg


@pytest.fixture(scope="module")
def market():
    return make_market()


@pytest.fixture(scope="module")
def run(market):
    prices, cfg = market
    return walk_forward(prices, cfg, risk_profiles=True)


def test_stability_table_separates_target_change_from_traded_turnover(run):
    table = stability_table(run)
    for name in run.strategies:
        d = target_changes(run.weights[name]).dropna()
        assert table.loc[name, "Mean target change"] == pytest.approx(d.mean())
        assert table.loc[name, "Mean traded turnover"] == pytest.approx(run.trading[name].iloc[1:].mean())
    # Equal weight never changes its targets but still trades after drift.
    assert table.loc["Equal Weight", "Mean target change"] == 0
    assert table.loc["Equal Weight", "Mean traded turnover"] > 0
    # Constraints remain respected in every fold.
    for name in run.policies + ["Constrained Equal Weight"]:
        assert (run.weights[name]["A"] <= .4 + 1e-9).all()


def test_realized_risk_uses_the_test_year_only(run):
    risk = realized_risk(run)
    year = run.folds[0].test_year
    expected = run.oos_returns.loc[str(year), "Maximum Sharpe"].std(ddof=1) * np.sqrt(252)
    assert risk.loc[("Maximum Sharpe", year), "Realized volatility"] == pytest.approx(expected)
    assert risk.loc[("Maximum Sharpe", year), "Estimated volatility"] == pytest.approx(
        run.train_metrics.loc[("Maximum Sharpe", year), "Estimated volatility"])


def test_window_sensitivity_is_zero_against_itself(run):
    distance, summary = window_sensitivity(run, run)
    assert (distance == 0).all().all()
    assert (summary["CAGR (primary)"] == summary["CAGR (alternative)"]).all()


def test_training_bootstrap_is_deterministic_and_ignores_test_years(market, run):
    prices, cfg = market
    first = training_bootstrap(prices, cfg, run, replications=4, seed=3, workers=1)
    again = training_bootstrap(prices, cfg, run, replications=4, seed=3, workers=1)
    pd.testing.assert_frame_equal(first.draws, again.draws)
    # Changing every test-year price leaves the bootstrap draws unchanged for that fold.
    shocked = prices.copy()
    shocked.loc["2018-01-01":, "A"] *= 3
    after = training_bootstrap(shocked, cfg, run, replications=4, seed=3, workers=1)
    pd.testing.assert_frame_equal(first.draws.xs(2018, level="Year"), after.draws.xs(2018, level="Year"))
    assert (first.draws.sum(axis=1) - 1).abs().max() < 1e-8
    assert (first.draws["A"] <= .4 + 1e-9).all()
    assert set(first.distance.columns) == set(run.policies)


def test_variant_changes_only_eligibility_or_leverage():
    assets = tuple(Asset(n, n, "s", "EUR", "Gross Return", "x") for n in ("Apple", "Nasdaq 100", "Gold"))
    cfg = Config(assets=assets, leverage=(("Nasdaq 100", 2.0),), max_weights=(("Gold", .1),))
    unlevered = variant_config(cfg, unlevered=["Nasdaq 100"])
    assert unlevered.leverage == () and unlevered.max_weights == cfg.max_weights
    assert robustness.select_frontier_assets(unlevered) == ["Apple", "Nasdaq 100", "Gold"]
    excluded = variant_config(cfg, excluded=["Nasdaq 100"])
    assert robustness.select_frontier_assets(excluded) == ["Apple", "Gold"]
    with pytest.raises(ValueError):
        variant_config(cfg, unlevered=["Apple"])


def test_unlevered_variant_runs_on_the_same_prices(market):
    prices, cfg = market
    prices = prices.assign(**{"A x2": prices["A"] * (prices["A"] / prices["A"].iloc[0])})
    levered = Config(**{**cfg.__dict__, "leverage": (("A", 2.0),), "max_weights": ()})
    comparison = compare_universes(prices, levered, {"x2": [], "1x": {"unlevered": ["A"]}})
    assert "A x2" in comparison.results["x2"].universe and "A" in comparison.results["1x"].universe
    pd.testing.assert_index_equal(comparison.results["x2"].oos_returns.index, comparison.results["1x"].oos_returns.index)


def test_research_config_parses_unlevered_variants():
    raw = {"universe": {"Apple": "AAPL", "Nasdaq 100": "QQQ"}, "leverage": {"Nasdaq 100": 2.0},
           "universe_variants": {"1x": {"unlevered": ["Nasdaq 100"]}, "No Apple": ["Apple"]}}
    research = parse_research_config(raw)
    assert research.variants() == {"1x": {"exclude": (), "unlevered": ("Nasdaq 100",)},
                                   "No Apple": {"exclude": ("Apple",), "unlevered": ()}}
    with pytest.raises(ValueError):
        parse_research_config({**raw, "universe_variants": {"bad": {"unlevered": ["Apple"]}}})


def test_plans_precede_results_and_exposure_is_flagged(market, run, tmp_path, monkeypatch):
    import portfolio_lab.experiments as experiments
    monkeypatch.setattr(experiments, "code_version", lambda _: {"commit": "c", "dirty": False, "worktree_hash": "h"})
    registry = tmp_path / "experiments" / "registry.jsonl"
    plan = register_plan(registry, label="p", hypothesis="h", questions=["q"])
    research = parse_research_config({"universe": {"Apple": "AAPL"}}, tmp_path)
    first = record_experiment(run, research, label="a", registry=registry, category="exploratory")
    # Adding a universe variant to the YAML does not make the same evaluation look new.
    research2 = parse_research_config({"universe": {"Apple": "AAPL"}, "universe_variants": {"x": []}}, tmp_path)
    second = record_experiment(run, research2, label="a", registry=registry, category="exploratory")
    assert first["previously_evaluated"] is False and second["previously_evaluated"] is True
    assert second["rerun_of"] == first["id"]
    entries = load_entries(registry)
    assert entries[0]["kind"] == "plan" and entries[0]["id"] == plan["id"]
    assert distinct_configurations(registry) == 1
    assert evaluation_fingerprint(first["snapshot"]) == evaluation_fingerprint(second["snapshot"])
