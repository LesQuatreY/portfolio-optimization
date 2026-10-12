"""Single expected-return estimator for the optimizer's model (Maximum Sharpe).

"sample": arithmetic mean of daily simple returns x trading_days (the earlier engine).

"bayes_stein": Jorion (1986) Bayes-Stein estimator. P. Jorion, "Bayes-Stein Estimation
for Portfolio Analysis", Journal of Financial and Quantitative Analysis 21(3), 279-292.
From T daily returns of N assets (all quantities daily, fitted on the given returns only):

    m      = sample mean vector
    Sigma  = S * (T - 1) / (T - N - 2),  S = sample covariance (ddof=1)
    mu0    = (1' Sigma^-1 m) / (1' Sigma^-1 1)        minimum-variance portfolio mean
    lambda = (N + 2) / ((m - mu0 1)' Sigma^-1 (m - mu0 1))
    w      = lambda / (T + lambda) = (N + 2) / ((N + 2) + T (m - mu0 1)' Sigma^-1 (m - mu0 1))
    mu_BS  = (1 - w) m + w mu0 1

w lies in (0, 1] by construction (w = 1 when all means already equal mu0), so no
clipping or user-chosen intensity is involved. Only Jorion's mean estimator is used;
the optimizer's covariance stays the configured covariance estimator. The result is
annualized once by trading_days, like the sample mean.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

EXPECTED_RETURN_METHODS = {"bayes_stein": "Bayes-Stein (Jorion 1986)", "sample": "Sample mean",
                           "anchored": "Anchored (Black-Litterman, ERC equilibrium)"}


@dataclass(frozen=True)
class ExpectedReturnEstimate:
    values: pd.Series
    method: str
    shrinkage: float | None = None
    target: float | None = None

    @property
    def label(self) -> str:
        return EXPECTED_RETURN_METHODS[self.method]


def validate_expected_return_method(method: str) -> None:
    if method not in EXPECTED_RETURN_METHODS:
        raise ValueError(f"Unsupported expected-return method '{method}'; "
                         f"use one of {sorted(EXPECTED_RETURN_METHODS)}.")


def estimate_expected_returns(returns: pd.DataFrame, method: str = "sample",
                              trading_days: int = 252) -> ExpectedReturnEstimate:
    """Annualized expected returns of the given daily simple returns, labelled in column order."""
    validate_expected_return_method(method)
    values = returns.to_numpy(dtype=float)
    if len(returns) < 2 or not np.isfinite(values).all():
        raise ValueError("Expected returns need at least two finite return observations.")
    mean = values.mean(axis=0)
    if method == "anchored":
        raise ValueError("Anchored expected returns need an anchor portfolio: use anchored_expected_returns "
                         "(PortfolioOptimizer builds it from the window's equal risk contribution portfolio).")
    if method == "sample":
        return ExpectedReturnEstimate(pd.Series(mean * trading_days, index=returns.columns), method)
    t, n = values.shape
    if t <= n + 2:
        raise ValueError(f"Bayes-Stein needs more than N + 2 = {n + 2} return observations; got {t}.")
    sigma = np.cov(values, rowvar=False, ddof=1).reshape(n, n) * (t - 1) / (t - n - 2)
    ones = np.ones(n)
    try:
        inv_ones, inv_mean = np.linalg.solve(sigma, np.column_stack([ones, mean])).T
    except np.linalg.LinAlgError as exc:
        raise ValueError("Bayes-Stein needs a nonsingular return covariance.") from exc
    target = float(ones @ inv_mean / (ones @ inv_ones))
    deviation = mean - target
    distance = float(deviation @ np.linalg.solve(sigma, deviation))
    shrinkage = 1. if distance <= 0 else (n + 2) / ((n + 2) + t * distance)
    shrunk = (1 - shrinkage) * mean + shrinkage * target
    annual = pd.Series(shrunk * trading_days, index=returns.columns)
    if not np.isfinite(annual.to_numpy()).all() or not 0 <= shrinkage <= 1:
        raise ValueError("Bayes-Stein estimate is not finite.")
    return ExpectedReturnEstimate(annual, method, float(shrinkage), target * trading_days)


def anchored_expected_returns(returns: pd.DataFrame, sigma_annual: pd.DataFrame, anchor: pd.Series,
                              trading_days: int = 252) -> ExpectedReturnEstimate:
    """Black-Litterman posterior mean with a neutral equilibrium prior implied by an anchor portfolio.

    All quantities in daily units, from the given (training) returns only:

        Sigma  = sigma_annual / trading_days                       risk model of the optimizer
        delta  = m' w_a / (w_a' Sigma w_a)                         anchor's implied return = its sample mean
        pi     = delta * Sigma w_a                                 equilibrium (prior) means
        Omega  = diag(Sigma) / T,  tau * Sigma with tau = 1 / T    view and prior uncertainty
        mu     = (Sigma^-1 + diag(Sigma)^-1)^-1 (Sigma^-1 pi + diag(Sigma)^-1 m)      (T cancels)

    The prior differs by asset and its precision Sigma^-1 is large on differences between highly
    correlated assets, so their noisy mean gaps are pulled toward equilibrium gaps; unlike a common
    shrinkage target, this changes relative expected returns and hence volatility-constrained portfolios.
    `shrinkage` reports delta; `target` the anchor's annualized implied return.
    """
    values = returns.to_numpy(dtype=float)
    if len(returns) < 2 or not np.isfinite(values).all():
        raise ValueError("Anchored expected returns need at least two finite return observations.")
    w = anchor.reindex(returns.columns).to_numpy(dtype=float)
    if not np.isfinite(w).all() or abs(w.sum() - 1) > 1e-8:
        raise ValueError("The anchor must be a fully invested portfolio over the same assets.")
    sigma = sigma_annual.reindex(index=returns.columns, columns=returns.columns).to_numpy() / trading_days
    m = values.mean(axis=0)
    anchor_variance = float(w @ sigma @ w)
    if anchor_variance <= 0:
        raise ValueError("The anchor must have positive variance.")
    delta = float(m @ w) / anchor_variance
    pi = delta * sigma @ w
    prior_precision = np.linalg.inv(sigma)
    view_precision = np.diag(1 / np.diag(sigma))
    posterior = np.linalg.solve(prior_precision + view_precision, prior_precision @ pi + view_precision @ m)
    annual = pd.Series(posterior * trading_days, index=returns.columns)
    if not np.isfinite(annual.to_numpy()).all():
        raise ValueError("Anchored expected returns are not finite.")
    return ExpectedReturnEstimate(annual, "anchored", delta, float(m @ w) * trading_days)
