from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from portfolio_lab.optimization import PortfolioOptimizer, select_frontier_assets


def test_optimization_independent_risk_growth_and_feasibility(config, portfolio_prices):
    optimizer = PortfolioOptimizer(portfolio_prices, config)
    result = optimizer.run()
    # Independent known optimum: uncorrelated shocks, variance ratio 4:1.
    np.testing.assert_allclose(result.weights.loc["Minimum Volatility"], [.2, .8], atol=1e-5)
    assert result.portfolios["Low"]["weights"] is None
    minimum = result.portfolios["Minimum Volatility"]
    maximum = result.portfolios["Maximum CAGR"]
    infeasible = optimizer.target(0., minimum, maximum, "probe")
    assert infeasible["weights"] is None
    returns = portfolio_prices.to_numpy()[1:] / portfolio_prices.to_numpy()[:-1] - 1
    years = 64 / 365.25
    for name, weights in result.weights.iterrows():
        if result.portfolios[name]["weights"] is None:
            continue
        assert weights.sum() == pytest.approx(1, abs=1e-8)
        assert weights.min() >= 0
        daily = returns @ weights.to_numpy()
        growth = np.prod(1 + daily)**(1 / years) - 1
        vol = np.sqrt(np.sum((daily - daily.mean())**2) / (len(daily) - 1) * 252)
        assert result.summary.loc[name, "CAGR"] == pytest.approx(growth, abs=1e-10)
        assert result.summary.loc[name, "Volatility"] == pytest.approx(vol, abs=1e-10)
        if name in dict(config.targets):
            assert vol <= dict(config.targets)[name] + config.tolerance
    assert np.linalg.eigvalsh(result.covariance).min() >= -1e-12
    assert (np.diff(result.frontier["CAGR"]) >= -config.tolerance).all()
    assert (result.dominance["Frontier CAGR"] >= result.dominance["100% CAGR"] - config.tolerance).all()
    # Retried attempts are disclosed; the final attempt for each solve must succeed.
    assert result.solver_log.groupby("Portfolio", sort=False).tail(1)["Success"].all()


def test_infeasible_target_and_high_cap(config, portfolio_prices):
    # Single exposure with nonzero risk guarantees a genuinely infeasible ceiling.
    optimizer = PortfolioOptimizer(portfolio_prices[["A"]], replace(config, targets=(("Impossible", .001), ("High", 10.))))
    result = optimizer.run()
    assert result.portfolios["Impossible"]["weights"] is None
    assert result.weights.loc["Impossible"].isna().all()
    assert "Infeasible" in result.summary.loc["Impossible", "Status"]
    np.testing.assert_allclose(result.weights.loc["High"], [1])


def test_universe_replacement(config):
    config = replace(config, leverage=(("A", 1.5),))
    assert select_frontier_assets(config) == ["A x1.5", "B"]
    assert select_frontier_assets(replace(config, include_leveraged_in_frontier=False)) == ["A", "B"]


def test_no_targets(config, portfolio_prices):
    result = PortfolioOptimizer(portfolio_prices, replace(config, targets=())).run()
    assert len(result.summary) == 3


def test_nonpositive_excess_sharpe(config, portfolio_prices):
    result = PortfolioOptimizer(portfolio_prices, replace(config, risk_free_rate=2., targets=())).run()
    mu = (portfolio_prices.pct_change(fill_method=None).iloc[1:].mean() * 252).to_numpy()
    covariance = result.covariance.to_numpy()
    grid = np.linspace(0, 1, 1001)
    weights = np.column_stack([grid, 1 - grid])
    vols = np.sqrt(np.einsum('ij,jk,ik->i', weights, covariance, weights).clip(1e-24))
    grid_sharpe = (weights @ mu - 2.) / vols
    assert result.summary.loc["Maximum Sharpe", "Sharpe"] >= grid_sharpe.max() - 1e-6


def test_covariance_cancellation_near_perfect_hedge(config):
    shocks = np.array([-.02, .012, -.015, .024, .008, -.005, .015, -.01] * 8)
    returns = np.column_stack([.001 + shocks, .0006 - .5 * shocks])
    prices = pd.DataFrame(np.vstack([np.ones(2), np.cumprod(1 + returns, axis=0)]),
                          index=pd.date_range("2020-01-01", periods=65), columns=["A", "B"])
    optimizer = PortfolioOptimizer(prices, config)
    metrics = optimizer.metrics(np.array([1/3, 2/3]))
    assert metrics["Volatility"] < 1e-12
