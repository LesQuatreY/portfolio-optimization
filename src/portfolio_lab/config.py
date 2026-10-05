"""One immutable, explicit configuration for the entire study."""
from dataclasses import dataclass
from pathlib import Path
import math


@dataclass(frozen=True)
class Asset:
    name: str
    symbol: str
    instrument: str
    currency: str
    return_type: str
    distributions: str
    limitation: str = ""
    reference: str = ""
    usable_start: str | None = None


@dataclass(frozen=True)
class Config:
    assets: tuple[Asset, ...]
    leverage: tuple[tuple[str, float], ...] = (("Apple", 1.5), ("Nasdaq 100", 2.0))
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
            for asset in self.assets:
                if asset.usable_start is not None:
                    date.fromisoformat(asset.usable_start)
        except (TypeError, ValueError) as exc:
            raise ValueError("Exclusive end and asset usable-start dates must use ISO YYYY-MM-DD.") from exc
        names = [a.name for a in self.assets]
        if not names or len(set(names)) != len(names) or len({a.symbol for a in self.assets}) != len(names):
            raise ValueError("Assets must have distinct nonempty names and symbols.")
        if any(not a.name.strip() or not a.symbol.strip() or a.currency not in {"EUR", "USD"}
               or a.return_type not in {"Price Return", "Total Return", "Gross Return", "Net Return", "Adjusted price"}
               for a in self.assets):
            raise ValueError("Invalid asset metadata or unsupported currency/return type.")
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
            if name not in names or not math.isfinite(factor) or factor <= 0:
                raise ValueError(f"Invalid leverage for {name}.")
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
    return Config(cache_dir=Path(project_dir) / ".cache/market", output_dir=Path(project_dir) / "outputs", assets=(
        Asset("Apple", "AAPL", "Primary US equity", "USD", "Adjusted price",
              "Yahoo split/dividend adjustment; reinvestment proxy before investor tax",
              "Adjusted prices are a vendor proxy, not an independently audited TR index."),
        Asset("Nasdaq 100", "QQQ", "Invesco QQQ ETF; Nasdaq-100 exposure proxy", "USD", "Adjusted price",
              "Yahoo dividend/split adjustments; distributions assumed reinvested",
              "Exact Nasdaq-100 TR unavailable from tested Yahoo ^XNDX. QQQ is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark.",
              "https://www.invesco.com/qqq-etf/en/home.html"),
        Asset("S&P 500", "^SP500TR", "S&P 500 Total Return index", "USD", "Gross Return",
              "Gross dividends reinvested by index methodology", reference="https://www.spglobal.com/spdji/en/indices/equity/sp-500/"),
        Asset("Dow Jones", "DIA", "State Street SPDR Dow Jones Industrial Average ETF proxy", "USD", "Adjusted price",
              "Yahoo dividend/split adjustments; distributions assumed reinvested",
              "Exact Dow Jones TR unavailable from tested Yahoo ^DJITR. DIA is an ETF proxy with fund fees/tracking differences, not the gross TR benchmark.",
              "https://www.ssga.com/us/en/individual/etfs/state-street-spdr-dow-jones-industrial-average-etf-trust-dia"),
        Asset("CAC 40", "CACC.PA", "Amundi CAC 40 UCITS ETF Acc; FR0013380607 proxy", "EUR", "Adjusted price",
              "Accumulating share class reinvests within fund; Yahoo adjusted close",
              "Exact CAC 40 GR unavailable from tested Yahoo ^PX1GR. ETF proxy includes fees/tracking effects. Vendor history before issuer-reported 2019-09-05 share-class creation is excluded from the study; lineage discrepancy unresolved.",
              "https://www.amundietf.fr/pdfDocuments/monthly-factsheet/FR0013380607/FRA/FRA/RETAIL/ETF/20251130", usable_start="2019-09-05"),
        Asset("Gold", "GC=F", "Yahoo continuous COMEX gold futures quotation", "USD", "Price Return",
              "No dividends; quoted futures price changes only",
              "Not spot gold or an investable futures total-return index: roll, collateral yield and contract stitching are unmodeled."),
    ))
