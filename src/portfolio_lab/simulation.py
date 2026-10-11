"""Wealth simulation of target weights: one accounting convention for in-sample and walk-forward.

Distinction that matters here: the optimizer *estimates* target weights from daily return
observations; that says nothing about how often the investor trades. The implementation is a
separate, explicit choice:

* ``"annual"`` (research baseline): at the close of the last session of each calendar year the
  portfolio is traded to its targets; holdings are then fixed and weights drift with prices
  until the next year-end close (buy and hold within the year).
* ``"daily"`` (constant mix): weights are reset to target at every common observation. This is
  the portfolio whose growth the optimizer's Maximum CAGR / frontier objective measures. Its
  intra-year trading is not costed, so it is a model reference, not an investable result.

Costs: ``cost_rate`` per unit of traded notional, i.e. ``cost_rate * sum(|target - drifted|)``
of pre-trade wealth, charged at the rebalance close and booked in the first return after it
(the first allocation is bought from cash: traded notional 1). This is the first-order
approximation of a self-financing trade; the neglected term is O(cost_rate^2).

The portfolio is always fully invested in the listed assets: there is no cash position and
no interest on cash.
"""
import numpy as np
import pandas as pd

from .returns import simple_returns


def hold_returns(returns: pd.DataFrame, weights: pd.Series, rebalance: str) -> tuple[pd.Series, pd.Series]:
    """Gross portfolio returns over one holding period and the end-of-period (drifted) weights.

    `returns` start with the first interval after the trade; `weights` are the traded targets.
    """
    if rebalance not in ("annual", "daily"):
        raise ValueError(f"Unknown rebalancing convention '{rebalance}'.")
    w = weights.reindex(returns.columns).to_numpy(dtype=float)
    if not np.isfinite(w).all() or abs(w.sum() - 1) > 1e-8:
        raise ValueError("Target weights must be finite and sum to one.")
    if rebalance == "daily":
        return pd.Series(returns.to_numpy() @ w, index=returns.index), weights.reindex(returns.columns).copy()
    growth = (1 + returns).cumprod()
    value = growth.to_numpy() @ w
    if (value <= 0).any():
        # Total wipeout: absorbing zero wealth (only possible with a fully wiped-out holding).
        dead = np.argmax(value <= 0)
        value[dead:] = 0.
        gross = np.r_[value[0] - 1, np.divide(value[1:], value[:-1], out=np.zeros(len(value) - 1),
                                              where=value[:-1] > 0) - 1]
        gross[dead + 1:] = 0.
        return pd.Series(gross, index=returns.index), pd.Series(w, index=returns.columns)
    gross = np.r_[value[0] - 1, value[1:] / value[:-1] - 1]
    end = pd.Series(w * growth.iloc[-1].to_numpy() / value[-1], index=returns.columns)
    return pd.Series(gross, index=returns.index), end


def static_policy_returns(prices: pd.DataFrame, weights: pd.Series, *, rebalance: str = "annual",
                          cost_rate: float = 0.) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Net returns of constant targets implemented over `prices` (descriptive, in-sample).

    The initial purchase happens at the first close; with "annual" the targets are restored at
    each calendar year-end close. Returns (net returns, gross returns, traded one-way turnover
    per rebalance date). Under "daily" only the initial purchase is costed.
    """
    assets = list(weights.index)
    returns = simple_returns(prices[assets])
    held = pd.Series(0., index=assets)
    net, gross, trades = [], [], {}
    groups = [returns] if rebalance == "daily" else [g for _, g in returns.groupby(returns.index.year)]
    for position, period in enumerate(groups):
        trade_date = prices.index[0] if position == 0 else groups[position - 1].index[-1]
        traded = float((weights - held).abs().sum())
        cost = cost_rate * traded
        period_gross, held = hold_returns(period, weights, rebalance)
        period_net = period_gross.copy()
        period_net.iloc[0] = (1 + period_gross.iloc[0]) * (1 - cost) - 1
        net.append(period_net)
        gross.append(period_gross)
        trades[trade_date] = traded / 2
    return pd.concat(net), pd.concat(gross), pd.Series(trades, name="One-way turnover")


def implemented_metrics(prices: pd.DataFrame, weights: pd.DataFrame, config, *, rebalance: str = "annual",
                        cost_rate: float | None = None) -> pd.DataFrame:
    """Realized in-sample metrics of each portfolio (row of `weights`) under an explicit implementation.

    Defaults: the walk-forward's rebalancing convention and transaction cost, so in-sample and
    out-of-sample figures describe the same investment behaviour.
    """
    from .metrics import compute_asset_metrics
    cost_rate = config.walk_forward.transaction_cost_bps / 1e4 if cost_rate is None else cost_rate
    series = {}
    for name, row in weights.dropna(how="all").iterrows():
        net, _, _ = static_policy_returns(prices, row.dropna(), rebalance=rebalance, cost_rate=cost_rate)
        series[name] = net
    returns = pd.DataFrame(series)
    nav = pd.concat([pd.DataFrame(1., index=[prices.index[0]], columns=returns.columns), (1 + returns).cumprod()])
    metrics = compute_asset_metrics(nav, config.trading_days, config.risk_free_rate, config.calendar_days_per_year)
    return metrics.loc[returns.columns]
