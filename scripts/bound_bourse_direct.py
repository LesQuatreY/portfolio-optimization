"""Date-first bounding of a user-supplied Bourse Direct export (owner authorization of 18/10/2026).

For each line only the text before the first ';' (the date) is read. A line dated outside
2014-10-01..2023-12-29 is discarded WITHOUT splitting or converting its other fields; post-cutoff
lines are only counted. In-window lines are copied verbatim to a bounded file under
data/v2_1/raw/cac40/ (ignored by Git). The original is opened read-only and its SHA-256 is
checked unchanged afterwards. No market value is parsed here.

    .venv\\Scripts\\python.exe -B scripts/bound_bourse_direct.py <export.csv> <label>
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

from portfolio_lab.v2.custom import DEVELOPMENT_START, ROOT
from portfolio_lab.v2.guard import HARD_CUTOFF, sha256_file

HEADER = "Date;Open;High;Low;Close;Volume;Currency"


def main():
    source, label = Path(sys.argv[1]), sys.argv[2]
    before = sha256_file(source)
    kept, counts, times = [], {"before_window": 0, "after_cutoff": 0, "in_window": 0}, set()
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        header = handle.readline().strip()
        if header != HEADER:
            raise SystemExit(f"En-tête inattendu : {header[:80]}")
        for line in handle:
            if not line.strip():
                continue
            stamp = line[:line.index(";")].strip().strip("\"")
            day = pd.Timestamp(datetime.strptime(stamp, "%Y/%m/%d %H:%M").date())
            if day > HARD_CUTOFF:
                counts["after_cutoff"] += 1      # never split, never converted
                continue
            if day < DEVELOPMENT_START:
                counts["before_window"] += 1
                continue
            counts["in_window"] += 1
            times.add(stamp[11:])
            kept.append(line.rstrip("\r\n"))
    if sha256_file(source) != before:
        raise SystemExit("Le fichier d'origine a changé pendant la lecture.")
    out_dir = ROOT / "data/v2_1/raw/cac40"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{label}_2014-10-01_2023-12-29.csv"
    body = (HEADER + "\n" + "\n".join(kept) + "\n").encode("utf-8")
    target.write_bytes(body)
    record = {"source_name": source.name, "source_sha256": before, "source_bytes": source.stat().st_size,
              "bounded_file": target.name, "bounded_sha256": hashlib.sha256(body).hexdigest(),
              "window": [str(DEVELOPMENT_START.date()), str(HARD_CUTOFF.date())], "lines": counts,
              "time_of_day_values_in_window": sorted(times),
              "method": "date-first: text before the first ';' only; out-of-window lines discarded unparsed",
              "authorization": "Propriétaire, 18/10/2026", "bounded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (out_dir / f"{label}_BOUNDING.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
