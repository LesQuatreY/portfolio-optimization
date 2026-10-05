"""Auditable ticker metadata; never infer financial characteristics from a name."""
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType


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


# Register new symbols here with verified listing currency and return treatment.
ASSET_CATALOGUE: Mapping[str, Asset] = MappingProxyType({
    asset.symbol: asset for asset in (
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
        Asset("CAC 40", "PX1GR.PA", "CAC 40 Gross Return Index", "EUR", "Gross Return",
              "Gross dividends reinvested in index levels; no additional dividend adjustment",
              "Yahoo daily history has missing observations; inspect raw valid end and missing counts before interpreting coverage.",
              reference="https://live.euronext.com/en/product/indices/QS0011131834-XPAR"),
        Asset("Gold", "GC=F", "Yahoo continuous COMEX gold futures quotation", "USD", "Price Return",
              "No dividends; quoted futures price changes only",
              "Not spot gold or an investable futures total-return index: roll, collateral yield and contract stitching are unmodeled."),
        Asset("MSCI World", "IWDA.AS",
              "iShares Core MSCI World UCITS ETF USD (Acc); Euronext Amsterdam listing",
              "EUR", "Adjusted price",
              "Accumulating ETF; income reinvested within the fund; Yahoo adjusted close",
              "ETF fees and tracking differences apply; EUR listing currency does not imply currency hedging.",
              "https://www.ishares.com/uk/individual/en/products/251882/ishares-core-msci-world-ucits-etf-usd-acc"),
    )
})


def resolve_assets(universe: Mapping[str, str], *,
                   catalogue: Mapping[str, Asset] | None = None) -> tuple[Asset, ...]:
    """Resolve symbols in input order, retaining the user's display names."""
    registry = ASSET_CATALOGUE if catalogue is None else catalogue
    resolved = []
    for name, symbol in universe.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Assets must map nonempty display names to symbol strings.")
        if symbol not in registry:
            raise ValueError(f"Unknown asset symbol '{symbol}'. "
                             "Register its metadata in src/portfolio_lab/assets.py.")
        metadata = registry[symbol]
        if metadata.symbol != symbol:
            raise ValueError(f"Catalogue symbol mismatch for '{symbol}'.")
        resolved.append(replace(metadata, name=name))
    return tuple(resolved)
