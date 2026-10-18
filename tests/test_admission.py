"""V2.2 data admission: calendars, clocks, causal as-of, imports. Synthetic values only.

Session counts and holidays are calendar facts, not market observations. No real price is used
and no date after the 2023-12-29 cutoff is ever read as data (only refused).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from portfolio_lab.v2 import admission as AD, custom as C
from portfolio_lab.v2.guard import CutoffViolation

T = pd.Timestamp
SESSIONS = AD.euronext_sessions()
NYSE = AD.nyse_sessions(T("2014-09-01"))


def synthetic(index, start=100.0, step=0.001):
    return pd.Series(start * np.exp(step * np.arange(len(index))), index=index)


def test_rule_calendars_counts_and_holidays():
    assert len(SESSIONS) == 2368 and len(AD.nyse_sessions()) == 2328
    assert T("2015-12-31") not in SESSIONS  # no Paris market data in any source (EURONEXT_NO_DATA_DAYS)
    assert SESSIONS[0] == T("2014-10-01") and SESSIONS[-1] == T("2023-12-29")
    paris_closed = ["2018-05-01", "2019-04-19", "2019-04-22", "2019-12-25", "2019-12-26", "2020-01-01"]
    us_closed = ["2017-01-02", "2018-12-05", "2019-04-19", "2019-11-28", "2021-12-24", "2022-06-20",
                 "2023-01-02", "2020-07-03"]
    assert not SESSIONS.isin(pd.to_datetime(paris_closed)).any()
    assert not NYSE.isin(pd.to_datetime(us_closed)).any()
    assert {T("2018-05-01"), T("2019-04-22"), T("2021-12-31")} <= set(NYSE)
    assert {T("2017-01-02"), T("2019-11-28"), T("2014-12-31"), T("2019-12-24")} <= set(SESSIONS)
    with pytest.raises(CutoffViolation):
        AD.euronext_sessions(end="2024-01-02")


def test_clocks_are_causal_on_every_session_including_dst_mismatch_weeks():
    nyse = AD.nyse_sessions(T("2014-09-01"))
    for day in SESSIONS:
        snap = AD.snapshot_instant(day)
        previous_us = nyse[nyse < day][-1]
        assert AD.nyse_close_instant(previous_us) < snap < AD.nyse_close_instant(day)
        assert AD.utc_day_close_instant(day - pd.Timedelta(days=1)) <= snap < AD.utc_day_close_instant(day)
        assert (AD.ecb_publication_instant(day) < snap) != AD.is_half_day(day)
    # US daylight time starts 12/03/2023, Europe 26/03/2023; Europe ends 29/10, US 05/11/2023.
    assert AD.snapshot_instant("2023-03-13") == T("2023-03-13 16:40", tz="UTC")
    assert AD.nyse_close_instant("2023-03-13") == T("2023-03-13 20:00", tz="UTC")
    assert AD.snapshot_instant("2023-03-27") == T("2023-03-27 15:40", tz="UTC")
    assert AD.snapshot_instant("2023-10-30") == T("2023-10-30 16:40", tz="UTC")
    assert AD.nyse_close_instant("2023-10-30") == T("2023-10-30 20:00", tz="UTC")
    assert AD.nyse_close_instant("2023-11-06") == T("2023-11-06 21:00", tz="UTC")
    assert AD.snapshot_instant("2019-12-24") == T("2019-12-24 13:10", tz="UTC")


def test_future_us_close_is_never_visible_at_the_paris_snapshot():
    us = synthetic(NYSE)
    poisoned = us.copy()
    poisoned.loc[T("2020-03-16")] = 1e9  # becomes known at 20:00 UTC, after the Paris snapshot
    clean, dirty = (AD.asof(s, "nyse", SESSIONS, "US") for s in (us, poisoned))
    assert dirty.loc["2020-03-16", "value"] == clean.loc["2020-03-16", "value"]
    assert dirty.loc["2020-03-16", "source_date"] == T("2020-03-13")
    assert dirty.loc["2020-03-17", "value"] == 1e9
    assert (dirty["available_utc"] <= dirty["snapshot_utc"]).all()


def test_partial_market_days_and_month_start_sessions():
    us = AD.asof(synthetic(NYSE), "nyse", SESSIONS, "US")
    # US holiday, Paris open: Thanksgiving uses Wednesday's close on Thursday and Friday.
    assert us.loc["2019-11-28", "source_date"] == us.loc["2019-11-29", "source_date"] == T("2019-11-27")
    # Paris holiday, US open: the 01/05/2018 US close reaches Paris at the next session.
    assert T("2018-05-01") not in us.index and us.loc["2018-05-02", "source_date"] == T("2018-05-01")
    # First sessions of a month, where the engine rebalances.
    firsts = SESSIONS.to_series().groupby(SESSIONS.to_period("M")).first()
    assert firsts.loc[pd.Period("2018-05")] == T("2018-05-02")
    assert firsts.loc[pd.Period("2017-01")] == T("2017-01-02")
    # NYSE closed on 02/01/2017 (New Year observed): Friday 30/12/2016 serves Monday and Tuesday.
    assert us.loc["2017-01-02", "source_date"] == T("2016-12-30") and us.loc["2017-01-02", "age_days"] == 3
    assert us.loc["2017-01-03", "source_date"] == T("2016-12-30") and us.loc["2017-01-03", "age_days"] == 4
    assert us["age_days"].between(1, AD.MAX_AGE_DAYS["nyse"]).all()


def test_half_day_uses_previous_ecb_fixing_and_btc_previous_utc_day():
    ecb_days = pd.bdate_range("2014-09-01", "2023-12-29")
    fx = AD.asof(synthetic(ecb_days, 1.1, 0.0001), "ecb", SESSIONS, "FX")
    assert fx.loc["2019-12-24", "source_date"] == T("2019-12-23")
    assert fx.loc["2018-12-31", "source_date"] == T("2018-12-28") and fx.loc["2018-12-31", "age_days"] == 3
    assert fx.loc["2019-12-27", "source_date"] == T("2019-12-27")
    btc = AD.asof(synthetic(pd.date_range("2014-09-17", "2023-12-29")), "utc_day", SESSIONS, "BTC")
    assert (btc["age_days"] == 1).all()


def test_gaps_fail_closed_unless_explicitly_listed():
    us = synthetic(NYSE).drop(pd.bdate_range("2020-06-01", "2020-06-12"))
    with pytest.raises(C.DataUnavailable, match="trop ancienne"):
        AD.asof(us, "nyse", SESSIONS, "US")
    paris = synthetic(SESSIONS)
    with pytest.raises(C.DataUnavailable, match="sans observation"):
        AD.asof(paris.drop(T("2016-06-24")), "same_session", SESSIONS, "EU")
    listed = AD.asof(paris.drop(T("2016-06-24")), "same_session", SESSIONS, "EU", allowed_missing=[T("2016-06-24")])
    assert listed.loc["2016-06-24", "source_date"] == T("2016-06-23")
    with pytest.raises(C.DataUnavailable, match="exception inutile"):
        AD.asof(paris, "same_session", SESSIONS, "EU", allowed_missing=[T("2016-06-24")])
    extra = pd.concat([paris, pd.Series([1.0], index=[T("2019-12-25")])]).sort_index()
    with pytest.raises(C.DataUnavailable, match="hors séance"):
        AD.asof(extra, "same_session", SESSIONS, "EU")
    with pytest.raises(ValueError):
        AD.asof(us, "nyse", SESSIONS, "US", allowed_missing=[T("2016-06-24")])
    bad = paris.copy()
    bad.iloc[10] = np.nan
    with pytest.raises(C.DataUnavailable, match="aucun remplissage"):
        AD.asof(bad, "same_session", SESSIONS, "EU")


def test_declared_vendor_placeholder_must_repeat_previous_value():
    idx = pd.to_datetime(["2019-12-24", "2019-12-25", "2019-12-27"])
    assert list(AD.drop_placeholders(pd.Series([10.0, 10.0, 11.0], index=idx), "WORLD").index) == [idx[0], idx[2]]
    with pytest.raises(C.DataUnavailable, match="répétition"):
        AD.drop_placeholders(pd.Series([10.0, 10.5, 11.0], index=idx), "WORLD")


def test_explicit_total_return_and_eur_conversion_by_hand():
    idx = pd.to_datetime(["2019-06-03", "2019-06-04", "2019-06-05"])
    raw = pd.DataFrame({"Close": [100.0, 102.0, 101.0], "Dividends": [0.0, 0.0, 1.0]}, index=idx)
    assert AD.explicit_total_return(raw, "X").tolist() == pytest.approx([1.0, 1.02, 1.02])
    with pytest.raises(C.DataUnavailable, match="division"):
        AD.explicit_total_return(raw.assign(**{"Stock Splits": [0, 2.0, 0]}), "X")
    with pytest.raises(C.DataUnavailable):
        AD.explicit_total_return(raw.assign(Dividends=[0, -1.0, 0]), "X")
    sessions = pd.to_datetime(["2019-06-04", "2019-06-05", "2019-06-06"])
    usd = pd.Series([100.0, 110.0, 121.0], index=idx)  # US closes of 03, 04, 05 June
    fx = pd.Series([1.25, 1.10, 1.21], index=pd.to_datetime(["2019-06-04", "2019-06-05", "2019-06-06"]))
    level, detail = AD.eur_level(usd, fx, sessions, "X")
    # EUR = previous US close / same-day ECB fixing: 100/1.25, 110/1.10, 121/1.21 -> 80, 100, 100.
    assert level.tolist() == pytest.approx([100, 125, 125])
    assert detail["price_source_date"].tolist() == list(idx)


def test_text_date_scan_formats_and_decimal_false_positive():
    assert AD.scan_dates("2023-12-29;29/12/2023;20231229")[1] == T("2023-12-29")
    for later in ("2024-01-02", "02/01/2024", "20240102", "1704153600"):
        with pytest.raises(CutoffViolation):
            AD.assert_text_before_cutoff(f"x,{later},1", "fixture")
    assert AD.scan_dates("level 1234.2075123456")[1] is None


def euronext_text(isin, levels, extra_rows=()):
    rows = [f"{d:%d/%m/%Y};{v};{v};{v};{v};{v};0;0;0" for d, v in levels.items()] + list(extra_rows)
    return "﻿\"Historical Data\"\n\"From 2014-10-01 to 2023-12-29\"\n" + isin + \
        "\nDate;Open;High;Low;Last;Close;\"Number of Shares\";\"Number of Trades\";Turnover\n" + "\n".join(rows)


def test_cac40_import_requires_total_return_identifier_and_independent_reference():
    price = synthetic(SESSIONS, 4000, 0.0002)
    tr = price * np.exp(0.0001 * np.arange(len(price)))  # dividends: never below price return
    isin, parsed = AD.parse_euronext_export(euronext_text("QS0011131834", tr))
    assert isin == "QS0011131834" and parsed.index.equals(SESSIONS)
    levels, checks, validated = AD.validate_cac40(isin, parsed)
    assert levels.index.equals(SESSIONS) and not validated
    _, checks, validated = AD.validate_cac40(isin, parsed, ("FR0003500008", price))
    assert validated and all(c.passed for c in checks)
    nr = price * np.exp(0.00008 * np.arange(len(price)))
    assert AD.validate_cac40("QS0011131826", nr, ("QS0011131834", tr))[2]
    slow = price * np.exp(-0.0005 * np.arange(len(price)))  # 5 pb/session below the reference
    assert not AD.validate_cac40("QS0011131834", slow, ("QS0011131826", tr))[2]  # GR below NR
    broken = tr.copy()
    broken.iloc[500:] *= 0.999  # one session 10 pb below the price index
    assert not AD.validate_cac40(isin, broken, ("FR0003500008", price))[2]
    with pytest.raises(C.DataUnavailable, match="prix"):
        AD.validate_cac40("FR0003500008", price)
    with pytest.raises(C.DataUnavailable, match="non reconnu"):
        AD.validate_cac40("FR0007052782", tr)
    with pytest.raises(C.DataUnavailable, match="sans observation"):
        AD.validate_cac40(isin, tr.drop(T("2018-04-03")))
    with pytest.raises(C.DataUnavailable, match="hors séances"):
        AD.validate_cac40(isin, pd.concat([tr, pd.Series([1.0], index=[T("2018-05-01")])]).sort_index())


def test_cac40_export_with_post_cutoff_row_is_refused_before_values_are_parsed():
    tr = synthetic(SESSIONS[-5:], 4000)
    # The malformed row would raise a parsing error if values were read before the date scan.
    text = euronext_text("QS0011131834", tr, ["02/01/2024;not-a-number"])
    with pytest.raises(CutoffViolation):
        AD.parse_euronext_export(text)


def test_external_parsers_check_identity():
    with pytest.raises(C.DataUnavailable):
        AD.parse_ecb("KEY,TIME_PERIOD,OBS_VALUE\nEXR.D.GBP.EUR.SP00.A,2019-01-02,0.9\n")
    ecb = AD.parse_ecb("KEY,TIME_PERIOD,OBS_VALUE\nEXR.D.USD.EUR.SP00.A,2019-01-02,1.14\n")
    assert ecb.iloc[0] == 1.14
    msci = '{"msci_index_code":"990100","index_variant_type":"NETR","ISO_currency_symbol":"EUR",' \
           '"indexes":{"INDEX_LEVELS":[{"level_eod":10.5,"calc_date":20190102}]}}'
    assert AD.parse_msci(msci, "990100", "EUR").iloc[0] == 10.5
    with pytest.raises(C.DataUnavailable):
        AD.parse_msci(msci.replace("NETR", "PRICE"), "990100", "EUR")
    candle = '{"data":{"pair":"BTC/EUR","ohlc":[{"timestamp":"1546311600","close":"3000"}]}}'
    with pytest.raises(C.DataUnavailable, match="00:00 UTC"):
        AD.parse_bitstamp([candle], "BTC/EUR")


def test_predeclared_tolerances_are_pinned():
    # Any change must be an explicit, reviewed protocol amendment (docs/V2_2_DATA_ADMISSION.md).
    assert AD.TOLERANCES["FX"] == {"median_abs_bp": 15.0, "p99_abs_bp": 80.0, "max_abs_bp": 300.0}
    assert AD.TOLERANCES["SP500"]["daily_corr_min"] == 0.999 and AD.TOLERANCES["SP500"]["p99_daily_abs_bp"] == 20.0
    assert AD.TOLERANCES["BTC"]["eur_p99_abs_bp"] == 300.0 and AD.TOLERANCES["BTC"]["extreme_gap_pp"] == 5.0
    assert AD.TOLERANCES["WORLD"]["migration_abs_bp"] == 100.0


def test_catalog_admission_state_is_consistent():
    catalog = C.load_catalog()
    validated = {a for a, item in catalog.items() if item["status"] == "validated"}
    assert validated == {"EM", "SP500", "WORLD", "CAC40", "GOLD", "BTC"}  # Phase A complete (V2.2)
    required = ("sha256", "path", "calendar", "clock", "dividends", "source", "independent_check",
                "calendar_path", "calendar_sha256")
    for asset in validated:
        assert all(catalog[asset].get(k) for k in required)
        assert (catalog[asset]["calendar"], catalog[asset]["clock"]) == (AD.CALENDAR_ID, AD.CLOCK_ID)
        assert catalog[asset]["research_alignment"] == AD.RESEARCH_ALIGNMENT


@pytest.mark.skipif(not (C.ROOT / "data/v2_1/levels/GOLD.csv").exists(), reason="données locales non préparées")
def test_validated_levels_load_through_the_guarded_interface():
    # Loading only: hash, cutoff and common-calendar gates. No portfolio is simulated here.
    weights = {"EM": .25, "SP500": .25, "WORLD": .25, "GOLD": .25}
    panel = C.load_validated_panel(C.PortfolioSpec("Contrôle de chargement", weights))
    assert panel.prices.index.equals(SESSIONS) and panel.sessions.equals(SESSIONS)
    assert set(panel.prices.columns) == set(weights) and not panel.synthetic


def test_ambiguous_slash_and_text_dates_are_read_both_ways():
    for later in ("12/31/2024", "Dec 31, 2024", "31.12.2024", "2024.01.02"):
        with pytest.raises(CutoffViolation):
            AD.assert_text_before_cutoff(f'"{later}","7,543.18"', "fixture")
    AD.assert_text_before_cutoff('"12/29/2023","7,543.18"\n"10/01/2014","4,400.00"', "fixture")


def investing_text(levels, date_order="mdy", decimal=".", extra_rows=()):
    fmt = "%m/%d/%Y" if date_order == "mdy" else "%d/%m/%Y"

    def number(v):
        s = f"{v:,.2f}"
        return s if decimal == "." else s.replace(",", " ").replace(".", ",")
    rows = [f'"{d.strftime(fmt)}","{number(v)}","{number(v)}","{number(v)}","{number(v)}","","0.00%"'
            for d, v in levels.iloc[::-1].items()] + list(extra_rows)  # newest first, as exported
    return '"Date","Price","Open","High","Low","Vol.","Change %"\n' + "\n".join(rows)


def test_investing_export_parser_explicit_conventions():
    levels = synthetic(SESSIONS, 7000, 0.0002).round(2)
    parsed = AD.parse_investing_export(investing_text(levels), "mdy", ".")
    pd.testing.assert_series_equal(parsed, levels.rename("level").rename_axis("Date"), check_freq=False)
    french = investing_text(levels, "dmy", ",").replace('"Price"', '"Dernier"')
    assert AD.parse_investing_export(french, "dmy", ",").equals(parsed)
    with pytest.raises((ValueError, C.DataUnavailable)):
        AD.parse_investing_export(investing_text(levels), "dmy", ".")
    with pytest.raises(ValueError):
        AD.parse_investing_export(investing_text(levels), "ymd", ".")
    with pytest.raises(CutoffViolation):
        AD.parse_investing_export(investing_text(levels, extra_rows=['"01/02/2024","not-a-number"']), "mdy", ".")


def etf_fixture(adjusted=False):
    """Unadjusted ETF closes: price-index return + 2.5 %/an accrual, minus the yearly distribution."""
    px = synthetic(SESSIONS, 4000, 0.0002) * (1 + 0.01 * np.sin(np.arange(len(SESSIONS)) / 7))
    exdates = SESSIONS.to_series().groupby(SESSIONS.to_period("M")).first()
    exdates = pd.DatetimeIndex([d for d in exdates if d.month == 7])
    accrual = 0.025 / 252
    values, amounts = [50.0], {}
    for i in range(1, len(SESSIONS)):
        price = values[-1] * (px.iloc[i] / px.iloc[i - 1] + accrual)
        if SESSIONS[i] in exdates:
            amounts[SESSIONS[i]] = round(0.025 * values[-1], 2)
            if not adjusted:
                price -= amounts[SESSIONS[i]]
        values.append(price)
    return pd.Series(values, index=SESSIONS), pd.Series(amounts), px


NO_EVENTS = pd.DataFrame({"ratio": pd.Series(dtype=float), "description": pd.Series(dtype=str)},
                         index=pd.DatetimeIndex([], name="Date"))


def nav_anchors(unadjusted):
    """Two issuer-style NAV anchors per year (first sessions of January and July), 0.1 % from the close."""
    firsts = SESSIONS.to_series().groupby(SESSIONS.to_period("M")).first()
    days = pd.DatetimeIndex([d for d in firsts if d.month in (1, 7) and d.year >= 2015])
    return unadjusted.loc[days] * 1.001


def etf_validate(etf, ledger, px, check=None, **overrides):
    inputs = dict(cross_check=ledger.copy() if check is None else check, reference=px,
                  nav_anchors=nav_anchors(etf_fixture()[0]), distributions_per_year=1, corporate_actions=NO_EVENTS)
    inputs.update(overrides)
    return AD.validate_cac40_etf(etf, ledger, **inputs)


def failed(result):
    return [c.name for c in result[1] if not c.passed]


def test_cac40_etf_route_reconstructs_total_return_without_double_counting():
    etf, ledger, px = etf_fixture()
    levels, checks, validated = etf_validate(etf, ledger, px)
    assert validated and all(c.passed for c in checks), [c for c in checks if not c.passed]
    assert levels.index.equals(SESSIONS) and levels.iloc[0] == 100
    # TR grows like the price index plus the accrual: no distribution lost or counted twice.
    expected = (px / px.shift(1) + 0.025 / 252).fillna(1).cumprod() * 100
    assert levels.iloc[-1] == pytest.approx(expected.iloc[-1], rel=1e-3)
    for missing in ("cross_check", "reference", "nav_anchors", "distributions_per_year", "corporate_actions"):
        assert not etf_validate(etf, ledger, px, **{missing: None})[2], missing
    shifted = ledger.copy()
    shifted.iloc[3] += 0.01
    assert not etf_validate(etf, ledger, px, check=shifted)[2]                  # amounts disagree
    assert not etf_validate(etf, ledger, px, check=ledger.drop(ledger.index[2]))[2]
    with pytest.raises(C.DataUnavailable, match="hors séance"):
        etf_validate(etf, pd.concat([ledger, pd.Series([1.0], index=[T("2018-05-01")])]).sort_index(), px)


def test_a4_detects_adjusted_prices_through_nav_anchors_and_events():
    etf, ledger, px = etf_fixture()
    adjusted, ledger_a, _ = etf_fixture(adjusted=True)
    names = failed(etf_validate(adjusted, ledger_a, px))
    assert any("non ajustés" in n for n in names)                              # no ex-date drop
    assert "Ancrages VL : |clôture / VL − 1| max" in names                     # level far from issuer NAV
    assert any(n.startswith("Par ex-date") for n in names)


def test_a4_distribution_missing_from_both_ledgers_is_an_unexplained_drop():
    etf, ledger, px = etf_fixture()
    partial = ledger.drop(ledger.index[4])
    names = failed(etf_validate(etf, partial, px, check=partial.copy()))
    assert any(n.startswith("Hors ex-dates : baisse inexpliquée") for n in names)
    assert any(n.startswith("Exhaustivité") for n in names)
    assert any(n.startswith("Exhaustivité") for n in failed(etf_validate(etf, ledger, px, distributions_per_year=2)))
    sparse = nav_anchors(etf).iloc[::2]                                         # one anchor per year only
    assert "Ancrages VL : nombre minimal par année 2015–2023" in failed(etf_validate(etf, ledger, px, nav_anchors=sparse))


def test_a4_corporate_actions_continuity():
    etf, ledger, px = etf_fixture()
    merger = pd.DataFrame({"ratio": [1.0], "description": ["Fusion Lyxor → Amundi"]},
                          index=pd.DatetimeIndex([T("2022-03-01")], name="Date"))
    assert etf_validate(etf, ledger, px, corporate_actions=merger)[2]
    with pytest.raises(C.DataUnavailable, match="ratio"):
        etf_validate(etf, ledger, px, corporate_actions=merger.assign(ratio=2.0))
    split = etf.copy()
    split.loc["2022-03-01":] /= 2                                             # declared ratio 1, but a jump
    halved = ledger.where(ledger.index < "2022-03-01", (ledger / 2).round(2))
    names = failed(etf_validate(split, halved, px, nav_anchors=nav_anchors(split), corporate_actions=merger))
    assert any(n.startswith("Opération du 2022-03-01") for n in names)


def test_corporate_action_and_nav_parsers():
    events = AD.parse_corporate_actions("date,ratio,description\n2022-03-01,1,Fusion\n", "x")
    assert events.loc["2022-03-01", "ratio"] == 1.0
    assert AD.parse_corporate_actions("date,ratio,description\n", "x").empty
    with pytest.raises(CutoffViolation):
        AD.parse_corporate_actions("date,ratio,description\n2024-03-01,1,x\n", "x")
    anchors = AD.parse_nav_anchors("date,nav_eur\n2019-12-31,55.1\n2019-06-28,52.3\n", "x")
    assert anchors.index[0] == T("2019-06-28")
    with pytest.raises(C.DataUnavailable):
        AD.parse_nav_anchors("date,nav\n2019-12-31,55.1\n", "x")



def test_distribution_ledger_parser():
    ledger = AD.parse_distributions("ex_date,amount_eur,source\n2019-07-03,1.12,issuer\n2018-07-04,1.05,issuer\n", "x")
    assert ledger.index[0] == T("2018-07-04") and ledger.iloc[1] == 1.12
    with pytest.raises(CutoffViolation):
        AD.parse_distributions("ex_date,amount_eur\n2024-07-03,1.2\n", "x")
    with pytest.raises(C.DataUnavailable):
        AD.parse_distributions("date,amount\n2019-07-03,1.2\n", "x")
    with pytest.raises(C.DataUnavailable):
        AD.parse_distributions("ex_date,amount_eur\n2019-07-03,-1.2\n", "x")


def test_etf_tolerances_are_pinned():
    assert AD.TOLERANCES["CAC40_ETF"] == {"ledger_amount_tol_eur": 0.005, "exdate_residual_bp": 100.0,
                                          "exdate_mean_residual_bp": 50.0, "daily_gap_bp_max": 300.0,
                                          "tr_minus_price": (0.003, 0.05)}


def test_amendments_are_pinned_and_original_tolerances_unchanged():
    assert AD.AMENDMENTS["FX_A1"] == {"median_abs_bp": 15.0, "max_abs_bp": 300.0, "absorption_slope": (0.7, 1.3),
                                      "absorption_corr_min": 0.3, "lag1_abs_max": 0.2, "endpoint_abs_bp": 10.0,
                                      "mean_abs_bp": 3.0}
    assert AD.AMENDMENTS["SP500_A2"]["max_run_sessions"] == 3 and AD.AMENDMENTS["SP500_A2"]["rolling21_abs_bp"] == 20.0
    assert AD.AMENDMENTS["BTC_A3"]["cross_p99_abs_bp"] == 300.0 and AD.AMENDMENTS["BTC_A3"]["min_volume_btc"] == 1.0
    assert AD.AMENDMENTS["CAC40_ETF_A4"]["unexplained_drop_bp"] == -75.0
    assert AD.TOLERANCES["FX"]["p99_abs_bp"] == 80.0  # original failed thresholds preserved


def fx_fixture(persistent=0.0):
    rng = np.random.default_rng(7)
    days = pd.bdate_range("2015-01-01", "2019-12-31")
    early, later = rng.normal(0, 0.0015, len(days)), rng.normal(0, 0.004, len(days))
    # Move from 14:15 to 17:00 (seen by WM/R) then after 17:00; the next ECB fixing contains both.
    ecb = pd.Series(1.1 * np.exp(np.cumsum(np.r_[0, (early + later)[:-1]])), index=days)
    gap = pd.Series(early * 1e4, index=days)
    gap.loc["2017-01-01":] += persistent
    return gap, ecb


def test_a1_fx_timing_gap_passes_and_level_error_fails():
    gap, ecb = fx_fixture()
    checks, stats = AD.fx_persistence_checks(gap, ecb)
    assert all(c.passed for c in checks) and stats["absorption_slope"] == pytest.approx(1.0, abs=0.15)
    bad, ecb = fx_fixture(persistent=40.0)  # a level error from 2017: persistent, not absorbed
    names = [c.name for c in AD.fx_persistence_checks(bad, ecb)[0] if not c.passed]
    assert "Écart à la fin (|pb|)" in names and "Écart moyen signé (|pb|)" in names


def test_a2_spy_drift_criteria():
    rng = np.random.default_rng(3)
    index = synthetic(NYSE, 1000, 0.0004)
    years = (NYSE - NYSE[0]).days / 365.25
    noise = pd.Series(rng.normal(0, 3e-4, len(NYSE)), index=NYSE)
    tr = index * np.exp(-0.0009 * years) * (1 + noise - noise.shift(1).fillna(0) * 0.5)
    exgap = pd.Series([5.0, -8.0], index=NYSE[[100, 200]])
    checks, diag = AD.spy_drift_checks(tr, index, exgap)
    assert all(c.passed for c in checks), [c for c in checks if not c.passed]
    assert diag["fitted_drift_bp_per_year"] == pytest.approx(-9, abs=1.5)
    drifting = tr.copy()
    drifting.iloc[1000:1040] *= 1.004  # 40 pb kept for 40 sessions: a level error, not timing noise
    names = [c.name for c in AD.spy_drift_checks(drifting, index, exgap)[0] if not c.passed]
    assert any(n.startswith("Plus longue série") for n in names)


def test_a3_candle_parsers_ms_epochs_and_alignment():
    finex = AD.parse_candles(["[[1420070400000,300,310,320,290,1200.5]]"], "bitfinex")
    assert finex.index[0] == T("2015-01-01") and finex.iloc[0].tolist() == [310.0, 1200.5]
    coin = AD.parse_candles(["[[1420070400,290,320,300,305,12.0]]"], "coinbase")
    assert coin.iloc[0, 0] == 305.0
    with pytest.raises(C.DataUnavailable, match="00:00 UTC"):
        AD.parse_candles(["[[1420074000,290,320,300,305,12.0]]"], "coinbase")
    with pytest.raises(CutoffViolation):
        AD.parse_candles(["[[1704067200000,1,2,3,4,5]]"], "bitfinex")


def test_a3_usd_conversion_uses_only_fixings_published_before_the_utc_close():
    ecb = pd.Series([1.10, 1.12], index=pd.to_datetime(["2019-06-07", "2019-06-10"]))  # Friday, Monday
    usd = pd.Series([8000.0, 8100.0, 8200.0], index=pd.to_datetime(["2019-06-07", "2019-06-08", "2019-06-10"]))
    out = AD.usd_to_eur_by_utc_day(usd, ecb)
    assert out["fx_date"].tolist() == list(pd.to_datetime(["2019-06-07", "2019-06-07", "2019-06-10"]))
    assert out["eur"].tolist() == pytest.approx([8000 / 1.10, 8100 / 1.10, 8200 / 1.12])
    with pytest.raises(C.DataUnavailable, match="trop ancien"):
        AD.usd_to_eur_by_utc_day(pd.Series([1.0], index=[T("2019-06-20")]), ecb)
    with pytest.raises(C.DataUnavailable):
        AD.usd_to_eur_by_utc_day(pd.Series([1.0], index=[T("2019-06-06")]), ecb)


def btc_books():
    days = pd.date_range("2014-09-01", "2023-12-29")
    walk = np.random.default_rng(5).normal(0.0008, 0.03, len(days))
    usd = pd.DataFrame({"close": 400 * np.exp(np.cumsum(walk)), "volume": 5000.0}, index=days)
    usd.loc[pd.to_datetime(["2015-01-06", "2015-01-07", "2015-01-08"]), "volume"] = 0.0
    eur_days = days[days >= "2016-04-16"]
    eur = pd.DataFrame({"close": usd["close"].loc[eur_days] / 1.1, "volume": 500.0})
    eur.loc["2016-04-18":"2016-04-24", "volume"] = 0.0
    eur.loc["2016-05-10", "volume"] = 5.0
    ecb = pd.Series(1.1, index=pd.bdate_range("2014-08-25", "2023-12-29"))
    return usd, eur, ecb


def test_a3_composite_liquidity_splice_and_suspension():
    usd, eur, ecb = btc_books()
    assert AD.btc_splice_date(eur) == T("2016-06-01")  # April and May contain illiquid days
    series, detail, removed, splice = AD.btc_composite(usd, eur, ecb)
    assert list(removed) == list(pd.to_datetime(["2015-01-06", "2015-01-07", "2015-01-08"]))
    assert detail.loc["2016-05-31", "source"] == "bitstamp_btcusd_ecb" and detail.loc[splice, "source"] == "bitstamp_btceur"
    snap = AD.asof(series, "utc_day", SESSIONS, "BTC", allowed_missing=list(AD.BTC_STALE_SESSIONS))
    assert snap.loc["2015-01-09", "source_date"] == T("2015-01-05") and snap.loc["2015-01-09", "age_days"] == 4
    assert (snap.drop(list(AD.BTC_STALE_SESSIONS))["age_days"] == 1).all()
    with pytest.raises(C.DataUnavailable, match="trop ancienne"):
        AD.asof(series, "utc_day", SESSIONS, "BTC")
    with pytest.raises(C.DataUnavailable, match="exception inutile"):
        AD.asof(series, "utc_day", SESSIONS, "BTC", allowed_missing=[*AD.BTC_STALE_SESSIONS, T("2018-03-05")])
    assert all(c.passed for c in AD.splice_checks(usd, eur, ecb, splice))
    jumped = eur.copy()
    jumped.loc[splice:, "close"] *= 1.05
    assert not AD.splice_checks(usd, jumped, ecb, splice)[1].passed


def test_a3_cross_venue_detects_persistent_premium():
    usd, _, _ = btc_books()
    rng = np.random.default_rng(11)
    noise = pd.Series(rng.normal(0, 0.002, len(usd)), index=usd.index)
    venue = usd.assign(close=usd["close"] * (1 + noise))
    primary = usd["close"].loc["2015-02-01":"2016-05-31"]
    assert all(c.passed for c in AD.cross_venue_checks(primary, venue, "test")[0])
    premium = venue.copy()
    premium.loc["2015-12", "close"] *= 0.96  # the reference sits 4 % lower for a month
    names = [c.name for c in AD.cross_venue_checks(primary, premium, "test")[0] if not c.passed]
    assert "test : |écart moyen mensuel| max (pb)" in names


def test_a3b_criteria_are_pinned():
    assert AD.AMENDMENTS["BTC_A3B"] == {"consensus_min_exchanges": 3, "median_abs_bp": 50.0, "p99_abs_bp": 300.0,
                                        "max_abs_bp": 1500.0, "month_mean_abs_bp": 200.0, "daily_corr_min": 0.95,
                                        "drift_bp_per_year": 50.0, "drift_window_obs": 20, "drift_z": 3.0,
                                        "outlier_month_bp": 200.0}
    assert AD.AMENDMENTS["BTC_A3"]["cross_cagr_abs"] == 0.005  # original criterion kept, superseded


def test_a3b_one_series_per_exchange_never_both_pairs():
    days = pd.date_range("2019-06-03", periods=6)
    eur = pd.DataFrame({"close": [9000.0] * 6, "volume": [10, 10, 0.5, 10, 10, 10]}, index=days)
    usd = pd.DataFrame({"close": [11000.0] * 6, "volume": 50.0}, index=days)
    ecb = pd.Series(1.1, index=pd.bdate_range("2019-05-27", "2019-06-10"))
    out = AD.exchange_eur_series(eur, usd, ecb)
    assert out.index.equals(days) and not out.index.has_duplicates
    assert out["pair"].tolist() == ["EUR", "EUR", "USD/BCE", "EUR", "EUR", "EUR"]  # illiquid EUR day only
    assert out.loc["2019-06-05", "eur"] == pytest.approx(10000.0)


def ar1(n, rho, sd, seed):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = rho * x[i - 1] + rng.normal(0, sd * np.sqrt(1 - rho ** 2))
    return x


def test_a3b_duration_aware_drift_replaces_annualized_cagr():
    short = pd.date_range("2015-07-20", periods=286)
    noise = pd.Series(ar1(286, 0.7, 40, 1), index=short)
    check, stats = AD.duration_drift_check(noise, "court")
    assert check.passed and stats["limit_bp"] > AD.AMENDMENTS["BTC_A3B"]["drift_bp_per_year"] * stats["years"]
    long = pd.date_range("2015-01-01", periods=1100)
    drifting = pd.Series(ar1(1100, 0.7, 40, 2) + np.linspace(0, 900, 1100), index=long)  # ~300 pb/an
    assert not AD.duration_drift_check(drifting, "dérive")[0].passed
    assert not AD.duration_drift_check(noise.iloc[:30], "trop court")[0].passed


def three_venues(primary_premium=False):
    days = pd.date_range("2017-01-01", "2018-12-31")
    rng = np.random.default_rng(4)
    base = pd.Series(1000 * np.exp(np.cumsum(rng.normal(0, 0.03, len(days)))), index=days)
    noise = lambda s: pd.Series(rng.normal(0, 0.003, len(days)), index=days)
    primary, a, b = base * (1 + noise(1)), base * (1 + noise(2)), base * (1 + noise(3))
    if primary_premium:
        primary.loc["2017-12"] *= 1.04
    else:
        b.loc["2017-12"] *= 1.04  # venue-specific premium on B only
    return primary, {"A": a, "B": b}


def test_a3b_consensus_is_robust_to_one_outlier_venue_but_not_to_an_outlier_primary():
    primary, venues = three_venues()
    checks, stats = AD.consensus_checks(primary, venues)
    assert all(c.passed for c in checks), [c for c in checks if not c.passed]
    assert AD.monthly_outliers(primary, venues)["2017-12"]["outlier"] == "B"
    primary, venues = three_venues(primary_premium=True)
    names = [c.name for c in AD.consensus_checks(primary, venues)[0] if not c.passed]
    assert "Consensus : |écart moyen mensuel| max (pb)" in names
    assert AD.monthly_outliers(primary, venues)["2017-12"]["outlier"] == "Bitstamp"


def test_a5_cac40_tolerances_are_pinned():
    assert AD.AMENDMENTS["CAC40_A5"] == {"level_max_abs_bp": 1.0, "level_median_abs_bp": 0.1,
                                         "daily_return_corr_min": 0.9999, "min_common_session_share": 0.99}


def bourse_direct_text(levels, extra=()):
    rows = [f"{d:%Y/%m/%d} 02:00;{v:.2f};{v:.2f};{v:.2f};{v:.2f};0;EUR" for d, v in levels.items()]
    return "Date;Open;High;Low;Close;Volume;Currency\n" + "\n".join(rows + list(extra))


def test_bourse_direct_parser_is_strict_and_never_trims():
    levels = synthetic(SESSIONS[:30], 9000)
    parsed = AD.parse_bourse_direct_export(bourse_direct_text(levels))
    assert parsed.index.equals(SESSIONS[:30]) and parsed.iloc[0] == pytest.approx(levels.iloc[0], abs=0.01)
    with pytest.raises(CutoffViolation):  # a single later row refuses the whole file, values unread
        AD.parse_bourse_direct_export(bourse_direct_text(levels, ["2024/01/02 02:00;not-a-number"]))
    with pytest.raises(C.DataUnavailable, match="EUR"):
        AD.parse_bourse_direct_export(bourse_direct_text(levels).replace(";EUR", ";USD", 1))
    with pytest.raises(C.DataUnavailable, match="en-tête"):
        AD.parse_bourse_direct_export("Date,Close\n2019/01/02 02:00,1\n")


class _FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.url = payload, status, "https://query2.finance.yahoo.com/v8/finance/chart/X"

    def json(self):
        return json.loads(json.dumps(self.payload))


def chart_payload(stamps):
    meta = {"symbol": "X", "currency": "EUR", "instrumentType": "INDEX", "exchangeTimezoneName": "Europe/Paris",
            "regularMarketPrice": 8123.4, "regularMarketTime": 1760000000, "fiftyTwoWeekHigh": 9000.0,
            "chartPreviousClose": 7000.0}
    return {"chart": {"result": [{"meta": meta, "timestamp": stamps,
                                  "indicators": {"quote": [{"close": [1.0] * len(stamps)}]}}], "error": None}}


def test_yahoo_transport_drops_current_quote_meta_and_refuses_unbounded_requests(monkeypatch):
    from portfolio_lab.v2 import yahoo_bounded as YB
    yfdata = pytest.importorskip("yfinance.data")
    calls = []

    def fake(self, url, request_method, body=None, params=None, timeout=30):
        calls.append(url)
        return _FakeResponse(chart_payload([1388563200, 1704182400 if "late" in url else 1388649600]))

    monkeypatch.setattr(yfdata.YfData, "_make_request", fake)
    audit = {"requests": [], "handshake": [], "http_status": []}
    end = pd.Timestamp("2023-12-30", tz="Europe/Paris")
    period2 = int(end.timestamp())
    with YB._bounded_transport(end, audit):
        guarded = yfdata.YfData._make_request
        out = guarded(None, "https://q/v8/finance/chart/X", None, params={"period1": 1, "period2": period2})
        meta = out.json()["chart"]["result"][0]["meta"]
        assert "regularMarketPrice" not in meta and "regularMarketTime" not in meta and meta["currency"] == "EUR"
        assert "regularMarketPrice" not in out.text and "1760000000" not in out.text
        with pytest.raises(CutoffViolation, match="non bornée"):
            guarded(None, "https://q/v8/finance/chart/X", None, params={"range": "1d"})
        with pytest.raises(CutoffViolation, match="non bornée"):
            guarded(None, "https://q/v8/finance/chart/X", None, params={"period1": 1, "period2": period2 + 86400})
        with pytest.raises(CutoffViolation, match="non autorisé"):
            guarded(None, "https://q/v10/finance/quoteSummary/X", None, params={})
        with pytest.raises(CutoffViolation):
            guarded(None, "https://q/v8/finance/chart/late", None, params={"period1": 1, "period2": period2})
    assert yfdata.YfData._make_request is fake  # original transport restored
    assert sorted(audit["meta_fields_dropped"]) == ["chartPreviousClose", "fiftyTwoWeekHigh", "regularMarketPrice",
                                                    "regularMarketTime"]
    with pytest.raises(CutoffViolation):
        YB.fetch_daily("X", "Europe/Paris", "2014-10-01", "2024-01-02")


def bourse_direct_like(price):
    """Synthetic NR on the session calendar carrying the two declared Bourse Direct anomalies."""
    nr = price * np.exp(0.00002 * np.arange(len(price)))  # ~0.2 pb/day of reinvested dividends
    moved = nr.loc[T("2014-12-31")]
    nr = nr.drop([T("2014-12-31"), T("2016-07-27")])
    return pd.concat([nr, pd.Series([moved], index=[T("2015-01-01")])]).sort_index()


def test_cac40_bourse_direct_relabel_and_stale_mark_are_declared_and_checked():
    price = synthetic(SESSIONS, 4000, 0.0002) * (1 + 0.01 * np.sin(np.arange(len(SESSIONS)) / 5))
    nr = bourse_direct_like(price)
    with pytest.raises(C.DataUnavailable):
        AD.validate_cac40("QS0011131826", nr, ("FR0003500008", price))           # undeclared anomalies
    levels, checks, ok = AD.validate_cac40("QS0011131826", nr, ("FR0003500008", price), vendor="CAC40_BOURSE_DIRECT")
    assert ok, [c for c in checks if not c.passed]
    assert levels.loc["2016-07-27"] == levels.loc["2016-07-26"]               # stale valuation mark
    assert levels.loc["2014-12-31"] == nr.loc["2015-01-01"]                    # relabelled row
    assert any(c.name.startswith("Réétiquetage") and c.passed for c in checks)
    bad = price.copy()
    bad.loc["2016-06-27"] *= 1.011                                              # one-day bad print, reversed
    names = [c.name for c in AD.validate_cac40("QS0011131826", nr, ("FR0003500008", bad),
                                               vendor="CAC40_BOURSE_DIRECT")[1] if not c.passed]
    assert names == ["Plus forte sous-performance quotidienne de la variante la plus riche (pb)"]
    with pytest.raises(C.DataUnavailable, match="Réétiquetage"):
        AD.apply_relabels(nr.drop(T("2015-01-01")), "CAC40_BOURSE_DIRECT")


def test_official_corrections_apply_only_to_the_expected_raw_value():
    days = pd.to_datetime(["2016-06-24", "2016-06-27", "2016-06-28"])
    raw = pd.Series([4106.73, 4030.30, 4088.85], index=days)
    corrected, records = AD.apply_official_corrections(raw, "FCHI_YAHOO")
    assert corrected.loc["2016-06-27"] == 3984.72 and raw.loc["2016-06-27"] == 4030.30  # raw copy untouched
    assert records[0]["raw"] == 4030.30 and records[0]["corrected"] == 3984.72 and "AFP" in records[0]["source"]
    with pytest.raises(C.DataUnavailable, match="inattendue"):
        AD.apply_official_corrections(raw.replace(4030.30, 4031.0), "FCHI_YAHOO")
    with pytest.raises(C.DataUnavailable, match="inattendue"):
        AD.apply_official_corrections(raw.drop(T("2016-06-27")), "FCHI_YAHOO")
    assert AD.OFFICIAL_CORRECTIONS["CAC40_BOURSE_DIRECT"][T("2020-10-19")]["value"] == 10521.77
    assert AD.TOLERANCES["CAC40"]["daily_shortfall_bp"] == 1.0  # the original test is not relaxed


BOUNDED_NR = C.ROOT / "data/v2_1/raw/cac40/PX1NR_bourse_direct_2014-10-01_2023-12-29.csv"
BOUNDED_PX = C.ROOT / "data/v2_1/raw/yahoo/FCHI_2014-10-01_2023-12-29.csv"


@pytest.mark.skipif(not (BOUNDED_NR.exists() and BOUNDED_PX.exists()), reason="exports bornés locaux absents")
def test_cac40_regression_on_exceptional_dates_and_neighbours():
    nr_raw = AD.parse_bourse_direct_export(BOUNDED_NR.read_text(encoding="utf-8"))
    px_raw = pd.read_csv(BOUNDED_PX, index_col=0, parse_dates=True)["Close"]
    assert nr_raw.index.max() <= T("2023-12-29") and px_raw.index.max() <= T("2023-12-29")
    raw = AD.validate_cac40("QS0011131826", nr_raw, ("FR0003500008", px_raw), vendor="CAC40_BOURSE_DIRECT")
    assert not raw[2]  # the original daily NR-versus-price test still fails on the raw files
    nr, _ = AD.apply_official_corrections(nr_raw, "CAC40_BOURSE_DIRECT")
    px, _ = AD.apply_official_corrections(px_raw, "FCHI_YAHOO")
    levels, checks, ok = AD.validate_cac40("QS0011131826", nr, ("FR0003500008", px), vendor="CAC40_BOURSE_DIRECT")
    assert ok, [c for c in checks if not c.passed]
    observed = AD.apply_relabels(nr, "CAC40_BOURSE_DIRECT")
    gap = (observed.pct_change() - px.reindex(observed.index).pct_change()) * 1e4
    raw_gap = (AD.apply_relabels(nr_raw, "CAC40_BOURSE_DIRECT").pct_change() - px_raw.reindex(observed.index).pct_change()) * 1e4
    for start, end, bad in (("2016-06-22", "2016-07-01", ("2016-06-27", "2016-06-28")),
                            ("2020-10-14", "2020-10-23", ("2020-10-19", "2020-10-20"))):
        assert gap.loc[start:end].abs().max() < 0.05                       # corrected: rounding only
        assert (raw_gap.loc[list(bad)].abs() > 25).all()                   # raw: the two reversing prints
        quiet = raw_gap.loc[start:end].drop(pd.to_datetime(list(bad)))
        assert quiet.abs().max() < 0.05                                    # neighbours were never affected
    assert levels.loc["2020-10-19"] / levels.loc["2020-10-16"] == pytest.approx(px.loc["2020-10-19"] / px.loc["2020-10-16"], abs=2e-6)
