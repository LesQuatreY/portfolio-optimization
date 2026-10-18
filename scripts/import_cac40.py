"""Admit a user-supplied CAC 40 total-return history (V2.2 Phase A). Offline, no fetching.

Two routes, by order of preference (docs/V2_2_DATA_ADMISSION.md, section 7):

1. Official index, NR QS0011131826 or GR QS0011131834, checked against the price index
   FR0003500008 (or the other TR variant):

    .venv\\Scripts\\python.exe -B scripts/import_cac40.py --isin QS0011131826 --export NR.csv \\
        --format investing --date-order mdy --decimal . --reference PX1.csv \\
        --reference-isin FR0003500008 --provider "Investing.com (export manuel)" --license "..."

2. ETF proxy FR0007052782 (unadjusted closes) + TWO independent distribution ledgers
   (CSV: ex_date,amount_eur) + the price index + issuer NAV anchors (date,nav_eur; >= 2 per year)
   + the prospectus distribution count + declared corporate actions (date,ratio,description;
   header only = none). Amendment A4. Distributions are reinvested at ex-date close:

    ... --isin FR0007052782 --export ETF.csv --distributions amundi.csv \\
        --distributions-check parqet.csv --reference PX1.csv --reference-isin FR0003500008 \\
        --nav-anchors vl.csv --distributions-per-year 1 --corporate-actions operations.csv ...

Every file is scanned for dates after 2023-12-29 BEFORE any value is read (both dd/mm and mm/dd
readings) and refused if one is found: exports must be bounded to 2014-10-01..2023-12-29 at the
source, never trimmed afterwards. The price index is never admitted as a total return.
--update-catalog rewrites the CAC40 entry of config/v2/custom_assets.yaml only when every check
passes. Raw files are kept under data/v2_1/raw/cac40/ (ignored by Git).
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import shutil

import pandas as pd

from portfolio_lab.v2 import admission as AD
from portfolio_lab.v2.custom import DataUnavailable, ROOT
from portfolio_lab.v2.guard import sha256_file

DATA = ROOT / "data/v2_1"


def read_text(path: Path) -> str:
    text = path.read_bytes().decode("utf-8-sig")
    AD.assert_text_before_cutoff(text, path.name)  # before any value is parsed
    return text


def read_levels(path: Path, fmt: str, isin: str | None, date_order: str, decimal: str):
    text = read_text(path)
    if fmt == "euronext":
        found, series = AD.parse_euronext_export(text)
        if isin and isin != found:
            raise DataUnavailable(f"{path.name} : ISIN {found} dans le fichier, {isin} déclaré.")
        return found, series
    if not isin:
        raise SystemExit(f"{path.name} : export sans ISIN (Investing.com, Bourse Direct) ; --isin requis.")
    if fmt == "bourse-direct":
        return isin, AD.parse_bourse_direct_export(text)
    if fmt == "csv":  # e.g. data/v2_1/raw/yahoo/FCHI_*.csv (bounded adapter output): Date, Close
        frame = pd.read_csv(io.StringIO(text), index_col="Date", parse_dates=True)
        return isin, frame["Close"].astype(float).rename("level")
    return isin, AD.parse_investing_export(text, date_order, decimal)


def catalog_block(isin, provider, license_, checks, sha, calendar_sha, raw_sha):
    if isin == AD.CAC40_ETF_ISIN:
        label, kind = "proxy ETF FR0007052782", "ETF proxy CAC 40 distribuant, pas l'indice officiel NR/GR"
        dividends = "Distributions réinvesties à la clôture ex-date ; registre recoupé par deux sources ; frais ETF incorporés"
    else:
        label, kind = AD.CAC40_TR_ISINS[isin], "Indice officiel Euronext"
        dividends = "Dividendes nets de retenue réinvestis (NR)" if isin.endswith("26") else "Dividendes bruts réinvestis (GR)"
    summary = " ; ".join(f"{c.name} {c.value:.4g}" for c in checks if not isinstance(c.value, str))
    return (f"  CAC40:\n    label: CAC 40 — {label}\n    status: validated\n    currency: EUR\n"
            f"    source: {provider}, {isin}, export SHA-256 {raw_sha[:12]}…, licence : {license_}\n"
            f"    dividends: {dividends}\n    kind: {kind}\n    independent_check: {summary}\n"
            f"    calendar: {AD.CALENDAR_ID}\n    clock: {AD.CLOCK_ID}\n"
            f"    research_alignment: {AD.RESEARCH_ALIGNMENT}\n    path: levels/CAC40.csv\n    sha256: {sha}\n"
            f"    calendar_path: calendar/euronext_paris_sessions.csv\n    calendar_sha256: {calendar_sha}\n"
            f"    reason: Validé par scripts/import_cac40.py\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--format", choices=("euronext", "investing", "bourse-direct", "csv"), default="euronext")
    parser.add_argument("--isin")
    parser.add_argument("--date-order", choices=("dmy", "mdy"), default="dmy")
    parser.add_argument("--decimal", choices=(".", ","), default=".")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--reference-format", choices=("euronext", "investing", "bourse-direct", "csv"))
    parser.add_argument("--reference-isin")
    parser.add_argument("--distributions", type=Path)
    parser.add_argument("--distributions-check", type=Path)
    parser.add_argument("--nav-anchors", type=Path, help="CSV date,nav_eur (rapports de l'émetteur)")
    parser.add_argument("--distributions-per-year", type=int, help="Politique du prospectus")
    parser.add_argument("--corporate-actions", type=Path, help="CSV date,ratio,description (vide = aucune)")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--corrections", help="Clé OFFICIAL_CORRECTIONS pour l'export (ex. CAC40_BOURSE_DIRECT)")
    parser.add_argument("--reference-corrections", help="Clé OFFICIAL_CORRECTIONS pour la référence (ex. FCHI_YAHOO)")
    parser.add_argument("--update-catalog", action="store_true")
    args = parser.parse_args()
    calendar = DATA / "calendar/euronext_paris_sessions.csv"
    if not calendar.exists():
        raise SystemExit("Calendrier absent : exécuter d'abord scripts/prepare_custom_data.py")
    isin, series = read_levels(args.export, args.format, args.isin, args.date_order, args.decimal)
    reference = None
    if args.reference:
        reference = read_levels(args.reference, args.reference_format or args.format, args.reference_isin,
                                args.date_order, args.decimal)
    if isin == AD.CAC40_ETF_ISIN:
        if not args.distributions:
            raise SystemExit("Voie ETF : --distributions requis (registre ex_date,amount_eur).")
        ledger = AD.parse_distributions(read_text(args.distributions), args.distributions.name)
        check = AD.parse_distributions(read_text(args.distributions_check), args.distributions_check.name) \
            if args.distributions_check else None
        if reference is not None and reference[0] != AD.CAC40_PRICE_ISIN:
            raise SystemExit("Voie ETF : la référence doit être l'indice prix FR0003500008.")
        anchors = AD.parse_nav_anchors(read_text(args.nav_anchors), args.nav_anchors.name) if args.nav_anchors else None
        events = AD.parse_corporate_actions(read_text(args.corporate_actions), args.corporate_actions.name)             if args.corporate_actions else None
        levels, checks, validated = AD.validate_cac40_etf(series, ledger, check, reference[1] if reference else None,
                                                           anchors, args.distributions_per_year, events)
    else:
        vendor = "CAC40_BOURSE_DIRECT" if args.format == "bourse-direct" else None
        # Raw files first: published, never used for the decision when corrections are declared.
        _, raw_checks, raw_validated = AD.validate_cac40(isin, series, reference, vendor=vendor)
        corrections = []
        if args.corrections:
            series, done = AD.apply_official_corrections(series, args.corrections)
            corrections += [{"series": "export", **d} for d in done]
        if args.reference_corrections and reference is not None:
            corrected, done = AD.apply_official_corrections(reference[1], args.reference_corrections)
            reference = (reference[0], corrected)
            corrections += [{"series": "reference", **d} for d in done]
        levels, checks, validated = AD.validate_cac40(isin, series, reference, vendor=vendor)
    raw_dir = DATA / "raw/cac40"
    raw_dir.mkdir(parents=True, exist_ok=True)
    inputs = {"export": args.export, "reference": args.reference, "distributions": args.distributions,
              "distributions_check": args.distributions_check, "nav_anchors": args.nav_anchors,
              "corporate_actions": args.corporate_actions}
    hashes = {}
    for role, path in inputs.items():
        if path:
            hashes[role] = sha256_file(path)
            shutil.copyfile(path, raw_dir / f"{role}_{hashes[role][:16]}{path.suffix}")
    (DATA / "levels").mkdir(parents=True, exist_ok=True)
    path = DATA / "levels/CAC40.csv"
    (levels / levels.iloc[0] * 100).rename_axis("Date").to_frame().to_csv(path, date_format="%Y-%m-%d")
    report = {"isin": isin, "route": "etf_proxy" if isin == AD.CAC40_ETF_ISIN else "official_index",
              "provider": args.provider, "license": args.license, "format": args.format,
              "inputs_sha256": hashes, "reference_isin": reference[0] if reference else None,
              "levels_sha256": sha256_file(path), "sessions": len(levels),
              "checks": [c.as_dict() for c in checks],
              "status": "VALIDATED" if validated else "PENDING_INDEPENDENT_CHECK"}
    if isin != AD.CAC40_ETF_ISIN:
        report.update({"official_corrections": corrections, "raw_checks_before_corrections": [c.as_dict() for c in raw_checks],
                       "raw_status_before_corrections": "VALIDATED" if raw_validated else "FAILED"})
    out = ROOT / "outputs/v2_1/cac40_import.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.update_catalog:
        if not validated:
            raise SystemExit("Catalogue inchangé : contrôle indépendant manquant ou non conforme.")
        catalog = ROOT / "config/v2/custom_assets.yaml"
        text = catalog.read_text(encoding="utf-8")
        block = catalog_block(isin, args.provider, args.license, checks, report["levels_sha256"],
                              sha256_file(calendar), hashes["export"])
        new, count = re.subn(r"(?ms)^  CAC40:\n.*?(?=^  \w+:\n|\Z)", block, text)
        if count != 1:
            raise SystemExit("Entrée CAC40 introuvable dans le catalogue.")
        catalog.write_text(new, encoding="utf-8")
        print("Catalogue mis à jour : CAC40 validé.")


if __name__ == "__main__":
    main()
