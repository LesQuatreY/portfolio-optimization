"""Import bridge: frozen Portfolio Research artifacts -> ``StrategyLab`` (read-only, guarded).

Nothing is simulated here and nothing is written to Portfolio Research. Every file goes through
``guard.ResearchGuard`` (allow-list, SHA-256, 2023-12-29 cutoff). The integrated portfolios, their
definitions and frozen configurations come from ``FROZEN_STRATEGY_MANIFEST.csv``; the configuration
hashes are recomputed with Research's canonical form and compared with the manifest and with
config/v2/lab.yaml. Reference metrics are Research's own (``historical_master_v11_2.csv``); the
derived quantities below are simple arithmetic on them or on the frozen daily curves.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import metrics as M
from .guard import IntegrityError, ResearchGuard, guard_from_settings
from .settings import LabSettings, load_settings

ROLLING = ("r3", "r5", "vol1", "vol3", "sh1", "sh3", "mdd3")
CRISIS_COLUMNS = ("Q4_2018_change", "Q4_2018_mdd", "COVID_2020_change", "COVID_2020_mdd", "BEAR_2022_change",
                  "BEAR_2022_mdd", "covid_recovery_sessions")
CLASS_FR = {"ROBUST ENOUGH TO RETAIN FOR FURTHER VALIDATION": "Retenue pour validation",
            "PROMISING BUT FRAGILE": "Prometteuse mais fragile",
            "WEAK OR UNATTRACTIVE RELATIVE TO AVAILABLE ALTERNATIVES": "Faible / peu attractive",
            "INCONCLUSIVE / INSUFFICIENT EVIDENCE": "Non concluante"}
PROVENANCE_FR = {"observe": "Observé", "proxy": "Proxy", "synthetique": "Synthétique", "comptable": "Liquidités"}
EXIT_TAXES = ("tax_exit_pea", "tax_exit_cto", "tax_exit_btc", "tax_exit_av")
INTERIM_TAXES = ("tax_interim_cto", "tax_interim_btc")


def canonical_config(c: dict) -> dict:
    """Research's canonical configuration (v11_1/inventory_v11_1.canon), hashed into config_sha256."""
    p = dict(c["policy"])
    p.setdefault("arch", "MIX")
    p.setdefault("reserve", "R1")
    if p["type"] == "D1":
        p.setdefault("band", 0.0)
    return {"policy": dict(sorted(p.items())), "div": dict(sorted(c.get("div", {}).items())),
            "mm": round(float(c.get("mm", 0.0)), 6), "rebal": c.get("rebal", "Q"), "gold": c["gold"],
            "gold_band": list(c["gold_band"]), "btc": c["btc"], "btc_threshold": c["btc_threshold"],
            "btc_floor": round(float(c["btc_floor"]), 6), "mm_fee": c.get("mm_fee")}


def config_sha256(c: dict) -> str:
    return hashlib.sha256(json.dumps(canonical_config(c), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class StrategyLab:
    """Everything the V2 interface shows, loaded once from the frozen Research artifacts."""
    settings: LabSettings
    ids: tuple[str, ...]
    meta: pd.DataFrame                 # one row per portfolio: labels, frozen config, provenance
    reference: pd.DataFrame            # Research metrics, unchanged (historical_master_v11_2.csv)
    summary: pd.DataFrame              # reference metrics + derived bases and recovery statistics
    curves: dict                       # field -> DataFrame (date x portfolio), frozen daily curves
    rolling: dict                      # r3, r5, vol1, vol3, sh1, sh3, mdd3 -> DataFrame (date x portfolio)
    calendar: pd.DataFrame             # portfolio x calendar year (2014 T4 = partial quarter)
    regimes: pd.DataFrame              # portfolio x market regime
    chrono: pd.DataFrame               # Research chronological summary
    crises: pd.DataFrame               # post-2014 crisis episodes only
    classification: pd.DataFrame
    periods: dict                      # FULL / DEV / EVAL / regime windows from protocol_v11_2.json
    eur_rate: pd.Series                # EUR overnight rate used by Research's Sharpe ratios
    cards: dict                        # French strategy descriptions (explorer V11.3)
    holdings: pd.DataFrame             # portfolio x line: held at least once
    guard_report: pd.DataFrame
    lines: pd.DataFrame = field(repr=False)   # instrument metadata (config/v2/instruments.yaml)

    @property
    def strategies(self) -> list[str]:
        return [s for s in self.ids if self.meta.loc[s, "kind"] == "strategy"]

    @property
    def benchmarks(self) -> list[str]:
        return [s for s in self.ids if self.meta.loc[s, "kind"] == "benchmark"]

    @property
    def wealth(self) -> pd.DataFrame:
        return self.curves["total"]

    @property
    def initial(self) -> float:
        return self.settings.initial_capital

    @property
    def period(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        return self.wealth.index[0], self.wealth.index[-1]

    def returns(self) -> pd.DataFrame:
        return self.wealth.apply(lambda v: M.path_returns(v, self.initial))

    def ordered(self, ids) -> list[str]:
        """Known ids in display order (unknown ids dropped)."""
        wanted = set(ids)
        return [s for s in self.ids if s in wanted]


def _wide(frame: pd.DataFrame, column: str, ids) -> pd.DataFrame:
    return frame[column].unstack("strategy").reindex(columns=list(ids))


def _manifest_rows(manifest: pd.DataFrame, settings: LabSettings) -> pd.DataFrame:
    man = manifest.set_index("strategy")
    rows = {}
    for spec in settings.strategies:
        if spec.id not in man.index:
            raise IntegrityError(f"{spec.id} : absent du manifeste gelé FROZEN_STRATEGY_MANIFEST.csv.")
        r = man.loc[spec.id]
        cfg = json.loads(r["config_json"])
        recomputed = config_sha256(cfg)
        if recomputed != r["config_sha256"]:
            raise IntegrityError(f"{spec.id} : la configuration du manifeste ne correspond plus à son empreinte.")
        if recomputed != spec.config_sha256:
            raise IntegrityError(f"{spec.id} : configuration gelée différente de celle attendue par "
                                 "config/v2/lab.yaml (empreinte config_sha256).")
        rows[spec.id] = {"config": cfg, **r.to_dict()}
    return pd.DataFrame.from_dict(rows, orient="index")


def _lines(settings: LabSettings) -> pd.DataFrame:
    return pd.DataFrame([vars(line) for line in settings.lines]).set_index("column")


def build_lab(settings: LabSettings, guard: ResearchGuard | None = None) -> StrategyLab:
    guard = guard or guard_from_settings(settings)
    report = guard.report()                       # every gate runs before any value is read
    ids = settings.ids
    initial = settings.initial_capital

    manifest = _manifest_rows(guard.load("manifest"), settings)
    master = guard.load("master").set_index("Unnamed: 0").rename_axis("strategy")
    missing = [s for s in ids if s not in master.index]
    if missing:
        raise IntegrityError(f"Métriques de référence absentes pour {missing} (historical_master_v11_2.csv).")
    reference = master.loc[list(ids)].copy()

    raw_curves = guard.load("curves")
    absent = [s for s in ids if s not in raw_curves.index.get_level_values("strategy")]
    if absent:
        raise IntegrityError(f"Courbes quotidiennes absentes pour {absent} (curves_FULL.parquet).")
    curves = {c: _wide(raw_curves, c, ids) for c in raw_curves.columns}
    total = curves["total"]
    if total.isna().any().any() or total.index[0] != settings.start or total.index[-1] != settings.cutoff:
        raise IntegrityError("Les courbes gelées n'ont pas toutes la même plage de dates "
                             f"{settings.start.date()} → {settings.cutoff.date()}.")
    lines = _lines(settings)
    for column in lines.index:
        curves[column] = curves[column].fillna(0.0) if column in curves else pd.DataFrame(0.0, total.index, list(ids))
    components = sum(curves[c] for c in lines.index)
    gap = (components - total).abs().max().max()
    if gap > 1e-6:
        raise IntegrityError(f"Les lignes de config/v2/instruments.yaml ne recomposent pas la valeur totale (écart {gap:.2e} €).")

    market = guard.load("market")
    eur_rate = market["eur_rate"].reindex(total.index)
    roll = guard.load("rolling")
    rolling = {m: _wide(roll, m, ids) for m in ROLLING}
    calendar = guard.load("calendar").set_index("strategy").reindex(list(ids))
    regimes = guard.load("regimes").pivot(index="strategy", columns="regime", values="return").reindex(list(ids))
    chrono = guard.load("chrono").set_index("strategy").reindex(list(ids))
    crises = guard.load("crises").set_index("strategy").reindex(list(ids))[list(CRISIS_COLUMNS)]
    classification = guard.load("classification").set_index("strategy")
    protocol = guard.load("protocol")
    cards = guard.load("cards")

    holdings = pd.DataFrame({c: (curves[c].abs() > 1e-9).any() for c in lines.index}).reindex(list(ids))
    meta = _meta(settings, manifest, reference, classification, cards, holdings, lines, curves, total)
    summary = _summary(reference, curves, total, eur_rate, initial)
    periods = {k: protocol["periods"][k] for k in ("FULL", "DEV", "EVAL", "regimes")}
    return StrategyLab(settings=settings, ids=tuple(ids), meta=meta, reference=reference, summary=summary,
                       curves=curves, rolling=rolling, calendar=calendar, regimes=regimes, chrono=chrono,
                       crises=crises, classification=classification, periods=periods, eur_rate=eur_rate,
                       cards={s: cards[s] for s in ids if s in cards}, holdings=holdings, guard_report=report,
                       lines=lines)


def _meta(settings, manifest, reference, classification, cards, holdings, lines, curves, total) -> pd.DataFrame:
    rows = []
    for spec in settings.strategies:
        sid = spec.id
        held = [c for c in lines.index if holdings.loc[sid, c]]
        reconstructed = [c for c in held if lines.loc[c, "provenance"] in ("proxy", "synthetique")]
        share = (sum(curves[c][sid] for c in reconstructed) / total[sid]).mean() if reconstructed else 0.0
        status = "Observé" if not reconstructed else (
            "Proxy partiel" if any(lines.loc[c, "provenance"] == "proxy" for c in reconstructed) else "Synthétique partiel")
        cls = classification["classification_rule"].get(sid) if sid in classification.index else None
        rows.append({
            "id": sid, "kind": spec.kind, "type": "Stratégie" if spec.kind == "strategy" else "Référence",
            "role": spec.role, "name": cards.get(sid, {}).get("nom", sid),
            "research_role": manifest.loc[sid, "role"], "source_version": manifest.loc[sid, "source_version"],
            "engine": str(reference.loc[sid, "source"]), "config_sha256": manifest.loc[sid, "config_sha256"],
            "fingerprint": manifest.loc[sid, "fingerprint_v11_1"], "composition": manifest.loc[sid, "composition"],
            "policy": manifest.loc[sid, "policy"], "rebalancing": manifest.loc[sid, "rebalancing"],
            "accounts": manifest.loc[sid, "accounts"], "config": manifest.loc[sid, "config"],
            "classification": CLASS_FR.get(cls, cls) if cls else "Référence (non classée)",
            "data_status": status, "reconstructed_lines": tuple(reconstructed), "reconstructed_share": float(share),
            "held_lines": tuple(held),
            "period": f"{settings.start.date().isoformat()} → {settings.cutoff.date().isoformat()}",
            "currency": settings.currency, "initial_capital": settings.initial_capital,
        })
    return pd.DataFrame(rows).set_index("id")


def _summary(reference: pd.DataFrame, curves: dict, total: pd.DataFrame, eur_rate: pd.Series, initial: float) -> pd.DataFrame:
    n_years = M.years(total.index)
    rows = {}
    for sid in total.columns:
        ref = reference.loc[sid]
        v = total[sid]
        path = M.path_metrics(v, initial, eur_rate)
        rec = M.recovery(v, initial)
        final_value = float(v.iloc[-1])
        exit_taxes = float(sum(ref[c] for c in EXIT_TAXES))
        interim_taxes = float(sum(ref[c] for c in INTERIM_TAXES))
        after_sale = float(ref["terminal_net"]) + exit_taxes           # = Research pre_liquidation_value
        path_fees = float(curves["cum_friction"][sid].iloc[-1] + curves["cum_custody"][sid].iloc[-1])
        rows[sid] = {
            # three measurement bases
            "cagr_gross": float(ref["cagr_gross"]), "cagr_after_costs": float(ref["cagr_after_costs"]),
            "cagr_path": path["cagr_path"], "cagr_net": float(ref["FULL_cagr"]),
            "terminal_gross": M.terminal_from_cagr(float(ref["cagr_gross"]), initial, n_years),
            "terminal_after_costs": M.terminal_from_cagr(float(ref["cagr_after_costs"]), initial, n_years),
            "final_value": final_value, "value_after_sale": after_sale, "terminal_net": float(ref["terminal_net"]),
            # daily-path risk (Research reference values)
            "arith_return": float(ref["arith_return"]), "volatility": float(ref["volatility"]),
            "sharpe": float(ref["sharpe"]), "sortino": float(ref["sortino"]), "max_drawdown": float(ref["FULL_mdd"]),
            "worst_12m": float(ref["worst_12m"]), "longest_underwater_sessions": int(ref["longest_underwater_sessions"]),
            "underwater_share": path["underwater_share"], **rec,
            # costs and taxes (Research accounting, EUR)
            "trading_friction": float(ref["trading_friction"]), "custody": float(ref["custody"]),
            "fees_total": float(ref["fees_total"]), "fees_in_path": path_fees,
            "liquidation_costs": final_value - after_sale,
            "tax_interim_cto": float(ref["tax_interim_cto"]), "tax_interim_btc": float(ref["tax_interim_btc"]),
            "interim_taxes": interim_taxes, "taxes_in_path": float(curves["cum_tax"][sid].iloc[-1]),
            **{c: float(ref[c]) for c in EXIT_TAXES}, "exit_taxes": exit_taxes, "taxes_total": float(ref["taxes_total"]),
            # activity and exposure
            "orders": int(ref["orders"]), "turnover_per_year": float(ref["turnover_per_year"]),
            "ndx_expo_mean": float(ref["ndx_expo_mean"]), "ndx_expo_max": float(ref["ndx_expo_max"]),
            # chronological windows (separate Research runs, EUR 100k at each window start)
            "dev_cagr": float(ref["DEV_cagr"]), "dev_mdd": float(ref["DEV_mdd"]),
            "eval_cagr": float(ref["EVAL_cagr"]), "eval_mdd": float(ref["EVAL_mdd"]),
        }
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "strategy"
    return out


@lru_cache(maxsize=4)
def _cached(settings: LabSettings) -> StrategyLab:
    return build_lab(settings)


def load_lab(project_dir: Path | None = None) -> StrategyLab:
    """Reuse parsed results, but revalidate settings and every artifact on each opening."""
    from .settings import find_project_dir
    settings = load_settings(find_project_dir(project_dir).resolve())
    guard_from_settings(settings).report()
    return _cached(settings)
