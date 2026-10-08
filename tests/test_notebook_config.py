"""Notebook universe changes propagate through the same effective configuration."""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.config import configure_universe, load_config
from portfolio_lab.assets import ASSET_CATALOGUE, Asset
from portfolio_lab.covariance import estimate_covariance
from portfolio_lab.data import YahooProvider, load_market_data, study_coverage
from portfolio_lab.leverage import add_leverage
from portfolio_lab.metrics import compute_asset_metrics
from portfolio_lab.optimization import optimize_frontier
from portfolio_lab.plotting import plot_frontier
from portfolio_lab.reporting import write_review_outputs


def test_notebook_defaults_match_package_and_can_be_overridden():
    path = Path(__file__).resolve().parents[1] / "notebooks/portfolio_analysis.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    cell = next(cell for cell in notebook["cells"] if cell.get("id") == "universe-config")
    namespace = dict(configure_universe=configure_universe, load_config=load_config, project_dir=Path("."),
                     replace=replace)
    exec("".join(cell["source"]), namespace)
    # The study end date is a notebook override; everything else must match the package defaults.
    if namespace["study_end"]:
        assert namespace["config"].end == namespace["study_end"]
    assert replace(namespace["config"], end=load_config().end) == load_config()
    assert namespace["config"].leverage == ()
    del namespace["assets"]["Dow Jones"]
    overridden = configure_universe(load_config(), namespace["assets"], namespace["leveraged_assets"])
    assert "Dow Jones" not in [asset.name for asset in overridden.assets]


def test_missing_leveraged_underlying_fails_before_download():
    assets = {asset.name: asset.symbol
              for asset in load_config().assets if asset.name != "Apple"}
    with pytest.raises(ValueError, match="Apple.*not in the configured asset universe"):
        configure_universe(load_config(), assets, {"Apple": 1.5})


DEFAULT_ASSETS = {asset.name: asset.symbol for asset in load_config().assets}
EXPLICIT = {"Apple": 1.5, "Nasdaq 100": 2.0}


def test_package_default_has_no_leverage():
    assert load_config().leverage == ()


@pytest.mark.parametrize("leveraged_assets", [None, {}, {"Apple": 1.0, "Nasdaq 100": 1}])
def test_none_empty_or_unit_leverage_clears_previous_leverage(leveraged_assets):
    leveraged = configure_universe(load_config(), DEFAULT_ASSETS, EXPLICIT)
    assert leveraged.leverage == (("Apple", 1.5), ("Nasdaq 100", 2.0))
    cleared = configure_universe(leveraged, DEFAULT_ASSETS, leveraged_assets)
    assert cleared.leverage == ()
    assert cleared == load_config()


def test_explicit_leverage_is_applied():
    cfg = configure_universe(load_config(), DEFAULT_ASSETS, EXPLICIT)
    assert cfg.leverage == (("Apple", 1.5), ("Nasdaq 100", 2.0))


@pytest.mark.parametrize("factor", [.5, 0, -1])
def test_sub_unit_leverage_rejected(factor):
    with pytest.raises(ValueError, match="above 1"):
        configure_universe(load_config(), DEFAULT_ASSETS, {"Apple": factor})


@pytest.mark.parametrize("leveraged_assets,labels", [
    (None, ["Apple", "Nasdaq 100"]), ({}, ["Apple", "Nasdaq 100"]),
    (EXPLICIT, ["Apple x1.5", "Nasdaq 100 x2"]),
])
def test_leverage_drives_returns_labels_and_optimizer_inputs(config, portfolio_prices, leveraged_assets, labels):
    catalogue = {
        "AAA": Asset("Apple", "AAA", "equity", "EUR", "Adjusted price", "reinvested"),
        "NNN": Asset("Nasdaq 100", "NNN", "equity", "EUR", "Adjusted price", "reinvested"),
    }
    cfg = configure_universe(config, {"Apple": "AAA", "Nasdaq 100": "NNN"}, leveraged_assets, catalogue=catalogue)
    common = portfolio_prices.set_axis(["Apple", "Nasdaq 100"], axis=1)
    native = {name: common[name] for name in common}
    prices, diagnostics = add_leverage(common, native, None, cfg)
    result = optimize_frontier(prices, cfg)
    assert list(result.weights) == labels
    assert list(result.covariance) == labels
    stats = compute_asset_metrics(prices)
    if cfg.leverage:
        assert list(diagnostics["Asset"]) == labels
        # Daily-reset returns are the underlying's returns times the factor.
        for (name, factor), label in zip(cfg.leverage, labels):
            np.testing.assert_allclose(prices[label].pct_change().dropna(),
                                       factor * common[name].pct_change().dropna())
    else:
        assert diagnostics.empty
        # Optimizer inputs are exactly the native series, not relabelled synthetic paths.
        pd.testing.assert_frame_equal(prices, common)
        native_estimate = estimate_covariance(common.pct_change().dropna(), cfg.covariance_method, cfg.trading_days)
        pd.testing.assert_frame_equal(result.covariance, native_estimate.matrix)
        assert not any(" x" in label for label in list(stats.index) + list(result.summary.index))


def test_unknown_symbol_is_informative(config):
    with pytest.raises(ValueError, match="Unknown asset symbol 'NEW'.*assets.py"):
        configure_universe(config, {"New": "NEW"})


@pytest.mark.parametrize("symbol,currency,return_type", [
    ("AAPL", "USD", "Adjusted price"), ("QQQ", "USD", "Adjusted price"),
    ("^SP500TR", "USD", "Gross Return"), ("DIA", "USD", "Adjusted price"),
    ("PX1GR.PA", "EUR", "Gross Return"), ("GC=F", "USD", "Price Return"),
    ("IWDA.AS", "EUR", "Adjusted price"), ("MSCI:990100:NETR", "USD", "Net Total Return"),
])
def test_catalogue_recovers_financial_metadata(symbol, currency, return_type):
    cfg = configure_universe(load_config(), {"My exposure": symbol}, {})
    assert cfg.assets == (replace(ASSET_CATALOGUE[symbol], name="My exposure"),)
    assert cfg.assets[0].currency == currency
    assert cfg.assets[0].return_type == return_type


def test_add_registered_asset_preserves_existing_metadata():
    original = load_config()
    assets = {asset.name: asset.symbol for asset in original.assets}
    assets["iShares Core MSCI World"] = "IWDA.AS"
    cfg = configure_universe(original, assets)
    assert cfg.assets[:-1] == original.assets
    assert cfg.assets[-1] == ASSET_CATALOGUE["IWDA.AS"]
    assert cfg.leverage == original.leverage


@pytest.mark.parametrize("assets", [{"New": {"symbol": "AAPL"}}, {"": "AAPL"}, {"New": ""}])
def test_invalid_simple_mapping_fails_explicitly(assets):
    with pytest.raises(ValueError, match="nonempty display names to symbol strings"):
        configure_universe(load_config(), assets, {})


def test_identical_effective_universe_preserves_optimization(config, portfolio_prices):
    catalogue = {asset.symbol: asset for asset in config.assets}
    resolved = configure_universe(config, {asset.name: asset.symbol for asset in config.assets},
                                  {}, catalogue=catalogue)
    assert resolved == config
    before = optimize_frontier(portfolio_prices, config)
    after = optimize_frontier(portfolio_prices, resolved)
    pd.testing.assert_frame_equal(before.covariance, after.covariance, check_exact=True)
    pd.testing.assert_frame_equal(before.weights, after.weights, check_exact=True)
    pd.testing.assert_frame_equal(before.frontier, after.frontier, check_exact=True)


def test_universe_propagates_to_data_fx_leverage_optimization_and_report(config, portfolio_prices, tmp_path):
    import matplotlib.pyplot as plt
    dates = portfolio_prices.index
    calls = []

    class Provider:
        name = "independent deterministic data"

        def history(self, asset, end):
            calls.append(asset.symbol)
            paths = {"REPLACED": portfolio_prices["A"] * 100, "NEW": portfolio_prices["B"] * 50,
                     "DEXUSEU": pd.Series(2., index=dates)}
            return paths[asset.symbol].rename(asset.name)

    catalogue = {
        "REPLACED": Asset("Replacement", "REPLACED", "replacement equity", "USD", "Adjusted price", "reinvested"),
        "NEW": Asset("New", "NEW", "new EUR index", "EUR", "Gross Return", "gross dividends reinvested"),
    }
    cfg = configure_universe(replace(config, output_dir=tmp_path),
                             {"A": "REPLACED", "New": "NEW"}, {"A": 1.5}, catalogue=catalogue)
    data = load_market_data(cfg, Provider())
    assert calls == ["REPLACED", "NEW", "DEXUSEU"]
    assert list(data.common) == ["A", "New"]
    np.testing.assert_allclose(data.common["A"], portfolio_prices["A"] * 50)
    assert data.provenance.loc["A", "Symbol"] == "REPLACED"
    assert data.provenance.loc["New", "FX series used"] == "None"
    prices, diagnostics = add_leverage(data.common, data.native, data.fx, cfg)
    assert list(prices) == ["A", "New", "A x1.5"]
    stats = compute_asset_metrics(prices)
    assert set(stats.index) == set(prices.columns)
    result = optimize_frontier(prices, cfg)
    assert list(result.covariance) == list(result.weights) == ["A x1.5", "New"]
    assert set(dict(cfg.targets)).issubset(result.portfolios)
    figure = plot_frontier(stats, result)
    labels = [text.get_text() for text in figure.axes[0].texts]
    assert set(labels) == {"A", "New", "A x1.5"}
    plt.close(figure)
    write_review_outputs(data, prices, stats, diagnostics, result, cfg)
    exported = pd.read_csv(tmp_path / "provenance.csv", index_col=0)
    assert list(exported.index) == ["A", "New", "A x1.5"]
    assert "Dow Jones" not in (tmp_path / "review.md").read_text(encoding="utf-8")


def test_cac_index_is_not_dividend_adjusted(monkeypatch, tmp_path):
    import yfinance as yf
    requested = {}

    class Ticker:
        def __init__(self, symbol):
            assert symbol == "PX1GR.PA"

        def history(self, **kwargs):
            requested.update(kwargs)
            return pd.DataFrame({"Close": [1000., 984.640015, 1021.590027]},
                                index=pd.date_range("1987-12-31", periods=3, tz="Europe/Paris"))

        def get_history_metadata(self):
            return {"currency": "EUR"}

    monkeypatch.setattr(yf, "Ticker", Ticker)
    monkeypatch.setattr(yf, "set_tz_cache_location", lambda path: None)
    asset = ASSET_CATALOGUE["PX1GR.PA"]
    assert asset.symbol == "PX1GR.PA" and asset.return_type == "Gross Return"
    provider = YahooProvider(tmp_path)
    result = provider.history(asset, "2026-10-05")
    assert requested["auto_adjust"] is False
    assert result.iloc[0] == 1000
    # A reload must use the same unadjusted, integrity-checked snapshot.
    pd.testing.assert_series_equal(provider.history(asset, "2026-10-05"), result, check_freq=False)


def test_coverage_identifies_fx_as_start_limit(config):
    dates = pd.date_range("2020-01-01", periods=5)

    class Provider:
        name = "fixture"

        def history(self, asset, end):
            index = dates[2:] if asset.name == "EURUSD" else dates
            return pd.Series(2. if asset.name == "EURUSD" else 100., index=index, name=asset.name)

    coverage = study_coverage(load_market_data(config, Provider()), config)
    assert coverage["common_start"] == "2020-01-03"
    assert coverage["start_limiting_series"] == ["DEXUSEU"]
    assert coverage["eur_start_limiting_assets"] == ["A"]


def test_missing_tail_does_not_extend_common_period(config):
    dates = pd.date_range("2020-01-01", periods=6)

    class Provider:
        name = "fixture"

        def history(self, asset, end):
            values = [100., 101., 102., np.nan, np.nan, np.nan] if asset.name == "B" else [100.] * 6
            return pd.Series(values, index=dates, name=asset.name)

    data = load_market_data(config, Provider())
    assert data.provenance.loc["B", "Raw observations"] == 3
    assert data.provenance.loc["B", "Raw missing observations"] == 3
    assert data.common.index[-1] == dates[2]
    assert study_coverage(data, config)["raw_end_limiting_assets"] == ["B"]
