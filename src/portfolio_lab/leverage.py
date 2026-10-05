"""Daily reset on all underlying sessions before portfolio-calendar sampling."""
import numpy as np
import pandas as pd
from .returns import validate_prices


def leveraged_name(underlying: str, leverage: float) -> str:
    return f"{underlying} x{leverage:g}"


def build_daily_leveraged_series(underlying_prices: pd.Series, leverage: float,
                               starting_nav: float = 100.) -> pd.Series:
    validate_prices(underlying_prices.to_frame(), minimum=1)
    if not np.isfinite(leverage) or leverage <= 0 or not np.isfinite(starting_nav) or starting_nav <= 0:
        raise ValueError("Leverage and initial NAV must be finite and positive.")
    growth = (1 + leverage * underlying_prices.pct_change(fill_method=None)).clip(lower=0)
    growth.iloc[0] = 1.
    with np.errstate(over="ignore", invalid="ignore"):
        nav = starting_nav * growth.cumprod()
    nav = nav.mask(growth.eq(0).cummax(), 0.)
    if not np.isfinite(nav.to_numpy()).all():
        raise ValueError("Synthetic NAV overflowed; reduce leverage or duration.")
    return nav


def add_leverage(base_prices: pd.DataFrame, native: dict[str, pd.Series], fx: pd.Series | None, config):
    """Reset in the exposure's native currency, then translate NAV into EUR.

    FX is unlevered: this represents a USD daily-reset product held by an EUR
    investor. Missing FX dates must not remove underlying reset sessions.
    """
    from .currency import to_eur
    prices = base_prices.copy()
    diagnostics = []
    metadata = {a.name: a for a in config.assets}
    for name, factor in config.leverage:
        path = native[name].loc[base_prices.index[0]:base_prices.index[-1]].dropna()
        nav_native = build_daily_leveraged_series(path, factor, config.initial_nav)
        nav_eur = to_eur(nav_native, metadata[name].currency, fx)
        label = leveraged_name(name, factor)
        prices[label] = nav_eur.reindex(base_prices.index)
        # Rebase only for presentation; EUR ratios and returns are unchanged.
        prices[label] *= config.initial_nav / prices[label].iloc[0]
        zeros = nav_native.index[nav_native.eq(0)]
        diagnostics.append({"Asset": label, "Underlying": name, "Leverage": factor,
                            "Reset sessions": len(path), "Worst underlying return": path.pct_change(fill_method=None).min(),
                            "Wipeout date": zeros[0] if len(zeros) else pd.NaT})
    validate_prices(prices, allow_zero=True)
    return prices, pd.DataFrame(diagnostics)
