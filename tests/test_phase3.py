"""Phase 3: point-in-time rates, leverage financing, holding costs, investable benchmark, provenance.

Synthetic data only, all dated before the holdout; expected values are computed by hand.
"""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import portfolio_lab.robustness as robustness
from portfolio_lab.assets import Asset
from portfolio_lab.config import Config, WalkForwardSettings
from portfolio_lab.data import FREDProvider
from portfolio_lab.experiments import decision_log, record_experiment
from portfolio_lab.leverage import add_leverage, build_daily_leveraged_series
from portfolio_lab.optimization import constrained_equal_weights, optimize_frontier
from portfolio_lab.protocol import HoldoutAccessError
from portfolio_lab.rates import RateSpec, Rates, available_from, point_in_time
from portfolio_lab.research import load_research_config, parse_research_config
from portfolio_lab.returns import apply_holding_costs

ROOT = Path(__file__).resolve().parents[1]


def assets(*names, currency="EUR"):
    return tuple(Asset(n, n, "s", currency, "Gross Return", "x") for n in names)


# --- Rates --------------------------------------------------------------------------------------

def test_daily_rates_are_usable_the_next_day_and_never_back_filled():
    raw = pd.Series([1.0, 2.0, -0.5], index=pd.to_datetime(["2015-01-05", "2015-01-06", "2015-01-08"]), name="DTB3")
    index = pd.to_datetime(["2015-01-06", "2015-01-07", "2015-01-08", "2015-01-09"])
    known = point_in_time(raw, index, "daily")
    np.testing.assert_allclose(known, [.010, .020, .020, -.005])  # negative rates allowed
    with pytest.raises(ValueError, match="back-filled"):
        point_in_time(raw, pd.to_datetime(["2015-01-05"]), "daily")


def test_monthly_averages_wait_for_publication():
    raw = pd.Series([3.0, 4.0], index=pd.to_datetime(["2015-01-01", "2015-02-01"]), name="EUR3M")
    shifted = available_from(raw, "monthly")
    assert list(shifted.index) == list(pd.to_datetime(["2015-03-01", "2015-04-01"]))
    known = point_in_time(raw, pd.to_datetime(["2015-03-31", "2015-04-01"]), "monthly")
    np.testing.assert_allclose(known, [.03, .04])


def test_rate_spec_parsing():
    assert RateSpec.parse(.015).constant == .015
    assert RateSpec.parse("DTB3").series == "DTB3"
    for bad in ("UNKNOWN", True, 2.0):
        with pytest.raises(ValueError):
            RateSpec.parse(bad)


def test_fred_rate_history_accepts_negative_rates_and_respects_the_lock(tmp_path):
    csv = "observation_date,IR3TIB01EZM156N\n2015-01-01,0.07\n2015-02-01,-0.01\n2015-03-01,\n"
    provider = FREDProvider(tmp_path, fetch_csv=lambda series, last: csv)
    series = provider.rate_history("IR3TIB01EZM156N", "2020-01-01")
    np.testing.assert_allclose(series, [.07, -.01])
    with pytest.raises(HoldoutAccessError):
        provider.rate_history("IR3TIB01EZM156N", "2021-01-01")


def test_mean_risk_free_over_a_window():
    raw = pd.Series([2.0, 0.0], index=pd.to_datetime(["2014-12-31", "2015-01-02"]), name="DTB3")
    rates = Rates(RateSpec(series="DTB3"), {}, {"DTB3": raw})
    index = pd.to_datetime(["2015-01-02", "2015-01-05", "2015-01-06"])  # 2% known, then 0% from the 3rd
    assert rates.mean_risk_free(index) == pytest.approx((.02 + 0 + 0) / 3)


# --- Leverage financing -------------------------------------------------------------------------

def test_time_varying_financing_uses_the_rate_known_at_the_start_of_each_interval():
    dates = pd.to_datetime(["2015-01-02", "2015-01-05", "2015-01-06"])
    underlying = pd.Series([100., 100., 100.], index=dates, name="U")
    cost = pd.Series([.0365, .073, .5], index=dates)  # the last value must never be used
    nav = build_daily_leveraged_series(underlying, 2., 100., cost, calendar_days_per_year=365.)
    assert nav.iloc[1] == pytest.approx(100 * (1 - .0365 * 3 / 365))
    assert nav.iloc[2] == pytest.approx(nav.iloc[1] * (1 - .073 / 365))


def test_add_leverage_finances_in_the_product_currency_plus_spread():
    dates = pd.bdate_range("2015-01-01", periods=6)
    native = {"U": pd.Series(100., index=dates, name="U")}
    common = pd.DataFrame({"U": native["U"]})
    cfg = Config(assets=assets("U", currency="USD"), leverage=(("U", 2.0),), leverage_annual_fee=.006,
                 leverage_financing_spread=.004)
    rates = Rates(RateSpec(constant=0.), {"USD": RateSpec(constant=.02), "EUR": RateSpec(constant=.5)}, {})
    fx = pd.Series(1., index=dates)
    prices, diagnostics = add_leverage(common, native, fx, cfg, rates=rates)
    expected_cost = .006 + 1 * (.02 + .004)
    assert diagnostics["Annual cost (fee + financing)"].iloc[0] == pytest.approx(expected_cost)
    days = (dates[-1] - dates[0]).days
    flat = np.prod([1 - expected_cost * d / 365.25 for d in np.diff(dates).astype("timedelta64[D]").astype(int)])
    assert prices["U x2"].iloc[-1] / prices["U x2"].iloc[0] == pytest.approx(flat)
    assert days == 7


# --- Holding costs ------------------------------------------------------------------------------

def test_holding_costs_accrue_on_calendar_days_and_only_where_configured():
    dates = pd.to_datetime(["2015-01-02", "2015-01-05", "2015-01-06"])
    prices = pd.DataFrame({"Index": [100., 101., 102.], "ETF": [50., 50., 50.]}, index=dates)
    out = apply_holding_costs(prices, {"Index": .0365}, calendar_days_per_year=365.)
    assert out["Index"].iloc[0] == 100.
    assert out["Index"].iloc[1] == pytest.approx(101 * (1 - .0365 * 3 / 365))
    assert out["Index"].iloc[2] == pytest.approx(102 * (1 - .0365 * 3 / 365) * (1 - .0365 / 365))
    pd.testing.assert_series_equal(out["ETF"], prices["ETF"])


def test_holding_costs_cannot_target_leveraged_labels_or_unknown_assets():
    with pytest.raises(ValueError):
        Config(assets=assets("U"), leverage=(("U", 2.0),), holding_costs=(("U x2", .01),))
    with pytest.raises(ValueError):
        Config(assets=assets("U"), holding_costs=(("U", .2),))


# --- Constrained equal weight -------------------------------------------------------------------

def test_constrained_equal_weight_is_the_closest_feasible_portfolio_to_one_over_n():
    cfg = Config(assets=assets(*"ABCDEFG"), max_weights=(("A", .10), ("B", .40)))
    w = constrained_equal_weights(list("ABCDEFG"), cfg)
    assert w["A"] == pytest.approx(.10) and w["B"] == pytest.approx(.15)
    np.testing.assert_allclose(w.drop(["A"]), .15)
    assert w.sum() == pytest.approx(1)
    plain = constrained_equal_weights(list("ABC"), Config(assets=assets(*"ABC")))
    np.testing.assert_allclose(plain, 1 / 3)
    floors = constrained_equal_weights(list("ABCD"), Config(assets=assets(*"ABCD"), min_weights=(("A", .4),)))
    assert floors["A"] == pytest.approx(.4) and floors.drop("A").tolist() == pytest.approx([.2] * 3)


def test_constrained_equal_weight_fails_on_infeasible_bounds_and_ignores_ineligible_caps():
    cfg = Config(assets=assets("A", "B", "C"), max_weights=(("A", .3), ("B", .3)))
    with pytest.raises(ValueError, match="infeasible"):
        constrained_equal_weights(["A", "B"], cfg)  # only A and B eligible: 60% < 100%
    w = constrained_equal_weights(["B", "C"], cfg)  # the cap on A is moot here
    assert w["B"] == pytest.approx(.3) and w["C"] == pytest.approx(.7)


def test_optimizer_detects_the_same_infeasibility():
    dates = pd.bdate_range("2010-01-01", periods=300)
    rng = np.random.default_rng(1)
    prices = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, .01, (300, 2)), axis=0), index=dates, columns=["A", "B"])
    cfg = Config(assets=assets("A", "B"), max_weights=(("A", .3), ("B", .3)), frontier_points=3)
    with pytest.raises(ValueError, match="infeasible"):
        optimize_frontier(prices, cfg)


@pytest.fixture
def market():
    dates = pd.bdate_range("2000-12-29", "2019-12-31")
    rng = np.random.default_rng(5)
    returns = rng.normal([.0005, .0003, .0002, .0003], [.015, .010, .006, .009], (len(dates), 4))
    prices = pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=dates, columns=list("ABCM"))
    cfg = Config(assets=assets(*"ABCM"), eligible=("A", "B", "C"), benchmark="M", max_weights=(("A", .2),),
                 frontier_points=5, targets=(("Low", .08),),
                 walk_forward=WalkForwardSettings(first_test_year=2013, last_test_year=2015, rebalance="annual",
                                                  decision_lag_sessions=1, transaction_cost_bps=10))
    return prices, cfg


def test_walk_forward_constrained_benchmark_respects_caps_and_shares_the_accounting(market):
    prices, cfg = market
    wf = robustness.walk_forward(prices, cfg)
    w = wf.weights[robustness.CONSTRAINED_EQUAL_WEIGHT]
    assert (w["A"] <= .2 + 1e-12).all() and np.allclose(w.sum(axis=1), 1)
    assert (wf.weights[robustness.EQUAL_WEIGHT]["A"] > .2).all()  # the descriptive one ignores the cap
    assert wf.costs.loc[2013, robustness.CONSTRAINED_EQUAL_WEIGHT] == pytest.approx(.001)  # bought from cash
    assert wf.benchmarks == [robustness.CONSTRAINED_EQUAL_WEIGHT, robustness.EQUAL_WEIGHT, "M"]


def test_walk_forward_uses_point_in_time_risk_free_means(market, monkeypatch):
    prices, cfg = market
    raw = pd.Series(np.where(prices.index.year < 2010, 4.0, 0.0), index=prices.index, name="DTB3")
    rates = Rates(RateSpec(series="DTB3"), {}, {"DTB3": raw})
    seen = {}
    original = robustness.fit_policies

    def spy(train, config, risk_profiles=False):
        seen[train.index[-1].year + 1] = (config.risk_free_rate, rates.mean_risk_free(train.index))
        return original(train, config, risk_profiles)

    monkeypatch.setattr(robustness, "fit_policies", spy)
    wf = robustness.walk_forward(prices, cfg, rates=rates)
    for used, expected in seen.values():
        assert used == pytest.approx(expected) and used > 0
    # OOS Sharpe uses the (zero) rate published over 2013-2015.
    nav = wf.nav
    returns = nav.pct_change().dropna()
    sharpe = returns.mean() * 252 / (returns.std() * np.sqrt(252))
    np.testing.assert_allclose(wf.metrics["Sharpe"], sharpe.loc[wf.metrics.index], rtol=1e-10)


# --- Investor preferences, provenance and the decision log ---------------------------------------

def test_shared_config_keeps_the_investor_preferences_with_provenance():
    research = load_research_config(ROOT)
    assert dict(research.config.max_weights) == {"Gold": .10, "Apple": .40}
    assert "not pre-registered" in research.constraint_provenance
    assert research.snapshot()["constraint_provenance"] == research.constraint_provenance


def test_constraints_require_a_provenance_note_and_stay_editable():
    base = {"universe": {"Apple": "AAPL", "Gold": "GC=F", "Coca-Cola": "KO"}}
    with pytest.raises(ValueError, match="provenance"):
        parse_research_config({**base, "constraints": {"max_weights": {"Gold": .1}}})
    edited = parse_research_config({**base, "constraints": {"max_weights": {"Gold": .15, "Apple": .25},
                                                            "provenance": "investor change"}})
    assert dict(edited.config.max_weights) == {"Gold": .15, "Apple": .25}


def test_decision_log_tracks_preference_changes(market, tmp_path, monkeypatch):
    import portfolio_lab.experiments as experiments
    prices, cfg = market
    monkeypatch.setattr(experiments, "code_version", lambda _: {"commit": "c", "dirty": False, "worktree_hash": "h"})
    base = {"universe": {"Apple": "AAPL", "Gold": "GC=F"}}
    registry = tmp_path / "registry.jsonl"
    wf = robustness.walk_forward(prices, cfg)
    first = parse_research_config({**base, "constraints": {"max_weights": {"Gold": .1}, "provenance": "p"}}, tmp_path)
    second = parse_research_config({**base, "constraints": {"max_weights": {"Gold": .15}, "provenance": "p"}}, tmp_path)
    record_experiment(wf, first, label="a", registry=registry, category="baseline")
    record_experiment(wf, second, label="b", registry=registry, category="baseline")
    with pytest.raises(ValueError, match="hypothesis"):
        record_experiment(wf, second, label="c", registry=registry, category="selection")
    log = decision_log(registry)
    assert list(log["Changements"]) == ["initial", "max_weights"]
