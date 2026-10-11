"""Allocation-stability diagnostics of walk-forward policies (descriptive, no composite score).

Two different quantities are kept apart:

* **target-weight change** ``D_t = 0.5 * sum_i |w_i,t - w_i,t-1|`` between consecutive *target*
  allocations: how much the model's answer moves from one fold to the next;
* **traded turnover**: what the investor actually trades at a rebalance, against holdings that have
  drifted during the year (``WalkForwardResult.trading``). A stable target can still require trading
  after a strong relative move, and a changing target can partly coincide with drift.

Counting conventions (fixed in docs/PHASE4_RESEARCH_PLAN.md before any result was computed; they are
descriptive definitions, not quality thresholds):

* zero/large switch: an asset at <= 1% in one fold and >= 20% in the next, or the reverse;
* persistent major holding: >= 10% in every fold.

The training-only bootstrap refits each fold's policy on resampled *training* returns only, so the
weights of a test year never depend on that year's observations.
"""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
import os

import numpy as np
import pandas as pd

from .bootstrap import bootstrap_indices, resampled_prices, stationary_block_length
from .returns import simple_returns

SWITCH_LOW, SWITCH_HIGH = .01, .20
PERSISTENT_WEIGHT = .10


def target_changes(weights: pd.DataFrame) -> pd.Series:
    """D_t between consecutive target allocations (NaN for the first fold)."""
    return 0.5 * weights.diff().abs().sum(axis=1, min_count=1)


def concentration_path(weights: pd.DataFrame) -> pd.DataFrame:
    hhi = (weights ** 2).sum(axis=1)
    return pd.DataFrame({"Max weight": weights.max(axis=1), "Largest holding": weights.idxmax(axis=1),
                         "HHI": hhi, "Effective assets": 1 / hhi})


def largest_changes(weights: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """The `top` largest absolute single-asset target changes between consecutive folds."""
    rows = []
    years = list(weights.index)
    for previous, year in zip(years, years[1:]):
        for asset in weights.columns:
            before, after = weights.loc[previous, asset], weights.loc[year, asset]
            rows.append({"Year": year, "Asset": asset, "Before": before, "After": after, "Change": after - before})
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    return table.reindex(table["Change"].abs().sort_values(ascending=False).index).head(top).reset_index(drop=True)


def zero_large_switches(weights: pd.DataFrame, low: float = SWITCH_LOW, high: float = SWITCH_HIGH) -> pd.DataFrame:
    rows = []
    years = list(weights.index)
    for previous, year in zip(years, years[1:]):
        for asset in weights.columns:
            before, after = weights.loc[previous, asset], weights.loc[year, asset]
            if (before <= low and after >= high) or (before >= high and after <= low):
                rows.append({"Year": year, "Asset": asset, "Before": before, "After": after})
    return pd.DataFrame(rows, columns=["Year", "Asset", "Before", "After"])


def persistent_holdings(weights: pd.DataFrame, level: float = PERSISTENT_WEIGHT) -> list[str]:
    return [asset for asset in weights.columns if (weights[asset] >= level).all()]


def realized_risk(result, trading_days: int = 252) -> pd.DataFrame:
    """Ex-ante (training) estimated volatility versus the realized volatility of each test year."""
    rows = []
    for policy in result.policies:
        for fold in result.folds:
            year = fold.test_year
            estimated = result.train_metrics.loc[(policy, year), "Estimated volatility"]
            returns = result.oos_returns.loc[str(year), policy]
            rows.append({"Policy": policy, "Year": year, "Estimated volatility": float(estimated),
                         "Realized volatility": float(returns.std(ddof=1) * np.sqrt(trading_days))})
    return pd.DataFrame(rows).set_index(["Policy", "Year"])


def stability_table(result, strategies=None) -> pd.DataFrame:
    """One row per strategy: target changes, traded turnover, concentration, switches, leverage weight."""
    strategies = list(result.strategies) if strategies is None else list(strategies)
    risk = realized_risk(result)
    rows = {}
    for name in strategies:
        weights = result.weights[name]
        changes = target_changes(weights).dropna()
        traded = result.trading[name].iloc[1:] if result.trading is not None else pd.Series(dtype=float)
        path = concentration_path(weights)
        levered = [c for c in weights.columns if " x" in c]
        row = {"Mean target change": changes.mean(), "Max target change": changes.max(),
               "Mean traded turnover": traded.mean(), "Max traded turnover": traded.max(),
               "Mean max weight": path["Max weight"].mean(), "Max max weight": path["Max weight"].max(),
               "Mean effective assets": path["Effective assets"].mean(),
               "Min effective assets": path["Effective assets"].min(),
               "Zero/large switches": len(zero_large_switches(weights)),
               "Persistent holdings": ", ".join(persistent_holdings(weights)) or "—",
               "Mean leveraged weight": weights[levered].sum(axis=1).mean() if levered else 0.}
        if name in result.policies:
            row["Mean estimated volatility"] = risk.loc[name, "Estimated volatility"].mean()
            row["Mean realized volatility (yearly)"] = risk.loc[name, "Realized volatility"].mean()
        rows[name] = row
    return pd.DataFrame(rows).T.rename_axis("Strategy")


def window_sensitivity(primary, alternative, policies=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Weight distance 0.5 * sum|w_primary - w_alternative| per policy and year, and a summary that puts
    weight sensitivity next to performance sensitivity (both runs share test years and costs)."""
    policies = primary.policies if policies is None else list(policies)
    distance = pd.DataFrame({p: 0.5 * (primary.weights[p] - alternative.weights[p].reindex(
        columns=primary.weights[p].columns, fill_value=0.)).abs().sum(axis=1) for p in policies})
    rows = {}
    for p in policies:
        levered = [c for c in primary.weights[p].columns if " x" in c]
        rows[p] = {"Mean weight distance": distance[p].mean(), "Max weight distance": distance[p].max(),
                   "CAGR (primary)": primary.metrics.loc[p, "CAGR"],
                   "CAGR (alternative)": alternative.metrics.loc[p, "CAGR"],
                   "Volatility (primary)": primary.metrics.loc[p, "Volatility annualized"],
                   "Volatility (alternative)": alternative.metrics.loc[p, "Volatility annualized"],
                   "Max drawdown (primary)": primary.metrics.loc[p, "Max Drawdown"],
                   "Max drawdown (alternative)": alternative.metrics.loc[p, "Max Drawdown"],
                   "Leveraged weight (primary)": primary.weights[p][levered].sum(axis=1).mean() if levered else 0.,
                   "Leveraged weight (alternative)": (alternative.weights[p][levered].sum(axis=1).mean()
                                                      if levered else 0.)}
    return distance.rename_axis("Test year"), pd.DataFrame(rows).T.rename_axis("Policy")


@dataclass
class WeightSensitivity:
    """Training-only bootstrap dispersion of each fold's fitted weights."""
    replications: int
    seed: int
    block_lengths: pd.Series
    draws: pd.DataFrame          # index (policy, year, replication), columns = assets
    distance: pd.DataFrame       # mean 0.5 * sum|w_b - w_hat| per (year) x policy
    ranges: pd.DataFrame         # per (policy, asset): mean point weight, mean P5, mean P95 over folds
    failures: int

    def summary(self) -> pd.DataFrame:
        return pd.DataFrame({"Mean bootstrap distance": self.distance.mean(),
                             "Max bootstrap distance": self.distance.max()}).rename_axis("Policy")


def _refit_chunk(train, config, risk_profiles, policies, rows):
    from .robustness import fit_policies
    out = []
    for row in rows:
        try:
            weights, _ = fit_policies(resampled_prices(train, row), config, risk_profiles)
            out.append({p: weights[p].to_numpy() for p in policies})
        except (RuntimeError, ValueError):
            out.append(None)
    return out


def _single_threaded():
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)


def training_bootstrap(prices: pd.DataFrame, config, result, *, replications: int = 40, seed: int = 0,
                       rates=None, risk_profiles: bool = True, workers: int | None = None) -> WeightSensitivity:
    """Refit each fold's policies on stationary-bootstrap resamples of that fold's training data only.

    Whole dates are resampled jointly (cross-asset dependence kept), with the expected block length
    of the training returns (Politis-White, mean over assets). Seeds are `seed + test_year`, drawn up
    front, so results do not depend on the worker count. Point estimates are the walk-forward weights.
    """
    universe = prices[list(result.universe)]
    policies = list(result.policies)
    # Few processes: each worker loads SciPy, and one per core exhausted virtual memory on this machine.
    workers = workers or min(4, os.cpu_count() or 1)
    draws, distances, blocks, failures = [], {}, {}, 0
    for fold in result.folds:
        train = universe.loc[(universe.index >= fold.return_base) & (universe.index <= fold.train_end)]
        if train.index[-1] >= fold.test_start:
            raise RuntimeError("Bootstrap training window overlaps the test year.")
        fold_config = config if rates is None else replace(config, risk_free_rate=rates.mean_risk_free(train.index))
        returns = simple_returns(train)
        block = stationary_block_length(returns)
        blocks[fold.test_year] = block
        indices = bootstrap_indices(len(returns), block, replications, seed + fold.test_year)
        chunks = np.array_split(indices, min(workers, replications))
        if workers > 1:
            with ProcessPoolExecutor(max_workers=workers, initializer=_single_threaded) as pool:
                parts = list(pool.map(_refit_chunk, *zip(*[(train, fold_config, risk_profiles, policies, c)
                                                            for c in chunks])))
        else:
            parts = [_refit_chunk(train, fold_config, risk_profiles, policies, c) for c in chunks]
        fits = [fit for part in parts for fit in part]
        failures += sum(fit is None for fit in fits)
        for policy in policies:
            point = result.weights[policy].loc[fold.test_year].reindex(universe.columns).to_numpy()
            gaps = []
            for b, fit in enumerate(fits):
                if fit is None:
                    continue
                draws.append(pd.Series(fit[policy], index=universe.columns, name=(policy, fold.test_year, b)))
                gaps.append(0.5 * np.abs(fit[policy] - point).sum())
            distances.setdefault(policy, {})[fold.test_year] = float(np.mean(gaps)) if gaps else np.nan
    draws = pd.DataFrame(draws)
    draws.index = pd.MultiIndex.from_tuples(draws.index, names=["Policy", "Year", "Replication"])
    ranges = {}
    for policy in policies:
        sub = draws.loc[policy]
        p5 = sub.groupby(level="Year").quantile(.05).mean()
        p95 = sub.groupby(level="Year").quantile(.95).mean()
        point = result.weights[policy].reindex(columns=universe.columns).mean()
        for asset in universe.columns:
            ranges[(policy, asset)] = {"Mean point weight": point[asset], "Mean P5": p5[asset], "Mean P95": p95[asset]}
    return WeightSensitivity(replications, seed, pd.Series(blocks, name="Expected block length"), draws,
                             pd.DataFrame(distances).rename_axis("Test year"),
                             pd.DataFrame(ranges).T.rename_axis(["Policy", "Asset"]), failures)


def research_summary(result, alternative=None, sensitivity=None, reference: str = "Constrained Equal Weight"
                     ) -> pd.DataFrame:
    """Performance and stability side by side, one row per strategy (raw values, no composite score)."""
    from .robustness import leave_one_year_out
    perf = result.summary()
    stab = stability_table(result)
    table = pd.DataFrame(index=list(result.strategies) + ([result.benchmark] if result.benchmark else []))
    for column in ("CAGR", "Volatility annualized", "Max Drawdown", "Sharpe", "CAGR excluding best year"):
        table[column] = perf[column]
    nav_cagr = result.metrics["CAGR"]
    table[f"Relative growth vs {reference}"] = (1 + nav_cagr) / (1 + nav_cagr[reference]) - 1
    signs = {}
    for name in result.policies:
        loyo = leave_one_year_out(result, name, reference).iloc[:, 0]
        signs[name] = int((np.sign(loyo.drop("Toutes les années")) != np.sign(loyo["Toutes les années"])).sum())
    table["Years whose removal flips the sign"] = pd.Series(signs)
    for column in ("Mean target change", "Mean traded turnover", "Mean max weight", "Mean effective assets",
                   "Zero/large switches", "Mean leveraged weight", "Mean estimated volatility"):
        table[column] = stab[column]
    if alternative is not None:
        distance, _ = window_sensitivity(result, alternative)
        table["Mean weight distance rolling vs expanding"] = distance.mean()
        table["CAGR (expanding window)"] = alternative.metrics["CAGR"]
    if sensitivity is not None:
        table["Mean bootstrap weight distance"] = sensitivity.distance.mean()
    return table


def stability_warnings(summary: pd.DataFrame, risk: pd.DataFrame | None = None) -> list[str]:
    """Factual French statements (signs and the plan's counting conventions only; no quality cutoff)."""
    notes = []
    for name, row in summary.iterrows():
        label = name
        if row.get("Zero/large switches", 0) and row["Zero/large switches"] > 0:
            notes.append(f"{label} : {int(row['Zero/large switches'])} bascule(s) d'un actif entre ≤ 1 % et ≥ 20 % "
                         "d'une année sur l'autre.")
        flips = row.get("Years whose removal flips the sign")
        if pd.notna(flips) and flips > 0:
            notes.append(f"{label} : retirer {int(flips)} année(s) de test inverse le signe de l'écart avec "
                         "l'équipondéré contraint.")
        # Display rounding only: a weight that prints as 0% is not reported.
        if pd.notna(row.get("Mean leveraged weight")) and row.get("Mean leveraged weight", 0) >= .005 and \
                name not in ("Constrained Equal Weight", "Equal Weight"):
            notes.append(f"{label} : poids moyen de l'actif synthétique à levier {row['Mean leveraged weight']:.0%}.")
        if pd.notna(row.get("CAGR (expanding window)")) and \
                pd.notna(row.get("Mean weight distance rolling vs expanding")):
            notes.append(f"{label} : CAGR {row['CAGR']:.1%} en fenêtre glissante contre "
                         f"{row['CAGR (expanding window)']:.1%} en fenêtre croissante ; écart d'allocation moyen "
                         f"{row['Mean weight distance rolling vs expanding']:.0%}.")
    if risk is not None:
        for name, sub in risk.groupby(level="Policy"):
            above = int((sub["Realized volatility"] > sub["Estimated volatility"]).sum())
            if above:
                notes.append(f"{name} : volatilité réalisée supérieure à l'estimation ex ante {above} année(s) sur "
                             f"{len(sub)}.")
    return notes
