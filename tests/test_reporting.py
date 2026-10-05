from dataclasses import replace
from portfolio_lab.data import load_market_data
from portfolio_lab.metrics import compute_asset_metrics
from portfolio_lab.optimization import PortfolioOptimizer
from portfolio_lab.reporting import write_review_outputs
from test_data import ToyProvider


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
    stats = compute_asset_metrics(portfolio_prices)
    sanity = write_review_outputs(data, portfolio_prices, stats, pd.DataFrame(), optimization, cfg)
    assert sanity["nonfinite_final_returns"] == 0
    assert sanity["largest_volatility_ceiling_violation"] <= cfg.tolerance
    assert (tmp_path / "review.md").exists()
    assert (tmp_path / "eur-returns.csv").exists()
    assert sanity["common_observations"] == len(portfolio_prices)
