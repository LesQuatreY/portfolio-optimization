from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.leverage import build_daily_leveraged_series, leveraged_name, add_leverage


@pytest.mark.parametrize("factor", [1.3, 1.5, 2., 3., 4.])
def test_daily_compounding(factor, dates):
    result = build_daily_leveraged_series(pd.Series([100, 110, 99], index=dates), factor)
    np.testing.assert_allclose(result, [100, 100 * (1 + .1 * factor), 100 * (1 + .1 * factor) * (1 - .1 * factor)])
    assert leveraged_name("Apple", factor) == f"Apple x{factor:g}"


@pytest.mark.parametrize("factor", [1.5, 2., 4.])
@pytest.mark.parametrize("extra_loss", [0., .1])
def test_wipeout_is_absorbing(factor, extra_loss):
    dates = pd.date_range("2020-01-01", periods=4)
    loss = min(1 / factor + extra_loss, .99)
    result = build_daily_leveraged_series(pd.Series([100, 100 * (1 - loss), 100, 200], index=dates), factor)
    np.testing.assert_allclose(result, [100, 0, 0, 0], atol=1e-12)


def test_no_lookahead_and_sampling(dates):
    prices = pd.Series([100, 110, 99], index=dates)
    full = build_daily_leveraged_series(prices, 1.5)
    np.testing.assert_allclose(full.iloc[:2], build_daily_leveraged_series(prices.iloc[:2], 1.5))
    np.testing.assert_allclose(full.iloc[[0, 2]], [100, 97.75])


def test_fx_gap_does_not_skip_native_reset(config):
    dates = pd.date_range("2020-01-01", periods=4)
    native = {"A": pd.Series([100., 110., 99., 100.], index=dates)}
    # Mid-session FX is absent; the leveraged native path must still compound it.
    fx = pd.Series([2., 1., 1.], index=dates[[0, 2, 3]])
    common = pd.DataFrame({"A": [50., 99., 100.], "B": [10., 10., 10.]}, index=dates[[0, 2, 3]])
    result, _ = add_leverage(common, native, fx, replace(config, leverage=(("A", 1.5),)))
    assert result.loc[dates[2], "A x1.5"] == pytest.approx(195.5)


@pytest.mark.parametrize("factor", [0, -2, np.nan, np.inf])
def test_invalid_factor(factor, dates):
    with pytest.raises(ValueError):
        build_daily_leveraged_series(pd.Series([100, 110, 99], index=dates), factor)


def test_overflow_guard(dates):
    with pytest.raises(ValueError, match="overflow"):
        build_daily_leveraged_series(pd.Series([1, 1e100, 1e200], index=dates), 1e100)
