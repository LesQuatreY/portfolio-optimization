"""V2.2 Phase D: audit analytics (drawdown profile, compounding, bootstrap) and regression of the
reported six-benchmark metrics. Synthetic values, plus real paths when admitted data exist."""
import numpy as np
import pandas as pd
import pytest

from portfolio_lab.v2 import custom as C, custom_analytics as A, final_audit as F, metrics as M

DAYS = pd.bdate_range("2019-01-01", periods=5)


def test_drawdown_sign_order_and_recovery_by_hand():
    path = pd.Series([110.0, 90.0, 120.0, 100.0, 130.0], index=DAYS)
    p = F.drawdown_profile(path, 100)
    assert p["max_drawdown"] == pytest.approx(20 / 110) and p["max_drawdown"] > 0          # positive loss
    assert p["peak_date"] == str(DAYS[0].date()) and p["trough_date"] == str(DAYS[1].date())
    assert p["recovery_date"] == str(DAYS[2].date())                                         # first value >= peak
    assert DAYS[0] < DAYS[1] < DAYS[2]
    assert p["peak_to_trough_sessions"] == 1 and p["trough_to_recovery_sessions"] == 1
    never = F.drawdown_profile(pd.Series([95.0, 80.0, 90.0, 99.0, 99.9], index=DAYS), 100)
    assert never["peak_date"] == "capital initial" and never["recovery_date"] is None
    assert never["max_drawdown"] == pytest.approx(0.2)
    rising = F.drawdown_profile(pd.Series([101.0, 102, 103, 104, 105], index=DAYS), 100)
    assert rising["max_drawdown"] == 0 and rising["underwater_share"] == 0


def test_drawdown_matches_existing_helper_on_random_paths():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2015-01-01", periods=600)
    for _ in range(5):
        path = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 600))), index=idx)
        p = F.drawdown_profile(path, 100)
        assert p["max_drawdown"] == pytest.approx(float(-M.drawdown(path, 100).min()))
        assert p["trough_date"] == str(pd.Timestamp(M.recovery(path, 100)["maxdd_trough_date"]).date())
        if p["recovery_date"]:
            assert p["peak_date"] == "capital initial" or p["peak_date"] < p["trough_date"] < p["recovery_date"]


def test_period_returns_compound_to_the_total_and_count_observations():
    idx = pd.bdate_range("2020-01-01", "2020-12-31")
    path = pd.DataFrame({"x": 100 * np.exp(np.linspace(0, 0.3, len(idx)) + 0.02 * np.sin(np.arange(len(idx))))}, index=idx)
    for rule in (None, "W-FRI", "ME"):
        r = F.period_returns(path, 100, rule)
        assert np.prod(1 + r["x"]) == pytest.approx(path["x"].iloc[-1] / 100)
    vol = F.volatility_table(path, 100)
    assert vol.loc[("x", "Mensuel"), "observations"] == 12 and vol.loc[("x", "Quotidien"), "observations"] == len(idx)


def test_window_uses_previous_value_as_base():
    path = pd.Series([100.0, 110, 99, 121, 130], index=DAYS)
    s = F.window_stats(path, 100, DAYS[2], DAYS[3])
    assert s["return"] == pytest.approx(121 / 110 - 1) and s["local_max_drawdown"] == pytest.approx(0.1)


def test_bootstrap_is_reproducible_and_keeps_rows_aligned():
    idx = pd.bdate_range("2018-01-01", periods=300)
    rng = np.random.default_rng(1)
    v = pd.Series(100000 * np.exp(np.cumsum(rng.normal(0, 0.01, 300))), index=idx)
    paths = pd.DataFrame({"BRK.B": v, "copie": v, "autre": v ** 1.5 / v.iloc[0] ** 0.5})
    rate = pd.Series(0.0, index=idx)
    a, b = (F.block_bootstrap(paths, 100000, rate, 21, reps=200) for _ in range(2))
    assert a == b
    same = a["differences"]["BRK.B − copie"]
    assert same["vol_diff_ci95"] == [0.0, 0.0] and same["share_vol_diff_positive"] == 0.0


def test_risk_table_conventions():
    idx = pd.bdate_range("2019-01-01", periods=260)
    rng = np.random.default_rng(3)
    v = pd.Series(100000 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, 260))), index=idx)
    rate = pd.Series(0.01, index=idx)
    row = F.risk_table(v.to_frame("p"), 100000, rate).loc["p"]
    assert row["Calmar"] == pytest.approx(row["CAGR"] / row["MaxDD"])
    assert row["Sharpe (EUR)"] == pytest.approx(A.risk(v, 100000, rate=rate)["Sharpe (taux EUR Research)"])
    assert row["ES 5 % mensuelle"] >= row["VaR 5 % mensuelle"]  # tail mean loss >= quantile loss


@pytest.mark.skipif(not (C.ROOT / "data/v2_1/levels/BRK_B.csv").exists(), reason="données admises locales absentes")
def test_reported_six_benchmark_metrics_are_reproduced():
    from portfolio_lab.v2.bridge import load_lab
    original = C.load_spec(C.ROOT / "config/v2/portfolios/mon_portefeuille_diversifie.json")
    div = C.simulate(original, C.load_validated_panel(original))
    brk = A.benchmark_result("BRK_B")
    view = A.common_calendar(load_lab(C.ROOT), div.ledger.index)
    paths = pd.DataFrame({"BRK.B": brk.ledger.nav, "Diversifié": div.ledger.nav,
                          **{s: view.wealth[s] for s in ("N07", "D2_25", "B1", "B2")}})
    risk = F.risk_table(paths, 100000, view.eur_rate)
    reported = {"BRK.B": (0.124, 0.206, 0.296, 0.66), "Diversifié": (0.127, 0.139, 0.296, 0.91),
                "N07": (0.274, 0.256, 0.377, 1.06), "D2_25": (0.296, 0.289, 0.451, 1.02),
                "B1": (0.190, 0.206, 0.314, 0.93), "B2": (0.299, 0.397, 0.612, 0.85)}
    for name, (cagr, vol, mdd, sharpe) in reported.items():
        assert round(risk.loc[name, "CAGR"], 3) == pytest.approx(cagr, abs=1.5e-3)
        assert round(risk.loc[name, "Volatilité"], 3) == pytest.approx(vol, abs=1.5e-3)
        assert round(risk.loc[name, "MaxDD"], 3) == pytest.approx(mdd, abs=1.5e-3)
        assert round(risk.loc[name, "Sharpe (EUR)"], 2) == pytest.approx(sharpe, abs=1.5e-2)
    b, d = (F.drawdown_profile(paths[n], 100000) for n in ("BRK.B", "Diversifié"))
    assert b["max_drawdown"] != d["max_drawdown"] and (b["trough_date"], d["trough_date"]) == ("2020-03-24", "2020-03-23")
    assert len(paths) == 2368 and paths.index.max() == pd.Timestamp("2023-12-29")
