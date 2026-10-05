"""Presentation only; calculations retain full precision."""
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd


def plot_frontier(stats: pd.DataFrame, optimization):
    fig, ax = plt.subplots(figsize=(13, 8), layout="constrained")
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


def allocation_summary(weights: pd.DataFrame, threshold: float = .01) -> pd.Series:
    return weights.apply(lambda row: " · ".join(f"{name} {weight:.1%}" for name, weight in
                        row.sort_values(ascending=False).items() if weight >= threshold), axis=1)
