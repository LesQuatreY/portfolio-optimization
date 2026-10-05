"""Execute only archived pure functions, never the legacy network/notebook cells."""
import ast
import json
from pathlib import Path
import numpy as np
import pandas as pd
from portfolio_lab.leverage import build_daily_leveraged_series
from portfolio_lab.metrics import compute_asset_metrics


def original_functions():
    archive = Path(__file__).resolve().parents[1] / "notebooks/archive/draft.ipynb"
    notebook = json.loads(archive.read_text(encoding="utf-8"))
    selected = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            tree = ast.parse("".join(cell["source"]))
            selected.extend(n for n in tree.body if isinstance(n, ast.FunctionDef)
                            and n.name in {"build_daily_leveraged_series", "compute_performance"})
    namespace = {"np": np, "pd": pd}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(archive), "exec"), namespace)
    return namespace


def test_refactor_regression_on_unchanged_inputs():
    old = original_functions()
    dates = pd.date_range("2020-01-01", periods=5)
    prices = pd.DataFrame({"A": [100., 110., 99., 130., 120.], "B": [100., 90., 95., 110., 115.]}, index=dates)
    for leverage in (1.3, 1.5, 2., 3., 4.):
        pd.testing.assert_series_equal(build_daily_leveraged_series(prices["A"], leverage),
                                       old["build_daily_leveraged_series"](prices["A"], leverage))
    pd.testing.assert_frame_equal(compute_asset_metrics(prices), old["compute_performance"](prices))


def test_original_wipeout_regression():
    old = original_functions()
    dates = pd.date_range("2020-01-01", periods=4)
    prices = pd.DataFrame({"A": [100., 0., 0., 0.]}, index=dates)
    pd.testing.assert_frame_equal(compute_asset_metrics(prices), old["compute_performance"](prices))
