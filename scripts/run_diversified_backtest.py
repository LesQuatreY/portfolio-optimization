"""V2.2 Phase B: historical backtest of « Mon portefeuille diversifié », exactly as saved.

Gate: every asset of the saved specification must be ``validated`` in the catalog and load through
``load_validated_panel`` (hash, cutoff and common-calendar checks). The specification file is read,
never modified. Research is read through the guarded bridge only; its frozen hashes are checked
before and after. Outputs go to outputs/v2_2/ (ignored by Git). No tax model is applied.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_lab.v2 import backtest_checks as B, custom as C, custom_analytics as A
from portfolio_lab.v2.bridge import load_lab
from portfolio_lab.v2.guard import HARD_CUTOFF, sha256_file
from portfolio_lab.v2.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/v2_2"
SPEC = ROOT / "config/v2/portfolios/mon_portefeuille_diversifie.json"
COMPARED = ["N07", "D2_25", "B1", "B2", "B1M", "B2M"]
EXPECTED_WEIGHTS = {"EM": .30, "SP500": .30, "WORLD": .15, "CAC40": .10, "GOLD": .10, "BTC": .05}


def windows(paths: pd.DataFrame, initial: float) -> pd.DataFrame:
    """Return and maximum drawdown inside each predefined window, for every path (same dates)."""
    rows = []
    for label, (start, end) in A.WINDOWS.items():
        for name, total in paths.items():
            block = total.loc[start:end]
            pos = total.index.get_loc(block.index[0])
            base = initial if pos == 0 else float(total.iloc[pos - 1])
            rows.append({"Fenêtre": label, "Portefeuille": name, "Rendement": float(block.iloc[-1] / base - 1),
                         "MaxDD": float(-(block / np.maximum.accumulate(np.r_[base, block.to_numpy()])[1:] - 1).min()),
                         "Début": str(block.index[0].date()), "Fin": str(block.index[-1].date())})
    return pd.DataFrame(rows)


def main():
    settings = load_settings(ROOT)
    frozen = {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    assert frozen == {a.name: a.sha256 for a in settings.artifacts}, "frozen Research hashes differ"
    spec_hash = sha256_file(SPEC)
    spec = C.load_spec(SPEC)
    assert dict(spec.weights) == EXPECTED_WEIGHTS and spec.rebalance == "monthly" and spec.cost_bps == 0
    assert (spec.initial_capital, spec.start, spec.end, spec.currency) == (100000.0, "2014-10-01", "2023-12-29", "EUR")
    catalog = C.load_catalog()
    assert C.availability(spec, catalog) == [], "Phase A gate: an asset is not validated"
    panel = C.load_validated_panel(spec, catalog)            # hash, cutoff and common-calendar gates
    assert panel.prices.index.max() <= HARD_CUTOFF and panel.prices.index.equals(panel.sessions)
    result = C.simulate(spec, panel)

    lab = load_lab(ROOT)
    view = A.common_calendar(lab, result.ledger.index)
    analytics_row = A.risk(result.ledger.nav, spec.initial_capital)
    accounting, stats = B.ledger_checks(result, panel, analytics_row, rate=view.eur_rate)
    causality = B.causality_checks(spec, panel)
    checks = accounting + causality

    summary = A.summary(result)
    summary["Sharpe (taux EUR Research)"] = A.risk(result.ledger.nav, spec.initial_capital,
                                                   rate=view.eur_rate)["Sharpe (taux EUR Research)"]
    annual = A.annual_returns(result)
    rolling = A.rolling(result.ledger.nav)
    stability, correlations = A.stability(result)
    weights = result.weights
    _, comparison = A.comparison(result, view, COMPARED)
    paths = pd.DataFrame({"Diversifié": result.ledger.nav, **{s: view.wealth[s] for s in COMPARED}})
    window_table = windows(paths, spec.initial_capital)
    annual_all = paths.apply(lambda v: (1 + C_path_returns(v, spec.initial_capital)).groupby(v.index.year).prod() - 1)

    OUT.mkdir(parents=True, exist_ok=True)
    result.ledger.to_csv(OUT / "ledger.csv")
    result.holdings.to_csv(OUT / "holdings.csv")
    result.trades.to_csv(OUT / "trades.csv", index=False)
    figures = {**A.figures(result), **{f"compare_{k}": v for k, v in A.comparison_figures(result, view, COMPARED)[0].items()}}
    for name, fig in figures.items():
        fig.write_html(OUT / f"{name}.html", include_plotlyjs="cdn")
    report = {
        "portfolio": spec.to_dict(), "identity": spec.identity, "spec_file_sha256": spec_hash,
        "spec_file_unchanged": sha256_file(SPEC) == spec_hash,
        "data": {a: {k: catalog[a][k] for k in ("sha256", "source", "calendar", "clock")} for a in spec.weights},
        "calendar_sessions": len(panel.sessions), "research_dates_not_in_custom_calendar": view.dropped_dates,
        "metadata": result.metadata(), "checks": [c.as_dict() for c in checks],
        "all_checks_passed": all(c.passed for c in checks), "accounting": stats,
        "summary": json.loads(summary.to_json(force_ascii=False)),
        "annual_returns": {str(k): float(v) for k, v in annual.items()},
        "annual_returns_comparison": json.loads(annual_all.to_json(force_ascii=False)),
        "rolling": {c: {"min": float(rolling[c].min()), "median": float(rolling[c].median()),
                        "max": float(rolling[c].max()), "last": float(rolling[c].iloc[-1])} for c in rolling},
        "stability": json.loads(stability.to_json(orient="records", force_ascii=False)),
        "windows_comparison": json.loads(window_table.to_json(orient="records", force_ascii=False)),
        "weights_drift": {a: {"min": float(weights[a].min()), "max": float(weights[a].max()),
                              "target": float(spec.weights[a])} for a in weights},
        "comparison": json.loads(comparison.to_json(orient="index", force_ascii=False)),
        "research_canonical_unchanged": json.loads(lab.summary.loc[COMPARED, ["cagr_net", "cagr_gross", "sharpe",
                                                                              "max_drawdown", "volatility"]].to_json(orient="index")),
    }
    for key in [a.name for a in settings.artifacts]:
        pass
    assert frozen == {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    report["frozen_research_hashes_unchanged"] = len(frozen)
    (OUT / "phase_b_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
                                             encoding="utf-8")
    print("checks:", sum(c.passed for c in checks), "/", len(checks), "passed")
    for c in checks:
        if not c.passed:
            print("  FAILED", c.as_dict())
    print(summary.T.to_string())
    print(comparison.to_string())


def C_path_returns(values, initial):
    from portfolio_lab.v2 import metrics as M
    return M.path_returns(values, initial)


if __name__ == "__main__":
    main()
