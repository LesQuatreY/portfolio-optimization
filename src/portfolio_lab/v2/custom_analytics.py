"""Reusable economic analytics; no personalized tax model or fetching."""
from __future__ import annotations

from dataclasses import replace
import html
from types import SimpleNamespace
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import charts, metrics as M
from .custom import (ROOT, BacktestResult, DataUnavailable, MODES, PortfolioSpec, load_catalog,
                     load_validated_panel, simulate)

ASSET_COLORS = {"EM": "#1baf7a", "SP500": "#2a78d6", "WORLD": "#5598e7", "CAC40": "#6250d6",
                "GOLD": "#eda100", "BTC": "#eb6834"}


def risk(total, initial, annual_rf=0.0, rate=None):
    """Economic path metrics. ``rate`` (annual EUR overnight series, ACT/360) gives the Sharpe on
    Research's cash convention; otherwise the explicit constant ``annual_rf`` is used."""
    ret = M.path_returns(total, initial)
    # RF = explicit constant, ACT/360; frozen Sharpe is retained separately, never relabelled.
    rf = pd.Series(float(annual_rf), index=total.index) if rate is None else rate.reindex(total.index)
    if rf.isna().any():
        raise DataUnavailable("Taux sans risque manquant sur le calendrier de comparaison.")
    excess = ret.to_numpy() - M.daily_risk_free(total.index, rf)
    std = excess.std(ddof=1) if len(excess) > 1 else np.nan
    metrics = {"CAGR économique": M.cagr(float(total.iloc[-1]), initial, M.years(total.index)),
               "Volatilité": float(ret.std(ddof=1) * np.sqrt(252)),
               "MaxDD": float(-M.drawdown(total, initial).min()),
               "Rendement arithmétique": float(ret.mean() * 252),
               "Sharpe (taux 0 %)": float(excess.mean() / std * np.sqrt(252)) if std > 1e-15 else np.nan,
               "Valeur finale économique (€)": float(total.iloc[-1])}
    if rate is not None:
        metrics["Sharpe (taux EUR Research)"] = metrics.pop("Sharpe (taux 0 %)")
    elif annual_rf != 0:
        metrics[f"Sharpe (taux {annual_rf:.2%})"] = metrics.pop("Sharpe (taux 0 %)")
    return metrics


def summary(result):
    row = risk(result.ledger.nav, result.spec.initial_capital)
    row.update({"CAGR net fiscal": "Non calculé", "Frais de transaction (€)": result.ledger.cost.sum(),
                "Rotation cumulée (deux côtés)": result.ledger.turnover.sum(),
                "Nature": "SYNTHÉTIQUE — validation logicielle" if result.synthetic else "Simulation historique personnalisée"})
    return pd.DataFrame([row], index=[result.spec.name])


def rolling(total):
    """Trailing calendar years; only a past observation at/before the anniversary is used."""
    out = pd.DataFrame(index=total.index)
    for years in (3, 5):
        values = []
        for date in total.index:
            anchor = date - pd.DateOffset(years=years)
            pos = total.index.searchsorted(anchor, side="right") - 1
            if pos < 0:
                values.append(np.nan)
            else:
                elapsed = (date - total.index[pos]).days / 365.25
                values.append((total.loc[date] / total.iloc[pos]) ** (1 / elapsed) - 1)
        out[f"{years} ans"] = values
    return out


def annual_returns(result):
    ret = M.path_returns(result.ledger.nav, result.spec.initial_capital)
    out = (1 + ret).groupby(ret.index.year).prod() - 1
    out.index = [str(y) + (" (partiel)" if (
        (y == ret.index[0].year and ret.index[0].month != 1) or
        (y == ret.index[-1].year and ret.index[-1].month != 12)) else "") for y in out.index]
    return out.rename("Rendement")


WINDOWS = {"2014–2018": ("2014-10-01", "2018-12-31"), "2019–2023": ("2019-01-01", "2023-12-29"),
           "T4 2018": ("2018-10-01", "2018-12-31"), "COVID 2020": ("2020-02-19", "2020-03-23"),
           "Baisse 2022": ("2022-01-01", "2022-12-30")}


def stability(result):
    total = result.ledger.nav
    rows, correlations = [], {}
    for label, (start, end) in WINDOWS.items():
        block = total.loc[start:end]
        if len(block) < 2:
            continue
        pos = total.index.get_loc(block.index[0])
        initial = result.spec.initial_capital if pos == 0 else float(total.iloc[pos - 1])
        row = risk(block, initial)
        episode = M.recovery(block, initial)
        trough = episode["maxdd_trough_date"]
        # Recovery may occur after the crisis window; only authorized later dates are examined.
        peak = max(initial, float(block.loc[:trough].max()))
        after = total.loc[trough:]
        recovered = after[after >= peak - 1e-9]
        row.update({"Fenêtre": label, "Début observé": str(block.index[0].date()),
                    "Fin observée": str(block.index[-1].date()),
                    "Rendement période": float(block.iloc[-1] / initial - 1),
                    "Récupération": recovered.index[0].date().isoformat() if len(recovered) else "Non récupéré",
                    "Séances depuis creux": total.index.get_loc(recovered.index[0]) - total.index.get_loc(trough)
                    if len(recovered) else np.nan})
        rows.append(row)
        returns = result.prices.pct_change(fill_method=None).loc[start:end].dropna()
        if len(returns) >= 20:
            correlations[label] = returns.corr()
    return pd.DataFrame(rows), correlations


def sensitivities(spec, panel):
    """Exactly three predeclared modes. Never selects a winner or optimizes weights."""
    return {mode: simulate(replace(spec, rebalance=mode), panel) for mode in MODES}


def common_calendar(lab, index):
    """Research paths SAMPLED on the custom valuation calendar: values are never changed, removed
    Research dates are listed (V2.2: 25/12/2019, a vendor placeholder on a Euronext holiday).
    The returns of removed dates are carried by the next common date."""
    index = pd.DatetimeIndex(index)
    missing = index.difference(lab.wealth.index)
    if len(missing):
        raise DataUnavailable(f"Dates du portefeuille absentes des courbes Research, ex. {missing[0].date()}.")
    return SimpleNamespace(ordered=lab.ordered, initial=lab.initial, wealth=lab.wealth.loc[index],
                           reference=lab.reference, summary=getattr(lab, "summary", None), meta=lab.meta,
                           strategies=lab.strategies, benchmarks=lab.benchmarks,
                           eur_rate=lab.eur_rate.reindex(index) if getattr(lab, "eur_rate", None) is not None else None,
                           dropped_dates=[str(d.date()) for d in lab.wealth.index.difference(index)])


def comparability_table():
    """Which numbers may be compared between a custom path and the frozen Research results."""
    rows = [
        ("Volatilité, MaxDD, Sharpe (taux EUR Research)", "Oui, avec réserve",
         "Mêmes séances et même taux ; Research inclut ses frais et impôts intermédiaires dans la trajectoire"),
        ("CAGR économique personnalisé vs CAGR brut Research", "Approximativement",
         "Tous deux sans frais de transaction ni fiscalité ; frais des fonds et coût du levier inclus ; "
         "le brut Research vient d'une simulation séparée"),
        ("CAGR de trajectoire Research", "Avec réserve",
         "Après frais et impôts intermédiaires Research, avant impôts de sortie"),
        ("CAGR net fiscal / patrimoine net", "Non",
         "Research : modèle fiscal gelé ; personnalisé : Non calculé (aucun modèle fiscal approuvé)"),
        ("Sharpe au taux 0 %", "Non avec Research",
         "Convention de taux différente du Sharpe canonique Research"),
    ]
    return pd.DataFrame(rows, columns=["Mesure", "Comparable ?", "Raison"]).set_index("Mesure")


BENCHMARKS_PATH = ROOT / "config/v2/custom_benchmarks.yaml"
EXTERNAL_COLORS = {"BRK_B": "#0f766e"}


def benchmark_catalog():
    return load_catalog(BENCHMARKS_PATH)


def benchmark_result(name, catalog=None):
    """Buy & hold of one validated external benchmark (100 % of the capital, explicit cost from the
    catalog). Fails closed through the same guarded loader as custom portfolios."""
    catalog = benchmark_catalog() if catalog is None else catalog
    if name not in catalog:
        raise DataUnavailable(f"Référence externe inconnue : {name}.")
    item = catalog[name]
    spec = PortfolioSpec(item["label"], {name: 1.0}, rebalance="buy_hold", cost_bps=float(item.get("cost_bps", 0)))
    return simulate(spec, load_validated_panel(spec, catalog))


def _external_row(bench):
    item = next(iter(bench.provenance.values()), {})
    return {"Base": f"Achat-conservation économique, frais explicites {bench.spec.cost_bps:g} pb, sans fiscalité ; "
                    + str(item.get("kind", "référence externe")),
            "CAGR brut Research (sans frais ni impôts)": "—", "CAGR net fiscal": "Non calculé",
            "Patrimoine net fiscal (€)": "Non calculé"}


def comparison(result, lab, ids, extra=()):
    """``extra``: validated external benchmark results (e.g. BRK.B) on the SAME calendar."""
    if result.synthetic:
        raise DataUnavailable("Une démonstration synthétique ne se compare pas aux performances Research.")
    ids = lab.ordered(ids)
    if not result.ledger.index.equals(lab.wealth.index):
        raise DataUnavailable("Comparaison refusée : les calendriers et bornes doivent être identiques.")
    if not all(p.get("research_alignment") == "validated_paris_session_end" for p in result.provenance.values()):
        raise DataUnavailable("L'alignement temporel avec les séances Research doit être validé indépendamment.")
    # Paths have different accounting bases, so show the distinction on every row.
    custom_label = result.spec.name + " · personnalisé " + result.spec.identity[:8]
    curves = pd.DataFrame({custom_label: result.ledger.nav / result.spec.initial_capital})
    rate = getattr(lab, "eur_rate", None)
    summary = getattr(lab, "summary", None)

    def sharpe_eur(total, initial):
        return risk(total, initial, rate=rate)["Sharpe (taux EUR Research)"] if rate is not None else np.nan

    rows = []
    row = risk(result.ledger.nav, result.spec.initial_capital)
    row.update({"Portefeuille": custom_label, "Base": "Économique, frais proportionnels, sans fiscalité",
                "Sharpe (taux EUR Research)": sharpe_eur(result.ledger.nav, result.spec.initial_capital),
                "CAGR brut Research (sans frais ni impôts)": "—",
                "CAGR net fiscal": "Non calculé", "Patrimoine net fiscal (€)": "Non calculé"})
    rows.append(row)
    for sid in ids:
        curves[sid] = lab.wealth[sid] / lab.initial
        row = risk(lab.wealth[sid], lab.initial)
        ref = lab.reference.loc[sid]
        row.update({"Portefeuille": sid, "Base": "Research gelé : frais et impôts intermédiaires inclus",
                    "Sharpe (taux EUR Research)": sharpe_eur(lab.wealth[sid], lab.initial),
                    "CAGR brut Research (sans frais ni impôts)":
                        float(summary.loc[sid, "cagr_gross"]) if summary is not None else "—",
                    "CAGR net fiscal": ref["FULL_cagr"], "Patrimoine net fiscal (€)": ref["terminal_net"]})
        rows.append(row)
    for bench in extra:
        if bench.synthetic or not bench.ledger.index.equals(result.ledger.index):
            raise DataUnavailable("Référence externe : calendrier différent ou données synthétiques.")
        name = next(iter(bench.spec.weights))
        label = bench.spec.name
        curves[label] = bench.ledger.nav / bench.spec.initial_capital
        row = risk(bench.ledger.nav, bench.spec.initial_capital)
        row.update({"Portefeuille": label, "Sharpe (taux EUR Research)": sharpe_eur(bench.ledger.nav, bench.spec.initial_capital),
                    **_external_row(bench)})
        rows.append(row)
        EXTERNAL_COLORS.setdefault(label, EXTERNAL_COLORS.get(name, "#0f766e"))
    return curves, pd.DataFrame(rows).set_index("Portefeuille")


def _figure(title, result, ytitle="", time=True):
    charts.setup()
    fig = go.Figure()
    subtitle = "SYNTHÉTIQUE — validation du logiciel, aucune performance historique" if result.synthetic else (
        "Économique après frais proportionnels ; fiscalité et liquidation non simulées")
    if result.synthetic:
        title = "Validation synthétique — " + title
    charts._layout(fig, title, subtitle, 490)
    fig.update_yaxes(title=ytitle)
    if time:
        fig.update_xaxes(range=[result.prices.index[0], result.prices.index[-1]])
    return fig


def figures(result):
    """Stable custom colour, reused V2 theme. Separate figures avoid crowded chart grids."""
    color = "#8a46ba"
    name = html.escape(result.spec.name)
    nav = result.ledger.nav
    outputs = {}
    for key, title, series, ylabel in (
        ("wealth", "Patrimoine économique", nav, "EUR"),
        ("drawdown", "Baisse depuis le sommet", M.drawdown(nav, result.spec.initial_capital), "Drawdown")):
        f = _figure(title, result, ylabel)
        f.add_scatter(x=series.index, y=series, name=name, line=dict(color=color))
        if key == "drawdown":
            f.update_yaxes(tickformat=".0%")
        outputs[key] = f
    f = _figure("Performances glissantes — années calendaires", result, "CAGR")
    for label, series in rolling(nav).items():
        f.add_scatter(x=series.index, y=series, name=label)
    f.update_yaxes(tickformat=".0%")
    outputs["rolling"] = f
    f = _figure("Allocations historiques", result, "Poids")
    for asset, series in result.weights.items():
        f.add_scatter(x=series.index, y=series, name=asset, stackgroup="allocation",
                      line=dict(color=ASSET_COLORS.get(asset, "#898781")))
    f.add_scatter(x=nav.index, y=result.ledger.cash / nav, name="Liquidités", stackgroup="allocation")
    f.update_yaxes(tickformat=".0%", range=[0, 1.02])
    outputs["allocation"] = f
    f = _figure("Rendements annuels", result, "Rendement", time=False)
    annual = annual_returns(result)
    f.add_bar(x=annual.index, y=annual, name=name, marker_color=color)
    f.update_yaxes(tickformat=".0%")
    outputs["annual"] = f
    f = _figure("Frais de transaction cumulés", result, "EUR")
    f.add_scatter(x=nav.index, y=result.ledger.cost.cumsum(), name="Frais cumulés", line=dict(color=color))
    outputs["costs"] = f
    f = _figure("Rotation du portefeuille — achats + ventes", result, "Notionnel / valeur avant ordres")
    f.add_bar(x=nav.index, y=result.ledger.turnover, name="Rotation, achat initial inclus", marker_color=color)
    f.update_yaxes(tickformat=".0%")
    outputs["turnover"] = f
    return outputs


def _color(lab, sid, custom_label):
    if sid == custom_label:
        return "#8a46ba"
    if sid in EXTERNAL_COLORS:
        return EXTERNAL_COLORS[sid]
    return charts.style(lab, sid)["color"]


def comparison_figures(result, lab, ids, extra=()):
    curves, table = comparison(result, lab, ids, extra)
    custom_label = curves.columns[0]
    outputs = {}
    for key, title in (("wealth", "Comparaison des trajectoires — bases comptables distinctes"),
                       ("drawdown", "Comparaison des drawdowns — bases comptables distinctes")):
        fig = _figure(title, result, "Base 1" if key == "wealth" else "Drawdown")
        for sid in curves:
            series = curves[sid] if key == "wealth" else M.drawdown(curves[sid], 1)
            color = _color(lab, sid, custom_label)
            fig.add_scatter(x=series.index, y=series, name=html.escape(sid), line=dict(color=color),
                            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.4f}<extra>%{fullData.name}</extra>")
        if key == "drawdown":
            fig.update_yaxes(tickformat=".0%")
        outputs[key] = fig
    fig = _figure("CAGR des trajectoires — aucune frontière fiscale commune", result, "CAGR", time=False)
    for name, row in table.iterrows():
        color = _color(lab, name, custom_label)
        fig.add_scatter(x=[row["Volatilité"]], y=[row["CAGR économique"]], mode="markers", name=html.escape(name),
                        marker=dict(color=color, size=12), customdata=[[row["MaxDD"], row["Base"]]],
                        hovertemplate="%{y:.2%}<br>%{customdata[1]}<extra>%{fullData.name}</extra>")
    # Keep same trace identity, toggle only the x coordinate.
    fig.update_layout(updatemenus=[dict(type="buttons", direction="right", y=1.15,
        buttons=[dict(label=label, method="update", args=[{"x": [[v] for v in table[column]]},
                                                        {"xaxis.title.text": label}])
                 for label, column in (("Volatilité", "Volatilité"), ("MaxDD", "MaxDD"))])])
    fig.update_xaxes(title="Volatilité", tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    outputs["risk"] = fig
    return outputs, table
