"""Long-only constant-weight historical growth optimization with risk ceilings."""
from dataclasses import dataclass, replace
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from .config import Config, with_max_weights
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


DOMINANCE_COLUMNS = ["Asset", "100% CAGR", "100% volatility", "Frontier CAGR", "Frontier volatility",
                     "100% estimated volatility", "Frontier estimated volatility"]


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
        # Optional investor upper bounds (policy, not model); 1 = only the long-only bound.
        limits = dict(config.max_weights)
        outside = [name for name in limits if name not in prices.columns]
        if outside:
            raise ValueError(f"Investor max weights {outside} do not match optimizer assets {list(prices.columns)}.")
        self.upper = np.array([float(limits.get(name, 1.)) for name in prices.columns])
        self.constrained = bool((self.upper < 1).any())
        if self.upper.sum() < 1 - 1e-12:
            raise ValueError(f"Investor max weights are infeasible: the {self.n} asset limits sum to "
                             f"{self.upper.sum():.2%} < 100%.")
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

    def cap_and_normalize(self, x, lower=None, upper=None):
        """Clip to [lower, upper] and restore sum 1 without leaving any bound (fixed weights stay exact)."""
        lower = np.zeros(self.n) if lower is None else lower
        upper = self.upper if upper is None else upper
        w = np.clip(x, lower, upper)
        residual = 1 - w.sum()
        if residual > 0:
            room = upper - w
            w = w + residual * room / room.sum()
        elif residual < 0:
            room = w - lower
            w = w + residual * room / room.sum()
        return np.clip(w, lower, upper)

    def solve(self, objective, gradient, start, label: str, target: float | None = None,
              bounds: list[tuple[float, float]] | None = None):
        constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1,
                        "jac": lambda w: np.ones(self.n)}]
        if target is not None:
            scale = max(target**2, 1e-12)
            constraints.append({"type": "ineq", "fun": lambda w: (target**2 - self.variance(w)) / scale,
                                "jac": lambda w: -2 * self.sigma @ w / scale})
        attempts = []
        explicit = bounds is not None
        if not explicit:
            bounds = [(0., float(cap)) for cap in self.upper] if self.constrained else [(0., 1.)] * self.n
        lower, upper = (np.array([b[0] for b in bounds]), np.array([b[1] for b in bounds]))
        for ftol in (1e-10, 1e-7):
            result = minimize(objective, start, jac=gradient, method="SLSQP",
                              bounds=bounds, constraints=constraints,
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
        if (not np.isfinite(result.x).all() or (result.x < lower - 1e-8).any()
                or (result.x > upper + 1e-8).any() or abs(result.x.sum() - 1) > 1e-8):
            raise RuntimeError(f"{label}: optimizer returned infeasible weights.")
        if explicit:
            w = self.cap_and_normalize(result.x, lower, upper)
        elif self.constrained:
            w = self.cap_and_normalize(result.x)
        else:
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

    def objective_sharpe(self, w) -> float:
        """The Maximum Sharpe objective value (model expected return over estimated volatility)."""
        return -self.sharpe_objective(np.asarray(w, dtype=float))

    def fixed_weight_sharpe(self, asset: str, weight: float, starts) -> dict:
        """Maximum Sharpe with `asset` held at exactly `weight`; all other weights re-optimized."""
        i = list(self.prices.columns).index(asset)
        if self.upper[i] < weight:
            raise ValueError(f"Fixed weight {weight:.2%} for {asset} exceeds its investor limit.")
        if weight == 1:
            return self.metrics(np.eye(self.n)[i])
        lower, upper = np.zeros(self.n), self.upper.copy()
        lower[i] = upper[i] = weight
        if upper.sum() < 1 - 1e-12:
            raise ValueError(f"Fixed weight {weight:.2%} for {asset} is infeasible with the other limits.")
        candidates = []
        for start in starts:
            # Project each start onto the fixed-weight slice: asset = weight, others scaled to 1 - weight.
            rest = np.clip(np.asarray(start, dtype=float), 0, None)
            rest[i] = 0
            rest = rest if rest.sum() > 0 else np.where(np.arange(self.n) == i, 0., 1.)
            point = rest / rest.sum() * (1 - weight)
            point[i] = weight
            candidates.append(self.solve(self.sharpe_objective, self.sharpe_gradient, point,
                                         f"Fixed {asset} {weight:.4f}", bounds=list(zip(lower, upper))))
        return min(candidates, key=lambda p: self.sharpe_objective(p["weights"].to_numpy()))

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
            if self.upper[i] < 1:
                # A 100% position is outside the investor's limits, so it is not a frontier competitor.
                continue
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
                                   pd.DataFrame(dominance, columns=DOMINANCE_COLUMNS).set_index("Asset"),
                                   pd.DataFrame(self.log),
                                   self.estimate.label, self.estimate.shrinkage,
                                   self.expected.label, self.expected.shrinkage)


def optimize_frontier(prices: pd.DataFrame, config: Config) -> OptimizationResults:
    return PortfolioOptimizer(prices[select_frontier_assets(config)], config).run()


COMPARED_PORTFOLIOS = ("Maximum Sharpe", "Minimum Volatility", "Maximum CAGR")
COST_METRICS = ("CAGR", "Volatility", "Sharpe", "Max Drawdown")


@dataclass
class InvestorConstraintComparison:
    """Unconstrained statistical optimum next to the best portfolio within investor limits.

    Difference = constrained - unconstrained (realized historical metrics on the same data).
    """
    limits: pd.Series
    unconstrained: OptimizationResults
    constrained: OptimizationResults
    cost: pd.DataFrame
    weights: pd.DataFrame

    def formatted(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        def fmt(metric, value, signed=False):
            if pd.isna(value):
                return "—"
            sign = "+" if signed else ""
            return f"{value:{sign}.3f}" if metric == "Sharpe" else f"{value:{sign}.2%}"
        cost = self.cost.copy().astype(object)
        for (portfolio, metric), row in self.cost.iterrows():
            cost.loc[(portfolio, metric)] = [fmt(metric, row["Unconstrained"]), fmt(metric, row["Constrained"]),
                                             fmt(metric, row["Difference"], signed=True)]
        weights = self.weights.copy().astype(object)
        for column in weights:
            weights[column] = self.weights[column].map(lambda v: fmt("w", v, column == "Difference"))
        return cost, weights


def compare_investor_constraints(prices: pd.DataFrame, config: Config,
                                 max_weights: dict[str, float] | None = None,
                                 portfolios=COMPARED_PORTFOLIOS) -> InvestorConstraintComparison:
    """Run the unconstrained reference and the investor-constrained optimizer on the same prices.

    `max_weights` (e.g. {"Gold": 0.10}) overrides config.max_weights; the reference always
    drops every investor limit, so the statistical optimum stays visible.
    """
    constrained_config = config if max_weights is None else with_max_weights(config, max_weights)
    if not constrained_config.max_weights:
        raise ValueError("No investor max weights configured; the unconstrained optimizer is the reference.")
    reference = optimize_frontier(prices, replace(constrained_config, max_weights=()))
    constrained = optimize_frontier(prices, constrained_config)
    limits = pd.Series(dict(constrained_config.max_weights), name="Investor limit", dtype=float)
    cost = pd.DataFrame([{"Portfolio": name, "Metric": metric,
                          "Unconstrained": float(reference.summary.loc[name, metric]),
                          "Constrained": float(constrained.summary.loc[name, metric])} for name in portfolios
                         for metric in COST_METRICS]).set_index(["Portfolio", "Metric"])
    cost["Difference"] = cost["Constrained"] - cost["Unconstrained"]
    weights = pd.concat({name: pd.DataFrame({"Unconstrained": reference.weights.loc[name],
                                             "Constrained": constrained.weights.loc[name]})
                         for name in portfolios}, names=["Portfolio", "Asset"])
    weights["Difference"] = weights["Constrained"] - weights["Unconstrained"]
    weights["Investor limit"] = weights.index.get_level_values("Asset").map(limits)
    return InvestorConstraintComparison(limits, reference, constrained, cost, weights)


PROFILE_THRESHOLDS = (.99, .98, .95)


@dataclass
class WeightProfile:
    """Descriptive in-sample map of Maximum Sharpe as one asset's weight is held fixed.

    Each row re-optimizes all other weights for the fixed weight. "Objective Sharpe" is the
    quantity Maximum Sharpe maximizes (configured expected returns / estimated volatility);
    loss and retained share are measured on it. "Sharpe" is the realized historical Sharpe.
    Thresholds and ranges are diagnostics only; they are never used as constraints.
    """
    asset: str
    optimum_weight: float
    optimum_objective: float
    table: pd.DataFrame
    weights: pd.DataFrame
    near_optimal: pd.DataFrame
    investor_limit: float | None = None

    def summary(self, step: float = .05) -> pd.DataFrame:
        """Rows on a coarser grid plus the unconstrained optimum, for display."""
        grid = self.table.index.to_numpy()
        keep = np.isclose(np.round(grid / step) * step, grid, atol=1e-9) | np.isclose(grid, self.optimum_weight)
        return self.table.loc[keep]

    def formatted(self, step: float = .05) -> pd.DataFrame:
        table = self.summary(step).copy()
        out = pd.DataFrame(index=[f"{w:.1%}" + (" (optimum)" if np.isclose(w, self.optimum_weight) else "")
                                  for w in table.index])
        out.index.name = f"{self.asset} weight"
        out["CAGR"] = [f"{v:.2%}" for v in table["CAGR"]]
        out["Volatility"] = [f"{v:.2%}" for v in table["Volatility"]]
        out["Sharpe"] = [f"{v:.3f}" for v in table["Sharpe"]]
        out["Objective Sharpe"] = [f"{v:.3f}" for v in table["Objective Sharpe"]]
        out["Loss vs optimum"] = [f"{v:+.3f}" for v in table["Loss vs optimum"]]
        out["Sharpe retained"] = [f"{v:.1%}" for v in table["Sharpe retained"]]
        return out


def sharpe_weight_profile(prices: pd.DataFrame, config: Config, asset: str,
                          weights=None, thresholds=PROFILE_THRESHOLDS) -> WeightProfile:
    """How much Maximum Sharpe changes when `asset` is fixed at each weight (others re-optimized).

    Maps the unconstrained in-sample objective surface: configured investor limits are not
    applied (the asset's limit, if any, is only recorded for display). The default grid is
    0%..100% in 1% steps plus the exact unconstrained optimum, which must be recovered.
    """
    reference = replace(config, max_weights=())
    prices = prices[select_frontier_assets(reference)]
    if asset not in prices.columns:
        raise ValueError(f"'{asset}' is not an optimizer asset; choose from {list(prices.columns)}.")
    grid = np.round(np.linspace(0, 1, 101), 10) if weights is None else np.asarray(weights, dtype=float)
    if grid.ndim != 1 or not len(grid) or not np.isfinite(grid).all() or (grid < 0).any() or (grid > 1).any():
        raise ValueError("Fixed weights must be a nonempty list of finite values in [0, 1].")
    optimizer = PortfolioOptimizer(prices, reference)
    core = optimizer.core_portfolios()
    best = core["Maximum Sharpe"]["weights"]
    optimum_weight = float(best[asset])
    optimum = optimizer.objective_sharpe(best.to_numpy())
    grid = np.unique(np.r_[grid, optimum_weight])
    rows, allocations, previous = [], {}, None
    for weight in grid:
        starts = [optimizer.equal, best.to_numpy(), core["Minimum Volatility"]["weights"].to_numpy()]
        starts += [] if previous is None else [previous]
        result = optimizer.fixed_weight_sharpe(asset, float(weight), starts)
        previous = result["weights"].to_numpy()
        objective = optimizer.objective_sharpe(previous)
        rows.append({"Weight": float(weight), "CAGR": result["CAGR"], "Volatility": result["Volatility"],
                     "Sharpe": result["Sharpe"], "Objective Sharpe": objective,
                     "Loss vs optimum": objective - optimum,
                     "Sharpe retained": objective / optimum if optimum > 0 else np.nan})
        allocations[float(weight)] = result["weights"]
    table = pd.DataFrame(rows).set_index("Weight")
    near = []
    for level in thresholds:
        inside = table.index[table["Sharpe retained"] >= level]
        positions = np.flatnonzero(table["Sharpe retained"].to_numpy() >= level)
        near.append({"Threshold": f">= {level:.0%} of optimal Sharpe",
                     "Min weight": inside.min() if len(inside) else np.nan,
                     "Max weight": inside.max() if len(inside) else np.nan,
                     "Contiguous": bool(len(positions) and (np.diff(positions) == 1).all())})
    limit = dict(config.max_weights).get(asset)
    return WeightProfile(asset, optimum_weight, optimum, table,
                         pd.DataFrame(allocations).T.rename_axis(f"{asset} weight"),
                         pd.DataFrame(near).set_index("Threshold"), limit)
