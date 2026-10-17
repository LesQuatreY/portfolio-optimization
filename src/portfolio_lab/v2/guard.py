"""TEST-period guard of the Portfolio Lab V2 data context.

Portfolio Research development data end on 2023-12-29; the 2024-2026 TEST period is locked.
This module is the only way V2 reads a Research file, and it fails closed:

1. allow-list: a logical artifact name must be declared in config/v2/lab.yaml, with a path inside
   the Research root (no ``..``, no symlink escape) that is not on the forbidden list;
2. integrity: the file's SHA-256 must equal the frozen hash pinned in the configuration;
3. cutoff: no date in the file may be later than the cutoff, checked BEFORE any value is read
   (parquet: column statistics from the file metadata, or the date column alone; CSV / JSON /
   YAML: every ISO date in the text and every year column header);
4. after loading, DataFrame date indexes and date columns are checked again (defence in depth).

``HARD_CUTOFF`` is a code constant: no configuration value, flag or environment variable lifts it.
A future evaluation on the TEST period must be a separate, explicitly authorized change of this
module. The V1 optimizer keeps its own, unrelated 2020 lock (``portfolio_lab.protocol``).
User-facing error messages are French.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

import pandas as pd

HARD_CUTOFF = pd.Timestamp("2023-12-29")
TEST_LABEL = "2024–2026"
SUFFIXES = (".csv", ".parquet", ".json", ".yaml", ".yml")
# ISO dates, also inside timestamps such as 2023-12-29T00:00:00 (no word boundary there).
ISO_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])(?!\d)")
YEAR_HEADER = re.compile(r"((?:19|20)\d{2})(?: T[1-4])?")


class GuardError(RuntimeError):
    """Base class: a Research file was refused (nothing was loaded)."""


class UnauthorizedArtifact(GuardError):
    """Not on the allow-list, outside the Research root, forbidden or of an unexpected type."""


class IntegrityError(GuardError):
    """Missing file, or content different from the frozen version (SHA-256 mismatch)."""


class CutoffViolation(GuardError):
    """The file (or a configuration) reaches past the 2023-12-29 development cutoff."""


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: str      # POSIX path relative to the Research root
    sha256: str


@dataclass(frozen=True)
class GateResult:
    name: str
    path: str
    sha256: str
    latest: pd.Timestamp | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parquet_max_date(path: Path) -> pd.Timestamp:
    """Latest date in a parquet file, from column statistics (values are not read).

    Falls back to reading the date column(s) alone when statistics are missing. A file without any
    date column cannot be verified and is refused.
    """
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    handle = pq.ParquetFile(path)
    schema = handle.schema_arrow
    columns = [f.name for f in schema if pa.types.is_timestamp(f.type) or pa.types.is_date(f.type)]
    if not columns:
        raise CutoffViolation(f"{Path(path).name} : aucune colonne de dates, le seuil ne peut pas être vérifié.")
    latest = None
    for column in columns:
        index = schema.get_field_index(column)
        top = None
        for group in range(handle.metadata.num_row_groups):
            stats = handle.metadata.row_group(group).column(index).statistics
            if stats is None or not stats.has_min_max:
                top = None
                break
            top = stats.max if top is None else max(top, stats.max)
        if top is None:
            top = pc.max(handle.read(columns=[column]).column(column)).as_py()
        if top is None:
            continue
        top = pd.Timestamp(top)
        latest = top if latest is None else max(latest, top)
    if latest is None:
        raise CutoffViolation(f"{Path(path).name} : colonnes de dates vides, le seuil ne peut pas être vérifié.")
    return latest


def text_max_date(path: Path, cutoff: pd.Timestamp = HARD_CUTOFF) -> pd.Timestamp | None:
    """Latest ISO date in a text artifact; CSV year column headers (e.g. 2023, 2014 T4) count too."""
    text = Path(path).read_text(encoding="utf-8")
    dates = []
    for year, month, day in ISO_DATE.findall(text):
        try:
            dates.append(pd.Timestamp(int(year), int(month), int(day)))
        except ValueError:          # e.g. 2023-02-31: not a date, ignored
            continue
    if Path(path).suffix == ".csv":
        header = text.splitlines()[0] if text else ""
        for cell in header.split(","):
            match = YEAR_HEADER.fullmatch(cell.strip().strip('"'))
            if match:
                year = int(match.group(1))
                dates.append(pd.Timestamp(year, 12, 31) if year > cutoff.year else pd.Timestamp(year, 1, 1))
    return max(dates) if dates else None


def frame_max_date(frame: pd.DataFrame) -> pd.Timestamp | None:
    """Latest date in a loaded frame's date index levels and datetime columns."""
    found = []
    index = frame.index
    levels = index.levels if isinstance(index, pd.MultiIndex) else [index]
    for level in levels:
        if isinstance(level, pd.DatetimeIndex) and len(level):
            found.append(level.max())
    for column in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[column]) and frame[column].notna().any():
            found.append(frame[column].max())
    return max(found) if found else None


def scan_text_for_dates_after(text: str, cutoff: pd.Timestamp = HARD_CUTOFF) -> list[str]:
    """ISO dates later than the cutoff found in a text (sorted, unique); used to check exported outputs."""
    out = set()
    for match in ISO_DATE.finditer(text):
        year, month, day = (int(g) for g in match.groups())
        try:
            if pd.Timestamp(year, month, day) > cutoff:
                out.add(match.group(0))
        except ValueError:
            continue
    return sorted(out)


def assert_notebook_safe(path: Path, cutoff: pd.Timestamp = HARD_CUTOFF) -> None:
    """An executed V2 notebook (outputs and widget state included) must not show TEST-period dates."""
    found = scan_text_for_dates_after(Path(path).read_text(encoding="utf-8"), cutoff)
    if found:
        raise CutoffViolation(f"{path} : le notebook exécuté contient des dates postérieures au "
                              f"{cutoff.date()} (par ex. {found[:5]}) ; rien ne doit être conservé.")


class ResearchGuard:
    """Gate-keeper for every Research file read by Portfolio Lab V2 (see module docstring)."""

    def __init__(self, root: Path, artifacts: Iterable[ArtifactSpec], cutoff: pd.Timestamp = HARD_CUTOFF,
                 forbidden: Iterable[str] = ()):
        cutoff = pd.Timestamp(cutoff)
        if cutoff > HARD_CUTOFF:
            raise CutoffViolation(f"Seuil demandé {cutoff.date()} postérieur à la limite verrouillée "
                                  f"{HARD_CUTOFF.date()} (période TEST {TEST_LABEL}).")
        root = Path(root)
        if not root.is_dir():
            raise IntegrityError(f"Dossier Portfolio Research introuvable : {root}. "
                                 "Vérifiez research.root dans config/v2/lab.yaml.")
        self.root = root.resolve()
        self.cutoff = cutoff
        self._forbidden = [(self.root / PurePosixPath(p)).resolve() for p in forbidden]
        self._specs: dict[str, ArtifactSpec] = {}
        self._paths: dict[str, Path] = {}
        for spec in artifacts:
            self._paths[spec.name] = self._resolve(spec)
            self._specs[spec.name] = spec

    # ------------------------------------------------------------------ allow-list
    def _resolve(self, spec: ArtifactSpec) -> Path:
        rel = PurePosixPath(spec.path)
        if rel.is_absolute() or ".." in rel.parts:
            raise UnauthorizedArtifact(f"{spec.name} : chemin refusé ({spec.path}) — relatif à Research, sans « .. ».")
        path = (self.root / rel).resolve()
        if self.root not in path.parents:
            raise UnauthorizedArtifact(f"{spec.name} : {spec.path} sort du dossier Portfolio Research.")
        for bad in self._forbidden:
            if path == bad or bad in path.parents:
                raise UnauthorizedArtifact(f"{spec.name} : {spec.path} fait partie des données interdites "
                                           f"(postérieures au {self.cutoff.date()} ou allocation réelle).")
        if path.suffix.lower() not in SUFFIXES:
            raise UnauthorizedArtifact(f"{spec.name} : type de fichier non autorisé ({path.suffix}).")
        return path

    @property
    def names(self) -> list[str]:
        return list(self._specs)

    def path(self, name: str) -> Path:
        if name not in self._paths:
            raise UnauthorizedArtifact(f"« {name} » n'est pas un artefact autorisé ; seuls les artefacts gelés "
                                       "déclarés dans config/v2/lab.yaml peuvent être lus.")
        return self._paths[name]

    # ------------------------------------------------------------------ gates
    def check(self, name: str) -> GateResult:
        """Integrity then cutoff gate for one artifact; raises before any value is read."""
        self.path(name)  # reject unknown names before looking up their specification
        spec = self._specs[name]
        path = self._resolve(spec)  # recheck containment if a symlink was replaced
        self._paths[name] = path
        if not path.is_file():
            raise IntegrityError(f"{name} : fichier introuvable ({path}).")
        digest = sha256_file(path)
        if digest != spec.sha256:
            raise IntegrityError(f"{name} : le fichier diffère de la version gelée (SHA-256 {digest[:12]}… "
                                 f"au lieu de {spec.sha256[:12]}…) ; rien n'a été chargé.")
        latest = parquet_max_date(path) if path.suffix == ".parquet" else text_max_date(path, self.cutoff)
        if latest is not None and latest > self.cutoff:
            raise CutoffViolation(f"{name} : contient le {latest.date()}, postérieur au {self.cutoff.date()} "
                                  f"(période TEST {TEST_LABEL} verrouillée) ; rien n'a été chargé.")
        result = GateResult(name, spec.path, digest, latest)
        return result

    def load(self, name: str):
        """Gate-checked read of one artifact (DataFrame for CSV / parquet, object for JSON / YAML)."""
        self.check(name)
        path = self._paths[name]
        suffix = path.suffix.lower()
        if suffix == ".parquet":
            obj = pd.read_parquet(path)
        elif suffix == ".csv":
            obj = pd.read_csv(path)
        elif suffix == ".json":
            obj = json.loads(path.read_text(encoding="utf-8"))
        else:
            import yaml
            obj = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.check(name)  # also reject replacement during the read, before returning values
        latest = frame_max_date(obj) if isinstance(obj, pd.DataFrame) else None
        if latest is not None and latest > self.cutoff:     # defence in depth (statistics already checked)
            raise CutoffViolation(f"{name} : date {latest.date()} postérieure au {self.cutoff.date()} après lecture.")
        return obj

    def report(self) -> pd.DataFrame:
        """One row per artifact (all gates run): what was checked, in French."""
        rows = []
        for name in self._specs:
            r = self.check(name)
            rows.append({"Artefact": name, "Fichier": r.path, "Empreinte SHA-256": f"{r.sha256[:12]}… conforme",
                         "Date la plus récente": "—" if r.latest is None else r.latest.date().isoformat(),
                         f"Seuil {self.cutoff.date()}": "respecté"})
        return pd.DataFrame(rows)


def guard_from_settings(settings) -> ResearchGuard:
    return ResearchGuard(settings.research_root, settings.artifacts, settings.cutoff, settings.forbidden)
