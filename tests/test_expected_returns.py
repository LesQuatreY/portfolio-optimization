"""Expected-return estimator: Jorion (1986) Bayes-Stein default, exact sample baseline, train-only fits."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.config import Asset
from portfolio_lab.expected_returns import estimate_expected_returns
from portfolio_lab.optimization import PortfolioOptimizer
from portfolio_lab.returns import simple_returns
from portfolio_lab.robustness import OPTIMIZED, walk_forward


@pytest.fixture(scope="module")
def returns():
    rng = np.random.default_rng(5)
    data = rng.normal([.0008, .0003, .0001, .0005], [.02, .012, .008, .015], (750, 4))
    return pd.DataFrame(data, index=pd.bdate_range("2020-01-01", periods=750), columns=["Z", "A", "M", "B"])


def jorion_reference(x: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Independent textbook implementation (daily units)."""
    t, n = x.shape
    m = x.mean(axis=0)
    sigma = np.cov(x, rowvar=False) * (t - 1) / (t - n - 2)
    inv = np.linalg.inv(sigma)
    one = np.ones(n)
    mu0 = one @ inv @ m / (one @ inv @ one)
    lam = (n + 2) / ((m - mu0) @ inv @ (m - mu0))
    w = lam / (t + lam)
    return (1 - w) * m + w * mu0, w, mu0


def test_sample_reproduces_previous_mean_exactly(returns):
    estimate = estimate_expected_returns(returns, "sample", 252)
    np.testing.assert_array_equal(estimate.values.to_numpy(), returns.to_numpy().mean(axis=0) * 252)
    assert estimate.shrinkage is None and estimate.label == "Sample mean"


def test_bayes_stein_matches_jorion_formula(returns):
    estimate = estimate_expected_returns(returns, "bayes_stein", 252)
    shrunk, w, mu0 = jorion_reference(returns.to_numpy())
    np.testing.assert_allclose(estimate.values.to_numpy(), shrunk * 252, rtol=1e-12)
    assert estimate.shrinkage == pytest.approx(w, rel=1e-12)
    assert estimate.target == pytest.approx(mu0 * 252, rel=1e-12)
    assert estimate.label == "Bayes-Stein (Jorion 1986)"


def test_names_order_finiteness_and_valid_intensity(returns):
    estimate = estimate_expected_returns(returns, "bayes_stein")
    assert list(estimate.values.index) == ["Z", "A", "M", "B"]
    assert np.isfinite(estimate.values.to_numpy()).all()
    assert 0 < estimate.shrinkage <= 1 and np.isfinite(estimate.shrinkage)
    order = ["B", "M", "Z", "A"]
    reordered = estimate_expected_returns(returns[order], "bayes_stein")
    assert list(reordered.values.index) == order
    pd.testing.assert_series_equal(reordered.values, estimate.values.loc[order], rtol=1e-12)
    assert reordered.shrinkage == pytest.approx(estimate.shrinkage, rel=1e-12)


def test_shrunk_means_move_towards_the_common_target(returns):
    sample = estimate_expected_returns(returns, "sample").values
    shrunk = estimate_expected_returns(returns, "bayes_stein")
    assert shrunk.shrinkage > 0
    distance_before = (sample - shrunk.target).abs()
    distance_after = (shrunk.values - shrunk.target).abs()
    assert (distance_after < distance_before).all()
    np.testing.assert_allclose(distance_after, (1 - shrunk.shrinkage) * distance_before, rtol=1e-12)


def test_equal_means_give_full_shrinkage_without_nan():
    rng = np.random.default_rng(1)
    x = rng.standard_normal((300, 3)) * .01
    x -= x.mean(axis=0) - .0004
    estimate = estimate_expected_returns(pd.DataFrame(x, columns=list("abc")), "bayes_stein")
    assert estimate.shrinkage == pytest.approx(1)
    np.testing.assert_allclose(estimate.values, .0004 * 252, rtol=1e-9)


def test_annualization_is_applied_exactly_once(returns):
    daily = estimate_expected_returns(returns, "bayes_stein", 1)
    annual = estimate_expected_returns(returns, "bayes_stein", 252)
    np.testing.assert_allclose(annual.values, daily.values * 252, rtol=1e-14)
    # The intensity is computed in daily units and does not depend on annualization.
    assert annual.shrinkage == daily.shrinkage


@pytest.mark.parametrize("method", ["james_stein", "Bayes_Stein", ""])
def test_unsupported_method_is_explicit(returns, config, method):
    with pytest.raises(ValueError, match="Unsupported expected-return method.*bayes_stein.*sample"):
        estimate_expected_returns(returns, method)
    with pytest.raises(ValueError, match="Unsupported expected-return method"):
        replace(config, expected_return_method=method)


def test_invalid_inputs_are_rejected(returns):
    broken = returns.copy()
    broken.iloc[2, 0] = np.inf
    with pytest.raises(ValueError, match="finite"):
        estimate_expected_returns(broken, "bayes_stein")
    with pytest.raises(ValueError, match="more than N \\+ 2"):
        estimate_expected_returns(returns.iloc[:6], "bayes_stein")


def test_only_maximum_sharpe_uses_expected_returns(config, portfolio_prices):
    shrunk = PortfolioOptimizer(portfolio_prices, replace(config, expected_return_method="bayes_stein")).run()
    sample = PortfolioOptimizer(portfolio_prices, replace(config, expected_return_method="sample")).run()
    assert shrunk.expected_return_estimator.startswith("Bayes-Stein") and shrunk.expected_return_shrinkage > 0
    # Covariance-only and realized-growth objectives are identical.
    for name in ["Minimum Volatility", "Maximum CAGR", *dict(config.targets)]:
        pd.testing.assert_series_equal(shrunk.weights.loc[name], sample.weights.loc[name])
    pd.testing.assert_frame_equal(shrunk.frontier.drop(columns="weights")[["CAGR", "Volatility"]],
                                  sample.frontier.drop(columns="weights")[["CAGR", "Volatility"]])
    # Realized metrics keep the raw sample mean; the model return is reported separately.
    realized = simple_returns(portfolio_prices).to_numpy().mean(axis=0) * 252
    for frame in (shrunk.summary, sample.summary):
        for name, row in frame.iterrows():
            w = (shrunk if frame is shrunk.summary else sample).weights.loc[name]
            if w.isna().any():
                continue
            assert row["Mean return annualized"] == pytest.approx(realized @ w.to_numpy(), rel=1e-12)
    pd.testing.assert_series_equal(sample.summary["Estimated return"], sample.summary["Mean return annualized"],
                                   check_names=False)


@pytest.fixture(scope="module")
def walk_data():
    dates = pd.bdate_range("2009-12-30", "2014-06-30")
    rng = np.random.default_rng(21)
    prices = pd.DataFrame(100 * np.cumprod(1 + rng.normal([.0008, .0003, .0002], [.02, .012, .008],
                                                          (len(dates), 3)), axis=0),
                          index=dates, columns=["A", "B", "W"])
    return prices


def wf_config(config):
    return replace(config, expected_return_method="bayes_stein",
                   assets=tuple(Asset(n, n, "synthetic", "EUR", "Gross Return", "x") for n in "ABW"))


def test_each_fold_fits_its_own_estimator_on_training_returns_only(config, walk_data):
    cfg = wf_config(config)
    result = walk_forward(walk_data, cfg, train_years=2, benchmark="W")
    assert result.expected_return_estimator == "Bayes-Stein (Jorion 1986)"
    intensities = []
    for fold in result.folds:
        train = simple_returns(walk_data.loc[fold.return_base:fold.train_end])
        assert train.index.max() < fold.test_start
        expected = estimate_expected_returns(train, "bayes_stein", cfg.trading_days).shrinkage
        for name in OPTIMIZED:
            assert result.train_metrics.loc[(name, fold.test_year), "Expected-return shrinkage"] == \
                pytest.approx(expected, rel=1e-12)
        intensities.append(expected)
    assert len(set(np.round(intensities, 12))) == len(result.folds)
    full = estimate_expected_returns(simple_returns(walk_data), "bayes_stein").shrinkage
    assert all(abs(value - full) > 1e-12 for value in intensities)


def test_test_year_cannot_change_its_weights_but_training_data_can(config, walk_data):
    cfg = wf_config(config)
    baseline = walk_forward(walk_data, cfg, train_years=2, benchmark="W")
    rng = np.random.default_rng(4)
    scrambled = walk_data.copy()
    in_2013 = scrambled.index.year == 2013
    scrambled.loc[in_2013] *= np.exp(np.cumsum(rng.normal(0, .02, (in_2013.sum(), 3)), axis=0))
    perturbed = walk_forward(scrambled, cfg, train_years=2, benchmark="W")
    shrinkage = lambda r, year: r.train_metrics.loc[("Maximum Sharpe", year), "Expected-return shrinkage"]
    for name in OPTIMIZED:
        for year in (2012, 2013):
            pd.testing.assert_series_equal(perturbed.weights[name].loc[year], baseline.weights[name].loc[year])
    for year in (2012, 2013):
        assert shrinkage(perturbed, year) == shrinkage(baseline, year)
    # 2013 is training data for the 2014 fold: its estimate and Max Sharpe weights change.
    assert shrinkage(perturbed, 2014) != pytest.approx(shrinkage(baseline, 2014), rel=1e-9)
    assert not np.allclose(perturbed.weights["Maximum Sharpe"].loc[2014], baseline.weights["Maximum Sharpe"].loc[2014])


def test_reference_default_is_sample_mean_and_bayes_stein_stays_available(config, portfolio_prices):
    from portfolio_lab.config import load_config
    assert load_config().expected_return_method == config.expected_return_method == "sample"
    default = PortfolioOptimizer(portfolio_prices, config)
    assert default.expected.label == "Sample mean"
    np.testing.assert_array_equal(default.mu, simple_returns(portfolio_prices).to_numpy().mean(axis=0) * 252)
    shrunk = PortfolioOptimizer(portfolio_prices, replace(config, expected_return_method="bayes_stein"))
    assert shrunk.expected.label == "Bayes-Stein (Jorion 1986)" and 0 < shrunk.expected.shrinkage <= 1
