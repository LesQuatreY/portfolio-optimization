"""Long-only constant-weight historical growth optimization with risk ceilings."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from .config import Config
from .metrics import compute_asset_metrics
from .leverage import leveraged_name
from .returns import simple_returns
from .covariance import estimate_covariance
from .expected_returns import estimate_expected_returns


@dataclass
class OptimizationResults:
    portfolios: dict[str, dict]
    frontier: pd.DataFrame
    summary: pd.DataFrame
    weights: pd.DataFrame
    covariance: pd.DataFrame
    dominance: pd.DataFrame
    solver_log: pd.DataFrame
    covariance_estimator: str = "Sample"
    covariance_shrinkage: float | None = None
    expected_return_estimator: str = "Sample mean"
    expected_return_shrinkage: float | None = None


def select_frontier_assets(config: Config) -> list[str]:
    labels = {name: leveraged_name(name, factor) for name, factor in config.leverage}
    return [labels.get(a.name, a.name) if config.include_leveraged_in_frontier else a.name for a in config.assets]


class PortfolioOptimizer:
    """Owns explicit numerical inputs; no notebook globals or provider dependency.

    Risk (minimum-volatility and Sharpe objectives, volatility ceilings, frontier grid)
    uses the configured covariance estimate of these prices' returns only, reported as
    "Estimated volatility". The Maximum Sharpe objective uses the configured expected-return
    estimate ("Estimated return"); Maximum CAGR, the frontier and targets maximize realized
    historical log growth and do not use it. "Volatility", "Mean return annualized",
    "Sharpe", CAGR and drawdown remain realized historical metrics; with the sample
    estimators the model and realized values coincide.
    """

    def __init__(self, prices: pd.DataFrame, config: Config):
        self.config = config
        self.prices = prices
        self.returns = simple_returns(prices)
        self.R = self.returns.to_numpy()
        self.centered = self.R - self.R.mean(axis=0)
        self.estimate = estimate_covariance(self.returns, config.covariance_method, config.trading_days)
        self.covariance = self.estimate.matrix
        self.sigma = self.covariance.to_numpy()
        # Realized arithmetic mean (reported metrics) vs model expected returns (Sharpe objective).
        self.realized_mean = self.R.mean(axis=0) * config.trading_days
        self.expected = estimate_expected_returns(self.returns, config.expected_return_method, config.trading_days)
        self.mu = self.expected.values.to_numpy()
        self.n = prices.shape[1]
        self.years = (prices.index[-1] - prices.index[0]).days / config.calendar_days_per_year
        self.log = []
        self.equal = np.full(self.n, 1 / self.n)
        self.variance_scale = max(float(np.diag(self.sigma).max()), 1e-12)

    def realized_variance(self, w):
        # Algebraically w.T @ Sample @ w, evaluated without cancellation near a
        # perfect hedge. A covariance quadratic can lose precision at zero risk.
        centered_portfolio = self.centered @ w
        return float(centered_portfolio @ centered_portfolio * self.config.trading_days / (len(self.R) - 1))

    def variance(self, w):
        """Risk-model variance w.T @ Sigma @ w for the configured covariance estimator."""
        if self.estimate.method == "sample":
            return self.realized_variance(w)
        return float(w @ self.sigma @ w)

    def growth_objective(self, w):
        factors = np.maximum(1 + self.R @ w, np.finfo(float).tiny)
        return -float(np.log(factors).mean()) * self.config.trading_days

    def growth_gradient(self, w):
        # Cap only numerical boundary evaluations, never reported NAV/CAGR.
        factors = np.maximum(1 + self.R @ w, 1e-15)
        return -(self.R.T @ (1 / factors)) * self.config.trading_days / len(self.R)

    def sharpe_objective(self, w):
        vol = np.sqrt(max(self.variance(w), 1e-24))
        return -float((self.mu @ w - self.config.risk_free_rate) / vol)

    def sharpe_gradient(self, w):
        vol = np.sqrt(max(self.variance(w), 1e-24))
        excess = self.mu @ w - self.config.risk_free_rate
        return -self.mu / vol + excess * (self.sigma @ w) / vol**3

    def solve(self, objective, gradient, start, label: str, target: float | None = None):
        constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1,
                        "jac": lambda w: np.ones(self.n)}]
        if target is not None:
            scale = max(target**2, 1e-12)
            constraints.append({"type": "ineq", "fun": lambda w: (target**2 - self.variance(w)) / scale,
                                "jac": lambda w: -2 * self.sigma @ w / scale})
        attempts = []
        for ftol in (1e-10, 1e-7):
            result = minimize(objective, start, jac=gradient, method="SLSQP",
                              bounds=[(0., 1.)] * self.n, constraints=constraints,
                              options={"ftol": ftol, "maxiter": 1000})
            attempts.append({"Portfolio": label, "Success": bool(result.success),
                             "Status": int(result.status), "Message": str(result.message),
                             "Iterations": result.nit, "ftol": ftol,
                             "Raw minimum weight": float(result.x.min()), "Raw weight sum": float(result.x.sum())})
            if result.success:
                break
            start = result.x
        self.log.extend(attempts)
        if not result.success:
            raise RuntimeError(f"{label}: portfolio optimization failed: {result.message}")
        if (not np.isfinite(result.x).all() or result.x.min() < -1e-8
                or result.x.max() > 1 + 1e-8 or abs(result.x.sum() - 1) > 1e-8):
            raise RuntimeError(f"{label}: optimizer returned infeasible weights.")
        w = np.clip(result.x, 0, 1)
        w /= w.sum()
        if target is not None and np.sqrt(max(self.variance(w), 0)) > target + self.config.tolerance:
            raise RuntimeError(f"{label}: volatility ceiling violated after numerical cleanup.")
        return self.metrics(w, str(result.message), int(result.status))

    def metrics(self, w, message="Reused optimal solution", status=0):
        daily = self.R @ w
        factors = 1 + daily
        cagr = -1. if (factors <= 0).any() else float(np.expm1(np.log(factors).sum() / self.years))
        estimated = np.sqrt(max(self.variance(w), 0))
        vol = np.sqrt(max(self.realized_variance(w), 0))
        np.testing.assert_allclose(estimated**2, float(w @ self.sigma @ w), rtol=1e-9, atol=1e-14)
        np.testing.assert_allclose(vol, daily.std(ddof=1) * np.sqrt(self.config.trading_days), rtol=1e-9, atol=1e-12)
        nav = np.r_[1., np.cumprod(factors)]
        drawdown = float((nav / np.maximum.accumulate(nav) - 1).min())
        mean = float(self.realized_mean @ w)
        return {"CAGR": cagr, "Mean return annualized": mean, "Estimated return": float(self.mu @ w),
                "Volatility": vol, "Estimated volatility": estimated,
                "Max Drawdown": drawdown, "Sharpe": (mean - self.config.risk_free_rate) / vol if vol > 0 else np.nan,
                "Calmar": cagr / abs(drawdown) if drawdown < 0 else np.nan,
                "weights": pd.Series(w, index=self.prices.columns), "Success": True,
                "Solver status": status, "Status": message}

    def target(self, ceiling: float, minimum: dict, maximum: dict, name: str):
        if not np.isfinite(ceiling) or ceiling < 0:
            raise ValueError("Risk ceiling must be finite and nonnegative.")
        # Ceilings bound the risk-model (estimated) volatility.
        if ceiling < minimum["Estimated volatility"] - self.config.tolerance:
            return {"weights": None, "Success": False, "Solver status": None,
                    "Status": "Infeasible: below minimum achievable volatility", "Risk ceiling": ceiling}
        if ceiling >= maximum["Estimated volatility"]:
            result = {**maximum, "Status": "Maximum CAGR reached; unused risk allowance"}
        elif ceiling <= minimum["Estimated volatility"] + 1e-10:
            result = {**minimum, "Status": "Minimum achievable volatility"}
        else:
            result = self.solve(self.growth_objective, self.growth_gradient,
                                minimum["weights"].to_numpy(), name, ceiling)
        return {**result, "Risk ceiling": ceiling}

    def core_portfolios(self) -> dict[str, dict]:
        """Minimum Volatility, Maximum CAGR and multi-start Maximum Sharpe, from these prices only."""
        minimum = self.solve(lambda w: self.variance(w) / self.variance_scale,
                             lambda w: 2 * self.sigma @ w / self.variance_scale, self.equal, "Minimum Volatility")
        maximum = self.solve(self.growth_objective, self.growth_gradient, self.equal, "Maximum CAGR")
        candidates = [self.solve(self.sharpe_objective, self.sharpe_gradient, start, f"Maximum Sharpe start {i}")
                      for i, start in enumerate([self.equal, minimum["weights"].to_numpy(),
                                                maximum["weights"].to_numpy(), *np.eye(self.n)])]
        sharpe = min(candidates, key=lambda p: self.sharpe_objective(p["weights"].to_numpy()))
        return {"Minimum Volatility": minimum, "Maximum CAGR": maximum, "Maximum Sharpe": sharpe}

    def run(self) -> OptimizationResults:
        portfolios = self.core_portfolios()
        minimum, maximum = portfolios["Minimum Volatility"], portfolios["Maximum CAGR"]
        rows = []
        for i, risk in enumerate(np.linspace(minimum["Estimated volatility"], maximum["Estimated volatility"],
                                             self.config.frontier_points)):
            rows.append(self.target(float(risk), minimum, maximum, f"Frontier {i}"))
        frontier = pd.DataFrame(rows)
        for name, risk in self.config.targets:
            if name in portfolios:
                raise ValueError(f"Target name collides with an optimized portfolio: {name}")
            portfolios[name] = self.target(risk, minimum, maximum, name)
        # Validate the exact risk of every feasible vertex, independently of plot resolution.
        standalone = compute_asset_metrics(self.prices, self.config.trading_days,
                                            self.config.risk_free_rate, self.config.calendar_days_per_year)
        dominance = []
        for i, asset in enumerate(self.prices.columns):
            single = self.metrics(np.eye(self.n)[i])
            np.testing.assert_allclose([single["CAGR"], single["Volatility"]],
                [standalone.loc[asset, "CAGR"], standalone.loc[asset, "Volatility annualized"]], atol=1e-10)
            # Dominance at the asset's own risk-model volatility (equal to realized for "sample").
            risk = single["Estimated volatility"]
            if maximum["Estimated volatility"] <= risk:
                optimal = maximum
            elif risk <= minimum["Estimated volatility"] + 1e-10:
                optimal = minimum
            else:
                optimal = self.solve(self.growth_objective, self.growth_gradient, np.eye(self.n)[i],
                                     f"Dominance {asset}", risk)
            if optimal["CAGR"] < single["CAGR"] - self.config.tolerance:
                raise RuntimeError(f"Frontier does not dominate {asset} at its own risk.")
            dominance.append({"Asset": asset, "100% CAGR": single["CAGR"], "100% volatility": single["Volatility"],
                              "Frontier CAGR": optimal["CAGR"], "Frontier volatility": optimal["Volatility"],
                              "100% estimated volatility": risk,
                              "Frontier estimated volatility": optimal["Estimated volatility"]})
        if ((np.diff(frontier["CAGR"]) < -self.config.tolerance).any()
                or (np.diff(frontier["Estimated volatility"]) < -self.config.tolerance).any()):
            raise RuntimeError("Frontier upper branch is not monotonic.")
        summary = pd.DataFrame({name: {k: v for k, v in p.items() if k != "weights"}
                                for name, p in portfolios.items()}).T.rename_axis("Portfolio")
        weights = pd.DataFrame({name: p["weights"] if p["weights"] is not None
                                else pd.Series(np.nan, index=self.prices.columns)
                                for name, p in portfolios.items()}).T.rename_axis("Portfolio")
        return OptimizationResults(portfolios, frontier, summary, weights, self.covariance,
                                   pd.DataFrame(dominance).set_index("Asset"), pd.DataFrame(self.log),
                                   self.estimate.label, self.estimate.shrinkage,
                                   self.expected.label, self.expected.shrinkage)


def optimize_frontier(prices: pd.DataFrame, config: Config) -> OptimizationResults:
    return PortfolioOptimizer(prices[select_frontier_assets(config)], config).run()
