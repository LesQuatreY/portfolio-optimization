"""Opportunity-set and exposure diagnostics (training data only; descriptive).

* How precisely are expected returns known? Annualized mean, its standard error under an i.i.d.
  approximation (trading_days * std / sqrt(n), i.e. annual volatility / sqrt(years)), and the same for the *difference* with a reference
  portfolio, which is what drives an optimizer's tilts.
* How much independent risk does the universe contain? Principal components of the correlation
  matrix and pairwise correlation ranges across estimation windows.
* Exposure, not instruments: the risk distance ``sqrt((w_a - w_b)' Sigma (w_a - w_b))`` is the annualized
  tracking volatility between two allocations. Swapping between highly correlated instruments moves
  weights a lot but risk distance little; a genuine change of exposure moves both. Measured return
  relationships only: no index constituent (look-through) data are used.
"""
import numpy as np
import pandas as pd

from .returns import simple_returns


def mean_uncertainty(prices: pd.DataFrame, reference: pd.Series | None = None, trading_days: int = 252
                     ) -> pd.DataFrame:
    """Annualized arithmetic means with i.i.d. standard errors, optionally relative to a reference portfolio."""
    returns = simple_returns(prices)
    n = len(returns)
    mean = returns.mean() * trading_days
    # SE of an annualized mean: trading_days * std_daily / sqrt(n) = annual volatility / sqrt(years).
    se = returns.std(ddof=1) * trading_days / np.sqrt(n)
    table = pd.DataFrame({"Mean": mean, "Standard error": se, "t-stat": mean / se})
    if reference is not None:
        ref = returns[reference.index] @ reference
        active = returns.sub(ref, axis=0)
        table["Mean vs reference"] = active.mean() * trading_days
        table["SE vs reference"] = active.std(ddof=1) * trading_days / np.sqrt(n)
        table["t-stat vs reference"] = table["Mean vs reference"] / table["SE vs reference"]
    return table.rename_axis("Asset")


def principal_components(prices: pd.DataFrame) -> pd.DataFrame:
    """Share of total variance explained by each principal component of the return correlation matrix."""
    corr = simple_returns(prices).corr().to_numpy()
    values, vectors = np.linalg.eigh(corr)
    order = np.argsort(values)[::-1]
    values, vectors = values[order], vectors[:, order]
    vectors = vectors * np.sign(vectors.sum(axis=0))  # deterministic sign: positive mean loading
    table = pd.DataFrame(vectors, index=prices.columns, columns=[f"PC{i + 1}" for i in range(len(values))])
    table.loc["Explained share"] = values / values.sum()
    return table


def correlation_ranges(windows: dict) -> pd.DataFrame:
    """Min / max / last pairwise correlation across a set of estimation windows {label: prices}."""
    mats = {label: simple_returns(p).corr() for label, p in windows.items()}
    stacked = pd.concat(mats, names=["Window"])
    assets = list(next(iter(mats.values())).columns)
    rows = []
    for i, a in enumerate(assets):
        for b in assets[i + 1:]:
            series = stacked.xs(a, level=1)[b]
            rows.append({"Pair": f"{a} / {b}", "Min": series.min(), "Max": series.max(), "Last": series.iloc[-1]})
    return pd.DataFrame(rows).set_index("Pair").sort_values("Min", ascending=False)


def risk_distance(a: pd.Series, b: pd.Series, sigma: pd.DataFrame) -> float:
    """Annualized tracking volatility between two allocations under the covariance `sigma`."""
    assets = list(sigma.index)
    d = a.reindex(assets, fill_value=0.).to_numpy() - b.reindex(assets, fill_value=0.).to_numpy()
    return float(np.sqrt(max(d @ sigma.to_numpy() @ d, 0.)))


def risk_contributions(weights: pd.Series, sigma: pd.DataFrame) -> pd.Series:
    """Share of portfolio variance contributed by each asset (sums to one)."""
    w = weights.reindex(sigma.index, fill_value=0.).to_numpy()
    marginal = sigma.to_numpy() @ w
    total = float(w @ marginal)
    return pd.Series(w * marginal / total, index=sigma.index, name="Risk contribution")


def exposure_changes(weights: pd.DataFrame, sigma: pd.DataFrame) -> pd.DataFrame:
    """Per consecutive fold: instrument distance 0.5 * sum|dw| next to risk distance sqrt(dw' Sigma dw)."""
    rows = []
    years = list(weights.index)
    for previous, year in zip(years, years[1:]):
        a, b = weights.loc[year], weights.loc[previous]
        rows.append({"Year": year, "Instrument distance": 0.5 * float((a - b).abs().sum()),
                     "Risk distance": risk_distance(a, b, sigma)})
    return pd.DataFrame(rows).set_index("Year")
