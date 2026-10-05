"""Persist independent review evidence and enforce numerical sanity checks."""
from pathlib import Path
from dataclasses import asdict
import json
import numpy as np
import pandas as pd
from .returns import simple_returns
from .plotting import allocation_summary


def format_weights(weights: pd.DataFrame) -> pd.DataFrame:
    """Return display strings without changing numerical weights or their sums."""
    def percentage(weight):
        if pd.isna(weight):
            return "—"
        return f"{0.0 if abs(weight) < 1e-10 else weight:.2%}"

    return weights.apply(lambda column: column.map(percentage))


def validate_study(prices, optimization, config) -> dict:
    returns = simple_returns(prices)
    finite_count = int((~np.isfinite(returns.to_numpy())).sum())
    weight_sums = {}
    minimum_weight = 1.
    violations = []
    all_results = list(optimization.portfolios.items()) + [
        (f"Frontier {i}", row) for i, row in optimization.frontier.iterrows()]
    for name, result in all_results:
        w = result["weights"]
        if w is None:
            continue
        if not result["Success"]:
            raise RuntimeError(f"{name}: optimized portfolio reports failure.")
        weight_sums[name] = float(w.sum())
        minimum_weight = min(minimum_weight, float(w.min()))
        if abs(w.sum() - 1) > 1e-8 or w.min() < -1e-8 or w.max() > 1 + 1e-8:
            raise RuntimeError(f"{name}: invalid optimized weights.")
        daily = returns[w.index] @ w
        nav = np.r_[1., np.cumprod(1 + daily.to_numpy())]
        years = (prices.index[-1] - prices.index[0]).days / config.calendar_days_per_year
        # Independently compound, rather than reuse the log-growth implementation.
        expected_cagr = nav[-1] ** (1 / years) - 1
        np.testing.assert_allclose(result["CAGR"], expected_cagr, atol=1e-10)
        np.testing.assert_allclose(result["Volatility"], daily.std(ddof=1) * np.sqrt(config.trading_days), atol=1e-12)
        np.testing.assert_allclose(result["Max Drawdown"], (nav / np.maximum.accumulate(nav) - 1).min(), atol=1e-12)
        if "Risk ceiling" in result and pd.notna(result["Risk ceiling"]):
            violations.append(float(result["Volatility"] - result["Risk ceiling"]))
    eigenvalue = float(np.linalg.eigvalsh(optimization.covariance).min())
    largest_violation = max([0., *violations])
    if finite_count or eigenvalue < -1e-10 or largest_violation > config.tolerance:
        raise RuntimeError("Return finiteness, covariance PSD or risk ceiling validation failed.")
    final_attempts = optimization.solver_log.groupby("Portfolio", sort=False).tail(1)
    return {"portfolio_weight_sums": weight_sums, "minimum_portfolio_weight": minimum_weight,
            "maximum_weight_sum_error": max(abs(value - 1) for value in weight_sums.values()),
            "largest_volatility_ceiling_violation": largest_violation,
            "nonfinite_final_returns": finite_count, "common_observations": len(prices),
            "return_observations": len(returns), "common_start": str(prices.index[0].date()),
            "common_end": str(prices.index[-1].date()), "covariance_minimum_eigenvalue": eigenvalue,
            "solver_attempts": len(optimization.solver_log),
            "successful_solver_attempts": int(optimization.solver_log["Success"].sum()),
            "optimizer_solve_count": len(final_attempts),
            "optimizer_success_count": int(final_attempts["Success"].sum()),
            "unsuccessful_solver_attempts": int((~optimization.solver_log["Success"]).sum())}


def write_review_outputs(data, prices, stats, diagnostics, optimization, config, directory: Path | None = None):
    directory = Path(config.output_dir if directory is None else directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "effective-config.json").write_text(
        json.dumps(asdict(config), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    sanity = validate_study(prices, optimization, config)
    from .data import study_coverage
    coverage = study_coverage(data, config)
    provenance = data.provenance.copy()
    for name, factor in config.leverage:
        from .leverage import leveraged_name
        label = leveraged_name(name, factor)
        row = provenance.loc[name].copy()
        row["Provider"] = f"Synthetic from {row['Provider']}"
        row["Instrument / benchmark"] = f"{factor:g}x daily reset of {row['Instrument / benchmark']}"
        row["Return type"] = "Synthetic daily-reset NAV"
        row["Distributions"] = "Inherited from underlying; native-currency daily reset, then unlevered FX"
        row["Limitation"] = "Financing, fees, tracking error, trading costs and tax excluded. " + row["Limitation"]
        path = data.native[name].loc[prices.index[0]:prices.index[-1]].dropna()
        row["Raw start date"] = path.index[0]
        row["Raw end date"] = path.index[-1]
        row["Raw observations"] = len(path)
        row["Raw missing observations"] = 0
        row["FX missing on observed sessions"] = int(data.fx.reindex(path.index).isna().sum()) if row["Native currency"] == "USD" else 0
        row["EUR observations"] = len(path) - row["FX missing on observed sessions"]
        provenance.loc[label] = row
    summary = optimization.summary.copy()
    summary["Main Allocation"] = allocation_summary(optimization.weights, config.allocation_display_threshold)
    tables = {"provenance": provenance, "fx-validation": data.fx_sample, "asset-performance": stats,
              "leverage-diagnostics": diagnostics, "portfolio-results": summary,
              "portfolio-weights": optimization.weights, "covariance": optimization.covariance,
              "frontier-dominance": optimization.dominance, "solver-log": optimization.solver_log}
    frontier = optimization.frontier.drop(columns="weights").copy()
    frontier_weights = pd.DataFrame(list(optimization.frontier["weights"]))
    tables["frontier"] = pd.concat([frontier, frontier_weights.add_prefix("Weight: ")], axis=1)
    prices.to_csv(directory / "eur-prices.csv", float_format="%.17g")
    simple_returns(prices).to_csv(directory / "eur-returns.csv", float_format="%.17g")
    for name, table in tables.items():
        table.to_csv(directory / f"{name}.csv", float_format="%.17g")
    (directory / "sanity-checks.json").write_text(json.dumps(sanity, indent=2, ensure_ascii=False), encoding="utf-8")
    (directory / "study-coverage.json").write_text(json.dumps(coverage, indent=2, ensure_ascii=False), encoding="utf-8")
    sections = ["# Executed study review", "All economic series are normalized to EUR before returns and covariance. Synthetic raw observations describe the constructed native NAV over the study interval; their symbols identify the underlying source."]
    for name, table in tables.items():
        display_table = table
        if name == "portfolio-weights":
            display_table = format_weights(table)
        elif name == "frontier":
            display_table = table.copy()
            columns = [column for column in table if column.startswith("Weight: ")]
            display_table[columns] = format_weights(table[columns])
        rendered = "\n".join(line.rstrip() for line in display_table.to_string().splitlines())
        sections.extend([f"## {name}", "```text\n" + rendered + "\n```"])
    sections.extend(["## Numerical sanity checks", "```json\n" + json.dumps(sanity, indent=2) + "\n```"])
    sections.extend(["## Historical coverage", "```json\n" + json.dumps(coverage, indent=2) + "\n```"])
    (directory / "review.md").write_text("\n\n".join(sections), encoding="utf-8")
    return sanity
