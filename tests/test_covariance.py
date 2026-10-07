"""Central covariance estimator: Ledoit-Wolf default, sample baseline, walk-forward fit on training only."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from sklearn.covariance import LedoitWolf
from portfolio_lab.config import Asset
from portfolio_lab.covariance import estimate_covariance
from portfolio_lab.optimization import PortfolioOptimizer
from portfolio_lab.returns import simple_returns
from portfolio_lab.robustness import OPTIMIZED, walk_forward


@pytest.fixture(scope="module")
def returns():
    rng = np.random.default_rng(3)
    factor = rng.standard_normal((500, 1))
    data = .01 * factor * np.array([1., .8, .3, 0.]) + .01 * rng.standard_normal((500, 4)) * [1., 1.5, .5, 2.]
    return pd.DataFrame(data, index=pd.bdate_range("2020-01-01", periods=500), columns=["Z", "A", "M", "B"])


def test_ledoit_wolf_is_labelled_symmetric_finite_and_positive_definite(returns):
    estimate = estimate_covariance(returns, "ledoit_wolf", 252)
    matrix = estimate.matrix
    assert estimate.label == "Ledoit-Wolf" and 0 < estimate.shrinkage < 1
    assert matrix.shape == (4, 4)
    assert list(matrix.index) == list(matrix.columns) == ["Z", "A", "M", "B"]
    assert np.isfinite(matrix.to_numpy()).all()
    np.testing.assert_array_equal(matrix.to_numpy(), matrix.to_numpy().T)
    assert np.linalg.eigvalsh(matrix).min() > 0


def test_annualization_is_applied_exactly_once(returns):
    daily = LedoitWolf().fit(returns.to_numpy()).covariance_
    np.testing.assert_array_equal(estimate_covariance(returns, "ledoit_wolf", 1).matrix, daily)
    np.testing.assert_allclose(estimate_covariance(returns, "ledoit_wolf", 252).matrix, daily * 252, rtol=1e-15)
    np.testing.assert_allclose(estimate_covariance(returns, "sample", 252).matrix,
                               np.cov(returns.to_numpy(), rowvar=False, ddof=1) * 252, rtol=1e-12)


def test_asset_order_is_preserved(returns):
    order = ["B", "Z", "M", "A"]
    for method in ("ledoit_wolf", "sample"):
        reordered = estimate_covariance(returns[order], method).matrix
        assert list(reordered.columns) == order
        pd.testing.assert_frame_equal(reordered, estimate_covariance(returns, method).matrix.loc[order, order])


def test_sample_reproduces_previous_covariance_exactly(returns):
    pd.testing.assert_frame_equal(estimate_covariance(returns, "sample", 252).matrix, returns.cov() * 252,
                                  check_exact=True)
    assert estimate_covariance(returns, "sample").shrinkage is None


@pytest.mark.parametrize("method", ["shrunk", "LEDOIT_WOLF", ""])
def test_unsupported_method_is_explicit(returns, config, method):
    with pytest.raises(ValueError, match="Unsupported covariance method.*ledoit_wolf.*sample"):
        estimate_covariance(returns, method)
    with pytest.raises(ValueError, match="Unsupported covariance method"):
        replace(config, covariance_method=method)


def test_nonfinite_returns_never_reach_the_estimator(returns):
    broken = returns.copy()
    broken.iloc[3, 1] = np.nan
    with pytest.raises(ValueError, match="finite"):
        estimate_covariance(broken)


def test_default_engine_uses_ledoit_wolf_for_risk_and_reports_realized_metrics(config, portfolio_prices):
    assert config.covariance_method == "ledoit_wolf"
    optimizer = PortfolioOptimizer(portfolio_prices, config)
    result = optimizer.run()
    assert result.covariance_estimator == "Ledoit-Wolf" and result.covariance_shrinkage is not None
    expected = estimate_covariance(simple_returns(portfolio_prices), "ledoit_wolf", config.trading_days).matrix
    pd.testing.assert_frame_equal(result.covariance, expected)
    sigma = expected.to_numpy()
    daily_returns = simple_returns(portfolio_prices).to_numpy()
    for name, weights in result.weights.dropna().iterrows():
        w = weights.to_numpy()
        row = result.summary.loc[name]
        assert row["Estimated volatility"] == pytest.approx(np.sqrt(w @ sigma @ w), rel=1e-9)
        assert row["Volatility"] == pytest.approx((daily_returns @ w).std(ddof=1) * np.sqrt(252), rel=1e-9)
        if name in dict(config.targets):
            assert row["Estimated volatility"] <= dict(config.targets)[name] + config.tolerance
    # Minimum volatility is optimal under the shrinkage risk model, not the sample one.
    w_min = result.weights.loc["Minimum Volatility"].to_numpy()
    for trial in np.linspace(0, 1, 101):
        w = np.array([trial, 1 - trial])
        assert w_min @ sigma @ w_min <= w @ sigma @ w + 1e-12


def test_sample_method_reproduces_previous_engine(config, portfolio_prices):
    sample = PortfolioOptimizer(portfolio_prices, replace(config, covariance_method="sample")).run()
    assert sample.covariance_estimator == "Sample" and sample.covariance_shrinkage is None
    pd.testing.assert_frame_equal(sample.covariance, simple_returns(portfolio_prices).cov() * 252, check_exact=True)
    # Previous behaviour: risk model == realized sample volatility for every portfolio.
    pd.testing.assert_series_equal(sample.summary["Estimated volatility"], sample.summary["Volatility"],
                                   check_names=False)
    np.testing.assert_allclose(sample.weights.loc["Minimum Volatility"], [.2, .8], atol=1e-5)


def test_walk_forward_fits_ledoit_wolf_on_each_training_window_only(config):
    dates = pd.bdate_range("2009-12-30", "2014-06-30")
    rng = np.random.default_rng(11)
    prices = pd.DataFrame(100 * np.cumprod(1 + rng.normal(.0004, [.02, .012, .008], (len(dates), 3)), axis=0),
                          index=dates, columns=["A", "B", "W"])
    cfg = replace(config, assets=tuple(Asset(n, n, "synthetic", "EUR", "Gross Return", "x") for n in "ABW"))
    result = walk_forward(prices, cfg, train_years=2, benchmark="W")
    assert result.covariance_estimator == "Ledoit-Wolf"
    shrinkages = []
    for fold in result.folds:
        train_returns = simple_returns(prices.loc[fold.return_base:fold.train_end])
        assert train_returns.index.max() < fold.test_start
        expected = LedoitWolf().fit(train_returns.to_numpy()).shrinkage_
        for name in OPTIMIZED:
            assert result.train_metrics.loc[(name, fold.test_year), "Covariance shrinkage"] == pytest.approx(expected)
        shrinkages.append(expected)
    # One fit per fold, not one fit on the whole history.
    assert len(set(np.round(shrinkages, 12))) == len(result.folds)
    full = LedoitWolf().fit(simple_returns(prices).to_numpy()).shrinkage_
    assert all(abs(s - full) > 1e-12 for s in shrinkages)
    # Scrambling a test year leaves that year's Ledoit-Wolf weights untouched.
    scrambled = prices.copy()
    year = scrambled.index.year == 2013
    scrambled.loc[year] *= np.exp(rng.normal(0, .05, (year.sum(), 3)))
    perturbed = walk_forward(scrambled, cfg, train_years=2, benchmark="W")
    for name in OPTIMIZED:
        pd.testing.assert_series_equal(perturbed.weights[name].loc[2013], result.weights[name].loc[2013])
        assert not perturbed.weights[name].loc[2014].equals(result.weights[name].loc[2014])
