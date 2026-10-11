"""Daily reset on all underlying sessions before portfolio-calendar sampling."""
import numpy as np
import pandas as pd
from .returns import validate_prices


def leveraged_name(underlying: str, leverage: float) -> str:
    return f"{underlying} x{leverage:g}"


def build_daily_leveraged_series(underlying_prices: pd.Series, leverage: float,
                               starting_nav: float = 100., annual_cost: float | pd.Series = 0.,
                               calendar_days_per_year: float = 365.25) -> pd.Series:
    """NAV(t) = NAV(t-1) * max(0, 1 + L * r(t) - cost(t-1) * days(t-1, t) / calendar_days_per_year).

    `annual_cost` (fees + financing of the borrowed exposure) accrues on calendar days, so a
    weekend or holiday interval pays for every elapsed day. It is a constant or a Series on the
    underlying's dates; the interval (t-1, t] pays the annual rate known at t-1 (point in time).
    It may be negative when financing rates are negative. 0 reproduces the cost-free model.
    """
    validate_prices(underlying_prices.to_frame(), minimum=1)
    if not np.isfinite(leverage) or leverage <= 0 or not np.isfinite(starting_nav) or starting_nav <= 0:
        raise ValueError("Leverage and initial NAV must be finite and positive.")
    if isinstance(annual_cost, pd.Series):
        cost = annual_cost.reindex(underlying_prices.index)
        if cost.isna().any():
            raise ValueError("Annual leverage cost series must cover every underlying session.")
        cost = cost.shift(1).to_numpy(dtype=float)
    else:
        cost = np.full(len(underlying_prices), float(annual_cost))
    if not np.isfinite(np.nan_to_num(cost)).all() or (np.abs(np.nan_to_num(cost)) >= 1).any():
        raise ValueError("Annual leverage cost must be a finite fraction with |cost| < 1.")
    elapsed = underlying_prices.index.to_series().diff().dt.days.to_numpy(dtype=float)
    drag = np.nan_to_num(cost * elapsed / calendar_days_per_year)
    growth = (1 + leverage * underlying_prices.pct_change(fill_method=None) - drag).clip(lower=0)
    growth.iloc[0] = 1.
    with np.errstate(over="ignore", invalid="ignore"):
        nav = starting_nav * growth.cumprod()
    nav = nav.mask(growth.eq(0).cummax(), 0.)
    if not np.isfinite(nav.to_numpy()).all():
        raise ValueError("Synthetic NAV overflowed; reduce leverage or duration.")
    return nav


def add_leverage(base_prices: pd.DataFrame, native: dict[str, pd.Series], fx: pd.Series | None, config,
                 rates=None):
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
        if rates is None:
            # Constant convention: leverage_financing_rate already includes any spread.
            annual_cost = config.leverage_annual_fee + (factor - 1) * config.leverage_financing_rate
        else:
            # Historical base rate of the product's own currency (point in time) + configured spread.
            base = rates.financing_on(metadata[name].currency, path.index)
            annual_cost = config.leverage_annual_fee + (factor - 1) * (base + config.leverage_financing_spread)
        nav_native = build_daily_leveraged_series(path, factor, config.initial_nav, annual_cost,
                                                  config.calendar_days_per_year)
        nav_eur = to_eur(nav_native, metadata[name].currency, fx)
        label = leveraged_name(name, factor)
        prices[label] = nav_eur.reindex(base_prices.index)
        # Rebase only for presentation; EUR ratios and returns are unchanged.
        prices[label] *= config.initial_nav / prices[label].iloc[0]
        zeros = nav_native.index[nav_native.eq(0)]
        diagnostics.append({"Asset": label, "Underlying": name, "Leverage": factor,
                            "Annual cost (fee + financing)": float(np.mean(annual_cost)),
                            "Reset sessions": len(path), "Worst underlying return": path.pct_change(fill_method=None).min(),
                            "Wipeout date": zeros[0] if len(zeros) else pd.NaT})
    validate_prices(prices, allow_zero=True)
    return prices, pd.DataFrame(diagnostics)
