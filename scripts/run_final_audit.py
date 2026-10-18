"""V2.2 Phase D: final cross-benchmark audit (post-hoc, exploratory, read-only).

Rebuilds the six wealth paths in memory with the validated components (no Phase B/C output is
rewritten), runs audits A-I and writes outputs/v2_2/phase_d/ (ignored by Git). Research artifacts
are read through the guarded bridge; their 12 hashes are checked before and after.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from portfolio_lab.v2 import admission as AD, charts, custom as C, custom_analytics as A, final_audit as F, metrics as M
from portfolio_lab.v2.bridge import load_lab
from portfolio_lab.v2.guard import HARD_CUTOFF, sha256_file
from portfolio_lab.v2.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/v2_2/phase_d"
NAMES = ["BRK.B", "Diversifié", "N07", "D2_25", "B1", "B2"]
INITIAL = 100000.0
STRESS = {"T4 2018": ("2018-10-01", "2018-12-31"), "COVID 2020 (fenêtre fixe)": ("2020-02-19", "2020-03-23"),
          "Année 2022": ("2022-01-01", "2022-12-30")}
WINDOWS = {"Complet": ("2014-10-01", "2023-12-29"), "2015–2019": ("2015-01-01", "2019-12-31"),
           "2020–2023": ("2020-01-01", "2023-12-29"),
           **{str(y): (f"{y}-01-01" if y > 2014 else "2014-10-01", f"{y}-12-31") for y in range(2014, 2024)}}


def jsonable(frame):
    return json.loads(frame.to_json(force_ascii=False, default_handler=str))


def main():
    settings = load_settings(ROOT)
    frozen = {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    assert frozen == {a.name: a.sha256 for a in settings.artifacts}, "frozen Research hashes differ"
    original = C.load_spec(ROOT / "config/v2/portfolios/mon_portefeuille_diversifie.json")
    panel = C.load_validated_panel(original)
    diversified = C.simulate(original, panel)
    brk = A.benchmark_result("BRK_B")
    lab = load_lab(ROOT)
    view = A.common_calendar(lab, diversified.ledger.index)
    paths = pd.DataFrame({"BRK.B": brk.ledger.nav, "Diversifié": diversified.ledger.nav,
                          **{s: view.wealth[s] for s in ["N07", "D2_25", "B1", "B2"]}})[NAMES]
    rate = view.eur_rate
    report = {"nature": "Analyse exploratoire a posteriori ; aucun résultat existant n'est modifié."}

    # ---------------------------------------------------------------- A. accounting and data integrity
    full = lab.wealth
    rec = {}
    for name in NAMES:
        v = paths[name]
        r = M.path_returns(v, INITIAL)
        rec[name] = {"first": str(v.index[0].date()), "last": str(v.index[-1].date()), "observations": len(v),
                     "initial": INITIAL, "first_value": float(v.iloc[0]), "final": float(v.iloc[-1]),
                     "cagr_from_values": M.cagr(float(v.iloc[-1]), INITIAL, M.years(v.index)),
                     "years": M.years(v.index), "exact_zero_return_days": int((r == 0).sum()),
                     "non_finite_or_non_positive": int((~np.isfinite(v) | (v <= 0)).sum()),
                     "max_abs_daily_return": float(r.abs().max()), "max_abs_daily_return_date": str(r.abs().idxmax().date())}
    research_extra = full.index.difference(paths.index)
    rec_research_full = {s: {"observations_2369": len(full), "final_2369": float(full[s].iloc[-1]),
                             "return_on_dropped_dates": {str(d.date()): float(full[s].loc[d] / full[s].shift(1).loc[d] - 1)
                                                         for d in research_extra},
                             "final_identical_after_sampling": bool(full[s].iloc[-1] == paths[s].iloc[-1])}
                         for s in ["N07", "D2_25", "B1", "B2"]}
    sessions = AD.euronext_sessions()
    report["A_accounting"] = {
        "paths": rec, "research_full_calendar": rec_research_full,
        "calendar": {"common_sessions": len(paths), "equals_euronext_rule_calendar": bool(paths.index.equals(sessions)),
                     "research_dates": len(full), "research_only_dates": [str(d.date()) for d in research_extra],
                     "custom_only_dates": [str(d.date()) for d in paths.index.difference(full.index)],
                     "max_date": str(paths.index.max().date()), "cutoff_respected": bool(paths.index.max() <= HARD_CUTOFF)},
        "phase_b_c_consistency": {"diversified_final": float(paths["Diversifié"].iloc[-1]), "brk_final": float(paths["BRK.B"].iloc[-1])},
    }
    # Valuation clocks: correlation of each path with the SPY EUR level (previous NYSE close at the
    # Paris snapshot) taken at the same snapshot vs. at the next one (which contains NYSE day D).
    spy = panel.prices["SP500"].pct_change()
    daily = paths.pct_change()
    report["A_accounting"]["clock_diagnostic_corr_with_spy"] = {
        name: {"same_snapshot": float(daily[name].corr(spy)), "spy_next_snapshot": float(daily[name].corr(spy.shift(-1)))}
        for name in NAMES}

    # ---------------------------------------------------------------- B. volatility by frequency
    vol = F.volatility_table(paths, INITIAL)
    report["B_volatility"] = {f"{n}|{f}": row for (n, f), row in vol.to_dict(orient="index").items()}
    ranks = {f: vol.xs(f, level="Fréquence")["volatilité"].rank(ascending=False).astype(int).to_dict() for f in F.PERIODS}
    report["B_volatility_ranks"] = ranks

    # ---------------------------------------------------------------- C. drawdowns
    report["C_drawdowns"] = {n: F.drawdown_profile(paths[n], INITIAL) for n in NAMES}
    for n in NAMES:  # cross-check with the existing Research-convention helper
        rec_m = M.recovery(paths[n], INITIAL)
        report["C_drawdowns"][n]["existing_helper_trough"] = str(pd.Timestamp(rec_m["maxdd_trough_date"]).date())
    years = {str(y): {n: float(paths[n].loc[str(y)].iloc[-1] / F.window(paths[n], INITIAL, paths.loc[str(y)].index[0], None)[1] - 1)
                      for n in NAMES} for y in range(2014, 2024)}
    report["C_worst_calendar_year"] = {n: min(((y, v[n]) for y, v in years.items()), key=lambda t: t[1]) for n in NAMES}
    report["C_worst_rolling"] = {f"{m} mois": {n: float(v) for n, v in F.worst_rolling(paths, INITIAL, m).items()} for m in (3, 6, 12)}
    report["C_maxdd_brk_vs_diversified"] = {n: report["C_drawdowns"][n] for n in ("BRK.B", "Diversifié")}

    # ---------------------------------------------------------------- D. stress periods
    stress = {}
    for label, (a, b) in STRESS.items():
        stress[label] = {n: F.window_stats(paths[n], INITIAL, a, b) for n in NAMES}
    covid = {}
    for n in NAMES:   # event-specific: the drawdown episode containing March 2020
        v = paths[n]
        block = v.loc[:"2020-12-31"]
        peaks = np.maximum.accumulate(np.r_[INITIAL, block.to_numpy()])[1:]
        dd = pd.Series(block.to_numpy() / peaks - 1, index=block.index).loc["2020-01-01":]
        trough = dd.idxmin()
        prof_peak = peaks[block.index.get_loc(trough)]
        peak_date = block.loc[:trough][block.loc[:trough] >= prof_peak - 1e-9].index[-1]
        rec_after = v.loc[trough:][v.loc[trough:] >= prof_peak - 1e-9]
        covid[n] = {"peak": str(peak_date.date()), "trough": str(trough.date()), "drawdown": float(-dd.min()),
                    "recovery": str(rec_after.index[0].date()) if len(rec_after) else None}
    stress["COVID 2020 (épisode pic-creux)"] = covid
    report["D_stress"] = stress
    report["D_calendar_years"] = {y: {n: F.window_stats(paths[n], INITIAL, *WINDOWS[y]) for n in NAMES}
                                  for y in [str(x) for x in range(2014, 2024)]}

    # ---------------------------------------------------------------- E. risk-adjusted
    risk = F.risk_table(paths, INITIAL, rate)
    report["E_risk"] = jsonable(risk.T)
    reported = {"BRK.B": (0.124, 0.206, 0.296, 0.66), "Diversifié": (0.127, 0.139, 0.296, 0.91),
                "N07": (0.274, 0.256, 0.377, 1.06), "D2_25": (0.296, 0.289, 0.451, 1.02),
                "B1": (0.190, 0.206, 0.314, 0.93), "B2": (0.299, 0.397, 0.612, 0.85)}
    report["E_reported_vs_recomputed"] = {
        n: {k: {"reported": rv, "recomputed": float(risk.loc[n, c]),
                "match_at_reported_precision": abs(round(float(risk.loc[n, c]), 3 if k != "Sharpe" else 2) - rv) < 1.5e-3}
            for k, c, rv in zip(("CAGR", "Volatilité", "MaxDD", "Sharpe"), ("CAGR", "Volatilité", "MaxDD", "Sharpe (EUR)"), reported[n])}
        for n in NAMES}

    # ---------------------------------------------------------------- F. correlations
    corr = F.correlations(paths, INITIAL)
    report["F_correlations"] = {k: jsonable(v) for k, v in corr.items()}
    report["F_beta_to_B1"] = {rule: {n: F.beta(paths, INITIAL, n, "B1", code) for n in NAMES if n != "B1"}
                              for rule, code in (("Hebdomadaire", "W-FRI"), ("Mensuel", "ME"))}

    # ---------------------------------------------------------------- G. bootstrap
    report["G_bootstrap"] = {str(L): F.block_bootstrap(paths, INITIAL, rate, L) for L in (5, 21, 63)}

    # ---------------------------------------------------------------- H. windows
    win = {}
    for label, (a, b) in WINDOWS.items():
        sub = {}
        for n in NAMES:
            block, base = F.window(paths[n], INITIAL, a, b)
            sub[n] = F.risk_table(block.to_frame(n), base, rate)[["CAGR", "Volatilité", "MaxDD", "Sharpe (EUR)"]].iloc[0].to_dict()
        frame = pd.DataFrame(sub).T
        sub["_rank_CAGR"] = frame["CAGR"].rank(ascending=False).astype(int).to_dict()
        sub["_rank_Sharpe"] = frame["Sharpe (EUR)"].rank(ascending=False).astype(int).to_dict()
        win[label] = sub
    report["H_windows"] = win

    # ---------------------------------------------------------------- I. BRK.B admission regression
    raw = ROOT / "data/v2_1/raw"
    b = pd.read_csv(raw / "yahoo/BRK-B_2014-09-01_2023-12-29.csv", index_col=0, parse_dates=True)
    a = pd.read_csv(raw / "yahoo/BRK-A_2014-09-01_2023-12-29.csv", index_col=0, parse_dates=True)
    vendor = AD.parse_nasdaq_history((raw / "nasdaq/BRK.B_2014-09-01_2023-12-29.json").read_text(encoding="utf-8"))
    ranges = json.loads((raw / "sec/berkshire_10k_2015_price_ranges.json").read_text(encoding="utf-8"))["ranges"]
    binding, diag, original_checks = AD.validate_brk_bis(b, a, vendor, ranges)
    manifest = json.loads((raw / "MANIFEST.json").read_text(encoding="utf-8"))
    report["I_brk"] = {"original_a6": [c.as_dict() for c in original_checks],
                       "original_failures": [c.name for c in original_checks if not c.passed],
                       "a6_bis": [c.as_dict() for c in binding], "a6_bis_all_pass": all(c.passed for c in binding),
                       "ten_k_closes_per_class": {cls: sum(r["closes"] for k, r in diag["ten_k"].items() if k.endswith(cls))
                                                  for cls in (" A", " B")},
                       "ten_k_complete_quarters": sum(r["complete_quarter"] for k, r in diag["ten_k"].items() if k.endswith(" B")),
                       "nasdaq_overlap_days": diag["vendor"]["common"],
                       "raw_hashes_match_manifest": {k: sha256_file(raw / k) == manifest[k]["sha256"] for k in
                                                     ("yahoo/BRK-B_2014-09-01_2023-12-29.csv", "yahoo/BRK-A_2014-09-01_2023-12-29.csv",
                                                      "nasdaq/BRK.B_2014-09-01_2023-12-29.json", "sec/berkshire_10k_2015_price_ranges.json")},
                       "level_equals_close_over_fx": None}
    level = C.load_validated_panel(brk.spec, A.benchmark_catalog()).prices["BRK_B"]
    rebuilt, _ = AD.eur_level(b["Close"].astype(float), AD.parse_ecb((raw / "ecb/EXR_D_USD_EUR_SP00_A.csv").read_text(encoding="utf-8")),
                              sessions, "BRK-B")
    report["I_brk"]["level_equals_close_over_fx"] = float((level / rebuilt - 1).abs().max())

    # ---------------------------------------------------------------- figures and outputs
    OUT.mkdir(parents=True, exist_ok=True)
    charts.setup()
    colors = {"BRK.B": "#0f766e", "Diversifié": "#8a46ba"}
    for key, title, frame, fmt in (("equity", "Patrimoine normalisé (base 1) — bases comptables distinctes", paths / INITIAL, ".2f"),
                                   ("underwater", "Baisse depuis le sommet", paths.apply(lambda v: M.drawdown(v, INITIAL)), ".0%")):
        fig = go.Figure()
        charts._layout(fig, title, "Audit Phase D, exploratoire ; BRK.B et Diversifié économiques, Research après frais et impôts intermédiaires", 480)
        for n in NAMES:
            fig.add_scatter(x=frame.index, y=frame[n], name=n,
                            line=dict(color=colors[n] if n in colors else charts.style(lab, n)["color"], width=2 if n in colors else 1.4))
        fig.update_yaxes(tickformat=fmt)
        fig.write_html(OUT / f"{key}.html", include_plotlyjs="cdn")
    assert frozen == {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    report["research_hashes_unchanged"] = len(frozen)
    (OUT / "phase_d_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print("written", OUT / "phase_d_audit.json")


if __name__ == "__main__":
    main()
