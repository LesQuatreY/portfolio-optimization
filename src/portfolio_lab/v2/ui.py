"""Interactive session of the V2 notebooks: one shared portfolio selector, short ready-made views.

Every view is ``render(selection, **controls) -> objects`` (a Plotly figure, a styled table, HTML or
text), shown as notebook outputs updated in place when the selection or a control changes.
Parsed data are cached, integrity is rechecked on opening; controls never re-run a backtest.
Without ipywidgets the views render once, statically, for the configured default selection.
User-facing text is French.
"""
from __future__ import annotations

import html
from typing import Callable, Sequence

from pandas.io.formats.style import Styler
from IPython.display import HTML, Markdown, display

from . import charts, checks, tables
from . import formatting as F
from .bridge import StrategyLab, load_lab

try:
    import ipywidgets as W
    HAS_WIDGETS = True
except ImportError:          # static fallback; Plotly legends stay clickable
    W = None
    HAS_WIDGETS = False

QUESTIONS = (("idee", "L'idée"), ("actifs", "Actifs détenus"), ("enveloppes", "Comptes"), ("exposition", "Exposition au Nasdaq"),
             ("levier", "Levier"), ("allocation", "Statique ou dynamique"), ("indicateur", "Indicateur surveillé"),
             ("observation", "Fréquence d'observation"), ("declencheur", "Déclencheur des ordres"), ("ordres", "Ordres passés"),
             ("maintenance", "Entretien et rééquilibrage"), ("forces", "Points forts (Research)"),
             ("faiblesses", "Points faibles (Research)"), ("stabilite", "Constats de stabilité V11.2"))
BASES_HTML = """
<div style="font-size:13px;line-height:1.55;max-width:980px">
<p><b>Trois bases de mesure, jamais mélangées.</b></p>
<ol style="margin-top:0">
<li><b>Brut</b> — simulation Research séparée, sans aucun frais ni impôt (CAGR brut). Les frais des fonds (TER) et le coût
du levier de LQQ restent inclus dans les prix : ils ne sont jamais retirés une seconde fois.</li>
<li><b>Valeur quotidienne</b> — la trajectoire suivie chaque jour : après frais de transaction, droits de garde et impôts
réellement payés en cours de route (PFU du CTO et du Bitcoin chaque fin d'année), <i>sans</i> impôt de sortie latent.
Volatilité, MaxDD journalier, Sharpe, drawdowns et rendements glissants sont calculés sur cette base.</li>
<li><b>Patrimoine net</b> — au 29 décembre 2023, tout est vendu (frais de la vente finale) puis les impôts de sortie sont
payés (PEA 18,6 % de prélèvements sociaux sur le gain, CTO et Bitcoin 31,4 %). Le CAGR net en découle.
Ces impôts ne sont jamais appliqués aux rendements quotidiens.</li>
</ol>
<p style="color:#52514e">Comptabilité figée de Research (simulation N100) : 100 000 € d'argent nouveau, PEA supposé de plus de
5 ans à la sortie, tarifs Bourse Direct relevés le 14/10/2026 par Research, fiscalité 2026. Ce ne sont <i>pas</i> les
comptes réels de l'investisseur : la modélisation des comptes réels (PEA, CTO, assurance-vie, Bitcoin)
viendra dans une version ultérieure.</p>
</div>"""
PROXY_HTML = """
<div style="font-size:13px;line-height:1.55;max-width:980px">
<p><b>Données observées, reconstituées ou synthétiques.</b> Plusieurs lignes n'existaient pas (ou pas encore sous leur forme
investissable) sur 2014–2023 : leur historique est reconstitué par Research. <b>Proxy</b> = série d'un autre instrument ou
indice (or : GLD converti en EUR ; consommation de base : XLP en EUR, −0,35 %/an pour COSE). <b>Synthétique</b> = série
calculée à partir d'un taux (monétaire PEA : €STR/EONIA − 0,25 %/an). Les résultats d'un portefeuille « proxy partiel »
dépendent donc en partie de ces approximations ; la part moyenne reconstituée est indiquée pour chacun.</p>
</div>"""


def _luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ink(hex_color: str) -> str:
    """Readable label colour on a filled button (white on dark fills, ink on light fills)."""
    return "#0b0b0b" if _luminance(hex_color) > 0.28 else "white"


def _displayable(obj):
    if isinstance(obj, Styler):
        return HTML('<div role="region" aria-label="Tableau défilant" tabindex="0" '
                    'style="max-width:100%;overflow-x:auto">' + obj.to_html() + '</div>')
    return Markdown(obj) if isinstance(obj, str) else obj


def show(obj) -> None:
    for item in obj if isinstance(obj, (list, tuple)) else [obj]:
        display(_displayable(item))


class View:
    """Output areas bound to a render function, the shared selection and the view's own controls.

    The first render creates ordinary cell outputs with a display id; later renders replace them in
    place (``DisplayHandle.update``), so figures stay plain notebook outputs (no Output widget).
    """

    def __init__(self, session: "LabSession", name: str, render: Callable, controls: dict | None = None,
                 use_selection: bool = True):
        self.session, self.name, self.render, self.use_selection = session, name, render, use_selection
        self.controls = controls or {}
        self.last = None
        self.handles: list = []

    def values(self) -> dict:
        return {k: (w.value if HAS_WIDGETS and isinstance(w, W.Widget) else w) for k, w in self.controls.items()}

    def compute(self):
        ids = self.session.selection if self.use_selection else list(self.session.lab.ids)
        self.last = self.render(ids, **self.values())
        self.session.rendered[self.name] = self.last
        return self.last

    def refresh(self, *_):
        objs = self.compute()
        items = list(objs) if isinstance(objs, (list, tuple)) else [objs]
        if not self.handles:
            self.handles = [display(_displayable(item), display_id=True) for item in items]
            return
        for handle, item in zip(self.handles, items):
            handle.update(_displayable(item))

    def show(self) -> None:
        widgets = [w for w in self.controls.values() if HAS_WIDGETS and isinstance(w, W.Widget)]
        if widgets:
            display(W.HBox(widgets, layout=W.Layout(flex_flow="row wrap")))
            for w in widgets:
                w.observe(self.refresh, "value")
        if self.use_selection and HAS_WIDGETS:
            self.session.subscribe(self.refresh)
        self.refresh()


class LabSession:
    """Shared state of one notebook: the loaded lab, the current selection and the live views."""

    def __init__(self, lab: StrategyLab, selection: Sequence[str] | None = None):
        charts.setup()
        self.lab = lab
        self._ids = lab.ordered(selection if selection is not None else lab.settings.default_selection)
        self._listeners: list[Callable] = []
        self._buttons: dict = {}
        self.views: dict[str, View] = {}
        self.rendered: dict = {}

    @classmethod
    def open(cls, project_dir=None, banner: bool = True, selection: Sequence[str] | None = None) -> "LabSession":
        session = cls(load_lab(project_dir), selection)
        if banner:
            display(session.banner())
        return session

    # ------------------------------------------------------------------ selection
    @property
    def selection(self) -> list[str]:
        return list(self._ids)

    def select(self, ids: Sequence[str]) -> None:
        """Programmatic selection (also used by the quick-select buttons); unknown ids are ignored."""
        self._ids = self.lab.ordered(ids)
        self._restyle()
        self._notify()

    def toggle(self, sid: str) -> None:
        self.select([s for s in self._ids if s != sid] if sid in self._ids else [*self._ids, sid])

    def subscribe(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for callback in list(self._listeners):
            callback()

    def _restyle(self) -> None:
        for sid, button in self._buttons.items():
            on = sid in self._ids
            color = charts.style(self.lab, sid)["color"]
            button.style.button_color = color if on else "#efeeea"
            button.style.text_color = _ink(color) if on else charts.TEXT2
            button.style.font_weight = "600" if on else "400"

    def selector(self):
        """Grouped toggle buttons (colour = the portfolio's colour in every chart) and quick selections."""
        lab = self.lab
        if not HAS_WIDGETS:
            return Markdown(f"*ipywidgets n'est pas installé : sélection fixe ({', '.join(self.selection)}). "
                            "Modifiez `default_selection` dans config/v2/lab.yaml, ou cliquez sur les légendes des graphiques.*")
        rows = []
        for label, ids in (("Stratégies", lab.strategies), ("Références", lab.benchmarks)):
            buttons = []
            for sid in ids:
                b = W.Button(description=sid, tooltip=f"{sid} — {lab.meta.loc[sid, 'name']}\n{lab.meta.loc[sid, 'role']}",
                             layout=W.Layout(width="auto", min_width="64px", height="30px", margin="2px"))
                b.on_click(lambda _, s=sid: self.toggle(s))
                self._buttons[sid] = b
                buttons.append(b)
            rows.append(W.HBox([W.HTML(f"<div style='width:92px;font-size:12px;color:{charts.TEXT2};line-height:34px'>{label}</div>"),
                                *buttons], layout=W.Layout(flex_flow="row wrap", align_items="center")))
        quick = []
        for text, ids in (("Sélection par défaut", lab.settings.default_selection), ("Stratégies + B1M", [*lab.strategies, "B1M"]),
                          ("Tout", lab.ids), ("Aucun", [])):
            b = W.Button(description=text, layout=W.Layout(width="auto", height="28px", margin="2px"))
            b.on_click(lambda _, ids=ids: self.select(ids))
            quick.append(b)
        self._restyle()
        note = W.HTML(f"<span style='font-size:11.5px;color:{charts.TEXT2}'>Cliquez pour ajouter ou retirer un portefeuille : "
                      "tous les graphiques et tableaux de ce notebook suivent la sélection. Couleur = identité de la stratégie ; "
                      "références en gris (tirets : Nasdaq seul, pointillés : + or et Bitcoin ; foncé = ×2).</span>")
        return W.VBox([*rows, W.HBox([W.HTML("<div style='width:92px'></div>"), *quick]), note],
                      layout=W.Layout(border=f"1px solid {charts.GRID}", padding="8px 10px", margin="4px 0 8px"))

    # ------------------------------------------------------------------ generic view
    def view(self, name: str, render: Callable, controls: dict | None = None, use_selection: bool = True) -> None:
        """Display a live view (controls first, then its outputs); it follows the shared selection."""
        v = View(self, name, render, controls, use_selection)
        self.views[name] = v
        v.show()

    def banner(self) -> HTML:
        lab = self.lab
        start, end = lab.period
        ok = checks.all_ok(lab)
        n = len(checks.reproduction(lab))
        state = (f"reproduction Research : {n}/{n} indicateurs conformes" if ok else
                 "<b style='color:#d03b3b'>contrôle de reproduction en échec — voir « Méthode »</b>")
        return HTML(f"<div style='font-family:{charts.FONT};font-size:12.5px;color:{charts.TEXT2};border-left:4px solid {charts.AXIS};"
                    f"background:#f7f7f4;padding:7px 12px;margin:2px 0 6px'>"
                    f"<b style='color:{charts.TEXT}'>Portfolio Lab V2</b> · {len(lab.ids)} portefeuilles gelés · données de "
                    f"développement du {F.date(start)} au {F.date(end)} · <b>période TEST 2024–2026 verrouillée</b> · "
                    f"{len(lab.guard_report)} artefacts vérifiés (SHA-256) · {state}</div>")

    # ------------------------------------------------------------------ notebook 01: comparison
    def kpis(self):
        return self.view("kpis", lambda ids: tables.kpi_table(self.lab, ids))

    def frontier(self):
        return self.view("frontier", lambda ids: charts.frontier_figure(self.lab, ids))

    def wealth(self):
        return self.view("wealth", lambda ids: charts.wealth_figure(self.lab, ids))

    def details(self):
        def render(ids):
            content = _displayable(tables.detail_table(self.lab, ids))
            if not isinstance(content, HTML):
                return content
            return HTML('<details><summary style="cursor:pointer">Afficher le détail des indicateurs</summary>'
                        + content.data + '</details>')
        return self.view("details", render)

    def card(self, default: str | None = None):
        lab = self.lab
        default = default or (self.selection[0] if self.selection else lab.ids[0])
        options = [(f"{s} — {lab.meta.loc[s, 'name']}", s) for s in lab.ids]
        pick = W.Dropdown(options=options, value=default, description="Portefeuille", layout=W.Layout(width="100%", max_width="560px"),
                          style={"description_width": "initial"}) if HAS_WIDGETS else default
        return self.view("card", lambda ids, Portefeuille: [self.card_html(Portefeuille), tables.config_table(lab, Portefeuille)],
                         {"Portefeuille": pick}, use_selection=False)

    def card_html(self, sid: str) -> HTML:
        lab = self.lab
        meta, s, card = lab.meta.loc[sid], lab.summary.loc[sid], lab.cards.get(sid, {})
        st = charts.style(lab, sid)
        tiles = [("CAGR net", F.pct(s["cagr_net"])), ("Volatilité", F.pct(s["volatility"])),
                 ("MaxDD journalier", F.pct(s["max_drawdown"])), ("Sharpe", F.ratio(s["sharpe"])),
                 ("Patrimoine net", F.eur(s["terminal_net"])), ("Frais totaux", F.eur(s["fees_total"])),
                 ("Impôts totaux", F.eur(s["taxes_total"])), ("Exposition Nasdaq moyenne", F.times(s["ndx_expo_mean"]))]
        strip = "".join(f"<div style='padding:6px 10px;border:1px solid {charts.GRID};border-radius:6px;min-width:118px'>"
                        f"<div style='font-size:11px;color:{charts.TEXT2}'>{a}</div><div style='font-size:15px;font-weight:600'>{b}</div></div>"
                        for a, b in tiles)
        badge = lambda text, bg, fg: f"<span style='padding:2px 8px;border-radius:10px;font-size:11.5px;background:{bg};color:{fg}'>{text}</span>"  # noqa: E731
        status = badge(meta["data_status"], "#f2f2ee" if meta["data_status"] == "Observé" else "#fff4e0", charts.TEXT2)
        cls = badge(f"Research V11.2 : {meta['classification']}", "#eef3fb", "#1c5cab")
        qa = "".join(f"<tr><td style='vertical-align:top;text-align:left;padding:4px 14px 4px 0;color:{charts.TEXT2};white-space:nowrap'>{q}</td>"
                     f"<td style='text-align:left;padding:4px 0'>{html.escape(str(card[k]))}</td></tr>" for k, q in QUESTIONS if k in card)
        return HTML(f"""<div style="font-family:{charts.FONT};font-size:13px;line-height:1.45;max-width:1080px">
<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:4px 0 6px">
<span style="width:14px;height:14px;border-radius:3px;background:{st['color']};display:inline-block"></span>
<span style="font-size:17px;font-weight:700">{sid} — {html.escape(meta['name'])}</span>{status}{cls}</div>
<div style="color:{charts.TEXT2};margin-bottom:6px">{meta['type']} · {html.escape(meta['role'])}</div>
<div style="display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 10px">{strip}</div>
<details><summary style="cursor:pointer;font-weight:600;margin:6px 0">Fiche détaillée (rédigée par Research d'après la configuration gelée)</summary>
<table style="border-collapse:collapse;margin:4px 0">{qa}</table></details></div>""")

    def method(self):
        lab = self.lab
        if not HAS_WIDGETS:
            for obj in (HTML(BASES_HTML), HTML(PROXY_HTML), tables.provenance_table(lab, lab.ids), tables.sources_table(lab),
                        tables.reproduction_table(lab), tables.accounting_table(lab), tables.guard_table(lab)):
                show(obj)
            return None
        panels = [("Lire les résultats : brut, valeur quotidienne, net", [HTML(BASES_HTML)]),
                  ("Données reconstituées (proxies)", [HTML(PROXY_HTML), tables.provenance_table(lab, lab.ids), tables.sources_table(lab)]),
                  ("Contrôles de reproduction et de comptabilité", [tables.reproduction_table(lab), tables.accounting_table(lab)]),
                  ("Verrou de la période TEST et artefacts lus", [tables.guard_table(lab)])]
        outs = []
        for _, objs in panels:
            out = W.Output()
            with out:
                show(objs)
            outs.append(out)
        acc = W.Accordion(children=outs, selected_index=None)
        for i, (title, _) in enumerate(panels):
            acc.set_title(i, title)
        self.rendered["method"] = panels
        return acc

    # ------------------------------------------------------------------ notebook 02: robustness
    def rolling(self):
        options = [(title, key) for key, (title, _) in charts.ROLLING.items()]
        pick = W.Dropdown(options=options, value="r3", description="Indicateur", style={"description_width": "initial"},
                          layout=W.Layout(width="100%", max_width="420px")) if HAS_WIDGETS else "r3"
        return self.view("rolling", lambda ids, Indicateur: charts.rolling_figure(self.lab, ids, Indicateur), {"Indicateur": pick})

    def chronology(self):
        return self.view("chronology", lambda ids: charts.chronology_figure(self.lab, ids))

    def calendar(self):
        return self.view("calendar", lambda ids: charts.calendar_figure(self.lab, ids))

    def crises(self):
        return self.view("crises", lambda ids: charts.crisis_figure(self.lab, ids))

    def recovery(self):
        return self.view("recovery", lambda ids: tables.recovery_table(self.lab, ids))

    def statistics(self):
        return self.view("statistics", lambda ids: tables.statistics_table(self.lab, ids))

    # ------------------------------------------------------------------ notebook 03: allocations and wrappers
    def allocation(self, default: str = "N07"):
        lab = self.lab
        options = [(f"{s} — {lab.meta.loc[s, 'name']}", s) for s in lab.ids]
        pick = W.Dropdown(options=options, value=default, description="Portefeuille", layout=W.Layout(width="100%", max_width="560px"),
                          style={"description_width": "initial"}) if HAS_WIDGETS else default
        return self.view("allocation", lambda ids, Portefeuille: charts.allocation_figure(lab, Portefeuille),
                         {"Portefeuille": pick}, use_selection=False)

    def exposure(self):
        return self.view("exposure", lambda ids: charts.exposure_figure(self.lab, ids))

    def costs(self):
        return self.view("costs", lambda ids: [charts.costs_figure(self.lab, ids), charts.gross_net_figure(self.lab, ids)])

    def cost_history(self):
        return self.view("cost_history", lambda ids: charts.costs_over_time_figure(self.lab, ids))

    def provenance(self):
        return self.view("provenance", lambda ids: [tables.provenance_table(self.lab, ids), tables.sources_table(self.lab)])
