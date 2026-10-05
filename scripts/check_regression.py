"""Compare archived and refactored engines with exactly the same EUR inputs."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from portfolio_lab.config import load_config
from portfolio_lab.metrics import compute_asset_metrics
from portfolio_lab.leverage import leveraged_name

root = Path(__file__).resolve().parents[1]
config = load_config()
notebook = json.loads((root / "notebooks/archive/draft.ipynb").read_text(encoding="utf-8"))
prices = pd.read_csv(root / "outputs/eur-prices.csv", index_col=0, parse_dates=True)
namespace = dict(
    np=np, pd=pd, minimize=minimize, prices=prices,
    assets={a.name: a.symbol for a in config.assets},
    leveraged_labels={name: leveraged_name(name, factor) for name, factor in config.leverage},
    include_leveraged_in_frontier=config.include_leveraged_in_frontier,
    frontier_points=config.frontier_points, trading_days=config.trading_days,
    risk_free_rate=config.risk_free_rate, calendar_days_per_year=config.calendar_days_per_year,
    portfolio_tolerance=config.tolerance, portfolio_targets=dict(config.targets),
    allocation_display_threshold=config.allocation_display_threshold,
    validation_checks=[], display=lambda *args, **kwargs: None,
    compute_performance=compute_asset_metrics,
    stats=compute_asset_metrics(prices, config.trading_days, config.risk_free_rate, config.calendar_days_per_year),
)
for cell_number in (12, 14):
    exec(compile("".join(notebook["cells"][cell_number]["source"]), f"original-cell-{cell_number}", "exec"), namespace)
new = pd.read_csv(root / "outputs/portfolio-results.csv", index_col=0)
new_weights = pd.read_csv(root / "outputs/portfolio-weights.csv", index_col=0)
original = {"Minimum Volatility": namespace["minimum_volatility_portfolio"],
            "Maximum CAGR": namespace["maximum_growth_portfolio"],
            "Maximum Sharpe": namespace["maximum_sharpe_portfolio"], **namespace["target_portfolios"]}
rows = []
for name, portfolio in original.items():
    if portfolio["weights"] is None:
        continue
    for metric in ("CAGR", "Volatility", "Sharpe"):
        delta = float(new.loc[name, metric] - portfolio[metric])
        np.testing.assert_allclose(new.loc[name, metric], portfolio[metric], atol=1e-6, rtol=1e-6)
        rows.append({"Portfolio": name, "Metric": metric, "Archived engine": portfolio[metric],
                     "Refactored engine": new.loc[name, metric], "Difference": delta})
    np.testing.assert_allclose(new_weights.loc[name, portfolio["weights"].index], portfolio["weights"], atol=1e-5)
table = pd.DataFrame(rows)
table.to_csv(root / "outputs/engine-regression.csv", index=False, float_format="%.17g")
print(table.to_string(index=False))
print(f"Archived optimization validations passed: {len(namespace['validation_checks'])}")
print("Equal-input engine regression passed; source/FX methodological changes are intentionally excluded.")
