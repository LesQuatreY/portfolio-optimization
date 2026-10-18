"""Portfolio Lab V2 settings: ``config/v2/lab.yaml`` and ``config/v2/instruments.yaml``.

Strict parsing: unknown keys, missing hashes, malformed dates or a cutoff beyond the hard-coded
TEST lock raise before anything is read from Portfolio Research. User-facing messages are French.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

import pandas as pd
import yaml

from .guard import HARD_CUTOFF, ArtifactSpec, CutoffViolation

CONFIG_PATH = Path("config/v2/lab.yaml")
INSTRUMENTS_PATH = Path("config/v2/instruments.yaml")
KINDS = ("strategy", "benchmark")
PROVENANCE = ("observe", "proxy", "synthetique", "comptable")
_TOP = {"research", "artifacts", "forbidden", "strategies", "default_selection"}
_RESEARCH = {"root", "cutoff", "start", "initial_capital", "currency", "hash_record"}
_STRATEGY = {"kind", "role", "config_sha256"}
_LINE = {"label", "group", "wrapper", "isin", "provenance", "source"}


class SettingsError(ValueError):
    """Invalid V2 configuration (message in French, shown to the user)."""


@dataclass(frozen=True)
class StrategySpec:
    id: str
    kind: str            # "strategy" | "benchmark"
    role: str            # French label shown in the interface
    config_sha256: str   # frozen configuration hash expected in the manifest


@dataclass(frozen=True)
class LineSpec:
    column: str          # value column of curves_FULL.parquet (EUR)
    label: str
    group: str
    wrapper: str
    provenance: str
    source: str
    isin: str = ""


@dataclass(frozen=True)
class LabSettings:
    project_dir: Path
    research_root: Path
    cutoff: pd.Timestamp
    start: pd.Timestamp
    initial_capital: float
    currency: str
    hash_record: str | None
    artifacts: tuple[ArtifactSpec, ...]
    forbidden: tuple[str, ...]
    strategies: tuple[StrategySpec, ...]
    default_selection: tuple[str, ...]
    lines: tuple[LineSpec, ...]
    groups: tuple[tuple[str, str], ...]      # (key, French label) in stacking order
    wrappers: tuple[tuple[str, str], ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(s.id for s in self.strategies)

    def strategy(self, sid: str) -> StrategySpec:
        for spec in self.strategies:
            if spec.id == sid:
                return spec
        raise KeyError(sid)


def find_project_dir(start: Path | None = None) -> Path:
    """Nearest ancestor containing config/v2/lab.yaml (works from notebooks/ or the root)."""
    start = Path.cwd() if start is None else Path(start)
    for candidate in (start, *start.resolve().parents):
        if (candidate / CONFIG_PATH).exists():
            return candidate
    raise SettingsError(f"Fichier {CONFIG_PATH.as_posix()} introuvable au-dessus de {start}.")


def _mapping(raw, where: str) -> Mapping:
    if not isinstance(raw, Mapping):
        raise SettingsError(f"{where} : une table (clé: valeur) est attendue.")
    return raw


def _keys(raw: Mapping, allowed: set, where: str, required: set | None = None) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise SettingsError(f"{where} : clé(s) inconnue(s) {sorted(unknown)} (autorisées : {sorted(allowed)}).")
    missing = (required if required is not None else allowed) - set(raw)
    if missing:
        raise SettingsError(f"{where} : clé(s) manquante(s) {sorted(missing)}.")


def _date(value, where: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"{where} : date invalide {value!r}.") from exc
    if pd.isna(stamp):
        raise SettingsError(f"{where} : date invalide {value!r}.")
    return stamp.normalize()


def _sha(value, where: str) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise SettingsError(f"{where} : empreinte SHA-256 invalide ({value!r}).")
    return text


def _relative(value, where: str) -> str:
    path = PurePosixPath(str(value).replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise SettingsError(f"{where} : chemin relatif à research.root attendu, sans « .. » ({value!r}).")
    return path.as_posix()


def parse_settings(raw: Mapping, instruments: Mapping, project_dir: Path) -> LabSettings:
    raw = _mapping(raw, "lab.yaml")
    _keys(raw, _TOP, "lab.yaml")
    res = _mapping(raw["research"], "research")
    _keys(res, _RESEARCH, "research", required=_RESEARCH - {"hash_record"})
    cutoff = _date(res["cutoff"], "research.cutoff")
    if cutoff > HARD_CUTOFF:
        raise CutoffViolation(
            f"research.cutoff {cutoff.date()} dépasse la limite verrouillée {HARD_CUTOFF.date()} : "
            "la période TEST 2024–2026 ne peut pas être ouverte par configuration.")
    start = _date(res["start"], "research.start")
    if start >= cutoff:
        raise SettingsError("research.start doit précéder research.cutoff.")
    root = Path(str(res["root"]))
    root = root if root.is_absolute() else (project_dir / root)
    capital = float(res["initial_capital"])
    if capital <= 0:
        raise SettingsError("research.initial_capital doit être positif.")

    arts = []
    for name, spec in _mapping(raw["artifacts"], "artifacts").items():
        spec = _mapping(spec, f"artifacts.{name}")
        _keys(spec, {"path", "sha256"}, f"artifacts.{name}")
        arts.append(ArtifactSpec(str(name), _relative(spec["path"], f"artifacts.{name}.path"),
                                 _sha(spec["sha256"], f"artifacts.{name}.sha256")))
    forbidden = tuple(_relative(p, "forbidden") for p in (raw["forbidden"] or ()))

    strategies = []
    for sid, spec in _mapping(raw["strategies"], "strategies").items():
        spec = _mapping(spec, f"strategies.{sid}")
        _keys(spec, _STRATEGY, f"strategies.{sid}")
        if spec["kind"] not in KINDS:
            raise SettingsError(f"strategies.{sid}.kind : {spec['kind']!r} (attendu : {', '.join(KINDS)}).")
        strategies.append(StrategySpec(str(sid), spec["kind"], str(spec["role"]),
                                       _sha(spec["config_sha256"], f"strategies.{sid}.config_sha256")))
    ids = [s.id for s in strategies]
    if len(set(ids)) != len(ids) or not ids:
        raise SettingsError("strategies : identifiants absents ou en double.")
    if sum(s.kind == "strategy" for s in strategies) > 8:
        raise SettingsError("strategies : 8 stratégies au plus (une couleur distincte par stratégie).")
    if sum(s.kind == "benchmark" for s in strategies) > 4:
        raise SettingsError("strategies : 4 références au plus (gris et tirets distincts).")
    default = tuple(raw["default_selection"] or ())
    unknown = set(default) - set(ids)
    if unknown:
        raise SettingsError(f"default_selection : portefeuille(s) non intégré(s) {sorted(unknown)}.")

    inst = _mapping(instruments, "instruments.yaml")
    _keys(inst, {"groups", "wrappers", "lines"}, "instruments.yaml")
    groups = tuple((str(k), str(v)) for k, v in _mapping(inst["groups"], "groups").items())
    wrappers = tuple((str(k), str(v)) for k, v in _mapping(inst["wrappers"], "wrappers").items())
    lines = []
    for col, spec in _mapping(inst["lines"], "lines").items():
        spec = _mapping(spec, f"lines.{col}")
        _keys(spec, _LINE, f"lines.{col}", required=_LINE - {"isin"})
        if spec["group"] not in dict(groups):
            raise SettingsError(f"lines.{col}.group : groupe inconnu {spec['group']!r}.")
        if spec["wrapper"] not in dict(wrappers):
            raise SettingsError(f"lines.{col}.wrapper : enveloppe inconnue {spec['wrapper']!r}.")
        if spec["provenance"] not in PROVENANCE:
            raise SettingsError(f"lines.{col}.provenance : {spec['provenance']!r} (attendu : {', '.join(PROVENANCE)}).")
        lines.append(LineSpec(str(col), str(spec["label"]), spec["group"], spec["wrapper"], spec["provenance"],
                              " ".join(str(spec["source"]).split()), str(spec.get("isin", "") or "")))
    return LabSettings(project_dir=project_dir, research_root=root, cutoff=cutoff, start=start, initial_capital=capital,
                       currency=str(res["currency"]), hash_record=res.get("hash_record"), artifacts=tuple(arts),
                       forbidden=forbidden, strategies=tuple(strategies), default_selection=default,
                       lines=tuple(lines), groups=groups, wrappers=wrappers)


def load_settings(project_dir: Path | None = None) -> LabSettings:
    """Read and validate config/v2/lab.yaml and config/v2/instruments.yaml."""
    project_dir = find_project_dir(project_dir)
    raw = yaml.safe_load((project_dir / CONFIG_PATH).read_text(encoding="utf-8"))
    instruments = yaml.safe_load((project_dir / INSTRUMENTS_PATH).read_text(encoding="utf-8"))
    return parse_settings(raw, instruments, project_dir)
