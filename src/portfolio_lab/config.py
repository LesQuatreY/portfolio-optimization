"""One immutable, explicit configuration for the entire study."""
from dataclasses import dataclass, replace
from collections.abc import Mapping
from pathlib import Path
import math


from .assets import Asset, resolve_assets


@dataclass(frozen=True)
class Config:
    assets: tuple[Asset, ...]
    # Safe default: no synthetic leverage unless explicitly requested.
    leverage: tuple[tuple[str, float], ...] = ()
    targets: tuple[tuple[str, float], ...] = (
        ("Prudent", .15), ("Modéré", .20), ("Dynamique", .30),
        ("Agressif", .40), ("Très agressif", .50),
    )
    include_leveraged_in_frontier: bool = True
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
    fx_symbol: str = "EURUSD=X"
    # Exclusive end: excludes the current, potentially incomplete session.
    end: str = "2026-10-05"
    cache_dir: Path = Path(".cache/market")
    output_dir: Path = Path("outputs")

    def __post_init__(self):
        from datetime import date
        try:
            date.fromisoformat(self.end)
        except (TypeError, ValueError) as exc:
            raise ValueError("Exclusive end must use ISO YYYY-MM-DD.") from exc
        names = [a.name for a in self.assets]
        if not names or len(set(names)) != len(names) or len({a.symbol for a in self.assets}) != len(names):
            raise ValueError("Assets must have distinct nonempty names and symbols.")
        if any(not a.name.strip() or not a.symbol.strip() or a.currency not in {"EUR", "USD"}
               or a.return_type not in {"Price Return", "Total Return", "Gross Return", "Net Return",
                                        "Net Total Return", "Adjusted price"}
               or a.provider not in {"yahoo", "msci"}
               for a in self.assets):
            raise ValueError("Invalid asset metadata or unsupported currency/return type/provider.")
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
        if len(dict(self.targets)) != len(self.targets) or any(
            not isinstance(name, str) or not name.strip() or not math.isfinite(risk) or risk < 0
            or name in {"Minimum Volatility", "Maximum CAGR", "Maximum Sharpe"} for name, risk in self.targets
        ):
            raise ValueError("Targets must have unique names and finite nonnegative ceilings.")


def load_config(project_dir: Path = Path(".")) -> Config:
    """Defaults use verified TR benchmarks when accessible; no automatic fallback."""
    assets = {
        "Apple": "AAPL", "Nasdaq 100": "QQQ", "S&P 500": "^SP500TR",
        "Dow Jones": "DIA", "CAC 40": "PX1GR.PA", "Gold": "GC=F",
        "MSCI World": "MSCI:990100:NETR",
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
