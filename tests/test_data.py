from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.data import load_market_data, prepare_common_prices, validate_history, CSVProvider


class ToyProvider:
    name = "deterministic fixture"

    def history(self, asset, end):
        dates = pd.date_range("2020-01-01", periods=5)
        values = {"A": [100, 110, 120, 130, 140], "B": [50, np.nan, 55, 60, 65],
                  "EURUSD": [2, 2, 1, 1, 2]}
        return pd.Series(values[asset.name], index=dates, name=asset.name, dtype=float)


def test_schema_alignment_metadata_and_names(config):
    data = load_market_data(config, ToyProvider())
    assert list(data.common) == ["A", "B"]
    assert len(data.common) == 4
    np.testing.assert_allclose(data.common["A"], [50, 120, 130, 70])
    assert data.provenance.loc["B", "Raw missing observations"] == 1
    assert data.provenance.loc["A", "Raw observations"] == 5
    assert data.provenance.loc["A", "Final common observations"] == 4
    assert data.provenance.loc["A", "Raw start date"] == pd.Timestamp("2020-01-01")
    assert data.provenance.loc["B", "Raw end date"] == pd.Timestamp("2020-01-05")
    assert data.common.index.is_unique and data.common.index.is_monotonic_increasing


@pytest.mark.parametrize("kind", ["duplicate", "unsorted", "zero", "negative", "infinite", "empty", "wrongname"])
def test_invalid_history_rejected(kind, dates):
    series = pd.Series([100., 110., 120.], index=dates, name="A")
    if kind == "duplicate":
        series.index = [dates[0], dates[0], dates[2]]
    elif kind == "unsorted":
        series = series.iloc[::-1]
    elif kind == "empty":
        series = series.iloc[:0]
    elif kind == "wrongname":
        series.name = "B"
    else:
        series.iloc[1] = {"zero": 0, "negative": -1, "infinite": np.inf}[kind]
    with pytest.raises(ValueError):
        validate_history(series, "A")


def test_no_joint_observations_rejected(dates):
    with pytest.raises(ValueError):
        prepare_common_prices(pd.DataFrame({"A": [100, np.nan, 100], "B": [np.nan, 100, np.nan]}, index=dates))


def test_csv_provider_roundtrip(tmp_path, config):
    dates = pd.date_range("2020-01-01", periods=3)
    pd.DataFrame({"Date": dates, "Value": [100, 110, 120]}).to_csv(tmp_path / "A.csv", index=False)
    result = CSVProvider(tmp_path).history(config.assets[0], "2020-01-03")
    assert result.name == "A" and len(result) == 2


def test_provider_end_contract_enforced(config):
    with pytest.raises(ValueError, match="exclusive"):
        load_market_data(replace(config, end="2020-01-03"), ToyProvider())


@pytest.mark.parametrize("kwargs", [{"base_currency": "USD"}, {"frontier_points": 1}, {"trading_days": 0},
                                     {"risk_free_rate": np.nan}, {"leverage": (("A", -2),)},
                                     {"targets": (("Bad", -.1),)}])
def test_invalid_config(config, kwargs):
    with pytest.raises(ValueError):
        replace(config, **kwargs)
