"""Download the bounded external reference series used by the V2.2 data admission.

Every request carries an explicit end date on or before 2023-12-29 enforced by the provider.
Each response is scanned for later dates IN MEMORY, before anything is written or parsed;
a response reaching past the cutoff is discarded. Files land in data/v2_1/raw/ (ignored by
Git) with a manifest of URL, retrieval time, size and SHA-256. Existing files are kept unless
--refresh is given. No Research file is read or written.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

import pandas as pd

from portfolio_lab.v2.admission import scan_dates
from portfolio_lab.v2.guard import HARD_CUTOFF

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/v2_1/raw"
MSCI = ("https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph?currency_symbol={c}"
        "&index_variant=NETR&start_date=20140901&end_date=20231229&data_frequency=DAILY&index_codes={i}")
BITSTAMP = "https://www.bitstamp.net/api/v2/ohlc/{p}/?step=86400&limit=1000&start={s}&end={e}"
# 1000-candle pages; the last page ends with the candle opening 2023-12-29 00:00 UTC.
PAGES = ((1409529600, 1495843200), (1495929600, 1582243200), (1582329600, 1668643200),
         (1668729600, 1703808000))
COINBASE = ("https://api.exchange.coinbase.com/products/{p}/candles?granularity=86400"
            "&start={s}T00:00:00Z&end={e}T00:00:00Z")
# 300-candle pages (Coinbase maximum); the last page ends with the candle opening 2023-12-29.
_edges = list(pd.date_range("2014-09-01", "2023-12-29", freq="299D")) + [pd.Timestamp("2023-12-29")]
COINBASE_PAGES = [(a.strftime("%Y-%m-%d"), (b - pd.Timedelta(days=1) if b != _edges[-1] else b).strftime("%Y-%m-%d"))
                  for a, b in zip(_edges[:-1], _edges[1:])]
BITFINEX = ("https://api-pub.bitfinex.com/v2/candles/trade:1D:tBTCUSD/hist?start=1409529600000"
            "&end=1703808000000&limit=10000&sort=1")
SOURCES = {
    "ecb/EXR_D_USD_EUR_SP00_A.csv": (
        "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2014-09-01"
        "&endPeriod=2023-12-29&format=csvdata",
        "ECB reference rate (official, 14:15 CET concertation). Reuse permitted with source attribution."),
    "msci/990100_NETR_USD.json": (MSCI.format(c="USD", i="990100"),
                                  "MSCI World Net Return USD, public end-of-day levels. MSCI terms: local research use only, no redistribution."),
    "msci/990100_NETR_EUR.json": (MSCI.format(c="EUR", i="990100"),
                                  "MSCI World Net Return EUR (WM/Refinitiv 16:00 London FX). Local research use only."),
    "msci/891800_NETR_USD.json": (MSCI.format(c="USD", i="891800"),
                                  "MSCI Emerging Markets Net Return USD. Local research use only."),
    **{f"bitstamp/{pair}_{s}.json": (BITSTAMP.format(p=pair, s=s, e=e),
                                     "Bitstamp public OHLC API, UTC-day candles. Local research use only.")
       for pair in ("btceur", "btcusd") for s, e in PAGES},
    # V2.2 amendment A3: independent venues, fetched only after the A3 tolerances were fixed in code.
    **{f"coinbase/{p}_{s}.json": (COINBASE.format(p=p, s=s, e=e),
                                  "Coinbase Exchange public candles, UTC days. Local research use only.")
       for p in ("BTC-EUR", "BTC-USD") for s, e in COINBASE_PAGES},
    "bitfinex/tBTCUSD_1D.json": (BITFINEX, "Bitfinex public candles (ms timestamps, UTC days). Local research use only."),
    # V2.2 amendment A3b: fetched only after the A3b consensus criteria were frozen in code.
    "bitfinex/tBTCEUR_1D.json": (BITFINEX.replace("tBTCUSD", "tBTCEUR").replace("start=1409529600000", "start=1509494400000"),
                                 "Bitfinex public candles BTC/EUR (pair launched 22/11/2017). Local research use only."),
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Portfolio Lab research)"})
    with urllib.request.urlopen(request, timeout=90) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        return response.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    manifest_path = RAW / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    for name, (url, usage) in SOURCES.items():
        target = RAW / name
        if (target.exists() or manifest.get(name, {}).get("empty")) and not args.refresh and name in manifest:
            print("kept", name)
            continue
        body = fetch(url)
        first, last = scan_dates(body.decode("utf-8", errors="replace"))
        if body.strip() == b"[]":  # page before the product listing: nothing to keep
            manifest[name] = {"url": url, "usage": usage, "empty": True,
                              "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            print("empty", name)
            continue
        if last is None or last > HARD_CUTOFF:
            raise SystemExit(f"REJECTED {name}: latest date {last}; nothing written, values not parsed")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        manifest[name] = {"url": url, "usage": usage, "bytes": len(body),
                          "sha256": hashlib.sha256(body).hexdigest(),
                          "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "requested_end": "2023-12-29", "scanned_first_date": str(first.date()),
                          "scanned_last_date": str(last.date())}
        print("fetched", name, len(body), "bytes, dates", first.date(), "->", last.date())
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
