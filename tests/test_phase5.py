"""Phase 5: unleveraged universe, Bayes-Stein drift, equal risk contribution, registry fingerprints."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import portfolio_lab.robustness as robustness
from portfolio_lab.assets import Asset
from portfolio_lab.config import Config, WalkForwardSettings
from portfolio_lab.experiments import (evaluation_fingerprint, load_entries, record_experiment, register_decision,
                                       strategy_fingerprints)
from portfolio_lab.optimization import PortfolioOptimizer
from portfolio_lab.research import load_research_config, parse_research_config

ROOT = Path(__file__).resolve().parents[1]


def assets(*names):
    return tuple(Asset(n, n, "s", "EUR", "Gross Return", "x") for n in names)


def prices_from(returns, start="2005-01-03"):
    dates = pd.bdate_range(start, periods=len(returns) + 1)
    return pd.DataFrame(100 * np.vstack([np.ones(returns.shape[1]), np.cumprod(1 + returns, axis=0)]),
                        index=dates, columns=[f"S{i}" for i in range(returns.shape[1])])


@pytest.fixture(scope="module")
def market():
    rng = np.random.default_rng(21)
    vols = np.array([.006, .012, .018, .010])
    returns = rng.standard_normal((1500, 4)) * vols + np.array([.0002, .0004, .0006, .0003])
    return prices_from(returns)


def cfg_for(prices, **kwargs):
    return Config(assets=assets(*prices.columns), covariance_method="sample", frontier_points=4,
                  targets=(("Low", .05), ("Mid", .12), ("High", .60)), **kwargs)


# --- Unleveraged main universe ------------------------------------------------------------------

def test_main_research_universe_has_no_leverage_but_keeps_nasdaq_and_caps():
    research = load_research_config(ROOT)
    cfg = research.config
    assert cfg.leverage == ()
    assert "Nasdaq 100" in research.eligible and "Apple" in research.eligible
    assert dict(cfg.max_weights) == {"Gold": .10, "Apple": .40}
    assert all(" x" not in name for name in robustness.select_frontier_assets(cfg))
    # Leverage support itself is preserved.
    levered = parse_research_config({"universe": {"Nasdaq 100": "QQQ"}, "leverage": {"Nasdaq 100": 2.0}}).config
    assert robustness.select_frontier_assets(levered) == ["Nasdaq 100 x2"]


# --- Equal risk contribution --------------------------------------------------------------------

def test_erc_equalizes_risk_contributions_without_binding_bounds(market):
    optimizer = PortfolioOptimizer(market, cfg_for(market))
    erc = optimizer.equal_risk_contribution()
    w = erc["weights"].to_numpy()
    sigma = optimizer.sigma
    contributions = w * (sigma @ w) / (w @ sigma @ w)
    np.testing.assert_allclose(contributions, .25, atol=1e-6)
    assert w.sum() == pytest.approx(1) and (w > 0).all() and erc["Bounds binding"] is False


def test_erc_matches_inverse_volatility_for_uncorrelated_assets():
    sigma = np.diag([.01, .04, .09])
    rng = np.random.default_rng(0)
    raw = rng.standard_normal((4000, 3))
    raw = (raw - raw.mean(0)) @ np.linalg.inv(np.linalg.cholesky(np.cov(raw, rowvar=False))).T
    returns = raw @ np.linalg.cholesky(sigma / 252).T
    prices = prices_from(returns, start="1995-01-02")
    optimizer = PortfolioOptimizer(prices, cfg_for(prices))
    w = optimizer.equal_risk_contribution()["weights"].to_numpy()
    inverse = 1 / np.sqrt(np.diag(optimizer.sigma))
    np.testing.assert_allclose(w, inverse / inverse.sum(), atol=1e-6)


def test_erc_respects_binding_caps_and_is_deterministic(market):
    cfg = cfg_for(market, max_weights=(("S0", .20),))
    first = PortfolioOptimizer(market, cfg).equal_risk_contribution()
    second = PortfolioOptimizer(market, cfg).equal_risk_contribution()
    pd.testing.assert_series_equal(first["weights"], second["weights"])
    assert first["Bounds binding"] is True
    assert first["weights"]["S0"] <= .20 + 1e-9 and first["weights"].sum() == pytest.approx(1)
    assert (first["weights"] >= -1e-12).all()


def test_erc_uses_no_expected_returns(market):
    shifted = market * np.exp(np.outer(np.arange(len(market)), [.001, 0, 0, -.001]))  # changes the means only
    a = PortfolioOptimizer(market, cfg_for(market)).equal_risk_contribution()["weights"]
    b = PortfolioOptimizer(shifted, cfg_for(market)).equal_risk_contribution()["weights"]
    np.testing.assert_allclose(a, b, atol=2e-3)  # covariance of simple returns barely changes


# --- Bayes-Stein drift ----------------------------------------------------------------------------

def test_estimated_drift_recentres_only_the_mean(market):
    cfg = cfg_for(market, expected_return_method="bayes_stein", growth_drift="estimated")
    optimizer = PortfolioOptimizer(market, cfg)
    np.testing.assert_allclose(optimizer.R_objective.mean(axis=0) * cfg.trading_days, optimizer.mu, rtol=1e-12)
    np.testing.assert_allclose(np.cov(optimizer.R_objective, rowvar=False), np.cov(optimizer.R, rowvar=False))
    # Realized metrics still use the actual returns.
    w = np.full(4, .25)
    assert optimizer.metrics(w)["CAGR"] == PortfolioOptimizer(market, cfg_for(market)).metrics(w)["CAGR"]
    reference = PortfolioOptimizer(market, cfg_for(market))
    assert (reference.R_objective is reference.R)


def test_shrunk_drift_moves_growth_weights_toward_the_minimum_variance_mean(market):
    sample = PortfolioOptimizer(market, cfg_for(market)).core_portfolios()["Maximum CAGR"]["weights"]
    shrunk = PortfolioOptimizer(market, cfg_for(market, expected_return_method="bayes_stein",
                                                 growth_drift="estimated")).core_portfolios()["Maximum CAGR"]["weights"]
    assert shrunk.max() <= sample.max() + 1e-9  # shrinkage cannot concentrate the growth optimum more


def test_invalid_growth_drift_rejected(market):
    with pytest.raises(ValueError):
        cfg_for(market, growth_drift="momentum")


# --- Infeasible and non-binding ceilings ----------------------------------------------------------

def test_profiles_report_infeasible_and_non_binding_ceilings(market):
    weights, metrics = robustness.fit_policies(market, cfg_for(market), risk_profiles=True, risk_parity=True)
    assert bool(metrics.loc["Low", "Fallback to Minimum Volatility"])            # 5% below minimum risk
    assert bool(metrics.loc["High", "Ceiling not binding (Maximum CAGR)"])       # 60% above max-growth risk
    assert not metrics.loc["Mid", ["Fallback to Minimum Volatility", "Ceiling not binding (Maximum CAGR)"]].any()
    assert (metrics["Feasible minimum volatility"] < metrics["Maximum-growth volatility"]).all()
    assert robustness.EQUAL_RISK in weights


def test_walk_forward_with_erc_keeps_accounting_and_bounds():
    dates = pd.bdate_range("2000-12-29", "2019-12-31")
    rng = np.random.default_rng(4)
    r = rng.normal([.0005, .0003, .0002, .0003], [.015, .010, .006, .009], (len(dates), 4))
    prices = pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=dates, columns=list("ABCM"))
    cfg = Config(assets=assets(*"ABCM"), eligible=("A", "B", "C"), benchmark="M", max_weights=(("A", .3),),
                 frontier_points=4, walk_forward=WalkForwardSettings(first_test_year=2017, last_test_year=2019,
                                                                     rebalance="annual", decision_lag_sessions=1,
                                                                     transaction_cost_bps=10))
    wf = robustness.walk_forward(prices, cfg, risk_parity=True)
    erc = wf.weights[robustness.EQUAL_RISK]
    assert (erc["A"] <= .3 + 1e-9).all() and np.allclose(erc.sum(axis=1), 1)
    assert robustness.EQUAL_RISK in wf.policies and wf.costs.loc[2017, robustness.EQUAL_RISK] == pytest.approx(.001)


# --- Registry fingerprints ------------------------------------------------------------------------

def _snapshot(config_extra=None, universe=("Apple", "Nasdaq 100"), policies=("Maximum Sharpe", "Equal Weight")):
    config = {"assets": ["a"], "eligible": ["Apple", "Nasdaq 100", "Gold"], "leverage": [["Nasdaq 100", 2.0]],
              "max_weights": [["Gold", .1], ["Apple", .4]], "holding_costs": [["MSCI World", .002], ["Gold", .0025]],
              "leverage_annual_fee": .006, "walk_forward": {"window": "rolling"}, **(config_extra or {})}
    return {"config": config, "evaluated_universe": list(universe), "policies": list(policies),
            "benchmark": "MSCI World", "walk_forward_used": {"window": "rolling"}}


def test_fingerprint_ignores_what_cannot_affect_the_evaluated_result():
    base = _snapshot()
    unlevered = _snapshot({"leverage": [], "eligible": ["Apple", "Nasdaq 100"], "leverage_annual_fee": 0.,
                           "max_weights": [["Apple", .4]], "holding_costs": [["MSCI World", .002]]})
    assert evaluation_fingerprint(base) == evaluation_fingerprint(unlevered)
    changed_cap = _snapshot({"max_weights": [["Apple", .3]]})
    assert evaluation_fingerprint(base) != evaluation_fingerprint(changed_cap)
    levered = _snapshot(universe=("Apple", "Nasdaq 100 x2"))
    cheaper = _snapshot({"leverage_annual_fee": .001}, universe=("Apple", "Nasdaq 100 x2"))
    assert evaluation_fingerprint(levered) != evaluation_fingerprint(cheaper)


def test_strategy_fingerprints_flag_only_new_strategies(tmp_path, monkeypatch):
    import portfolio_lab.experiments as experiments
    monkeypatch.setattr(experiments, "code_version", lambda _: {"commit": "c", "dirty": False, "worktree_hash": "h"})
    first, second = strategy_fingerprints(_snapshot()), strategy_fingerprints(
        _snapshot(policies=("Maximum Sharpe", "Equal Weight", "Equal Risk Contribution")))
    assert first["Maximum Sharpe"] == second["Maximum Sharpe"] and "Equal Risk Contribution" not in first
    registry = tmp_path / "experiments" / "registry.jsonl"
    decision = register_decision(registry, label="no leverage", rationale="investor", informed_by_validation=True)
    assert load_entries(registry)[0]["informed_by_validation"] is True and decision["kind"] == "decision"


def test_fields_added_later_do_not_make_old_evaluations_look_new():
    old = _snapshot()
    new = _snapshot({"growth_drift": "sample", "min_weights": [], "risk_free_series": None})
    assert evaluation_fingerprint(old) == evaluation_fingerprint(new)
    assert evaluation_fingerprint(old) != evaluation_fingerprint(_snapshot({"growth_drift": "estimated"}))


def test_exposure_history_recomputes_flags_in_log_order(tmp_path, monkeypatch):
    import json
    from portfolio_lab.experiments import exposure_history
    registry = tmp_path / "registry.jsonl"
    rows = [{"id": "1", "label": "a", "kind": "walk_forward", "snapshot": _snapshot()},
            {"id": "2", "label": "b", "kind": "walk_forward",
             "snapshot": _snapshot({"growth_drift": "sample"}, policies=("Maximum Sharpe", "Equal Weight", "ERC"))}]
    registry.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    history = exposure_history(registry)
    assert history["1|a"]["previously_evaluated"] is False
    assert history["2|b"]["new_strategies"] == ["ERC"]
