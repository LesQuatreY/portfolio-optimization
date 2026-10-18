"""Daily-path metrics with the exact Portfolio Research conventions (V11 ``run_v11.metrics``).

Conventions (reproduced, not re-invented):

* daily path = the simulator's ``total`` column: value after transaction costs and after the taxes
  actually paid along the way (CTO and Bitcoin, at each year end), WITHOUT any latent exit tax;
* path return of day 1 is measured against the initial capital (initial deployment costs included);
* years = (last date - first date + 1 day) / 365.25;
* arithmetic return = mean(daily) x 252; volatility = std(daily, ddof=1) x sqrt(252);
* Sharpe / Sortino use the daily excess over the EUR overnight rate (EONIA/€STR, ACT/360 over the
  calendar days since the previous session);
* drawdowns are measured from the running peak INCLUDING the initial capital;
* net CAGR is derived from the terminal wealth after the final sale and exit taxes.

Liquidation taxes are never applied to daily returns: they only enter terminal wealth.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
UNDERWATER_EPS = 1e-12


def years(index: pd.DatetimeIndex) -> float:
    return ((index[-1] - index[0]).days + 1) / 365.25


def path_returns(total: pd.Series, initial: float) -> pd.Series:
    return total / total.shift(1).fillna(initial) - 1


def wealth_from_returns(returns: pd.Series, initial: float) -> pd.Series:
    """Research's w3 path, rebuilt from returns (identical to ``total`` up to float rounding)."""
    return (1 + returns).cumprod() * initial


def cagr(terminal: float, initial: float, n_years: float) -> float:
    return (terminal / initial) ** (1 / n_years) - 1


def terminal_from_cagr(rate: float, initial: float, n_years: float) -> float:
    return initial * (1 + rate) ** n_years


def daily_risk_free(index: pd.DatetimeIndex, eur_rate: pd.Series) -> np.ndarray:
    days = pd.Series(index, index=index).diff().dt.days.fillna(0).to_numpy()
    return eur_rate.reindex(index).fillna(0.0).to_numpy() * days / 360.0


def drawdown(total: pd.Series, initial: float) -> pd.Series:
    """Daily drawdown (<= 0) from the running peak, the initial capital being the first peak."""
    values = total.to_numpy(float)
    peak = np.maximum.accumulate(np.r_[initial, values])[1:]
    return pd.Series(values / peak - 1, index=total.index)


def sessions_below_peak(total: pd.Series, initial: float) -> pd.Series:
    """Sessions elapsed since the last peak (0 on a new high): time spent below the previous peak."""
    under = (drawdown(total, initial) < -UNDERWATER_EPS).astype(int)
    return under.groupby((under != under.shift()).cumsum()).cumsum()


def path_metrics(total: pd.Series, initial: float, eur_rate: pd.Series) -> dict:
    """Research daily-path metrics of one portfolio (same formulas and float order as run_v11.metrics)."""
    ret = path_returns(total, initial)
    rf = daily_risk_free(total.index, eur_rate)
    ex = ret.to_numpy() - rf
    w3 = wealth_from_returns(ret, initial)
    roll = (w3 / w3.shift(TRADING_DAYS) - 1).dropna()
    dd = w3 / np.maximum.accumulate(np.r_[initial, w3.to_numpy()])[1:] - 1
    uw = (dd < -UNDERWATER_EPS).astype(int)
    runs = uw.groupby((uw != uw.shift()).cumsum()).cumsum()
    return {
        "arith_return": float(ret.mean() * TRADING_DAYS),
        "volatility": float(ret.std(ddof=1) * np.sqrt(TRADING_DAYS)),
        "sharpe": float(ex.mean() / ex.std(ddof=1) * np.sqrt(TRADING_DAYS)),
        "sortino": float(ex.mean() / np.sqrt(np.mean(np.minimum(ex, 0) ** 2)) * np.sqrt(TRADING_DAYS)),
        "max_drawdown": float(-dd.min()),
        "worst_12m": float(roll.min()) if len(roll) else np.nan,
        "longest_underwater_sessions": int(runs.max()),
        "underwater_share": float(uw.mean()),
        "cagr_path": cagr(float(total.iloc[-1]), initial, years(total.index)),
    }


def recovery(total: pd.Series, initial: float) -> dict:
    """Deepest drawdown episode: previous peak, trough and recovery (None when not recovered)."""
    values = total.to_numpy(float)
    peak_values = np.maximum.accumulate(np.r_[initial, values])
    dd = values / peak_values[1:] - 1
    trough = int(np.argmin(dd))
    peak_level = peak_values[trough + 1]
    before = np.flatnonzero(values[: trough + 1] >= peak_level - 1e-9)
    peak_date = total.index[before[-1]] if len(before) else None          # None: the initial capital
    after = np.flatnonzero(values[trough:] >= peak_level - 1e-9)
    rec = trough + int(after[0]) if len(after) else None
    return {
        "maxdd_peak_date": peak_date,
        "maxdd_trough_date": total.index[trough],
        "maxdd_recovery_date": None if rec is None else total.index[rec],
        "maxdd_recovery_sessions": None if rec is None else rec - trough,
        "maxdd_underwater_sessions": None if rec is None else rec - (before[-1] if len(before) else -1),
    }
