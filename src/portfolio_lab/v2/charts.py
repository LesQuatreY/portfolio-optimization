"""Plotly figures of Portfolio Lab V2 (French labels; presentation only).

Every builder takes the loaded ``StrategyLab`` and a list of portfolio ids and returns a
``go.Figure``. Nothing is simulated; values are the frozen Research results or simple arithmetic
on the frozen daily curves. One visual system for every chart:

* a strategy keeps the same colour everywhere (fixed by its order in config/v2/lab.yaml), the
  four permanent benchmarks are neutral greys (dashes = ×1 / ×2 darkness, dots = + gold/Bitcoin);
* the same light palette and benchmark marks are used in every notebook;
* small toggles (risk axis, scale, drawdown view, allocation view, heatmap view) are Plotly
  buttons inside the figure, so switching never re-runs anything;
* historical reconstructions are named in hover texts and subtitles.
"""
from __future__ import annotations

from typing import Sequence
import textwrap

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from . import formatting as F
from . import metrics as M

SURFACE, TEXT, TEXT2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
STRATEGY_COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
BENCHMARK_STYLES = (("#6b6a66", "dash", "diamond"), ("#262624", "dash", "diamond"),
                    ("#6b6a66", "dot", "diamond-open"), ("#262624", "dot", "diamond-open"))
GROUP_COLORS = {"nasdaq_x2": "#1c5cab", "nasdaq_x1": "#5598e7", "staples": "#1baf7a", "gold": "#eda100",
                "bonds": "#6250d6", "bitcoin": "#eb6834", "money_market": "#a8a69e", "cash": "#d6d5ce",
                "life_insurance": "#e87ba4"}
WRAPPER_COLORS = {"PEA": "#2a78d6", "CTO": "#1baf7a", "BTC": "#eb6834", "AV": "#6250d6"}
COST_COLORS = ("#1c5cab", "#5598e7", "#eda100", "#e34948")
DIVERGING = [[0.0, "#e34948"], [0.5, "#f0efec"], [1.0, "#2a78d6"]]
LOSSES = [[0.0, "#f0efec"], [1.0, "#e34948"]]
CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
          "toImageButtonOptions": {"format": "png", "scale": 2}}
SHADED = (("R2_correction_2018", "Correction 2018"), ("R4_covid_crash", "Krach Covid"), ("R6_bear_2022", "Baisse 2022"))
REGIMES_FR = {"R1_expansion_2014_2017": "Expansion 2014–2017", "R2_correction_2018": "Correction 2018",
              "R3_recovery_2019": "Reprise 2019", "R4_covid_crash": "Krach Covid (fév.–mars 2020)",
              "R5_rally_2020_2021_ex_crash": "Rallye 2020–2021", "R6_bear_2022": "Baisse 2022", "R7_rebound_2023": "Rebond 2023"}
CRISES_FR = (("Q4_2018", "Correction T4 2018"), ("COVID_2020", "Krach Covid 2020"), ("BEAR_2022", "Baisse 2022"))
ROLLING = {"r3": ("CAGR glissant sur 3 ans", "pct"), "r5": ("CAGR glissant sur 5 ans", "pct"),
           "vol1": ("Volatilité glissante sur 1 an", "pct"), "vol3": ("Volatilité glissante sur 3 ans", "pct"),
           "sh1": ("Sharpe glissant sur 1 an", "num"), "sh3": ("Sharpe glissant sur 3 ans", "num"),
           "mdd3": ("Pire baisse sur les 3 années précédentes", "pct")}
EMPTY = "Sélectionnez au moins un portefeuille."


# --------------------------------------------------------------------------- theme and styles
def setup() -> None:
    """Plotly defaults: French separators, quiet chrome, renderers for JupyterLab / VS Code."""
    template = go.layout.Template(pio.templates["plotly_white"])
    template.layout.font = dict(family=FONT, size=12, color=TEXT)
    template.layout.separators = ", "
    template.layout.paper_bgcolor = SURFACE
    template.layout.plot_bgcolor = SURFACE
    template.layout.hoverlabel = dict(bgcolor="white", bordercolor=AXIS, font=dict(family=FONT, size=12, color=TEXT))
    template.layout.xaxis = dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, tickfont=dict(color=TEXT2))
    template.layout.yaxis = dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, tickfont=dict(color=TEXT2))
    pio.templates["portfolio_lab"] = template
    pio.templates.default = "portfolio_lab"
    # Native Plotly output (JupyterLab with the bundled jupyterlab-plotly extension, VS Code): offline, one copy of the data.
    pio.renderers.default = "plotly_mimetype"
    pio.renderers["plotly_mimetype"].config = CONFIG


def style(lab, sid: str) -> dict:
    """Colour, dash and marker of a portfolio (stable: follows its configured order, never its rank)."""
    if lab.meta.loc[sid, "kind"] == "strategy":
        return {"color": STRATEGY_COLORS[lab.strategies.index(sid) % len(STRATEGY_COLORS)], "dash": "solid",
                "symbol": "circle", "width": 2.0, "benchmark": False}
    color, dash, symbol = BENCHMARK_STYLES[lab.benchmarks.index(sid) % len(BENCHMARK_STYLES)]
    return {"color": color, "dash": dash, "symbol": symbol, "width": 1.6, "benchmark": True}


def _title(text: str, subtitle: str | None = None) -> dict:
    title = "<br>".join(textwrap.wrap(text, 58))
    sub = (f"<br><span style='font-size:12px;color:{TEXT2}'>"
           + "<br>".join(textwrap.wrap(subtitle, 84)) + "</span>") if subtitle else ""
    return dict(text=f"<b>{title}</b>{sub}", x=0.02, xanchor="left", y=0.96, yanchor="top", font=dict(size=16))


def _layout(fig: go.Figure, title: str, subtitle: str | None, height: int, top: int = 96, bottom: int = 96) -> go.Figure:
    """Title block, margins and a legend pinned to the bottom of the figure (never over the x-axis title)."""
    # Reserve distinct rows for wrapped titles, context and controls, including at 640 px.
    title_rows = len(textwrap.wrap(title, 58))
    subtitle_rows = len(textwrap.wrap(subtitle or "", 84))
    top = max(top, 24 + 24 * title_rows + 16 * subtitle_rows + (46 if fig.layout.updatemenus else 24))
    fig.update_layout(title=_title(title, subtitle), height=height, margin=dict(l=72, r=28, t=top, b=bottom),
                      legend=dict(orientation="h", yref="container", y=0.005, yanchor="bottom", x=0, title_text="",
                                  font=dict(size=11), traceorder="normal"),
                      template="portfolio_lab")
    return fig


def _time_axis(fig: go.Figure, lab, start=None, **kw) -> None:
    """Time axis bounded by the data (no tick beyond the 2023-12-29 cutoff)."""
    first, last = lab.period
    fig.update_xaxes(range=[start if start is not None else first, last], **kw)


def _buttons(options: Sequence[tuple[str, list]], *, x: float = 1.0, y: float = 1.02, active: int = 0) -> dict:
    return dict(type="buttons", direction="right", x=x, xanchor="right", y=y, yanchor="bottom", showactive=True,
                active=active, bgcolor="white", bordercolor=AXIS, borderwidth=1, font=dict(size=11, color=TEXT),
                pad=dict(l=2, r=2, t=2, b=2), buttons=[dict(label=label, method="update", args=args) for label, args in options])


def _legend_keys(items) -> list:
    """Legend-only traces in neutral ink (the marks themselves carry the portfolio colours)."""
    return [go.Scatter(x=[None], y=[None], mode="markers", name=name, hoverinfo="skip",
                       marker=dict(symbol=symbol, size=12, color=TEXT2, line=dict(width=2.5, color=TEXT2)))
            for name, symbol in items]


def empty_figure(message: str = EMPTY, height: int = 260) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                       font=dict(size=14, color=TEXT2))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=height, template="portfolio_lab", margin=dict(l=20, r=20, t=20, b=20))
    return fig


def _label(lab, sid: str) -> str:
    return f"{sid} — {lab.meta.loc[sid, 'name']}"


def _status(lab, sid: str) -> str:
    meta = lab.meta.loc[sid]
    if not meta["reconstructed_lines"]:
        return "observées"
    names = ", ".join(lab.lines.loc[c, "label"].split(" — ")[0] for c in meta["reconstructed_lines"])
    return f"{meta['data_status'].lower()} — {names} ({F.pct(meta['reconstructed_share'], 0)} en moyenne)"


def _shade(fig: go.Figure, lab, rows: bool = False, start=None) -> None:
    """Grey bands for Research's 2018, Covid-crash and 2022 regimes; labels inside the top of the plot."""
    for key, text in SHADED:
        a, b = lab.periods["regimes"][key]
        if start is not None and pd.Timestamp(b) < start:
            continue
        kw = dict(row="all", col=1) if rows else {}
        fig.add_vrect(x0=a, x1=b, fillcolor=MUTED, opacity=0.08, line_width=0, layer="below", **kw)
        anchor = max(pd.Timestamp(a), start) if start is not None else pd.Timestamp(a)
        fig.add_annotation(x=anchor, y=0.995, xref="x", yref="paper", text=text, showarrow=False,
                           xanchor="left", yanchor="top", xshift=2, font=dict(size=10, color=TEXT2),
                           bgcolor="rgba(252,252,251,0.75)")


# --------------------------------------------------------------------------- A. risk / return frontier
_POSITIONS = (("top right", 1, 1), ("bottom right", 1, -1), ("top left", -1, 1), ("bottom left", -1, -1),
              ("middle right", 1, 0), ("middle left", -1, 0), ("top center", 0, 1), ("bottom center", 0, -1))


def _label_positions(points, xr, yr, width=540.0, height=300.0) -> dict:
    """Greedy, overlap-avoiding text positions for point labels; points = [(sid, x, y)]."""
    def px(x, y):
        return (x - xr[0]) / (xr[1] - xr[0]) * width, (y - yr[0]) / (yr[1] - yr[0]) * height
    boxes = [(a - 8, b - 8, a + 8, b + 8) for a, b in (px(x, y) for _, x, y in points)]
    out = {}
    for sid, x, y in sorted(points, key=lambda p: (p[1], p[2])):
        cx, cy = px(x, y)
        w, h = 7.0 * len(sid) + 6, 15
        best = None
        for name, dx, dy in _POSITIONS:
            x0 = cx + 9 if dx > 0 else cx - 9 - w if dx < 0 else cx - w / 2
            y0 = cy + 9 if dy > 0 else cy - 9 - h if dy < 0 else cy - h / 2
            box = (x0, y0, x0 + w, y0 + h)
            score = sum(max(0, min(box[2], o[2]) - max(box[0], o[0])) * max(0, min(box[3], o[3]) - max(box[1], o[1]))
                        for o in boxes)
            score += 400 * (box[0] < 0 or box[2] > width or box[1] < 0 or box[3] > height)
            if best is None or score < best[0]:
                best = (score, name, box)
        out[sid] = best[1]
        boxes.append(best[2])
    return out


def frontier_figure(lab, selected: Sequence[str], metric: str = "volatility") -> go.Figure:
    """Net CAGR against annualized volatility or daily MaxDD: one figure, one in-figure toggle."""
    s = lab.summary
    ids = list(lab.ids)
    chosen = set(lab.ordered(selected))
    axes = {"volatility": ("Volatilité annualisée (quotidienne, %)", s["volatility"] * 100),
            "max_drawdown": ("MaxDD journalier (%)", s["max_drawdown"] * 100)}
    y = s["cagr_net"] * 100

    def span(v):
        pad = 0.08 * (v.max() - v.min())
        return [float(v.min() - pad), float(v.max() + pad)]

    yr = span(y)
    ranges = {k: span(v) for k, (_, v) in axes.items()}
    labels = {k: _label_positions([(sid, v[sid], y[sid]) for sid in ids], ranges[k], yr) for k, (_, v) in axes.items()}
    fig = go.Figure()
    for sid in ids:
        st = style(lab, sid)
        on = sid in chosen
        r = s.loc[sid]
        custom = [[_label(lab, sid), lab.meta.loc[sid, "role"], F.pct(r["cagr_net"]), F.pct(r["volatility"]),
                   F.pct(r["max_drawdown"]), F.ratio(r["sharpe"]), F.eur(r["terminal_net"]), lab.meta.loc[sid, "period"],
                   _status(lab, sid)]]
        fig.add_trace(go.Scatter(
            x=[axes[metric][1][sid]], y=[y[sid]], name=sid, mode="markers+text", text=[sid],
            textposition=labels[metric].get(sid, "top right"),
            textfont=dict(size=12 if on else 11, color=TEXT if on else MUTED), customdata=custom, legendgroup=sid,
            marker=dict(size=15 if st["benchmark"] else 14, color=st["color"], symbol=st["symbol"], opacity=1.0 if on else 0.3,
                        line=dict(color=SURFACE if not st["symbol"].endswith("open") else st["color"],
                                  width=2 if not st["symbol"].endswith("open") else 2.5)),
            hovertemplate=("<b>%{customdata[0]}</b><br><span style='color:#52514e'>%{customdata[1]}</span><br>"
                           "CAGR net : <b>%{customdata[2]}</b><br>Volatilité : %{customdata[3]}<br>"
                           "MaxDD journalier : %{customdata[4]}<br>Sharpe : %{customdata[5]}<br>"
                           "Patrimoine net : %{customdata[6]}<br>Période : %{customdata[7]}<br>"
                           "Données : %{customdata[8]}<extra></extra>")))
    options = []
    for key, (title, values) in axes.items():
        options.append((title.split(" (")[0], [{"x": [[values[sid]] for sid in ids],
                                                "textposition": [labels[key].get(sid, "top right") for sid in ids]},
                                               {"xaxis.title.text": title, "xaxis.range": ranges[key]}]))
    start, end = lab.period
    fig.update_layout(updatemenus=[_buttons(options, active=list(axes).index(metric))])
    fig.update_xaxes(title_text=axes[metric][0], range=ranges[metric])
    fig.update_yaxes(title_text="CAGR net (%/an)", range=yr)
    fig.add_annotation(x=0.01, y=0.99, xref="paper", yref="paper", text="↖ plus de rendement pour moins de risque",
                       showarrow=False, xanchor="left", yanchor="top", font=dict(size=11, color=MUTED))
    return _layout(fig, "Rendement net et risque — chaque point est un portefeuille",
                   f"CAGR net après frais, vente finale et impôts de sortie ; {F.date(start)} → {F.date(end)}, 100 000 € investis. "
                   "Points pâles : hors sélection. Une seule trajectoire passée : être bien placé ici ne garantit rien pour l'avenir.",
                   580)


# --------------------------------------------------------------------------- B. wealth and drawdowns
def wealth_figure(lab, selected: Sequence[str], log: bool = False) -> go.Figure:
    """Daily wealth (EUR) over drawdown depth or time below the previous peak, shared time axis."""
    ids = lab.ordered(selected)
    if not ids:
        return empty_figure()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.62, 0.38], vertical_spacing=0.05)
    depth, duration, dd_index = [], [], []
    for sid in ids:
        st = style(lab, sid)
        v = lab.wealth[sid]
        line = dict(color=st["color"], width=st["width"], dash=st["dash"])
        fig.add_trace(go.Scatter(x=v.index, y=v, name=sid, legendgroup=sid, line=line,
                                 hovertemplate=f"{sid} : %{{y:,.0f}} €<extra></extra>"), row=1, col=1)
        term = lab.summary.loc[sid, "terminal_net"]
        fig.add_trace(go.Scatter(x=[v.index[-1]], y=[term], mode="markers", legendgroup=sid, showlegend=False, cliponaxis=False,
                                 marker=dict(symbol="x-thin", size=11, line=dict(width=2.5, color=st["color"])),
                                 hovertemplate=f"{sid} — patrimoine net après vente finale et impôts de sortie : "
                                               f"{F.eur(term)}<extra></extra>"), row=1, col=1)
        dd = M.drawdown(v, lab.initial) * 100
        below = M.sessions_below_peak(v, lab.initial)
        depth.append(dd.to_numpy())
        duration.append(below.to_numpy())
        fig.add_trace(go.Scatter(x=v.index, y=dd, name=sid, legendgroup=sid, showlegend=False, line=dict(line, width=1.3),
                                 hovertemplate=f"{sid} : %{{y:.1f}} %<extra></extra>"), row=2, col=1)
        dd_index.append(len(fig.data) - 1)
    _shade(fig, lab, rows=True)
    views = [("Drawdown (%)", depth, "Baisse depuis le sommet (%)", ".0f"),
             ("Durée sous le sommet", duration, "Séances depuis le dernier sommet", ",.0f")]
    dd_buttons = [(label, [{"y": data, "hovertemplate": [f"{sid} : %{{y:.1f}} %<extra></extra>" if i == 0
                                                         else f"{sid} : %{{y:,.0f}} séances<extra></extra>" for sid in ids]},
                           {"yaxis2.title.text": title, "yaxis2.tickformat": fmt, "yaxis2.autorange": True}, dd_index])
                  for i, (label, data, title, fmt) in enumerate(views)]
    scale = [dict(label=label, method="relayout", args=[{"yaxis.type": kind}]) for label, kind in
             (("Échelle linéaire", "linear"), ("Échelle log", "log"))]
    fig.update_layout(updatemenus=[
        dict(type="buttons", direction="right", x=0.0, xanchor="left", y=1.02, yanchor="bottom", showactive=True,
             active=int(log), bgcolor="white", bordercolor=AXIS, font=dict(size=11), buttons=scale),
        dict(_buttons(dd_buttons, y=1.02))])
    fig.update_yaxes(title_text="Patrimoine (€)", type="log" if log else "linear", tickformat=",.0f", row=1, col=1)
    fig.update_yaxes(title_text="Baisse depuis le sommet (%)", tickformat=".0f", row=2, col=1)
    fig.update_layout(hovermode="x unified")
    _time_axis(fig, lab)
    start, end = lab.period
    return _layout(fig, "Patrimoine et drawdowns",
                   f"Valeur quotidienne après frais et impôts payés en cours de route (sans impôt de sortie latent), "
                   f"100 000 € le {F.date(start)}. × = patrimoine net au {F.date(end)} après vente finale et impôts de sortie.",
                   720, top=118)


# --------------------------------------------------------------------------- C. allocations and exposure
def allocation_figure(lab, sid: str, view: str = "assets") -> go.Figure:
    """100 % stacked accounting weights of one portfolio, by asset class or by tax wrapper."""
    total = lab.wealth[sid]
    lines = lab.lines
    fig = go.Figure()
    sets = []
    for kind, keys, colors in (("assets", [g for g, _ in lab.settings.groups], GROUP_COLORS),
                               ("wrappers", [w for w, _ in lab.settings.wrappers], WRAPPER_COLORS)):
        labels = dict(lab.settings.groups if kind == "assets" else lab.settings.wrappers)
        field = "group" if kind == "assets" else "wrapper"
        members = []
        for key in keys:
            cols = [c for c in lines.index if lines.loc[c, field] == key and lab.holdings.loc[sid, c]]
            if not cols:
                continue
            weight = sum(lab.curves[c][sid] for c in cols) / total
            proxied = [c for c in cols if lines.loc[c, "provenance"] in ("proxy", "synthetique")]
            name = labels[key] + (" *" if proxied else "")
            fig.add_trace(go.Scatter(x=total.index, y=weight, name=name, stackgroup=kind, mode="lines",
                                     line=dict(width=0.6, color=SURFACE), fillcolor=colors[key], visible=kind == view,
                                     hovertemplate=f"{name} : %{{y:.1%}}<extra></extra>"))
            members.append(len(fig.data) - 1)
        sets.append(members)
    vis = [[i in sets[k] for i in range(len(fig.data))] for k in (0, 1)]
    fig.update_layout(updatemenus=[_buttons([("Par classe d'actifs", [{"visible": vis[0]}]),
                                             ("Par enveloppe", [{"visible": vis[1]}])], active=0 if view == "assets" else 1)],
                      hovermode="x unified")
    fig.update_yaxes(title_text="Poids dans le patrimoine total", tickformat=".0%", range=[0, 1])
    _time_axis(fig, lab)
    return _layout(fig, f"Allocation comptable — {_label(lab, sid)}",
                   "Valeur de chaque ligne ÷ patrimoine total. LQQ compte pour sa valeur, pas pour son exposition ×2 "
                   "(voir l'exposition économique). * = série reconstituée (proxy ou synthétique).", 470, top=104)


EXPOSURE = (("ndx_exposure_total", "Exposition Nasdaq économique", "Exposition au Nasdaq-100 (× le patrimoine)", ".2f", "×"),
            ("expo_sleeve", "Levier de la poche Nasdaq", "Levier de la poche Nasdaq (×)", ".2f", "×"),
            ("cash_mm_share", "Liquidités + monétaire", "Liquidités et monétaire (% du patrimoine)", ".0%", "%"))


def exposure_figure(lab, selected: Sequence[str]) -> go.Figure:
    """Economic Nasdaq exposure (LQQ counted ×2), sleeve leverage or cash share; in-figure toggle."""
    ids = lab.ordered(selected)
    if not ids:
        return empty_figure()
    fig = go.Figure()
    for sid in ids:
        st = style(lab, sid)
        v = lab.curves[EXPOSURE[0][0]][sid]
        fig.add_trace(go.Scatter(x=v.index, y=v, name=sid, line=dict(color=st["color"], width=st["width"], dash=st["dash"]),
                                 hovertemplate=f"{sid} : ×%{{y:.2f}}<extra></extra>"))
    options = []
    for column, label, title, fmt, unit in EXPOSURE:
        data = [lab.curves[column][sid].to_numpy() for sid in ids]
        hover = [f"{sid} : " + ("×%{y:.2f}" if unit == "×" else "%{y:.1%}") + "<extra></extra>" for sid in ids]
        options.append((label, [{"y": data, "hovertemplate": hover}, {"yaxis.title.text": title, "yaxis.tickformat": fmt}]))
    fig.update_layout(updatemenus=[_buttons(options)], hovermode="x unified")
    fig.update_yaxes(title_text=EXPOSURE[0][2], tickformat=EXPOSURE[0][3])
    _shade(fig, lab)
    _time_axis(fig, lab)
    return _layout(fig, "Exposition et levier au fil du temps",
                   "Exposition économique = (PUST + 2 × LQQ) ÷ patrimoine : à distinguer des poids comptables. "
                   "Levier de la poche = exposition de la seule poche Nasdaq du PEA.", 450, top=104)


# --------------------------------------------------------------------------- D. robustness
def rolling_figure(lab, selected: Sequence[str], metric: str = "r3") -> go.Figure:
    ids = lab.ordered(selected)
    if not ids:
        return empty_figure()
    title, unit = ROLLING[metric]
    data = lab.rolling[metric]
    first = data[ids].dropna(how="all").index.min()
    fig = go.Figure()
    for sid in ids:
        st = style(lab, sid)
        v = data[sid].dropna()
        fig.add_trace(go.Scatter(x=v.index, y=v, name=sid, line=dict(color=st["color"], width=st["width"], dash=st["dash"]),
                                 hovertemplate=f"{sid} : " + ("%{y:.1%}" if unit == "pct" else "%{y:.2f}") + "<extra></extra>"))
    if metric in ("r3", "r5", "sh1", "sh3"):
        fig.add_hline(y=0, line=dict(color=AXIS, width=1))
    _shade(fig, lab, start=first)
    _time_axis(fig, lab, start=first)
    fig.update_yaxes(title_text=title, tickformat=".0%" if unit == "pct" else ".1f")
    fig.update_layout(hovermode="x unified")
    window = {"r3": 756, "r5": 1260, "vol1": 252, "vol3": 756, "sh1": 252, "sh3": 756, "mdd3": 756}[metric]
    return _layout(fig, title, f"Fenêtre glissante de {window} séances sur la valeur quotidienne (avant impôts de sortie). "
                   "Source : rolling_metrics.parquet (Research V11.2).", 450, top=88)


def calendar_figure(lab, selected: Sequence[str]) -> go.Figure:
    """Calendar-year or market-regime returns as a heatmap (toggle inside the figure)."""
    ids = lab.ordered(selected)
    if not ids:
        return empty_figure()
    views = []
    cal = lab.calendar.loc[ids]
    views.append(("Années civiles", cal.rename(columns={"2014 T4": "2014 (T4)"})))
    reg = lab.regimes.loc[ids, list(REGIMES_FR)].rename(columns=REGIMES_FR)
    views.append(("Régimes de marché", reg))
    traces = []
    for label, tab in views:
        z = tab.to_numpy(float) * 100
        lim = float(np.nanpercentile(np.abs(z), 95)) or 1.0
        text = [[F.num(v, 0) for v in row] for row in z]
        traces.append(dict(z=z, x=list(tab.columns), y=list(tab.index), text=text, lim=lim))
    t0 = traces[0]
    fig = go.Figure(go.Heatmap(z=t0["z"], x=t0["x"], y=t0["y"], text=t0["text"], texttemplate="%{text}",
                               colorscale=DIVERGING, zmin=-t0["lim"], zmax=t0["lim"], xgap=2, ygap=2,
                               colorbar=dict(title="%", thickness=10, len=0.8),
                               hovertemplate="%{y} — %{x} : %{text} %<extra></extra>"))
    options = [(label, [{"z": [t["z"]], "x": [t["x"]], "y": [t["y"]], "text": [t["text"]], "zmin": [-t["lim"]],
                         "zmax": [t["lim"]]}, {}]) for (label, _), t in zip(views, traces)]
    fig.update_layout(updatemenus=[_buttons(options)])
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickangle=0)
    return _layout(fig, "Rendements par année et par régime de marché (%)",
                   "Valeur quotidienne (frais et impôts payés inclus, avant impôts de sortie) ; 2014 = dernier trimestre "
                   "seulement. Couleurs saturées au-delà du 95e centile.", 160 + 38 * len(ids), top=100, bottom=48)


def chronology_figure(lab, selected: Sequence[str]) -> go.Figure:
    """DEV (2014-10 → 2018-12) against EVAL (2019-01 → 2023-12): separate Research runs, dumbbell form."""
    ids = lab.ordered(selected)
    if not ids:
        return empty_figure()
    s = lab.summary.loc[ids]
    rows = [f"{sid}" for sid in ids]
    colors = [style(lab, sid)["color"] for sid in ids]
    views = {"cagr": ("CAGR net", s["dev_cagr"] * 100, s["eval_cagr"] * 100, "CAGR net (%/an)"),
             "mdd": ("MaxDD", s["dev_mdd"] * 100, s["eval_mdd"] * 100, "MaxDD journalier (%)")}

    def connector(a, b):
        xs, ys = [], []
        for sid, u, v in zip(rows, a, b):
            xs += [u, v, None]
            ys += [sid, sid, None]
        return xs, ys

    label, dev, ev, axis = views["cagr"]
    cx, cy = connector(dev, ev)
    fig = go.Figure([
        go.Scatter(x=cx, y=cy, mode="lines", line=dict(color=AXIS, width=2), hoverinfo="skip", showlegend=False),
        go.Scatter(x=dev, y=rows, mode="markers", name="DEV", showlegend=False,
                   marker=dict(size=12, symbol="circle-open", color=colors, line=dict(width=2.5, color=colors)),
                   hovertemplate="%{y} — DEV : %{x:.1f} %<extra></extra>"),
        go.Scatter(x=ev, y=rows, mode="markers", name="EVAL", showlegend=False,
                   marker=dict(size=12, symbol="circle", color=colors, line=dict(width=2, color=SURFACE)),
                   hovertemplate="%{y} — EVAL : %{x:.1f} %<extra></extra>"),
        *_legend_keys((("DEV : oct. 2014 → déc. 2018", "circle-open"), ("EVAL : janv. 2019 → déc. 2023", "circle")))])
    options = []
    for key, (label, dev, ev, axis) in views.items():
        cx, cy = connector(dev, ev)
        options.append((label, [{"x": [cx, list(dev), list(ev)]}, {"xaxis.title.text": axis}, [0, 1, 2]]))
    fig.update_layout(updatemenus=[_buttons(options)])
    fig.update_xaxes(title_text=views["cagr"][3], ticksuffix="")
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, "Stabilité chronologique : première moitié contre seconde moitié",
                   "Deux simulations Research distinctes (100 000 € au début de chaque fenêtre, impôts de sortie inclus). "
                   "○ DEV · ● EVAL. EVAL n'est pas un test vierge : ces années ont été étudiées.", 170 + 40 * len(ids), top=104)


def crisis_figure(lab, selected: Sequence[str]) -> go.Figure:
    ids = lab.ordered(selected)
    if not ids:
        return empty_figure()
    c = lab.crises.loc[ids]
    cols = [label for _, label in CRISES_FR]
    change = np.column_stack([c[f"{k}_change"].to_numpy(float) for k, _ in CRISES_FR]) * 100
    depth = np.column_stack([c[f"{k}_mdd"].to_numpy(float) for k, _ in CRISES_FR]) * 100
    lim_c = float(np.nanmax(np.abs(change))) or 1.0
    lim_d = float(np.nanmax(depth)) or 1.0
    txt = lambda z: [[F.num(v, 1) for v in row] for row in z]  # noqa: E731
    fig = go.Figure(go.Heatmap(z=change, x=cols, y=ids, text=txt(change), texttemplate="%{text}", colorscale=DIVERGING,
                               zmin=-lim_c, zmax=lim_c, xgap=2, ygap=2, colorbar=dict(title="%", thickness=10, len=0.8),
                               hovertemplate="%{y} — %{x} : %{text} %<extra></extra>"))
    options = [("Variation sur l'épisode", [{"z": [change], "text": [txt(change)], "colorscale": [DIVERGING],
                                              "zmin": [-lim_c], "zmax": [lim_c]}, {}]),
               ("Baisse maximale pendant l'épisode", [{"z": [depth], "text": [txt(depth)], "colorscale": [LOSSES],
                                                       "zmin": [0], "zmax": [lim_d]}, {}])]
    fig.update_layout(updatemenus=[_buttons(options)])
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, "Comportement pendant les crises 2014–2023 (%)",
                   "Épisodes définis par Research (crisis_summary.csv) ; valeur quotidienne avant impôts de sortie. "
                   "Les reconstitutions antérieures à 2014 sont exclues de cette version.", 160 + 38 * len(ids), top=100, bottom=48)


# --------------------------------------------------------------------------- E. costs and taxes
def costs_figure(lab, selected: Sequence[str]) -> go.Figure:
    """Where the money went: fees and taxes of the frozen accounting, stacked per portfolio (EUR)."""
    ids = lab.ordered(selected)
    if not ids:
        return empty_figure()
    s = lab.summary.loc[ids]
    parts = (("Frais courants", s["fees_in_path"], "frais de transaction et droits de garde"),
             ("Frais de liquidation", s["liquidation_costs"], "vente de toutes les lignes au 29/12/2023"),
             ("Impôts courants", s["interim_taxes"], "PFU sur plus-values du CTO et du Bitcoin, chaque année"),
             ("Impôts de sortie", s["exit_taxes"], "PEA, CTO, Bitcoin à la liquidation"))
    fig = go.Figure()
    for (name, values, detail), color in zip(parts, COST_COLORS):
        extra = ""
        if name == "Impôts de sortie":
            extra = [f"<br>dont PEA {F.eur(s.loc[i, 'tax_exit_pea'])} · CTO {F.eur(s.loc[i, 'tax_exit_cto'])} · "
                     f"Bitcoin {F.eur(s.loc[i, 'tax_exit_btc'])}" for i in ids]
        else:
            extra = [""] * len(ids)
        fig.add_trace(go.Bar(y=ids, x=values, name=name, orientation="h", marker=dict(color=color, line=dict(color=SURFACE, width=2)),
                             customdata=[[F.eur(v), detail, e] for v, e in zip(values, extra)],
                             hovertemplate="%{y} — " + name + " : <b>%{customdata[0]}</b><br>%{customdata[1]}%{customdata[2]}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.45)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Montant cumulé 2014–2023 (€)", tickformat=",.0f")
    return _layout(fig, "Frais et impôts de la comptabilité Research",
                   "Simulation N100 : 100 000 € investis le 1er oct. 2014, liquidation complète le 29 déc. 2023. "
                   "Frais de fonds (TER) et coût du levier déjà inclus dans les prix : jamais déduits une seconde fois.",
                   170 + 46 * len(ids), top=104)


def gross_net_figure(lab, selected: Sequence[str]) -> go.Figure:
    """Terminal wealth on three bases: gross, daily path at the end, net after the final sale and exit taxes."""
    ids = lab.ordered(selected)
    if not ids:
        return empty_figure()
    s = lab.summary.loc[ids]
    marks = (("Brut — sans frais ni impôts (simulation séparée)", s["terminal_gross"], "circle-open"),
             ("Trajectoire quotidienne — avant vente finale et impôts de sortie", s["final_value"], "line-ns-open"),
             ("Net — après vente finale et impôts de sortie", s["terminal_net"], "circle"))
    fig = go.Figure()
    xs, ys = [], []
    for sid in ids:
        vals = [s.loc[sid, "terminal_gross"], s.loc[sid, "final_value"], s.loc[sid, "terminal_net"]]
        xs += [min(vals), max(vals), None]
        ys += [sid, sid, None]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=AXIS, width=2), hoverinfo="skip", showlegend=False))
    colors = [style(lab, sid)["color"] for sid in ids]
    for name, values, symbol in marks:
        fig.add_trace(go.Scatter(x=values, y=ids, mode="markers", name=name, showlegend=False,
                                 marker=dict(size=13 if symbol != "line-ns-open" else 16, symbol=symbol, color=colors,
                                             line=dict(width=2.5, color=colors if symbol != "circle" else SURFACE)),
                                 customdata=[F.eur(v) for v in values],
                                 hovertemplate="%{y} — " + name.split(" — ")[0] + " : <b>%{customdata}</b><extra></extra>"))
    fig.add_traces(_legend_keys([(label, symbol) for label, (_, _, symbol) in
                                zip(("Brut", "Valeur quotidienne", "Net après liquidation"), marks)]))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Patrimoine au 29/12/2023 (€)", tickformat=",.0f")
    return _layout(fig, "Patrimoine final : brut, trajectoire quotidienne, net",
                   "Le brut vient d'une simulation Research séparée sans frais ni impôts (règles de bandes et arrondis "
                   "identiques) : l'écart brut–net n'est donc pas exactement la somme des frais et impôts.",
                   170 + 40 * len(ids), top=104)


COSTS_OVER_TIME = (("fees", "Frais cumulés", "Frais de transaction et de garde cumulés (€)"),
                   ("taxes", "Impôts payés cumulés", "Impôts payés en cours de route, cumulés (€)"))


def costs_over_time_figure(lab, selected: Sequence[str]) -> go.Figure:
    ids = lab.ordered(selected)
    if not ids:
        return empty_figure()
    fees = lab.curves["cum_friction"] + lab.curves["cum_custody"]
    taxes = lab.curves["cum_tax"]
    fig = go.Figure()
    for sid in ids:
        st = style(lab, sid)
        fig.add_trace(go.Scatter(x=fees.index, y=fees[sid], name=sid, line=dict(color=st["color"], width=st["width"], dash=st["dash"]),
                                 hovertemplate=f"{sid} : %{{y:,.0f}} €<extra></extra>"))
    options = [(label, [{"y": [(fees if key == "fees" else taxes)[sid].to_numpy() for sid in ids]}, {"yaxis.title.text": title}])
               for key, label, title in COSTS_OVER_TIME]
    fig.update_layout(updatemenus=[_buttons(options)], hovermode="x unified")
    fig.update_yaxes(title_text=COSTS_OVER_TIME[0][2], tickformat=",.0f")
    _time_axis(fig, lab)
    return _layout(fig, "Frais et impôts payés au fil du temps",
                   "Montants cumulés inclus dans la valeur quotidienne (hors vente finale et impôts de sortie).", 420, top=96)
