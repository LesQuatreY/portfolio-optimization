"""Phase 7B: MSCI Emerging Markets integration, weekly covariance, 7- vs 8-asset universes, caps."""
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import portfolio_lab.robustness as robustness
from portfolio_lab.assets import ASSET_CATALOGUE, Asset
from portfolio_lab.config import Config
from portfolio_lab.covariance import WEEKS_PER_YEAR, estimate_covariance_from_prices, weekly_returns
from portfolio_lab.data import parse_msci_symbol
from portfolio_lab.experiments import evaluation_fingerprint
from portfolio_lab.optimization import PortfolioOptimizer, select_frontier_assets
from portfolio_lab.research import load_research_config
from portfolio_lab.robustness import variant_config

ROOT = Path(__file__).resolve().parents[1]


def assets(*names):
    return tuple(Asset(n, n, "s", "EUR", "Gross Return", "x") for n in names)


# --- Weekly sampling -----------------------------------------------------------------------------

def test_weekly_returns_use_the_last_common_close_of_each_week_without_filling():
    dates = pd.to_datetime(["2015-01-05", "2015-01-08", "2015-01-09",          # week 1: Friday 9th present
                            "2015-01-12", "2015-01-15",                        # week 2: Friday holiday -> Thursday
                            "2015-01-26", "2015-01-30"])                       # week 3 missing entirely
    prices = pd.DataFrame({"X": [100., 101., 102., 103., 104., 110., 111.]}, index=dates)
    weekly = weekly_returns(prices)
    assert list(weekly.index) == list(pd.to_datetime(["2015-01-15", "2015-01-30"]))
    np.testing.assert_allclose(weekly["X"], [104 / 102 - 1, 111 / 104 - 1])   # week 3 carried by week 4


def test_weekly_covariance_is_annualized_on_the_same_scale_as_daily():
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2001-01-01", periods=2600)
    chol = np.linalg.cholesky(np.array([[1., .5], [.5, 1.]]) * 1e-4)
    returns = rng.standard_normal((2600, 2)) @ chol.T
    prices = pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=dates, columns=["A", "B"])
    daily = estimate_covariance_from_prices(prices, "sample", "daily").matrix.to_numpy()
    weekly = estimate_covariance_from_prices(prices, "sample", "weekly").matrix.to_numpy()
    np.testing.assert_allclose(np.diag(weekly), np.diag(daily), rtol=.15)      # same annual variance
    assert WEEKS_PER_YEAR == 52


def test_weekly_sampling_removes_the_asynchronous_close_bias():
    rng = np.random.default_rng(1)
    dates = pd.bdate_range("2001-01-01", periods=2600)
    shocks = rng.standard_normal(2600) * .01
    early = 100 * np.cumprod(1 + shocks)
    late = 100 * np.cumprod(1 + np.r_[0, shocks[:-1]])     # same market, recorded one session later
    prices = pd.DataFrame({"Early": early, "Late": late}, index=dates)

    def corr(m):
        m = m.to_numpy()
        return m[0, 1] / np.sqrt(m[0, 0] * m[1, 1])
    assert corr(estimate_covariance_from_prices(prices, "sample", "daily").matrix) < .1
    assert corr(estimate_covariance_from_prices(prices, "sample", "weekly").matrix) > .7


def test_optimizer_uses_the_weekly_risk_model_everywhere(prices_8):
    cfg = Config(assets=assets(*prices_8.columns), covariance_method="ledoit_wolf", covariance_frequency="weekly",
                 frontier_points=4, targets=(("Mid", .16),))
    optimizer = PortfolioOptimizer(prices_8, cfg)
    expected = estimate_covariance_from_prices(prices_8, "ledoit_wolf", "weekly").matrix
    pd.testing.assert_frame_equal(optimizer.covariance, expected)
    w = np.full(prices_8.shape[1], 1 / prices_8.shape[1])
    assert optimizer.variance(w) == pytest.approx(float(w @ expected.to_numpy() @ w))
    weights, metrics = robustness.fit_policies(prices_8, cfg, risk_profiles=True, risk_parity=True)
    vol = np.sqrt(weights["Mid"].to_numpy() @ expected.to_numpy() @ weights["Mid"].to_numpy())
    assert vol <= .16 + 1e-6 or bool(metrics.loc["Mid", "Ceiling not binding (Maximum CAGR)"])
    # Realized metrics stay daily.
    daily = optimizer.R @ w
    assert optimizer.metrics(w)["Volatility"] == pytest.approx(daily.std(ddof=1) * np.sqrt(252))


@pytest.fixture(scope="module")
def prices_8():
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2003-01-01", periods=1800)
    vols = np.array([.025, .015, .010, .011, .011, .010, .010, .014])
    common = rng.standard_normal(1800)
    loads = np.array([.8, .9, .95, .97, .95, 0., .6, .8])
    noise = rng.standard_normal((1800, 8))
    r = (common[:, None] * loads + noise * np.sqrt(1 - loads ** 2)) * vols + .0003
    names = ["Apple", "Nasdaq 100", "MSCI World", "S&P 500", "Dow Jones", "Gold", "Coca-Cola", "Emerging Markets"]
    return pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=dates, columns=names)


# --- Emerging Markets asset --------------------------------------------------------------------

def test_emerging_markets_maps_to_msci_891800_net_total_return():
    asset = ASSET_CATALOGUE["MSCI:891800:NETR"]
    assert asset.name == "Emerging Markets" and asset.provider == "msci" and asset.currency == "USD"
    assert asset.return_type == "Net Total Return"
    assert parse_msci_symbol(asset) == ("891800", "NETR")
    assert "891800" in asset.reference


def test_cached_emerging_markets_snapshot_is_index_891800_before_2020():
    manifests = [m for m in (ROOT / ".cache/market/msci").glob("*.json")
                 if json.loads(m.read_text())["parameters"].get("index_code") == "891800"
                 and json.loads(m.read_text())["parameters"].get("variant") == "NETR"]
    if not manifests:
        pytest.skip("No cached MSCI EM snapshot (offline environment).")
    for manifest in manifests:
        source = pd.read_csv(manifest.with_suffix(".source.csv"), dtype={"INDEX_CODE": str})
        assert set(source["INDEX_CODE"].astype(str)) == {"891800"}
        assert set(source["VARIANT"]) == {"NETR"} and set(source["CURRENCY"]) == {"USD"}
        assert pd.to_datetime(source["DATE"]).max() < pd.Timestamp("2020-01-01")


# --- Universes and investor constraints ---------------------------------------------------------

def test_shared_config_is_the_eight_asset_universe_with_confirmed_caps_and_weekly_risk():
    research = load_research_config(ROOT)
    cfg = research.config
    assert research.eligible == ["Apple", "Nasdaq 100", "MSCI World", "S&P 500", "Dow Jones", "Gold", "Coca-Cola",
                                 "Emerging Markets"]
    assert dict(cfg.max_weights) == {"Gold": .10, "Apple": .40, "Coca-Cola": .10}
    assert "Coca-Cola <= 10%" in research.constraint_provenance
    assert cfg.covariance_frequency == "weekly" and cfg.leverage == ()
    assert dict(cfg.holding_costs)["Emerging Markets"] == pytest.approx(.002)
    seven = variant_config(cfg, **{"excluded": research.variants()["Univers historique (7 actifs)"]["exclude"]})
    assert select_frontier_assets(seven) == ["Apple", "Nasdaq 100", "MSCI World", "S&P 500", "Dow Jones", "Gold",
                                             "Coca-Cola"]
    assert seven.max_weights == cfg.max_weights and seven.covariance_frequency == "weekly"


def test_every_policy_respects_the_three_caps(prices_8):
    caps = (("Apple", .40), ("Gold", .10), ("Coca-Cola", .10))
    cfg = Config(assets=assets(*prices_8.columns), max_weights=caps, covariance_frequency="weekly",
                 frontier_points=4, targets=(("Low", .12), ("High", .5)))
    weights, _ = robustness.fit_policies(prices_8, cfg, risk_profiles=True, risk_parity=True)
    weights["Constrained Equal Weight"] = robustness.constrained_equal_weights(list(prices_8.columns), cfg)
    for name, w in weights.items():
        assert w.sum() == pytest.approx(1) and (w >= -1e-12).all(), name
        for asset, cap in caps:
            assert w[asset] <= cap + 1e-9, (name, asset)


def test_covariance_frequency_added_later_keeps_old_fingerprints():
    old = {"config": {"assets": ["a"]}, "evaluated_universe": ["A"], "policies": ["P"], "benchmark": None,
           "walk_forward_used": {}}
    assert evaluation_fingerprint(old) == evaluation_fingerprint(
        {**old, "config": {"assets": ["a"], "covariance_frequency": "daily"}})
    assert evaluation_fingerprint(old) != evaluation_fingerprint(
        {**old, "config": {"assets": ["a"], "covariance_frequency": "weekly"}})
