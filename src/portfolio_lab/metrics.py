"""Preserved calendar CAGR and sample-volatility metric definitions."""
import numpy as np
import pandas as pd
from .returns import simple_returns


def compute_asset_metrics(prices: pd.DataFrame, trading_days: int = 252,
                          risk_free_rate: float = 0., calendar_days_per_year: float = 365.25) -> pd.DataFrame:
    returns = simple_returns(prices)
    years = (prices.index[-1] - prices.index[0]).days / calendar_days_per_year
    if (not np.isfinite(calendar_days_per_year) or calendar_days_per_year <= 0 or years <= 0
            or trading_days <= 0 or not np.isfinite(risk_free_rate)):
        raise ValueError("Invalid elapsed period, annualization or risk-free rate.")
    cagr = (prices.iloc[-1] / prices.iloc[0]) ** (1 / years) - 1
    mean = returns.mean() * trading_days
    volatility = returns.std(ddof=1) * np.sqrt(trading_days)
    drawdown = (prices / prices.cummax() - 1).min()
    return pd.DataFrame({
        "CAGR": cagr, "Mean return annualized": mean,
        "Volatility annualized": volatility, "Max Drawdown": drawdown,
        "Sharpe": (mean - risk_free_rate) / volatility.replace(0, np.nan),
        "Calmar": cagr / drawdown.abs().replace(0, np.nan),
    }).rename_axis("Asset").sort_values("Calmar", ascending=False)
