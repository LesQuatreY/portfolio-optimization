"""Single covariance estimator for the portfolio engine's risk model."""
from dataclasses import dataclass
import numpy as np
import pandas as pd

COVARIANCE_METHODS = {"ledoit_wolf": "Ledoit-Wolf", "sample": "Sample"}
COVARIANCE_FREQUENCIES = ("daily", "weekly")
# Weekly convention: the last common close of each week ending Friday (W-FRI); annualized x 52.
WEEKLY_RULE = "W-FRI"
WEEKS_PER_YEAR = 52


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


def weekly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple returns between consecutive week-end closes (last common observation of each W-FRI week).

    A week whose Friday is a holiday uses its last available common close (e.g. Thursday); a week with no
    common observation is skipped, so its move is carried by the next weekly return (never filled).
    """
    from .returns import simple_returns
    week_end = prices.groupby(prices.index.to_period(WEEKLY_RULE)).tail(1)
    return simple_returns(week_end)


def estimate_covariance_from_prices(prices: pd.DataFrame, method: str = "ledoit_wolf", frequency: str = "daily",
                                    trading_days: int = 252) -> CovarianceEstimate:
    """Annualized covariance from daily prices, sampled daily (x trading_days) or weekly (x 52).

    Weekly sampling reduces the bias of asynchronous closes (markets closing at different hours) on
    correlations. Only the risk model changes: expected returns and portfolio accounting stay daily.
    """
    from .returns import simple_returns
    if frequency not in COVARIANCE_FREQUENCIES:
        raise ValueError(f"Unsupported covariance frequency '{frequency}'; use one of {COVARIANCE_FREQUENCIES}.")
    if frequency == "daily":
        return estimate_covariance(simple_returns(prices), method, trading_days)
    weekly = weekly_returns(prices)
    if len(weekly) <= prices.shape[1] + 1:
        raise ValueError("Too few weekly observations for a covariance estimate.")
    return estimate_covariance(weekly, method, WEEKS_PER_YEAR)
