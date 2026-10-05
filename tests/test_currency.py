import numpy as np
import pandas as pd
import pytest
from portfolio_lab.currency import to_eur


def test_quote_direction(dates):
    usd = pd.Series([100., 100., 120.], index=dates, name="A")
    fx = pd.Series([2., 1., 2.], index=dates)
    np.testing.assert_allclose(to_eur(usd, "USD", fx), [50, 100, 60])


def test_eur_identity(dates):
    values = pd.Series([100, 110, 90], index=dates)
    pd.testing.assert_series_equal(to_eur(values, "EUR"), values)


def test_missing_fx_is_not_filled(dates):
    values = pd.Series([100, 100, 100], index=dates)
    fx = pd.Series([2, 1], index=dates[[0, 2]])
    result = to_eur(values, "USD", fx)
    assert np.isnan(result.iloc[1])
    np.testing.assert_allclose(result.iloc[[0, 2]], [50, 100])


@pytest.mark.parametrize("rate", [0, -1, np.inf])
def test_bad_fx_rejected(rate, dates):
    with pytest.raises(ValueError):
        to_eur(pd.Series(100, index=dates), "USD", pd.Series(rate, index=dates))


def test_unsupported_currency(dates):
    with pytest.raises(ValueError):
        to_eur(pd.Series(100, index=dates), "GBP")
