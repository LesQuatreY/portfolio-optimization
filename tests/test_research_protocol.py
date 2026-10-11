"""Safety guards of the research protocol: holdout lock, eligibility, strict walk-forward, costs.

All data here are synthetic and dated before the holdout; the guard itself is tested with
synthetic dates only (no real 2020+ observation is ever read).
"""
from dataclasses import replace
from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest

from portfolio_lab.config import Asset, Config, WalkForwardSettings, with_eligible, with_min_weights
from portfolio_lab.data import CSVProvider, load_market_data
from portfolio_lab.experiments import distinct_configurations, load_entries, record_experiment
from portfolio_lab.leverage import build_daily_leveraged_series
from portfolio_lab.metrics import compute_asset_metrics
from portfolio_lab.optimization import PortfolioOptimizer, optimize_frontier, select_frontier_assets
from portfolio_lab.protocol import (HOLDOUT_START, HoldoutAccessError, assert_dates_before_holdout,
                                    assert_end_allowed, assert_file_safe, find_holdout_dates,
                                    notebook_holdout_dates)
from portfolio_lab.research import load_research_config, parse_research_config
from portfolio_lab.returns import simple_returns
from portfolio_lab.robustness import (EQUAL_WEIGHT, OPTIMIZED, compare_universes, hold_returns,
                                      relative_growth_interval, walk_forward, walk_forward_folds)

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["A", "B", "C", "M"]


def synthetic(start="1999-12-31", end="2019-12-31", seed=3):
    dates = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    returns = rng.normal([.0005, .0003, .0002, .0003], [.015, .010, .006, .009], (len(dates), 4))
    return pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=dates, columns=NAMES)


@pytest.fixture(scope="module")
def prices():
    return synthetic()


def make_config(**kwargs):
    assets = tuple(Asset(n, n, "synthetic", "EUR", "Gross Return", "x") for n in NAMES)
    settings = WalkForwardSettings(train_years=10, first_test_year=2013, last_test_year=2019,
                                   rebalance="annual", decision_lag_sessions=1, transaction_cost_bps=10)
    base = dict(assets=assets, eligible=("A", "B", "C"), benchmark="M", walk_forward=settings,
                targets=(("Low", .08), ("High", .3)), frontier_points=5)
    base.update(kwargs)
    return Config(**base)


# --- Holdout lock -----------------------------------------------------------------------------

@pytest.mark.parametrize("end", ["2020-01-02", "2026-10-05", "2030-01-01"])
def test_config_cannot_reach_the_holdout(end):
    with pytest.raises(HoldoutAccessError):
        make_config(end=end)
    with pytest.raises(HoldoutAccessError):
        assert_end_allowed(end)


def test_boundary_and_earlier_ends_are_allowed():
    assert make_config(end="2020-01-01").end == "2020-01-01"
    assert make_config(end="2015-06-30").end == "2015-06-30"
    assert Config(assets=make_config().assets).end == "2020-01-01"


def test_invalid_end_fails_safely():
    with pytest.raises(ValueError):
        make_config(end="not-a-date")


def test_any_holdout_date_in_prices_is_rejected_by_every_computation(prices):
    shifted = prices.copy()
    shifted.index = shifted.index + pd.Timedelta(days=366)  # synthetic dates reaching 2020
    assert shifted.index.max() >= HOLDOUT_START
    cfg = make_config()
    with pytest.raises(HoldoutAccessError):
        simple_returns(shifted)
    with pytest.raises(HoldoutAccessError):
        compute_asset_metrics(shifted)
    with pytest.raises(HoldoutAccessError):
        PortfolioOptimizer(shifted[["A", "B", "C"]], cfg)
    with pytest.raises(HoldoutAccessError):
        walk_forward(shifted, cfg)
    with pytest.raises(HoldoutAccessError):
        walk_forward_folds(shifted.index, 10)


def test_providers_refuse_holdout_requests(tmp_path):
    asset = Asset("A", "A", "synthetic", "EUR", "Gross Return", "x")
    pd.DataFrame({"Date": pd.date_range("2019-12-30", periods=5), "Value": [1., 2, 3, 4, 5]}).to_csv(
        tmp_path / "A.csv", index=False)
    with pytest.raises(HoldoutAccessError):
        CSVProvider(tmp_path).history(asset, "2021-01-01")
    # A normal request silently stops before the boundary, even if the file holds later rows.
    assert CSVProvider(tmp_path).history(asset, "2020-01-01").index.max() < HOLDOUT_START


def test_provider_returning_holdout_rows_is_rejected():
    cfg = make_config()

    class Leaky:
        name = "leaky"

        def history(self, asset, end):
            return pd.Series(100., index=pd.date_range("2019-12-27", "2020-01-03"), name=asset.name)

    with pytest.raises(HoldoutAccessError):
        load_market_data(cfg, Leaky())


def test_holdout_date_scanner():
    assert find_holdout_dates("study end 2020-01-01, last 2019-12-31") == []
    assert find_holdout_dates("rows 2020-03-16 and 2026/10/02") == ["2020-03-16", "2026/10/02"]
    assert find_holdout_dates("run 20261011T101500Z commit abc") == []


def test_exports_with_holdout_dates_are_flagged(tmp_path):
    good, bad = tmp_path / "good.csv", tmp_path / "bad.csv"
    good.write_text("Date,Value\n2019-12-31,1\n", encoding="utf-8")
    bad.write_text("Date,Value\n2020-01-02,1\n", encoding="utf-8")
    assert_file_safe(good)
    with pytest.raises(HoldoutAccessError):
        assert_file_safe(bad)


@pytest.mark.parametrize("name", ["portfolio_analysis.ipynb", "portfolio_robustness.ipynb"])
def test_active_notebooks_hold_no_holdout_outputs_and_use_shared_config(name):
    path = ROOT / "notebooks" / name
    assert notebook_holdout_dates(path) == []
    sources = "\n".join("".join(cell["source"]) for cell in json.loads(path.read_text(encoding="utf-8"))["cells"]
                        if cell["cell_type"] == "code")
    assert "load_research_study" in sources
    # No notebook-local universe, end-date or package-default configuration.
    for forbidden in ("load_config(", "configure_universe(", "end=", "yfinance", "mscidata", "fredgraph"):
        assert forbidden not in sources, forbidden


def test_shared_research_config_is_locked_and_consistent():
    research = load_research_config(ROOT)
    cfg = research.config
    assert pd.Timestamp(cfg.end) <= HOLDOUT_START
    assert cfg.walk_forward.last_test_year <= 2019 and cfg.walk_forward.first_test_year == 2013
    assert pd.Timestamp(cfg.development_end) == pd.Timestamp("2013-01-01")
    assert cfg.benchmark in [a.name for a in cfg.assets]
    assert set(research.eligible) <= {a.name for a in cfg.assets}


def test_research_config_rejects_holdout_end_and_unknown_keys():
    raw = {"universe": {"Apple": "AAPL"}, "protocol": {"study_end": "2024-01-01"}}
    with pytest.raises(HoldoutAccessError):
        parse_research_config(raw)
    with pytest.raises(ValueError, match="unknown sections"):
        parse_research_config({"universe": {"Apple": "AAPL"}, "holdout": {"unlock": True}})
    with pytest.raises(ValueError, match="variant"):
        parse_research_config({"universe": {"Apple": "AAPL"}, "universe_variants": {"x": ["Gold"]}})


# --- Asset universe ---------------------------------------------------------------------------

def test_ineligible_assets_never_receive_direct_weight(prices):
    cfg = make_config()
    assert select_frontier_assets(cfg) == ["A", "B", "C"]
    result = optimize_frontier(prices.loc[:"2012-12-31"], cfg)
    assert "M" not in result.weights.columns
    narrower = with_eligible(cfg, ["A", "C"])
    assert select_frontier_assets(narrower) == ["A", "C"]
    # Only eligibility changed.
    assert replace(narrower, eligible=cfg.eligible) == cfg
    wf = walk_forward(prices, narrower)
    for name in wf.policies + [EQUAL_WEIGHT]:
        assert list(wf.weights[name].columns) == ["A", "C"]


def test_ineligible_leveraged_underlying_is_excluded():
    cfg = make_config(leverage=(("A", 2.0),))
    assert select_frontier_assets(cfg) == ["A x2", "B", "C"]
    assert select_frontier_assets(with_eligible(cfg, ["B", "C"])) == ["B", "C"]


def test_enabled_assets_can_get_exactly_zero(prices):
    # A dominated asset (strongly negative drift, high volatility) is eligible but unused.
    bad = prices.copy()
    bad["C"] = 100 * np.cumprod(np.r_[1, np.full(len(bad) - 1, .997)])
    result = optimize_frontier(bad.loc[:"2012-12-31"], make_config())
    assert result.weights.loc["Maximum Sharpe", "C"] == pytest.approx(0, abs=1e-8)
    assert result.weights.loc["Maximum CAGR", "C"] == pytest.approx(0, abs=1e-8)


def test_weights_long_only_fully_invested_and_bounded(prices):
    cfg = replace(make_config(), max_weights=(("A", .3),))
    cfg = with_min_weights(cfg, {"C": .2})
    result = optimize_frontier(prices.loc[:"2012-12-31"], cfg)
    weights = pd.DataFrame([p["weights"] for p in result.portfolios.values() if p["weights"] is not None] +
                           [w for w in result.frontier["weights"] if w is not None])
    np.testing.assert_allclose(weights.sum(axis=1), 1, atol=1e-10)
    assert (weights >= -1e-12).all().all()
    assert (weights["A"] <= .3 + 1e-9).all() and (weights["C"] >= .2 - 1e-9).all()


@pytest.mark.parametrize("kwargs", [{"min_weights": (("A", .6), ("B", .6))},
                                    {"min_weights": (("A", .5),), "max_weights": (("A", .4),)},
                                    {"eligible": ("Z",)}, {"benchmark": "Z"}])
def test_infeasible_or_invalid_universe_settings_fail(kwargs):
    with pytest.raises(ValueError):
        make_config(**kwargs)


def test_caps_on_excluded_assets_are_moot_not_errors(prices):
    cfg = with_eligible(replace(make_config(), max_weights=(("A", .2),)), ["B", "C"])
    result = optimize_frontier(prices.loc[:"2012-12-31"], cfg)
    assert list(result.weights.columns) == ["B", "C"]


# --- Walk-forward correctness -----------------------------------------------------------------

def test_strict_folds_cover_exactly_2013_to_2019_and_never_train_on_the_test_year(prices):
    cfg = make_config()
    wf = walk_forward(prices, cfg)
    folds = wf.fold_table
    assert list(folds.index) == list(range(2013, 2020))
    for year, fold in folds.iterrows():
        assert fold["train_end"] < fold["rebalance_date"] < fold["test_start"]
        assert fold["train_end"].year == fold["rebalance_date"].year == year - 1
        assert fold["train_start"].year == year - 10
        assert fold["test_start"].year == fold["test_end"].year == year
        assert fold["complete_test_year"]
    oos = wf.oos_returns
    assert oos.index.is_unique and oos.index.is_monotonic_increasing
    assert oos.index.min().year == 2013 and oos.index.max() < HOLDOUT_START
    assert set(oos.index.year) == set(range(2013, 2020))


def test_decision_lag_excludes_the_rebalance_close_from_estimation(prices):
    cfg = make_config()
    lagged = walk_forward_folds(prices.index, 10, first_test_year=2013, last_test_year=2013, decision_lag=1)[0]
    plain = walk_forward_folds(prices.index, 10, first_test_year=2013, last_test_year=2013, decision_lag=0)[0]
    assert plain.train_end == plain.rebalance_date == lagged.rebalance_date
    assert lagged.train_end < lagged.rebalance_date
    # Shocking the rebalance-day close (after the decision) must not change the 2013 weights.
    shocked = prices.copy()
    shocked.loc[lagged.rebalance_date:, "A"] *= 3
    base, after = walk_forward(prices, cfg), walk_forward(shocked, cfg)
    for name in OPTIMIZED:
        pd.testing.assert_series_equal(base.weights[name].loc[2013], after.weights[name].loc[2013])


def test_test_year_data_cannot_influence_its_weights(prices):
    cfg = make_config()
    shocked = prices.copy()
    shocked.loc["2016-01-01":, "B"] *= np.linspace(.4, 2.5, (shocked.index >= "2016-01-01").sum())
    base, after = walk_forward(prices, cfg), walk_forward(shocked, cfg)
    for name in OPTIMIZED:
        for year in range(2013, 2017):
            pd.testing.assert_series_equal(base.weights[name].loc[year], after.weights[name].loc[year])
        assert not np.allclose(base.weights[name].loc[2019], after.weights[name].loc[2019])


def test_requested_year_without_full_history_fails_explicitly(prices):
    late = prices.loc["2005-06-01":]
    with pytest.raises(ValueError, match="2013"):
        walk_forward(late, make_config())


def test_incomplete_or_sparse_years_fail_explicitly(prices):
    with pytest.raises(ValueError, match="incomplete"):
        walk_forward(prices.loc[:"2019-06-28"], make_config())
    gappy = prices.drop(prices.loc["2009-02-01":"2009-11-30"].index)
    with pytest.raises(ValueError, match="sessions"):
        walk_forward(gappy, make_config())


def test_expanding_window_uses_all_history_with_same_test_years(prices):
    cfg = make_config()
    rolling = walk_forward(prices, cfg)
    expanding = walk_forward(prices, replace(cfg, walk_forward=replace(cfg.walk_forward, window="expanding")))
    assert list(expanding.fold_table.index) == list(rolling.fold_table.index)
    assert (expanding.fold_table["return_base"] == prices.index[0]).all()
    assert (expanding.fold_table["train_returns"] > rolling.fold_table["train_returns"]).all()


def test_annual_holding_drifts_and_costs_follow_traded_notional(prices):
    cfg = make_config()
    wf = walk_forward(prices, cfg)
    gross_free = walk_forward(prices, replace(cfg, walk_forward=replace(cfg.walk_forward, transaction_cost_bps=0)))
    pd.testing.assert_frame_equal(gross_free.oos_returns, wf.gross_returns)
    rate = cfg.walk_forward.transaction_cost_bps / 1e4
    # First year: bought from cash (traded notional = 1, one-way turnover = 0.5).
    for name in wf.strategies:
        assert wf.trading.loc[2013, name] == pytest.approx(.5)
        assert wf.costs.loc[2013, name] == pytest.approx(rate)
        first = wf.oos_returns.loc["2013", name].iloc[0]
        assert first == pytest.approx((1 + wf.gross_returns.loc["2013", name].iloc[0]) * (1 - rate) - 1)
    # Later years: cost = rate x |target - drifted holdings|.
    fold = wf.folds[1]
    returns = simple_returns(prices.loc[wf.folds[0].rebalance_date:wf.folds[0].test_end, ["A", "B", "C"]])
    _, drifted = hold_returns(returns, wf.weights["Maximum Sharpe"].loc[2013], "annual")
    traded = (wf.weights["Maximum Sharpe"].loc[2014] - drifted).abs().sum()
    assert wf.costs.loc[2014, "Maximum Sharpe"] == pytest.approx(rate * traded)
    # The passive benchmark is bought once and never traded again.
    assert wf.costs[cfg.benchmark].iloc[1:].eq(0).all()
    assert (wf.metrics["CAGR"] <= wf.gross_metrics["CAGR"] + 1e-15).all()
    assert fold.test_year == 2014


def test_hold_returns_buy_and_hold_math():
    returns = pd.DataFrame({"X": [.10, -.50], "Y": [0., .20]}, index=pd.date_range("2015-01-01", periods=2))
    weights = pd.Series({"X": .5, "Y": .5})
    gross, end = hold_returns(returns, weights, "annual")
    # Values: day1 .5*1.1 + .5*1 = 1.05; day2 .5*.55 + .5*1.2 = .875.
    np.testing.assert_allclose(gross, [.05, .875 / 1.05 - 1])
    np.testing.assert_allclose(end, [.275 / .875, .6 / .875])
    daily, same = hold_returns(returns, weights, "daily")
    np.testing.assert_allclose(daily, [.05, -.15])
    pd.testing.assert_series_equal(same, weights)


def test_risk_profiles_are_fitted_and_evaluated_like_other_policies(prices):
    wf = walk_forward(prices, make_config(), risk_profiles=True)
    assert wf.policies == ["Maximum Sharpe", "Minimum Volatility", "Low", "High"]
    assert "Fallback to Minimum Volatility" in wf.train_metrics
    summary = wf.summary()
    assert list(summary.index) == [*wf.policies, "Constrained Equal Weight", EQUAL_WEIGHT, "M"]
    assert summary["CAGR excluding best year"].notna().all()


def test_universe_comparison_changes_only_eligibility(prices):
    cfg = make_config()
    comparison = compare_universes(prices, cfg, {"Complet": [], "Sans A": ["A"]})
    full, without = comparison.results["Complet"], comparison.results["Sans A"]
    assert list(without.weights["Maximum Sharpe"].columns) == ["B", "C"]
    pd.testing.assert_index_equal(full.oos_returns.index, without.oos_returns.index)
    pd.testing.assert_series_equal(full.oos_returns["M"], without.oos_returns["M"])
    with pytest.raises(ValueError, match="not eligible"):
        compare_universes(prices, cfg, {"Typo": ["Z"]})


def test_relative_growth_interval_is_reproducible_and_brackets_the_estimate(prices):
    wf = walk_forward(prices, make_config())
    first = relative_growth_interval(wf.oos_returns, "Maximum Sharpe", EQUAL_WEIGHT, wf.nav.index[0],
                                     replications=300, seed=1)
    again = relative_growth_interval(wf.oos_returns, "Maximum Sharpe", EQUAL_WEIGHT, wf.nav.index[0],
                                     replications=300, seed=1)
    assert first == again
    assert first.lower <= first.observed <= first.upper
    cagr = wf.metrics["CAGR"]
    assert first.observed == pytest.approx((1 + cagr["Maximum Sharpe"]) / (1 + cagr[EQUAL_WEIGHT]) - 1)


# --- Financial metrics with independently verifiable values ---------------------------------------

def test_cagr_volatility_drawdown_on_hand_computed_case():
    dates = pd.to_datetime(["2015-01-01", "2016-01-01", "2017-01-01"])  # 365 + 366 days
    prices = pd.DataFrame({"X": [100., 50., 121.]}, index=dates)
    metrics = compute_asset_metrics(prices, trading_days=1)
    years = 731 / 365.25
    assert metrics.loc["X", "CAGR"] == pytest.approx(1.21 ** (1 / years) - 1)
    assert metrics.loc["X", "Max Drawdown"] == pytest.approx(-.5)
    assert metrics.loc["X", "Volatility annualized"] == pytest.approx(np.std([-.5, 1.42], ddof=1))


def test_oos_cagr_is_from_the_concatenated_series_not_the_mean_of_years(prices):
    wf = walk_forward(prices, make_config())
    nav = wf.nav["Maximum Sharpe"]
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    assert wf.metrics.loc["Maximum Sharpe", "CAGR"] == pytest.approx(nav.iloc[-1] ** (1 / years) - 1)
    assert (1 + wf.annual_returns()["Maximum Sharpe"]).prod() == pytest.approx(nav.iloc[-1] / nav.iloc[0], rel=1e-12)


def test_leverage_cost_accrues_on_calendar_days():
    dates = pd.to_datetime(["2015-01-02", "2015-01-05", "2015-01-06"])  # Friday -> Monday -> Tuesday
    nav = build_daily_leveraged_series(pd.Series([100., 101., 101.], index=dates, name="U"), 2., 100., .0365,
                                       calendar_days_per_year=365.)
    assert nav.iloc[1] == pytest.approx(100 * (1 + 2 * .01 - .0365 * 3 / 365))
    assert nav.iloc[2] == pytest.approx(nav.iloc[1] * (1 - .0365 / 365))
    free = build_daily_leveraged_series(pd.Series([100., 101., 101.], index=dates, name="U"), 2.)
    assert free.iloc[-1] == pytest.approx(102.)


# --- Experiment registry ----------------------------------------------------------------------

def test_registry_records_every_run_and_marks_reruns(prices, tmp_path):
    research = parse_research_config({"universe": {"Apple": "AAPL", "Gold": "GC=F"}}, tmp_path)
    wf = walk_forward(prices, make_config())
    registry = tmp_path / "registry.jsonl"
    first = record_experiment(wf, research, label="baseline", registry=registry, project_dir=tmp_path)
    second = record_experiment(wf, research, label="baseline", registry=registry, project_dir=tmp_path)
    assert second["rerun_of"] == first["id"] and first["rerun_of"] is None
    assert len(load_entries(registry)) == 2 and distinct_configurations(registry) == 1
    assert find_holdout_dates(registry.read_text(encoding="utf-8")) == []
    assert first["validation_years"] == list(range(2013, 2020))


# --- Phase 2: uncertainty diagnostics, registry semantics, single short rate -----------------------

def test_sensitivity_panel_reports_every_prespecified_block(prices):
    from portfolio_lab.robustness import SENSITIVITY_BLOCKS, relative_growth_panel
    wf = walk_forward(prices, make_config())
    panel = relative_growth_panel(wf, ["Maximum Sharpe"], [EQUAL_WEIGHT], replications=200, seed=0)
    assert len(panel) == len(SENSITIVITY_BLOCKS)
    assert panel["Observed"].nunique() == 1  # the point estimate never depends on the block rule
    assert list(panel["Expected block length"].iloc[1:]) == [21., 63.]
    assert (panel["Lower"] <= panel["Observed"]).all() and (panel["Observed"] <= panel["Upper"]).all()


def test_bootstrap_pairs_policy_and_reference_by_date(prices):
    wf = walk_forward(prices, make_config())
    # Identical series => every paired draw has zero difference; an unpaired scheme would not.
    same = wf.oos_returns.assign(Copy=wf.oos_returns[EQUAL_WEIGHT])
    g = relative_growth_interval(same, "Copy", EQUAL_WEIGHT, wf.nav.index[0], replications=100, block_length=5)
    assert g.lower == g.upper == g.observed == 0


def test_leave_one_year_out_matches_hand_computation(prices):
    from portfolio_lab.robustness import leave_one_year_out
    wf = walk_forward(prices, make_config())
    table = leave_one_year_out(wf, "Maximum Sharpe", EQUAL_WEIGHT).iloc[:, 0]
    cagr = wf.metrics["CAGR"]
    assert table["Toutes les années"] == pytest.approx((1 + cagr["Maximum Sharpe"]) / (1 + cagr[EQUAL_WEIGHT]) - 1)
    annual = wf.annual_returns()
    kept = annual.drop(2016)
    days = sum((f.test_end - (wf.folds[i - 1].test_end if i else f.rebalance_date)).days
               for i, f in enumerate(wf.folds) if f.test_year != 2016)
    ratio = (1 + kept["Maximum Sharpe"]).prod() / (1 + kept[EQUAL_WEIGHT]).prod()
    assert table["Sans 2016"] == pytest.approx(ratio ** (365.25 / days) - 1)


def test_registry_distinguishes_reruns_from_code_changes_and_requires_hypotheses(prices, tmp_path, monkeypatch):
    import portfolio_lab.experiments as experiments
    research = parse_research_config({"universe": {"Apple": "AAPL", "Gold": "GC=F"}}, tmp_path)
    wf = walk_forward(prices, make_config())
    registry = tmp_path / "registry.jsonl"
    with pytest.raises(ValueError, match="hypothesis"):
        record_experiment(wf, research, label="x", registry=registry, category="pre-registered")
    with pytest.raises(ValueError, match="category"):
        record_experiment(wf, research, label="x", registry=registry, category="winner")
    monkeypatch.setattr(experiments, "code_version", lambda _: {"commit": "aaa", "dirty": False, "worktree_hash": "1"})
    first = record_experiment(wf, research, label="b", registry=registry, category="baseline")
    monkeypatch.setattr(experiments, "code_version", lambda _: {"commit": "aaa", "dirty": True, "worktree_hash": "2"})
    second = record_experiment(wf, research, label="b", registry=registry, category="baseline")
    third = record_experiment(wf, research, label="b", registry=registry, category="baseline")
    assert second["rerun_of"] is None and second["supersedes"] == first["id"]
    assert third["rerun_of"] == second["id"] and third["supersedes"] is None
    assert first["category"] == "baseline"


def test_rate_roles_are_distinct_and_validated():
    raw = {"universe": {"Apple": "AAPL", "Nasdaq 100": "QQQ"}, "leverage": {"Nasdaq 100": 2.0},
           "rates": {"risk_free": .01, "financing_base": .02, "financing_spread": .005},
           "leverage_costs": {"annual_fee": .006}}
    cfg = parse_research_config(raw).config
    assert cfg.risk_free_rate == .01 and cfg.leverage_financing_rate == pytest.approx(.025)
    series = parse_research_config({**raw, "rates": {"risk_free": "IR3TIB01EZM156N",
                                                     "financing_base": {"USD": "DTB3"}, "financing_spread": .004}}).config
    assert series.risk_free_series == "IR3TIB01EZM156N" and series.financing_series == (("USD", "DTB3"),)
    for bad in ({"estimation": {"risk_free_rate": 0.}}, {"leverage_costs": {"financing_rate": .01}},
                {"rates": {"short_rate": .01}}, {"rates": {"risk_free": "NOT_A_SERIES"}}):
        with pytest.raises(ValueError):
            parse_research_config({"universe": {"Apple": "AAPL"}, **bad})
    shared = load_research_config(ROOT).config
    assert shared.risk_free_series and dict(shared.financing_series)["USD"] == "DTB3"
