"""Historical short rates, used point in time.

Two economically distinct uses, each with its own currency:

* the **risk-free reference** of Sharpe ratios and of the Maximum Sharpe objective: the investor's
  currency (EUR) cash rate;
* the **financing base** of synthetic leverage: the short rate of the leveraged product's own
  currency (a USD daily-reset product borrows USD), plus a configured spread.

Each role is either a constant (annual fraction) or a FRED series id. Series are converted from
percent to fractions and used only once published:

* daily series (e.g. DTB3): an observation dated t is usable from the next calendar day;
* monthly series (e.g. IR3TIB01EZM156N, a monthly average dated the first of its month): usable
  from the first day of the second following month (conservative publication lag).

Values are carried forward from the last published observation and never filled backwards: a date
before the first usable observation raises an error.
"""
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .protocol import assert_dates_before_holdout

# Known series and their observation frequency; another series must be registered here first.
RATE_SERIES = {
    "DTB3": ("daily", "US 3-month Treasury bill, secondary market (percent, discount basis)", "USD"),
    "IR3TIB01EZM156N": ("monthly", "Euro area 3-month interbank rate, monthly average (OECD MEI)", "EUR"),
}


def available_from(series: pd.Series, frequency: str) -> pd.Series:
    """Re-index observations by the first date on which each value could have been known."""
    if frequency == "daily":
        shifted = series.index + pd.Timedelta(days=1)
    elif frequency == "monthly":
        shifted = series.index.to_period("M").to_timestamp() + pd.DateOffset(months=2)
    else:
        raise ValueError(f"Unknown rate frequency '{frequency}'.")
    return pd.Series(series.to_numpy(dtype=float), index=pd.DatetimeIndex(shifted), name=series.name)


def point_in_time(series: pd.Series, index: pd.DatetimeIndex, frequency: str) -> pd.Series:
    """Annual rate (fraction) known on each date of `index`, from a percent series."""
    usable = available_from(series.dropna(), frequency)
    usable = usable[~usable.index.duplicated(keep="last")].sort_index()
    if not len(index) or usable.index[0] > index[0]:
        raise ValueError(f"{series.name}: no published rate before {index[0].date()}; history is never back-filled.")
    known = usable.reindex(usable.index.union(index)).ffill().reindex(index)
    return (known / 100.).rename(series.name)


@dataclass(frozen=True)
class RateSpec:
    """One rate role: a constant annual fraction or a FRED series id."""
    constant: float | None = None
    series: str | None = None

    def __post_init__(self):
        if (self.constant is None) == (self.series is None):
            raise ValueError("A rate is either a constant or a series id, not both.")
        if self.series is not None and self.series not in RATE_SERIES:
            raise ValueError(f"Unknown rate series '{self.series}'; register it in portfolio_lab.rates.RATE_SERIES.")
        if self.constant is not None and (not np.isfinite(self.constant) or abs(self.constant) >= 1):
            raise ValueError("Constant rates are annual fractions with |rate| < 1.")

    @classmethod
    def parse(cls, value) -> "RateSpec":
        if isinstance(value, str):
            return cls(series=value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Rate must be an annual fraction or a FRED series id; got {value!r}.")
        return cls(constant=float(value))

    def describe(self) -> str:
        if self.series is None:
            return f"constante {self.constant:.2%}"
        return f"{self.series} ({RATE_SERIES[self.series][1]})"


class Rates:
    """Point-in-time rates for one study: risk-free (investor currency) and financing per currency."""

    def __init__(self, risk_free: RateSpec, financing: Mapping[str, RateSpec], raw: Mapping[str, pd.Series]):
        self.risk_free, self.financing, self.raw = risk_free, dict(financing), dict(raw)

    def _daily(self, spec: RateSpec, index: pd.DatetimeIndex) -> pd.Series:
        assert_dates_before_holdout(index, "Rate request")
        if spec.series is None:
            return pd.Series(spec.constant, index=index)
        return point_in_time(self.raw[spec.series], index, RATE_SERIES[spec.series][0])

    def risk_free_on(self, index: pd.DatetimeIndex) -> pd.Series:
        return self._daily(self.risk_free, index).rename("Risk-free rate")

    def mean_risk_free(self, index: pd.DatetimeIndex) -> float:
        """Average annual risk-free rate over the dates of a window (Sharpe numerator convention)."""
        return float(self.risk_free_on(index).mean())

    def financing_on(self, currency: str, index: pd.DatetimeIndex) -> pd.Series:
        if currency not in self.financing:
            raise ValueError(f"No financing rate configured for currency {currency}.")
        return self._daily(self.financing[currency], index).rename(f"Financing base {currency}")


def load_rates(risk_free: RateSpec, financing: Mapping[str, RateSpec], end: str, provider=None) -> Rates:
    """Fetch every series the specs need (once each), strictly before the exclusive end."""
    needed = {spec.series for spec in [risk_free, *financing.values()] if spec.series is not None}
    raw = {}
    for series_id in sorted(needed):
        if provider is None:
            raise ValueError("A FRED provider is required for rate series.")
        raw[series_id] = provider.rate_history(series_id, end)
    return Rates(risk_free, financing, raw)


def constant_rates(risk_free: float = 0., financing: float = 0., currencies=("USD", "EUR")) -> Rates:
    return Rates(RateSpec(constant=risk_free), {c: RateSpec(constant=financing) for c in currencies}, {})
