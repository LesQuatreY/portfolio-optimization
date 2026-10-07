"""MSCI provider normalization and per-asset provider routing, fully offline."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.assets import ASSET_CATALOGUE
from portfolio_lab.config import configure_universe, load_config
from portfolio_lab.data import FREDProvider, MSCIProvider, load_market_data, normalize_msci_levels

MSCI_WORLD = ASSET_CATALOGUE["MSCI:990100:NETR"]


def msci_frame(dates, levels, **overrides):
    columns = {"INDEX_CODE": "990100", "VARIANT": "NETR", "RETURN_TYPE": "Net Total Return",
               "CURRENCY": "USD", "DATE": dates, "LEVEL": levels}
    return pd.DataFrame({**columns, **overrides})


def test_catalogue_resolves_msci_world():
    cfg = configure_universe(load_config(), {"MSCI World": "MSCI:990100:NETR"}, {})
    (asset,) = cfg.assets
    assert asset.provider == "msci"
    assert asset.currency == "USD"
    assert asset.return_type == "Net Total Return"
    assert ASSET_CATALOGUE["IWDA.AS"].provider == "yahoo"
    assert all(a.provider == "yahoo" for a in ASSET_CATALOGUE.values() if a is not MSCI_WORLD)


def test_normalization_parses_sorts_and_deduplicates():
    frame = msci_frame(["2001-01-02", "2000-12-29", "2001-01-02", "2001-01-03"],
                       ["101.5", 100, 101.5, 102.25])
    result = normalize_msci_levels(frame, MSCI_WORLD, "2026-10-07")
    assert result.name == "MSCI World"
    assert isinstance(result.index, pd.DatetimeIndex) and result.index.tz is None
    assert list(result.index) == list(pd.to_datetime(["2000-12-29", "2001-01-02", "2001-01-03"]))
    assert result.dtype == float
    np.testing.assert_array_equal(result, [100., 101.5, 102.25])
    # NETR levels are already total return: returns are plain level changes.
    np.testing.assert_allclose(result.pct_change().dropna(), [.015, 102.25 / 101.5 - 1])


def test_normalization_respects_exclusive_end():
    frame = msci_frame(["2026-10-05", "2026-10-06", "2026-10-07"], [1., 2., 3.])
    result = normalize_msci_levels(frame, MSCI_WORLD, "2026-10-07")
    assert result.index[-1] == pd.Timestamp("2026-10-06")


@pytest.mark.parametrize("frame", [None, msci_frame([], []),
                                   msci_frame(["2026-10-08"], [1.])])
def test_no_data_fails_loudly(frame):
    with pytest.raises(RuntimeError, match="No MSCI history.*no substitute"):
        normalize_msci_levels(frame, MSCI_WORLD, "2026-10-07")


@pytest.mark.parametrize("frame,match", [
    (msci_frame(["2001-01-02", "2001-01-03"], [100., "n/a"]), "non-numeric LEVEL"),
    (msci_frame(["2001-01-02", "2001-01-03"], [100., None]), "non-numeric LEVEL"),
    (msci_frame(["2001-01-02", "garbage"], [100., 101.]), "unparseable DATE"),
    (msci_frame(["2001-01-02", "2001-01-03"], [100., -1.]), "invalid observed values"),
    (msci_frame(["2001-01-02", "2001-01-02"], [100., 101.]), "conflicting levels"),
    (msci_frame(["2001-01-02"], [100.], CURRENCY="EUR"), "CURRENCY"),
    (msci_frame(["2001-01-02"], [100.], VARIANT="GRTR"), "VARIANT"),
    (msci_frame(["2001-01-02"], [100.]).drop(columns="LEVEL"), "lacks columns"),
])
def test_malformed_data_rejected(frame, match):
    with pytest.raises(ValueError, match=match):
        normalize_msci_levels(frame, MSCI_WORLD, "2026-10-07")


def test_symbol_and_return_type_must_agree():
    with pytest.raises(ValueError, match="variant NETR"):
        normalize_msci_levels(msci_frame(["2001-01-02"], [1.]),
                              replace(MSCI_WORLD, return_type="Price Return"), "2026-10-07")


def test_provider_requests_netr_with_inclusive_end_and_reuses_snapshot(tmp_path):
    calls = []

    def get_levels(code, start, end, variant):
        calls.append((code, start, end, variant))
        return msci_frame(["2000-12-29", "2001-01-02"], [3000., 3010.])

    provider = MSCIProvider(tmp_path, get_levels=get_levels)
    first = provider.history(MSCI_WORLD, "2026-10-07")
    assert calls == [("990100", "2000-01-01", "2026-10-06", "NETR")]
    assert first.first_valid_index() == pd.Timestamp("2000-12-29")
    second = provider.history(MSCI_WORLD, "2026-10-07")
    assert len(calls) == 1
    pd.testing.assert_series_equal(second, first, check_freq=False)


def test_mixed_providers_route_per_asset_and_msci_enters_fx_path(config, tmp_path):
    dates = pd.date_range("2020-01-01", periods=4)
    calls = []

    class Yahoo:
        name = "Yahoo Finance"
        values = {"AAPL": [10., 11., 12., 13.]}

        def history(self, asset, end):
            calls.append((self.name, asset.symbol))
            return pd.Series(self.values[asset.symbol], index=dates, name=asset.name)

    def get_levels(code, start, end, variant):
        calls.append(("MSCI", code, variant))
        return msci_frame(dates.strftime("%Y-%m-%d"), [100., 110., 120., 130.])

    def fetch_csv(series_id, last):
        calls.append(("FRED", series_id))
        return "observation_date,DEXUSEU\n" + "".join(
            f"{d:%Y-%m-%d},{v}\n" for d, v in zip(dates, [2., 2., 1., 1.]))

    msci = MSCIProvider(tmp_path / "msci", get_levels=get_levels)
    fred = FREDProvider(tmp_path / "fred", fetch_csv=fetch_csv)
    cfg = configure_universe(config, {"Apple": "AAPL", "MSCI World": "MSCI:990100:NETR"}, {})
    data = load_market_data(cfg, {"yahoo": Yahoo(), "msci": msci, "fred": fred})
    assert calls == [("Yahoo Finance", "AAPL"), ("MSCI", "990100", "NETR"), ("FRED", "DEXUSEU")]
    # Native USD levels are kept; EUR = USD / EURUSD through the shared FX path.
    np.testing.assert_array_equal(data.native["MSCI World"], [100., 110., 120., 130.])
    np.testing.assert_allclose(data.common["MSCI World"], [50., 55., 120., 130.])
    row = data.provenance.loc["MSCI World"]
    assert row["Provider"] == "MSCI" and row["Symbol"] == "MSCI:990100:NETR"
    assert row["Native currency"] == "USD" and row["FX series used"] == "DEXUSEU"
    assert row["FX provider"] == "FRED" and row["FX convention"] == "USD per EUR"
    assert row["Return type"] == "Net Total Return"
    assert "990100" in row["Source detail"] and "NETR" in row["Source detail"]
    assert data.provenance.loc["Apple", "Provider"] == "Yahoo Finance"
    assert data.provenance.loc["Apple", "Source detail"] == ""


def test_default_loading_routes_by_catalogue_without_notebook_provider_choice(config, monkeypatch, tmp_path):
    import portfolio_lab.data as data_module
    dates = pd.date_range("2020-01-01", periods=3)
    built, calls = [], []

    def fake(label):
        class Fake:
            name = label

            def __init__(self, cache_dir):
                built.append((label, cache_dir))

            def history(self, asset, end):
                calls.append((label, asset.symbol))
                return pd.Series(2. if asset.name == "EURUSD" else 100., index=dates, name=asset.name)
        return Fake

    monkeypatch.setattr(data_module, "YahooProvider", fake("yahoo"))
    monkeypatch.setattr(data_module, "MSCIProvider", fake("msci"))
    monkeypatch.setattr(data_module, "FREDProvider", fake("fred"))
    cfg = configure_universe(replace(config, cache_dir=tmp_path),
                             {"Apple": "AAPL", "MSCI World": "MSCI:990100:NETR", "Gold": "GC=F"}, {})
    load_market_data(cfg)
    assert built == [("yahoo", tmp_path), ("msci", tmp_path / "msci"), ("fred", tmp_path / "fred")]
    assert calls == [("yahoo", "AAPL"), ("msci", "MSCI:990100:NETR"), ("yahoo", "GC=F"), ("fred", "DEXUSEU")]


def test_missing_provider_for_asset_is_explicit(config):
    cfg = configure_universe(config, {"MSCI World": "MSCI:990100:NETR"}, {})
    with pytest.raises(ValueError, match="no data provider configured for 'msci'"):
        load_market_data(cfg, {"yahoo": object()})
