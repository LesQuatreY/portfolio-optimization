"""Bounded Yahoo Finance daily history through yfinance, without current-quote leakage.

Yahoo's chart endpoint returns, with any bounded history, a ``meta`` block holding CURRENT
quotation fields (regularMarketPrice/Time, 52-week range, previous close, trading periods).
This adapter, used only offline-in-spirit by the data-admission scripts:

* fixes the exchange timezone in advance, so yfinance never issues its ``range=1d`` lookup;
* allows only chart requests with explicit ``period1``/``period2`` ending no later than the day
  after the cutoff (exclusive), plus Yahoo's cookie/crumb handshake; anything else is refused;
* replaces each chart response, before yfinance parses it, by a copy whose ``meta`` keeps only
  identity fields (currency, symbol, exchange, instrument type, timezone, granularity);
* refuses the response if any remaining timestamp or date is later than the cutoff.

The unfiltered bytes transit through memory once; they are never parsed, logged or stored.
Every URL (never a body) is recorded in the returned audit.
"""
from __future__ import annotations

from contextlib import contextmanager
import json

import pandas as pd

from .admission import assert_text_before_cutoff
from .guard import HARD_CUTOFF, CutoffViolation

META_KEEP = {"currency", "symbol", "exchangeName", "fullExchangeName", "instrumentType", "timezone",
             "exchangeTimezoneName", "gmtoffset", "dataGranularity", "priceHint", "shortName", "longName"}
HANDSHAKE_HOSTS = ("fc.yahoo.com", "/v1/test/getcrumb", "guce.yahoo.com", "consent.yahoo.com")


class _Filtered:
    """Minimal stand-in for the HTTP response, exposing only the filtered chart JSON."""

    def __init__(self, response, payload):
        self.status_code, self.url = response.status_code, response.url
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return json.loads(self.text)


def _filter_chart(payload: dict, audit: dict) -> dict:
    result = payload.get("chart", {}).get("result") or []
    for item in result:
        dropped = sorted(set(item.get("meta", {})) - META_KEEP)
        item["meta"] = {k: v for k, v in item.get("meta", {}).items() if k in META_KEEP}
        audit["meta_fields_dropped"] = sorted(set(audit.get("meta_fields_dropped", [])) | set(dropped))
        stamps = item.get("timestamp") or []
        for events in (item.get("events") or {}).values():
            stamps += [int(k) for k in events]
        if stamps and pd.Timestamp(max(stamps), unit="s") > HARD_CUTOFF + pd.Timedelta(days=1):
            raise CutoffViolation("Yahoo : horodatage postérieur à la coupure ; réponse rejetée.")
    assert_text_before_cutoff(json.dumps(payload), "Yahoo (réponse filtrée)")
    return payload


@contextmanager
def _bounded_transport(end_exclusive: pd.Timestamp, audit: dict):
    from yfinance.data import YfData
    original = YfData._make_request
    limit = int(end_exclusive.timestamp())

    def guarded(self, url, request_method, body=None, params=None, timeout=30):
        params = dict(params or {})
        if "/v8/finance/chart/" in url:
            if "range" in params or "period2" not in params or int(params["period2"]) > limit:
                raise CutoffViolation(f"Requête Yahoo non bornée refusée ({sorted(params)}).")
            audit["requests"].append({"url": url, "period1": int(params["period1"]), "period2": int(params["period2"])})
            response = original(self, url, request_method, body=body, params=params, timeout=timeout)
            audit["http_status"].append(response.status_code)
            if response.status_code != 200:
                return response
            return _Filtered(response, _filter_chart(response.json(), audit))
        if not any(h in url for h in HANDSHAKE_HOSTS):
            raise CutoffViolation(f"Point d'accès Yahoo non autorisé : {url}")
        audit["handshake"].append(url)
        return original(self, url, request_method, body=body, params=params, timeout=timeout)

    YfData._make_request = guarded
    try:
        yield
    finally:
        YfData._make_request = original


def fetch_daily(ticker: str, timezone: str, start: str, end_inclusive: str = str(HARD_CUTOFF.date())):
    """Daily OHLC + actions, unadjusted, for [start, end_inclusive]. Returns (frame, audit)."""
    import yfinance as yf

    end_inclusive = pd.Timestamp(end_inclusive)
    if end_inclusive > HARD_CUTOFF:
        raise CutoffViolation("Fin demandée au-delà du 29/12/2023.")
    end_exclusive = pd.Timestamp(end_inclusive + pd.Timedelta(days=1), tz=timezone)
    audit = {"ticker": ticker, "timezone_fixed": timezone, "requests": [], "handshake": [], "http_status": [],
             "yfinance": yf.__version__}
    t = yf.Ticker(ticker)
    t._tz = timezone  # no `range=1d` timezone lookup (it would return the latest quote)
    with _bounded_transport(end_exclusive, audit):
        frame = t.history(start=start, end=str(end_exclusive.date()), interval="1d", auto_adjust=False,
                          actions=True, repair=False, raise_errors=True)
    if frame.empty:
        raise ValueError(f"Yahoo : historique vide pour {ticker}.")
    index = frame.index.tz_convert(timezone).tz_localize(None)
    if not (index == index.normalize()).all():
        raise ValueError("Yahoo : horodatages journaliers non alignés sur minuit local.")
    frame.index = pd.DatetimeIndex(index.normalize(), name="Date")
    if frame.index.max() > HARD_CUTOFF:
        raise CutoffViolation("Yahoo : observation postérieure à la coupure.")
    audit["rows"] = len(frame)
    return frame, audit
