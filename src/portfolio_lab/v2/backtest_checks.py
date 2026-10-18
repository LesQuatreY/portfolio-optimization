"""Independent checks of a custom backtest (V2.2 Phase B), from the output ledgers and prices.

Nothing here calls the simulator's loop to check itself, except the two causality tests, which
compare runs on truncated or perturbed FUTURE prices. The reference wealth path is rebuilt in
closed form: between two rebalancing sessions r and t, a zero-cost fixed-weight basket is worth
V_r * sum_i w_i * P_i(t) / P_i(r). Metrics are recomputed with plain numpy formulas.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .admission import Check, within
from .custom import BacktestResult, PricePanel, simulate

YEAR_DAYS = 365.25


def rebalance_dates(index: pd.DatetimeIndex, mode: str) -> pd.DatetimeIndex:
    """First session of each month (monthly) / year (annual); only the first session for buy & hold."""
    if mode == "buy_hold":
        return index[:1]
    key = index.to_period("M") if mode == "monthly" else index.to_period("Y")
    return pd.DatetimeIndex(index.to_series().groupby(key).first().to_numpy())


def closed_form_nav(prices: pd.DataFrame, weights: dict, initial: float, mode: str) -> pd.Series:
    """Zero-cost fixed-target wealth path, independent of the simulator's ledger arithmetic."""
    dates = rebalance_dates(prices.index, mode)
    w = np.array([weights[c] for c in prices.columns])
    values, value = [], float(initial)
    anchors = prices.index.searchsorted(dates)
    for k, start in enumerate(anchors):
        last = k + 1 == len(anchors)
        stop = len(prices) - 1 if last else anchors[k + 1]   # next rebalance valued with OLD weights
        block = prices.iloc[start:stop + 1].to_numpy() / prices.iloc[start].to_numpy()
        path = value * block @ w
        values.extend(path if last else path[:-1])
        value = float(path[-1])
    return pd.Series(values, index=prices.index)


def independent_metrics(nav: pd.Series, initial: float, rate: pd.Series | None = None) -> dict:
    """CAGR, volatility, MaxDD and Sharpe from first principles (Research conventions)."""
    v = nav.to_numpy(float)
    returns = v / np.r_[initial, v[:-1]] - 1
    years = ((nav.index[-1] - nav.index[0]).days + 1) / YEAR_DAYS
    peaks = np.maximum.accumulate(np.r_[initial, v])[1:]
    out = {"cagr": (v[-1] / initial) ** (1 / years) - 1, "volatility": returns.std(ddof=1) * np.sqrt(252),
           "max_drawdown": -(v / peaks - 1).min(), "final": v[-1], "years": years}
    if rate is not None:
        days = np.r_[0, np.diff(nav.index.values).astype("timedelta64[D]").astype(float)]
        excess = returns - rate.reindex(nav.index).to_numpy() * days / 360
        out["sharpe_eur"] = excess.mean() / excess.std(ddof=1) * np.sqrt(252)
    excess0 = returns
    out["sharpe_0"] = excess0.mean() / excess0.std(ddof=1) * np.sqrt(252)
    return out


def ledger_checks(result: BacktestResult, panel: PricePanel, analytics_row: dict | None = None,
                  rate: pd.Series | None = None) -> tuple[list[Check], dict]:
    """Accounting identities on the ledger and an independent rebuild of wealth and metrics."""
    spec, book, held, prices, trades = result.spec, result.ledger, result.holdings, result.prices, result.trades
    rate_cost = spec.cost_bps / 10000
    expected = rebalance_dates(prices.index, spec.rebalance)
    weights_after = held.mul(prices).div(book["nav"], axis=0).loc[expected]
    target = pd.Series(dict(spec.weights))[weights_after.columns]
    first = trades[trades["Date"] == prices.index[0]]
    by_trade = trades.groupby("Date")["notional"].apply(lambda x: x.abs().sum()).reindex(book.index, fill_value=0.0)
    delta = held.diff().fillna(held.iloc[[0]]).mul(prices)
    recon = (held.mul(prices).sum(axis=1) + book["cash"] - book["nav"]).abs() / book["nav"]
    nav_ref = closed_form_nav(prices, dict(spec.weights), spec.initial_capital, spec.rebalance)
    checks = [
        Check("Calendrier : séances simulées = calendrier validé", float(len(prices)), f"= {len(panel.sessions)}",
              prices.index.equals(panel.sessions)),
        Check("Rééquilibrages exécutés = premières séances attendues", float(book["rebalance"].sum()),
              f"= {len(expected)}", book.index[book["rebalance"]].equals(expected)),
        within("Investissement initial : |Σ achats − capital| (€)", abs(float(first["notional"].sum()) - spec.initial_capital
               + float(book["cost"].iloc[0])), high=1e-6),
        within("Normalisation des poids cibles : |Σ w − 1|", abs(float(sum(spec.weights.values())) - 1), high=1e-12),
        within("Poids après rééquilibrage : écart max à la cible", float((weights_after - target).abs().max().max()), high=1e-10),
        within("Autofinancement : |liquidités| / valeur max", float((book["cash"].abs() / book["nav"]).max()), high=1e-9),
        within("Réconciliation positions × prix + liquidités = valeur (relatif)", float(recon.max()), high=1e-12),
        within("Notionnels des ordres = Δ positions × prix (€)", float((delta.abs().sum(axis=1) - by_trade).abs().max()), high=1e-6),
        within("Notionnel du registre = somme des ordres (€)", float((book["notional"] - by_trade).abs().max()), high=1e-6),
        within("Frais = taux × notionnel (€)", float((book["cost"] - rate_cost * book["notional"]).abs().max()), high=1e-6),
        within("Rotation = notionnel / valeur avant ordres", float((book["turnover"] - book["notional"] / book["pretrade_nav"]).abs().max()),
               high=1e-12),
    ]
    stats = {"rebalances": int(book["rebalance"].sum()), "orders": len(trades),
             "cumulative_costs_eur": float(book["cost"].sum()), "turnover_cumulative": float(book["turnover"].sum()),
             "turnover_excluding_initial": float(book["turnover"].iloc[1:].sum())}
    if spec.cost_bps == 0:
        gap = float((book["nav"] / nav_ref - 1).abs().max())
        checks.append(within("Valeur : moteur vs formule fermée indépendante (écart relatif max)", gap, high=1e-10))
        stats["closed_form_max_rel_gap"] = gap
    ref = independent_metrics(book["nav"], spec.initial_capital, rate)
    stats["independent_metrics"] = {k: float(v) for k, v in ref.items()}
    if analytics_row is not None:
        pairs = (("CAGR économique", "cagr"), ("Volatilité", "volatility"), ("MaxDD", "max_drawdown"),
                 ("Valeur finale économique (€)", "final"), ("Sharpe (taux 0 %)", "sharpe_0"))
        for label, key in pairs:
            checks.append(within(f"Indicateur « {label} » : module vs recalcul indépendant",
                                 abs(float(analytics_row[label]) - float(ref[key])), high=1e-9 * max(1, abs(ref[key]))))
    return checks, stats


def causality_checks(spec, panel: PricePanel, cut: str = "2019-06-28") -> list[Check]:
    """No dependence on future prices: (1) a run on prices truncated at ``cut`` reproduces the
    full run up to ``cut``; (2) multiplying every price after ``cut`` by random factors leaves
    the path up to ``cut`` unchanged."""
    full = simulate(spec, panel).ledger["nav"]
    cut = pd.Timestamp(cut)
    short_sessions = panel.sessions[panel.sessions <= cut]
    truncated = PricePanel(panel.prices.loc[:cut], panel.provenance, panel.synthetic, panel.currency, short_sessions)
    short = simulate(replace(spec, end=str(cut.date())), truncated).ledger["nav"]
    rng = np.random.default_rng(20231229)
    noisy = panel.prices.copy()
    later = noisy.index > cut
    noisy.loc[later] = noisy.loc[later].to_numpy() * rng.uniform(0.5, 1.5, size=noisy.loc[later].shape)
    perturbed = simulate(spec, PricePanel(noisy, panel.provenance, panel.synthetic, panel.currency, panel.sessions)).ledger["nav"]
    return [within(f"Causalité : run tronqué au {cut.date()} = run complet (écart relatif max)",
                   float((short / full.loc[:cut] - 1).abs().max()), high=0.0),
            within(f"Causalité : prix postérieurs au {cut.date()} perturbés, trajectoire antérieure inchangée",
                   float((perturbed.loc[:cut] / full.loc[:cut] - 1).abs().max()), high=0.0),
            Check("Causalité : la perturbation modifie bien la suite (témoin)",
                  float((perturbed.loc[cut:] / full.loc[cut:] - 1).abs().max()), "> 0",
                  bool((perturbed.loc[cut:] != full.loc[cut:]).any()))]
