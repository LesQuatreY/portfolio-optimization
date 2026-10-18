"""V2.2 Phase B: independent backtest checks, Research calendar view, comparison layers.

Unit tests use synthetic prices only. The last test runs the real saved portfolio when the
admitted local data exist (data/v2_1, ignored by Git) and pins its result as a regression.
"""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from portfolio_lab.v2 import backtest_checks as B, custom as C, custom_analytics as A, metrics as M


def synthetic_panel(start="2015-01-01", end="2016-12-30", assets="ABC"):
    dates = pd.bdate_range(start, end)
    t = np.arange(len(dates))
    prices = pd.DataFrame({a: 100 * np.exp(.0003 * (i + 1) * t + .1 * np.sin(t / (20 + 7 * i)))
                           for i, a in enumerate(assets)}, index=dates)
    return C.PricePanel(prices, {a: {"source": "synthetic"} for a in assets}, synthetic=True, sessions=dates)


def spec(**kw):
    return C.PortfolioSpec("Synthétique", {"A": .5, "B": .3, "C": .2}, start="2015-01-01", end="2016-12-30", **kw)


@pytest.mark.parametrize("mode", ["monthly", "annual", "buy_hold"])
def test_closed_form_matches_engine_and_all_ledger_checks_pass(mode):
    panel = synthetic_panel()
    result = C.simulate(spec(rebalance=mode), panel)
    nav = B.closed_form_nav(panel.prices, dict(result.spec.weights), 100000, mode)
    assert np.allclose(nav, result.ledger.nav, rtol=1e-12)
    checks, stats = B.ledger_checks(result, panel, A.risk(result.ledger.nav, 100000))
    assert all(c.passed for c in checks), [c for c in checks if not c.passed]
    assert stats["rebalances"] == len(B.rebalance_dates(panel.prices.index, mode))


def test_closed_form_by_hand_two_months():
    dates = pd.to_datetime(["2018-01-31", "2018-02-01", "2018-02-02"])
    prices = pd.DataFrame({"A": [10.0, 20.0, 20.0], "B": [10.0, 10.0, 20.0]}, index=dates)
    # Jan 31: 50/50 of 100. Feb 1 (new month): value 150 then rebalanced; Feb 2: 75 + 75*2 = 225.
    assert B.closed_form_nav(prices, {"A": .5, "B": .5}, 100, "monthly").tolist() == [100, 150, 225]


def test_ledger_checks_detect_tampered_accounting():
    panel = synthetic_panel()
    result = C.simulate(spec(cost_bps=10), panel)
    good = B.ledger_checks(result, panel)[0]
    assert all(c.passed for c in good)
    bad_cash = replace(result, ledger=result.ledger.assign(cash=result.ledger.cash + 50))
    assert any(not c.passed and c.name.startswith("Autofinancement") for c in B.ledger_checks(bad_cash, panel)[0])
    held = result.holdings.copy()
    held.iloc[100, 0] *= 1.01
    names = [c.name for c in B.ledger_checks(replace(result, holdings=held), panel)[0] if not c.passed]
    assert any(n.startswith("Réconciliation") for n in names)
    flags = result.ledger.copy()
    flags.iloc[25, flags.columns.get_loc("rebalance")] = True
    assert any(not c.passed and c.name.startswith("Rééquilibrages") for c in
               B.ledger_checks(replace(result, ledger=flags), panel)[0])
    costs = result.ledger.assign(cost=result.ledger.cost * 2)
    assert any(not c.passed and c.name.startswith("Frais") for c in B.ledger_checks(replace(result, ledger=costs), panel)[0])


def test_causality_checks_on_synthetic_panel():
    checks = B.causality_checks(spec(), synthetic_panel(), cut="2016-03-31")
    assert all(c.passed for c in checks), [c for c in checks if not c.passed]


def test_independent_metrics_by_hand():
    nav = pd.Series([110.0, 99.0, 121.0], index=pd.to_datetime(["2019-01-02", "2019-01-03", "2019-01-04"]))
    out = B.independent_metrics(nav, 100, pd.Series(0.036, index=nav.index))
    returns = np.array([.1, -.1, 121 / 99 - 1])
    assert out["max_drawdown"] == pytest.approx(0.1) and out["final"] == 121
    assert out["volatility"] == pytest.approx(returns.std(ddof=1) * np.sqrt(252))
    excess = returns - np.array([0, 0.036 / 360, 0.036 / 360])
    assert out["sharpe_eur"] == pytest.approx(excess.mean() / excess.std(ddof=1) * np.sqrt(252))
    rate = pd.Series(0.036, index=nav.index)
    assert A.risk(nav, 100, rate=rate)["Sharpe (taux EUR Research)"] == pytest.approx(out["sharpe_eur"])
    with pytest.raises(C.DataUnavailable):
        A.risk(nav, 100, rate=rate.iloc[:2])


def lab_fixture():
    dates = pd.to_datetime(["2019-12-23", "2019-12-24", "2019-12-25", "2019-12-27"])
    wealth = pd.DataFrame({"N07": [100.0, 101.0, 101.0, 103.0]}, index=dates)
    return SimpleNamespace(ordered=lambda ids: list(ids), initial=100, wealth=wealth,
                           reference=pd.DataFrame({"FULL_cagr": [.1], "terminal_net": [200]}, index=["N07"]),
                           summary=pd.DataFrame({"cagr_gross": [.12]}, index=["N07"]),
                           meta=pd.DataFrame({"kind": ["strategy"]}, index=["N07"]), strategies=["N07"], benchmarks=[],
                           eur_rate=pd.Series(0.0, index=dates))


def test_common_calendar_samples_without_changing_values():
    lab = lab_fixture()
    index = lab.wealth.index.drop(pd.Timestamp("2019-12-25"))
    view = A.common_calendar(lab, index)
    assert view.dropped_dates == ["2019-12-25"] and view.wealth.index.equals(index)
    assert (view.wealth["N07"] == lab.wealth["N07"].loc[index]).all()
    with pytest.raises(C.DataUnavailable, match="absentes"):
        A.common_calendar(lab, index.append(pd.DatetimeIndex(["2019-12-30"])))
    table = A.comparability_table()
    assert table.loc["CAGR net fiscal / patrimoine net", "Comparable ?"] == "Non"


ADMITTED = C.ROOT / "data/v2_1/levels/CAC40.csv"


@pytest.mark.skipif(not ADMITTED.exists(), reason="données admises locales absentes")
def test_real_diversified_portfolio_regression():
    original = C.load_spec(C.ROOT / "config/v2/portfolios/mon_portefeuille_diversifie.json")
    assert C.availability(original, C.load_catalog()) == []
    panel = C.load_validated_panel(original)
    result = C.simulate(original, panel)
    checks, stats = B.ledger_checks(result, panel, A.risk(result.ledger.nav, original.initial_capital))
    assert all(c.passed for c in checks), [c for c in checks if not c.passed]
    assert stats["rebalances"] == 111 and len(result.ledger) == 2368
    assert result.ledger.index.max() == pd.Timestamp("2023-12-29")
    # Regression pins (V2.2 admitted data; any data or engine change must be explained).
    assert result.ledger.nav.iloc[-1] == pytest.approx(302448.53, abs=0.05)
    metrics = A.risk(result.ledger.nav, original.initial_capital)
    assert metrics["CAGR économique"] == pytest.approx(0.127162, abs=1e-6)
    assert metrics["MaxDD"] == pytest.approx(0.296455, abs=1e-6)
    assert M.years(result.ledger.index) == pytest.approx(9.2457, abs=1e-4)
