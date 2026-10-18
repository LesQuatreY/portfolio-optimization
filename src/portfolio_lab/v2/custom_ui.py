"""French notebook builder. Opening, editing and saving never load market data."""
from __future__ import annotations

import html
import json
from pathlib import Path

import ipywidgets as W
import pandas as pd
import plotly.graph_objects as go
from IPython.display import HTML, display

from . import charts
from .custom import (ROOT, MODES, DataUnavailable, PortfolioSpec, availability, load_catalog,
                     load_spec, save_spec, load_validated_panel, simulate)
from . import custom_analytics as A


class PortfolioBuilder:
    def __init__(self, project_dir: Path | None = None, *, panel_loader=None):
        if project_dir is not None and Path(project_dir).resolve() != ROOT:
            raise ValueError("Le constructeur utilise le dossier de ce dépôt.")
        self.catalog = load_catalog()
        self.folder = ROOT / "config/v2/portfolios"
        self.spec = load_spec(self.folder / "mon_portefeuille_diversifie.json")
        self.panel_loader = panel_loader or load_validated_panel
        self.result = None
        self._updating = True
        self.name = W.Text(value=self.spec.name, description="Nom", layout=W.Layout(width="100%"))
        self.capital = W.FloatText(value=self.spec.initial_capital, description="Capital (€)")
        self.cost = W.FloatText(value=self.spec.cost_bps, description="Frais (pb)")
        self.frequency = W.Dropdown(options=[(v, k) for k, v in MODES.items()], value=self.spec.rebalance,
                                    description="Rééquilibrage", style={"description_width": "initial"})
        self.weights, self.enabled = {}, {}
        rows = []
        for asset, item in self.catalog.items():
            check = W.Checkbox(value=asset in self.spec.weights, description=item["label"], indent=False,
                               layout=W.Layout(width="330px"))
            weight = W.BoundedFloatText(value=self.spec.weights.get(asset, 0) * 100, min=0, max=100,
                                       step=1, description="%", layout=W.Layout(width="150px"))
            status = {"validated": "Validée", "missing": "Manquante"}.get(item["status"], "À vérifier")
            rows.append(W.HBox([check, weight, W.HTML(html.escape(status))],
                               layout=W.Layout(flex_flow="row wrap", align_items="center")))
            self.enabled[asset], self.weights[asset] = check, weight
            check.observe(self._changed, names="value")
            weight.observe(self._changed, names="value")
        self.total = W.HTML()
        self.status = W.HTML()
        self.preview = W.Output()
        self.output = W.Output()
        self.saved = W.Dropdown(description="Configuration", style={"description_width": "initial"},
                                layout=W.Layout(width="500px", max_width="100%"))
        self.save_button = W.Button(description="Enregistrer")
        self.load_button = W.Button(description="Charger")
        self.run_button = W.Button(description="Simuler l’historique", button_style="primary")
        self.compare_button = W.Button(description="Comparer à Research", disabled=True)
        from .settings import load_settings
        settings = load_settings(ROOT)
        self.research = W.SelectMultiple(options=[s.id for s in settings.strategies],
                                        value=("N07", "D2_25", "B1", "B2", "B1M", "B2M"),
                                        description="Research", rows=6)
        self.save_button.on_click(self._save)
        self.load_button.on_click(self._load)
        self.run_button.on_click(self._run)
        self.compare_button.on_click(self._compare)
        for control in (self.name, self.capital, self.cost, self.frequency):
            control.observe(self._changed, names="value")
        self._refresh_saved()
        provenance = W.Output()
        with provenance:
            display(pd.DataFrame([{**{"Actif": key}, **value} for key, value in self.catalog.items()]))
        details = W.Accordion(children=[provenance])
        details.set_title(0, "Sources et état des validations")
        details.selected_index = None
        self.widget = W.VBox([
            W.HTML("<h2>Créer un portefeuille</h2><p>Historique autorisé : 01/10/2014–29/12/2023. "
                   "Les actifs absents ne sont jamais remplacés. Les poids restent ceux que vous choisissez.</p>"),
            self.name, *rows, self.total,
            W.HBox([self.frequency, self.capital, self.cost], layout=W.Layout(flex_flow="row wrap")),
            W.HTML("<small>1 pb = 0,01 % de chaque achat ou vente, achat initial compris. "
                   "Aucun impôt personnel ni frais de liquidation. Les frais des fonds restent inclus dans les séries.</small>"),
            W.HBox([self.saved, self.load_button, self.save_button], layout=W.Layout(flex_flow="row wrap")),
            self.preview, self.status, self.run_button, details,
            W.HBox([self.research, self.compare_button], layout=W.Layout(flex_flow="row wrap")), self.output],
            layout=W.Layout(width="100%", max_width="1050px"))
        self._updating = False
        self._changed()

    def current_spec(self):
        return PortfolioSpec(self.name.value,
            {a: self.weights[a].value / 100 for a in self.catalog if self.enabled[a].value},
            rebalance=self.frequency.value, initial_capital=self.capital.value, cost_bps=self.cost.value,
            start=self.spec.start, end=self.spec.end)

    def _refresh_saved(self, selected=None):
        options = []
        for path in sorted(self.folder.glob("*.json")):
            try:
                spec = load_spec(path)
                options.append((spec.name + " · " + spec.identity[:8], path.name))
            except (ValueError, TypeError, OSError):
                continue
        self.saved.options = options
        if selected in [p for _, p in options]:
            self.saved.value = selected

    def _changed(self, *_):
        if self._updating:
            return
        self.result = None
        self.compare_button.disabled = True
        self.output.clear_output(wait=False)
        total = sum(self.weights[a].value for a in self.catalog if self.enabled[a].value)
        for asset in self.catalog:
            self.weights[asset].disabled = not self.enabled[asset].value
        self.total.value = f"<b>Total : {total:.2f} %</b>"
        try:
            spec = self.current_spec()
            blocked = availability(spec, self.catalog)
            self.save_button.disabled = False
            self.run_button.disabled = bool(blocked) and self.panel_loader is load_validated_panel
            self.status.value = ("<b>Simulation historique indisponible</b><ul>" + "".join(
                "<li>" + html.escape(line) + "</li>" for line in blocked) + "</ul>" if blocked else
                "<b>Configuration valide ; les contrôles des fichiers seront vérifiés à l'exécution.</b>")
            with self.preview:
                self.preview.clear_output(wait=True)
                display(allocation_preview(spec))
        except ValueError as exc:
            self.save_button.disabled = self.run_button.disabled = True
            self.status.value = "<b>Configuration invalide :</b> " + html.escape(str(exc))
            self.preview.clear_output(wait=False)

    def _save(self, *_):
        try:
            path = save_spec(self.current_spec())
            self._refresh_saved(path.name)
            self.status.value += "<p>Configuration enregistrée.</p>"
        except (ValueError, OSError) as exc:
            self.status.value = html.escape(str(exc))

    def _load(self, *_):
        try:
            if not self.saved.value:
                return
            spec = load_spec(self.folder / self.saved.value)
            if not set(spec.weights).issubset(self.catalog):
                raise ValueError("La configuration contient un actif non approuvé.")
            self._updating = True
            self.spec = spec
            self.name.value, self.capital.value = spec.name, spec.initial_capital
            self.cost.value, self.frequency.value = spec.cost_bps, spec.rebalance
            for a in self.catalog:
                self.enabled[a].value = a in spec.weights
                self.weights[a].value = spec.weights.get(a, 0) * 100
        except (ValueError, TypeError, OSError) as exc:
            self.status.value = html.escape(str(exc))
            return
        finally:
            self._updating = False
        self._changed()

    def run(self):
        spec = self.current_spec()
        # Loader itself fails closed, even if a widget callback is invoked directly.
        panel = self.panel_loader(spec)
        self.result = simulate(spec, panel)
        self.compare_button.disabled = self.result.synthetic
        return self.result, panel

    def _run(self, *_):
        self.output.clear_output(wait=True)
        try:
            result, panel = self.run()
            with self.output:
                render_result(result, panel)
        except (ValueError, RuntimeError, OSError) as exc:
            self.result = None
            self.compare_button.disabled = True
            with self.output:
                display(HTML("<p><b>Simulation indisponible :</b> " + html.escape(str(exc)) + "</p>"))

    def _compare(self, *_):
        if self.result is None:
            return
        with self.output:
            try:
                if self.result.synthetic:
                    raise DataUnavailable("Comparaison Research interdite pour une démonstration synthétique.")
                from .bridge import load_lab
                figs, table = A.comparison_figures(self.result, load_lab(ROOT), self.research.value)
                display(HTML("<b>Bases différentes :</b> la trajectoire personnalisée n'inclut pas la fiscalité. "
                             "Research inclut ses frais et impôts intermédiaires. Aucun classement fiscal commun."))
                display(table)
                for fig in figs.values():
                    display(fig)
            except (ValueError, RuntimeError, OSError) as exc:
                display(HTML(html.escape(str(exc))))


def allocation_preview(spec):
    charts.setup()
    fig = go.Figure(go.Pie(labels=list(spec.weights), values=list(spec.weights.values()), hole=0.55,
                          textinfo="label+percent", sort=False,
                          marker=dict(colors=[A.ASSET_COLORS.get(a, "#898781") for a in spec.weights])))
    charts._layout(fig, "Allocation cible — " + html.escape(spec.name),
                   "Configuration enregistrable ; aucune performance historique calculée", 410)
    return fig


def render_result(result, panel=None):
    display(HTML("<h3>" + html.escape(result.spec.name) + "</h3><p>" + (
        "<b>Données synthétiques : validation du logiciel uniquement.</b>" if result.synthetic else
        "Simulation économique : frais proportionnels, hors fiscalité personnelle et liquidation.") + "</p>"))
    display(A.summary(result))
    outputs, titles = [], []
    names = {"wealth": "Patrimoine", "drawdown": "Drawdowns", "rolling": "Glissants",
             "allocation": "Allocations", "annual": "Années", "costs": "Frais", "turnover": "Rotation"}
    for key, fig in A.figures(result).items():
        out = W.Output()
        with out:
            display(fig)
        outputs.append(out)
        titles.append(names[key])
    stability, correlations = A.stability(result)
    out = W.Output()
    with out:
        display(stability if len(stability) else HTML("Fenêtres historiques non couvertes."))
        for name, corr in correlations.items():
            display(HTML("<b>Corrélations : " + html.escape(name) + "</b>"), corr)
        if panel is not None:
            display(pd.concat({MODES[k]: A.summary(v) for k, v in A.sensitivities(result.spec, panel).items()}))
    outputs.append(out)
    titles.append("Stabilité et sensibilités")
    out = W.Output()
    with out:
        display(HTML("<pre style='white-space:pre-wrap'>" + html.escape(json.dumps(
            result.metadata(), ensure_ascii=False, indent=2)) + "</pre>"))
        display(result.trades)
    outputs.append(out)
    titles.append("Provenance et transactions")
    tabs = W.Tab(children=outputs)
    for i, title in enumerate(titles):
        tabs.set_title(i, title)
    display(tabs)


def open_builder():
    builder = PortfolioBuilder()
    display(builder.widget)
    return builder
