"""V2.2 Phase C data admission for Berkshire Hathaway B (BRK-B), offline.

Inputs (data/v2_1/raw, ignored by Git, SHA-256 checked against MANIFEST.json): Yahoo BRK-B and BRK-A
fetched by the bounded adapter (2014-09-01..2023-12-29), the Nasdaq.com BRK.B history and the ECB
EUR/USD file. Checks: tolerances AMENDMENTS["BRK_A6"], frozen before any BRK request. Only when
every check passes and --update-catalog is given, the EUR level (NYSE close available before the
Paris snapshot / ECB fixing published, same convention as SPY) is written to data/v2_1/levels/
BRK_B.csv and the BRK_B entry of config/v2/custom_benchmarks.yaml becomes ``validated``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import pandas as pd

from portfolio_lab.v2 import admission as AD
from portfolio_lab.v2.custom import ROOT
from portfolio_lab.v2.guard import sha256_file

DATA, OUT = ROOT / "data/v2_1", ROOT / "outputs/v2_2"
FILES = {"b": "yahoo/BRK-B_2014-09-01_2023-12-29.csv", "a": "yahoo/BRK-A_2014-09-01_2023-12-29.csv",
         "vendor": "nasdaq/BRK.B_2014-09-01_2023-12-29.json", "ecb": "ecb/EXR_D_USD_EUR_SP00_A.csv",
         "ten_k": "sec/berkshire_10k_2015_price_ranges.json"}


def raw(name: str) -> bytes:
    manifest = json.loads((DATA / "raw/MANIFEST.json").read_text(encoding="utf-8"))
    body = (DATA / "raw" / name).read_bytes()
    if hashlib.sha256(body).hexdigest() != manifest[name]["sha256"]:
        raise SystemExit(f"{name}: SHA-256 differs from the manifest")
    AD.assert_text_before_cutoff(body.decode("utf-8", "replace"), name)
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-catalog", action="store_true")
    args = parser.parse_args()
    frames = {k: pd.read_csv(pd.io.common.BytesIO(raw(FILES[k])), index_col=0, parse_dates=True) for k in ("b", "a")}
    vendor = AD.parse_nasdaq_history(raw(FILES["vendor"]).decode("utf-8"))
    ecb = AD.parse_ecb(raw(FILES["ecb"]).decode("utf-8"))
    ranges = json.loads(raw(FILES["ten_k"]).decode("utf-8"))["ranges"]
    # A6-bis (owner-approved post-hoc revision) decides; the 12 original A6 checks stay in the audit.
    checks, stats, original = AD.validate_brk_bis(frames["b"], frames["a"], vendor, ranges)
    sessions = AD.euronext_sessions()
    level, detail = AD.eur_level(frames["b"]["Close"].astype(float), ecb, sessions, "BRK-B")
    validated = all(c.passed for c in checks)
    report = {"status": "VALIDATED" if validated else "FAILED_A6_BIS_CHECKS", "methodology": "A6-bis (révision a posteriori approuvée)",
              "tolerances_a6_bis": AD.AMENDMENTS["BRK_A6_BIS"], "tolerances_a6_original": AD.AMENDMENTS["BRK_A6"],
              "checks": [c.as_dict() for c in checks], "statistics": stats,
              "original_a6_checks": [c.as_dict() for c in original],
              "original_a6_status": "VALIDATED" if all(c.passed for c in original) else "FAILED",
              "asof_age_days": {str(k): int(v) for k, v in detail["price_age_days"].value_counts().sort_index().items()},
              "sessions": len(sessions), "inputs": FILES}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "brk_admission.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "checks")}, ensure_ascii=False, indent=1))
    if not args.update_catalog:
        return
    if not validated:
        raise SystemExit("Catalogue inchangé : contrôles A6-bis non conformes.")
    path = DATA / "levels/BRK_B.csv"
    level.rename_axis("Date").to_frame().to_csv(path, date_format="%Y-%m-%d")
    calendar = DATA / "calendar/euronext_paris_sessions.csv"
    catalog = ROOT / "config/v2/custom_benchmarks.yaml"
    text = catalog.read_text(encoding="utf-8")
    block = re.search(r"(?ms)^  BRK_B:\n.*?(?=^  \w+:\n|\Z)", text).group(0)
    keep = {k: re.search(rf"(?m)^    {k}: (.*)$", block).group(1) for k in ("label", "cost_bps", "source", "dividends", "kind")}
    summary = " ; ".join(f"{c.name} {c.value:.4g}" for c in checks if not isinstance(c.value, str))
    new = (f"  BRK_B:\n    label: {keep['label']}\n    status: validated\n    currency: EUR\n    cost_bps: {keep['cost_bps']}\n"
           f"    source: {keep['source']}\n    dividends: {keep['dividends']}\n    kind: {keep['kind']}\n"
           f"    independent_check: \"{summary}\"\n    calendar: {AD.CALENDAR_ID}\n    clock: {AD.CLOCK_ID}\n"
           f"    research_alignment: {AD.RESEARCH_ALIGNMENT}\n    path: levels/BRK_B.csv\n    sha256: {sha256_file(path)}\n"
           f"    calendar_path: calendar/euronext_paris_sessions.csv\n    calendar_sha256: {sha256_file(calendar)}\n"
           f"    reason: \"Validé selon A6-bis (révision a posteriori approuvée) ; A6 d'origine publié : 2 critères A/B non conformes\"\n")
    catalog.write_text(text.replace(block, new), encoding="utf-8")
    print("Catalogue des références mis à jour : BRK_B validé.")


if __name__ == "__main__":
    main()
