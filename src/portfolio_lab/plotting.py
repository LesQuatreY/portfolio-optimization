"""Presentation only; calculations retain full precision."""
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd


def plot_frontier(stats: pd.DataFrame, optimization, band: pd.DataFrame | None = None):
    """Observed frontier; optionally a bootstrap uncertainty band (index = estimated-volatility grid)."""
    fig, ax = plt.subplots(figsize=(13, 8), layout="constrained")
    if band is not None and len(band):
        ax.fill_between(band.index, band["Lower"], band["Upper"], color="tab:blue", alpha=.15, linewidth=0,
                        label=f"Bootstrap uncertainty band ({band['Level'].iloc[0]:.0%})")
    curve = optimization.frontier.drop_duplicates(subset=["Volatility", "CAGR"])
    ax.plot(curve["Volatility"], curve["CAGR"], color="black", label="Efficient frontier")
    for name, row in stats.iterrows():
        ax.scatter(row["Volatility annualized"], row["CAGR"], s=35)
        right_edge = row["Volatility annualized"] > .8 * stats["Volatility annualized"].max()
        ax.annotate(name, (row["Volatility annualized"], row["CAGR"]),
                    xytext=(-5 if right_edge else 5, 7), ha="right" if right_edge else "left",
                    textcoords="offset points", fontsize=8)
    grouped = {}
    for name, row in optimization.portfolios.items():
        if row["weights"] is None:
            continue
        key = tuple(np.round([row["Volatility"], row["CAGR"]], 7))
        grouped.setdefault(key, []).append(name)
    for (x, y), names in grouped.items():
        ax.scatter(x, y, s=90, marker="D", label=" / ".join(names))
    ax.set(xlabel="Annualized volatility (EUR)", ylabel="CAGR (EUR)", title="Historical risk and compounded return")
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(alpha=.2)
    ax.margins(x=.12, y=.1)
    ax.legend(loc="upper left", fontsize=8)
    return fig


def plot_drawdown(stats: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 7), layout="constrained")
    for name, row in stats.iterrows():
        ax.scatter(abs(row["Max Drawdown"]), row["CAGR"])
        right_edge = abs(row["Max Drawdown"]) > .8 * stats["Max Drawdown"].abs().max()
        ax.annotate(f"{name} (Calmar {row['Calmar']:.2f})", (abs(row["Max Drawdown"]), row["CAGR"]),
                    xytext=(-5 if right_edge else 5, 5), ha="right" if right_edge else "left",
                    textcoords="offset points", fontsize=8)
    ax.set(xlabel="Absolute maximum drawdown", ylabel="CAGR (EUR)", title="Drawdown and compounded return")
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(alpha=.2)
    ax.margins(x=.25, y=.1)
    return fig


def plot_oos_growth(nav: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 6), layout="constrained")
    for name in nav:
        ax.plot(nav.index, nav[name], label=name)
    ax.set(yscale="log", ylabel="Growth of 1 EUR (log scale)",
           title="Walk-forward out-of-sample growth (test-year returns only)")
    ax.grid(alpha=.2, which="both")
    ax.legend(loc="upper left", fontsize=8)
    return fig


def plot_allocations(weights: pd.DataFrame, title: str):
    """Annual target weights; each test year's allocation is held for that whole year."""
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    years = weights.index.astype(int)
    ax.stackplot(np.r_[years, years[-1] + 1], *[np.r_[weights[c], weights[c].iloc[-1]] for c in weights],
                 labels=weights.columns, step="post")
    ax.set(xlim=(years[0], years[-1] + 1), ylim=(0, 1), xlabel="Test year", ylabel="Weight", title=title)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.legend(loc="center left", bbox_to_anchor=(1, .5), fontsize=8)
    return fig


def plot_effective_assets(effective: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 4), layout="constrained")
    for name in effective:
        ax.step(effective.index.astype(int), effective[name], where="post", label=name, marker="o")
    ax.set(xlabel="Test year", ylabel="1 / HHI", title="Effective number of assets of walk-forward allocations")
    ax.grid(alpha=.2)
    ax.legend(fontsize=8)
    return fig


def plot_weight_profile(profile, investor_limit: float | None = None):
    """Best achievable Maximum Sharpe objective for each fixed weight of one asset."""
    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    table = profile.table
    ax.plot(table.index, table["Objective Sharpe"], color="black", label="Best achievable Sharpe")
    for level, style in zip((.99, .95), (":", "--")):
        ax.axhline(level * profile.optimum_objective, color="grey", linestyle=style, linewidth=1,
                   label=f"{level:.0%} of optimal Sharpe")
    ax.scatter([profile.optimum_weight], [profile.optimum_objective], s=80, marker="D", zorder=3,
               label=f"Unconstrained optimum ({profile.optimum_weight:.1%})")
    limit = profile.investor_limit if investor_limit is None else investor_limit
    if limit is not None:
        ax.axvline(limit, color="tab:red", linestyle="--", label=f"Investor limit ({limit:.0%})")
    ax.set(xlabel=f"{profile.asset} weight (others re-optimized)", ylabel="Sharpe (optimizer objective)",
           title=f"How sensitive is Maximum Sharpe to the {profile.asset} weight? (in-sample)")
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(alpha=.2)
    ax.legend(fontsize=8, loc="lower center")
    return fig


def allocation_summary(weights: pd.DataFrame, threshold: float = .01) -> pd.Series:
    return weights.apply(lambda row: " · ".join(f"{name} {weight:.1%}" for name, weight in
                        row.sort_values(ascending=False).items() if weight >= threshold), axis=1)
