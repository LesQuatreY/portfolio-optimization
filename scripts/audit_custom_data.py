"""Read-only, offline audit of six pinned development artifacts; no Research imports.

Does not admit data to the simulator, repair prices, or calculate portfolio performance.
Only Lab outputs/v2_1 is writable. ResearchGuard checks hashes and cutoff before values.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_lab.v2.custom import DEVELOPMENT_START, ROOT
from portfolio_lab.v2.guard import ArtifactSpec, ResearchGuard, sha256_file
from portfolio_lab.v2.settings import load_settings

# References: DV2 FREEZE_DV2_PROTOCOL dv1_snapshot (panel, SPY, CW8);
# DV1-frozen V11 raw manifest (EEM, GLD, QQQ); V7 data manifest (BTC).
SOURCES = {
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
}


def main():
    settings = load_settings(ROOT)
    frozen = {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    assert frozen == {a.name: a.sha256 for a in settings.artifacts}
    guard = ResearchGuard(settings.research_root,
                          [ArtifactSpec(k, *v) for k, v in SOURCES.items()],
                          forbidden=settings.forbidden)
    frames = {key: guard.load(key) for key in SOURCES}
    # No Research engine, builder or cleaning routine is imported or executed.
    panel = frames.pop("panel").loc[DEVELOPMENT_START:settings.cutoff, list(frames)]
    report = {"window": ["2014-10-01", "2023-12-29"], "admitted_to_backtest": False,
              "sources": {k: {"path": p, "sha256": h} for k, (p, h) in SOURCES.items()},
              "panel_rows": len(panel), "assets": {}}
    implied_fx = {}
    for asset, raw in frames.items():
        raw = raw.loc[DEVELOPMENT_START:settings.cutoff]
        close = raw["Close"].astype(float)
        item = {"raw_rows": len(raw), "panel_rows": int(panel[asset].notna().sum()),
                "first": str(raw.index.min().date()), "last": str(raw.index.max().date()),
                "duplicate_dates": int(raw.index.duplicated().sum()),
                "sorted_dates": bool(raw.index.is_monotonic_increasing),
                "invalid_close": int((~np.isfinite(close) | (close <= 0)).sum()),
                "invalid_panel": int((~np.isfinite(panel[asset]) | (panel[asset] <= 0)).sum()),
                "raw_dates_outside_panel": len(raw.index.difference(panel.index)),
                "panel_dates_without_raw_observation": [str(d.date()) for d in panel.index.difference(raw.index)],
                "max_raw_gap_days": int(raw.index.to_series().diff().dt.days.max()),
                "zero_panel_changes": int(panel[asset].diff().eq(0).sum()),
                "raw_close_moves_over_25pct": [str(d.date()) for d in close.index
                                                if abs(close.pct_change(fill_method=None).loc[d]) > .25]}
        if "AdjClose" in raw:
            adj = raw["AdjClose"].astype(float)
            item["invalid_adjclose"] = int((~np.isfinite(adj) | (adj <= 0)).sum())
        for field in ("Dividends", "Stock Splits", "Capital Gains"):
            if field in raw:
                item[field] = {str(d.date()): float(v) for d, v in raw[field].items() if v != 0}
        # Independent arithmetic, SAME vendor: this is not external price corroboration.
        if asset in ("EM", "SP500", "GOLD"):
            cash = raw["Dividends"].astype(float)
            if "Capital Gains" in raw:
                cash = cash + raw["Capital Gains"].astype(float)
            growth = (close + cash) / close.shift(1)
            growth.iloc[0] = 1  # normalization anchor, not an imputed return
            tr = growth.cumprod(skipna=False)
            adj = raw["AdjClose"].astype(float)
            relative = (tr / tr.iloc[0]) / (adj / adj.iloc[0]) - 1
            item["max_abs_explicit_tr_vs_adjclose_relative"] = float(relative.abs().max())
            fx = (tr / panel[asset].reindex(tr.index)).dropna()
            implied_fx[asset] = fx / fx.iloc[0]
        elif asset == "WORLD":
            overlap = panel.index.intersection(close.index)
            ratio = panel.loc[overlap, asset] / close.loc[overlap]
            item["panel_differs_from_raw_close_dates"] = [str(d.date()) for d in ratio.index
                                                          if abs(ratio.loc[d] - 1) > 1e-10]
            # Detect the documented future-neighbor cleaning rule; do NOT apply it.
            prior, following = close.shift(1), close.shift(-1)
            jump = close / prior - 1
            flags = (jump.abs() > .08) & ((following / prior - 1).abs() < .25 * jump.abs())
            item["future_neighbor_cleaning_candidates"] = [str(d.date()) for d in close.index[flags]]
        else:
            item["panel_equals_raw_on_panel_dates"] = bool(np.array_equal(
                panel[asset].to_numpy(), close.reindex(panel.index).to_numpy()))
        report["assets"][asset] = item
    fx_frame = pd.DataFrame(implied_fx).dropna()
    report["implied_normalized_fx_max_spread"] = float(
        (fx_frame.max(axis=1) - fx_frame.min(axis=1)).abs().max())
    report["limitations"] = [
        "Same-vendor arithmetic is not an independent market-data check.",
        "US-calendar panel carries observations; no common execution clock is attested.",
        "FX source/fixing timestamps and historical corrections are not independently certified.",
        "BTC date labels alone do not certify when the close was available.",
        "CAC40 remains unavailable; no substitute or portfolio return is calculated."]
    for key in SOURCES:
        guard.check(key)
    assert frozen == {a.name: sha256_file(settings.research_root / a.path) for a in settings.artifacts}
    report["frozen_research_hashes_unchanged"] = len(frozen)
    out = ROOT / "outputs/v2_1/custom_data_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(out)
    for asset, item in report["assets"].items():
        print(asset, json.dumps({k: v for k, v in item.items()
                               if k not in ("Dividends", "Stock Splits", "Capital Gains")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
