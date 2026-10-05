import numpy as np
import pandas as pd
import pytest
from portfolio_lab.config import Asset, Config


@pytest.fixture
def dates():
    return pd.date_range("2020-01-01", periods=3)


@pytest.fixture
def config():
    return Config(assets=(Asset("A", "A", "equity", "USD", "Adjusted price", "reinvested"),
                          Asset("B", "B", "equity", "EUR", "Adjusted price", "reinvested")),
                  leverage=(), targets=(("Low", .01), ("Medium", .17), ("High", 1.)), frontier_points=9)


@pytest.fixture
def portfolio_prices():
    # Orthogonal zero-mean shocks, variance ratio 4:1 => minimum weights 1:4.
    first = .02 * np.array([1, 1, -1, -1] * 16)
    second = .01 * np.array([1, -1, 1, -1] * 16)
    returns = np.column_stack([.001 + first, .0006 + second])
    return pd.DataFrame(np.vstack([np.ones(2), np.cumprod(1 + returns, axis=0)]),
                        columns=["A", "B"], index=pd.date_range("2020-01-01", periods=65))
