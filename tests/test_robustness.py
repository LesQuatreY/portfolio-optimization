"""Walk-forward and subperiod robustness on deterministic synthetic EUR prices (offline)."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.config import Asset
from portfolio_lab.metrics import compute_asset_metrics
from portfolio_lab.optimization import PortfolioOptimizer
from portfolio_lab.returns import simple_returns
from portfolio_lab.robustness import (
    EQUAL_WEIGHT, OPTIMIZED, concentration, growth_metrics, hhi, subperiod_stability, turnover,
    walk_forward, walk_forward_folds, weight_stability, window_prices)


def synthetic_prices(start, end, seed=7):
    dates = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    drift = np.array([.0006, .0003, .0002])
    vol = np.array([.02, .012, .008])
    returns = drift + vol * rng.standard_normal((len(dates), 3))
    return pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), index=dates, columns=["A", "B", "W"])


@pytest.fixture
def cfg(config):
    assets = tuple(Asset(name, name, "synthetic", "EUR", "Gross Return", "reinvested") for name in "ABW")
    return replace(config, assets=assets)


@pytest.fixture(scope="module")
def short_prices():
    # 2009-12-30 is the return base of a 2010-2011 training window.
    return synthetic_prices("2009-12-30", "2015-06-30")


def run(prices, cfg, **kwargs):
    return walk_forward(prices, cfg, train_years=2, benchmark="W", **kwargs)


def test_ten_year_folds_follow_actual_history():
    index = pd.bdate_range("2000-12-29", "2026-10-02")
    folds = walk_forward_folds(index, 10)
    assert [f.test_year for f in folds] == list(range(2011, 2027))
    first = folds[0]
    assert (first.return_base, first.train_start, first.train_end) == (
        pd.Timestamp("2000-12-29"), pd.Timestamp("2001-01-01"), pd.Timestamp("2010-12-31"))
    assert (first.test_start, first.test_end) == (pd.Timestamp("2011-01-03"), pd.Timestamp("2011-12-30"))
    for previous, fold in zip(folds, folds[1:]):
        # The 10-year window rolls forward by exactly one calendar year.
        assert fold.train_start.year == previous.train_start.year + 1
        assert fold.train_end.year == previous.train_end.year + 1 == fold.test_year - 1
        assert previous.test_end < fold.test_start
    for fold in folds:
        assert fold.return_base < fold.train_start <= fold.train_end < fold.test_start <= fold.test_end
        assert fold.train_end.year - fold.train_start.year == 9


def test_folds_need_a_full_training_window():
    # Data starting on 2001-01-02 cannot provide the 2001 return from a prior close.
    with pytest.raises(ValueError, match="too short"):
        walk_forward_folds(pd.bdate_range("2001-01-02", "2011-06-30"), 10)
    assert walk_forward_folds(pd.bdate_range("2001-01-02", "2012-06-29"), 10)[0].test_year == 2012


def test_partial_final_year_is_flagged_and_optional():
    index = pd.bdate_range("2000-12-29", "2026-10-02")
    last = walk_forward_folds(index, 10)[-1]
    assert (last.test_year, last.test_end, last.complete_test_year) == (2026, pd.Timestamp("2026-10-02"), False)
    assert all(f.complete_test_year for f in walk_forward_folds(index, 10)[:-1])
    assert walk_forward_folds(index, 10, include_partial_final_year=False)[-1].test_year == 2025


def test_oos_series_contains_only_chronological_test_returns(short_prices, cfg):
    result = run(short_prices, cfg)
    assert [f.test_year for f in result.folds] == [2012, 2013, 2014, 2015]
    oos = result.oos_returns
    assert oos.index.is_unique and oos.index.is_monotonic_increasing
    expected = short_prices.index[short_prices.index >= result.folds[0].test_start]
    assert oos.index.equals(expected)
    for fold in result.folds:
        year = oos.loc[str(fold.test_year)]
        assert (year.index[0], year.index[-1]) == (fold.test_start, fold.test_end)
        assert fold.train_end < year.index.min()
    assert result.nav.index[0] == result.folds[0].train_end
    np.testing.assert_allclose(result.nav.iloc[1:], (1 + oos).cumprod())


def test_test_year_prices_cannot_change_that_years_weights(short_prices, cfg):
    baseline = run(short_prices, cfg)
    shocked = short_prices.copy()
    in_2013 = shocked.index >= "2013-01-01"
    # A large, return-changing path shock from the first 2013 observation onward.
    shocked.loc[in_2013, "A"] *= np.linspace(.5, 3., in_2013.sum())
    perturbed = run(shocked, cfg)
    for name in OPTIMIZED:
        for year in (2012, 2013):
            pd.testing.assert_series_equal(perturbed.weights[name].loc[year], baseline.weights[name].loc[year])
        # The shock is visible to later training windows, proving the check is sensitive.
        assert not np.allclose(perturbed.weights[name].loc[2015], baseline.weights[name].loc[2015])
    # ...while the shocked test-year returns themselves are what gets evaluated.
    assert not np.allclose(perturbed.oos_returns.loc["2013", EQUAL_WEIGHT],
                           baseline.oos_returns.loc["2013", EQUAL_WEIGHT])


def test_weights_come_from_training_prices_and_are_applied_to_test_returns(short_prices, cfg):
    result = run(short_prices, cfg)
    fold = result.folds[1]
    train = short_prices.loc[fold.return_base:fold.train_end]
    expected = PortfolioOptimizer(train, cfg).core_portfolios()
    test_returns = simple_returns(short_prices.loc[fold.train_end:fold.test_end])
    for name in OPTIMIZED:
        weights = result.weights[name].loc[fold.test_year]
        pd.testing.assert_series_equal(weights, expected[name]["weights"], check_names=False)
        assert weights.sum() == pytest.approx(1, abs=1e-12) and (weights >= 0).all()
        np.testing.assert_allclose(result.oos_returns.loc[str(fold.test_year), name], test_returns @ weights)
    np.testing.assert_allclose(result.oos_returns.loc[str(fold.test_year), "W"], test_returns["W"])


def test_equal_weight_uses_the_optimizer_universe(short_prices, cfg):
    result = run(short_prices, cfg)
    assert (result.weights[EQUAL_WEIGHT] == 1 / 3).all().all()
    test_returns = simple_returns(short_prices.loc[result.folds[0].train_end:])
    np.testing.assert_allclose(result.oos_returns[EQUAL_WEIGHT], test_returns.mean(axis=1))
    assert result.turnover[EQUAL_WEIGHT].iloc[1:].eq(0).all()
    for name in OPTIMIZED:
        np.testing.assert_allclose(result.weights[name].sum(axis=1), 1, atol=1e-12)


def test_oos_metrics_reuse_engine_conventions(short_prices, cfg):
    result = run(short_prices, cfg)
    expected = compute_asset_metrics(result.nav, cfg.trading_days, cfg.risk_free_rate,
                                     cfg.calendar_days_per_year).loc[result.metrics.index]
    pd.testing.assert_frame_equal(result.metrics, expected)
    assert list(result.metrics.index) == ["Maximum Sharpe", "Minimum Volatility", EQUAL_WEIGHT, "W"]
    pd.testing.assert_frame_equal(growth_metrics(result.oos_returns, result.nav.index[0], cfg), result.metrics)


def test_missing_benchmark_is_explicit(short_prices, cfg):
    with pytest.raises(ValueError, match="Benchmark 'MSCI World'"):
        walk_forward(short_prices, cfg, train_years=2)


def test_turnover_definition():
    weights = pd.DataFrame({"A": [.5, .2, .2], "B": [.5, .8, .3], "C": [0., 0., .5]}, index=[2011, 2012, 2013])
    result = turnover(weights)
    assert np.isnan(result.loc[2011])
    assert result.loc[2012] == pytest.approx(.3)
    assert result.loc[2013] == pytest.approx(.5)


def test_hhi_and_effective_number():
    weights = pd.DataFrame({"A": [1., .25, .5], "B": [0., .25, .5], "C": [0., .25, 0.], "D": [0., .25, 0.]})
    np.testing.assert_allclose(hhi(weights), [1., .25, .5])
    np.testing.assert_allclose(concentration(weights)["Effective assets"], [1., 4., 2.])


def test_weight_stability_statistics():
    weights = pd.DataFrame({"A": [.6, .4, 0.], "B": [.4, .6, 1.]})
    stats = weight_stability(weights)
    assert stats.loc["A", "Mean weight"] == pytest.approx(1 / 3)
    assert (stats.loc["A", "Min weight"], stats.loc["A", "Max weight"]) == (0., .6)
    assert stats.loc["A", "Std weight"] == pytest.approx(np.std([.6, .4, 0.], ddof=1))
    assert stats.loc["A", "Zero-weight share"] == pytest.approx(1 / 3)
    assert stats.loc["B", "Zero-weight share"] == 0


def test_window_prices_prepends_only_the_previous_observation(short_prices):
    window = window_prices(short_prices, "2011-01-01", "2011-12-31")
    assert window.index[0] == pd.Timestamp("2010-12-31")
    assert window.index[1] == pd.Timestamp("2011-01-03") and window.index[-1] == pd.Timestamp("2011-12-30")
    # Before the data start there is no base: the window starts at the first observation.
    assert window_prices(short_prices, "2001-01-01", "2010-01-31").index[0] == short_prices.index[0]


def test_subperiods_respect_availability_and_rerun_the_engine(short_prices, cfg):
    periods = (("2008-01-01", "2011-12-31"), ("2012-01-01", "2013-12-31"), ("2014-01-01", None))
    result = subperiod_stability(short_prices, cfg, periods)
    assert list(result.periods["First date"]) == [pd.Timestamp("2009-12-30"), pd.Timestamp("2012-01-02"),
                                                  pd.Timestamp("2014-01-01")]
    assert result.periods["Last date"].iloc[-1] == short_prices.index[-1]
    label = result.periods.index[1]
    expected = PortfolioOptimizer(short_prices.loc["2011-12-30":"2013-12-31"], cfg).core_portfolios()
    for name in OPTIMIZED:
        pd.testing.assert_series_equal(result.weights.loc[(name, label)], expected[name]["weights"],
                                       check_names=False)
        assert result.weights.loc[name].sum(axis=1).sub(1).abs().max() < 1e-12
    assert set(result.stability.index.get_level_values("Portfolio")) == set(OPTIMIZED)
    assert set(result.stability.columns) == {"Mean weight", "Min weight", "Max weight", "Std weight",
                                             "Zero-weight share"}
