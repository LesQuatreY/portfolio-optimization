"""Causal EUR data admission for custom portfolios (V2.2, Phase A).

Snapshot convention ``euronext_close_snapshot_asof_v1``
-------------------------------------------------------
One valuation per Euronext Paris session D, at a snapshot instant just after the Paris closing
auction (17:40 Paris; 14:10 on the 24 and 31 December half-day sessions). Each asset contributes
the latest observation whose *availability instant* is not later than the snapshot:

* Euronext-listed series (CW8, CAC 40 total return): close of D itself; a missing session fails.
* US-listed ETFs (SPY, EEM, GLD): latest NYSE close. 16:00 New York is always after 17:40 Paris,
  so this is normally the close of D-1, whatever the daylight-saving offsets.
* EUR/USD: latest ECB reference rate, considered available at 16:00 Frankfurt on its date; on a
  Paris half-day session the previous fixing is used.
* BTC-EUR: latest UTC-day close, i.e. the D-1 candle, available at 00:00 UTC on D.

This is a causal *valuation snapshot*, not a simultaneous executable basket order: US lines are
valued and traded at the last known close. Nothing is interpolated or shifted silently; every
observation age is reported, and ages beyond explicit bounds fail.

All requested data end on or before ``HARD_CUTOFF``. Downloaded texts are scanned for later dates
before any value is parsed. No fetch happens in this module.
"""
from __future__ import annotations

import io
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from dateutil.easter import easter

from .custom import DEVELOPMENT_START, DataUnavailable
from .guard import HARD_CUTOFF, CutoffViolation

PARIS, NEW_YORK, FRANKFURT = ZoneInfo("Europe/Paris"), ZoneInfo("America/New_York"), ZoneInfo("Europe/Berlin")
CALENDAR_ID = "euronext_paris_sessions_v1"
CLOCK_ID = "euronext_close_snapshot_asof_v1"
RESEARCH_ALIGNMENT = "validated_paris_session_end"
SNAPSHOT_TIME, HALF_DAY_SNAPSHOT_TIME = time(17, 40), time(14, 10)
ECB_PUBLICATION_TIME, NYSE_CLOSE_TIME = time(16, 0), time(16, 0)
# Maximum calendar-day age of an as-of observation at the snapshot; beyond => data gap, failure.
MAX_AGE_DAYS = {"same_session": 0, "nyse": 5, "ecb": 5, "utc_day": 1}
NYSE_SPECIAL_CLOSURES = {date(2018, 12, 5)}  # National Day of Mourning, President G. H. W. Bush
# Vendor anomalies found against the rule calendar. Each is listed, justified and tested; any
# other missing session or extra row still fails. They are never generalized to other dates.
# Weekdays without ANY Paris market data in the independent sources examined (Bourse Direct CAC 40
# NR, Yahoo ^FCHI, CW8): removed from the valuation calendar rather than valued with stale marks.
# No return is lost: it is carried by the next session. (18/10/2026, investigation in §7.)
EURONEXT_NO_DATA_DAYS = {date(2015, 12, 31): "Aucune donnée parisienne : CAC 40 NR (Bourse Direct), CAC 40 "
                                             "(Yahoo ^FCHI) et CW8 absents ; ancienne exception CW8 supprimée"}
VENDOR_EXCEPTIONS = {
    "WORLD": {
        "placeholder": {pd.Timestamp("2019-12-25"): "Ligne fournisseur un jour de fermeture Euronext, "
                                                    "O=H=L=C=clôture du 24/12/2019 ; retirée"},
    },
    "CAC40_BOURSE_DIRECT": {
        # Row dated on a holiday, while the previous session is missing; its return equals the
        # ^FCHI return of 31/12/2014 (checked in validate_cac40): a one-day label error.
        "relabel": {pd.Timestamp("2015-01-01"): pd.Timestamp("2014-12-31")},
        "missing": {pd.Timestamp("2016-07-27"): "Ligne absente chez Bourse Direct (séance ouverte : ^FCHI et CW8 "
                                                "présents) ; clôture du 26/07 reprise comme marque de valorisation"},
    },
}
# Official closing values replacing erroneous vendor prints. Raw files are never modified: each
# correction applies at validation time, only if the raw value still equals ``raw`` (so it can
# never silently hit another file), and is reported. 18/10/2026, docs/V2_2_DATA_ADMISSION.md §7.
OFFICIAL_CORRECTIONS = {
    "FCHI_YAHOO": {
        pd.Timestamp("2016-06-27"): {
            "raw": 4030.30, "value": 3984.72, "kind": "clôture officielle rapportée",
            "source": "Dépêche AFP « La Bourse de Paris finit en recul de 2,97 % à 3 984,72 points » (medias24.com, "
                      "fournie par le propriétaire ; page HTTP 403, non consultée). Corroborée : rendement −2,971 % "
                      "= CAC 40 NR Bourse Direct à 0,01 pb sur le 27/06 et le 28/06 ; la barre Yahoo du jour a un "
                      "plus bas (4 012,20) supérieur à la clôture officielle"},
    },
    "CAC40_BOURSE_DIRECT": {
        pd.Timestamp("2020-10-19"): {
            "raw": 10493.36, "value": 10521.77, "kind": "clôture officielle observée",
            "source": "Euronext, cours de clôture ajustés du 19/10/2020 après annulation des transactions "
                      "postérieures à 17 h 30 (live.euronext.com/media/516/download, SHA-256 e42ebf4f…, ligne "
                      "QS0011131826 PX1NR). Le même fichier donne PX1 4 942,62, identique à Yahoo ^FCHI"},
    },
}
# Pinned development artifacts (paths relative to the Research root; read via ResearchGuard only).
# The first six are those of scripts/audit_custom_data.py; IAU and ^SP500TR are pinned by the
# research_gold and DV2 raw manifests respectively.
PINNED_RESEARCH_SOURCES = {
    "panel": ("research_diversification_v1/outputs/research_panel_eur.parquet",
              "35e80e58c779adb834e910c4fa7d8befd6bcd5c657964cb0d201f17255fe4656"),
    "SP500": ("research_diversification_v1/data/raw/YF_SPY.parquet",
              "141e76910903e25d984c24e9a584c3339680633619e86cbf417048b180a3c0b8"),
    "WORLD": ("research_diversification_v1/data/raw/YF_CW8_PA.parquet",
              "2294f68a0da5a2456baa97fd3609d54aaea1bfaa36bb3329b8b4afe037fc1d74"),
    "EM": ("research_v11_multi_asset_optimization/data/raw/YF_EEM.parquet",
           "612e77ab6e41ff06eca0a8f02e642639343ac115d925bbe429b4d14914226269"),
    "GOLD": ("research_v11_multi_asset_optimization/data/raw/YF_GLD.parquet",
             "b4c2e79826d8da6899ee76b7468c7dc2b551f1d29c6766c5d6a61912b098dcd9"),
    "BTC": ("research_v7_global/data/BTC_EUR.parquet",
            "cfded6f035eabf3e1f62f21cffe686628ed5cb125fe8b8f18f0aac331d4d7f0f"),
    "IAU": ("research_gold/data/IAU_to_2023.parquet",
            "82f08cc9b1b322229f19a7cb718bc635d0d58bc3ed21139baa47289eecd51361"),
    "SP500TR": ("research_diversification_v2/data/raw/YF_SP500TR.parquet",
                "68e53d04e61f8464aece0595bb685e4b65a289ad74352a1ec3636e770a7266bc"),
}
CAC40_TR_ISINS = {"QS0011131826": "CAC 40 Net Return (NR)", "QS0011131834": "CAC 40 Gross Return (GR)"}
CAC40_PRICE_ISIN = "FR0003500008"

# Acceptance tolerances, declared BEFORE comparing any external series (V2.2 protocol).
# Rationale per entry is documented in docs/V2_2_DATA_ADMISSION.md. They are never tuned on results.
TOLERANCES = {
    "FX": {"median_abs_bp": 15.0, "p99_abs_bp": 80.0, "max_abs_bp": 300.0},
    "SP500": {"td_min": -0.0030, "td_max": 0.0, "daily_corr_min": 0.999, "p99_daily_abs_bp": 20.0,
              "exdate_abs_bp": 25.0},
    "EM": {"td_min": -0.0150, "td_max": 0.0025, "monthly_corr_min": 0.95, "year_abs_td_max": 0.03},
    "WORLD": {"td_min": -0.0100, "td_max": 0.0050, "monthly_corr_min": 0.95, "year_abs_td_max": 0.03,
              "migration_abs_bp": 100.0},
    "GOLD": {"diff_min": -0.0040, "diff_max": 0.0010, "daily_corr_min": 0.99, "p99_daily_abs_bp": 50.0,
             "split_day_abs_bp": 100.0},
    "BTC": {"eur_median_abs_bp": 50.0, "eur_p99_abs_bp": 300.0, "usd_median_abs_bp": 100.0,
            "usd_p99_abs_bp": 500.0, "daily_corr_min": 0.95, "extreme_gap_pp": 5.0},
    "CAC40": {"daily_shortfall_bp": 1.0, "gr_yield_gap": (0.01, 0.06), "nr_yield_gap": (0.005, 0.05)},
    # Declared on 18/10/2026 before any ETF observation was obtained (route 2 of the handover).
    "CAC40_ETF": {"ledger_amount_tol_eur": 0.005, "exdate_residual_bp": 100.0, "exdate_mean_residual_bp": 50.0,
                  "daily_gap_bp_max": 300.0, "tr_minus_price": (0.003, 0.05)},
}
CAC40_ETF_ISIN = "FR0007052782"

# Protocol amendments approved by the project owner on 18/10/2026 (docs/V2_2_DATA_ADMISSION.md, §10).
# A1/A2 thresholds were chosen AFTER the original TOLERANCES failed: the original checks stay
# computed and published, non-binding. A3/A4 tolerances were fixed BEFORE fetching or receiving
# the Coinbase/Bitfinex comparison data and any ETF observation. TOLERANCES above stay unchanged.
AMENDMENTS = {
    # A1 — ECB vs WM/R: a gap must be a timing difference absorbed by the next fixing, not a level error.
    "FX_A1": {"median_abs_bp": 15.0, "max_abs_bp": 300.0, "absorption_slope": (0.7, 1.3),
              "absorption_corr_min": 0.3, "lag1_abs_max": 0.2, "endpoint_abs_bp": 10.0, "mean_abs_bp": 3.0},
    # A2 — SPY vs S&P 500 TR: no level drift once the linear fee drift is removed. Daily correlation,
    # p99 and the lag-1 autocorrelation are diagnostics only.
    "SP500_A2": {"td_min": -0.0030, "td_max": 0.0, "exdate_abs_bp": 25.0, "detrended_median_abs_bp": 5.0,
                 "rolling21_abs_bp": 20.0, "run_threshold_bp": 25.0, "max_run_sessions": 3},
    # A3 — Bitstamp composite (USD book / ECB, then native EUR book), declared before fetching
    # Coinbase and Bitfinex. A candle below min_volume_btc is not a price (treated as missing).
    "BTC_A3": {"min_volume_btc": 1.0, "splice_min_daily_volume_btc": 10.0, "max_stale_days": 4,
               "fx_max_age_days": 5, "cross_min_volume_btc": 1.0, "cross_median_abs_bp": 50.0,
               "cross_p99_abs_bp": 300.0, "cross_max_abs_bp": 1500.0, "cross_month_mean_abs_bp": 200.0,
               "cross_cagr_abs": 0.005, "daily_corr_min": 0.95, "splice_window_days": 30,
               "splice_median_abs_bp": 100.0, "splice_jump_bp": 300.0},
    # A3b — exchange-level consensus (approved 18/10/2026). Formulated AFTER the A3 pairwise failures
    # against Coinbase were seen, frozen BEFORE downloading Bitfinex BTC/EUR. One EUR series per
    # exchange and day (native EUR pair when liquid, else its USD pair / ECB): two pairs of the same
    # exchange never count as two witnesses; Bitstamp's own books never corroborate each other.
    # Where three exchanges trade, the primary is compared with the daily median of the three
    # (robust to one outlier venue); where only two trade, with the other exchange directly.
    # The A3 level thresholds are unchanged. The annualized-CAGR gap (unsuitable for short overlaps)
    # is replaced by a duration-aware drift test: |mean gap of the last N obs − first N obs| must not
    # exceed drift_bp_per_year × years + drift_z × SE, SE from the gap's AR(1) effective sample size.
    "BTC_A3B": {"consensus_min_exchanges": 3, "median_abs_bp": 50.0, "p99_abs_bp": 300.0, "max_abs_bp": 1500.0,
                "month_mean_abs_bp": 200.0, "daily_corr_min": 0.95, "drift_bp_per_year": 50.0,
                "drift_window_obs": 20, "drift_z": 3.0, "outlier_month_bp": 200.0},
    # A5 — CAC 40 NR from Yahoo (PX1NR.PA) checked against the user's Bourse Direct export of the same
    # official index (QS0011131826). Frozen BEFORE any Yahoo request and before reading any reference
    # value. Two distributors of one official index may differ only by rounding (2 decimals ≈ 0.02 pb).
    "CAC40_A5": {"level_max_abs_bp": 1.0, "level_median_abs_bp": 0.1, "daily_return_corr_min": 0.9999,
                 "min_common_session_share": 0.99},
    # A6 — Phase C, Berkshire Hathaway Class B (BRK-B, US0846707026). Frozen BEFORE any BRK request.
    # Share-class identity: each A share converts into 1,500 B shares (since the 50:1 B split of
    # 21/01/2010), so A / (1,500 x B) stays close to 1; a second vendor's closes must match the
    # NYSE closing prices to rounding; Berkshire paid no dividend, so close = total return.
    "BRK_A6": {"ab_ratio_median_abs_bp": 50.0, "ab_ratio_max_abs_bp": 200.0, "ab_daily_corr_min": 0.99,
               "vendor_median_abs_bp": 1.0, "vendor_p99_abs_bp": 5.0, "vendor_max_abs_bp": 50.0,
               "vendor_min_common_share": 0.99, "dividends_max": 0, "splits_max": 0,
               "adjclose_max_rel_gap": 1e-9},
    # A6-bis — owner-approved POST-HOC revision (18/10/2026) after the A6 A/B failures were observed.
    # Conversion is one-way (A -> 1,500 B; Berkshire SEC filings), so only A < 1,500 B is anomalous.
    # Where Nasdaq.com prices exist, the direct vendor comparison decides and the symmetric A/B max
    # and daily correlation become diagnostics. Before Nasdaq coverage: median kept, one-sided lower
    # bound and cumulative A/B divergence (both chosen after observation: measured -75 bp and 14 bp).
    # 10-K ranges (frozen BEFORE downloading the 2015 Form 10-K): every Yahoo close inside the
    # officially reported quarterly [low, high] (0.1 % rounding margin); for complete quarters, the
    # Yahoo intraday extremes within 1 % of the reported extremes. A sanity check, not a daily proof.
    "BRK_A6_BIS": {"ab_median_abs_bp": 50.0, "ab_lower_bound_bp": -100.0, "ab_cumulative_abs_bp": 50.0,
                   "range_margin": 0.001, "range_extreme_rel": 0.01},
    # A4 — ETF proxy FR0007052782: level anchors, completeness, unexplained drops, corporate actions.
    "CAC40_ETF_A4": {"nav_anchor_abs": 0.01, "nav_anchors_per_year_min": 2, "unexplained_drop_bp": -75.0,
                     "event_residual_cap_bp": 100.0, "event_residual_yield_share": 0.5,
                     "corporate_action_gap_bp": 100.0},
}
# Bitstamp suspended trading after its 04/01/2015 hack: the 06–08/01/2015 candles have zero volume
# (no price). The snapshots that would use them keep the last traded close (05/01), explicitly.
BTC_STALE_SESSIONS = {pd.Timestamp("2015-01-07"): "Bougie Bitstamp du 06/01/2015 sans volume (suspension)",
                      pd.Timestamp("2015-01-08"): "Bougie Bitstamp du 07/01/2015 sans volume (suspension)",
                      pd.Timestamp("2015-01-09"): "Bougie Bitstamp du 08/01/2015 sans volume (suspension)"}


# ---------------------------------------------------------------- calendars and clocks
def _observed(day: date) -> date | None:
    """NYSE observance: Sunday -> Monday, Saturday -> Friday (but never into the previous year)."""
    if day.weekday() == 6:
        return day + timedelta(days=1)
    if day.weekday() == 5:
        friday = day - timedelta(days=1)
        return None if friday.year != day.year else friday
    return day


def _nth_weekday(year, month, weekday, n):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year, month, weekday):
    last = (date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def euronext_holidays(year: int) -> set[date]:
    e = easter(year)
    return {date(year, 1, 1), e - timedelta(days=2), e + timedelta(days=1), date(year, 5, 1),
            date(year, 12, 25), date(year, 12, 26)}


def nyse_holidays(year: int) -> set[date]:
    e = easter(year)
    days = {_observed(date(year, 1, 1)), _nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3),
            e - timedelta(days=2), _last_weekday(year, 5, 0), _observed(date(year, 7, 4)),
            _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 11, 3, 4), _observed(date(year, 12, 25))}
    if year >= 2022:
        days.add(_observed(date(year, 6, 19)))
    return {d for d in days if d is not None} | {d for d in NYSE_SPECIAL_CLOSURES if d.year == year}


def _sessions(start, end, holidays) -> pd.DatetimeIndex:
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if end > HARD_CUTOFF:
        raise CutoffViolation("Calendrier demandé au-delà du 29/12/2023.")
    days = pd.bdate_range(start, end)
    closed = set().union(*(holidays(y) for y in range(start.year, end.year + 1)))
    return pd.DatetimeIndex([d for d in days if d.date() not in closed], name="Date")


def euronext_sessions(start=DEVELOPMENT_START, end=HARD_CUTOFF) -> pd.DatetimeIndex:
    return _sessions(start, end, lambda y: euronext_holidays(y) | {d for d in EURONEXT_NO_DATA_DAYS if d.year == y})


def nyse_sessions(start=DEVELOPMENT_START, end=HARD_CUTOFF) -> pd.DatetimeIndex:
    return _sessions(start, end, nyse_holidays)


def is_half_day(day) -> bool:
    day = pd.Timestamp(day)
    return day.month == 12 and day.day in (24, 31)


def _utc(day, clock: time, zone: ZoneInfo) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(pd.Timestamp(day).date(), clock, zone)).tz_convert("UTC")


def snapshot_instant(day) -> pd.Timestamp:
    return _utc(day, HALF_DAY_SNAPSHOT_TIME if is_half_day(day) else SNAPSHOT_TIME, PARIS)


def nyse_close_instant(day) -> pd.Timestamp:
    # 16:00 is an upper bound on early-close days (13:00): availability is never understated.
    return _utc(day, NYSE_CLOSE_TIME, NEW_YORK)


def ecb_publication_instant(day) -> pd.Timestamp:
    return _utc(day, ECB_PUBLICATION_TIME, FRANKFURT)


def utc_day_close_instant(day) -> pd.Timestamp:
    return pd.Timestamp(pd.Timestamp(day).date() + timedelta(days=1), tz="UTC")


def euronext_close_instant(day) -> pd.Timestamp:
    return snapshot_instant(day)


CLOCKS = {"same_session": euronext_close_instant, "nyse": nyse_close_instant,
          "ecb": ecb_publication_instant, "utc_day": utc_day_close_instant}


# ---------------------------------------------------------------- causal as-of selection
def _check_index(index: pd.DatetimeIndex, label: str):
    if not isinstance(index, pd.DatetimeIndex) or index.tz is not None or index.hasnans or index.empty:
        raise DataUnavailable(f"{label} : dates journalières sans fuseau requises.")
    if index.max() > HARD_CUTOFF:
        raise CutoffViolation(f"{label} : observation après le 29/12/2023 interdite.")
    if index.has_duplicates or not index.is_monotonic_increasing or not index.equals(index.normalize()):
        raise DataUnavailable(f"{label} : dates uniques, normalisées et triées requises.")


def _check_values(values: pd.Series, label: str):
    array = values.to_numpy(float)
    if not np.isfinite(array).all() or (array <= 0).any():
        raise DataUnavailable(f"{label} : valeur manquante, nulle ou invalide ; aucun remplissage.")


def drop_placeholders(values: pd.Series, asset: str) -> pd.Series:
    """Remove declared vendor rows on closed days, after checking they carry no new information."""
    for day in VENDOR_EXCEPTIONS.get(asset, {}).get("placeholder", {}):
        if day not in values.index:
            raise DataUnavailable(f"{asset} : ligne fictive déclarée absente ({day.date()}).")
        position = values.index.get_loc(day)
        if position == 0 or values.iloc[position] != values.iloc[position - 1]:
            raise DataUnavailable(f"{asset} : la ligne du {day.date()} n'est pas une simple répétition.")
    return values.drop(list(VENDOR_EXCEPTIONS.get(asset, {}).get("placeholder", {})))


def asof(values: pd.Series, clock: str, sessions: pd.DatetimeIndex, label: str,
         allowed_missing=()) -> pd.DataFrame:
    """Latest observation available at each snapshot; returns value, source date and age.

    ``available`` instants come from the declared clock, never from the data. An observation
    becoming available after the snapshot can never be selected (strictly causal). For the
    ``same_session`` clock every session needs its own observation, except the exact listed
    ``allowed_missing`` sessions (previous close used, at most MAX_AGE_DAYS['nyse'] days old).
    For other clocks, listed sessions may exceed the clock's age limit up to the same bound.
    """
    _check_index(values.index, label)
    _check_values(values, label)
    _check_index(sessions, "Calendrier")
    allowed = pd.DatetimeIndex(sorted(allowed_missing))
    if clock == "same_session":
        window = values.loc[sessions[0]:sessions[-1]].index
        if len(window.difference(sessions)):
            raise DataUnavailable(f"{label} : observation hors séance Euronext ({window.difference(sessions)[0].date()}).")
        missing = sessions.difference(window)
        if not missing.equals(allowed.intersection(sessions)) or len(allowed.difference(sessions)):
            extra = missing.difference(allowed)
            day = extra[0].date() if len(extra) else allowed.difference(missing)[0].date()
            raise DataUnavailable(f"{label} : séance Euronext sans observation ou exception inutile ({day}).")
    available = pd.DatetimeIndex([CLOCKS[clock](d) for d in values.index])
    if not available.is_monotonic_increasing:
        raise DataUnavailable(f"{label} : horloge de disponibilité non monotone.")
    snaps = pd.DatetimeIndex([snapshot_instant(d) for d in sessions])
    position = available.searchsorted(snaps, side="right") - 1
    if (position < 0).any():
        raise DataUnavailable(f"{label} : aucune observation disponible au premier instantané.")
    source = values.index[position]
    age = (sessions - source).days.to_numpy()
    limit = np.full(len(sessions), MAX_AGE_DAYS[clock])
    limit[sessions.isin(allowed)] = MAX_AGE_DAYS["nyse"]
    if clock != "same_session" and len(allowed):
        # Other clocks: a listed session must really exceed the normal age limit (no blanket waiver).
        needed = sessions[age > MAX_AGE_DAYS[clock]]
        if not allowed.isin(needed).all():
            raise DataUnavailable(f"{label} : exception inutile ({allowed[~allowed.isin(needed)][0].date()}).")
    if (age > limit).any():
        worst = sessions[int(np.argmax(age - limit))]
        raise DataUnavailable(f"{label} : observation trop ancienne au {worst.date()} ({age.max()} jours).")
    if (available[position] > snaps).any():  # defence in depth
        raise CutoffViolation(f"{label} : observation future sélectionnée.")
    return pd.DataFrame({"value": values.to_numpy(float)[position], "source_date": source,
                         "age_days": age, "available_utc": available[position],
                         "snapshot_utc": snaps}, index=sessions)


def explicit_total_return(raw: pd.DataFrame, label: str) -> pd.Series:
    """USD total-return level: (Close + cash distributions) / previous Close, compounded.

    Distributions are reinvested gross at the ex-date close (no withholding tax). A split inside
    the frame is refused rather than adjusted implicitly.
    """
    _check_index(raw.index, label)
    close = raw["Close"].astype(float)
    _check_values(close, label)
    if "Stock Splits" in raw and (raw["Stock Splits"].fillna(0) != 0).any():
        raise DataUnavailable(f"{label} : division d'actions dans la fenêtre ; ajustement explicite requis.")
    cash = raw.get("Dividends", pd.Series(0.0, index=raw.index)).astype(float)
    if "Capital Gains" in raw:
        cash = cash + raw["Capital Gains"].astype(float)
    if not np.isfinite(cash.to_numpy()).all() or (cash < 0).any():
        raise DataUnavailable(f"{label} : distribution invalide.")
    growth = (close + cash) / close.shift(1)
    growth.iloc[0] = 1.0  # normalization anchor, not an imputed return
    return growth.cumprod().rename(label)


def eur_level(usd: pd.Series, usd_per_eur: pd.Series, sessions: pd.DatetimeIndex, label: str):
    """US close as-of (NYSE clock) divided by the ECB fixing as-of (publication clock)."""
    price = asof(usd, "nyse", sessions, label)
    fx = asof(usd_per_eur, "ecb", sessions, "EUR/USD BCE")
    level = price["value"] / fx["value"]
    detail = price.add_prefix("price_").join(fx.add_prefix("fx_"))
    return (level / level.iloc[0] * 100).rename("level"), detail


# ---------------------------------------------------------------- external file parsers
# (pattern, candidate (year, month, day) group orders). Slash dates are read BOTH as dd/mm and
# mm/dd (Investing.com English exports): the scan must never miss a later date by ambiguity.
_MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                                           "oct", "nov", "dec"))}
_DATE_PATTERNS = (
    (re.compile(r"(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)"), ((0, 1, 2),)),
    (re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})(?!\d)"), ((2, 1, 0), (2, 0, 1))),
    (re.compile(r"(?<![\d.])(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?![\d.])"), ((0, 1, 2),)),
)
_TEXT_DATE = re.compile(r"(?i)\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (\d{1,2}),? (20\d{2})\b")
_EPOCH = re.compile(r"(?<![\d.])(1[4-9]\d{8}|2[0-1]\d{8})(?:\d{3})?(?![\d.])")  # seconds or milliseconds


def scan_dates(text: str) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """(min, max) date in a downloaded text: ISO, dd/mm/yyyy AND mm/dd/yyyy, 'Dec 29, 2023',
    yyyymmdd and epoch seconds.

    Used BEFORE parsing values: a later-than-cutoff maximum means the file must be discarded.
    """
    found = []
    for pattern, orders in _DATE_PATTERNS:
        for groups in pattern.findall(text):
            for order in orders:
                y, m, d = (int(groups[i]) for i in order)
                try:
                    found.append(pd.Timestamp(y, m, d))
                except ValueError:
                    continue
    for month, day, year in _TEXT_DATE.findall(text):
        try:
            found.append(pd.Timestamp(int(year), _MONTHS[month.lower()[:3]], int(day)))
        except ValueError:
            continue
    for epoch in _EPOCH.findall(text):
        found.append(pd.Timestamp(int(epoch), unit="s").normalize())
    return (min(found), max(found)) if found else (None, None)


def assert_text_before_cutoff(text: str, label: str):
    latest = scan_dates(text)[1]
    if latest is not None and latest > HARD_CUTOFF:
        raise CutoffViolation(f"{label} : date {latest.date()} postérieure au 29/12/2023 ; valeurs non lues.")


def parse_ecb(text: str) -> pd.Series:
    assert_text_before_cutoff(text, "BCE")
    frame = pd.read_csv(io.StringIO(text))
    if set(frame["KEY"]) != {"EXR.D.USD.EUR.SP00.A"}:
        raise DataUnavailable("BCE : série EXR.D.USD.EUR.SP00.A attendue.")
    series = pd.Series(frame["OBS_VALUE"].astype(float).to_numpy(),
                       index=pd.DatetimeIndex(pd.to_datetime(frame["TIME_PERIOD"]), name="Date"), name="usd_per_eur")
    _check_index(series.index, "BCE")
    _check_values(series, "BCE")
    return series


def parse_msci(text: str, code: str, currency: str) -> pd.Series:
    assert_text_before_cutoff(text, "MSCI")
    data = json.loads(text)
    if str(data.get("msci_index_code")) != code or data.get("index_variant_type") != "NETR" \
            or data.get("ISO_currency_symbol") != currency:
        raise DataUnavailable("MSCI : indice, variante NETR ou devise inattendus.")
    rows = data["indexes"]["INDEX_LEVELS"]
    series = pd.Series([float(r["level_eod"]) for r in rows],
                       index=pd.DatetimeIndex(pd.to_datetime([str(r["calc_date"]) for r in rows]), name="Date"))
    _check_index(series.index, "MSCI")
    _check_values(series, "MSCI")
    return series


def parse_bitstamp(texts: list[str], pair: str) -> pd.Series:
    """Daily candles keyed by UTC opening date; close = last trade of that UTC day."""
    rows = {}
    for text in texts:
        assert_text_before_cutoff(text, "Bitstamp")
        data = json.loads(text)["data"]
        if data["pair"] != pair:
            raise DataUnavailable("Bitstamp : paire inattendue.")
        for candle in data["ohlc"]:
            day = pd.Timestamp(int(candle["timestamp"]), unit="s")
            if day != day.normalize():
                raise DataUnavailable("Bitstamp : bougie non alignée sur 00:00 UTC.")
            value = float(candle["close"])
            if day in rows and rows[day] != value:
                raise DataUnavailable("Bitstamp : bougies contradictoires.")
            rows[day] = value
    series = pd.Series(rows).sort_index()
    series.index = pd.DatetimeIndex(series.index, name="Date")
    _check_index(series.index, "Bitstamp")
    _check_values(series, "Bitstamp")
    return series


# ---------------------------------------------------------------- comparison statistics
def _cagr(series: pd.Series) -> float:
    years = (series.index[-1] - series.index[0]).days / 365.25
    return (series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1


def _month_end(series: pd.Series) -> pd.Series:
    return series.groupby(series.index.to_period("M")).last()


def tracking(fund: pd.Series, index: pd.Series) -> dict:
    """Common-date tracking statistics of a fund versus a reference (same currency)."""
    common = fund.index.intersection(index.index)
    f, i = fund.loc[common], index.loc[common]
    daily = pd.DataFrame({"f": f.pct_change(), "i": i.pct_change()}).dropna()
    monthly = pd.DataFrame({"f": _month_end(f).pct_change(), "i": _month_end(i).pct_change()}).dropna()
    both = pd.DataFrame({"f": f, "i": i})
    years, previous = {}, both.iloc[0]
    for year, end in both.groupby(common.year).last().iterrows():
        years[str(year)] = float(end["f"] / previous["f"] - end["i"] / previous["i"])
        previous = end
    diff = (daily["f"] - daily["i"]).abs() * 1e4
    return {"common_dates": len(common), "first": str(common[0].date()), "last": str(common[-1].date()),
            "annualized_difference": _cagr(f) - _cagr(i),
            "daily_corr": float(daily.corr().iloc[0, 1]), "monthly_corr": float(monthly.corr().iloc[0, 1]),
            "daily_abs_diff_bp_median": float(diff.median()), "daily_abs_diff_bp_p99": float(diff.quantile(.99)),
            "daily_abs_diff_bp_max": float(diff.max()), "calendar_year_difference": years}


def level_gap_bp(a: pd.Series, b: pd.Series) -> pd.Series:
    common = a.index.intersection(b.index)
    return (a.loc[common] / b.loc[common] - 1) * 1e4


@dataclass(frozen=True)
class Check:
    name: str
    value: float | str
    limit: str
    passed: bool

    def as_dict(self):
        value = self.value if isinstance(self.value, str) or not math.isfinite(self.value) else round(self.value, 6)
        return {"contrôle": self.name, "valeur": value, "limite": self.limit, "conforme": self.passed}


def within(name, value, low=None, high=None) -> Check:
    ok = math.isfinite(value) and (low is None or value >= low) and (high is None or value <= high)
    limit = f"[{'-∞' if low is None else low}, {'+∞' if high is None else high}]"
    return Check(name, float(value), limit, bool(ok))


# ---------------------------------------------------------------- CAC 40 total-return import
def parse_euronext_export(text: str) -> tuple[str, pd.Series]:
    """Euronext 'Historical Data' CSV (';' separated, dd/mm/yyyy) -> (ISIN, Close series).

    The date scan runs first: an export reaching past the cutoff is refused before values are read.
    """
    assert_text_before_cutoff(text, "Export CAC 40")
    lines = [line.strip().lstrip("﻿") for line in text.splitlines() if line.strip()]
    header = next((k for k, line in enumerate(lines) if line.split(";")[0].strip('"') == "Date"), None)
    if header is None or header == 0:
        raise DataUnavailable("Export Euronext : en-tête Date;…;Close introuvable.")
    isin = lines[header - 1].strip('"').strip()
    columns = [c.strip('"') for c in lines[header].split(";")]
    if "Close" not in columns:
        raise DataUnavailable("Export Euronext : colonne Close requise.")
    rows = [line.split(";") for line in lines[header + 1:]]
    if not rows:
        raise DataUnavailable("Export Euronext : aucune observation.")
    dates, closes = [], []
    for row in rows:
        if len(row) != len(columns):
            raise DataUnavailable("Export Euronext : ligne mal formée.")
        dates.append(pd.to_datetime(row[0].strip('"'), format="%d/%m/%Y"))
        closes.append(float(row[columns.index("Close")].strip('"')))
    series = pd.Series(closes, index=pd.DatetimeIndex(dates, name="Date"), name="level").sort_index()
    return isin, series


def _localized_number(text: str, decimal: str) -> float:
    cleaned = text.strip().strip('"').replace("\xa0", "").replace(" ", "").replace(" ", "")
    cleaned = cleaned.replace(",", "") if decimal == "." else cleaned.replace(".", "").replace(",", ".")
    return float(cleaned)


def parse_investing_export(text: str, date_order: str, decimal: str) -> pd.Series:
    """Investing.com 'Historical Data' CSV -> Close series. The file carries no ISIN: the
    caller must declare it. Date order and decimal mark are explicit, never guessed; a wrong
    order then fails the Euronext-session check. The date scan runs before any value is read.
    """
    if date_order not in ("dmy", "mdy") or decimal not in (".", ","):
        raise ValueError("Ordre des dates (dmy/mdy) et séparateur décimal (. ou ,) explicites requis.")
    assert_text_before_cutoff(text, "Export Investing.com")
    import csv
    rows = [r for r in csv.reader(io.StringIO(text.lstrip("﻿"))) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise DataUnavailable("Export Investing.com : aucune observation.")
    header = [c.strip().strip("﻿") for c in rows[0]]
    close = next((c for c in ("Price", "Dernier", "Close", "Clôture") if c in header), None)
    if header[0] not in ("Date", "Datum") or close is None:
        raise DataUnavailable("Export Investing.com : colonnes Date et Price/Dernier requises.")
    fmt = "%d/%m/%Y" if date_order == "dmy" else "%m/%d/%Y"
    dates, closes = [], []
    for row in rows[1:]:
        if len(row) != len(header):
            raise DataUnavailable("Export Investing.com : ligne mal formée.")
        dates.append(pd.to_datetime(row[0].strip().replace(".", "/").replace("-", "/"), format=fmt))
        closes.append(_localized_number(row[header.index(close)], decimal))
    series = pd.Series(closes, index=pd.DatetimeIndex(dates, name="Date"), name="level")
    if series.index.has_duplicates:
        raise DataUnavailable("Export Investing.com : dates dupliquées.")
    return series.sort_index()


def parse_bourse_direct_export(text: str) -> pd.Series:
    """Bourse Direct historical CSV ('Date;Open;High;Low;Close;Volume;Currency', 'YYYY/MM/DD HH:MM').

    The file carries no ISIN (declared by the caller). Every row must be EUR. A file reaching past
    the cutoff is refused whole, before values are read: it is never trimmed afterwards.
    """
    assert_text_before_cutoff(text, "Export Bourse Direct")
    lines = [line.strip() for line in text.lstrip("﻿").splitlines() if line.strip()]
    if not lines or [c.strip('"') for c in lines[0].split(";")] != ["Date", "Open", "High", "Low", "Close", "Volume", "Currency"]:
        raise DataUnavailable("Export Bourse Direct : en-tête Date;Open;High;Low;Close;Volume;Currency attendu.")
    dates, closes = [], []
    for line in lines[1:]:
        row = [field.strip().strip('"') for field in line.split(";")]
        if len(row) != 7 or row[6] != "EUR":
            raise DataUnavailable("Export Bourse Direct : ligne mal formée ou devise différente de EUR.")
        dates.append(pd.to_datetime(row[0], format="%Y/%m/%d %H:%M").normalize())
        closes.append(float(row[4]))
    series = pd.Series(closes, index=pd.DatetimeIndex(dates, name="Date"), name="level")
    if series.index.has_duplicates:
        raise DataUnavailable("Export Bourse Direct : dates dupliquées.")
    return series.sort_index()


def parse_distributions(text: str, label: str) -> pd.Series:
    """Distribution ledger CSV with columns ex_date (YYYY-MM-DD) and amount_eur (per share)."""
    assert_text_before_cutoff(text, label)
    frame = pd.read_csv(io.StringIO(text.lstrip("﻿")), dtype=str)
    if list(frame.columns)[:2] != ["ex_date", "amount_eur"]:
        raise DataUnavailable(f"{label} : colonnes ex_date, amount_eur requises.")
    index = pd.DatetimeIndex(pd.to_datetime(frame["ex_date"].str.strip(), format="%Y-%m-%d"), name="Date")
    series = pd.Series(frame["amount_eur"].astype(float).to_numpy(), index=index, name="amount_eur")
    _check_index(series.sort_index().index, label)
    _check_values(series, label)
    return series.sort_index()


def _session_levels(series: pd.Series, label: str, allowed_missing=()) -> pd.Series:
    if series.index.has_duplicates:
        raise DataUnavailable(f"{label} : dates dupliquées.")
    _check_index(series.index, label)
    _check_values(series, label)
    sessions = euronext_sessions()
    window = series.loc[DEVELOPMENT_START:HARD_CUTOFF]
    extra = window.index.difference(sessions)
    if len(extra):
        raise DataUnavailable(f"{label} : {len(extra)} date(s) hors séances Euronext, ex. {extra[0].date()}.")
    return asof(window, "same_session", sessions, label, allowed_missing=allowed_missing)["value"].rename("level")


def parse_nav_anchors(text: str, label: str) -> pd.Series:
    """Issuer NAV anchors CSV: date (YYYY-MM-DD), nav_eur — from annual/semi-annual reports."""
    assert_text_before_cutoff(text, label)
    frame = pd.read_csv(io.StringIO(text.lstrip("﻿")), dtype=str)
    if list(frame.columns)[:2] != ["date", "nav_eur"]:
        raise DataUnavailable(f"{label} : colonnes date, nav_eur requises.")
    series = pd.Series(frame["nav_eur"].astype(float).to_numpy(), name="nav_eur",
                       index=pd.DatetimeIndex(pd.to_datetime(frame["date"].str.strip(), format="%Y-%m-%d"), name="Date"))
    series = series.sort_index()
    _check_index(series.index, label)
    _check_values(series, label)
    return series


def parse_corporate_actions(text: str, label: str) -> pd.DataFrame:
    """Declared corporate actions CSV: date (YYYY-MM-DD), ratio (new shares per old share), description.
    An empty table (header only) is a positive declaration that no event occurred."""
    assert_text_before_cutoff(text, label)
    frame = pd.read_csv(io.StringIO(text.lstrip("﻿")), dtype=str)
    if list(frame.columns)[:3] != ["date", "ratio", "description"]:
        raise DataUnavailable(f"{label} : colonnes date, ratio, description requises.")
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame["date"].str.strip(), format="%Y-%m-%d"), name="Date")
    frame = frame.assign(ratio=frame["ratio"].astype(float)).drop(columns="date").sort_index()
    if len(frame):
        _check_index(frame.index, label)
    return frame


def validate_cac40_etf(price: pd.Series, distributions: pd.Series, cross_check: pd.Series | None = None,
                       reference: pd.Series | None = None, nav_anchors: pd.Series | None = None,
                       distributions_per_year: int | None = None, corporate_actions: pd.DataFrame | None = None):
    """ETF proxy FR0007052782: unadjusted closes + distribution ledger -> total-return level.

    Validation requires (1) a second, independent ledger matching every ex-date and amount and
    (2) the CAC 40 price index FR0003500008, against which the ETF must drop by the distribution
    yield on each ex-date (proof that closes are NOT already dividend-adjusted, so distributions
    are not counted twice) and show no unexplained jump (split, wrong series).
    Amendment A4 adds: issuer NAV anchors (an adjusted history sits ~20 % below them in 2014),
    exact distribution count per year from the prospectus policy, no unexplained drop on ordinary
    sessions (a distribution missing from BOTH ledgers), a per-event residual bounded by half the
    distribution yield, and declared corporate actions with ratio 1 and no jump. Every input is
    required for validation. Returns (levels, checks, validated). This is an ETF proxy, never an
    official NR/GR series; the official CAC 40 Net Return remains the preferred source.
    """
    tol, a4 = TOLERANCES["CAC40_ETF"], AMENDMENTS["CAC40_ETF_A4"]
    levels = _session_levels(price, "ETF CAC 40")
    sessions = levels.index
    ledger = distributions.loc[DEVELOPMENT_START:HARD_CUTOFF]
    outside = ledger.index.difference(sessions)
    if len(outside):
        raise DataUnavailable(f"Registre de distributions : ex-date hors séance ({outside[0].date()}).")
    if not ledger.empty and ledger.index[0] == sessions[0]:
        ledger = ledger.iloc[1:]  # entitlement precedes the first purchase: excluded explicitly
    raw = pd.DataFrame({"Close": levels, "Dividends": ledger.reindex(sessions).fillna(0.0)})
    tr = explicit_total_return(raw, "ETF CAC 40")
    checks = [Check("Séances Euronext couvertes", float(len(levels)), f"= {len(sessions)}", True),
              Check("Distributions dans la fenêtre", float(len(ledger)), "information", True)]
    events = pd.DataFrame(columns=["ratio", "description"]) if corporate_actions is None else corporate_actions
    events = events.loc[DEVELOPMENT_START:HARD_CUTOFF]
    if len(events.index.difference(sessions)):
        raise DataUnavailable("Opérations sur titres : date hors séance Euronext.")
    if (events["ratio"] != 1.0).any():
        raise DataUnavailable("Opération sur titres de ratio différent de 1 : ajustement explicite requis, non automatique.")
    validated = all(x is not None for x in (cross_check, reference, nav_anchors, distributions_per_year,
                                            corporate_actions))
    if distributions_per_year is not None:
        counts = ledger.groupby(ledger.index.year).size().reindex(range(2015, 2024), fill_value=0)
        wrong = {int(y): int(n) for y, n in counts.items() if n != distributions_per_year}
        partial = int((ledger.index.year == 2014).sum())
        checks.append(Check(f"Exhaustivité : {distributions_per_year} distribution(s) par année 2015–2023",
                            float(len(wrong)), f"0 année en écart {wrong}" if wrong else "0 année en écart",
                            not wrong and partial <= distributions_per_year))
    if nav_anchors is not None:
        anchors = nav_anchors.loc[DEVELOPMENT_START:HARD_CUTOFF]
        if len(anchors.index.difference(sessions)):
            raise DataUnavailable("Ancrages VL : date hors séance Euronext.")
        per_year = anchors.groupby(anchors.index.year).size().reindex(range(2015, 2024), fill_value=0)
        deviation = (levels.reindex(anchors.index) / anchors - 1).abs()
        checks += [within("Ancrages VL : nombre minimal par année 2015–2023", float(per_year.min()),
                          a4["nav_anchors_per_year_min"]),
                   within("Ancrages VL : |clôture / VL − 1| max", float(deviation.max()) if len(anchors) else float("nan"),
                          high=a4["nav_anchor_abs"])]
    if cross_check is not None:
        other = cross_check.loc[DEVELOPMENT_START:HARD_CUTOFF].drop(sessions[0], errors="ignore")
        same_dates = other.index.equals(ledger.index)
        checks.append(Check("Registres indépendants : mêmes ex-dates", float(len(ledger.index.symmetric_difference(other.index))),
                            "0 écart", same_dates))
        if same_dates:
            checks.append(within("Registres : écart de montant maximal (EUR)", float((other - ledger).abs().max()) if len(ledger) else 0.0,
                                 high=tol["ledger_amount_tol_eur"]))
    if reference is not None:
        ref = _session_levels(reference, "CAC 40 prix")
        gap = (levels.pct_change() - ref.pct_change()).dropna()
        ex = ledger.index
        yield_ = ledger / levels.shift(1).reindex(ex)
        residual = (gap.reindex(ex) + yield_) * 1e4
        ordinary = gap.drop(ex, errors="ignore").abs() * 1e4
        checks += [within("Ex-dates : |écart ETF − indice + rendement distribué| max (pb)",
                          float(residual.abs().max()) if len(ex) else 0.0, high=tol["exdate_residual_bp"]),
                   within("Ex-dates : résidu moyen absolu (pb)", abs(float(residual.mean())) if len(ex) else 0.0,
                          high=tol["exdate_mean_residual_bp"]),
                   Check("Cours non ajustés des distributions (baisse moyenne ≥ moitié du rendement)",
                         float(-gap.reindex(ex).mean() * 1e4) if len(ex) else float("nan"),
                         f"≥ {float(yield_.mean() * 1e4 / 2) if len(ex) else 'n/a'}",
                         bool(len(ex)) and float(-gap.reindex(ex).mean()) >= float(yield_.mean()) / 2),
                   within("Hors ex-dates : écart quotidien maximal vs indice (pb)", float(ordinary.max()),
                          high=tol["daily_gap_bp_max"]),
                   within("Écart annualisé rendement total ETF − indice prix", _cagr(tr) - _cagr(ref),
                          *tol["tr_minus_price"])]
        # A4: per-event power, unexplained drops (missing distribution), corporate-action continuity.
        bound = np.minimum(a4["event_residual_cap_bp"], a4["event_residual_yield_share"] * yield_ * 1e4)
        closer = ((gap.reindex(ex) + yield_).abs() < gap.reindex(ex).abs())
        weak = ex[(residual.abs() > bound) | ~closer]
        checks.append(Check("Par ex-date : résidu ≤ min(100 pb ; ½ rendement) et plus proche de « non ajusté »",
                            float(len(weak)), f"0 événement en écart {[str(d.date()) for d in weak]}" if len(weak)
                            else "0 événement en écart", not len(weak)))
        plain = gap.drop(ex.union(events.index), errors="ignore") * 1e4
        drops = plain[plain < a4["unexplained_drop_bp"]]
        checks.append(Check(f"Hors ex-dates : baisse inexpliquée < {a4['unexplained_drop_bp']:.0f} pb vs indice",
                            float(len(drops)), f"0 séance {[str(d.date()) for d in drops.index[:5]]}" if len(drops)
                            else "0 séance", not len(drops)))
        for day, row in events.iterrows():
            checks.append(within(f"Opération du {day.date()} ({row['description']}) : écart vs indice (|pb|)",
                                 abs(float(gap.loc[day] * 1e4)), high=a4["corporate_action_gap_bp"]))
    validated = validated and all(c.passed for c in checks)
    return (tr / tr.iloc[0] * 100).rename("level"), checks, validated


def apply_official_corrections(series: pd.Series, key: str) -> tuple[pd.Series, list[dict]]:
    """Replace declared erroneous vendor prints by official closes; returns (copy, records)."""
    out, records = series.copy(), []
    for day, item in OFFICIAL_CORRECTIONS.get(key, {}).items():
        if day not in out.index or abs(float(out.loc[day]) - item["raw"]) > 0.01:
            raise DataUnavailable(f"Correction {key} du {day.date()} non applicable : valeur brute inattendue.")
        records.append({"date": str(day.date()), "raw": float(out.loc[day]), "corrected": item["value"],
                        "kind": item["kind"], "source": item["source"]})
        out.loc[day] = item["value"]
    return out, records


def apply_relabels(series: pd.Series, vendor: str) -> pd.Series:
    """Move declared mislabelled rows (holiday -> missing previous session). Each declaration must
    match the file exactly: source present on a non-session, target absent and a session."""
    sessions = euronext_sessions()
    out = series.copy()
    for source, target in VENDOR_EXCEPTIONS.get(vendor, {}).get("relabel", {}).items():
        if source not in out.index or source in sessions or target in out.index or target not in sessions:
            raise DataUnavailable(f"Réétiquetage déclaré {source.date()} → {target.date()} non applicable.")
        out = out.rename(index={source: target})
    return out.sort_index()


def validate_cac40(isin: str, series: pd.Series, reference: tuple[str, pd.Series] | None = None,
                   vendor: str | None = None):
    """Structural checks always; economic validation requires an independent reference series.

    ``reference`` is (ISIN, levels) of the CAC 40 price index FR0003500008 or of the other TR
    variant. Dividends are never negative, so on every session GR >= NR >= price index in
    daily return, up to a declared rounding tolerance.
    ``vendor`` selects the declared VENDOR_EXCEPTIONS of that export (relabelled rows, missing
    sessions valued with the previous close as a stale mark). Return comparisons with the reference
    use the export's OBSERVED dates only, so a stale mark never creates an artificial gap.
    Returns (levels on the Euronext calendar, checks, validated flag).
    """
    if isin == CAC40_PRICE_ISIN:
        raise DataUnavailable("CAC 40 prix (FR0003500008) refusé : rendement total NR ou GR requis.")
    if isin not in CAC40_TR_ISINS:
        raise DataUnavailable(f"Identifiant {isin!r} non reconnu : QS0011131826 (NR) ou QS0011131834 (GR) requis.")
    exceptions = VENDOR_EXCEPTIONS.get(vendor, {}) if vendor else {}
    series = apply_relabels(series, vendor) if vendor else series
    missing = list(exceptions.get("missing", {}))
    levels = _session_levels(series, "CAC 40", allowed_missing=missing)
    sessions = levels.index
    observed = series.loc[DEVELOPMENT_START:HARD_CUTOFF]
    returns = observed.pct_change().dropna()
    checks = [Check("Séances Euronext couvertes (dont marques reportées déclarées)", float(len(levels)),
                    f"= {len(sessions)} ; {len(missing)} marque(s) reportée(s)", True),
              Check("Variation absolue maximale entre observations", float(returns.abs().max()), "information", True)]
    validated = False
    if reference is not None:
        ref_isin, ref = reference
        if ref_isin == isin or ref_isin not in set(CAC40_TR_ISINS) | {CAC40_PRICE_ISIN}:
            raise DataUnavailable("Référence CAC 40 : indice prix ou autre variante TR requis.")
        ref = _session_levels(ref, "Référence CAC 40")
        tol = TOLERANCES["CAC40"]
        # Returns between consecutive OBSERVED dates of the export, the reference on the same dates.
        mine, theirs = observed, ref.reindex(observed.index)
        if theirs.isna().any():
            raise DataUnavailable("Référence CAC 40 absente à une date observée de l'export.")
        # Order the pair so that `high` must (weakly) out-perform `low` every interval.
        rank = {CAC40_PRICE_ISIN: 0, "QS0011131826": 1, "QS0011131834": 2}
        high, low = (mine, theirs) if rank[isin] > rank[ref_isin] else (theirs, mine)
        gap = (high.pct_change() - low.pct_change()).dropna() * 1e4
        for source, target in exceptions.get("relabel", {}).items():
            follow = observed.index[observed.index.get_loc(target) + 1]
            checks.append(within(f"Réétiquetage {source.date()} → {target.date()} : |écart de rendement vs référence| "
                                 f"le jour et le suivant (pb)", float(gap.loc[[target, follow]].abs().max()),
                                 high=tol["daily_shortfall_bp"]))
        checks.append(within("Plus forte sous-performance quotidienne de la variante la plus riche (pb)",
                             float(-gap.min()), high=tol["daily_shortfall_bp"]))
        if ref_isin == CAC40_PRICE_ISIN:
            bounds = tol["gr_yield_gap" if isin == "QS0011131834" else "nr_yield_gap"]
            checks.append(within("Écart annualisé TR − prix", _cagr(levels) - _cagr(ref), *bounds))
        validated = all(c.passed for c in checks)
    return levels, checks, validated


# ---------------------------------------------------------------- amendment A1: ECB FX persistence
def fx_persistence_checks(gap_bp: pd.Series, ecb: pd.Series) -> tuple[list[Check], dict]:
    """ECB vs WM/R gap (bp, base constant removed): accepted when it is information arriving
    between 14:15 and 17:00 that the NEXT ECB fixing absorbs, without persistence or level drift."""
    a = AMENDMENTS["FX_A1"]
    gap = gap_bp.dropna()
    following = (ecb.shift(-1) / ecb - 1).reindex(gap.index) * 1e4
    both = pd.DataFrame({"gap": gap, "next": following}).dropna()
    slope = float(np.polyfit(both["gap"], both["next"], 1)[0])
    corr = float(both.corr().iloc[0, 1])
    checks = [within("Écart absolu médian (pb)", float(gap.abs().median()), high=a["median_abs_bp"]),
              within("Écart absolu maximal (pb)", float(gap.abs().max()), high=a["max_abs_bp"]),
              within("Absorption : pente écart → mouvement BCE suivant", slope, *a["absorption_slope"]),
              within("Absorption : corrélation", corr, a["absorption_corr_min"]),
              within("Persistance : |autocorrélation à 1 jour|", abs(float(gap.autocorr())), high=a["lag1_abs_max"]),
              within("Écart au début (|pb|)", abs(float(gap.iloc[0])), high=a["endpoint_abs_bp"]),
              within("Écart à la fin (|pb|)", abs(float(gap.iloc[-1])), high=a["endpoint_abs_bp"]),
              within("Écart moyen signé (|pb|)", abs(float(gap.mean())), high=a["mean_abs_bp"])]
    return checks, {"absorption_slope": slope, "absorption_corr": corr, "observations": len(both)}


# ---------------------------------------------------------------- amendment A2: SPY level drift
def _longest_run(flags: pd.Series) -> int:
    runs = (flags != flags.shift()).cumsum()[flags]
    return int(runs.value_counts().max()) if len(runs) else 0


def spy_drift_checks(tr: pd.Series, index: pd.Series, exdate_gap_bp: pd.Series) -> tuple[list[Check], dict]:
    """Level gap of the explicit TR versus the index after removing a fitted linear fee drift.
    The original total-return construction is unchanged; daily statistics are diagnostics only."""
    a = AMENDMENTS["SP500_A2"]
    common = tr.index.intersection(index.index)
    f, i = tr.loc[common], index.loc[common]
    level = ((f / f.iloc[0]) / (i / i.iloc[0]) - 1) * 1e4
    years = (common - common[0]).days.to_numpy() / 365.25
    slope, intercept = np.polyfit(years, level.to_numpy(), 1)
    residual = level - (intercept + slope * years)
    daily = ((f.pct_change() - i.pct_change()) * 1e4).dropna()
    checks = [within("Écart annualisé SPY TR − S&P 500 TR", _cagr(f) - _cagr(i), a["td_min"], a["td_max"]),
              within(f"Écart max aux {len(exdate_gap_bp)} dates ex-dividende (pb)", float(exdate_gap_bp.abs().max()),
                     high=a["exdate_abs_bp"]),
              within("Écart de niveau hors dérive : médiane absolue (pb)", float(residual.abs().median()),
                     high=a["detrended_median_abs_bp"]),
              within("Écart de niveau hors dérive : |moyenne glissante 21 séances| max (pb)",
                     float(residual.rolling(21).mean().abs().max()), high=a["rolling21_abs_bp"]),
              within(f"Plus longue série de séances au-delà de {a['run_threshold_bp']:.0f} pb",
                     float(_longest_run(residual.abs() > a["run_threshold_bp"])), high=a["max_run_sessions"])]
    diagnostics = {"fitted_drift_bp_per_year": float(slope), "daily_gap_lag1_autocorrelation": float(daily.autocorr()),
                   "daily_corr": float(pd.concat([f.pct_change(), i.pct_change()], axis=1).dropna().corr().iloc[0, 1]),
                   "daily_abs_gap_p99_bp": float(daily.abs().quantile(.99)),
                   "sessions_beyond_run_threshold": int((residual.abs() > a["run_threshold_bp"]).sum())}
    return checks, diagnostics


# ---------------------------------------------------------------- amendment A3: Bitstamp composite
def parse_candles(texts: list[str], venue: str, pair: str | None = None) -> pd.DataFrame:
    """Daily candles keyed by UTC opening day -> DataFrame(close, volume). Scanned before parsing."""
    rows = {}
    for text in texts:
        assert_text_before_cutoff(text, venue)
        data = json.loads(text)
        if venue == "bitstamp":
            if data["data"]["pair"] != pair:
                raise DataUnavailable("Bitstamp : paire inattendue.")
            items = [(int(c["timestamp"]), float(c["close"]), float(c["volume"])) for c in data["data"]["ohlc"]]
        elif venue == "coinbase":   # [time, low, high, open, close, volume]
            items = [(int(c[0]), float(c[4]), float(c[5])) for c in data]
        elif venue == "bitfinex":   # [mts, open, close, high, low, volume]
            items = [(int(c[0]) // 1000, float(c[2]), float(c[5])) for c in data]
        else:
            raise ValueError("Plateforme inconnue.")
        for stamp, close, volume in items:
            day = pd.Timestamp(stamp, unit="s")
            if day != day.normalize():
                raise DataUnavailable(f"{venue} : bougie non alignée sur 00:00 UTC.")
            if day in rows and rows[day] != (close, volume):
                raise DataUnavailable(f"{venue} : bougies contradictoires ({day.date()}).")
            rows[day] = (close, volume)
    frame = pd.DataFrame.from_dict(rows, orient="index", columns=["close", "volume"]).sort_index()
    frame.index = pd.DatetimeIndex(frame.index, name="Date")
    _check_index(frame.index, venue)
    _check_values(frame["close"], venue)
    if (frame["volume"] < 0).any() or not np.isfinite(frame["volume"]).all():
        raise DataUnavailable(f"{venue} : volume invalide.")
    return frame


def usd_to_eur_by_utc_day(usd: pd.Series, usd_per_eur: pd.Series) -> pd.DataFrame:
    """Convert a UTC-day close with the latest ECB fixing published before that close (causal)."""
    published = pd.DatetimeIndex([ecb_publication_instant(d) for d in usd_per_eur.index])
    closes = pd.DatetimeIndex([utc_day_close_instant(d) for d in usd.index])
    position = published.searchsorted(closes, side="right") - 1
    if (position < 0).any():
        raise DataUnavailable("BTC : aucun fixing BCE publié avant la clôture.")
    source = usd_per_eur.index[position]
    age = (usd.index - source).days.to_numpy()
    if (age > AMENDMENTS["BTC_A3"]["fx_max_age_days"]).any():
        raise DataUnavailable("BTC : fixing BCE trop ancien.")
    if (published[position] > closes).any():
        raise CutoffViolation("BTC : fixing BCE futur.")
    return pd.DataFrame({"eur": usd.to_numpy() / usd_per_eur.to_numpy()[position], "fx_date": source,
                         "fx_age_days": age}, index=usd.index)


def btc_splice_date(eur: pd.DataFrame) -> pd.Timestamp:
    """First day of the first complete calendar month in which every EUR-book candle trades at
    least ``splice_min_daily_volume_btc`` (declared rule, not chosen on returns)."""
    threshold = AMENDMENTS["BTC_A3"]["splice_min_daily_volume_btc"]
    for period, block in eur.groupby(eur.index.to_period("M")):
        days = pd.date_range(period.start_time, period.end_time.normalize())
        if block.index.equals(days) and (block["volume"] >= threshold).all():
            return days[0]
    raise DataUnavailable("BTC : aucun mois liquide complet dans le carnet EUR.")


def btc_composite(usd: pd.DataFrame, eur: pd.DataFrame, usd_per_eur: pd.Series):
    """Bitstamp BTC/USD / ECB before the splice, native BTC/EUR from it. Candles below
    ``min_volume_btc`` are not prices: removed, never filled. Returns (series, detail, removed, splice)."""
    a = AMENDMENTS["BTC_A3"]
    splice = btc_splice_date(eur)
    pre, post = usd.loc[:splice - pd.Timedelta(days=1)], eur.loc[splice:]
    removed = pre.index[pre["volume"] < a["min_volume_btc"]].union(post.index[post["volume"] < a["min_volume_btc"]])
    pre, post = pre.drop(removed, errors="ignore"), post.drop(removed, errors="ignore")
    converted = usd_to_eur_by_utc_day(pre["close"], usd_per_eur)
    detail = pd.concat([pd.DataFrame({"eur": converted["eur"], "source": "bitstamp_btcusd_ecb",
                                      "volume_btc": pre["volume"], "fx_date": converted["fx_date"]}),
                        pd.DataFrame({"eur": post["close"], "source": "bitstamp_btceur",
                                      "volume_btc": post["volume"], "fx_date": pd.NaT})])
    _check_index(detail.index, "BTC composite")
    return detail["eur"].rename("BTC"), detail, removed, splice


def cross_venue_checks(primary: pd.Series, reference: pd.DataFrame, label: str) -> tuple[list[Check], dict]:
    """Same-currency, same-UTC-day comparison with an independent venue (illiquid reference
    candles excluded). Detects persistent venue premia, timing shifts and level drift."""
    a = AMENDMENTS["BTC_A3"]
    ref = reference.loc[reference["volume"] >= a["cross_min_volume_btc"], "close"]
    common = primary.index.intersection(ref.index)
    if len(common) < 60:
        raise DataUnavailable(f"{label} : recouvrement insuffisant.")
    p, r = primary.loc[common], ref.loc[common]
    gap = (p / r - 1) * 1e4
    returns = pd.DataFrame({"p": p.pct_change(), "r": r.pct_change()})
    shifted = {lag: float(pd.concat([returns["p"], returns["r"].shift(lag)], axis=1).dropna().corr().iloc[0, 1])
               for lag in (-1, 0, 1)}
    month = gap.groupby(gap.index.to_period("M")).mean().abs()
    checks = [within(f"{label} : écart médian absolu (pb)", float(gap.abs().median()), high=a["cross_median_abs_bp"]),
              within(f"{label} : écart 99e centile (pb)", float(gap.abs().quantile(.99)), high=a["cross_p99_abs_bp"]),
              within(f"{label} : écart maximal (pb)", float(gap.abs().max()), high=a["cross_max_abs_bp"]),
              within(f"{label} : |écart moyen mensuel| max (pb)", float(month.max()), high=a["cross_month_mean_abs_bp"]),
              within(f"{label} : corrélation quotidienne même jour UTC", shifted[0], a["daily_corr_min"]),
              Check(f"{label} : même jour mieux corrélé que J±1", round(shifted[0] - max(shifted[-1], shifted[1]), 6),
                    "> 0", shifted[0] > max(shifted[-1], shifted[1])),
              within(f"{label} : écart de CAGR sur le recouvrement", abs(_cagr(p) - _cagr(r)), high=a["cross_cagr_abs"])]
    return checks, {"first": str(common[0].date()), "last": str(common[-1].date()), "days": len(common),
                    "largest_gap_bp": {str(d.date()): round(float(gap.loc[d]), 1)
                                       for d in gap.abs().sort_values(ascending=False).index[:5]},
                    "worst_month": str(month.idxmax()), "worst_month_mean_abs_bp": float(month.max()),
                    "shifted_corr": shifted}


def splice_checks(usd: pd.DataFrame, eur: pd.DataFrame, usd_per_eur: pd.Series, splice: pd.Timestamp) -> list[Check]:
    """Around the splice, the native EUR book and the USD book / ECB must agree, and the switch
    must not create a jump of its own."""
    a = AMENDMENTS["BTC_A3"]
    span = pd.Timedelta(days=a["splice_window_days"])
    window = slice(splice - span, splice + span - pd.Timedelta(days=1))
    liquid_usd = usd.loc[window]
    liquid_usd = liquid_usd.loc[liquid_usd["volume"] >= a["min_volume_btc"], "close"]
    converted = usd_to_eur_by_utc_day(liquid_usd, usd_per_eur)["eur"]
    native = eur.loc[window]
    native = native.loc[native["volume"] >= a["min_volume_btc"], "close"]
    gap = level_gap_bp(native, converted).abs()
    previous = splice - pd.Timedelta(days=1)
    jump = ((eur.loc[splice, "close"] / converted.loc[previous]) - (converted.loc[splice] / converted.loc[previous])) * 1e4
    return [within("Raccord : écart médian EUR natif vs USD/BCE ±30 jours (pb)", float(gap.median()),
                   high=a["splice_median_abs_bp"]),
            within("Raccord : saut propre au changement de carnet (|pb|)", abs(float(jump)), high=a["splice_jump_bp"])]


# ---------------------------------------------------------------- amendment A3b: exchange consensus
def exchange_eur_series(eur: pd.DataFrame | None, usd: pd.DataFrame | None, usd_per_eur: pd.Series) -> pd.DataFrame:
    """ONE EUR series per exchange and UTC day: its native EUR pair when liquid, otherwise its USD
    pair divided by the last ECB fixing published before the close. Never both on the same day."""
    floor = AMENDMENTS["BTC_A3"]["cross_min_volume_btc"]
    parts = []
    if eur is not None:
        native = eur.loc[eur["volume"] >= floor, "close"]
        parts.append(pd.DataFrame({"eur": native, "pair": "EUR"}))
    if usd is not None:
        liquid = usd.loc[usd["volume"] >= floor, "close"]
        converted = usd_to_eur_by_utc_day(liquid, usd_per_eur)["eur"]
        if parts:
            converted = converted.drop(parts[0].index, errors="ignore")
        parts.append(pd.DataFrame({"eur": converted, "pair": "USD/BCE"}))
    frame = pd.concat(parts).sort_index()
    _check_index(frame.index, "Plateforme")
    return frame


def duration_drift_check(gap_bp: pd.Series, label: str) -> tuple[Check, dict]:
    """Level drift between the first and last N observations of an overlap, tested against an
    economic allowance proportional to its length plus drift_z standard errors of sampling noise
    (AR(1) effective sample size). Replaces the annualized-CAGR gap, which explodes on short overlaps."""
    a = AMENDMENTS["BTC_A3B"]
    gap, n = gap_bp.dropna(), a["drift_window_obs"]
    if len(gap) < 2 * n:
        return Check(f"{label} : dérive de niveau (durée prise en compte)", float("nan"), f"≥ {2 * n} observations", False), {}
    drift = float(gap.iloc[-n:].mean() - gap.iloc[:n].mean())
    years = (gap.index[-1] - gap.index[0]).days / 365.25
    # Noise is measured around a fitted linear trend: estimated on the raw gap, a genuine drift
    # would inflate both the dispersion and the autocorrelation and hide itself (defect found by
    # the adversarial test after the A3b freeze; this correction only makes the test stricter).
    t = (gap.index - gap.index[0]).days.to_numpy(float)
    residual = gap - np.polyval(np.polyfit(t, gap.to_numpy(), 1), t)
    rho = float(np.clip(residual.autocorr(), 0.0, 0.99))
    effective = n * (1 - rho) / (1 + rho)
    se = float(residual.std() * np.sqrt(2 / effective))
    limit = a["drift_bp_per_year"] * years + a["drift_z"] * se
    return (Check(f"{label} : dérive de niveau |fin − début| (pb, durée prise en compte)", round(abs(drift), 6),
                  f"≤ {limit:.1f} ({a['drift_bp_per_year']:.0f} pb/an × {years:.2f} ans + {a['drift_z']:.0f} × {se:.1f})",
                  abs(drift) <= limit),
            {"drift_bp": drift, "years": years, "lag1": rho, "effective_n": effective, "se_bp": se, "limit_bp": limit})


def consensus_checks(primary: pd.Series, exchanges: dict[str, pd.Series], label: str = "Consensus"):
    """Primary versus the daily median of the exchanges trading that day (itself included) when at
    least three trade, otherwise versus the single other exchange. One witness per exchange."""
    a = AMENDMENTS["BTC_A3B"]
    frame = pd.DataFrame({"primary": primary, **exchanges}).loc[primary.index]
    count = frame.notna().sum(axis=1)
    median = frame.median(axis=1)
    single = frame.drop(columns="primary").bfill(axis=1).iloc[:, 0]
    reference = median.where(count >= a["consensus_min_exchanges"], single.where(count == 2))
    deviation = ((frame["primary"] / reference - 1) * 1e4).dropna()
    month = deviation.groupby(deviation.index.to_period("M")).mean().abs()
    checks = [within(f"{label} : écart médian absolu (pb)", float(deviation.abs().median()), high=a["median_abs_bp"]),
              within(f"{label} : écart 99e centile (pb)", float(deviation.abs().quantile(.99)), high=a["p99_abs_bp"]),
              within(f"{label} : écart maximal (pb)", float(deviation.abs().max()), high=a["max_abs_bp"]),
              within(f"{label} : |écart moyen mensuel| max (pb)", float(month.max()), high=a["month_mean_abs_bp"])]
    drift_check, drift = duration_drift_check(deviation, label)
    checks.append(drift_check)
    stats = {"days_three_or_more": int((count >= 3).sum()), "days_two": int((count == 2).sum()),
             "days_primary_only": int((count == 1).sum()), "worst_month": str(month.idxmax()),
             "largest_deviation_bp": {str(d.date()): round(float(deviation.loc[d]), 1)
                                      for d in deviation.abs().sort_values(ascending=False).index[:5]},
             "drift": drift, "exchanges": {}}
    for name, series in exchanges.items():
        common = frame["primary"].dropna().index.intersection(series.dropna().index)
        p, r = frame.loc[common, "primary"], series.loc[common]
        returns = pd.DataFrame({"p": p.pct_change(), "r": r.pct_change()})
        shifted = {lag: float(pd.concat([returns["p"], returns["r"].shift(lag)], axis=1).dropna().corr().iloc[0, 1])
                   for lag in (-1, 0, 1)}
        pair_drift_check, pair_drift = duration_drift_check((p / r - 1) * 1e4, f"Bitstamp vs {name}")
        checks += [within(f"Bitstamp vs {name} : corrélation quotidienne même jour UTC", shifted[0], a["daily_corr_min"]),
                   Check(f"Bitstamp vs {name} : même jour mieux corrélé que J±1",
                         round(shifted[0] - max(shifted[-1], shifted[1]), 6), "> 0",
                         shifted[0] > max(shifted[-1], shifted[1])),
                   pair_drift_check]
        stats["exchanges"][name] = {"first": str(common[0].date()), "last": str(common[-1].date()),
                                    "days": len(common), "shifted_corr": shifted, "drift": pair_drift}
    return checks, stats


def monthly_outliers(primary: pd.Series, exchanges: dict[str, pd.Series], threshold: float | None = None) -> dict:
    """Diagnostic: months (three exchanges trading) where one exchange departs from BOTH others by
    more than the threshold while those two agree. Never an admission criterion by itself."""
    threshold = AMENDMENTS["BTC_A3B"]["outlier_month_bp"] if threshold is None else threshold
    frame = pd.DataFrame({"Bitstamp": primary, **exchanges}).dropna()
    names, out = list(frame.columns), {}
    for period, block in frame.groupby(frame.index.to_period("M")):
        gaps = {(x, y): float(((block[x] / block[y] - 1) * 1e4).mean()) for i, x in enumerate(names) for y in names[i + 1:]}
        if max(abs(v) for v in gaps.values()) <= threshold:
            continue
        outlier = None
        for x in names:
            others = [y for y in names if y != x]
            far = all(abs(gaps.get((x, y), -gaps.get((y, x), 0))) > threshold for y in others)
            close = abs(gaps.get(tuple(others), -gaps.get(tuple(reversed(others)), 0))) <= threshold
            if far and close:
                outlier = x
        out[str(period)] = {"outlier": outlier, "mean_gap_bp": {f"{x}/{y}": round(v, 1) for (x, y), v in gaps.items()},
                            "days": len(block)}
    return out


# ---------------------------------------------------------------- Phase C: Berkshire Hathaway B (A6)
BRK_CONVERSION = 1500  # one A share converts into 1,500 B shares (since the 21/01/2010 B split)


def parse_nasdaq_history(text: str) -> pd.Series:
    """Nasdaq.com historical JSON (rows: date MM/DD/YYYY, close '$123.45') -> closes; scanned first."""
    assert_text_before_cutoff(text, "Nasdaq.com")
    rows = (json.loads(text).get("data") or {}).get("tradesTable", {}).get("rows") or []
    if not rows:
        raise DataUnavailable("Nasdaq.com : aucune observation.")
    series = pd.Series([float(r["close"].replace("$", "").replace(",", "")) for r in rows],
                       index=pd.DatetimeIndex(pd.to_datetime([r["date"] for r in rows], format="%m/%d/%Y"), name="Date"),
                       name="close").sort_index()
    if series.index.has_duplicates:
        raise DataUnavailable("Nasdaq.com : dates dupliquées.")
    _check_index(series.index, "Nasdaq.com")
    _check_values(series, "Nasdaq.com")
    return series


def validate_brk(b: pd.DataFrame, a: pd.DataFrame, vendor: pd.Series | None) -> tuple[list[Check], dict]:
    """BRK-B admission: NYSE calendar, no distribution or split, close = adjusted close, A/B share-class
    identity and a second vendor's closes. Tolerances BRK_A6 were frozen before any request."""
    t = AMENDMENTS["BRK_A6"]
    for frame, label in ((b, "BRK-B"), (a, "BRK-A")):
        _check_index(frame.index, label)
        _check_values(frame["Close"].astype(float), label)
    nyse = nyse_sessions(b.index[0], HARD_CUTOFF)
    close_b, close_a = b["Close"].astype(float), a["Close"].astype(float)
    adj_gap = float((b["Adj Close"].astype(float) / close_b - 1).abs().max())
    ratio = (close_a.reindex(close_b.index) / (BRK_CONVERSION * close_b) - 1) * 1e4
    corr = float(pd.concat([close_a.pct_change(), close_b.pct_change()], axis=1).dropna().corr().iloc[0, 1])
    checks = [Check("Calendrier BRK-B = séances NYSE (règles)", float(len(b.index.symmetric_difference(nyse))), "0 écart",
                    b.index.equals(nyse)),
              Check("Calendrier BRK-A = calendrier BRK-B", float(len(a.index.symmetric_difference(b.index))), "0 écart",
                    a.index.equals(b.index)),
              within("Distributions déclarées dans la fenêtre", float((b["Dividends"] != 0).sum()), high=t["dividends_max"]),
              within("Divisions d'actions déclarées dans la fenêtre", float((b["Stock Splits"] != 0).sum()), high=t["splits_max"]),
              within("Clôture ajustée = clôture (écart relatif max)", adj_gap, high=t["adjclose_max_rel_gap"]),
              within("Classe A / (1 500 × classe B) : écart médian absolu (pb)", float(ratio.abs().median()),
                     high=t["ab_ratio_median_abs_bp"]),
              within("Classe A / (1 500 × classe B) : écart maximal (pb)", float(ratio.abs().max()), high=t["ab_ratio_max_abs_bp"]),
              within("Classes A et B : corrélation des rendements quotidiens", corr, t["ab_daily_corr_min"])]
    stats = {"rows": len(b), "first": str(b.index[0].date()), "last": str(b.index[-1].date()),
             "ab_ratio_bp": {"median": float(ratio.median()), "min": float(ratio.min()), "max": float(ratio.max())}}
    if vendor is not None:
        common = vendor.index.intersection(close_b.index)
        gap = ((close_b.loc[common] / vendor.loc[common] - 1) * 1e4).abs()
        checks += [within("Second fournisseur : part de ses dates présentes chez Yahoo", len(common) / len(vendor),
                          t["vendor_min_common_share"]),
                   within("Second fournisseur : écart médian absolu (pb)", float(gap.median()), high=t["vendor_median_abs_bp"]),
                   within("Second fournisseur : écart 99e centile (pb)", float(gap.quantile(.99)), high=t["vendor_p99_abs_bp"]),
                   within("Second fournisseur : écart maximal (pb)", float(gap.max()), high=t["vendor_max_abs_bp"])]
        stats["vendor"] = {"first": str(vendor.index[0].date()), "last": str(vendor.index[-1].date()),
                           "rows": len(vendor), "common": len(common),
                           "largest_gap_bp": {str(d.date()): round(float(gap.loc[d]), 3)
                                              for d in gap.sort_values(ascending=False).index[:5]}}
    return checks, stats


def brk_10k_checks(b: pd.DataFrame, a: pd.DataFrame, ranges: dict) -> tuple[list[Check], dict]:
    """Yahoo daily data against the quarterly high/low sales prices of Berkshire's 10-K (NYSE
    Composite). A sanity check of levels and adjustments, not a validation of each daily close."""
    t = AMENDMENTS["BRK_A6_BIS"]
    outside, extremes, rows = 0, [], {}
    for quarter, classes in ranges.items():
        period = pd.Period(quarter, freq="Q")
        for cls, frame in (("B", b), ("A", a)):
            block = frame.loc[period.start_time:period.end_time.normalize()]
            if block.empty:
                continue
            high, low = classes[cls]
            close = block["Close"].astype(float)
            bad = int(((close > high * (1 + t["range_margin"])) | (close < low * (1 - t["range_margin"]))).sum())
            outside += bad
            complete = block.index[0] <= period.start_time + pd.Timedelta(days=6)
            row = {"closes": len(close), "outside": bad, "complete_quarter": bool(complete)}
            if complete:
                gaps = (float(block["High"].max()) / high - 1, float(block["Low"].min()) / low - 1)
                extremes += [abs(g) for g in gaps]
                row["high_gap"], row["low_gap"] = gaps
            rows[f"{quarter} {cls}"] = row
    checks = [Check("10-K 2015 : clôtures Yahoo hors des fourchettes trimestrielles officielles", float(outside), "= 0",
                    outside == 0),
              within("10-K 2015 : extrêmes trimestriels Yahoo vs officiels (écart relatif max, trimestres complets)",
                     max(extremes) if extremes else float("nan"), high=t["range_extreme_rel"])]
    return checks, rows


def validate_brk_bis(b: pd.DataFrame, a: pd.DataFrame, vendor: pd.Series, ranges: dict):
    """A6-bis (post-hoc, owner-approved). Returns (binding checks, diagnostics, original A6 checks).
    Prices are never modified or selected."""
    t = AMENDMENTS["BRK_A6_BIS"]
    original, stats = validate_brk(b, a, vendor)
    keep = ("Calendrier", "Distributions", "Divisions", "Clôture ajustée", "Second fournisseur")
    binding = [c for c in original if c.name.startswith(keep)]
    close_a, close_b = a["Close"].astype(float), b["Close"].astype(float)
    gap = (close_a / (BRK_CONVERSION * close_b) - 1) * 1e4
    early = gap.loc[:vendor.index[0] - pd.Timedelta(days=1)]
    ea, eb = close_a.loc[early.index], close_b.loc[early.index]
    cumulative = float(abs(np.log(ea.iloc[-1] / ea.iloc[0]) - np.log(eb.iloc[-1] / eb.iloc[0])) * 1e4)
    binding += [within(f"Avant Nasdaq ({early.index[0].date()} → {early.index[-1].date()}) : A/(1 500 × B) écart médian absolu (pb)",
                       float(early.abs().median()), high=t["ab_median_abs_bp"]),
                within("Avant Nasdaq : borne basse de conversion, A/(1 500 × B) − 1 minimal (pb)", float(early.min()),
                       t["ab_lower_bound_bp"]),
                within("Avant Nasdaq : divergence cumulée A/B (|Δ log|, pb)", cumulative, high=t["ab_cumulative_abs_bp"])]
    tenk, tenk_rows = brk_10k_checks(b, a, ranges)
    binding += tenk

    def longest(flags):
        runs = (flags != flags.shift()).cumsum()[flags]
        return int(runs.value_counts().max()) if len(runs) else 0

    corr = lambda x, y, k=1: float(pd.concat([x.pct_change(k), y.pct_change(k)], axis=1).dropna().iloc[::k].corr().iloc[0, 1])
    diagnostics = {**stats, "ten_k": tenk_rows,
                   "ab_full_window_bp": {"median_abs": float(gap.abs().median()), "min": float(gap.min()), "max": float(gap.max())},
                   "ab_before_nasdaq_bp": {"median_abs": float(early.abs().median()), "min": float(early.min()),
                                           "max": float(early.max()), "cumulative_divergence": cumulative},
                   "ab_daily_corr": {"full": corr(close_a, close_b), "before_nasdaq": corr(ea, eb)},
                   "ab_5day_corr": {"full": corr(close_a, close_b, 5), "before_nasdaq": corr(ea, eb, 5)},
                   "persistent_discount": {"longest_run_below_minus_50bp_full": longest(gap < -50),
                                           "longest_run_below_minus_50bp_before_nasdaq": longest(early < -50),
                                           "min_rolling_20d_mean_bp_full": float(gap.rolling(20).mean().min())},
                   "persistent_premium_2023": {"median_bp": float(gap.loc["2023"].median()),
                                               "longest_run_above_100bp": longest(gap > 100)}}
    return binding, diagnostics, original
