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
    # Explicit data source key, routed by data.load_market_data; never inferred from the symbol.
    provider: str = "yahoo"


# Register new symbols here with verified listing currency and return treatment.
ASSET_CATALOGUE: Mapping[str, Asset] = MappingProxyType({
    asset.symbol: asset
    for asset in (
        Asset(
            "Apple",
            "AAPL",
            "Primary US equity",
            "USD",
            "Adjusted price",
            "Yahoo split/dividend adjustment; reinvestment proxy before investor tax",
            "Adjusted prices are a vendor proxy, not an independently audited TR index.",
        ),

        Asset(
            "Nasdaq 100",
            "QQQ",
            "Invesco QQQ ETF; Nasdaq-100 exposure proxy",
            "USD",
            "Adjusted price",
            "Yahoo dividend/split adjustments; distributions assumed reinvested",
            (
                "Exact Nasdaq-100 TR unavailable from tested Yahoo ^XNDX. "
                "QQQ is an ETF proxy with fund fees/tracking differences, "
                "not the gross TR benchmark."
            ),
            "https://www.invesco.com/qqq-etf/en/home.html",
        ),

        Asset(
            "S&P 500",
            "^SP500TR",
            "S&P 500 Total Return index",
            "USD",
            "Gross Return",
            "Gross dividends reinvested by index methodology",
            reference="https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
        ),

        Asset(
            "Dow Jones",
            "DIA",
            "State Street SPDR Dow Jones Industrial Average ETF proxy",
            "USD",
            "Adjusted price",
            "Yahoo dividend/split adjustments; distributions assumed reinvested",
            (
                "Exact Dow Jones TR unavailable from tested Yahoo ^DJITR. "
                "DIA is an ETF proxy with fund fees/tracking differences, "
                "not the gross TR benchmark."
            ),
            (
                "https://www.ssga.com/us/en/individual/etfs/"
                "state-street-spdr-dow-jones-industrial-average-etf-trust-dia"
            ),
        ),

        Asset(
            "CAC 40",
            "PX1GR.PA",
            "CAC 40 Gross Return Index",
            "EUR",
            "Gross Return",
            "Gross dividends reinvested in index levels; no additional dividend adjustment",
            (
                "Yahoo daily history has missing observations; inspect raw valid end "
                "and missing counts before interpreting coverage."
            ),
            reference="https://live.euronext.com/en/product/indices/QS0011131834-XPAR",
        ),

        Asset(
            "Gold",
            "GC=F",
            "Yahoo continuous COMEX gold futures quotation",
            "USD",
            "Price Return",
            "No dividends; quoted futures price changes only",
            (
                "Not spot gold or an investable futures total-return index: "
                "roll, collateral yield and contract stitching are unmodeled."
            ),
        ),

        Asset(
            "MSCI World",
            "MSCI:990100:NETR",
            "MSCI World Index (index code 990100), Net Total Return variant (NETR)",
            "USD",
            "Net Total Return",
            "Net dividends reinvested according to MSCI index methodology",
            (
                "Official index rather than ETF prices; excludes ETF fees and "
                "tracking difference. NETR reflects MSCI withholding-tax "
                "assumptions on dividends. USD levels, unhedged; converted to "
                "EUR by the standard FX pipeline."
            ),
            reference="https://www.msci.com/indexes/index/990100/msci-world-index",
            provider="msci",
        ),

        Asset(
            "iShares Core MSCI World",
            "IWDA.AS",
            "iShares Core MSCI World UCITS ETF USD (Acc); Euronext Amsterdam listing",
            "EUR",
            "Adjusted price",
            "Accumulating ETF; income reinvested within the fund; Yahoo adjusted close",
            (
                "ETF fees and tracking differences apply; EUR listing currency does "
                "not imply currency hedging. Short Yahoo history; prefer "
                "MSCI:990100:NETR for the MSCI World benchmark."
            ),
            (
                "https://www.ishares.com/uk/individual/en/products/251882/"
                "ishares-core-msci-world-ucits-etf-usd-acc"
            ),
        ),

        Asset(
            "Euro Govt Bond 1-3y",
            "IBGS.AS",
            "iShares € Govt Bond 1-3yr UCITS ETF; Euronext Amsterdam listing",
            "EUR",
            "Adjusted price",
            "Yahoo dividend/split adjustments; distributions assumed reinvested",
            "ETF fees and tracking differences apply.",
            reference="https://finance.yahoo.com/quote/IBGS.AS/",
        ),

        Asset(
            "Coca-Cola",
            "KO",
            "The Coca-Cola Company; US large-cap consumer equity",
            "USD",
            "Adjusted price",
            "Yahoo split/dividend adjustment; reinvestment proxy before investor tax",
            "Adjusted prices are a vendor proxy, not an independently audited TR index.",
            reference="https://finance.yahoo.com/quote/KO/",
        ),

        Asset(
            "Euro Govt Bond 7-10y",
            "IBGM.AS",
            "iShares € Govt Bond 7-10yr UCITS ETF; Euronext Amsterdam listing",
            "EUR",
            "Adjusted price",
            "Yahoo dividend/split adjustments; distributions assumed reinvested",
            (
                "ETF fees and tracking differences apply. "
                "Higher duration makes it more volatile than the 1-3yr equivalent "
                "(IBGS.AS)."
            ),
            reference="https://finance.yahoo.com/quote/IBGM.AS/",
        ),

        Asset(
            "Global Real Estate",
            "IWDP.AS",
            (
                "iShares Developed Markets Property Yield UCITS ETF; "
                "Euronext Amsterdam listing (Global REITs / Real Estate)"
            ),
            "EUR",
            "Adjusted price",
            "Yahoo dividend/split adjustments; distributions assumed reinvested",
            "ETF fees and tracking differences apply.",
            reference="https://finance.yahoo.com/quote/IWDP.AS/",
        ),

        Asset(
            "Broad Commodities",
            "DBC",
            (
                "Invesco DB Commodity Index Tracking Fund; "
                "US listing (Diversified Commodities futures)"
            ),
            "USD",
            "Adjusted price",
            "Yahoo dividend/split adjustments; distributions assumed reinvested",
            (
                "Tracks a diversified basket of commodity futures. ETF fees apply. "
                "Structured as a commodity pool and may generate a Schedule K-1 "
                "for US tax purposes."
            ),
            reference="https://finance.yahoo.com/quote/DBC/",
        ),

        Asset(
    "US Real Estate",
    "IYR",
    "iShares U.S. Real Estate ETF; US real estate equities and REITs",
    "USD",
    "Adjusted price",
    "Yahoo dividend/split adjustments; distributions assumed reinvested",
    (
        "US real estate exposure rather than global real estate. "
        "ETF fees and tracking differences apply."
    ),
    reference="https://www.ishares.com/us/products/239520/ishares-us-real-estate-etf",
    ),
    Asset(
    "Europe",
    "IEV",
    "iShares Europe ETF; developed European equities",
    "USD",
    "Adjusted price",
    "Yahoo dividend/split adjustments; distributions assumed reinvested",
    (
        "Tracks European developed equities through the S&P Europe 350 Index. "
        "ETF fees and tracking differences apply."
    ),
    reference="https://www.ishares.com/us/products/239736/IEV",
    ),
    )
})


def resolve_assets(
    universe: Mapping[str, str],
    *,
    catalogue: Mapping[str, Asset] | None = None,
) -> tuple[Asset, ...]:
    """Resolve symbols in input order, retaining the user's display names."""

    registry = ASSET_CATALOGUE if catalogue is None else catalogue
    resolved = []

    for name, symbol in universe.items():
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(symbol, str)
            or not symbol.strip()
        ):
            raise ValueError(
                "Assets must map nonempty display names to symbol strings."
            )

        if symbol not in registry:
            raise ValueError(
                f"Unknown asset symbol '{symbol}'. "
                "Register its metadata in src/portfolio_lab/assets.py."
            )

        metadata = registry[symbol]

        if metadata.symbol != symbol:
            raise ValueError(
                f"Catalogue symbol mismatch for '{symbol}'."
            )

        resolved.append(
            replace(metadata, name=name)
        )

    return tuple(resolved)
