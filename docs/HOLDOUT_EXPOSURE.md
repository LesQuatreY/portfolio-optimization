# Prior exposure of the 2020+ final holdout

**Status: the final holdout (every date on or after 2020-01-01) is locked in code** (`src/portfolio_lab/protocol.py`). It is reserved for a future, separately authorized final evaluation. It is **not** scientifically pristine.

## What was exposed before the lock (introduced 2026-10-11)

Before the lock, the project routinely used data through early October 2026:

* `Config.end` defaulted to `2026-10-05`; `portfolio_robustness.ipynb` used those defaults and displayed full-sample, subperiod (2011-2020, 2021-latest) and walk-forward results for test years 2011-2026, with a written interpretation of them.
* The README reported a Bayes-Stein versus sample-mean walk-forward comparison computed on data through 2026-10-02.
* Executed notebooks, CSV/Markdown reports and market snapshots in `outputs/` and `.cache/` covered 2020-2026.
* The research team has read some of these results. Decisions taken since (asset universe, estimators, leverage) may therefore reflect 2020-2026 information.

Consequences: an evaluation on 2020-2026 can no longer be described as a genuinely untouched out-of-sample test. At best it is a reserved period with known exposure; a prospective test needs observations after the lock date or another demonstrably untouched dataset.

## What was done (non-destructive)

* Legacy outputs, the two notebooks as they were (with their outputs) and every market snapshot extending past 2019-12-31 were **moved** (not deleted) to `.cache/legacy-quarantine/20261011/` (git-ignored). Git history is unchanged and still contains the earlier committed notebook outputs and README text.
* Active notebooks were rebuilt without outputs; their figures were not consulted to design the new protocol.
* README statements quoting 2020-2026 performance were removed; their figures are intentionally not repeated anywhere in the active documentation.
* Technical guards (configuration, providers, price validation, walk-forward calendars, exports, executed-notebook scan, tests) make normal use of the holdout impossible.

## Not covered by the lock

The lock protects the package's data paths and outputs. It cannot prevent hand-written code that downloads data directly (for example `notebooks/archive/draft.ipynb`, the original notebook kept as regression evidence, which contains direct downloads through 2026). That archive is not a research entry point.
