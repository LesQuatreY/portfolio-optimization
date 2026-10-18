"""Independent fractional arithmetic, adversarial data and real notebook controls.

All new observations are synthetic and strictly before the development cutoff.
"""
from dataclasses import replace
from fractions import Fraction as Q
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from portfolio_lab.v2 import custom as C, custom_analytics as A
from portfolio_lab.v2.guard import CutoffViolation, IntegrityError, sha256_file


def panel(dates=None, values=None):
    dates = pd.to_datetime(dates or ["2018-01-31", "2018-02-01", "2018-02-02", "2018-03-01"])
    values = values or [[10, 10], [20, 10], [20, 20], [10, 20]]
    return C.PricePanel(pd.DataFrame(values, index=dates, columns=["A", "B"]),
                        {"A": {"source": "Synthetic oracle"}, "B": {"source": "Synthetic oracle"}},
                        synthetic=True, sessions=dates)


def spec(p=None, **kw):
    p = p or panel()
    return C.PortfolioSpec("Exemple synthétique", {"A": .5, "B": .5}, initial_capital=100,
                           start=str(p.prices.index[0].date()), end=str(p.prices.index[-1].date()), **kw)


@pytest.mark.parametrize("weights", [{}, {"A": .5}, {"A": -.1, "B": 1.1}, {"A": 0, "B": 1},
                                    {"A": np.nan}, {"A": np.inf}, {"A": True}, {"A": "1"}])
def test_invalid_weights(weights):
    with pytest.raises(ValueError):
        C.PortfolioSpec("test", weights)


@pytest.mark.parametrize("kw", [{"initial_capital": 0}, {"initial_capital": float('nan')},
    {"initial_capital": True}, {"cost_bps": -1}, {"cost_bps": 10000}, {"rebalance": "daily"},
    {"currency": "USD"}, {"schema_version": True}, {"name": ""}, {"start": "NaT"},
    {"start": "2023-12-29"}, {"start": "2010-01-01"}, {"end": "2024-01-01"}, {"end": "2023-12-29T12:00:00"}])
def test_invalid_spec(kw):
    with pytest.raises(ValueError if kw.get("end") != "2024-01-01" else CutoffViolation):
        C.PortfolioSpec(**{"name": "test", "weights": {"A": 1}, **kw})


def test_weights_are_copied_immutable_and_identity_is_order_independent():
    weights = {"A": .5, "B": .5}
    a = C.PortfolioSpec("test", weights)
    weights["A"] = .9
    assert a.weights["A"] == .5
    with pytest.raises(TypeError):
        a.weights["A"] = .9
    assert a.identity == C.PortfolioSpec("test", {"B": .5, "A": .5}).identity
    assert a.identity != replace(a, cost_bps=1).identity


def test_monthly_independent_oracle():
    r = C.simulate(spec(), panel())
    # Hand calculation: 5 units each -> 3.75 A / 7.5 B -> 9.375 A / 4.6875 B.
    assert r.ledger.nav.to_list() == pytest.approx([100, 150, 225, 187.5])
    np.testing.assert_allclose(r.holdings, [[5, 5], [3.75, 7.5], [3.75, 7.5], [9.375, 4.6875]])
    tx = r.trades[r.trades.Date == pd.Timestamp("2018-02-01")]
    assert tx.notional.tolist() == pytest.approx([-25, 25])
    assert r.ledger.turnover.tolist() == pytest.approx([1, 1/3, 0, .6])


@pytest.mark.parametrize("mode", ["annual", "buy_hold"])
def test_hold_independent_oracle(mode):
    r = C.simulate(spec(rebalance=mode), panel())
    assert r.ledger.nav.tolist() == pytest.approx([100, 150, 200, 150])
    np.testing.assert_allclose(r.holdings, [[5, 5]] * 4)
    assert r.ledger.rebalance.sum() == 1


def test_exact_cost_oracle_not_first_order_approximation():
    p = panel()
    p = replace(p, prices=p.prices.iloc[:2], sessions=p.sessions[:2])
    r = C.simulate(spec(p, cost_bps=1000), p)
    # Independently solved with rational arithmetic: initial v=100/(1+.1).
    # Second fee=.1*(old A-old B)=50/11, post-trade v=(1500-50)/11.
    assert r.ledger.nav.tolist() == pytest.approx([float(Q(1000, 11)), float(Q(1450, 11))])
    assert r.ledger.cost.tolist() == pytest.approx([float(Q(100, 11)), float(Q(50, 11))])
    np.testing.assert_allclose(r.holdings.iloc[1], [float(Q(145, 44)), float(Q(145, 22))])
    assert r.trades.cost.sum() == pytest.approx(r.ledger.cost.sum())


@pytest.mark.parametrize("rate", [0, 1, 25, 1000, 9999])
def test_self_financing_no_external_cash(rate):
    p = panel()
    r = C.simulate(spec(cost_bps=rate), p)
    previous_units = r.holdings.shift(1).fillna(0)
    previous_cash = r.ledger.cash.shift(1).fillna(r.spec.initial_capital)
    before = (previous_units * p.prices).sum(axis=1) + previous_cash
    np.testing.assert_allclose(r.ledger.nav, before - r.ledger.cost, rtol=1e-12)
    assert (r.ledger.cash.abs() < 1e-9).all()
    assert (r.holdings >= 0).all().all()
    np.testing.assert_allclose(r.weights.sum(axis=1) + r.ledger.cash / r.ledger.nav, 1)


def test_annual_first_eligible_session_not_year_end():
    p = panel(["2018-12-28", "2018-12-31", "2019-01-02", "2019-01-03"])
    r = C.simulate(spec(p, rebalance="annual"), p)
    assert r.ledger.rebalance.tolist() == [True, False, True, False]


def test_prefix_and_future_perturbation_do_not_change_past():
    p = panel()
    r = C.simulate(spec(cost_bps=25), p)
    short = replace(p, prices=p.prices.iloc[:3], sessions=p.sessions[:3])
    prefix = C.simulate(spec(short, cost_bps=25), short)
    pd.testing.assert_frame_equal(r.ledger.iloc[:3], prefix.ledger)
    changed = p.prices.copy()
    changed.iloc[-1] = [1000, 1]
    other = C.simulate(spec(cost_bps=25), replace(p, prices=changed))
    pd.testing.assert_frame_equal(r.ledger.iloc[:3], other.ledger.iloc[:3])
    pd.testing.assert_frame_equal(r.ledger, C.simulate(spec(cost_bps=25), p).ledger)


@pytest.mark.parametrize("problem", ["missing_asset", "missing_value", "zero", "inf", "duplicate", "reverse",
                                     "gap", "extra", "no_calendar", "currency", "real_unvalidated", "bounds", "test"])
def test_fail_closed(problem):
    p = panel()
    if problem == "missing_asset": p = replace(p, prices=p.prices[["A"]])
    elif problem in ("missing_value", "zero", "inf"):
        prices = p.prices.astype(float).copy()
        prices.iloc[1, 0] = {"missing_value": np.nan, "zero": 0, "inf": np.inf}[problem]
        p = replace(p, prices=prices)
    elif problem == "duplicate": p = replace(p, prices=pd.concat([p.prices.iloc[:1], p.prices]))
    elif problem == "reverse": p = replace(p, prices=p.prices.iloc[::-1])
    elif problem == "gap": p = replace(p, prices=p.prices.drop(p.prices.index[1]))
    elif problem == "extra": p = replace(p, sessions=p.sessions[:-1])
    elif problem == "no_calendar": p = replace(p, sessions=None)
    elif problem == "currency": p = replace(p, currency="USD")
    elif problem == "real_unvalidated": p = replace(p, synthetic=False)
    elif problem == "bounds": p = replace(p, prices=p.prices.iloc[1:], sessions=p.sessions[1:])
    elif problem == "test":
        # Adversarial synthetic dates only. No real TEST source is accessed.
        prices = p.prices.copy()
        prices.index = pd.to_datetime(["2018-01-31", "2018-02-01", "2018-02-02", "2024-01-01"])
        p = replace(p, prices=prices)
    with pytest.raises((ValueError, CutoffViolation)):
        C.simulate(spec(), p)


def test_fx_direction_and_no_fill():
    p = panel()
    usd = p.prices.A
    fx = pd.Series([2, 2, 4, 4], index=usd.index)
    assert C.to_eur(usd, "USD", fx).tolist() == [5, 10, 5, 2.5]
    pd.testing.assert_series_equal(C.to_eur(usd, "EUR"), usd)
    with pytest.raises(C.DataUnavailable):
        C.to_eur(usd, "USD", fx.iloc[1:])


def test_saved_original_is_blocked_without_reweighting():
    original = C.load_spec(C.ROOT / "config/v2/portfolios/mon_portefeuille_diversifie.json")
    assert dict(original.weights) == {"EM": .30, "SP500": .30, "WORLD": .15, "CAC40": .10, "GOLD": .10, "BTC": .05}
    assert len(C.availability(original, C.load_catalog())) == 6
    with pytest.raises(C.DataUnavailable, match="CAC 40"):
        C.load_validated_panel(original)
    assert dict(original.weights)["CAC40"] == .1


def test_save_reload_conflicts_and_path_boundary(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "ROOT", tmp_path)
    s = spec()
    path = C.save_spec(s)
    assert C.load_spec(path).identity == s.identity
    assert C.save_spec(s) == path
    with pytest.raises(ValueError): C.save_spec(s, tmp_path / "outside")
    with pytest.raises(ValueError): C.load_spec(tmp_path / "outside.json")
    path.write_text(json.dumps(replace(s, name="Altered").to_dict()), encoding="utf-8")
    with pytest.raises(ValueError): C.save_spec(s)
    path.write_text('{"name":"a","name":"b"}', encoding="utf-8")
    with pytest.raises(ValueError, match="dupliquée"): C.load_spec(path)


def test_guarded_local_loader_integrity_and_sessions(monkeypatch, tmp_path):
    # Authorize only tiny synthetic local CSVs. Never copy Research data into a test fixture.
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(C, "load_settings", lambda _: SimpleNamespace(research_root=tmp_path / "research"))
    root = tmp_path / "data/v2_1"
    root.mkdir(parents=True)
    p = panel()
    calendar = root / "sessions.csv"
    pd.DataFrame({"Date": p.prices.index}).to_csv(calendar, index=False)
    catalog = {}
    for asset in ("A", "B"):
        path = root / (asset + ".csv")
        p.prices[asset].rename("level").rename_axis("Date").to_csv(path)
        catalog[asset] = dict(label=asset, status="validated", currency="EUR", path=path.name,
                              sha256=sha256_file(path), calendar="synthetic", clock="shared",
                              dividends="synthetic total return", source="synthetic", independent_check="oracle",
                              calendar_path=calendar.name, calendar_sha256=sha256_file(calendar))
    loaded = C.load_validated_panel(spec(), catalog)
    assert not loaded.synthetic
    assert C.simulate(spec(), loaded).ledger.nav.iloc[-1] == pytest.approx(187.5)
    (root / "A.csv").write_text("Date,level\n2018-01-31,1\n", encoding="utf-8")
    with pytest.raises(IntegrityError): C.load_validated_panel(spec(), catalog)


def test_risk_against_hand_calculation_and_constant_path():
    r = C.simulate(spec(), panel())
    computed = A.risk(r.ledger.nav, 100)
    returns = np.array([0, .5, .5, -1/6])
    assert computed["MaxDD"] == pytest.approx(1/6)
    assert computed["Rendement arithmétique"] == pytest.approx(returns.mean() * 252)
    assert computed["Volatilité"] == pytest.approx(returns.std(ddof=1) * np.sqrt(252))
    assert computed["CAGR économique"] == pytest.approx((187.5/100)**(365.25/30)-1)
    assert np.isnan(A.risk(pd.Series(100., index=r.ledger.index), 100)["Sharpe (taux 0 %)"])
    assert A.summary(r).iloc[0]["CAGR net fiscal"] == "Non calculé"
    assert A.annual_returns(r).iloc[0] == pytest.approx(.875)


def test_trailing_years_no_future_anchor_and_sensitivities():
    dates = pd.to_datetime(["2015-01-02", "2018-01-02", "2020-01-02"])
    curve = pd.Series([100, 133.1, 161.051], index=dates)
    out = A.rolling(curve)
    assert np.isnan(out.iloc[0]["3 ans"])
    assert out.iloc[1]["3 ans"] == pytest.approx((1.331)**(365.25/1096)-1)
    assert out.iloc[2]["5 ans"] == pytest.approx((1.61051)**(365.25/1826)-1)
    modes = A.sensitivities(spec(), panel())
    assert list(modes) == ["monthly", "annual", "buy_hold"]
    assert modes["monthly"].spec.weights == modes["annual"].spec.weights


def test_comparison_refuses_synthetic_and_calendar_mismatch():
    r = C.simulate(spec(), panel())
    with pytest.raises(C.DataUnavailable, match="synthétique"):
        A.comparison(r, None, [])
    lab = SimpleNamespace(ordered=lambda ids: ids, wealth=pd.DataFrame(index=r.prices.index[:-1]))
    with pytest.raises(C.DataUnavailable, match="calendriers"):
        A.comparison(replace(r, synthetic=False), lab, [])


def test_charts_have_synthetic_labels_and_bounded_axes():
    r = C.simulate(spec(), panel())
    figs = A.figures(r)
    assert set(figs) == {"wealth", "drawdown", "rolling", "allocation", "annual", "costs", "turnover"}
    for fig in figs.values():
        assert "SYNTHÉTIQUE" in fig.layout.title.text
    assert figs["wealth"].layout.xaxis.range == (r.prices.index[0], r.prices.index[-1])


def test_ui_validation_missing_dataset_and_preserved_weights(monkeypatch):
    from portfolio_lab.v2 import custom_ui as UI
    monkeypatch.setattr(UI, "display", lambda *args, **kw: None)
    b = UI.PortfolioBuilder()
    original = b.current_spec()
    assert b.run_button.disabled
    assert "Simulation historique indisponible" in b.status.value
    with pytest.raises(C.DataUnavailable): b.run()
    b.weights["CAC40"].value = 0
    assert b.run_button.disabled and b.save_button.disabled
    assert b.result is None
    b.weights["CAC40"].value = 10
    assert b.current_spec().identity == original.identity
    b.enabled["CAC40"].value = False
    assert b.save_button.disabled  # 90%, never silently renormalized


def test_custom_paths_preserve_research_hashes():
    from portfolio_lab.v2.settings import load_settings
    s = load_settings()
    before = {a.name: sha256_file(s.research_root/a.path) for a in s.artifacts}
    C.simulate(spec(), panel())
    C.load_catalog()
    assert before == {a.name: sha256_file(s.research_root/a.path) for a in s.artifacts}
    assert all(before[a.name] == a.sha256 for a in s.artifacts)


def test_comparison_accounting_labels_risk_toggle_and_frozen_net_values():
    r = C.simulate(spec(), panel())
    # Entire adapter fixture is synthetic. No real historical performance is invented.
    provenance = {a: {"research_alignment": "validated_paris_session_end"} for a in r.prices}
    r = replace(r, synthetic=False, provenance=provenance)
    lab = SimpleNamespace(ordered=lambda ids: [s for s in ids if s == "N07"], initial=100,
        wealth=pd.DataFrame({"N07": [100, 160, 200, 220]}, index=r.prices.index),
        reference=pd.DataFrame({"FULL_cagr": [.08], "terminal_net": [200]}, index=["N07"]),
        meta=pd.DataFrame({"kind": ["strategy"]}, index=["N07"]), strategies=["N07"], benchmarks=[])
    figs, table = A.comparison_figures(r, lab, ["N07"])
    assert table.loc["N07", "CAGR net fiscal"] == .08
    assert table.loc["N07", "Patrimoine net fiscal (€)"] == 200
    assert table.iloc[0]["CAGR net fiscal"] == "Non calculé"
    assert "impôts intermédiaires" in table.loc["N07", "Base"]
    buttons = figs["risk"].layout.updatemenus[0].buttons
    assert [b.label for b in buttons] == ["Volatilité", "MaxDD"]
    assert len(buttons[1].args[0]["x"]) == 2
    with pytest.raises(C.DataUnavailable, match="temporel"):
        A.comparison(replace(r, provenance={"A": {}}), lab, ["N07"])


def test_widget_save_and_load_restore_exact_spec(monkeypatch, tmp_path):
    import shutil
    from portfolio_lab.v2 import custom_ui as UI, settings
    folder = tmp_path / "config/v2/portfolios"
    folder.mkdir(parents=True)
    shutil.copy(C.ROOT / "config/v2/portfolios/mon_portefeuille_diversifie.json", folder)
    shutil.copy(C.ROOT / "config/v2/custom_assets.yaml", tmp_path / "config/v2")
    actual_settings = settings.load_settings()
    monkeypatch.setattr(settings, "load_settings", lambda _: actual_settings)
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setattr(UI, "ROOT", tmp_path)
    monkeypatch.setattr(UI, "display", lambda *args, **kw: None)
    b = UI.PortfolioBuilder()
    original = b.current_spec()
    b.name.value = "Configuration personnalisée"
    b.frequency.value = "annual"
    b.cost.value = 25
    expected = b.current_spec()
    b.save_button.click()
    saved = b.saved.value
    assert C.load_spec(folder / saved).identity == expected.identity
    b.name.value = "Autre"
    b.frequency.value = "buy_hold"
    b.saved.value = saved
    b.load_button.click()
    assert b.current_spec().identity == expected.identity
    assert C.load_spec(folder / "mon_portefeuille_diversifie.json").identity == original.identity
    assert b.run_button.disabled
