"""Provider boundary, auditable snapshots and observed-date normalization."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import hashlib
import json
import numpy as np
import pandas as pd
from .config import Asset, Config
from .currency import to_eur
from .returns import validate_prices


class Provider(Protocol):
    name: str

    def history(self, asset: Asset, end: str) -> pd.Series:
        """Return named values on unique sorted native session dates, with optional NaNs."""
        ...


def validate_history(series: pd.Series, name: str) -> None:
    if (series.name != name or not isinstance(series.index, pd.DatetimeIndex)
            or series.index.tz is not None or not series.index.is_unique
            or not series.index.is_monotonic_increasing or series.empty
            or series.index.hasnans or not series.index.equals(series.index.normalize())):
        raise ValueError(f"{name}: expected named series with unique sorted, timezone-free session dates.")
    observed = series.dropna()
    if observed.empty or not np.isfinite(observed.to_numpy()).all() or (observed <= 0).any():
        raise ValueError(f"{name}: missing history or invalid observed values.")


class YahooProvider:
    """Single yfinance boundary. Snapshots include download parameters and hashes."""
    name = "Yahoo Finance"

    def __init__(self, cache_dir: Path, *, refresh: bool = False):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        import yfinance as yf
        yf.set_tz_cache_location(str(self.cache_dir / "yfinance"))

    def history(self, asset: Asset, end: str) -> pd.Series:
        import yfinance as yf
        params = {"symbol": asset.symbol, "end_exclusive": end, "interval": "1d",
                  "auto_adjust": asset.return_type == "Adjusted price", "repair": False}
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:20]
        path = self.cache_dir / f"{key}.csv"
        manifest = path.with_suffix(".json")
        if path.exists() and manifest.exists() and not self.refresh:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
            if meta["parameters"] != params or meta["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError(f"Snapshot integrity check failed for {asset.name}.")
            result = pd.read_csv(path, index_col=0, parse_dates=True)["Value"].rename(asset.name)
        else:
            ticker = yf.Ticker(asset.symbol)
            frame = ticker.history(period="max", end=end, interval="1d", auto_adjust=params["auto_adjust"],
                                   actions=True, keepna=True, repair=False, timeout=30, raise_errors=True)
            if frame.empty or "Close" not in frame:
                raise RuntimeError(f"No history for {asset.name} ({asset.symbol}); no substitute was selected.")
            currency = ticker.get_history_metadata().get("currency")
            if currency and currency != asset.currency:
                raise ValueError(f"{asset.symbol}: provider currency {currency} differs from configured {asset.currency}.")
            result = frame["Close"].rename(asset.name)
            # Preserve exchange-local session date; converting to UTC can shift dates.
            result.index = result.index.tz_localize(None).normalize()
            validate_history(result, asset.name)
            result.rename("Value").to_csv(path, float_format="%.17g")
            frame.to_csv(path.with_suffix(".source.csv"), float_format="%.17g")
            manifest.write_text(json.dumps({"provider": self.name, "parameters": params,
                "downloaded_at_utc": pd.Timestamp.now(tz="UTC").isoformat(), "vendor_currency": currency,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2), encoding="utf-8")
        validate_history(result, asset.name)
        if (result.index >= pd.Timestamp(end)).any():
            raise ValueError(f"{asset.name}: provider returned dates at or beyond the exclusive end.")
        return result


class CSVProvider:
    """Offline provider: one Date/Value CSV per explicitly configured symbol."""
    name = "CSV"

    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def history(self, asset: Asset, end: str) -> pd.Series:
        series = pd.read_csv(self.directory / f"{asset.symbol}.csv", index_col="Date", parse_dates=True)["Value"]
        series = series.loc[series.index < pd.Timestamp(end)].rename(asset.name)
        validate_history(series, asset.name)
        return series


@dataclass
class MarketData:
    native: dict[str, pd.Series]
    normalized: dict[str, pd.Series]
    fx: pd.Series | None
    common: pd.DataFrame
    provenance: pd.DataFrame
    fx_sample: pd.DataFrame


def prepare_common_prices(history: pd.DataFrame) -> pd.DataFrame:
    if not history.index.is_unique or not history.index.is_monotonic_increasing:
        raise ValueError("History must have sorted unique dates.")
    for name in history:
        validate_history(history[name], name)
    start = max(history[name].first_valid_index() for name in history)
    end = min(history[name].last_valid_index() for name in history)
    common = history.loc[start:end].dropna(how="any")
    validate_prices(common)
    return common


def load_market_data(config: Config, provider: Provider | None = None) -> MarketData:
    if provider is None:
        if config.provider == "yahoo":
            provider = YahooProvider(config.cache_dir)
        elif config.provider == "csv":
            provider = CSVProvider(config.cache_dir)
        else:
            raise ValueError("Pass a provider instance for this provider configuration.")
    native = {a.name: provider.history(a, config.end) for a in config.assets}
    for name, series in native.items():
        validate_history(series, name)
        if (series.index >= pd.Timestamp(config.end)).any():
            raise ValueError(f"{name}: history extends beyond the exclusive configured end date.")
    fx = None
    if any(a.currency == "USD" for a in config.assets):
        fx_asset = Asset("EURUSD", config.fx_symbol, "USD per EUR FX quote", "USD", "Price Return", "None")
        fx = provider.history(fx_asset, config.end)
        validate_history(fx, "EURUSD")
        if (fx.index >= pd.Timestamp(config.end)).any():
            raise ValueError("FX history extends beyond the exclusive configured end date.")
    normalized = {a.name: to_eur(native[a.name], a.currency, fx) for a in config.assets}
    for asset in config.assets:
        if asset.usable_start is not None:
            normalized[asset.name] = normalized[asset.name].loc[asset.usable_start:]
    common = prepare_common_prices(pd.DataFrame(normalized).sort_index())
    rows = []
    for asset in config.assets:
        raw = native[asset.name]
        eur = normalized[asset.name]
        rows.append({"Asset": asset.name, "Provider": provider.name, "Symbol": asset.symbol,
                     "Instrument / benchmark": asset.instrument, "Return type": asset.return_type,
                     "Native currency": asset.currency, "Converted to": "EUR",
                     "FX series used": config.fx_symbol if asset.currency == "USD" else "None",
                     "Raw start date": raw.first_valid_index(), "Raw end date": raw.last_valid_index(),
                     "Raw observations": raw.count(), "Raw missing observations": int(raw.isna().sum()),
                     "FX missing on observed sessions": int((raw.notna() & to_eur(raw, asset.currency, fx).isna()).sum()),
                     "Configured usable start": asset.usable_start,
                     "Pre-usable source observations excluded": int(raw.loc[raw.index < pd.Timestamp(asset.usable_start)].count()) if asset.usable_start else 0,
                     "EUR observations": eur.count(), "Final common start": common.index[0],
                     "Final common end": common.index[-1], "Final common observations": len(common),
                     "Distributions": asset.distributions, "Limitation": asset.limitation,
                     "Reference": asset.reference})
    sample = pd.DataFrame()
    usd_asset = next((a for a in config.assets if a.currency == "USD"), None)
    if usd_asset:
        dates = common.index[:5]
        sample = pd.DataFrame({"USD value": native[usd_asset.name].reindex(dates),
                              "EURUSD": fx.reindex(dates), "Computed EUR value": common[usd_asset.name].loc[dates]})
        sample.index.name = "Date"
        np.testing.assert_allclose(sample["Computed EUR value"], sample["USD value"] / sample["EURUSD"],
                                   rtol=1e-12, atol=1e-12)
    return MarketData(native, normalized, fx, common, pd.DataFrame(rows).set_index("Asset"), sample)
