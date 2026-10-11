"""Run the research notebooks in fresh kernels (outputs safety-checked) or the test suite."""
from pathlib import Path
import argparse
import json
import os
import sys
import asyncio


def configure_runtime(root: Path) -> None:
    paths = {"TEMP": "tmp", "TMP": "tmp", "MPLCONFIGDIR": ".cache/matplotlib",
             "IPYTHONDIR": ".cache/ipython", "JUPYTER_CONFIG_DIR": ".cache/jupyter/config",
             "JUPYTER_DATA_DIR": ".cache/jupyter/data", "JUPYTER_RUNTIME_DIR": ".cache/jupyter/runtime",
             "PIP_CACHE_DIR": ".cache/pip", "XDG_CACHE_HOME": ".cache"}
    for key, directory in paths.items():
        path = root / directory
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["MPLBACKEND"] = "Agg"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Run pytest rather than the notebooks.")
    parser.add_argument("notebooks", nargs="*", help="Notebook names (default: both research notebooks).")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    os.chdir(root)
    configure_runtime(root)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if args.test:
        import pytest
        raise SystemExit(pytest.main(["-q", "--basetemp", str(root / "tmp/pytest")]))
    import nbformat
    from nbclient import NotebookClient
    # Local kernelspec explicitly uses this environment's interpreter.
    kernel_path = root / ".cache/jupyter/data/kernels/portfolio-lab"
    kernel_path.mkdir(parents=True, exist_ok=True)
    spec = {"argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Portfolio Lab", "language": "python"}
    (kernel_path / "kernel.json").write_text(json.dumps(spec), encoding="utf-8")
    from portfolio_lab.protocol import assert_notebook_outputs_safe, find_holdout_dates
    names = args.notebooks or ["portfolio_analysis", "portfolio_robustness"]
    for name in names:
        notebook = nbformat.read(root / f"notebooks/{name}.ipynb", as_version=4)
        client = NotebookClient(notebook, timeout=1800, kernel_name="portfolio-lab",
                                resources={"metadata": {"path": str(root / "notebooks")}})
        client.execute()
        # Never persist an executed notebook whose outputs mention locked holdout dates.
        outputs = nbformat.writes(notebook)
        dates = find_holdout_dates(json.dumps([c.get("outputs", []) for c in notebook.cells], ensure_ascii=False))
        if dates:
            raise SystemExit(f"{name}: outputs contain holdout dates {dates[:5]}; nothing was written.")
        target = root / f"outputs/{name}.executed.ipynb"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(outputs, encoding="utf-8")
        assert_notebook_outputs_safe(target)
        print(f"Notebook completed in a fresh kernel: {target}")


if __name__ == "__main__":
    main()
