"""Interactive Plotly charts for the research notebooks (user-facing text in French).

Presentation only: every chart consumes results computed elsewhere and never recomputes
financial quantities beyond simple transformations (drawdown from a NAV, cumulative
products). One visual system for all charts:

* fixed categorical order, colour follows the entity (asset or strategy), never its rank;
* benchmarks are neutral greys with dashed/dotted lines, so they never look like a policy;
* titles state whether a chart is IN-SAMPLE (fitted) or OUT-OF-SAMPLE (realized);
* percentages everywhere, French hover labels.
"""
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .protocol import assert_dates_before_holdout, assert_file_safe

# Validated categorical order (dataviz reference palette, light mode).
PALETTE = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
# Reference (non-policy) series: neutral greys, distinct dashes, never a policy colour.
NEUTRAL = {"Constrained Equal Weight": ("#2b2b2b", "dashdot"), "Equal Weight": ("#8a8984", "dash"),
           "benchmark": ("#6b6a66", "dot")}


def _is_reference(name: str, benchmark: str | None) -> bool:
    return name in ("Constrained Equal Weight", "Equal Weight") or (benchmark is not None and name == benchmark)


def _reference_color(name: str) -> str:
    return NEUTRAL[name][0] if name in NEUTRAL else NEUTRAL["benchmark"][0]
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
FONT = "Inter, Segoe UI, Helvetica, Arial, sans-serif"

LABELS = {
    "Maximum Sharpe": "Sharpe maximal", "Minimum Volatility": "Volatilité minimale",
    "Maximum CAGR": "CAGR maximal", "Equal Weight": "Équipondéré non contraint (descriptif)",
    "Constrained Equal Weight": "Équipondéré contraint (investissable)",
    "Equal Risk Contribution": "Contribution au risque égale (ERC)",
    "CAGR": "CAGR", "Volatility annualized": "Volatilité annualisée", "Volatility": "Volatilité annualisée",
    "Estimated volatility": "Volatilité estimée (ex ante)", "Sharpe": "Ratio de Sharpe",
    "Max Drawdown": "Perte maximale (drawdown)", "Calmar": "Ratio de Calmar",
    "Mean return annualized": "Rendement arithmétique annualisé", "Estimated return": "Rendement espéré estimé",
    "CAGR excluding best year": "CAGR hors meilleure année", "Best year": "Meilleure année",
    "Worst year return": "Pire rendement annuel", "Gross CAGR (before costs)": "CAGR brut (avant coûts)",
    "Mean traded turnover": "Rotation annuelle moyenne", "Gold": "Or", "Emerging Markets": "Marchés émergents",
}


def fr(name: str) -> str:
    """French display label (leveraged suffixes are kept: 'Nasdaq 100 x2' -> 'Nasdaq 100 ×2')."""
    name = str(name)
    if name in LABELS:
        return LABELS[name]
    if " x" in name:
        base, factor = name.rsplit(" x", 1)
        return f"{LABELS.get(base, base)} ×{factor}"
    return name


def colors_for(names: Sequence[str], order: Sequence[str] | None = None) -> dict[str, str]:
    """Stable colour per entity: position in `order` (defaults to `names`), never re-ranked."""
    order = list(order or names)
    extra = [n for n in names if n not in order]
    order += extra
    return {name: PALETTE[order.index(name) % len(PALETTE)] for name in names}


def _layout(fig: go.Figure, title: str, subtitle: str | None = None, height: int = 520) -> go.Figure:
    text = f"<b>{title}</b>" + (f"<br><span style='font-size:12px;color:{MUTED}'>{subtitle}</span>"
                               if subtitle else "")
    fig.update_layout(
        template="plotly_white", height=height, title=dict(text=text, x=0.01, xanchor="left"),
        font=dict(family=FONT, size=13, color=TEXT), hoverlabel=dict(font_family=FONT),
        legend=dict(orientation="h", yanchor="top", y=-0.14, x=0, title_text=""),
        margin=dict(l=70, r=30, t=90 if subtitle else 70, b=90), plot_bgcolor="white")
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def _line_style(name: str, benchmark: str | None, color: str) -> dict:
    if name in ("Constrained Equal Weight", "Equal Weight"):
        return dict(color=NEUTRAL[name][0], width=2, dash=NEUTRAL[name][1])
    if benchmark is not None and name == benchmark:
        return dict(color=NEUTRAL["benchmark"][0], width=2, dash=NEUTRAL["benchmark"][1])
    return dict(color=color, width=2)


def frontier_chart(stats: pd.DataFrame, optimization, *, investor=None, band: pd.DataFrame | None = None,
                   period: str = "", asset_order: Sequence[str] | None = None,
                   extra_frontiers: dict | None = None, extra_points: dict | None = None) -> go.Figure:
    """In-sample frontier: maximum historical growth for each estimated-volatility ceiling.

    `extra_frontiers` {label: OptimizationResults} overlays other estimation methods (dashed);
    `extra_points` {label: metrics dict} adds single portfolios (e.g. equal risk contribution).
    """
    fig = go.Figure()
    if band is not None and len(band):
        level = band["Level"].iloc[0]
        fig.add_trace(go.Scatter(x=list(band.index) + list(band.index[::-1]),
                                 y=list(band["Upper"]) + list(band["Lower"][::-1]), fill="toself",
                                 fillcolor="rgba(42,120,214,0.12)", line=dict(width=0), hoverinfo="skip",
                                 name=f"Incertitude bootstrap ({level:.0%})"))
    curve = optimization.frontier.drop_duplicates(subset=["Volatility", "CAGR"])
    fig.add_trace(go.Scatter(x=curve["Volatility"], y=curve["CAGR"], mode="lines", name="Frontière estimée",
                             line=dict(color=TEXT, width=2),
                             hovertemplate="Volatilité %{x:.1%}<br>CAGR %{y:.1%}<extra>Frontière</extra>"))
    names = list(stats.index)
    palette = colors_for(names, asset_order)
    for name, row in stats.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["Volatility annualized"]], y=[row["CAGR"]], mode="markers+text", text=[fr(name)],
            textposition="top center", textfont=dict(size=11, color=MUTED), showlegend=False,
            marker=dict(size=10, color=palette[name], line=dict(color="white", width=2)),
            hovertemplate=(f"<b>{fr(name)}</b> (100 %)<br>Volatilité %{{x:.1%}}<br>CAGR %{{y:.1%}}"
                           f"<br>Perte max {row['Max Drawdown']:.1%}<extra></extra>")))
    for name, point in optimization.portfolios.items():
        if point["weights"] is None:
            continue
        top = point["weights"].sort_values(ascending=False)
        mix = "<br>".join(f"{fr(a)} {w:.0%}" for a, w in top.items() if w >= .01)
        fig.add_trace(go.Scatter(
            x=[point["Volatility"]], y=[point["CAGR"]], mode="markers", name=fr(name),
            marker=dict(size=13, symbol="diamond", color="white", line=dict(color=TEXT, width=2)),
            hovertemplate=(f"<b>{fr(name)}</b><br>Volatilité %{{x:.1%}}<br>CAGR %{{y:.1%}}<br>"
                           f"Perte max {point['Max Drawdown']:.1%}<br>{mix}<extra></extra>")))
    for i, (label, other) in enumerate((extra_frontiers or {}).items()):
        curve_other = other.frontier.drop_duplicates(subset=["Volatility", "CAGR"])
        fig.add_trace(go.Scatter(x=curve_other["Volatility"], y=curve_other["CAGR"], mode="lines", name=label,
                                 line=dict(color=PALETTE[(i + 6) % len(PALETTE)], width=2, dash="dash"),
                                 hovertemplate=f"<b>{label}</b><br>Volatilité %{{x:.1%}}<br>CAGR %{{y:.1%}}<extra></extra>"))
    for i, (label, point) in enumerate((extra_points or {}).items()):
        top = point["weights"].sort_values(ascending=False)
        mix = "<br>".join(f"{fr(a)} {w:.0%}" for a, w in top.items() if w >= .01)
        fig.add_trace(go.Scatter(x=[point["Volatility"]], y=[point["CAGR"]], mode="markers", name=label,
                                 marker=dict(size=13, symbol="star", color=PALETTE[(i + 5) % len(PALETTE)],
                                             line=dict(color="white", width=1)),
                                 hovertemplate=(f"<b>{label}</b><br>Volatilité %{{x:.1%}}<br>CAGR %{{y:.1%}}<br>"
                                                f"{mix}<extra></extra>")))
    if investor is not None:
        reference = investor.unconstrained.frontier.drop_duplicates(subset=["Volatility", "CAGR"])
        fig.add_trace(go.Scatter(x=reference["Volatility"], y=reference["CAGR"], mode="lines",
                                 name="Frontière sans contraintes investisseur", line=dict(color=MUTED, dash="dash"),
                                 hovertemplate="Volatilité %{x:.1%}<br>CAGR %{y:.1%}<extra></extra>"))
    fig.update_xaxes(title="Volatilité annualisée réalisée (EUR, modèle à poids constants)", tickformat=".0%")
    fig.update_yaxes(title="CAGR historique réalisé (EUR, modèle à poids constants)", tickformat=".0%")
    return _layout(fig, f"Frontière efficiente estimée — IN-SAMPLE {period}".strip(),
                   "Modèle de l'optimiseur : poids remis à la cible à chaque séance, sans coûts. Ajustée et mesurée "
                   "sur les mêmes données : ni un CAGR espéré, ni une performance future.", 620)


def allocation_chart(weights: pd.DataFrame, *, title: str, subtitle: str | None = None,
                     asset_order: Sequence[str] | None = None, threshold: float = 0.) -> go.Figure:
    """Horizontal 100% stacked bars: one row per portfolio, one segment per asset."""
    weights = weights.dropna(how="all")
    assets = [c for c in weights.columns if (weights[c].fillna(0) > threshold).any()]
    palette = colors_for(list(weights.columns), asset_order)
    fig = go.Figure()
    rows = [fr(i) for i in weights.index][::-1]
    for asset in assets:
        values = weights[asset].fillna(0).to_numpy()[::-1]
        fig.add_trace(go.Bar(y=rows, x=values, name=fr(asset), orientation="h",
                             marker=dict(color=palette[asset], line=dict(color="white", width=2)),
                             text=[f"{v:.0%}" if v >= .06 else "" for v in values], textposition="inside",
                             insidetextanchor="middle", textfont=dict(color="white", size=11),
                             hovertemplate=f"<b>{fr(asset)}</b><br>%{{y}} : %{{x:.1%}}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=.35)
    fig.update_xaxes(tickformat=".0%", range=[0, 1], title="Poids")
    return _layout(fig, title, subtitle, height=max(320, 70 + 46 * len(rows)))


def growth_chart(nav: pd.DataFrame, *, strategies: Sequence[str] | None = None, benchmark: str | None = None,
                 title: str = "Croissance de 1 € — HORS ÉCHANTILLON (walk-forward)",
                 subtitle: str | None = None, policy_order: Sequence[str] | None = None,
                 log: bool = True) -> go.Figure:
    assert_dates_before_holdout(nav.index, "Growth chart")
    strategies = list(nav.columns) if strategies is None else list(strategies)
    palette = colors_for([s for s in strategies if not _is_reference(s, benchmark)], policy_order)
    fig = go.Figure()
    for name in strategies:
        fig.add_trace(go.Scatter(x=nav.index, y=nav[name], mode="lines", name=fr(name),
                                 line=_line_style(name, benchmark, palette.get(name, MUTED)),
                                 hovertemplate=f"<b>{fr(name)}</b><br>%{{x|%d/%m/%Y}} : %{{y:.2f}} €<extra></extra>"))
    for year in sorted(set(nav.index.year))[1:]:
        fig.add_vline(x=pd.Timestamp(year=year, month=1, day=1), line=dict(color=GRID, width=1))
    fig.update_yaxes(type="log" if log else "linear", title="Valeur de 1 € investi" + (" (échelle log)" if log else ""))
    fig.update_xaxes(title=None)
    fig.update_layout(hovermode="x unified")
    return _layout(fig, title, subtitle)


def drawdown_chart(nav: pd.DataFrame, *, strategies: Sequence[str] | None = None, benchmark: str | None = None,
                   title: str = "Pertes depuis le plus haut — HORS ÉCHANTILLON", subtitle: str | None = None,
                   policy_order: Sequence[str] | None = None) -> go.Figure:
    assert_dates_before_holdout(nav.index, "Drawdown chart")
    strategies = list(nav.columns) if strategies is None else list(strategies)
    drawdown = nav[strategies] / nav[strategies].cummax() - 1
    palette = colors_for([s for s in strategies if not _is_reference(s, benchmark)], policy_order)
    fig = go.Figure()
    for name in strategies:
        fig.add_trace(go.Scatter(x=drawdown.index, y=drawdown[name], mode="lines", name=fr(name),
                                 line=_line_style(name, benchmark, palette.get(name, MUTED)),
                                 hovertemplate=f"<b>{fr(name)}</b><br>%{{x|%d/%m/%Y}} : %{{y:.1%}}<extra></extra>"))
    fig.update_yaxes(tickformat=".0%", title="Perte depuis le plus haut")
    fig.update_layout(hovermode="x unified")
    return _layout(fig, title, subtitle or "Une perte historique maximale n'est pas la pire perte future possible.",
                   height=420)


def oos_risk_return_chart(summary: pd.DataFrame, *, benchmark: str | None = None,
                          policy_order: Sequence[str] | None = None,
                          title: str = "Risque et rendement RÉALISÉS hors échantillon",
                          subtitle: str | None = None) -> go.Figure:
    """Empirical scatter of realized OOS CAGR vs volatility: NOT an estimated frontier."""
    fig = go.Figure()
    policies = [s for s in summary.index if not _is_reference(s, benchmark)]
    palette = colors_for(policies, policy_order)
    for name, row in summary.iterrows():
        neutral = _is_reference(name, benchmark)
        color = _reference_color(name) if neutral else palette[name]
        fig.add_trace(go.Scatter(
            x=[row["Volatility annualized"]], y=[row["CAGR"]], mode="markers+text", text=[fr(name)],
            textposition="top center", textfont=dict(size=11, color=MUTED), name=fr(name), showlegend=False,
            marker=dict(size=12, symbol="square" if neutral else "circle", color=color,
                        line=dict(color="white", width=2)),
            hovertemplate=(f"<b>{fr(name)}</b><br>Volatilité %{{x:.1%}}<br>CAGR %{{y:.1%}}<br>"
                           f"Perte max {row['Max Drawdown']:.1%}<br>Sharpe {row['Sharpe']:.2f}<extra></extra>")))
    fig.update_xaxes(title="Volatilité annualisée réalisée", tickformat=".0%")
    fig.update_yaxes(title="CAGR réalisé (net de coûts)", tickformat=".0%")
    return _layout(fig, title, subtitle or "Nuage empirique de politiques évaluées — pas une frontière estimée. "
                   "Carrés gris : références.", 540)


def walk_forward_weights_chart(weights: pd.DataFrame, *, title: str, asset_order: Sequence[str] | None = None
                               ) -> go.Figure:
    """Stacked target weights per test year (each allocation is fixed for its whole year)."""
    palette = colors_for(list(weights.columns), asset_order)
    years = [str(y) for y in weights.index]
    fig = go.Figure()
    for asset in weights.columns:
        if not (weights[asset] > 1e-4).any():
            continue
        fig.add_trace(go.Bar(x=years, y=weights[asset], name=fr(asset),
                             marker=dict(color=palette[asset], line=dict(color="white", width=2)),
                             hovertemplate=f"<b>{fr(asset)}</b><br>Année %{{x}} : %{{y:.1%}}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=.3)
    fig.update_yaxes(tickformat=".0%", range=[0, 1], title="Poids cible")
    fig.update_xaxes(title="Année de test (poids estimés sur les 10 années précédentes)", type="category")
    return _layout(fig, title, "Poids figés au début de chaque année de test, puis laissés dériver.", 440)


def annual_returns_chart(annual: pd.DataFrame, *, strategies: Sequence[str], benchmark: str | None = None,
                         policy_order: Sequence[str] | None = None,
                         title: str = "Rendements annuels — HORS ÉCHANTILLON") -> go.Figure:
    policies = [s for s in strategies if not _is_reference(s, benchmark)]
    palette = colors_for(policies, policy_order)
    fig = go.Figure()
    for name in strategies:
        if _is_reference(name, benchmark):
            color = _reference_color(name)
            marker = dict(color="white", line=dict(color=color, width=2))
        else:
            marker = dict(color=palette[name], line=dict(color="white", width=1))
        fig.add_trace(go.Bar(x=[str(y) for y in annual.index], y=annual[name], name=fr(name), marker=marker,
                             hovertemplate=f"<b>{fr(name)}</b><br>%{{x}} : %{{y:+.1%}}<extra></extra>"))
    fig.update_layout(barmode="group", bargap=.25, bargroupgap=.05)
    fig.update_yaxes(tickformat=".0%", title="Rendement de l'année (net)")
    fig.update_xaxes(type="category", title=None)
    return _layout(fig, title, "Sept années seulement : une ou deux années peuvent dominer le résultat.", 440)


def universe_comparison_chart(summary: pd.DataFrame, *, strategies: Sequence[str], metric: str = "CAGR",
                              policy_order: Sequence[str] | None = None) -> go.Figure:
    """Grouped bars of one OOS metric for each pre-specified universe variant."""
    universes = list(dict.fromkeys(summary.index.get_level_values("Universe")))
    palette = colors_for([s for s in strategies if not _is_reference(s, None)], policy_order)
    fig = go.Figure()
    for name in strategies:
        values = [summary.loc[(u, name), metric] for u in universes]
        marker = (dict(color="white", line=dict(color=_reference_color(name), width=2))
                  if _is_reference(name, None) else dict(color=palette[name]))
        fig.add_trace(go.Bar(x=universes, y=values, name=fr(name), marker=marker,
                             hovertemplate=f"<b>{fr(name)}</b><br>%{{x}} : %{{y:.1%}}<extra></extra>"))
    fig.update_layout(barmode="group", bargap=.3)
    fig.update_yaxes(tickformat=".0%", title=fr(metric) + " (hors échantillon, net)")
    fig.update_xaxes(title=None)
    return _layout(fig, f"Comparaison d'univers — {fr(metric)} HORS ÉCHANTILLON",
                   "Mêmes dates, coûts, estimateurs et contraintes ; seule l'éligibilité change.", 460)


def weight_profile_chart(profile, investor_limit: float | None = None) -> go.Figure:
    table = profile.table
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=table.index, y=table["Objective Sharpe"], mode="lines", name="Meilleur Sharpe atteignable",
                             line=dict(color=TEXT, width=2),
                             hovertemplate="Poids %{x:.0%}<br>Sharpe objectif %{y:.3f}<extra></extra>"))
    for level, dash in ((.99, "dot"), (.95, "dash")):
        fig.add_hline(y=level * profile.optimum_objective, line=dict(color=MUTED, dash=dash, width=1),
                      annotation_text=f"{level:.0%} de l'optimum", annotation_font_color=MUTED)
    fig.add_trace(go.Scatter(x=[profile.optimum_weight], y=[profile.optimum_objective], mode="markers",
                             name=f"Optimum ({profile.optimum_weight:.1%})",
                             marker=dict(size=12, symbol="diamond", color=PALETTE[0])))
    limit = profile.investor_limit if investor_limit is None else investor_limit
    if limit is not None:
        fig.add_vline(x=limit, line=dict(color=PALETTE[7], dash="dash"),
                      annotation_text=f"Limite investisseur {limit:.0%}")
    fig.update_xaxes(tickformat=".0%", title=f"Poids de {fr(profile.asset)} (autres poids ré-optimisés)")
    fig.update_yaxes(title="Sharpe (objectif de l'optimiseur)")
    return _layout(fig, f"Sensibilité du Sharpe maximal au poids de {fr(profile.asset)} — IN-SAMPLE",
                   "Une courbe plate signifie que des portefeuilles très différents se valent historiquement.", 440)


def save_html(fig: go.Figure, path: Path) -> Path:
    """Standalone HTML export (Plotly.js from CDN), checked for holdout dates after writing."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(path, include_plotlyjs="cdn", full_html=True)
    assert_file_safe(path)
    return path


def french_table(table: pd.DataFrame, percent: Sequence[str] = (), ratio: Sequence[str] = (),
                 integer: Sequence[str] = ()) -> pd.DataFrame:
    """Display copy with French labels and formatted numbers (raw values are never modified)."""
    out = pd.DataFrame(index=[fr(i) if not isinstance(i, tuple) else tuple(fr(x) for x in i) for i in table.index])
    for column in table.columns:
        values = table[column]
        if column in percent:
            shown = values.map(lambda v: "—" if pd.isna(v) else f"{v:.1%}")
        elif column in ratio:
            shown = values.map(lambda v: "—" if pd.isna(v) else f"{v:.2f}")
        elif column in integer:
            shown = values.map(lambda v: "—" if pd.isna(v) else f"{int(v)}")
        else:
            shown = values
        out[fr(column)] = shown.to_numpy()
    if isinstance(table.index, pd.MultiIndex):
        out.index = pd.MultiIndex.from_tuples(out.index)
    return out


def target_change_chart(changes: pd.DataFrame, traded: pd.DataFrame, *, policy_order: Sequence[str] | None = None,
                        title: str = "Changements d'allocation entre années — HORS ÉCHANTILLON") -> go.Figure:
    """Target-weight change D_t (solid) next to traded turnover after drift (dotted), per policy."""
    palette = colors_for(list(changes.columns), policy_order)
    fig = go.Figure()
    for name in changes.columns:
        fig.add_trace(go.Scatter(x=[str(y) for y in changes.index], y=changes[name], mode="lines+markers",
                                 name=f"{fr(name)} — variation des cibles", line=dict(color=palette[name], width=2),
                                 hovertemplate=f"<b>{fr(name)}</b><br>%{{x}} : cibles %{{y:.0%}}<extra></extra>"))
        if name in traded:
            fig.add_trace(go.Scatter(x=[str(y) for y in traded.index], y=traded[name], mode="lines+markers",
                                     name=f"{fr(name)} — rotation réelle", showlegend=True,
                                     line=dict(color=palette[name], width=1, dash="dot"), marker=dict(symbol="circle-open"),
                                     hovertemplate=f"<b>{fr(name)}</b><br>%{{x}} : rotation %{{y:.0%}}<extra></extra>"))
    fig.update_yaxes(tickformat=".0%", title="Part du portefeuille modifiée")
    fig.update_xaxes(type="category", title="Année de test")
    return _layout(fig, title, "Trait plein : ½ Σ|w(t) − w(t−1)| entre poids cibles. Pointillé : rotation réellement "
                   "échangée (depuis les poids ayant dérivé, achat initial exclu).", 460)


def concentration_chart(effective: pd.DataFrame, *, policy_order: Sequence[str] | None = None,
                        title: str = "Nombre effectif d'actifs (1 / HHI) par année") -> go.Figure:
    palette = colors_for([c for c in effective.columns if not _is_reference(c, None)], policy_order)
    fig = go.Figure()
    for name in effective.columns:
        line = (_line_style(name, None, MUTED) if _is_reference(name, None) else dict(color=palette[name], width=2))
        fig.add_trace(go.Scatter(x=[str(y) for y in effective.index], y=effective[name], mode="lines+markers",
                                 name=fr(name), line=line,
                                 hovertemplate=f"<b>{fr(name)}</b><br>%{{x}} : %{{y:.2f}} actifs<extra></extra>"))
    fig.update_yaxes(title="Nombre effectif d'actifs", rangemode="tozero")
    fig.update_xaxes(type="category", title="Année de test")
    return _layout(fig, title, "Plus la valeur est basse, plus le portefeuille est concentré. Apple et Nasdaq 100 "
                   "restent des expositions économiquement proches.", 420)


def bootstrap_range_chart(ranges: pd.DataFrame, policy: str, *, asset_order: Sequence[str] | None = None
                          ) -> go.Figure:
    """Per asset: mean fitted weight and mean 5-95% bootstrap range across folds (training data only)."""
    table = ranges.loc[policy]
    table = table[(table["Mean P95"] > .005) | (table["Mean point weight"] > .005)]
    palette = colors_for(list(ranges.index.get_level_values("Asset").unique()), asset_order)
    fig = go.Figure()
    for asset, row in table.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["Mean point weight"]], y=[fr(asset)], mode="markers", showlegend=False,
            marker=dict(size=11, color=palette[asset], line=dict(color="white", width=2)),
            error_x=dict(type="data", symmetric=False, array=[row["Mean P95"] - row["Mean point weight"]],
                         arrayminus=[row["Mean point weight"] - row["Mean P5"]], color=palette[asset], thickness=2),
            hovertemplate=(f"<b>{fr(asset)}</b><br>Poids estimé moyen %{{x:.0%}}<br>Plage 5–95 % : "
                           f"{row['Mean P5']:.0%} – {row['Mean P95']:.0%}<extra></extra>")))
    fig.update_xaxes(tickformat=".0%", range=[0, 1], title="Poids (moyenne sur les 7 plis)")
    return _layout(fig, f"{fr(policy)} — sensibilité des poids à l'échantillon d'apprentissage",
                   "Rééchantillonnage bootstrap des seules données d'apprentissage de chaque pli (40 tirages). "
                   "Une barre large = poids mal déterminé par les données.", max(300, 80 + 45 * len(table)))


def window_distance_chart(distance: pd.DataFrame, *, policy_order: Sequence[str] | None = None) -> go.Figure:
    palette = colors_for(list(distance.columns), policy_order)
    fig = go.Figure()
    for name in distance.columns:
        fig.add_trace(go.Bar(x=[str(y) for y in distance.index], y=distance[name], name=fr(name),
                             marker=dict(color=palette[name]),
                             hovertemplate=f"<b>{fr(name)}</b><br>%{{x}} : %{{y:.0%}}<extra></extra>"))
    fig.update_layout(barmode="group", bargap=.25)
    fig.update_yaxes(tickformat=".0%", range=[0, 1], title="½ Σ|w glissante − w croissante|")
    fig.update_xaxes(type="category", title="Année de test")
    return _layout(fig, "Écart d'allocation : fenêtre glissante (10 ans) vs croissante",
                   "0 % = allocations identiques ; 100 % = aucun actif en commun.", 420)


def risk_forecast_chart(risk: pd.DataFrame, *, policy_order: Sequence[str] | None = None) -> go.Figure:
    """Ex-ante estimated volatility (training) against realized volatility of each test year."""
    policies = list(dict.fromkeys(risk.index.get_level_values("Policy")))
    palette = colors_for(policies, policy_order)
    fig = go.Figure()
    top = float(np.nanmax(risk.to_numpy())) * 1.1
    fig.add_trace(go.Scatter(x=[0, top], y=[0, top], mode="lines", line=dict(color=GRID, dash="dash"),
                             name="Réalisé = estimé", hoverinfo="skip"))
    for name in policies:
        sub = risk.loc[name]
        fig.add_trace(go.Scatter(x=sub["Estimated volatility"], y=sub["Realized volatility"], mode="markers",
                                 name=fr(name), marker=dict(size=9, color=palette[name], line=dict(color="white", width=1)),
                                 text=[str(y) for y in sub.index],
                                 hovertemplate=(f"<b>{fr(name)}</b> %{{text}}<br>Estimée %{{x:.1%}}<br>"
                                                "Réalisée %{y:.1%}<extra></extra>")))
    fig.update_xaxes(tickformat=".0%", title="Volatilité estimée à l'apprentissage (ex ante)")
    fig.update_yaxes(tickformat=".0%", title="Volatilité réalisée sur l'année de test")
    return _layout(fig, "Risque prévu vs risque réalisé — par année de test",
                   "Points au-dessus de la diagonale : risque sous-estimé à l'apprentissage.", 480)


def correlation_heatmap(corr: pd.DataFrame, *, title: str = "Corrélations des rendements quotidiens — apprentissage"
                        ) -> go.Figure:
    """Diverging heatmap (blue = positive, red = negative, grey midpoint) with the values printed."""
    labels = [fr(c) for c in corr.columns]
    fig = go.Figure(go.Heatmap(z=corr.to_numpy(), x=labels, y=labels, zmin=-1, zmax=1,
                               colorscale=[[0, "#e34948"], [.5, "#f0efec"], [1, "#2a78d6"]],
                               text=corr.round(2).to_numpy(), texttemplate="%{text}",
                               hovertemplate="%{y} / %{x} : %{z:.2f}<extra></extra>", colorbar=dict(title="ρ")))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, title, "Corrélation de rendements mesurée ; ce n'est pas un recouvrement de titres "
                   "confirmé (aucune composition d'indice historique n'est utilisée).", 520)


def risk_contribution_chart(contributions: pd.DataFrame, *, asset_order: Sequence[str] | None = None,
                            title: str = "D'où vient le risque ? Contributions au risque par portefeuille") -> go.Figure:
    """Horizontal 100% stacked bars of variance contributions (rows = portfolios, columns = assets)."""
    palette = colors_for(list(contributions.columns), asset_order)
    fig = go.Figure()
    rows = [fr(i) for i in contributions.index][::-1]
    for asset in contributions.columns:
        values = contributions[asset].to_numpy()[::-1]
        fig.add_trace(go.Bar(y=rows, x=values, name=fr(asset), orientation="h",
                             marker=dict(color=palette[asset], line=dict(color="white", width=2)),
                             text=[f"{v:.0%}" if v >= .06 else "" for v in values], textposition="inside",
                             textfont=dict(color="white", size=11),
                             hovertemplate=f"<b>{fr(asset)}</b><br>%{{y}} : %{{x:.1%}} du risque<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=.35)
    fig.update_xaxes(tickformat=".0%", range=[0, 1], title="Part de la variance du portefeuille")
    return _layout(fig, title, "Covariance fixe de la période de développement (2001–2012).",
                   max(320, 70 + 46 * len(rows)))
