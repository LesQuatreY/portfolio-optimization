"""Observed interval returns, including an absorbing zero synthetic NAV."""
import numpy as np
import pandas as pd
from .protocol import assert_dates_before_holdout


def validate_prices(prices: pd.DataFrame, *, allow_zero: bool = False, minimum: int = 3) -> None:
    if (len(prices) < minimum or not isinstance(prices.index, pd.DatetimeIndex)
            or not prices.index.is_unique or not prices.index.is_monotonic_increasing
            or not prices.columns.is_unique or prices.shape[1] == 0):
        raise ValueError("Prices need a unique sorted date index, unique assets and sufficient observations.")
    # Single choke point for every return, metric, optimizer, walk-forward and bootstrap input.
    assert_dates_before_holdout(prices.index, "Prices")
    array = prices.to_numpy(dtype=float)
    if (not np.isfinite(array).all() or (array < 0).any()
            or (not allow_zero and (array == 0).any()) or (array[0] <= 0).any()):
        raise ValueError("Prices must be finite, positive initially and nonnegative thereafter.")
    if ((prices.shift(1) == 0) & (prices != 0)).any().any():
        raise ValueError("A wiped-out NAV must remain zero.")


def simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """First observation has no return; zero/zero after wipeout is defined as 0%."""
    validate_prices(prices, allow_zero=True)
    return prices.pct_change(fill_method=None).mask(prices.shift(1).eq(0), 0.).iloc[1:]


def apply_holding_costs(prices: pd.DataFrame, costs, calendar_days_per_year: float = 365.25) -> pd.DataFrame:
    """Deduct annual holding costs (e.g. a tracker's TER) from index series, accrued on calendar days.

    P_net(t) = P(t) * prod_{s <= t} (1 - c * days(s-1, s) / calendar_days_per_year): each interval pays
    the cost of its own elapsed days, so returns stay point in time. Columns without a cost are unchanged.
    """
    validate_prices(prices, allow_zero=True)
    costs = dict(costs)
    unknown = [name for name in costs if name not in prices.columns]
    if unknown:
        raise ValueError(f"Holding costs for unknown series {unknown}.")
    days = prices.index.to_series().diff().dt.days.fillna(0).to_numpy(dtype=float)
    out = prices.copy()
    for name, cost in costs.items():
        if not 0 <= cost < 1:
            raise ValueError("Holding costs must be annual fractions in [0, 1).")
        out[name] = prices[name] * np.cumprod(1 - cost * days / calendar_days_per_year)
    return out
