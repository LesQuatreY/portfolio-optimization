"""French summary tables of Portfolio Lab V2 (pandas Styler; values come from ``StrategyLab``)."""
from __future__ import annotations

from typing import Sequence

import pandas as pd

from . import checks
from . import formatting as F
from .bridge import PROVENANCE_FR
from .charts import FONT, MUTED, TEXT2, style

STYLES = [{"selector": "", "props": "margin-left:0;border-collapse:collapse"},
          {"selector": "caption", "props": f"caption-side:bottom;text-align:left;font-size:11.5px;color:{TEXT2};padding:6px 0 0"},
          {"selector": "th", "props": f"font-family:{FONT};font-size:12px;font-weight:600;text-align:left;background:#f4f4f1;"
                                      "border-bottom:1px solid #d6d5ce;padding:5px 9px;white-space:nowrap"},
          {"selector": "td", "props": f"font-family:{FONT};font-size:12.5px;padding:4px 9px;border-bottom:1px solid #ecebe6;"
                                      "text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap"}]


def swatch(lab, sid: str) -> str:
    st = style(lab, sid)
    if st["benchmark"]:
        border = "dashed" if st["dash"] == "dash" else "dotted"
        mark = f'<span style="display:inline-block;width:16px;border-top:2.5px {border} {st["color"]};vertical-align:middle"></span>'
    else:
        mark = f'<span style="display:inline-block;width:11px;height:11px;border-radius:3px;background:{st["color"]};vertical-align:-1px"></span>'
    return f'{mark}&nbsp;<b>{sid}</b>'


def _status(lab, sid: str) -> str:
    meta = lab.meta.loc[sid]
    if meta["data_status"] == "Observé":
        return "Observé"
    return f"{meta['data_status']} ({F.pct(meta['reconstructed_share'], 0)})"


def _style(table: pd.DataFrame, lab, ids: Sequence[str], caption: str, left: int = 3):
    benchmarks = set(lab.benchmarks)
    styles = STYLES + [{"selector": ", ".join(f"td.col{i}" for i in range(left)), "props": "text-align:left"}]
    return (table.style.hide(axis="index")
            .apply(lambda r: ["background-color:#f7f7f4" if ids[r.name] in benchmarks else "" for _ in r], axis=1)
            .set_table_styles(styles).set_caption(caption))


def kpi_table(lab, ids: Sequence[str]):
    ids = lab.ordered(ids)
    if not ids:
        return "Sélectionnez au moins un portefeuille."
    s = lab.summary.loc[ids]
    table = pd.DataFrame({
        "Portefeuille": [swatch(lab, i) for i in ids],
        "CAGR net ¹": [F.pct(v) for v in s["cagr_net"]],
        "Volatilité ²": [F.pct(v) for v in s["volatility"]],
        "MaxDD journalier ²": [F.pct(v) for v in s["max_drawdown"]],
        "Sharpe ²": [F.ratio(v) for v in s["sharpe"]],
        "Patrimoine net ¹": [F.eur(v) for v in s["terminal_net"]],
        "Données": [_status(lab, i) for i in ids],
    }).reset_index(drop=True)
    start, end = lab.period
    return (_style(table, lab, ids,
                   f"¹ 100 000 € investis le {F.date(start)}, liquidés le {F.date(end)} : après frais, impôts payés en cours "
                   "de route, frais de vente finale et impôts de sortie. ² Valeur quotidienne après frais et impôts déjà "
                   "payés, sans impôt de sortie latent ; Sharpe contre le taux €STR/EONIA. Proxy : part moyenne du "
                   "portefeuille dont l'historique est reconstitué. Références sur fond gris ; descriptions dans les fiches.", left=1))


def detail_table(lab, ids: Sequence[str]):
    ids = lab.ordered(ids)
    if not ids:
        return "Sélectionnez au moins un portefeuille."
    s = lab.summary.loc[ids]
    table = pd.DataFrame({
        "Portefeuille": [swatch(lab, i) for i in ids],
        "CAGR brut": [F.pct(v) for v in s["cagr_gross"]],
        "CAGR après frais (sans impôts)": [F.pct(v) for v in s["cagr_after_costs"]],
        "CAGR trajectoire quotidienne": [F.pct(v) for v in s["cagr_path"]],
        "CAGR net": [F.pct(v) for v in s["cagr_net"]],
        "Rendement arithmétique": [F.pct(v) for v in s["arith_return"]],
        "Patrimoine brut": [F.eur(v) for v in s["terminal_gross"]],
        "Valeur quotidienne finale": [F.eur(v) for v in s["final_value"]],
        "Patrimoine net": [F.eur(v) for v in s["terminal_net"]],
        "Frais totaux": [F.eur(v) for v in s["fees_total"]],
        "Impôts en cours de route": [F.eur(v) for v in s["interim_taxes"]],
        "Impôts de sortie": [F.eur(v) for v in s["exit_taxes"]],
        "Ordres": [f"{int(v)}" for v in s["orders"]],
        "Exposition Nasdaq moy. / max": [f"{F.times(a)} / {F.times(b)}" for a, b in zip(s["ndx_expo_mean"], s["ndx_expo_max"])],
    }).reset_index(drop=True)
    return _style(table, lab, ids,
                  "Brut : simulation séparée sans frais ni impôts. Après frais : simulation séparée avec frais, sans aucun "
                  "impôt. Trajectoire quotidienne : fin de la courbe (frais et impôts payés inclus, avant vente finale). "
                  "Net : après vente finale et impôts de sortie. Exposition : (PUST + 2 × LQQ) ÷ patrimoine.", left=1)


def recovery_table(lab, ids: Sequence[str]):
    ids = lab.ordered(ids)
    if not ids:
        return "Sélectionnez au moins un portefeuille."
    s = lab.summary.loc[ids]
    covid = lab.crises.loc[ids, "covid_recovery_sessions"]
    table = pd.DataFrame({
        "Portefeuille": [swatch(lab, i) for i in ids],
        "MaxDD journalier": [F.pct(v) for v in s["max_drawdown"]],
        "Sommet précédent": [F.date(v) if v is not None else "départ" for v in s["maxdd_peak_date"]],
        "Creux": [F.date(v) for v in s["maxdd_trough_date"]],
        "Retour au sommet": [F.date(v) if pd.notna(v) else "non atteint au 29 déc. 2023" for v in s["maxdd_recovery_date"]],
        "Durée creux → retour": [F.sessions(v) for v in s["maxdd_recovery_sessions"]],
        "Plus longue période sous un sommet": [F.sessions(v) for v in s["longest_underwater_sessions"]],
        "Récupération Covid": [F.sessions(v) for v in covid],
        "Pire 12 mois": [F.pct(v) for v in s["worst_12m"]],
    }).reset_index(drop=True)
    return _style(table, lab, ids,
                  "Sommets mesurés sur la valeur quotidienne, le capital initial comptant comme premier sommet "
                  "(convention Research). Une séance ≈ un jour de bourse ; 21 séances ≈ 1 mois.", left=1)


def statistics_table(lab, ids: Sequence[str]):
    ids = lab.ordered(ids)
    if not ids:
        return "Sélectionnez au moins un portefeuille."
    c = lab.chrono.loc[ids]
    table = pd.DataFrame({
        "Portefeuille": [swatch(lab, i) for i in ids],
        "CAGR 3 ans glissant min / méd. / max": [f"{F.pct(a)} / {F.pct(b)} / {F.pct(d)}" for a, b, d in zip(c["r3_min"], c["r3_med"], c["r3_max"])],
        "CAGR 5 ans min / max": [f"{F.pct(a)} / {F.pct(b)}" for a, b in zip(c["r5_min"], c["r5_max"])],
        "Sharpe 3 ans min / max": [f"{F.ratio(a)} / {F.ratio(b)}" for a, b in zip(c["sh3_min"], c["sh3_max"])],
        "Volatilité 1 an min / max": [f"{F.pct(a)} / {F.pct(b)}" for a, b in zip(c["vol1_min"], c["vol1_max"])],
        "Pire année": [f"{F.pct(a)} ({b})" for a, b in zip(c["worst_year"], c["worst_year_label"])],
        "Meilleure année": [F.pct(v) for v in c["best_year"]],
        "Années devant B1M (sur 9)": [f"{int(v)}" for v in c["years_beat_B1M"]],
        "Fenêtres 3 ans ≥ B1M": [F.pct(v, 0) for v in c["share3y_ge_B1M"]],
        "Statut Research V11.2": [lab.meta.loc[i, "classification"] for i in ids],
    }).reset_index(drop=True)
    return _style(table, lab, ids,
                  "Statistiques existantes de Research V11.2 (chronological_summary.csv, classification.csv), affichées "
                  "telles quelles : aucune nouvelle conclusion ni nouveau classement n'est calculé ici.", left=1)


def provenance_table(lab, ids: Sequence[str]):
    ids = lab.ordered(ids)
    if not ids:
        return "Sélectionnez au moins un portefeuille."
    lines = lab.lines
    rows = []
    for sid in ids:
        meta = lab.meta.loc[sid]
        rec = [f"{lines.loc[c, 'label']} ({PROVENANCE_FR[lines.loc[c, 'provenance']].lower()})"
               for c in meta["reconstructed_lines"]]
        rows.append({"Portefeuille": swatch(lab, sid), "Données": meta["data_status"],
                     "Part reconstituée (moyenne)": F.pct(meta["reconstructed_share"], 1),
                     "Lignes reconstituées": " · ".join(rec) if rec else "aucune",
                     "Comptes": meta["accounts"]})
    table = pd.DataFrame(rows)
    return _style(table, lab, ids, "Détermination automatique à partir des lignes réellement détenues dans les courbes "
                  "gelées (une ligne jamais détenue ne compte pas). Sources détaillées : tableau suivant.", left=5)


def sources_table(lab):
    lines = lab.lines
    used = [c for c in lines.index if lab.holdings[c].any()]
    table = pd.DataFrame({"Ligne": [lines.loc[c, "label"] for c in used],
                          "Enveloppe": [lines.loc[c, "wrapper"] for c in used],
                          "ISIN": [lines.loc[c, "isin"] or "—" for c in used],
                          "Provenance": [PROVENANCE_FR[lines.loc[c, "provenance"]] for c in used],
                          "Série utilisée 2014–2023": [lines.loc[c, "source"] for c in used]})
    styles = STYLES + [{"selector": "td", "props": "text-align:left;white-space:normal"},
                       {"selector": "td.col4", "props": "min-width:420px"}]
    return table.style.hide(axis="index").set_table_styles(styles).set_caption(
        "Source : config/v2/instruments.yaml, établi d'après les définitions de séries de Portfolio Research.")


def reproduction_table(lab):
    rep = checks.reproduction(lab)
    summary = rep.groupby("Indicateur", sort=False).agg(Portefeuilles=("Portefeuille", "count"),
                                                        Conformes=("Conforme", "sum"), Écart_max=("Écart", "max"))
    summary["Écart_max"] = [f"{v:.1e}" for v in summary["Écart_max"]]
    summary = summary.rename(columns={"Écart_max": "Écart maximal"}).reset_index()
    styles = STYLES + [{"selector": "td.col0", "props": "text-align:left"}]
    return summary.style.hide(axis="index").set_table_styles(styles).set_caption(
        f"Recalcul depuis les courbes quotidiennes gelées avec les formules de Research ; tolérance {checks.METRIC_TOL:.0e}.")


def accounting_table(lab):
    acc = checks.accounting(lab).copy()
    acc["Conforme"] = ["✓ conforme" if v else "✗ ÉCHEC" for v in acc["Conforme"]]
    styles = STYLES + [{"selector": "td", "props": "text-align:left"}]
    return acc.style.hide(axis="index").set_table_styles(styles)


def guard_table(lab):
    styles = STYLES + [{"selector": "td", "props": "text-align:left"}]
    return lab.guard_report.style.hide(axis="index").set_table_styles(styles).set_caption(
        "Chaque fichier lu dans Portfolio Research est vérifié avant lecture : liste d'autorisation, empreinte SHA-256 "
        "de la version gelée, aucune date après le 29/12/2023.")


def config_table(lab, sid: str):
    meta = lab.meta.loc[sid]
    rows = [("Composition (manifeste gelé)", meta["composition"]), ("Politique", meta["policy"]),
            ("Rééquilibrage", meta["rebalancing"]), ("Comptes", meta["accounts"]),
            ("Version et moteur Research", f"{meta['source_version']} — {meta['engine']}"),
            ("Empreinte de configuration", f"{meta['config_sha256'][:16]}… (revérifiée au chargement)"),
            ("Période, devise, capital", f"{meta['period']} · {meta['currency']} · {F.eur(meta['initial_capital'])}"),
            ("Données", _status(lab, sid))]
    table = pd.DataFrame(rows, columns=["Élément", "Valeur"])
    styles = STYLES + [{"selector": "td", "props": "text-align:left;white-space:normal"},
                       {"selector": "th", "props": f"color:{MUTED}"}]
    return table.style.hide(axis="index").set_table_styles(styles)
