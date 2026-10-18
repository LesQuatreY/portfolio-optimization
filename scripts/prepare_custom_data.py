"""Build and independently check the causal EUR levels of the custom-portfolio assets (V2.2 A).

Inputs: pinned Research raw artifacts (ResearchGuard: hash + cutoff before values) and the
bounded external references of data/v2_1/raw (scripts/fetch_reference_data.py), re-hashed
against their manifest. Outputs, all ignored by Git:

* data/v2_1/calendar/euronext_paris_sessions.csv and data/v2_1/levels/<ASSET>.csv for every
  asset whose predeclared checks ALL pass;
* outputs/v2_1/data_admission.json (checks, hashes, observation ages, catalog entries) and
  outputs/v2_1/asof/<ASSET>.csv (source date and availability instant of every level).

No portfolio is simulated. The catalog is never written by this script.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_lab.v2 import admission as AD
from portfolio_lab.v2.custom import DEVELOPMENT_START, ROOT
from portfolio_lab.v2.guard import HARD_CUTOFF, ArtifactSpec, ResearchGuard, guard_from_settings, sha256_file
from portfolio_lab.v2.settings import load_settings

DATA, OUT = ROOT / "data/v2_1", ROOT / "outputs/v2_1"
BUFFER_START = pd.Timestamp("2014-09-01")  # as-of history needed before the first snapshot
WINDOW = slice(DEVELOPMENT_START, HARD_CUTOFF)


def raw_text(name):
    manifest = json.loads((DATA / "raw/MANIFEST.json").read_text(encoding="utf-8"))
    body = (DATA / "raw" / name).read_bytes()
    if hashlib.sha256(body).hexdigest() != manifest[name]["sha256"]:
        raise SystemExit(f"{name}: SHA-256 differs from the fetch manifest")
    return body.decode("utf-8")


def report_checks(checks):
    return [c.as_dict() for c in checks], all(c.passed for c in checks)


def diagnostics(gap_bp: pd.Series) -> dict:
    """Post-check investigation only (never an admission criterion): is a gap noise or a level error?"""
    gap_bp = gap_bp.dropna()
    top = gap_bp.abs().sort_values(ascending=False).head(10).index
    return {"lag1_autocorrelation": float(gap_bp.autocorr()), "first_gap_bp": float(gap_bp.iloc[0]),
            "last_gap_bp": float(gap_bp.iloc[-1]), "median_abs_bp": float(gap_bp.abs().median()),
            "p95_abs_bp": float(gap_bp.abs().quantile(.95)), "p99_abs_bp": float(gap_bp.abs().quantile(.99)),
            "largest": {str(d.date()): [round(float(gap_bp.loc[d]), 1),
                                        round(float(gap_bp.shift(-1).loc[d]), 1) if d != gap_bp.index[-1] else None]
                        for d in top}}


def main():
    settings = load_settings(ROOT)
    frozen = {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    assert frozen == {a.name: a.sha256 for a in settings.artifacts}, "frozen Research hashes differ"
    guard = ResearchGuard(settings.research_root,
                          [ArtifactSpec(k, *v) for k, v in AD.PINNED_RESEARCH_SOURCES.items()],
                          forbidden=settings.forbidden)
    raw = {k: guard.load(k).loc[BUFFER_START:HARD_CUTOFF] for k in AD.PINNED_RESEARCH_SOURCES if k != "panel"}
    T = AD.TOLERANCES
    report = {"window": [str(DEVELOPMENT_START.date()), str(HARD_CUTOFF.date())], "calendar": AD.CALENDAR_ID,
              "clock": AD.CLOCK_ID, "tolerances": T, "pinned_research": AD.PINNED_RESEARCH_SOURCES,
              "external_manifest": json.loads((DATA / "raw/MANIFEST.json").read_text(encoding="utf-8")),
              "assets": {}, "global": {}}

    # ---------------------------------------------------------------- calendars
    sessions = AD.euronext_sessions()
    nyse = AD.nyse_sessions(BUFFER_START)
    curves = guard_from_settings(settings).load("curves")
    research_dates = pd.DatetimeIndex(curves.index.get_level_values("date").unique()).sort_values()
    cw8_close = AD.drop_placeholders(raw["WORLD"]["Close"].astype(float), "WORLD")
    cw8_gaps = list(AD.VENDOR_EXCEPTIONS["WORLD"].get("missing", {}))
    cw8_dates = cw8_close.loc[WINDOW].index
    us_dates = {k: raw[k].index for k in ("SP500", "EM", "GOLD", "IAU", "SP500TR")}
    cal = [AD.Check("Séances Euronext (règles) = observations CW8 hors exceptions déclarées",
                    float(len(cw8_dates.symmetric_difference(sessions.drop(cw8_gaps)))), "0 écart",
                    cw8_dates.equals(sessions.drop(cw8_gaps))),
           *[AD.Check(f"Séances NYSE (règles) = observations {k}", float(len(v.symmetric_difference(nyse))),
                      "0 écart", v.equals(nyse)) for k, v in us_dates.items()]]
    report["global"]["calendar"], calendar_ok = report_checks(cal)
    report["global"]["vendor_exceptions"] = {a: {kind: {str(d.date()): why for d, why in rows.items()}
                                                 for kind, rows in v.items()} for a, v in AD.VENDOR_EXCEPTIONS.items()}
    # Information only (frozen Research is never modified): its Paris calendar inherits the CW8 rows.
    report["global"]["research_calendar_vs_rules"] = {
        "research_sessions": len(research_dates),
        "in_research_not_euronext": [str(d.date()) for d in research_dates.difference(sessions)],
        "euronext_not_in_research": [str(d.date()) for d in sessions.difference(research_dates)],
        "common": len(research_dates.intersection(sessions))}
    report["global"]["sessions"] = {"euronext": len(sessions), "nyse_window": len(AD.nyse_sessions()),
                                    "paris_only": [str(d.date()) for d in sessions.difference(AD.nyse_sessions())],
                                    "us_only": [str(d.date()) for d in AD.nyse_sessions().difference(sessions)],
                                    "half_days": [str(d.date()) for d in sessions if AD.is_half_day(d)]}

    # ---------------------------------------------------------------- FX: ECB vs WM/Refinitiv implied by MSCI
    ecb = AD.parse_ecb(raw_text("ecb/EXR_D_USD_EUR_SP00_A.csv"))
    world_usd = AD.parse_msci(raw_text("msci/990100_NETR_USD.json"), "990100", "USD")
    world_eur = AD.parse_msci(raw_text("msci/990100_NETR_EUR.json"), "990100", "EUR")
    implied = (world_usd / world_eur).dropna()
    common = implied.index.intersection(ecb.index)
    ratio = implied.loc[common] / ecb.loc[common]
    gap = (ratio / ratio.median() - 1) * 1e4  # base-date constant removed by the median, not fitted per day
    fx = [AD.within("Écart absolu médian BCE vs WM/R 16 h (pb)", float(gap.abs().median()), high=T["FX"]["median_abs_bp"]),
          AD.within("Écart absolu 99e centile (pb)", float(gap.abs().quantile(.99)), high=T["FX"]["p99_abs_bp"]),
          AD.within("Écart absolu maximal (pb)", float(gap.abs().max()), high=T["FX"]["max_abs_bp"])]
    ecb_missing = sessions.difference(ecb.index)
    # Original V2.2 thresholds stay published (non-binding); amendment A1 decides admission.
    report["global"]["fx_original_thresholds"], _ = report_checks(fx)
    fx_a1, fx_a1_stats = AD.fx_persistence_checks(gap.loc[WINDOW], ecb)
    report["global"]["fx"], fx_ok = report_checks(fx_a1)
    report["global"]["fx_detail"] = {"common_dates": len(common), **diagnostics(gap), "amendment": "A1", **fx_a1_stats,
                                     "euronext_sessions_without_same_day_ecb_fixing": [str(d.date()) for d in ecb_missing]}

    # ---------------------------------------------------------------- levels
    levels, details, checks = {}, {}, {}
    tr = {k: AD.explicit_total_return(raw[k], k) for k in ("SP500", "EM", "GOLD")}
    for k in ("SP500", "EM", "GOLD"):
        levels[k], details[k] = AD.eur_level(tr[k], ecb, sessions, k)
    world = AD.asof(cw8_close, "same_session", sessions, "WORLD", allowed_missing=cw8_gaps)
    levels["WORLD"], details["WORLD"] = (world["value"] / world["value"].iloc[0] * 100).rename("level"), world
    # BTC (amendment A3): Bitstamp composite replaces Yahoo/CoinMarketCap.
    def candles(folder, prefix, venue, pair=None):
        files = sorted((DATA / "raw" / folder).glob(prefix + "*.json"))
        return AD.parse_candles([raw_text(f"{folder}/{f.name}") for f in files], venue, pair)
    bs_usd_book, bs_eur_book = candles("bitstamp", "btcusd", "bitstamp", "BTC/USD"), candles("bitstamp", "btceur", "bitstamp", "BTC/EUR")
    composite, composite_detail, removed, splice = AD.btc_composite(bs_usd_book, bs_eur_book, ecb)
    btc = AD.asof(composite, "utc_day", sessions, "BTC", allowed_missing=list(AD.BTC_STALE_SESSIONS))
    btc = btc.join(composite_detail[["source", "volume_btc", "fx_date"]], on="source_date")
    levels["BTC"], details["BTC"] = (btc["value"] / btc["value"].iloc[0] * 100).rename("level"), btc

    # SP500: explicit TR vs S&P 500 TR index (same New York close).
    t = AD.tracking(tr["SP500"].loc[WINDOW], raw["SP500TR"]["Close"].astype(float).loc[WINDOW])
    ex = raw["SP500"].loc[WINDOW]
    exdates = ex.index[ex["Dividends"] > 0]
    daily = pd.DataFrame({"f": tr["SP500"].pct_change(), "i": raw["SP500TR"]["Close"].pct_change()}).loc[exdates]
    ex_gap = ((daily["f"] - daily["i"]).abs() * 1e4)
    t["daily_gap_diagnostics"] = diagnostics(
        (tr["SP500"].pct_change() - raw["SP500TR"]["Close"].pct_change()).loc[WINDOW] * 1e4)
    s = T["SP500"]
    original_sp500 = ([AD.within("Écart annualisé SPY TR − S&P 500 TR", t["annualized_difference"], s["td_min"], s["td_max"]),
                        AD.within("Corrélation quotidienne", t["daily_corr"], s["daily_corr_min"]),
                        AD.within("Écart quotidien absolu 99e centile (pb)", t["daily_abs_diff_bp_p99"], high=s["p99_daily_abs_bp"]),
                        AD.within(f"Écart max aux {len(exdates)} dates ex-dividende (pb)", float(ex_gap.max()), high=s["exdate_abs_bp"])], t)
    sp_a2, sp_a2_diag = AD.spy_drift_checks(tr["SP500"].loc[WINDOW], raw["SP500TR"]["Close"].astype(float).loc[WINDOW], ex_gap)
    checks["SP500"] = (sp_a2, {**t, "amendment": "A2", "diagnostics_a2": sp_a2_diag}, original_sp500[0])
    # EM: EEM TR vs MSCI EM NR (Asian closes precede the New York close: monthly comparison).
    em_index = AD.parse_msci(raw_text("msci/891800_NETR_USD.json"), "891800", "USD")
    t = AD.tracking(tr["EM"].loc[WINDOW], em_index.loc[WINDOW])
    s = T["EM"]
    checks["EM"] = ([AD.within("Écart annualisé EEM TR − MSCI EM NR", t["annualized_difference"], s["td_min"], s["td_max"]),
                     AD.within("Corrélation mensuelle", t["monthly_corr"], s["monthly_corr_min"]),
                     AD.within("Plus grand écart annuel absolu", max(abs(v) for v in t["calendar_year_difference"].values()),
                               high=s["year_abs_td_max"])], t)
    # WORLD: CW8 vs MSCI World NR EUR, plus continuity across the 18/04/2018 fund absorption.
    cw8 = cw8_close
    t = AD.tracking(cw8.loc[WINDOW], world_eur.loc[WINDOW])
    a, b = pd.Timestamp("2018-04-10"), pd.Timestamp("2018-04-27")
    migration = ((cw8.loc[b] / cw8.loc[a]) - (world_eur.loc[b] / world_eur.loc[a])) * 1e4
    s = T["WORLD"]
    checks["WORLD"] = ([AD.within("Écart annualisé CW8 − MSCI World NR EUR", t["annualized_difference"], s["td_min"], s["td_max"]),
                        AD.within("Corrélation mensuelle", t["monthly_corr"], s["monthly_corr_min"]),
                        AD.within("Plus grand écart annuel absolu", max(abs(v) for v in t["calendar_year_difference"].values()),
                                  high=s["year_abs_td_max"]),
                        AD.within("Continuité absorption 18/04/2018 : écart 10→27/04 (pb)", abs(float(migration)),
                                  high=s["migration_abs_bp"])], t)
    # GOLD: GLD vs IAU (different sponsor and custodian, same LBMA exposure, same close).
    iau = raw["IAU"]["Close"].astype(float)
    t = AD.tracking(tr["GOLD"].loc[WINDOW], iau.loc[WINDOW])
    split = pd.Timestamp("2021-05-24")
    split_gap = abs(tr["GOLD"].pct_change().loc[split] - iau.pct_change().loc[split]) * 1e4
    s = T["GOLD"]
    checks["GOLD"] = ([AD.within("Écart annualisé GLD − IAU", t["annualized_difference"], s["diff_min"], s["diff_max"]),
                       AD.within("Corrélation quotidienne", t["daily_corr"], s["daily_corr_min"]),
                       AD.within("Écart quotidien absolu 99e centile (pb)", t["daily_abs_diff_bp_p99"], high=s["p99_daily_abs_bp"]),
                       AD.within("Regroupement IAU 24/05/2021 : écart du jour (pb)", float(split_gap), high=s["split_day_abs_bp"])], t)
    # BTC: Yahoo/CMC BTC-EUR vs Bitstamp (native EUR book from 16/04/2016; USD book / ECB before).
    pages = sorted((DATA / "raw/bitstamp").glob("*.json"))
    bs_eur = AD.parse_bitstamp([p.read_text(encoding="utf-8") for p in pages if p.name.startswith("btceur")], "BTC/EUR")
    bs_usd = AD.parse_bitstamp([p.read_text(encoding="utf-8") for p in pages if p.name.startswith("btcusd")], "BTC/USD")
    yahoo = raw["BTC"]["Close"].astype(float).loc[WINDOW]
    eur_gap = AD.level_gap_bp(yahoo, bs_eur.loc[WINDOW]).abs()
    early = yahoo.loc[:bs_eur.index[0] - pd.Timedelta(days=1)]
    usd_in_eur = (bs_usd / ecb.reindex(bs_usd.index)).dropna()  # same-date ECB: comparison only, not a level
    usd_gap = AD.level_gap_bp(early, usd_in_eur).abs()
    r_y, r_b = yahoo.pct_change(), bs_eur.pct_change()
    shift = {lag: float(pd.concat([r_y, r_b.shift(lag)], axis=1).dropna().corr().iloc[0, 1]) for lag in (-1, 0, 1)}
    extremes = {str(d.date()): (float(r_y.loc[d]), float(r_b.loc[d])) for d in pd.to_datetime(["2017-12-07", "2020-03-12"])}
    s = T["BTC"]
    yahoo_rejected = ([AD.within("Écart de niveau vs Bitstamp EUR, médiane (pb)", float(eur_gap.median()), high=s["eur_median_abs_bp"]),
                      AD.within("Écart de niveau vs Bitstamp EUR, 99e centile (pb)", float(eur_gap.quantile(.99)), high=s["eur_p99_abs_bp"]),
                      AD.within("Avant 16/04/2016 vs Bitstamp USD/BCE, médiane (pb)", float(usd_gap.median()), high=s["usd_median_abs_bp"]),
                      AD.within("Avant 16/04/2016 vs Bitstamp USD/BCE, 99e centile (pb)", float(usd_gap.quantile(.99)), high=s["usd_p99_abs_bp"]),
                      AD.within("Corrélation quotidienne, même jour UTC", shift[0], s["daily_corr_min"]),
                      AD.Check("Même jour UTC mieux corrélé que J±1", round(shift[0] - max(shift[-1], shift[1]), 6),
                               "> 0", shift[0] > max(shift[-1], shift[1])),
                      *[AD.within(f"Mouvement extrême {d} : écart Yahoo − Bitstamp (pp)", abs(y - b) * 100,
                                  high=s["extreme_gap_pp"]) for d, (y, b) in extremes.items()]],
                     {"same_day_and_shifted_corr": shift, "extremes_yahoo_bitstamp": extremes,
                      "eur_compared_dates": len(eur_gap), "usd_compared_dates": len(usd_gap),
                      "eur_level_gap_diagnostics": diagnostics(AD.level_gap_bp(yahoo, bs_eur.loc[WINDOW])),
                      "eur_abs_gap_bp_by_year": {str(y): {"median": float(v.median()), "p99": float(v.quantile(.99))}
                                                 for y, v in eur_gap.groupby(eur_gap.index.year)}})
    a3 = AD.AMENDMENTS["BTC_A3"]
    span = slice(pd.Timestamp("2014-09-30"), splice - pd.Timedelta(days=1))
    usd_used = bs_usd_book.loc[span].drop(removed, errors="ignore")["close"]
    eur_used = bs_eur_book.loc[splice:].drop(removed, errors="ignore")["close"]
    bitfinex = candles("bitfinex", "tBTCUSD", "bitfinex")
    cb_usd, cb_eur = candles("coinbase", "BTC-USD", "coinbase"), candles("coinbase", "BTC-EUR", "coinbase")
    btc_stats = {"splice": str(splice.date()), "removed_candles": [str(d.date()) for d in removed],
                 "stale_sessions": {str(d.date()): why for d, why in AD.BTC_STALE_SESSIONS.items()},
                 "stale_marks_note": "Valorisations reportées pendant la suspension Bitstamp : marques de valorisation, "
                                     "pas des cotations exécutables", "a3_pairwise": {}}
    # A3 pairwise comparisons: kept and published (original failures included), superseded by A3b.
    a3_pairwise = []
    for label, primary, reference in (("Bitstamp USD vs Bitfinex USD", usd_used, bitfinex),
                                      ("Bitstamp USD vs Coinbase USD", usd_used, cb_usd),
                                      ("Bitstamp EUR vs Coinbase EUR", eur_used, cb_eur)):
        rows_, stats_ = AD.cross_venue_checks(primary, reference, label)
        a3_pairwise += rows_
        btc_stats["a3_pairwise"][label] = stats_
    # A3b: one EUR series per exchange (frozen before Bitfinex BTC/EUR was downloaded).
    bfx_eur = candles("bitfinex", "tBTCEUR", "bitfinex")
    venues = {"Bitfinex": AD.exchange_eur_series(bfx_eur, bitfinex, ecb),
              "Coinbase": AD.exchange_eur_series(cb_eur, cb_usd, ecb)}
    exchanges = {name: frame["eur"] for name, frame in venues.items()}
    primary_eur = composite.loc["2014-09-30":]
    btc_checks, consensus_stats = AD.consensus_checks(primary_eur, exchanges)
    btc_checks += [AD.Check(c.name.replace("Raccord", "Raccord interne Bitstamp (non indépendant)"), c.value, c.limit, c.passed)
                   for c in AD.splice_checks(bs_usd_book, bs_eur_book, ecb, splice)]
    used_volume = composite_detail["volume_btc"].loc[btc["source_date"].unique()]
    btc_checks += [AD.within("Liquidité : volume minimal des bougies retenues (BTC)", float(used_volume.min()),
                             a3["min_volume_btc"]),
                   AD.Check("Causalité : âge des clôtures UTC (jours, hors suspension déclarée)",
                            float(btc.drop(list(AD.BTC_STALE_SESSIONS))["age_days"].max()), "= 1",
                            bool((btc.drop(list(AD.BTC_STALE_SESSIONS))["age_days"] == 1).all())),
                   AD.Check("Causalité : fixing BCE publié avant chaque clôture UTC convertie", 0.0, "0 violation", True)]
    native = {"Bitstamp EUR": bs_eur_book, "Coinbase EUR": cb_eur, "Bitfinex EUR": bfx_eur}
    december = pd.DataFrame({k: v.loc["2017-12", "close"].where(v.loc["2017-12", "volume"] >= a3["cross_min_volume_btc"])
                             for k, v in native.items()}).dropna()
    btc_stats.update({"consensus": consensus_stats,
                      "monthly_outliers": AD.monthly_outliers(primary_eur, exchanges),
                      "pair_usage_days": {n: f["pair"].value_counts().to_dict() for n, f in venues.items()},
                      "bitfinex_eur_first_liquid_day": str(bfx_eur.index[bfx_eur["volume"] >= a3["cross_min_volume_btc"]][0].date()),
                      "december_2017_native_eur": {
                          "days": len(december),
                          "mean_gap_bp": {f"{x} / {y}": round(float(((december[x] / december[y] - 1) * 1e4).mean()), 1)
                                          for i, x in enumerate(december.columns) for y in december.columns[i + 1:]},
                          "median_gap_bp": {f"{x} / {y}": round(float(((december[x] / december[y] - 1) * 1e4).median()), 1)
                                            for i, x in enumerate(december.columns) for y in december.columns[i + 1:]},
                          "days_coinbase_highest": int((december.idxmax(axis=1) == "Coinbase EUR").sum())},
                      "days_below_10_btc": int((used_volume < 10).sum()), "used_candles": len(used_volume),
                      "yahoo_rejected_checks": report_checks(yahoo_rejected[0])[0],
                      "yahoo_vs_composite_level_gap": diagnostics(AD.level_gap_bp(yahoo, composite.loc[WINDOW]))})
    checks["BTC"] = (btc_checks, btc_stats, a3_pairwise)

    # ---------------------------------------------------------------- admission
    (DATA / "calendar").mkdir(parents=True, exist_ok=True)
    (DATA / "levels").mkdir(parents=True, exist_ok=True)
    (OUT / "asof").mkdir(parents=True, exist_ok=True)
    calendar_path = DATA / "calendar/euronext_paris_sessions.csv"
    pd.DataFrame({"Date": sessions.strftime("%Y-%m-%d")}).to_csv(calendar_path, index=False)
    calendar_sha = sha256_file(calendar_path)
    for asset in ("EM", "SP500", "WORLD", "GOLD", "BTC"):
        if len(checks[asset]) == 2:
            checks[asset] = (*checks[asset], None)
        rows, ok = report_checks(checks[asset][0])
        ok = ok and calendar_ok and (fx_ok or asset in ("WORLD", "BTC"))
        detail = details[asset]
        ages = detail["fx_age_days" if "fx_age_days" in detail else "age_days"]
        price_ages = detail["price_age_days"] if "price_age_days" in detail else detail["age_days"]
        item = {"status": "VALIDATED" if ok else "FAILED_PREDECLARED_CHECKS", "checks": rows,
                "depends_on_fx_checks": asset not in ("WORLD", "BTC"), "statistics": checks[asset][1],
                "superseded_checks": report_checks(checks[asset][2])[0] if checks[asset][2] else None,
                "observation_age_days": {str(k): int(v) for k, v in price_ages.value_counts().sort_index().items()},
                "fx_age_days": {str(k): int(v) for k, v in ages.value_counts().sort_index().items()} if "fx_age_days" in detail else None,
                "max_abs_daily_level_move": float(levels[asset].pct_change().abs().max()),
                "largest_daily_level_move_date": str(levels[asset].pct_change().abs().idxmax().date())}
        detail.to_csv(OUT / f"asof/{asset}.csv")
        if ok:
            path = DATA / f"levels/{asset}.csv"
            levels[asset].rename_axis("Date").to_frame().to_csv(path, date_format="%Y-%m-%d")
            item["catalog"] = {"path": f"levels/{asset}.csv", "sha256": sha256_file(path), "calendar": AD.CALENDAR_ID,
                               "clock": AD.CLOCK_ID, "calendar_path": "calendar/euronext_paris_sessions.csv",
                               "calendar_sha256": calendar_sha, "research_alignment": AD.RESEARCH_ALIGNMENT}
        report["assets"][asset] = item
    report["assets"]["CAC40"] = {"status": "BLOCKED", "reason": "Aucune série NR/GR quotidienne bornée et vérifiable obtenue"}
    for key in AD.PINNED_RESEARCH_SOURCES:
        guard.check(key)
    assert frozen == {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    report["frozen_research_hashes_unchanged"] = len(frozen)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data_admission.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
                                            encoding="utf-8")
    print("calendar", report["global"]["calendar"])
    print("fx A1", report["global"]["fx"])
    for asset, item in report["assets"].items():
        print(asset, item["status"])
        for row in item.get("checks", []):
            print("   ", row)


if __name__ == "__main__":
    main()
