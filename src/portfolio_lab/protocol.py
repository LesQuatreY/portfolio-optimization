"""Research protocol: chronological boundaries and the technical lock on the final holdout.

Every date boundary is an exclusive upper bound (``date < boundary``).

* Development period: data before ``DEVELOPMENT_END`` (2001-2012 in practice). Free
  exploration, in-sample frontier analysis and model development.
* Validation period: calendar years ``VALIDATION_FIRST_YEAR``..``VALIDATION_LAST_YEAR``
  (2013-2019), used only as walk-forward evaluation years.
* Final holdout: every date on or after ``HOLDOUT_START`` (2020-01-01). LOCKED.

The lock is enforced in code, not by convention: configurations, providers, price
validation (and therefore every return, metric, optimizer, walk-forward and bootstrap
computation) and exported outputs reject any observation dated on or after
``HOLDOUT_START``. There is deliberately no flag, environment variable or keyword that
lifts it. A future final evaluation must be a separate, explicitly authorized change of
this module, reviewed on its own.

Known limitation: results covering 2020-2026 were viewed by the research team before
this lock existed (see docs/HOLDOUT_EXPOSURE.md). The holdout is therefore a reserved
period with known prior exposure, not a pristine out-of-sample test.
"""
from __future__ import annotations

from pathlib import Path
import json
import re

import pandas as pd

HOLDOUT_START = pd.Timestamp("2020-01-01")
DEVELOPMENT_END = pd.Timestamp("2013-01-01")
VALIDATION_FIRST_YEAR = 2013
VALIDATION_LAST_YEAR = 2019
# Default exclusive end of every research data request: the holdout start itself.
RESEARCH_END = HOLDOUT_START.date().isoformat()

LEGACY_EXPOSURE_NOTE = (
    "Results covering 2020-2026 were viewed before the holdout lock was introduced; "
    "this period is reserved but not scientifically pristine."
)


class HoldoutAccessError(RuntimeError):
    """Raised whenever code would read, compute on or export locked holdout dates."""


def assert_end_allowed(end, context: str = "Study end") -> pd.Timestamp:
    """An exclusive end date must not reach past the holdout start."""
    try:
        timestamp = pd.Timestamp(end)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: invalid date {end!r}.") from exc
    if pd.isna(timestamp):
        raise ValueError(f"{context}: invalid date {end!r}.")
    if timestamp > HOLDOUT_START:
        raise HoldoutAccessError(
            f"{context} {timestamp.date()} is after the locked holdout start {HOLDOUT_START.date()} "
            "(exclusive end). The 2020+ final holdout cannot be used in research.")
    return timestamp


def assert_dates_before_holdout(index, context: str = "Data") -> None:
    """Reject any date on or after the holdout start (DatetimeIndex, Series or DataFrame index)."""
    if isinstance(index, (pd.Series, pd.DataFrame)):
        index = index.index
    if not isinstance(index, pd.DatetimeIndex) or not len(index):
        return
    latest = index.max()
    if pd.notna(latest) and latest >= HOLDOUT_START:
        raise HoldoutAccessError(
            f"{context} contains dates up to {latest.date()}, on or after the locked holdout start "
            f"{HOLDOUT_START.date()}. The 2020+ final holdout cannot be used in research.")


# ISO dates (2020-01-01, 2020/01/01) and bare years 2020-2099 inside date-like contexts.
_ISO_DATE = re.compile(r"(?<!\d)(20[2-9]\d)[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])(?!\d)")


def find_holdout_dates(text: str) -> list[str]:
    """ISO-formatted dates on or after the holdout start found in text (sorted, unique)."""
    found = {match.group(0) for match in _ISO_DATE.finditer(text)}
    # The boundary itself (an exclusive end, never a trading session) may be named.
    return sorted(date for date in found if pd.Timestamp(date.replace("/", "-")) > HOLDOUT_START)


def notebook_holdout_dates(path: Path) -> list[str]:
    """Holdout dates in a notebook's *outputs* (sources may legitimately name the boundary)."""
    notebook = json.loads(Path(path).read_text(encoding="utf-8"))
    texts = []
    for cell in notebook.get("cells", []):
        for output in cell.get("outputs", []):
            texts.append(json.dumps(output, ensure_ascii=False))
    return find_holdout_dates("\n".join(texts))


def assert_notebook_outputs_safe(path: Path) -> None:
    dates = notebook_holdout_dates(path)
    if dates:
        raise HoldoutAccessError(f"{path}: outputs contain locked holdout dates, e.g. {dates[:5]}.")


def assert_file_safe(path: Path) -> None:
    """Exported text/CSV/JSON/HTML outputs must not contain holdout dates."""
    path = Path(path)
    if path.suffix.lower() == ".ipynb":
        assert_notebook_outputs_safe(path)
        return
    if path.suffix.lower() not in {".csv", ".json", ".md", ".txt", ".html", ".jsonl", ".log"}:
        return
    dates = find_holdout_dates(path.read_text(encoding="utf-8", errors="ignore"))
    if dates:
        raise HoldoutAccessError(f"{path}: contains locked holdout dates, e.g. {dates[:5]}.")
