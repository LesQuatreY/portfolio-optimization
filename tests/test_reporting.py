from dataclasses import replace
from portfolio_lab.data import load_market_data
from portfolio_lab.metrics import compute_asset_metrics
from portfolio_lab.optimization import PortfolioOptimizer
from portfolio_lab.reporting import format_weights, write_review_outputs
from test_data import ToyProvider
import pandas as pd
import pytest


@pytest.mark.parametrize("weight,expected", [
    (1e-17, "0.00%"), (0.2414892, "24.15%"), (0.4339953, "43.40%"),
    (1.0, "100.00%"), (-1e-17, "0.00%"), (float("nan"), "—"),
])
def test_weights_display_percentages_without_mutation(weight, expected):
    raw = pd.DataFrame({"Asset": [weight]}, index=["Portfolio"])
    before = raw.copy(deep=True)
    formatted = format_weights(raw)
    assert formatted.loc["Portfolio", "Asset"] == expected
    pd.testing.assert_frame_equal(raw, before, check_exact=True)


def test_coverage_reports_observed_dates(config):
    from portfolio_lab.data import study_coverage
    data = load_market_data(config, ToyProvider())
    coverage = study_coverage(data, config)
    assert coverage["common_start"] == "2020-01-01"
    assert coverage["common_observations"] == 4
    assert coverage["raw_start_limiting_assets"] == ["A", "B"]
    assert not coverage["first_common_date_delayed_by_calendar"]


def test_review_exports_independent_checks(config, portfolio_prices, tmp_path):
    from portfolio_lab.data import MarketData
    import pandas as pd
    cfg = replace(config, output_dir=tmp_path)
    native = {name: portfolio_prices[name] for name in portfolio_prices}
    data = MarketData(native, native, None, portfolio_prices, pd.DataFrame(), pd.DataFrame())
    optimization = PortfolioOptimizer(portfolio_prices, cfg).run()
    raw_weights = optimization.weights.copy(deep=True)
    raw_sums = optimization.weights.sum(axis=1)
    raw_summary = optimization.summary.copy(deep=True)
    stats = compute_asset_metrics(portfolio_prices)
    sanity = write_review_outputs(data, portfolio_prices, stats, pd.DataFrame(), optimization, cfg)
    assert sanity["nonfinite_final_returns"] == 0
    assert sanity["largest_volatility_ceiling_violation"] <= cfg.tolerance
    assert (tmp_path / "review.md").exists()
    assert (tmp_path / "eur-returns.csv").exists()
    assert sanity["common_observations"] == len(portfolio_prices)
    pd.testing.assert_frame_equal(optimization.weights, raw_weights, check_exact=True)
    pd.testing.assert_series_equal(optimization.weights.sum(axis=1), raw_sums, check_exact=True)
    pd.testing.assert_frame_equal(optimization.summary, raw_summary, check_exact=True)
    assert (tmp_path / "portfolio-weights.csv").read_text().splitlines() == raw_weights.to_csv(float_format="%.17g").splitlines()
    allocation_text = (tmp_path / "review.md").read_text(encoding="utf-8").split(
        "## portfolio-weights\n\n```text\n", 1)[1].split("```", 1)[0]
    assert [line.rstrip() for line in format_weights(raw_weights).to_string().splitlines()] == allocation_text.splitlines()
    assert "%" in allocation_text
    assert "e-" not in allocation_text
