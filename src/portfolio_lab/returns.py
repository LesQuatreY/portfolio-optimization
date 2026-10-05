"""Observed interval returns, including an absorbing zero synthetic NAV."""
import numpy as np
import pandas as pd


def validate_prices(prices: pd.DataFrame, *, allow_zero: bool = False, minimum: int = 3) -> None:
    if (len(prices) < minimum or not isinstance(prices.index, pd.DatetimeIndex)
            or not prices.index.is_unique or not prices.index.is_monotonic_increasing
            or not prices.columns.is_unique or prices.shape[1] == 0):
        raise ValueError("Prices need a unique sorted date index, unique assets and sufficient observations.")
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
