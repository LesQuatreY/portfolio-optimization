"""V2.2 Phase C: BRK.B buy & hold benchmark versus the diversified portfolio and frozen Research.

Gate: BRK_B must be ``validated`` in config/v2/custom_benchmarks.yaml and the six portfolio assets
in config/v2/custom_assets.yaml. Same Euronext valuation calendar and clocks as Phase B; Research
paths are sampled on it (values unchanged). Explicit costs: the catalog's cost_bps (baseline) and a
10 bp one-off purchase as sensitivity. No tax model. Outputs: outputs/v2_2/phase_c_report.json and
figures (ignored by Git). Research hashes are checked before and after.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_lab.v2 import backtest_checks as B, custom as C, custom_analytics as A, metrics as M
from portfolio_lab.v2.bridge import load_lab
from portfolio_lab.v2.guard import sha256_file
from portfolio_lab.v2.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/v2_2"
COMPARED = ["N07", "D2_25", "B1", "B2", "B1M", "B2M"]
PHASE_B_FINAL = 302448.53  # diversified portfolio, docs/V2_2_PHASE_B_RESULTS.md


def windows(paths: pd.DataFrame, initial: float) -> pd.DataFrame:
    rows = []
    for label, (start, end) in A.WINDOWS.items():
        for name, total in paths.items():
            block = total.loc[start:end]
            pos = total.index.get_loc(block.index[0])
            base = initial if pos == 0 else float(total.iloc[pos - 1])
            peaks = np.maximum.accumulate(np.r_[base, block.to_numpy()])[1:]
            rows.append({"Fenêtre": label, "Portefeuille": name, "Rendement": float(block.iloc[-1] / base - 1),
                         "MaxDD": float(-(block / peaks - 1).min())})
    return pd.DataFrame(rows)


def main():
    settings = load_settings(ROOT)
    frozen = {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    assert frozen == {a.name: a.sha256 for a in settings.artifacts}, "frozen Research hashes differ"
    benchmarks = A.benchmark_catalog()
    if benchmarks["BRK_B"]["status"] != "validated":
        raise SystemExit("BRK_B non validé : exécuter scripts/prepare_brk_benchmark.py après décision. Rien n'est calculé.")
    original = C.load_spec(ROOT / "config/v2/portfolios/mon_portefeuille_diversifie.json")
    diversified = C.simulate(original, C.load_validated_panel(original))
    assert abs(diversified.ledger.nav.iloc[-1] - PHASE_B_FINAL) < 0.05, "Phase B result changed"
    brk = A.benchmark_result("BRK_B", benchmarks)
    panel = C.load_validated_panel(brk.spec, benchmarks)
    lab = load_lab(ROOT)
    view = A.common_calendar(lab, diversified.ledger.index)
    accounting, stats = B.ledger_checks(brk, panel, A.risk(brk.ledger.nav, brk.spec.initial_capital), rate=view.eur_rate)
    checks = accounting + B.causality_checks(brk.spec, panel)
    checks.append(B.Check("Calendrier BRK.B = calendrier du portefeuille diversifié", float(len(brk.ledger)),
                          f"= {len(diversified.ledger)}", brk.ledger.index.equals(diversified.ledger.index)))
    with_cost = C.simulate(replace(brk.spec, cost_bps=10.0), panel)
    _, table = A.comparison(diversified, view, COMPARED, extra=[brk])
    figures, _ = A.comparison_figures(diversified, view, COMPARED, extra=[brk])
    paths = pd.DataFrame({"Diversifié": diversified.ledger.nav, "BRK.B": brk.ledger.nav,
                          **{s: view.wealth[s] for s in COMPARED}})
    annual = paths.apply(lambda v: (1 + M.path_returns(v, 100000)).groupby(v.index.year).prod() - 1)
    rolling = A.rolling(brk.ledger.nav)
    corr = M.path_returns(paths, 100000).corr().loc["BRK.B"]
    # Daily correlations with Research are distorted by clocks (Research Nasdaq lines are Paris-listed
    # ETFs at the Paris close, BRK.B the previous NYSE close): weekly and monthly ones are reported too.
    corr_w = paths.resample("W-FRI").last().pct_change().corr().loc["BRK.B"]
    corr_m = paths.resample("ME").last().pct_change().corr().loc["BRK.B"]
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fig in figures.items():
        fig.write_html(OUT / f"phase_c_{name}.html", include_plotlyjs="cdn")
    report = {
        "brk_metadata": brk.metadata(), "checks": [c.as_dict() for c in checks],
        "all_checks_passed": all(c.passed for c in checks), "accounting": stats,
        "comparison": json.loads(table.to_json(orient="index", force_ascii=False)),
        "cost_sensitivity_10bp": {"final": float(with_cost.ledger.nav.iloc[-1]),
                                  "cagr": A.risk(with_cost.ledger.nav, 100000)["CAGR économique"]},
        "windows": json.loads(windows(paths, 100000).to_json(orient="records", force_ascii=False)),
        "annual_returns": json.loads(annual.to_json(force_ascii=False)),
        "rolling_brk": {c: {"min": float(rolling[c].min()), "median": float(rolling[c].median()),
                            "max": float(rolling[c].max())} for c in rolling},
        "daily_return_correlation_with_brk": {k: float(v) for k, v in corr.items()},
        "weekly_return_correlation_with_brk": {k: float(v) for k, v in corr_w.items()},
        "monthly_return_correlation_with_brk": {k: float(v) for k, v in corr_m.items()},
        "research_dates_not_in_calendar": view.dropped_dates,
    }
    assert frozen == {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    report["frozen_research_hashes_unchanged"] = len(frozen)
    (OUT / "phase_c_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
                                             encoding="utf-8")
    print("checks:", sum(c.passed for c in checks), "/", len(checks))
    print(table.to_string())


if __name__ == "__main__":
    main()
