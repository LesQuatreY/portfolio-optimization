"""Lightweight, append-only registry of every walk-forward evaluation on the validation years.

Each entry records what was evaluated (full configuration snapshot, code version) and what
was observed (net OOS metrics), successful or not. Re-running an identical configuration
on identical code is recorded as a rerun of the earlier entry, so the count of *distinct*
configurations evaluated on 2013-2019 stays visible: the more configurations are compared
on the same years, the more the best one is expected to overstate its future performance.

Each entry carries a category, declared by the caller:

* "baseline"       the configuration in config/research.yaml as committed to before the run;
* "pre-registered" a variant or check written down (with its hypothesis) before its results existed;
* "exploratory"    anything else; such results must not drive selection without a fresh test;
* "correction"     a rerun required by a methodological fix (hypothesis = what was fixed);
* "selection"      a final model-selection decision (hypothesis = the criterion, declared beforehand).

Investor preferences (caps, eligibility) are configuration: changing them yields a new configuration
fingerprint, and `decision_log` shows what changed between successive baseline runs.

A rerun is an identical configuration on identical code (commit + hash of uncommitted changes).
The same configuration on changed code "supersedes" the earlier entry: results may differ because
of a correction, and both stay in the log.

Timestamps use the compact UTC form YYYYMMDDTHHMMSSZ.
"""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import subprocess

import pandas as pd

from .protocol import assert_dates_before_holdout

DEFAULT_REGISTRY = Path("experiments/registry.jsonl")
CATEGORIES = ("baseline", "pre-registered", "exploratory", "correction", "selection")
# Categories whose `hypothesis` text is mandatory (the question, the fix or the selection criterion).
NEEDS_HYPOTHESIS = ("pre-registered", "correction", "selection")
# Assumptions tracked by the decision log (keys of the snapshot's engine config).
TRACKED = ("eligible", "benchmark", "leverage", "max_weights", "min_weights", "covariance_method",
           "expected_return_method", "targets", "risk_free_rate", "risk_free_series", "financing_series",
           "leverage_annual_fee", "leverage_financing_rate", "leverage_financing_spread", "holding_costs",
           "walk_forward")
_METRICS = ("CAGR", "Volatility annualized", "Sharpe", "Max Drawdown", "CAGR excluding best year",
            "Gross CAGR (before costs)", "Mean traded turnover")


def code_version(project_dir: Path) -> dict:
    """Git commit and whether tracked files had uncommitted changes (None when unavailable)."""
    def git(*args):
        try:
            done = subprocess.run(["git", *args], cwd=project_dir, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout.strip() if done.returncode == 0 else None
    commit = git("rev-parse", "--short", "HEAD")
    status = git("status", "--porcelain", "--untracked-files=no")
    # Uncommitted state of the engine itself (tracked diff + untracked package files), so two runs on
    # different uncommitted code are never mistaken for reruns.
    diff = git("diff", "HEAD", "--", "src", "config") or ""
    untracked = git("ls-files", "--others", "--exclude-standard", "--", "src", "config") or ""
    contents = "".join((project_dir / name).read_text(encoding="utf-8", errors="ignore")
                       for name in sorted(untracked.split()) if (project_dir / name).is_file())
    state = hashlib.sha256((diff + untracked + contents).encode()).hexdigest()[:12] if commit else None
    return {"commit": commit, "dirty": None if status is None else bool(status), "worktree_hash": state}


def _metrics(result) -> dict:
    table = result.summary()
    return {name: {k: (None if pd.isna(row[k]) else float(row[k])) for k in _METRICS if k in row}
            for name, row in table.iterrows()}


def record_experiment(result, research, *, label: str, notes: str = "", project_dir: Path | None = None,
                      registry: Path | None = None, kind: str = "walk_forward", category: str = "exploratory",
                      hypothesis: str = "") -> dict:
    """Append one evaluation (or a rerun marker) to the registry and return the entry."""
    if category not in CATEGORIES:
        raise ValueError(f"Experiment category must be one of {CATEGORIES}.")
    if category in NEEDS_HYPOTHESIS and not hypothesis.strip():
        raise ValueError(f"A '{category}' entry needs its hypothesis (question, fix or criterion), "
                         "written before the run.")
    assert_dates_before_holdout(result.oos_returns.index, "Recorded experiment")
    project_dir = Path(research.config.output_dir).parent if project_dir is None else Path(project_dir)
    registry = project_dir / DEFAULT_REGISTRY if registry is None else Path(registry)
    snapshot = research.snapshot()
    # What was actually evaluated (may differ from the file: universe variants, methods, checks).
    if getattr(result, "config", None) is not None:
        evaluated = asdict(result.config)
        evaluated.pop("cache_dir"), evaluated.pop("output_dir")
        snapshot["config"] = json.loads(json.dumps(evaluated, default=str))
    snapshot["evaluated_universe"] = list(result.universe)
    snapshot["policies"] = list(result.strategies)
    snapshot["benchmark"] = result.benchmark
    snapshot["walk_forward_used"] = asdict(result.settings) if result.settings is not None else None
    version = code_version(project_dir)
    configuration = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:12]
    evaluation = evaluation_fingerprint(snapshot)
    metrics = _metrics(result)
    # Same evaluation = same result-determining inputs (engine config, evaluated universe, policies,
    # benchmark, walk-forward settings), whatever the label, the variant list or the provenance text.
    history = [entry for entry in load_entries(registry) if entry.get("kind") not in NOTE_KINDS]
    same = [entry for entry in history if evaluation_fingerprint(entry["snapshot"]) == evaluation]
    seen = {fp for entry in history for fp in strategy_fingerprints(entry["snapshot"]).values()}
    new_strategies = [name for name, fp in strategy_fingerprints(snapshot).items() if fp not in seen]
    previous = [entry for entry in same if entry.get("code") == version]
    superseded = [entry for entry in same if entry.get("code") != version]
    entry = {
        "id": f"{pd.Timestamp.now(tz='UTC'):%Y%m%dT%H%M%SZ}-{configuration[:6]}",
        "evaluation": evaluation,
        "timestamp_utc": f"{pd.Timestamp.now(tz='UTC'):%Y%m%dT%H%M%SZ}",
        "kind": kind, "label": label, "notes": notes, "configuration": configuration,
        "code": version, "category": category, "hypothesis": hypothesis,
        "rerun_of": previous[0]["id"] if previous else None,
        "supersedes": superseded[-1]["id"] if superseded and not previous else None,
        # True when this configuration had already been evaluated (any code version): its validation
        # result is then previously exposed evidence, not a new look.
        "previously_evaluated": bool(same),
        # Strategies never evaluated before under identical result-determining inputs.
        "new_strategies": new_strategies,
        "validation_years": [f.test_year for f in result.folds],
        "snapshot": snapshot, "metrics": metrics,
    }
    registry.parent.mkdir(parents=True, exist_ok=True)
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


RESULT_KEYS = ("config", "evaluated_universe", "policies", "benchmark", "walk_forward_used")
_LEVERAGE_KEYS = ("leverage_annual_fee", "leverage_financing_rate", "leverage_financing_spread", "financing_series")
# Fields added after some registry entries were written, with the value equivalent to their absence.
_LEGACY_DEFAULTS = {"growth_drift": "sample", "resampling_draws": 0, "min_weights": [], "holding_costs": [],
                    "risk_free_series": None,
                    "financing_series": [], "leverage_financing_spread": 0.}


def _result_inputs(snapshot: dict) -> dict:
    """Normalized inputs that determine a walk-forward result, comparable across registry versions.

    Eligibility and leverage are carried by the evaluated universe (labels include the factor), so
    the research-level `eligible`/`leverage` fields are dropped; leverage costs only matter when a
    leveraged label is evaluated; investor bounds and holding costs only for evaluated names; the
    walk-forward settings actually used replace the configured ones.
    """
    config = dict(snapshot.get("config") or {})
    universe = list(snapshot.get("evaluated_universe") or [])
    benchmark = snapshot.get("benchmark")
    for key in ("eligible", "leverage", "walk_forward", "cache_dir", "output_dir"):
        config.pop(key, None)
    for key, default in _LEGACY_DEFAULTS.items():
        if key in config and config[key] == default:
            config.pop(key)
    if not any(" x" in name for name in universe):
        for key in _LEVERAGE_KEYS:
            config.pop(key, None)
    for key in ("max_weights", "min_weights"):
        config[key] = [entry for entry in config.get(key) or [] if entry[0] in universe]
    config["holding_costs"] = [entry for entry in config.get("holding_costs") or []
                               if entry[0] in set(universe) | {benchmark}]
    return {"config": config, "evaluated_universe": universe, "benchmark": benchmark,
            "walk_forward_used": snapshot.get("walk_forward_used")}


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:12]


def evaluation_fingerprint(snapshot: dict) -> str:
    """Hash of the inputs that determine a walk-forward result (recomputable for old entries)."""
    return _hash({**_result_inputs(snapshot), "policies": snapshot.get("policies")})


def strategy_fingerprints(snapshot: dict) -> dict[str, str]:
    """One fingerprint per evaluated strategy: a strategy's result does not depend on the others."""
    inputs = _result_inputs(snapshot)
    names = list(snapshot.get("policies") or []) + ([inputs["benchmark"]] if inputs["benchmark"] else [])
    return {name: _hash({**inputs, "strategy": name}) for name in names}


def load_entries(registry: Path) -> list[dict]:
    registry = Path(registry)
    if not registry.exists():
        return []
    return [json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines() if line.strip()]


def exposure_history(registry: Path) -> dict[str, dict]:
    """Recompute, in log order, whether each result entry repeated an earlier evaluation and which of its
    strategies were new. Uses the current fingerprint rules (stored flags reflect the rules of their time)."""
    seen_runs, seen_strategies, out = set(), set(), {}
    for entry in load_entries(registry):
        if entry.get("kind") in NOTE_KINDS:
            continue
        run = evaluation_fingerprint(entry["snapshot"])
        strategies = strategy_fingerprints(entry["snapshot"])
        out[entry["id"] + "|" + entry["label"]] = {
            "previously_evaluated": run in seen_runs,
            "new_strategies": [name for name, fp in strategies.items() if fp not in seen_strategies]}
        seen_runs.add(run)
        seen_strategies.update(strategies.values())
    return out


def registry_summary(registry: Path) -> pd.DataFrame:
    """One row per recorded evaluation (French labels); exposure flags recomputed chronologically."""
    rows = []
    exposure = exposure_history(registry)
    for entry in load_entries(registry):
        if entry.get("kind") in NOTE_KINDS:
            rows.append({"Identifiant": entry["id"], "Libellé": entry["label"], "Type": entry["kind"],
                         "Catégorie": entry.get("category"), "Configuration": "—",
                         "Commit": (entry.get("code") or {}).get("commit"), "Relance de": "—", "Remplace": "—",
                         "Univers évalué": "—"})
            continue
        rows.append({"Identifiant": entry["id"], "Libellé": entry["label"], "Type": entry["kind"],
                     "Catégorie": entry.get("category", "non renseignée"),
                     "Configuration": entry["configuration"], "Commit": (entry.get("code") or {}).get("commit"),
                     "Relance de": entry.get("rerun_of") or "—", "Remplace": entry.get("supersedes") or "—",
                     "Déjà évaluée": "oui" if exposure[entry["id"] + "|" + entry["label"]]["previously_evaluated"]
                     else "non",
                     "Nouvelles stratégies": ", ".join(exposure[entry["id"] + "|" + entry["label"]]["new_strategies"])
                     or "—",
                     "Univers évalué": ", ".join(entry["snapshot"].get("evaluated_universe", []))})
    return pd.DataFrame(rows)


NOTE_KINDS = ("plan", "decision")


def distinct_configurations(registry: Path, kind: str | None = None) -> int:
    """Distinct evaluated configurations (plans and decisions, which carry no result, are not counted)."""
    return len({evaluation_fingerprint(e["snapshot"]) for e in load_entries(registry)
                if e.get("kind") not in NOTE_KINDS and (kind is None or e["kind"] == kind)})


def distinct_strategy_evaluations(registry: Path) -> int:
    """Distinct (strategy, inputs) pairs evaluated on the validation years: the number of looks."""
    return len({fp for e in load_entries(registry) if e.get("kind") not in NOTE_KINDS
                for fp in strategy_fingerprints(e["snapshot"]).values()})


def register_decision(registry: Path, *, label: str, rationale: str, informed_by_validation: bool,
                      project_dir: Path | None = None) -> dict:
    """Record a research or investor decision (no result), stating whether validation results informed it."""
    if not rationale.strip():
        raise ValueError("A decision needs its rationale.")
    registry = Path(registry)
    project_dir = registry.parent.parent if project_dir is None else Path(project_dir)
    now = f"{pd.Timestamp.now(tz='UTC'):%Y%m%dT%H%M%SZ}"
    entry = {"id": f"{now}-decision", "timestamp_utc": now, "kind": "decision", "category": "decision",
             "label": label, "rationale": rationale, "informed_by_validation": bool(informed_by_validation),
             "code": code_version(project_dir), "configuration": None}
    registry.parent.mkdir(parents=True, exist_ok=True)
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def register_plan(registry: Path, *, label: str, hypothesis: str, questions: list[str], document: str = "",
                  project_dir: Path | None = None) -> dict:
    """Record a research plan BEFORE its experiments run (no result, no configuration fingerprint).

    Later result entries can cite the plan id in their `notes`; the timestamp order in the append-only
    log is the evidence that the plan preceded the results.
    """
    if not hypothesis.strip() or not questions:
        raise ValueError("A plan needs a hypothesis and at least one question.")
    registry = Path(registry)
    project_dir = registry.parent.parent if project_dir is None else Path(project_dir)
    now = f"{pd.Timestamp.now(tz='UTC'):%Y%m%dT%H%M%SZ}"
    entry = {"id": f"{now}-plan", "timestamp_utc": now, "kind": "plan", "category": "pre-registered",
             "label": label, "hypothesis": hypothesis, "questions": list(questions), "document": document,
             "code": code_version(project_dir), "configuration": None}
    registry.parent.mkdir(parents=True, exist_ok=True)
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def decision_log(registry: Path, kind: str = "walk_forward") -> pd.DataFrame:
    """Chronological changes of tracked assumptions between successive runs of one kind.

    Each row lists the fields that differ from the previous run (or "initial"), so investor
    preference changes, modelling changes and code changes stay visible in order.
    """
    rows, previous = [], None
    for entry in load_entries(registry):
        if entry.get("kind") != kind:
            continue
        config = entry["snapshot"]["config"]
        current = {key: json.dumps(config.get(key), sort_keys=True) for key in TRACKED}
        current["constraint_provenance"] = entry["snapshot"].get("constraint_provenance", "")
        current["code"] = json.dumps(entry.get("code"), sort_keys=True)
        if previous is None:
            changed = ["initial"]
        else:
            changed = [key for key in current if current[key] != previous[key]] or ["rerun (no change)"]
        rows.append({"Identifiant": entry["id"], "Catégorie": entry.get("category", "non renseignée"),
                     "Configuration": entry["configuration"], "Changements": ", ".join(changed)})
        previous = current
    return pd.DataFrame(rows)
