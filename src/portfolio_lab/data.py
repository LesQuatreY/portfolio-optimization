"""Provider boundary, auditable snapshots and observed-date normalization."""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import hashlib
import json
import re
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


def _snapshot_paths(cache_dir: Path, params: dict) -> tuple[Path, Path]:
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:20]
    path = cache_dir / f"{key}.csv"
    return path, path.with_suffix(".json")


def _read_snapshot(path: Path, manifest: Path, params: dict, asset: Asset) -> pd.Series:
    meta = json.loads(manifest.read_text(encoding="utf-8"))
    if meta["parameters"] != params or meta["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError(f"Snapshot integrity check failed for {asset.name}.")
    # Round-trip parsing reproduces the %.17g-written floats bit for bit.
    frame = pd.read_csv(path, index_col=0, parse_dates=True, float_precision="round_trip")
    return frame["Value"].astype(float).rename(asset.name)


def _write_snapshot(path: Path, manifest: Path, result: pd.Series, source: pd.DataFrame,
                    provider: str, params: dict, vendor_currency: str | None) -> None:
    result.rename("Value").to_csv(path, float_format="%.17g")
    source.to_csv(path.with_suffix(".source.csv"), float_format="%.17g")
    manifest.write_text(json.dumps({"provider": provider, "parameters": params,
        "downloaded_at_utc": pd.Timestamp.now(tz="UTC").isoformat(), "vendor_currency": vendor_currency,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2), encoding="utf-8")


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
        path, manifest = _snapshot_paths(self.cache_dir, params)
        if path.exists() and manifest.exists() and not self.refresh:
            result = _read_snapshot(path, manifest, params, asset)
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
            _write_snapshot(path, manifest, result, frame, self.name, params, currency)
        validate_history(result, asset.name)
        if (result.index >= pd.Timestamp(end)).any():
            raise ValueError(f"{asset.name}: provider returned dates at or beyond the exclusive end.")
        return result


# Canonical catalogue symbol for an official MSCI series: MSCI:<index code>:<variant>.
MSCI_SYMBOL = re.compile(r"MSCI:(?P<code>\d{6}):(?P<variant>NETR|GRTR|STRD)")
# msci-data variant -> this project's return classification; a mismatch is a catalogue error.
MSCI_RETURN_TYPES = {"NETR": "Net Total Return", "GRTR": "Gross Return", "STRD": "Price Return"}
# Earliest date accepted by the MSCI API (World NETR history itself starts 2000-12-29).
MSCI_API_FLOOR = "2000-01-01"


def parse_msci_symbol(asset: Asset) -> tuple[str, str]:
    match = MSCI_SYMBOL.fullmatch(asset.symbol)
    if match is None:
        raise ValueError(f"{asset.name}: MSCI symbol '{asset.symbol}' must look like 'MSCI:990100:NETR'.")
    code, variant = match["code"], match["variant"]
    if asset.return_type != MSCI_RETURN_TYPES[variant]:
        raise ValueError(f"{asset.name}: MSCI variant {variant} is '{MSCI_RETURN_TYPES[variant]}', "
                         f"but the catalogue says '{asset.return_type}'.")
    return code, variant


def normalize_msci_levels(frame: pd.DataFrame | None, asset: Asset, end: str) -> pd.Series:
    """msci-data DATE/LEVEL rows -> validated native-currency index levels before the exclusive end.

    NETR/GRTR levels already embed reinvested dividends: pct_change() is the total return,
    so no adjustment, dividend addition or FX conversion is applied here.
    """
    code, variant = parse_msci_symbol(asset)
    label = f"{asset.name} (MSCI {code} {variant})"
    if frame is None or frame.empty:
        raise RuntimeError(f"No MSCI history for {label}; no substitute was selected.")
    missing = {"DATE", "LEVEL"} - set(frame.columns)
    if missing:
        raise ValueError(f"{label}: MSCI response lacks columns {sorted(missing)}.")
    for column, expected in (("INDEX_CODE", code), ("VARIANT", variant), ("CURRENCY", asset.currency)):
        if column in frame and set(frame[column].astype(str)) != {expected}:
            raise ValueError(f"{label}: MSCI {column} {sorted(set(frame[column].astype(str)))} "
                             f"differs from configured {expected}.")
    dates = pd.to_datetime(frame["DATE"], format="%Y-%m-%d", errors="coerce")
    levels = pd.to_numeric(frame["LEVEL"], errors="coerce")
    if dates.isna().any() or levels.isna().any() or not np.isfinite(levels.to_numpy(float)).all():
        raise ValueError(f"{label}: MSCI response contains unparseable DATE or non-numeric LEVEL values.")
    series = pd.Series(levels.to_numpy(float), index=pd.DatetimeIndex(dates, name="Date"), name=asset.name)
    duplicated = series.index.duplicated(keep=False)
    if duplicated.any():
        if (series[duplicated].groupby(level=0).nunique() > 1).any():
            raise ValueError(f"{label}: MSCI response has conflicting levels for the same date.")
        series = series[~series.index.duplicated()]
    series = series.sort_index()
    series = series.loc[series.index < pd.Timestamp(end)]
    if series.empty:
        raise RuntimeError(f"No MSCI history for {label} before {end}; no substitute was selected.")
    validate_history(series, asset.name)
    return series


class MSCIProvider:
    """Single msci-data boundary for official MSCI index levels, with auditable snapshots.

    Returns the index's native currency (USD for MSCI World); EUR conversion stays in
    load_market_data like any USD asset, so the exposure remains unhedged.
    """
    name = "MSCI"

    def __init__(self, cache_dir: Path, *, refresh: bool = False,
                 get_levels: Callable[..., pd.DataFrame] | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self._get_levels = get_levels

    def source_detail(self, asset: Asset) -> str:
        code, variant = parse_msci_symbol(asset)
        return (f"MSCI index code {code}; variant {variant} ({MSCI_RETURN_TYPES[variant]}); "
                f"native {asset.currency} index levels, not an ETF adjusted price")

    def history(self, asset: Asset, end: str) -> pd.Series:
        code, variant = parse_msci_symbol(asset)
        # msci-data's to_date is inclusive; the study end is exclusive.
        last = (pd.Timestamp(end) - pd.Timedelta(days=1)).date().isoformat()
        params = {"index_code": code, "variant": variant, "from_date": MSCI_API_FLOOR, "to_date": last}
        path, manifest = _snapshot_paths(self.cache_dir, params)
        if path.exists() and manifest.exists() and not self.refresh:
            result = _read_snapshot(path, manifest, params, asset)
        else:
            get_levels = self._get_levels
            if get_levels is None:
                from mscidata import msci
                get_levels = msci.get_levels
            frame = get_levels(code, MSCI_API_FLOOR, last, variant=variant)
            result = normalize_msci_levels(frame, asset, end)
            _write_snapshot(path, manifest, result, frame, self.name, params, asset.currency)
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


FRED_SERIES = re.compile(r"[A-Z0-9]+")
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def normalize_fred_series(frame: pd.DataFrame | None, asset: Asset, end: str) -> pd.Series:
    """fredgraph observation_date/<series id> rows -> observed values before the exclusive end.

    Values are kept exactly as published (DEXUSEU stays USD per EUR; never inverted).
    Blank cells are FRED's non-publication days (holidays) and are dropped, like any
    unobserved session; any other non-numeric value is rejected.
    """
    label = f"{asset.name} (FRED {asset.symbol})"
    if frame is None or frame.empty:
        raise RuntimeError(f"No FRED history for {label}; no substitute was selected.")
    missing = {"observation_date", asset.symbol} - set(frame.columns)
    if missing:
        raise ValueError(f"{label}: FRED response lacks columns {sorted(missing)}.")
    raw = frame[asset.symbol].astype("string").str.strip()
    unpublished = raw.isna() | raw.isin(["", "."])
    dates = pd.to_datetime(frame["observation_date"], format="%Y-%m-%d", errors="coerce")
    values = pd.to_numeric(raw.where(~unpublished), errors="coerce").astype(float)
    if dates.isna().any() or (values.isna() & ~unpublished).any():
        raise ValueError(f"{label}: FRED response contains unparseable dates or non-numeric values.")
    series = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates, name="Date"), name=asset.name)
    series = series[~unpublished.to_numpy()]
    duplicated = series.index.duplicated(keep=False)
    if duplicated.any():
        if (series[duplicated].groupby(level=0).nunique() > 1).any():
            raise ValueError(f"{label}: FRED response has conflicting values for the same date.")
        series = series[~series.index.duplicated()]
    series = series.sort_index()
    series = series.loc[series.index < pd.Timestamp(end)]
    if series.empty:
        raise RuntimeError(f"No FRED history for {label} before {end}; no substitute was selected.")
    validate_history(series, asset.name)
    return series


class FREDProvider:
    """Single FRED boundary: public fredgraph CSV (no API key), with auditable snapshots."""
    name = "FRED"

    def __init__(self, cache_dir: Path, *, refresh: bool = False,
                 fetch_csv: Callable[[str, str], str] | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self._fetch_csv = fetch_csv or self._download

    @staticmethod
    def _download(series_id: str, last: str) -> str:
        from urllib.parse import urlencode
        from urllib.request import urlopen
        with urlopen(f"{FRED_CSV_URL}?{urlencode({'id': series_id, 'coed': last})}", timeout=60) as response:
            return response.read().decode("utf-8")

    def history(self, asset: Asset, end: str) -> pd.Series:
        if FRED_SERIES.fullmatch(asset.symbol) is None:
            raise ValueError(f"{asset.name}: invalid FRED series id '{asset.symbol}'.")
        # FRED's coed is inclusive; the study end is exclusive.
        last = (pd.Timestamp(end) - pd.Timedelta(days=1)).date().isoformat()
        params = {"series_id": asset.symbol, "url": FRED_CSV_URL, "to_date": last}
        path, manifest = _snapshot_paths(self.cache_dir, params)
        if path.exists() and manifest.exists() and not self.refresh:
            result = _read_snapshot(path, manifest, params, asset)
        else:
            from io import StringIO
            frame = pd.read_csv(StringIO(self._fetch_csv(asset.symbol, last)), dtype=str, keep_default_na=False)
            result = normalize_fred_series(frame, asset, end)
            _write_snapshot(path, manifest, result, frame, self.name, params, asset.currency)
        validate_history(result, asset.name)
        if (result.index >= pd.Timestamp(end)).any():
            raise ValueError(f"{asset.name}: provider returned dates at or beyond the exclusive end.")
        return result


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


def provider_router(config: Config, provider: Provider | Mapping[str, Provider] | None = None
                    ) -> Callable[[Asset], Provider]:
    """Asset -> provider. A single injected provider serves every series (tests, offline);
    a mapping is keyed by Asset.provider; otherwise each catalogued Asset.provider is built lazily."""
    if provider is not None and not isinstance(provider, Mapping):
        return lambda asset: provider
    if provider is None and config.provider == "csv":
        csv = CSVProvider(config.cache_dir)
        return lambda asset: csv
    if provider is None and config.provider != "yahoo":
        raise ValueError("Pass a provider instance for this provider configuration.")
    factories = {"yahoo": lambda: YahooProvider(config.cache_dir),
                 "msci": lambda: MSCIProvider(config.cache_dir / "msci"),
                 "fred": lambda: FREDProvider(config.cache_dir / "fred")}
    instances = dict(provider or {})

    def route(asset: Asset) -> Provider:
        if asset.provider not in instances:
            if provider is not None or asset.provider not in factories:
                raise ValueError(f"{asset.name}: no data provider configured for '{asset.provider}'.")
            instances[asset.provider] = factories[asset.provider]()
        return instances[asset.provider]
    return route


def load_market_data(config: Config, provider: Provider | Mapping[str, Provider] | None = None) -> MarketData:
    route = provider_router(config, provider)
    native = {a.name: route(a).history(a, config.end) for a in config.assets}
    for name, series in native.items():
        validate_history(series, name)
        if (series.index >= pd.Timestamp(config.end)).any():
            raise ValueError(f"{name}: history extends beyond the exclusive configured end date.")
    fx = None
    fx_source = None
    if any(a.currency == "USD" for a in config.assets):
        # Quote convention is USD per EUR (1 EUR = X USD); to_eur divides USD values by it.
        fx_asset = Asset("EURUSD", config.fx_symbol, "USD per EUR FX quote", "USD", "Price Return", "None",
                         provider=config.fx_provider)
        fx_source = route(fx_asset)
        fx = fx_source.history(fx_asset, config.end)
        validate_history(fx, "EURUSD")
        if (fx.index >= pd.Timestamp(config.end)).any():
            raise ValueError("FX history extends beyond the exclusive configured end date.")
    normalized = {a.name: to_eur(native[a.name], a.currency, fx) for a in config.assets}
    common = prepare_common_prices(pd.DataFrame(normalized).sort_index())
    rows = []
    for asset in config.assets:
        raw = native[asset.name]
        eur = normalized[asset.name]
        source = route(asset)
        detail = getattr(source, "source_detail", None)
        usd = asset.currency == "USD"
        rows.append({"Asset": asset.name, "Provider": source.name, "Symbol": asset.symbol,
                     "Source detail": detail(asset) if detail else "",
                     "Instrument / benchmark": asset.instrument, "Return type": asset.return_type,
                     "Native currency": asset.currency, "Converted to": "EUR",
                     "FX provider": fx_source.name if usd else "None",
                     "FX series used": config.fx_symbol if usd else "None",
                     "FX convention": "USD per EUR" if usd else "None",
                     "FX start date": fx.first_valid_index() if usd else pd.NaT,
                     "Raw start date": raw.first_valid_index(), "Raw end date": raw.last_valid_index(),
                     "Raw observations": raw.count(), "Raw missing observations": int(raw.isna().sum()),
                     "FX missing on observed sessions": int((raw.notna() & to_eur(raw, asset.currency, fx).isna()).sum()),
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


def study_coverage(data: MarketData, config: Config) -> dict:
    """Separate raw-asset limits, FX limits and the first jointly observed date."""
    raw_starts = {name: series.first_valid_index() for name, series in data.native.items()}
    raw_ends = {name: series.last_valid_index() for name, series in data.native.items()}
    eur_starts = {name: series.first_valid_index() for name, series in data.normalized.items()}
    raw_limit = max(raw_starts.values())
    eligible_start = max(eur_starts.values())
    limiting_assets = [name for name, start in eur_starts.items() if start == eligible_start]
    fx_start = data.fx.first_valid_index() if data.fx is not None else None
    fx_limits = fx_start == eligible_start and any(
        asset.currency == "USD" and raw_starts[asset.name] < fx_start for asset in config.assets
    )
    return {
        "common_start": str(data.common.index[0].date()),
        "common_end": str(data.common.index[-1].date()),
        "common_observations": len(data.common),
        "latest_raw_asset_start": str(raw_limit.date()),
        "raw_start_limiting_assets": [name for name, start in raw_starts.items() if start == raw_limit],
        "earliest_raw_asset_end": str(min(raw_ends.values()).date()),
        "raw_end_limiting_assets": [name for name, end in raw_ends.items() if end == min(raw_ends.values())],
        "latest_eur_asset_start": str(eligible_start.date()),
        "eur_start_limiting_assets": limiting_assets,
        "start_limiting_series": [config.fx_symbol] if fx_limits else limiting_assets,
        "fx_start": str(fx_start.date()) if fx_start is not None else None,
        "first_common_date_delayed_by_calendar": bool(data.common.index[0] > eligible_start),
    }
