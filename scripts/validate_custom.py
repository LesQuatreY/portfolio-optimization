"""Fresh-kernel builder checks + explicitly SYNTHETIC rendering, offline.

Nothing is written to source notebooks, Research or configuration. All exports ignored by Git.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

import nbformat
from nbclient import NotebookClient
import numpy as np
import pandas as pd
import plotly.io as pio

from portfolio_lab.v2 import custom as C, custom_analytics as A
from portfolio_lab.v2.custom_ui import allocation_preview
from portfolio_lab.v2.guard import scan_text_for_dates_after, sha256_file
from portfolio_lab.v2.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]


def synthetic_panel(spec):
    # Artificial business-day grid, NOT the Euronext calendar or historical observations.
    dates = pd.bdate_range(spec.start, spec.end)
    t = np.arange(len(dates))
    prices = pd.DataFrame({a: 100 * np.exp(.00005 * (i + 1) * t + .13 * np.sin(t / (35 + i * 11)))
                           for i, a in enumerate(spec.weights)}, index=dates)
    return C.PricePanel(prices, {a: {"source": "Artificial deterministic software fixture"}
                                for a in spec.weights}, synthetic=True, sessions=dates)


def main():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    out = ROOT / "outputs/v2_1"
    out.mkdir(parents=True, exist_ok=True)
    settings = load_settings(ROOT)
    before = {s.name: sha256_file(settings.research_root / s.path) for s in settings.artifacts}
    notebook = ROOT / "notebooks/04_portefeuilles_personnalises.ipynb"
    source_hash = sha256_file(notebook)
    nb = nbformat.read(notebook, as_version=4)
    nb.cells.append(nbformat.v4.new_code_cell(
        "from portfolio_lab.v2.custom import DataUnavailable\n"
        "identity = builder.current_spec().identity\n"
        "expected = builder.current_spec().to_dict()\n"
        "assert expected['name'] == 'Mon portefeuille diversifié'\n"
        "assert expected['weights'] == {'EM': .30, 'SP500': .30, 'WORLD': .15, 'CAC40': .10, 'GOLD': .10, 'BTC': .05}\n"
        "assert not builder.run_button.disabled and not builder.save_button.disabled\n"
        "# V2.2: the six sources are validated; the saved portfolio runs unchanged on real data.\n"
        "result, panel = builder.run()\n"
        "assert not result.synthetic and len(result.ledger) == 2368 and not builder.compare_button.disabled\n"
        "assert str(result.ledger.index[0].date()) == '2014-10-01' and str(result.ledger.index[-1].date()) == '2023-12-29'\n"
        "builder._run()\n"
        "builder.research.value = ('N07', 'D2_25', 'B1', 'B2', 'B1M', 'B2M', 'BRK_B')\n"
        "builder._compare()\n"
        "from portfolio_lab.v2 import custom_analytics as A\n"
        "from portfolio_lab.v2.bridge import load_lab\n"
        "view = A.common_calendar(load_lab(project), result.ledger.index)\n"
        "assert view.dropped_dates == ['2019-12-25'] and view.wealth.index.equals(result.ledger.index)\n"
        "brk = A.benchmark_result('BRK_B')\n"
        "assert brk.spec.rebalance == 'buy_hold' and brk.ledger.index.equals(result.ledger.index)\n"
        "figs, table = A.comparison_figures(result, view, ['N07', 'D2_25', 'B1', 'B2', 'B1M', 'B2M'], extra=[brk])\n"
        "assert len(table) == 8 and table.iloc[0]['CAGR net fiscal'] == 'Non calculé' and len(figs) == 3\n"
        "assert table.loc[brk.spec.name, 'CAGR net fiscal'] == 'Non calculé' and 'concentrée' in table.loc[brk.spec.name, 'Base']\n"
        "display(A.comparability_table(), A.summary(result), table)\n"
        "builder.weights['CAC40'].value = 12\n"
        "assert builder.run_button.disabled and builder.save_button.disabled\n"
        "builder.weights['CAC40'].value = 10\n"
        "assert builder.current_spec().identity == identity\n"
        "builder.saved.value = 'mon_portefeuille_diversifie.json'\n"
        "builder._load()\n"
        "assert builder.current_spec().identity == identity\n"
        "assert builder.result is None\n"
        "import tempfile, shutil\n"
        "from unittest.mock import patch\n"
        "from portfolio_lab.v2 import custom as C, custom_ui as UI, settings as S\n"
        "settings = S.load_settings()\n"
        "with tempfile.TemporaryDirectory() as temporary:\n"
        "    root = Path(temporary)\n"
        "    folder = root / 'config/v2/portfolios'\n"
        "    folder.mkdir(parents=True)\n"
        "    shutil.copy(project / 'config/v2/portfolios/mon_portefeuille_diversifie.json', folder)\n"
        "    shutil.copy(project / 'config/v2/custom_assets.yaml', root / 'config/v2')\n"
        "    with patch.object(C, 'ROOT', root), patch.object(UI, 'ROOT', root), patch.object(S, 'load_settings', lambda _: settings):\n"
        "        editor = UI.PortfolioBuilder()\n"
        "        editor.name.value = 'Brouillon'\n"
        "        editor.name.value = 'Mon portefeuille diversifié'\n"
        "        editor.save_button.click()\n"
        "        saved = editor.saved.value\n"
        "        assert C.load_spec(folder / saved).to_dict() == expected\n"
        "        reopened = UI.PortfolioBuilder()\n"
        "        reopened.weights['EM'].value = 25\n"
        "        reopened.weights['SP500'].value = 35\n"
        "        reopened.name.value = 'Autre'\n"
        "        reopened.saved.value = saved\n"
        "        reopened.load_button.click()\n"
        "        assert reopened.current_spec().to_dict() == expected\n"
        "        assert not reopened.save_button.disabled\n"))
    env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
               PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
    NotebookClient(nb, timeout=180, kernel_name="python3", record_timing=False,
                   resources={"metadata": {"path": str(ROOT / "notebooks")}}).execute(env=env)
    # TEST lock on everything the executed notebook DISPLAYS, check cell included (the markdown
    # cites 2024–2026 on purpose, so sources are not scanned).
    shown = json.dumps([c.get("outputs", []) for c in nb.cells], ensure_ascii=False)
    later = scan_text_for_dates_after(shown)
    assert not later, f"post-cutoff dates in notebook outputs: {later[:5]}"
    for label in ("Comparable ?", "Sharpe (taux EUR Research)", "CAGR brut Research", "Non calculé"):
        assert label in shown, f"comparison output missing: {label}"
    nb.cells.pop()
    text = nbformat.writes(nb)
    # The documentation mentions the TEST lock; check saved outputs only, not explanatory text.
    # Widget state includes no historical market data; validate the only plotted allocation separately.
    assert sha256_file(notebook) == source_hash
    (out / "04.executed.ipynb").write_text(text, encoding="utf-8")
    print("Fresh-kernel notebook, exact named allocation, disk save/reload, real six-asset run, Research comparison "
          "and output cutoff scan: PASS", flush=True)
    spec = C.load_spec(ROOT / "config/v2/portfolios/mon_portefeuille_diversifie.json")
    panel = synthetic_panel(spec)
    result = C.simulate(spec, panel)
    figs = {"target": allocation_preview(spec), **A.figures(result)}
    (out / "SYNTHETIC_metadata.json").write_text(json.dumps(result.metadata(), ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    for name, fig in figs.items():
        if name != "target":
            assert "SYNTH" in fig.layout.title.text
        fig.write_html(out / f"SYNTHETIC_{name}.html", include_plotlyjs=True)
        if args.render:
            # Reuse the V2 workaround for the Windows Kaleido 0.1 engine.
            for width in (1050, 640):
                for extension in ("svg", "png"):
                    pio.kaleido.scope._shutdown_kaleido()
                    pio.kaleido.scope.mathjax = None
                    fig.write_image(str(out / f"SYNTHETIC_{name}_{width}.{extension}"), width=width,
                                    height=fig.layout.height, scale=1)
    stability, correlations = A.stability(result)
    assert len(stability) == 5 and len(correlations) == 5
    assert set(A.sensitivities(spec, panel)) == set(C.MODES)
    after = {s.name: sha256_file(settings.research_root / s.path) for s in settings.artifacts}
    assert before == after
    print("Synthetic analytics, three modes, chart exports and 12 frozen hashes: PASS", flush=True)


if __name__ == "__main__":
    main()
