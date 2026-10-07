"""Single covariance estimator for the portfolio engine's risk model."""
from dataclasses import dataclass
import numpy as np
import pandas as pd

COVARIANCE_METHODS = {"ledoit_wolf": "Ledoit-Wolf", "sample": "Sample"}


@dataclass(frozen=True)
class CovarianceEstimate:
    matrix: pd.DataFrame
    method: str
    shrinkage: float | None = None

    @property
    def label(self) -> str:
        return COVARIANCE_METHODS[self.method]


def validate_covariance_method(method: str) -> None:
    if method not in COVARIANCE_METHODS:
        raise ValueError(f"Unsupported covariance method '{method}'; use one of {sorted(COVARIANCE_METHODS)}.")


def estimate_covariance(returns: pd.DataFrame, method: str = "ledoit_wolf",
                        trading_days: int = 252) -> CovarianceEstimate:
    """Annualized covariance of the given daily simple returns, labelled in their column order.

    The daily estimate is multiplied by `trading_days` exactly once (the engine's 252
    common-observation convention). "sample" is pandas' ddof=1 covariance, as before.
    "ledoit_wolf" is scikit-learn's LedoitWolf with its data-driven shrinkage intensity
    (towards a scaled identity; maximum-likelihood 1/n normalization).
    """
    validate_covariance_method(method)
    values = returns.to_numpy(dtype=float)
    if len(returns) < 2 or not np.isfinite(values).all():
        raise ValueError("Covariance needs at least two finite return observations.")
    shrinkage = None
    if method == "sample":
        annual = returns.cov() * trading_days
    else:
        from sklearn.covariance import LedoitWolf
        fitted = LedoitWolf().fit(values)
        shrinkage = float(fitted.shrinkage_)
        annual = pd.DataFrame(fitted.covariance_ * trading_days, index=returns.columns, columns=returns.columns)
    matrix = annual.to_numpy()
    if not np.isfinite(matrix).all() or not np.allclose(matrix, matrix.T, rtol=0, atol=1e-15 * np.abs(matrix).max()):
        raise ValueError(f"{COVARIANCE_METHODS[method]} covariance is not finite and symmetric.")
    return CovarianceEstimate(annual, method, shrinkage)
