"""Execute only the three guarded V2 notebooks and optionally render offline Plotly previews.

Usage: python scripts/validate_v2.py --render
Outputs stay in the git-ignored outputs/v2 directory. Never executes V1 or archived notebooks.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import asyncio

import nbformat
import plotly.io as pio
from nbclient import NotebookClient
from nbconvert import HTMLExporter

from portfolio_lab.v2 import charts, checks
from portfolio_lab.v2.bridge import load_lab
from portfolio_lab.v2.guard import (CutoffViolation, guard_from_settings, scan_text_for_dates_after,
                                    sha256_file)
from portfolio_lab.v2.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ("01_comparaison_strategies", "02_robustesse_historique", "03_allocations_enveloppes")


def execute_notebooks(out: Path) -> None:
    for name in NOTEBOOKS:
        nb = nbformat.read(ROOT / "notebooks" / f"{name}.ipynb", as_version=4)
        nb.cells.append(nbformat.v4.new_code_cell(
            "# Validation des interactions dans ce noyau neuf\n"
            "initial_selection = lab.selection\n"
            "lab.select(lab.lab.ids)\n"
            "assert len(lab.selection) == 11\n"
            "lab._buttons['N07'].click()\n"
            "assert 'N07' not in lab.selection\n"
            "lab.select([])\n"
            "assert not lab.selection\n"
            "lab.select(initial_selection)\n"
            "from portfolio_lab.v2.checks import all_ok\n"
            "assert all_ok(lab.lab)\n",
            metadata={"tags": ["validation"]}))
        # Bind the fresh python3 kernel to this interpreter, even outside an activated venv.
        env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
                   PYTHONDONTWRITEBYTECODE="1")
        client = NotebookClient(nb, timeout=180, kernel_name="python3", record_timing=False,
                                resources={"metadata": {"path": str(ROOT / "notebooks")}})
        client.execute(env=env)
        # nbclient records update_display_data messages from the interaction probe in its cell.
        # Keep the validated default views in the deliverable, without duplicate probe outputs.
        nb.cells.pop()
        text = nbformat.writes(nb)
        if scan_text_for_dates_after(text):
            raise CutoffViolation(f"{name} : date interdite dans les sorties ; export annulé.")
        (out / f"{name}.executed.ipynb").write_text(text, encoding="utf-8")
        # nbconvert does not render Plotly's native MIME by itself. Embed the local JS bundle
        # once so the exported figures and their selectors work without a CDN.
        html_nb = nbformat.reads(text, as_version=4)
        include_bundle = True
        for cell in html_nb.cells:
            for output in cell.get("outputs", []):
                data = output.get("data", {})
                plot = data.pop("application/vnd.plotly.v1+json", None)
                if plot:
                    config = plot.pop("config", charts.CONFIG)
                    data["text/html"] = pio.to_html(plot, config=config, full_html=False,
                                                     include_plotlyjs=True if include_bundle else False)
                    include_bundle = False
        html, _ = HTMLExporter().from_notebook_node(html_nb)
        (out / f"{name}.html").write_text(html, encoding="utf-8")
        print(f"EXECUTED {name}: {sum(c.cell_type == 'code' for c in nb.cells)} cells", flush=True)


def render_figures(lab, out: Path) -> None:
    """Real SVG/PNG renders, including narrow displays and alternate views."""
    charts.setup()
    pio.kaleido.scope.mathjax = None  # no mathematical typesetting or network access needed
    directory = out / "figures"
    directory.mkdir(exist_ok=True)
    figures = {name: getattr(charts, name)(lab, "N07" if name == "allocation_figure" else lab.ids)
               for name in dir(charts) if name.endswith("_figure") and name != "empty_figure"}
    figures["frontier_maxdd"] = charts.frontier_figure(lab, lab.ids, "max_drawdown")
    figures["allocation_wrappers"] = charts.allocation_figure(lab, "N07", "wrappers")
    figures["rolling_five_years"] = charts.rolling_figure(lab, lab.ids, "r5")
    for name, figure in figures.items():
        print(f"RENDERING {name}", flush=True)
        for width in (1100, 640):
            # Avoid stale text/layout state between unrelated figures in bundled Chromium.
            pio.kaleido.scope._shutdown_kaleido()
            figure.write_image(str(directory / f"{name}-{width}.svg"), width=width)
            figure.write_image(str(directory / f"{name}-{width}.png"), width=width, scale=1)
        print(f"RENDERED {name}: 1100 + 640 px", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true", help="Rendus PNG/SVG (kaleido, dépendance de développement)")
    parser.add_argument("--figures-only", action="store_true", help="Ne pas réexécuter les notebooks déjà validés")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    settings = load_settings(ROOT)
    guard = guard_from_settings(settings)
    guard.report()  # authorization, cutoff and hashes precede all performance reads
    before = {n: sha256_file(guard.path(n)) for n in guard.names}
    out = ROOT / "outputs" / "v2"
    out.mkdir(parents=True, exist_ok=True)
    lab = load_lab(ROOT)
    assert checks.all_ok(lab), "Frozen financial reproduction failed"
    if not args.figures_only:
        execute_notebooks(out)
    if args.render:
        render_figures(lab, out)
    after = {n: sha256_file(guard.path(n)) for n in guard.names}
    assert before == after, "Research artifacts changed"
    summary = {"portfolios": len(lab.ids), "metrics_passed": int(checks.reproduction(lab)["Conforme"].sum()),
               "accounting_passed": int(checks.accounting(lab)["Conforme"].sum()),
               "cutoff": str(settings.cutoff.date()), "research_hashes_unchanged": before == after,
               "artifact_hashes": after}
    (out / "validation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "artifact_hashes"}), flush=True)


if __name__ == "__main__":
    main()
