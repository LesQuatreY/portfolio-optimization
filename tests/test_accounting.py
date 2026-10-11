"""Portfolio accounting, execution timing and costs checked against hand-computed values.

Expected results are derived analytically from deterministic price paths, never from the engine.
"""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import portfolio_lab.robustness as robustness
from portfolio_lab.config import Asset, Config, WalkForwardSettings
from portfolio_lab.leverage import build_daily_leveraged_series
from portfolio_lab.metrics import compute_asset_metrics
from portfolio_lab.simulation import hold_returns, implemented_metrics, static_policy_returns


def frame(values, start="2015-01-01", freq="D"):
    return pd.DataFrame(values, index=pd.date_range(start, periods=len(next(iter(values.values()))), freq=freq))


# --- Holding mechanics -------------------------------------------------------------------------

def test_buy_and_hold_weights_drift_with_relative_prices():
    returns = frame({"A": [.10, .10, .10], "B": [0., 0., 0.]})
    gross, end = hold_returns(returns, pd.Series({"A": .5, "B": .5}), "annual")
    growth_a = 1.1 ** 3
    value = .5 * growth_a + .5
    assert end["A"] == pytest.approx(.5 * growth_a / value)
    assert end["B"] == pytest.approx(.5 / value)
    # Wealth is conserved before fees: compounding the portfolio returns gives sum_i w_i * G_i.
    assert (1 + gross).prod() == pytest.approx(value)
    # Day-by-day return = weighted average of asset returns with the *drifted* weights.
    w_a_day2 = .5 * 1.1 / (.5 * 1.1 + .5)
    assert gross.iloc[1] == pytest.approx(w_a_day2 * .10)


def test_constant_mix_is_rebalanced_every_observation():
    returns = frame({"A": [.10, -.20, .05], "B": [-.05, .10, 0.]})
    gross, end = hold_returns(returns, pd.Series({"A": .6, "B": .4}), "daily")
    np.testing.assert_allclose(gross, [.6 * .10 + .4 * -.05, .6 * -.20 + .4 * .10, .6 * .05])
    assert (1 + gross).prod() == pytest.approx(1.04 * .92 * 1.03)
    pd.testing.assert_series_equal(end, pd.Series({"A": .6, "B": .4}))


def test_one_asset_portfolio_equals_the_asset_less_initial_cost():
    prices = frame({"A": [100., 105., 98., 120.]})
    net, gross, trades = static_policy_returns(prices, pd.Series({"A": 1.}), cost_rate=.001)
    assert (1 + gross).prod() == pytest.approx(1.2)
    assert (1 + net).prod() == pytest.approx(1.2 * (1 - .001))
    assert trades.iloc[0] == pytest.approx(.5)


def test_annual_rebalance_costs_follow_the_drifted_trade():
    # Two calendar years; A doubles in year one then is flat; B is flat then rises 10%.
    dates = pd.to_datetime(["2014-12-31", "2015-06-30", "2015-12-31", "2016-06-30", "2016-12-30"])
    prices = pd.DataFrame({"A": [100., 150., 200., 200., 200.], "B": [100., 100., 100., 105., 110.]}, index=dates)
    c = .001
    net, gross, trades = static_policy_returns(prices, pd.Series({"A": .5, "B": .5}), cost_rate=c)
    # Initial purchase: notional 1. Year one: wealth 0.5*2 + 0.5*1 = 1.5, drifted weights 2/3, 1/3.
    # Year-end trade back to 50/50: notional |0.5-2/3| + |0.5-1/3| = 1/3. Year two growth: 0.5 + 0.5*1.1.
    expected = (1 - c) * 1.5 * (1 - c / 3) * (.5 + .5 * 1.1)
    assert (1 + net).prod() == pytest.approx(expected, rel=1e-14)
    assert (1 + gross).prod() == pytest.approx(1.5 * 1.05)
    np.testing.assert_allclose(trades.to_numpy(), [.5, 1 / 6])
    assert list(trades.index) == [dates[0], dates[2]]  # traded at the year-end closes


def test_costs_are_symmetric_for_buys_and_sells():
    returns = frame({"A": [0.], "B": [0.]})
    for held, target in ((pd.Series({"A": 1., "B": 0.}), pd.Series({"A": 0., "B": 1.})),
                         (pd.Series({"A": .2, "B": .8}), pd.Series({"A": .8, "B": .2}))):
        traded = (target - held).abs().sum()
        assert traded == pytest.approx(2 * abs(target["A"] - held["A"]))  # one sell + one buy
    gross, _ = hold_returns(returns, pd.Series({"A": .5, "B": .5}), "annual")
    assert gross.iloc[0] == 0


def test_no_cash_weights_must_be_fully_invested():
    returns = frame({"A": [.01], "B": [.02]})
    with pytest.raises(ValueError, match="sum to one"):
        hold_returns(returns, pd.Series({"A": .5, "B": .4}), "annual")


def test_leveraged_holding_is_buy_and_hold_of_the_daily_reset_nav():
    dates = pd.date_range("2015-01-01", periods=4)
    underlying = pd.Series([100., 110., 99., 108.9], index=dates, name="U")
    nav = build_daily_leveraged_series(underlying, 2.)
    # 1.2 * 0.8 * 1.2: daily reset path dependence, not 2x the underlying's total return (+8.9%).
    assert nav.iloc[-1] / nav.iloc[0] == pytest.approx(1.2 * .8 * 1.2)
    prices = pd.DataFrame({"U x2": nav, "U": underlying})
    net, _, _ = static_policy_returns(prices, pd.Series({"U x2": 1., "U": 0.}))
    assert (1 + net).prod() == pytest.approx(1.152)


def test_total_wipeout_is_absorbing():
    returns = frame({"A": [-1., .5, .5], "B": [-1., .2, .2]})
    gross, _ = hold_returns(returns, pd.Series({"A": .5, "B": .5}), "annual")
    np.testing.assert_allclose(gross, [-1., 0., 0.])


def test_implemented_metrics_compound_net_wealth_with_calendar_cagr():
    dates = pd.to_datetime(["2014-12-31", "2015-12-31", "2016-12-30"])
    prices = pd.DataFrame({"A": [100., 121., 121.], "B": [100., 100., 121.]}, index=dates)
    cfg = Config(assets=tuple(Asset(n, n, "s", "EUR", "Gross Return", "x") for n in "AB"),
                 walk_forward=WalkForwardSettings(transaction_cost_bps=0))
    metrics = implemented_metrics(prices, pd.DataFrame({"A": [.5], "B": [.5]}, index=["P"]), cfg)
    wealth = (.5 * 1.21 + .5) * (.5 + .5 * 1.21)  # rebalanced to 50/50 at the 2015 close
    years = (dates[-1] - dates[0]).days / 365.25
    assert metrics.loc["P", "CAGR"] == pytest.approx(wealth ** (1 / years) - 1)


def test_metrics_cagr_is_not_the_mean_of_annual_returns():
    dates = pd.to_datetime(["2014-12-31", "2015-12-31", "2016-12-31"])
    prices = pd.DataFrame({"X": [100., 150., 75.]}, index=dates)  # +50% then -50%
    cagr = compute_asset_metrics(prices).loc["X", "CAGR"]
    assert cagr < 0 and cagr == pytest.approx(.75 ** (365.25 / 731) - 1)


# --- End-to-end walk-forward timing with stubbed (known) weights -------------------------------

@pytest.fixture
def deterministic():
    dates = pd.bdate_range("2000-12-29", "2019-12-31")
    steps = np.arange(len(dates))
    prices = pd.DataFrame({"A": 100 * 1.0004 ** steps, "B": 100 * 0.9999 ** steps,
                           "M": 100 * 1.0002 ** steps}, index=dates)
    assets = tuple(Asset(n, n, "s", "EUR", "Gross Return", "x") for n in "ABM")
    cfg = Config(assets=assets, eligible=("A", "B"), benchmark="M",
                 walk_forward=WalkForwardSettings(first_test_year=2013, last_test_year=2015, rebalance="annual",
                                                  decision_lag_sessions=1, transaction_cost_bps=25))
    return prices, cfg


def stub_weights(monkeypatch, schedule, seen):
    def fake(train, config, risk_profiles=False, risk_parity=False):
        year = train.index[-1].year + 1
        seen[year] = (train.index[0], train.index[-1])
        w = pd.Series(schedule[year], index=train.columns)
        metrics = pd.DataFrame({k: [np.nan] * 2 for k in ("CAGR", "Volatility")}, index=list(robustness.OPTIMIZED))
        metrics["Fallback to Minimum Volatility"] = False
        return {name: w for name in robustness.OPTIMIZED}, metrics
    monkeypatch.setattr(robustness, "fit_policies", fake)


def test_walk_forward_timing_and_costs_match_hand_calculation(deterministic, monkeypatch):
    prices, cfg = deterministic
    schedule = {2013: [.7, .3], 2014: [.2, .8], 2015: [.5, .5]}
    seen = {}
    stub_weights(monkeypatch, schedule, seen)
    wf = robustness.walk_forward(prices, cfg)
    c = .0025
    idx = prices.index
    for year, (first, last) in seen.items():
        prior = idx[idx < pd.Timestamp(year=year, month=1, day=1)]
        # Estimation ends one session before the rebalance close (decision lag = 1)...
        assert last == prior[-2]
        # ...and the 10-year window starts at the return base just before its first year.
        assert first == idx[idx < pd.Timestamp(year=year - 10, month=1, day=1)][-1]
    # Hand-computed wealth path for "Maximum Sharpe" (stubbed weights).
    wealth, held = 1., np.zeros(2)
    for year, target in schedule.items():
        target = np.array(target)
        start = idx[idx < pd.Timestamp(year=year, month=1, day=1)][-1]   # rebalance close
        end = idx[idx < pd.Timestamp(year=year + 1, month=1, day=1)][-1]
        growth = (prices.loc[end, ["A", "B"]] / prices.loc[start, ["A", "B"]]).to_numpy()
        wealth *= 1 - c * np.abs(target - held).sum()
        value = target @ growth
        wealth *= value
        held = target * growth / value
        nav = wf.nav["Maximum Sharpe"]
        assert nav.loc[end] == pytest.approx(wealth, rel=1e-12)
        # The new allocation earns nothing before the rebalance close: the first return of the year
        # is measured from that close.
        first = wf.oos_returns.loc[str(year)].index[0]
        assert first == idx[idx > start][0]
    # Benchmark: bought once (one cost), then buy and hold.
    end = wf.nav.index[-1]
    expected = (1 - c) * prices.loc[end, "M"] / prices.loc[wf.nav.index[0], "M"]
    assert wf.nav["M"].iloc[-1] == pytest.approx(expected, rel=1e-12)


def test_rebalance_session_return_belongs_to_the_previous_holdings(deterministic, monkeypatch):
    prices, cfg = deterministic
    schedule = {2013: [1., 0.], 2014: [0., 1.], 2015: [0., 1.]}
    stub_weights(monkeypatch, schedule, {})
    base = robustness.walk_forward(prices, cfg)
    last_2013 = prices.index[prices.index.year == 2013][-1]
    shocked = prices.copy()
    shocked.loc[last_2013:, "A"] *= 1.5   # jump on the 2013 rebalance session, persists after
    after = robustness.walk_forward(shocked, cfg)
    # The jump is earned in 2013 (held 100% A until the close of the last 2013 session)...
    assert after.oos_returns.loc[last_2013, "Maximum Sharpe"] == pytest.approx(
        (1 + base.oos_returns.loc[last_2013, "Maximum Sharpe"]) * 1.5 - 1)
    # ...and none of it leaks into 2014, when B is held.
    pd.testing.assert_series_equal(after.oos_returns.loc["2014", "Maximum Sharpe"],
                                   base.oos_returns.loc["2014", "Maximum Sharpe"])


def test_daily_mode_is_explicitly_labelled_and_costs_only_target_changes(deterministic, monkeypatch):
    prices, cfg = deterministic
    cfg = replace(cfg, walk_forward=replace(cfg.walk_forward, rebalance="daily"))
    schedule = {2013: [.7, .3], 2014: [.7, .3], 2015: [.5, .5]}
    stub_weights(monkeypatch, schedule, {})
    wf = robustness.walk_forward(prices, cfg)
    assert wf.settings.rebalance == "daily"
    np.testing.assert_allclose(wf.trading["Maximum Sharpe"].to_numpy(), [.5, 0., .2])
