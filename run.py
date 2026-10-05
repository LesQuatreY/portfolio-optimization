"""Run the notebook in a fresh kernel with every writable runtime path in this repo."""
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
    parser.add_argument("--test", action="store_true", help="Run pytest rather than the notebook.")
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
    notebook = nbformat.read(root / "notebooks/portfolio_analysis.ipynb", as_version=4)
    client = NotebookClient(notebook, timeout=1800, kernel_name="portfolio-lab", resources={"metadata": {"path": str(root)}})
    client.execute()
    target = root / "outputs/portfolio_analysis.executed.ipynb"
    nbformat.write(notebook, target)
    print(f"Notebook completed in a fresh kernel: {target}")


if __name__ == "__main__":
    main()
