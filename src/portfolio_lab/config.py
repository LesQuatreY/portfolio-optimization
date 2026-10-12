"""One immutable, explicit configuration for the entire study."""
from dataclasses import dataclass, replace
from collections.abc import Mapping
from pathlib import Path
import math


from .assets import Asset, resolve_assets
from .covariance import validate_covariance_method
from .expected_returns import validate_expected_return_method
from .protocol import RESEARCH_END, assert_end_allowed

WINDOW_KINDS = ("rolling", "expanding")
REBALANCE_MODES = ("annual", "daily")


@dataclass(frozen=True)
class WalkForwardSettings:
    """Walk-forward protocol. Defaults reproduce the legacy engine semantics; the shared
    research configuration (config/research.yaml) sets the authoritative values.

    * window: "rolling" (fixed `train_years`) or "expanding" (all history since the data start;
      same test years as the rolling design so both are comparable).
    * first_test_year / last_test_year: None = every feasible year in the data.
    * rebalance: "annual" = trade to the new targets once, at the close of the rebalance date,
      then let weights drift with prices during the test year (realistic, costed); "daily" =
      legacy constant mix rebalanced at every common observation (intra-year trading not costed).
    * decision_lag_sessions: sessions between the last observation used for estimation and the
      rebalance close (1 = decide on the previous close, trade at the next close).
    * transaction_cost_bps: cost per unit of traded notional (each buy and each sell pays it).
    """
    window: str = "rolling"
    train_years: int = 10
    first_test_year: int | None = None
    last_test_year: int | None = None
    rebalance: str = "daily"
    decision_lag_sessions: int = 0
    transaction_cost_bps: float = 0.

    def __post_init__(self):
        if self.window not in WINDOW_KINDS:
            raise ValueError(f"Walk-forward window must be one of {WINDOW_KINDS}; got {self.window!r}.")
        if self.rebalance not in REBALANCE_MODES:
            raise ValueError(f"Rebalancing must be one of {REBALANCE_MODES}; got {self.rebalance!r}.")
        if isinstance(self.train_years, bool) or not isinstance(self.train_years, int) or self.train_years < 1:
            raise ValueError("Training window must be a positive whole number of years.")
        if (isinstance(self.decision_lag_sessions, bool) or not isinstance(self.decision_lag_sessions, int)
                or self.decision_lag_sessions < 0):
            raise ValueError("Decision lag must be a nonnegative whole number of sessions.")
        if (isinstance(self.transaction_cost_bps, bool) or not isinstance(self.transaction_cost_bps, (int, float))
                or not math.isfinite(self.transaction_cost_bps) or not 0 <= self.transaction_cost_bps < 1e4):
            raise ValueError("Transaction cost must be finite, in basis points, and in [0, 10000).")
        for year in (self.first_test_year, self.last_test_year):
            if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
                raise ValueError("Test years must be whole calendar years or None.")
        if (self.first_test_year is not None and self.last_test_year is not None
                and self.first_test_year > self.last_test_year):
            raise ValueError("First test year must not be after the last test year.")


@dataclass(frozen=True)
class Config:
    assets: tuple[Asset, ...]
    # Safe default: no synthetic leverage unless explicitly requested.
    leverage: tuple[tuple[str, float], ...] = ()
    # Optional investor policy limits (asset -> maximum weight), not statistical estimates.
    # Empty = unconstrained reference optimizer (long-only, fully invested only).
    max_weights: tuple[tuple[str, float], ...] = ()
    # Optional investor minimum weights, only when explicitly required (never implied by eligibility).
    min_weights: tuple[tuple[str, float], ...] = ()
    # Assets eligible for direct allocation (underlying names). Empty = every configured asset.
    # Loaded-but-ineligible assets (e.g. a benchmark) can never receive a direct weight.
    eligible: tuple[str, ...] = ()
    # Passive benchmark series (a configured asset name) for walk-forward comparisons.
    benchmark: str | None = None
    # Synthetic leverage running costs, accrued on calendar days in the native currency:
    # annual drag = leverage_annual_fee + (L - 1) * leverage_financing_rate (constant convention), or
    # leverage_annual_fee + (L - 1) * (historical base rate of the product's currency + spread).
    leverage_annual_fee: float = 0.
    leverage_financing_rate: float = 0.
    leverage_financing_spread: float = 0.
    # Historical rate series (FRED ids, see portfolio_lab.rates.RATE_SERIES). None / () = constants above.
    risk_free_series: str | None = None
    financing_series: tuple[tuple[str, str], ...] = ()
    # Annual holding cost of turning a non-investable index series into an investable exposure
    # (e.g. a tracker ETF's TER), accrued on calendar days. Never applied to leveraged labels.
    holding_costs: tuple[tuple[str, float], ...] = ()
    targets: tuple[tuple[str, float], ...] = (
        ("Prudent", .15), ("Modéré", .20), ("Dynamique", .30),
        ("Agressif", .40), ("Très agressif", .50),
    )
    include_leveraged_in_frontier: bool = True
    # Optimizer risk model: "ledoit_wolf" (shrinkage) or "sample" (historical sample covariance).
    covariance_method: str = "ledoit_wolf"
    # Sampling frequency of the risk model: "daily" (x trading_days) or "weekly" (W-FRI closes, x 52).
    covariance_frequency: str = "daily"
    # Maximum Sharpe expected returns: "sample" (arithmetic mean; reference default) or "bayes_stein"
    # (Jorion 1986 shrinkage; pre-specified OOS experiment documented in README).
    expected_return_method: str = "sample"
    # Drift used by the growth objective (Maximum CAGR, frontier, risk profiles): "sample" = the raw
    # historical returns (reference); "estimated" = training returns re-centred on the configured
    # expected returns (e.g. Bayes-Stein), r~_t = r_t - mean(r) + mu, leaving risk and path shape unchanged.
    growth_drift: str = "sample"
    # Resampled-efficiency policies (Michaud): average each policy's optimal weights over this many
    # stationary-bootstrap resamples of the training window (0 = off). A Monte Carlo size, not a tuning knob.
    resampling_draws: int = 0
    trading_days: int = 252
    calendar_days_per_year: float = 365.25
    risk_free_rate: float = 0.
    initial_nav: float = 100.
    frontier_points: int = 50
    tolerance: float = 1e-7
    allocation_display_threshold: float = .01
    base_currency: str = "EUR"
    # "yahoo": route each asset to its catalogued Asset.provider; "csv": offline files for every series.
    provider: str = "yahoo"
    # EUR/USD for USD -> EUR conversion, quoted USD per EUR. FRED DEXUSEU starts 1999-01-04
    # (Yahoo EURUSD=X only from 2003-12-01, which used to truncate the common window).
    fx_provider: str = "fred"
    fx_symbol: str = "DEXUSEU"
    # Exclusive end. It can never be later than the locked holdout start (2020-01-01).
    end: str = RESEARCH_END
    # Exclusive end of the development period (in-sample exploration window).
    development_end: str = "2013-01-01"
    walk_forward: WalkForwardSettings = WalkForwardSettings()
    cache_dir: Path = Path(".cache/market")
    output_dir: Path = Path("outputs")

    def __post_init__(self):
        from datetime import date
        try:
            date.fromisoformat(self.end)
            date.fromisoformat(self.development_end)
        except (TypeError, ValueError) as exc:
            raise ValueError("Exclusive end dates must use ISO YYYY-MM-DD.") from exc
        assert_end_allowed(self.end, "Study end")
        assert_end_allowed(self.development_end, "Development end")
        if not isinstance(self.walk_forward, WalkForwardSettings):
            raise ValueError("walk_forward must be a WalkForwardSettings instance.")
        names = [a.name for a in self.assets]
        if not names or len(set(names)) != len(names) or len({a.symbol for a in self.assets}) != len(names):
            raise ValueError("Assets must have distinct nonempty names and symbols.")
        if any(not a.name.strip() or not a.symbol.strip() or a.currency not in {"EUR", "USD"}
               or a.return_type not in {"Price Return", "Total Return", "Gross Return", "Net Return",
                                        "Net Total Return", "Adjusted price"}
               or a.provider not in {"yahoo", "msci"}
               for a in self.assets):
            raise ValueError("Invalid asset metadata or unsupported currency/return type/provider.")
        if self.fx_provider not in {"fred", "yahoo"} or not self.fx_symbol.strip():
            raise ValueError("FX must come from a supported provider ('fred' or 'yahoo') with a series id.")
        validate_covariance_method(self.covariance_method)
        if self.covariance_frequency not in ("daily", "weekly"):
            raise ValueError("covariance_frequency must be 'daily' or 'weekly'.")
        validate_expected_return_method(self.expected_return_method)
        if self.growth_drift not in ("sample", "estimated"):
            raise ValueError("growth_drift must be 'sample' or 'estimated'.")
        if isinstance(self.resampling_draws, bool) or not isinstance(self.resampling_draws, int)                 or self.resampling_draws < 0:
            raise ValueError("resampling_draws must be a nonnegative integer.")
        if self.base_currency != "EUR":
            raise ValueError("This study supports EUR as base currency.")
        if not isinstance(self.include_leveraged_in_frontier, bool):
            raise ValueError("Leverage universe switch must be boolean.")
        if (not isinstance(self.frontier_points, int) or self.frontier_points < 2
                or not isinstance(self.trading_days, int) or self.trading_days <= 0):
            raise ValueError("Invalid frontier resolution or trading-days convention.")
        for field in (self.calendar_days_per_year, self.initial_nav, self.tolerance):
            if not math.isfinite(field) or field <= 0:
                raise ValueError("Duration convention, NAV and tolerance must be finite and positive.")
        if not math.isfinite(self.risk_free_rate) or not 0 <= self.allocation_display_threshold <= 1:
            raise ValueError("Invalid risk-free rate or allocation display threshold.")
        if len(dict(self.leverage)) != len(self.leverage):
            raise ValueError("Duplicate leveraged underlying.")
        for name, factor in self.leverage:
            if name not in names:
                raise ValueError(f"Leveraged underlying '{name}' is not in the configured asset universe. "
                                 "Restore the asset or remove its leverage entry.")
            if not math.isfinite(factor) or factor <= 1:
                raise ValueError(f"Invalid leverage for {name}: factors must be finite and above 1 "
                                 "(omit the asset, or use 1, for no leverage).")
        labels = [f"{name} x{factor:g}" for name, factor in self.leverage]
        if len(set(names + labels)) != len(names + labels):
            raise ValueError("Synthetic labels collide with asset names.")
        for cost in (self.leverage_annual_fee, self.leverage_financing_rate):
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) \
                    or not 0 <= cost < 1:
                raise ValueError("Leverage fee and financing rate must be annual fractions in [0, 1).")
        if not math.isfinite(self.leverage_financing_spread) or not -.05 < self.leverage_financing_spread < .05:
            raise ValueError("Leverage financing spread must be an annual fraction in (-5%, 5%).")
        from .rates import RATE_SERIES
        for series in [self.risk_free_series, *dict(self.financing_series).values()]:
            if series is not None and series not in RATE_SERIES:
                raise ValueError(f"Unknown rate series '{series}'; register it in portfolio_lab.rates.RATE_SERIES.")
        if len(dict(self.financing_series)) != len(self.financing_series) or \
                any(ccy not in {"EUR", "USD"} for ccy, _ in self.financing_series):
            raise ValueError("Financing series must map distinct currencies (EUR, USD) to series ids.")
        if len(dict(self.holding_costs)) != len(self.holding_costs):
            raise ValueError("Duplicate asset in holding costs.")
        for name, cost in self.holding_costs:
            if name not in names:
                raise ValueError(f"Holding cost for '{name}': not a configured asset (choose from {names}).")
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not 0 <= cost < .05:
                raise ValueError(f"Holding cost for '{name}' must be an annual fraction in [0, 5%).")
        if len(set(self.eligible)) != len(self.eligible):
            raise ValueError("Duplicate eligible asset.")
        unknown = [name for name in self.eligible if name not in names]
        if unknown:
            raise ValueError(f"Eligible assets {unknown} are not configured assets (choose from {names}).")
        if self.benchmark is not None and self.benchmark not in names:
            raise ValueError(f"Benchmark '{self.benchmark}' is not a configured asset (choose from {names}).")
        if len(dict(self.max_weights)) != len(self.max_weights):
            raise ValueError("Duplicate asset in investor max weights.")
        for name, cap in self.max_weights:
            if name not in names + labels:
                raise ValueError(f"Investor max weight for '{name}': not a configured asset "
                                 f"(choose from {names + labels}).")
            if isinstance(cap, bool) or not isinstance(cap, (int, float)) or not math.isfinite(cap) \
                    or not 0 < cap <= 1:
                raise ValueError(f"Investor max weight for '{name}' must satisfy 0 < weight <= 1; got {cap!r}.")
        if len(dict(self.min_weights)) != len(self.min_weights):
            raise ValueError("Duplicate asset in investor min weights.")
        caps = dict(self.max_weights)
        for name, floor in self.min_weights:
            if name not in names + labels:
                raise ValueError(f"Investor min weight for '{name}': not a configured asset "
                                 f"(choose from {names + labels}).")
            if isinstance(floor, bool) or not isinstance(floor, (int, float)) or not math.isfinite(floor) \
                    or not 0 < floor <= 1:
                raise ValueError(f"Investor min weight for '{name}' must satisfy 0 < weight <= 1; got {floor!r}.")
            if floor > caps.get(name, 1.):
                raise ValueError(f"Investor min weight for '{name}' ({floor:.2%}) exceeds its max weight.")
        if sum(dict(self.min_weights).values()) > 1 + 1e-12:
            raise ValueError("Investor min weights are infeasible: they sum to more than 100%.")
        if len(dict(self.targets)) != len(self.targets) or any(
            not isinstance(name, str) or not name.strip() or not math.isfinite(risk) or risk < 0
            or name in {"Minimum Volatility", "Maximum CAGR", "Maximum Sharpe"} for name, risk in self.targets
        ):
            raise ValueError("Targets must have unique names and finite nonnegative ceilings.")


def load_config(project_dir: Path = Path(".")) -> Config:
    """Package defaults (legacy universe, no leverage, legacy walk-forward semantics).

    Research notebooks use the shared configuration instead:
    portfolio_lab.research.load_research_config().
    """
    assets = {
        "Apple": "AAPL", "Nasdaq 100": "QQQ", "MSCI World": "MSCI:990100:NETR",
        "S&P 500": "^SP500TR", "Dow Jones": "DIA", "Gold": "GC=F", "Coca-Cola": "KO",
    }
    return Config(cache_dir=Path(project_dir) / ".cache/market",
                  output_dir=Path(project_dir) / "outputs", assets=resolve_assets(assets))


def configure_universe(config: Config, assets: Mapping[str, str],
                       leverage: Mapping[str, float] | None = None, *,
                       catalogue: Mapping[str, Asset] | None = None) -> Config:
    """Resolve notebook name -> symbol selections into the full study config.

    Metadata comes only from the catalogue; no guessing or ticker fallback.
    An explicit catalogue can be injected for a custom provider or offline fixtures.
    `leverage` fully replaces any existing leverage: None or {} means no leveraged assets,
    and a factor of exactly 1 is the unleveraged asset itself, so it is dropped.
    """
    if leverage is not None and not isinstance(leverage, Mapping):
        raise ValueError("Leveraged assets must be a mapping of asset name to factor, {} or None.")
    selected = tuple((name, factor) for name, factor in (leverage or {}).items() if factor != 1)
    return replace(config, assets=resolve_assets(assets, catalogue=catalogue), leverage=selected)


def with_max_weights(config: Config, max_weights: Mapping[str, float] | None) -> Config:
    """Investor policy limits, e.g. {"Gold": 0.10}; None or {} removes all limits."""
    if max_weights is not None and not isinstance(max_weights, Mapping):
        raise ValueError("Investor max weights must be a mapping of asset name to maximum weight, {} or None.")
    return replace(config, max_weights=tuple((max_weights or {}).items()))


def with_min_weights(config: Config, min_weights: Mapping[str, float] | None) -> Config:
    """Explicit investor minimum weights, e.g. {"MSCI World": 0.20}; None or {} removes them."""
    if min_weights is not None and not isinstance(min_weights, Mapping):
        raise ValueError("Investor min weights must be a mapping of asset name to minimum weight, {} or None.")
    return replace(config, min_weights=tuple((min_weights or {}).items()))


def with_eligible(config: Config, eligible) -> Config:
    """Restrict direct allocation to `eligible` asset names; nothing else in the config changes."""
    return replace(config, eligible=tuple(eligible))


def eligible_names(config: Config) -> list[str]:
    """Underlying asset names eligible for direct allocation, in configuration order."""
    allowed = set(config.eligible) if config.eligible else None
    return [a.name for a in config.assets if allowed is None or a.name in allowed]
