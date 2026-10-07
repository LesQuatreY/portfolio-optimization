"""FRED DEXUSEU FX provider: normalization, quote convention, caching and routing, fully offline."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.assets import Asset
from portfolio_lab.config import configure_universe
from portfolio_lab.data import FREDProvider, load_market_data, normalize_fred_series, study_coverage

FX = Asset("EURUSD", "DEXUSEU", "USD per EUR FX quote", "USD", "Price Return", "None", provider="fred")


def fred_frame(dates, values):
    return pd.DataFrame({"observation_date": dates, "DEXUSEU": values}, dtype=str)


def csv_text(rows):
    return "observation_date,DEXUSEU\n" + "".join(f"{d},{v}\n" for d, v in rows)


def test_normalization_parses_sorts_deduplicates_and_drops_holidays():
    frame = fred_frame(["1999-01-05", "1999-01-04", "1999-01-05", "1999-01-06", "1999-01-07"],
                       ["1.1760", "1.1812", "1.1760", "", "1.1636"])
    result = normalize_fred_series(frame, FX, "2026-10-07")
    assert result.name == "EURUSD" and result.dtype == float
    assert isinstance(result.index, pd.DatetimeIndex) and result.index.tz is None
    assert list(result.index) == list(pd.to_datetime(["1999-01-04", "1999-01-05", "1999-01-07"]))
    # USD per EUR exactly as published; never inverted.
    np.testing.assert_array_equal(result, [1.1812, 1.1760, 1.1636])
    assert not result.isna().any()


def test_normalization_respects_exclusive_end():
    frame = fred_frame(["2026-10-01", "2026-10-02", "2026-10-07"], ["1.12", "1.13", "1.14"])
    assert normalize_fred_series(frame, FX, "2026-10-07").index[-1] == pd.Timestamp("2026-10-02")


@pytest.mark.parametrize("frame", [None, fred_frame([], []), fred_frame(["1999-01-04"], [""]),
                                   fred_frame(["2026-10-08"], ["1.1"])])
def test_no_data_fails_loudly(frame):
    with pytest.raises(RuntimeError, match="No FRED history.*no substitute"):
        normalize_fred_series(frame, FX, "2026-10-07")


@pytest.mark.parametrize("frame,match", [
    (fred_frame(["1999-01-04", "1999-01-05"], ["1.18", "abc"]), "non-numeric"),
    (fred_frame(["1999-01-04", "garbage"], ["1.18", "1.17"]), "unparseable dates"),
    (fred_frame(["1999-01-04", "1999-01-04"], ["1.18", "1.17"]), "conflicting values"),
    (fred_frame(["1999-01-04"], ["-1.18"]), "invalid observed values"),
    (pd.DataFrame({"DATE": ["1999-01-04"], "DEXUSEU": ["1.18"]}), "lacks columns"),
])
def test_malformed_data_rejected(frame, match):
    with pytest.raises(ValueError, match=match):
        normalize_fred_series(frame, FX, "2026-10-07")


def test_provider_requests_inclusive_end_and_cached_reload_is_identical(tmp_path):
    calls = []
    # Values that the default fast CSV parser would not round-trip bit for bit.
    rows = [("1999-01-04", "1.1812"), ("1999-01-05", "1.17600000000000004"), ("1999-01-06", ""),
            ("1999-01-07", "1.1635999999999999")]

    def fetch_csv(series_id, last):
        calls.append((series_id, last))
        return csv_text(rows)

    fresh = FREDProvider(tmp_path, fetch_csv=fetch_csv).history(FX, "2026-10-07")
    assert calls == [("DEXUSEU", "2026-10-06")]
    cached = FREDProvider(tmp_path, fetch_csv=fetch_csv).history(FX, "2026-10-07")
    assert len(calls) == 1
    assert fresh.equals(cached)
    refreshed = FREDProvider(tmp_path, refresh=True, fetch_csv=fetch_csv).history(FX, "2026-10-07")
    assert refreshed.equals(cached) and len(calls) == 2


def test_invalid_series_id_rejected_before_any_request(tmp_path):
    provider = FREDProvider(tmp_path, fetch_csv=lambda *args: pytest.fail("no request expected"))
    with pytest.raises(ValueError, match="invalid FRED series id"):
        provider.history(replace(FX, symbol="DEXUSEU&x=1"), "2026-10-07")


def make_providers(tmp_path, asset_dates, asset_values, fx_rows, calls):
    class Yahoo:
        name = "Yahoo Finance"

        def history(self, asset, end):
            calls.append(("Yahoo Finance", asset.symbol))
            return pd.Series(asset_values, index=pd.DatetimeIndex(asset_dates), name=asset.name)

    def fetch_csv(series_id, last):
        calls.append(("FRED", series_id))
        return csv_text(fx_rows)

    return {"yahoo": Yahoo(), "fred": FREDProvider(tmp_path, fetch_csv=fetch_csv)}


def test_usd_to_eur_math_routing_and_provenance(config, tmp_path):
    calls = []
    dates = ["2020-01-02", "2020-01-03", "2020-01-06"]
    providers = make_providers(tmp_path, dates, [110., 220., 121.],
                               [(dates[0], "1.10"), (dates[1], "1.10"), (dates[2], "1.21")], calls)
    cfg = configure_universe(config, {"Apple": "AAPL"}, {},
                             catalogue={"AAPL": Asset("Apple", "AAPL", "equity", "USD", "Adjusted price", "x")})
    data = load_market_data(cfg, providers)
    # Assets stay on their own provider; only FX comes from FRED.
    assert calls == [("Yahoo Finance", "AAPL"), ("FRED", "DEXUSEU")]
    # USD 110 / 1.10 USD-per-EUR = EUR 100: DEXUSEU is used as published, not inverted.
    np.testing.assert_allclose(data.common["Apple"], [100., 200., 100.])
    np.testing.assert_allclose(data.fx, [1.10, 1.10, 1.21])
    row = data.provenance.loc["Apple"]
    assert row["Provider"] == "Yahoo Finance"
    assert (row["FX provider"], row["FX series used"], row["FX convention"]) == ("FRED", "DEXUSEU", "USD per EUR")
    assert row["FX start date"] == pd.Timestamp("2020-01-02")


def test_fred_history_from_1999_keeps_2000_usd_asset_from_its_start(config, tmp_path):
    calls = []
    fx_dates = pd.bdate_range("1999-01-04", "2001-01-31")
    asset_dates = pd.bdate_range("2000-12-29", "2001-01-31")
    providers = make_providers(tmp_path, asset_dates, np.linspace(100, 110, len(asset_dates)),
                               [(f"{d:%Y-%m-%d}", "0.95") for d in fx_dates], calls)
    cfg = configure_universe(config, {"World": "WLD"}, {},
                             catalogue={"WLD": Asset("World", "WLD", "index", "USD", "Net Total Return", "x")})
    data = load_market_data(cfg, providers)
    coverage = study_coverage(data, cfg)
    assert coverage["fx_start"] == "1999-01-04"
    assert coverage["common_start"] == "2000-12-29"
    assert coverage["start_limiting_series"] == ["World"]
