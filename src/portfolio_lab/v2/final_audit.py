"""V2.2 Phase D: post-hoc exploratory audit of the six benchmark wealth paths (read-only).

Pure functions on a DataFrame of EUR wealth paths (columns = portfolios, index = common valuation
sessions) and the initial capital. Nothing here simulates, optimizes or rewrites a result; every
statistic is descriptive. Conventions (documented in docs/V2_2_PHASE_D_FINAL_AUDIT.md):

* returns: path returns, the first one measured against the initial capital (Research convention);
* weekly / monthly returns: compounded from the LAST valuation of each Friday-ending week / calendar
  month, the initial capital standing at the start; annualization sqrt(52) / sqrt(12);
* drawdowns: from the running peak including the initial capital, reported as positive losses;
* Sharpe / Sortino: daily excess over the Research EUR overnight rate (ACT/360), sqrt(252); the
  Sortino target is that same daily risk-free rate (downside deviation of excess returns);
* bootstrap: circular moving-block bootstrap of ALIGNED daily rows (all portfolios together).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics as M

PERIODS = {"Quotidien": (None, 252), "Hebdomadaire": ("W-FRI", 52), "Mensuel": ("ME", 12)}


def period_returns(paths: pd.DataFrame, initial: float, rule: str | None) -> pd.DataFrame:
    """Compounded returns between consecutive period-end valuations; initial capital first."""
    if rule is None:
        return paths.apply(lambda v: M.path_returns(v, initial))
    ends = paths.resample(rule).last().dropna(how="all")
    start = pd.DataFrame([[initial] * paths.shape[1]], columns=paths.columns, index=[paths.index[0] - pd.Timedelta(days=1)])
    return pd.concat([start, ends]).pct_change().iloc[1:]


def volatility_table(paths: pd.DataFrame, initial: float) -> pd.DataFrame:
    rows = {}
    for label, (rule, factor) in PERIODS.items():
        r = period_returns(paths, initial, rule)
        for name in paths:
            rows[(name, label)] = {"volatilité": float(r[name].std(ddof=1) * np.sqrt(factor)), "observations": len(r)}
    out = pd.DataFrame(rows).T
    out.index.names = ["Portefeuille", "Fréquence"]
    return out


def drawdown_profile(path: pd.Series, initial: float) -> dict:
    """Maximum drawdown with peak, trough, recovery and durations (positive loss convention)."""
    values = path.to_numpy(float)
    peaks = np.maximum.accumulate(np.r_[initial, values])[1:]
    dd = values / peaks - 1
    trough_pos = int(np.argmin(dd))
    peak_value = peaks[trough_pos]
    before = np.where(values[:trough_pos + 1] >= peak_value - 1e-9)[0]
    peak_date = path.index[before[-1]] if len(before) else None          # None: the initial capital
    after = np.where(values[trough_pos:] >= peak_value - 1e-9)[0]
    recovery = path.index[trough_pos + after[0]] if len(after) else None
    under = dd < -1e-12
    runs = (pd.Series(under) != pd.Series(under).shift()).cumsum()[under]
    return {"max_drawdown": float(-dd[trough_pos]),
            "peak_date": str(peak_date.date()) if peak_date is not None else "capital initial",
            "trough_date": str(path.index[trough_pos].date()),
            "recovery_date": str(recovery.date()) if recovery is not None else None,
            "peak_to_trough_sessions": trough_pos - (int(before[-1]) if len(before) else -1),
            "trough_to_recovery_sessions": int(after[0]) if len(after) else None,
            "peak_to_recovery_days": (recovery - (peak_date or path.index[0])).days if recovery is not None else None,
            "underwater_share": float(under.mean()),
            "longest_underwater_sessions": int(runs.value_counts().max()) if len(runs) else 0}


def window(path: pd.Series, initial: float, start, end) -> tuple[pd.Series, float]:
    """Sub-path and its base value (previous session, or the initial capital at the start)."""
    block = path.loc[start:end]
    pos = path.index.get_loc(block.index[0])
    return block, (initial if pos == 0 else float(path.iloc[pos - 1]))


def window_stats(path: pd.Series, initial: float, start, end) -> dict:
    block, base = window(path, initial, start, end)
    dd = drawdown_profile(block, base)
    return {"start": str(block.index[0].date()), "end": str(block.index[-1].date()), "sessions": len(block),
            "return": float(block.iloc[-1] / base - 1), "local_max_drawdown": dd["max_drawdown"],
            "local_peak": dd["peak_date"], "local_trough": dd["trough_date"], "local_recovery_in_window": dd["recovery_date"]}


def worst_rolling(paths: pd.DataFrame, initial: float, months: int) -> pd.Series:
    monthly = period_returns(paths, initial, "ME")
    return ((1 + monthly).rolling(months).apply(np.prod, raw=True) - 1).min()


def risk_table(paths: pd.DataFrame, initial: float, rate: pd.Series) -> pd.DataFrame:
    rf = M.daily_risk_free(paths.index, rate.reindex(paths.index))
    monthly = period_returns(paths, initial, "ME")
    rows = {}
    for name in paths:
        v = paths[name]
        r = M.path_returns(v, initial).to_numpy()
        excess = r - rf
        downside = np.sqrt(np.mean(np.minimum(excess, 0) ** 2)) * np.sqrt(252)
        cagr = M.cagr(float(v.iloc[-1]), initial, M.years(v.index))
        mdd = drawdown_profile(v, initial)["max_drawdown"]
        m = monthly[name]
        var = float(np.quantile(m, 0.05))
        rows[name] = {"CAGR": cagr, "Volatilité": float(r.std(ddof=1) * np.sqrt(252)), "MaxDD": mdd,
                      "Sharpe (EUR)": float(excess.mean() / excess.std(ddof=1) * np.sqrt(252)),
                      "Sortino (EUR)": float(excess.mean() * 252 / downside), "Écart baissier": float(downside),
                      "Calmar": cagr / mdd, "VaR 5 % mensuelle": -var, "ES 5 % mensuelle": float(-m[m <= var].mean()),
                      "Mois dans la queue": int((m <= var).sum()), "Valeur finale": float(v.iloc[-1])}
    return pd.DataFrame(rows).T


def correlations(paths: pd.DataFrame, initial: float) -> dict:
    return {label: period_returns(paths, initial, rule).corr() for label, (rule, _) in PERIODS.items()}


def beta(paths: pd.DataFrame, initial: float, target: str, reference: str, rule: str) -> float:
    r = period_returns(paths, initial, rule)
    return float(r[target].cov(r[reference]) / r[reference].var())


def block_bootstrap(paths: pd.DataFrame, initial: float, rate: pd.Series, block: int, reps: int = 2000,
                    seed: int = 20231229, focus: str = "BRK.B") -> dict:
    """Circular moving-block bootstrap of aligned daily rows: annualized volatility and EUR Sharpe
    intervals per portfolio and for differences focus − other. Descriptive, not a formal test."""
    rf = M.daily_risk_free(paths.index, rate.reindex(paths.index))
    r = paths.apply(lambda v: M.path_returns(v, initial)).to_numpy()
    x = r - rf[:, None]
    t, k = x.shape
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(t / block))
    vols, sharpes = np.empty((reps, k)), np.empty((reps, k))
    for i in range(reps):
        starts = rng.integers(0, t, n_blocks)
        idx = ((starts[:, None] + np.arange(block)[None, :]) % t).ravel()[:t]
        rr, xx = r[idx], x[idx]
        vols[i] = rr.std(axis=0, ddof=1) * np.sqrt(252)
        sharpes[i] = xx.mean(axis=0) / xx.std(axis=0, ddof=1) * np.sqrt(252)
    names = list(paths.columns)
    j = names.index(focus)
    q = lambda a: [float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))]
    out = {"block": block, "reps": reps, "seed": seed, "per_portfolio": {}, "differences": {}}
    for n, name in enumerate(names):
        out["per_portfolio"][name] = {"vol_ci95": q(vols[:, n]), "sharpe_ci95": q(sharpes[:, n])}
        if n != j:
            dv, ds = vols[:, j] - vols[:, n], sharpes[:, j] - sharpes[:, n]
            out["differences"][f"{focus} − {name}"] = {"vol_diff_ci95": q(dv), "share_vol_diff_positive": float((dv > 0).mean()),
                                                       "sharpe_diff_ci95": q(ds), "share_sharpe_diff_positive": float((ds > 0).mean())}
    return out
