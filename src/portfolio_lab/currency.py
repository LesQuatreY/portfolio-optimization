"""Explicit quote direction and strictly observed FX normalization."""
import numpy as np
import pandas as pd


def to_eur(values: pd.Series, currency: str, eurusd: pd.Series | None = None) -> pd.Series:
    """EURUSD is USD per EUR: USD value / EURUSD. Never fill missing quotes."""
    if currency == "EUR":
        return values.copy()
    if currency != "USD" or eurusd is None:
        raise ValueError(f"Cannot convert {currency} without supported FX history.")
    rates = eurusd.reindex(values.index)
    observed = rates.dropna()
    if not np.isfinite(observed.to_numpy()).all() or (observed <= 0).any():
        raise ValueError("EURUSD quotes must be finite and strictly positive.")
    return (values / rates).rename(values.name)
