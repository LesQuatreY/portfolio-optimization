import numpy as np
import pandas as pd
import pytest
from portfolio_lab.returns import simple_returns


def test_simple_returns_and_first_observation(dates):
    result = simple_returns(pd.DataFrame({"A": [100, 110, 99]}, index=dates))
    np.testing.assert_allclose(result["A"], [.1, -.1])
    assert result.index.equals(dates[1:])


def test_no_forward_filling(dates):
    with pytest.raises(ValueError):
        simple_returns(pd.DataFrame({"A": [100, np.nan, 99]}, index=dates))


def test_wipeout_returns(dates):
    np.testing.assert_allclose(simple_returns(pd.DataFrame({"A": [100, 0, 0]}, index=dates))["A"], [-1, 0])


def test_recovery_from_zero_rejected(dates):
    with pytest.raises(ValueError):
        simple_returns(pd.DataFrame({"A": [100, 0, 10]}, index=dates))
