"""Reproduction and accounting checks of the imported Research results (shown in the notebooks, run by tests).

* reproduction: every daily-path metric is recomputed from the frozen curve with Research's formulas
  and compared with Research's reference value; net CAGR is re-derived from net terminal wealth;
* accounting: lines add up to the total, terminal wealth reconciles with the final sale and exit
  taxes, and fees / taxes are counted exactly once (path + final sale = reported totals).
"""
from __future__ import annotations

import pandas as pd

from . import metrics as M
from .bridge import EXIT_TAXES, INTERIM_TAXES

METRIC_TOL = 1e-12          # observed differences are float rounding (<= 3e-16)
EUR_TOL = 1e-6
REPRODUCED = (("cagr_net", "FULL_cagr", "CAGR net (après impôts de sortie)"),
              ("arith_return", "arith_return", "Rendement arithmétique annualisé"),
              ("volatility", "volatility", "Volatilité annualisée"),
              ("sharpe", "sharpe", "Sharpe"),
              ("sortino", "sortino", "Sortino"),
              ("max_drawdown", "FULL_mdd", "MaxDD journalier"),
              ("worst_12m", "worst_12m", "Pire rendement sur 12 mois"),
              ("longest_underwater_sessions", "longest_underwater_sessions", "Plus longue période sous un sommet (séances)"))


def reproduction(lab) -> pd.DataFrame:
    rows = []
    n_years = M.years(lab.wealth.index)
    for sid in lab.ids:
        ref = lab.reference.loc[sid]
        got = M.path_metrics(lab.wealth[sid], lab.initial, lab.eur_rate)
        got["cagr_net"] = M.cagr(float(ref["terminal_net"]), lab.initial, n_years)
        for key, column, label in REPRODUCED:
            a, b = float(ref[column]), float(got[key])
            rows.append({"Portefeuille": sid, "Indicateur": label, "Référence Research": a, "Recalculé": b,
                         "Écart": abs(a - b), "Conforme": abs(a - b) <= METRIC_TOL})
    return pd.DataFrame(rows)


def accounting(lab) -> pd.DataFrame:
    s, ref = lab.summary, lab.reference
    total = lab.wealth
    lines = sum(lab.curves[c] for c in lab.lines.index)
    pea_lines = sum(lab.curves[c] for c in lab.lines.index if lab.lines.loc[c, "wrapper"] == "PEA")
    exit_sum = ref[list(EXIT_TAXES)].sum(axis=1)
    rows = [
        ("Même calendrier pour tous les portefeuilles", bool(total.notna().all().all()),
         f"{total.index[0].date()} → {total.index[-1].date()}, {len(total)} séances"),
        ("Somme des lignes = valeur totale (chaque séance)", float((lines - total).abs().max().max()) <= EUR_TOL,
         f"écart max {(lines - total).abs().max().max():.1e} €"),
        ("Lignes PEA = valeur du PEA (chaque séance)", float((pea_lines - lab.curves['pea']).abs().max().max()) <= EUR_TOL,
         f"écart max {(pea_lines - lab.curves['pea']).abs().max().max():.1e} €"),
        ("Patrimoine net = valeur après vente − impôts de sortie",
         float((ref["pre_liquidation_value"] - exit_sum - ref["terminal_net"]).abs().max()) <= EUR_TOL, ""),
        ("Frais de la vente finale = frais totaux − frais déjà inclus dans la courbe",
         float((s["liquidation_costs"] - (s["fees_total"] - s["fees_in_path"])).abs().max()) <= EUR_TOL,
         f"frais de vente {s['liquidation_costs'].min():,.0f} à {s['liquidation_costs'].max():,.0f} €".replace(",", " ")),
        ("Impôts inclus dans la courbe = impôts payés en cours de route (CTO + Bitcoin)",
         float((s["taxes_in_path"] - ref[list(INTERIM_TAXES)].sum(axis=1)).abs().max()) <= EUR_TOL, ""),
        ("Impôts totaux = en cours de route + sortie",
         float((ref["taxes_total"] - ref[list(INTERIM_TAXES)].sum(axis=1) - exit_sum).abs().max()) <= EUR_TOL, ""),
        ("Frais totaux = frais de transaction + garde",
         float((ref["fees_total"] - ref["trading_friction"] - ref["custody"]).abs().max()) <= EUR_TOL, ""),
        ("Frais de vente finale entre 0 et 0,5 % de la valeur finale",
         bool(((s["liquidation_costs"] >= 0) & (s["liquidation_costs"] <= 0.005 * s["final_value"])).all()), ""),
        ("Patrimoine net ≤ valeur après vente ≤ valeur quotidienne finale",
         bool(((s["terminal_net"] <= s["value_after_sale"]) & (s["value_after_sale"] <= s["final_value"])).all()), ""),
    ]
    return pd.DataFrame(rows, columns=["Contrôle", "Conforme", "Détail"])


def all_ok(lab) -> bool:
    return bool(reproduction(lab)["Conforme"].all() and accounting(lab)["Conforme"].all())
