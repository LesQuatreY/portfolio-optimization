"""Compare archived and refactored engines with exactly the same EUR inputs AND assumptions.

The archived notebook engine uses the daily sample covariance, sample-mean expected returns and no
investor bounds over every configured asset. The refactored engine is therefore re-run here
with exactly those settings on the same exported prices, instead of reading the notebook's
results (which use the research configuration: Ledoit-Wolf, investor caps, eligibility).
Estimator-dependent differences are a methodology change, not a regression, and are reported
separately by the analysis notebook. Tolerances are unchanged.
"""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from portfolio_lab.config import Asset, Config, WalkForwardSettings
from portfolio_lab.metrics import compute_asset_metrics
from portfolio_lab.leverage import leveraged_name
from portfolio_lab.optimization import optimize_frontier

root = Path(__file__).resolve().parents[1]
settings = json.loads((root / "outputs/effective-config.json").read_text(encoding="utf-8"))
config = Config(**{**settings, "assets": tuple(Asset(**asset) for asset in settings["assets"]),
                   "leverage": tuple(tuple(entry) for entry in settings["leverage"]),
                   "targets": tuple(tuple(entry) for entry in settings["targets"]),
                   "max_weights": tuple(tuple(entry) for entry in settings.get("max_weights", ())),
                   "min_weights": tuple(tuple(entry) for entry in settings.get("min_weights", ())),
                   "eligible": tuple(settings.get("eligible", ())),
                   "financing_series": tuple(tuple(entry) for entry in settings.get("financing_series", ())),
                   "holding_costs": tuple(tuple(entry) for entry in settings.get("holding_costs", ())),
                   "walk_forward": WalkForwardSettings(**settings.get("walk_forward", {})),
                   "cache_dir": Path(settings["cache_dir"]), "output_dir": Path(settings["output_dir"])})
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
equivalent = replace(config, covariance_method="sample", covariance_frequency="daily", expected_return_method="sample",
                     max_weights=(), min_weights=(), eligible=())
refactored = optimize_frontier(prices, equivalent)
new, new_weights = refactored.summary, refactored.weights
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
