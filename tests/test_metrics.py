import numpy as np
import pandas as pd
import pytest
from portfolio_lab.metrics import compute_asset_metrics


def test_independent_metric_values():
    # Exactly one calendar year, with returns +10%, -20%, +25% => terminal 110.
    dates = pd.to_datetime(["2021-01-01", "2021-04-01", "2021-08-01", "2022-01-01"])
    stats = compute_asset_metrics(pd.DataFrame({"A": [100, 110, 88, 110]}, index=dates), 252, .02, 365).loc["A"]
    arithmetic = .05 * 252
    sample_variance = ((.1 - .05)**2 + (-.2 - .05)**2 + (.25 - .05)**2) / 2
    vol = np.sqrt(sample_variance * 252)
    assert stats["CAGR"] == pytest.approx(.1)
    assert stats["Mean return annualized"] == pytest.approx(arithmetic)
    assert stats["Volatility annualized"] == pytest.approx(vol)
    assert stats["Max Drawdown"] == pytest.approx(-.2)
    assert stats["Sharpe"] == pytest.approx((arithmetic - .02) / vol)
    assert stats["Calmar"] == pytest.approx(.5)


def test_initial_nav_included_in_drawdown(dates):
    stats = compute_asset_metrics(pd.DataFrame({"A": [100, 80, 90]}, index=dates)).loc["A"]
    assert stats["Max Drawdown"] == pytest.approx(-.2)


def test_undefined_ratios(dates):
    stats = compute_asset_metrics(pd.DataFrame({"A": [100, 100, 100]}, index=dates)).loc["A"]
    assert np.isnan(stats["Sharpe"]) and np.isnan(stats["Calmar"])


def test_wipeout_metrics(dates):
    stats = compute_asset_metrics(pd.DataFrame({"A": [100, 0, 0]}, index=dates)).loc["A"]
    assert stats["CAGR"] == -1 and stats["Max Drawdown"] == -1
