"""V2.2 Phase C: BRK.B admission checks, external benchmark integration. Synthetic values, plus a
state test on the bounded raw files when present. No BRK performance is computed here."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from portfolio_lab.v2 import admission as AD, custom as C, custom_analytics as A
from portfolio_lab.v2.guard import CutoffViolation, sha256_file

NYSE = AD.nyse_sessions(pd.Timestamp("2014-09-02"))


def brk_frames(seed=1):
    rng = np.random.default_rng(seed)
    close = pd.Series(130 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(NYSE)))), index=NYSE)
    b = pd.DataFrame({"Close": close, "Adj Close": close, "Dividends": 0.0, "Stock Splits": 0.0})
    a_close = 1500 * close * (1 + rng.normal(0.001, 0.0005, len(NYSE)))
    a = pd.DataFrame({"Close": a_close, "Adj Close": a_close, "Dividends": 0.0, "Stock Splits": 0.0})
    return b, a, close.loc["2016-10-17":].round(2)


def failed(checks):
    return [c.name for c in checks if not c.passed]


def test_a6_tolerances_are_pinned():
    assert AD.AMENDMENTS["BRK_A6"] == {"ab_ratio_median_abs_bp": 50.0, "ab_ratio_max_abs_bp": 200.0,
                                       "ab_daily_corr_min": 0.99, "vendor_median_abs_bp": 1.0, "vendor_p99_abs_bp": 5.0,
                                       "vendor_max_abs_bp": 50.0, "vendor_min_common_share": 0.99, "dividends_max": 0,
                                       "splits_max": 0, "adjclose_max_rel_gap": 1e-9}
    assert AD.BRK_CONVERSION == 1500


def test_validate_brk_passes_and_detects_each_failure():
    b, a, vendor = brk_frames()
    checks, stats = AD.validate_brk(b, a, vendor)
    assert not failed(checks), failed(checks)
    paid = b.copy()
    paid.loc[paid.index[300], "Dividends"] = 1.0
    assert any("Distributions" in n for n in failed(AD.validate_brk(paid, a, vendor)[0]))
    split = b.copy()
    split.loc[split.index[400], "Stock Splits"] = 2.0
    assert any("Divisions" in n for n in failed(AD.validate_brk(split, a, vendor)[0]))
    adjusted = b.assign(**{"Adj Close": b["Close"] * 0.99})
    assert any("ajustée" in n for n in failed(AD.validate_brk(adjusted, a, vendor)[0]))
    premium = a.copy()
    premium.loc["2020-03-12":"2020-03-20", "Close"] *= 1.04
    assert any("écart maximal (pb)" in n and "Classe A" in n for n in failed(AD.validate_brk(b, premium, vendor)[0]))
    wrong = vendor.copy()
    wrong.iloc[50] *= 1.01
    assert any("Second fournisseur : écart maximal" in n for n in failed(AD.validate_brk(b, a, wrong)[0]))
    gap = b.drop(b.index[700])
    assert any("Calendrier BRK-B" in n for n in failed(AD.validate_brk(gap, a.drop(a.index[700]), vendor)[0]))


def test_nasdaq_parser_refuses_post_cutoff_and_reads_dollar_prices():
    rows = [{"date": "12/29/2023", "close": "$356.66", "volume": "1", "open": "$1", "high": "$1", "low": "$1"},
            {"date": "12/28/2023", "close": "$1,355.00", "volume": "1", "open": "$1", "high": "$1", "low": "$1"}]
    text = json.dumps({"data": {"symbol": "BRK.B", "totalRecords": 2, "tradesTable": {"rows": rows}}})
    series = AD.parse_nasdaq_history(text)
    assert series.tolist() == [1355.0, 356.66] and series.index[-1] == pd.Timestamp("2023-12-29")
    with pytest.raises(CutoffViolation):
        AD.parse_nasdaq_history(text.replace("12/29/2023", "01/02/2024"))


def synthetic_result(name, weights, index, values, synthetic=False, kind=None):
    spec = C.PortfolioSpec(name, weights, start=str(index[0].date()), end=str(index[-1].date()),
                           rebalance="buy_hold" if len(weights) == 1 else "monthly")
    panel = C.PricePanel(pd.DataFrame(values, index=index), {a: {"research_alignment": "validated_paris_session_end",
                                                                  "kind": kind or "test"} for a in weights},
                         synthetic=True, sessions=index)
    return C.BacktestResult(**{**vars(C.simulate(spec, panel)), "synthetic": synthetic,
                               "provenance": {a: {"research_alignment": "validated_paris_session_end",
                                                  "kind": kind or "test"} for a in weights}})


def test_comparison_with_external_benchmark_keeps_bases_separate():
    index = pd.bdate_range("2019-01-02", periods=60)
    t = np.arange(60)
    main = synthetic_result("Diversifié", {"A": .5, "B": .5}, index, {"A": 100 + t, "B": 100 + 0.5 * t})
    brk = synthetic_result("BRK.B — test", {"BRK_B": 1.0}, index, {"BRK_B": 100 * np.exp(0.001 * t)},
                           kind="Référence professionnelle concentrée")
    lab = SimpleNamespace(ordered=lambda ids: [s for s in ids if s == "N07"], initial=100000,
                          wealth=pd.DataFrame({"N07": 100000 * np.exp(0.002 * t)}, index=index),
                          reference=pd.DataFrame({"FULL_cagr": [.2], "terminal_net": [9e5]}, index=["N07"]),
                          summary=pd.DataFrame({"cagr_gross": [.25]}, index=["N07"]),
                          meta=pd.DataFrame({"kind": ["strategy"]}, index=["N07"]), strategies=["N07"], benchmarks=[],
                          eur_rate=pd.Series(0.0, index=index))
    figs, table = A.comparison_figures(main, lab, ["N07"], extra=[brk])
    row = table.loc["BRK.B — test"]
    assert row["CAGR net fiscal"] == "Non calculé" and row["CAGR brut Research (sans frais ni impôts)"] == "—"
    assert "Référence professionnelle concentrée" in row["Base"] and "0 pb" in row["Base"]
    assert row["Valeur finale économique (€)"] == pytest.approx(100000 * np.exp(0.059))
    assert len(table) == 3 and len(figs) == 3
    shifted = synthetic_result("BRK.B — décalé", {"BRK_B": 1.0}, index[1:], {"BRK_B": 100 * np.exp(0.001 * t[1:])})
    with pytest.raises(C.DataUnavailable, match="calendrier"):
        A.comparison(main, lab, ["N07"], extra=[shifted])


def test_benchmark_result_fails_closed_until_validated(monkeypatch, tmp_path):
    catalog = A.benchmark_catalog()
    assert catalog["BRK_B"]["status"] in ("pending_validation", "validated")
    pending = {"BRK_B": {**catalog["BRK_B"], "status": "pending_validation"}}
    with pytest.raises(C.DataUnavailable, match="indisponible"):
        A.benchmark_result("BRK_B", pending)
    with pytest.raises(C.DataUnavailable, match="inconnue"):
        A.benchmark_result("XYZ", pending)
    # A validated synthetic benchmark goes through the same guarded loader.
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "load_settings", lambda _: SimpleNamespace(research_root=tmp_path / "research"))
    root = tmp_path / "data/v2_1"
    root.mkdir(parents=True)
    dates = AD.euronext_sessions()
    calendar = root / "sessions.csv"
    pd.DataFrame({"Date": dates.strftime("%Y-%m-%d")}).to_csv(calendar, index=False)
    level = root / "BRK_B.csv"
    pd.Series(np.linspace(100, 250, len(dates)), index=dates, name="level").rename_axis("Date").to_csv(level, date_format="%Y-%m-%d")
    ok = {"BRK_B": {**catalog["BRK_B"], "status": "validated", "path": level.name, "sha256": sha256_file(level),
                    "calendar": AD.CALENDAR_ID, "clock": AD.CLOCK_ID, "independent_check": "synthétique",
                    "calendar_path": calendar.name, "calendar_sha256": sha256_file(calendar)}}
    result = A.benchmark_result("BRK_B", ok)
    assert result.spec.rebalance == "buy_hold" and dict(result.spec.weights) == {"BRK_B": 1.0}
    assert result.ledger.nav.iloc[-1] == pytest.approx(250000) and result.ledger.rebalance.sum() == 1


RAW = C.ROOT / "data/v2_1/raw"


@pytest.mark.skipif(not (RAW / "yahoo/BRK-B_2014-09-01_2023-12-29.csv").exists(), reason="fichiers BRK bornés absents")
def test_real_brk_state_vendor_agrees_and_ab_checks_fail_as_reported():
    b = pd.read_csv(RAW / "yahoo/BRK-B_2014-09-01_2023-12-29.csv", index_col=0, parse_dates=True)
    a = pd.read_csv(RAW / "yahoo/BRK-A_2014-09-01_2023-12-29.csv", index_col=0, parse_dates=True)
    vendor = AD.parse_nasdaq_history((RAW / "nasdaq/BRK.B_2014-09-01_2023-12-29.json").read_text(encoding="utf-8"))
    assert b.index.max() <= pd.Timestamp("2023-12-29") and vendor.index.max() <= pd.Timestamp("2023-12-29")
    checks, _ = AD.validate_brk(b, a, vendor)
    assert set(failed(checks)) == {"Classe A / (1 500 × classe B) : écart maximal (pb)",
                                   "Classes A et B : corrélation des rendements quotidiens"}
    if A.benchmark_catalog()["BRK_B"]["status"] != "validated":
        assert not (C.ROOT / "data/v2_1/levels/BRK_B.csv").exists()   # nothing admitted before a decision


def test_a6_bis_tolerances_are_pinned_and_original_kept():
    assert AD.AMENDMENTS["BRK_A6_BIS"] == {"ab_median_abs_bp": 50.0, "ab_lower_bound_bp": -100.0,
                                           "ab_cumulative_abs_bp": 50.0, "range_margin": 0.001, "range_extreme_rel": 0.01}
    assert AD.AMENDMENTS["BRK_A6"]["ab_ratio_max_abs_bp"] == 200.0 and AD.AMENDMENTS["BRK_A6"]["ab_daily_corr_min"] == 0.99


def bis_inputs(seed=3):
    b, a, vendor = brk_frames(seed)
    for frame in (a, b):
        frame["High"], frame["Low"] = frame["Close"] * 1.004, frame["Close"] * 0.996
    ranges = {}
    for q in ("2014Q3", "2014Q4", "2015Q1", "2015Q2", "2015Q3", "2015Q4"):
        p = pd.Period(q, freq="Q")
        ranges[q] = {c: [float(f.loc[p.start_time:p.end_time, "High"].max()), float(f.loc[p.start_time:p.end_time, "Low"].min())]
                     for c, f in (("A", a), ("B", b))}
    return b, a, vendor, ranges


def test_a6_bis_is_asymmetric_and_catches_each_defect():
    b, a, vendor, ranges = bis_inputs()
    binding, diag, original = AD.validate_brk_bis(b, a, vendor, ranges)
    assert not failed(binding), failed(binding)
    premium = a.copy()                       # A above 1,500 B: allowed by the one-way conversion
    premium.loc["2015-03-02":"2015-03-20", "Close"] *= 1.03
    assert not [n for n in failed(AD.validate_brk_bis(b, premium, vendor, ranges)[0]) if "Avant Nasdaq" in n]
    late_premium = a.copy()                  # covered by Nasdaq: symmetric A/B rule is only diagnostic
    late_premium.loc["2023-04-03":"2023-05-31", "Close"] *= 1.035
    bis, _, orig = AD.validate_brk_bis(b, late_premium, vendor, ranges)
    assert not failed(bis) and any("écart maximal" in n for n in failed(orig))
    discount = a.copy()                      # A below 1,500 B by 150 bp: conversion arbitrage violated
    discount.loc["2015-06-01":"2015-06-05", "Close"] *= 0.985
    assert any("borne basse" in n for n in failed(AD.validate_brk_bis(b, discount, vendor, ranges)[0]))
    drift = b.copy()                         # B drifts 1 % away from A before Nasdaq coverage
    drift.loc[:"2016-10-14", "Close"] *= np.linspace(1, 1.01, len(drift.loc[:"2016-10-14"]))
    drift["Adj Close"] = drift["Close"]
    assert any("divergence cumulée" in n for n in failed(AD.validate_brk_bis(drift, a, vendor, ranges)[0]))
    bad_close = b.copy()
    bad_close.loc["2015-08-03", "Close"] = ranges["2015Q3"]["B"][0] * 1.02
    bad_close["Adj Close"] = bad_close["Close"]
    assert any("hors des fourchettes" in n for n in failed(AD.validate_brk_bis(bad_close, a, vendor, ranges)[0]))
    shifted = {**ranges, "2015Q2": {**ranges["2015Q2"], "B": [ranges["2015Q2"]["B"][0] * 1.02, ranges["2015Q2"]["B"][1]]}}
    assert any("extrêmes" in n for n in failed(AD.validate_brk_bis(b, a, vendor, shifted)[0]))
    wrong = vendor.copy()
    wrong.iloc[10] *= 1.01
    assert any("Second fournisseur" in n for n in failed(AD.validate_brk_bis(b, a, wrong, ranges)[0]))


@pytest.mark.skipif(not (RAW / "sec/berkshire_10k_2015_price_ranges.json").exists(), reason="extraction 10-K absente")
def test_real_brk_a6_bis_state():
    b = pd.read_csv(RAW / "yahoo/BRK-B_2014-09-01_2023-12-29.csv", index_col=0, parse_dates=True)
    a = pd.read_csv(RAW / "yahoo/BRK-A_2014-09-01_2023-12-29.csv", index_col=0, parse_dates=True)
    vendor = AD.parse_nasdaq_history((RAW / "nasdaq/BRK.B_2014-09-01_2023-12-29.json").read_text(encoding="utf-8"))
    ranges = json.loads((RAW / "sec/berkshire_10k_2015_price_ranges.json").read_text(encoding="utf-8"))["ranges"]
    binding, diag, original = AD.validate_brk_bis(b, a, vendor, ranges)
    assert not failed(binding) and len(failed(original)) == 2
    assert diag["persistent_discount"]["longest_run_below_minus_50bp_full"] <= 2


@pytest.mark.skipif(A.benchmark_catalog()["BRK_B"]["status"] != "validated"
                    or not (C.ROOT / "data/v2_1/levels/BRK_B.csv").exists(), reason="BRK.B non admis localement")
def test_real_brk_buy_and_hold_regression():
    from portfolio_lab.v2 import backtest_checks as B
    brk = A.benchmark_result("BRK_B")
    panel = C.load_validated_panel(brk.spec, A.benchmark_catalog())
    checks, stats = B.ledger_checks(brk, panel, A.risk(brk.ledger.nav, 100000))
    assert all(c.passed for c in checks) and stats["rebalances"] == 1 and stats["orders"] == 1
    assert len(brk.ledger) == 2368 and brk.ledger.index.max() == pd.Timestamp("2023-12-29")
    # Buy & hold of a non-distributing stock: wealth = capital x EUR level ratio, exactly.
    level = panel.prices["BRK_B"]
    assert np.allclose(brk.ledger.nav, 100000 * level / level.iloc[0], rtol=1e-12)
    metrics = A.risk(brk.ledger.nav, 100000)
    assert brk.ledger.nav.iloc[-1] == pytest.approx(295225.11, abs=0.01)
    assert metrics["CAGR économique"] == pytest.approx(0.124219, abs=1e-6)
    assert metrics["MaxDD"] == pytest.approx(0.296207, abs=1e-6)
