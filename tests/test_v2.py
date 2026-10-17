"""Frozen development artifacts only. Adversarial files are synthetic and local to tmp_path."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
import pytest

from portfolio_lab.v2 import bridge, charts, checks, formatting
from portfolio_lab.v2.guard import (ArtifactSpec, ResearchGuard, CutoffViolation, IntegrityError,
                                    UnauthorizedArtifact, assert_notebook_safe, sha256_file)
from portfolio_lab.v2.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]
IDS = ("N07", "D2_25", "D2_10", "S056", "S054", "G03", "G04", "B1", "B2", "B1M", "B2M")


@pytest.fixture(scope="module")
def lab():
    settings = load_settings(ROOT)
    guard = ResearchGuard(settings.research_root, settings.artifacts, forbidden=settings.forbidden)
    guard.report()  # cutoff and pinned integrity, before loading any values
    before = {a.name: sha256_file(guard.path(a.name)) for a in settings.artifacts}
    loaded = bridge.build_lab(settings, guard)
    yield loaded
    # Never write to Research, including from tests. Hash only the authorized frozen artifacts.
    assert before == {a.name: sha256_file(guard.path(a.name)) for a in settings.artifacts}


@pytest.mark.parametrize("sid", IDS)
def test_reference_metrics(lab, sid):
    rep = checks.reproduction(lab)
    rows = rep[rep["Portefeuille"] == sid]
    assert len(rows) == 8 and rows["Conforme"].all()
    assert tuple(lab.ids) == IDS


@pytest.mark.parametrize("sid", IDS)
def test_net_terminal_reconciliation(lab, sid):
    ref = lab.reference.loc[sid]
    taxes = sum(ref[c] for c in bridge.EXIT_TAXES)
    net = lab.wealth[sid].iloc[-1] - lab.summary.loc[sid, "liquidation_costs"] - taxes
    assert net == pytest.approx(ref["terminal_net"], abs=checks.EUR_TOL)


def test_accounting_dates_and_pinned_integrity(lab):
    assert checks.accounting(lab)["Conforme"].all()
    assert lab.wealth.shape == (2369, 11)
    assert lab.period == (pd.Timestamp("2014-10-01"), pd.Timestamp("2023-12-29"))
    for spec in lab.settings.artifacts:
        assert sha256_file(lab.settings.research_root / spec.path) == spec.sha256


def synthetic_guard(tmp_path, content="Date,value\n2023-12-29,1\n", suffix=".csv"):
    path = tmp_path / ("fixture" + suffix)
    path.write_text(content, encoding="utf-8")
    spec = ArtifactSpec("fixture", path.name, sha256_file(path))
    return ResearchGuard(tmp_path, [spec], forbidden=["private"]), path


def test_same_guard_rejects_changed_content_with_unchanged_size_and_mtime(tmp_path):
    import os
    guard, path = synthetic_guard(tmp_path)
    guard.load("fixture")
    stamp = path.stat()
    path.write_text("Date,value\n2023-12-29,2\n", encoding="utf-8")
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    with pytest.raises(IntegrityError):
        guard.load("fixture")


def test_changed_during_read_is_not_returned(tmp_path, monkeypatch):
    guard, path = synthetic_guard(tmp_path)
    original = pd.read_csv
    def replace_after_read(*args, **kwargs):
        frame = original(*args, **kwargs)
        path.write_text("Date,value\n2023-12-29,2\n", encoding="utf-8")
        return frame
    monkeypatch.setattr(pd, "read_csv", replace_after_read)
    with pytest.raises(IntegrityError):
        guard.load("fixture")


def test_cached_lab_opening_rechecks_artifacts(tmp_path, lab, monkeypatch):
    guard, path = synthetic_guard(tmp_path)
    settings = replace(lab.settings, research_root=tmp_path, artifacts=tuple(guard._specs.values()))
    monkeypatch.setattr(bridge, "load_settings", lambda *_: settings)
    monkeypatch.setattr(bridge, "_cached", lambda *_: lab)
    assert bridge.load_lab(ROOT) is lab
    path.write_text("Date,value\n2023-12-29,2\n", encoding="utf-8")
    with pytest.raises(IntegrityError):
        bridge.load_lab(ROOT)


@pytest.mark.parametrize("path", ["../outside.csv", "private/account.csv", "/outside.csv", "code.py"])
def test_unauthorized_paths(tmp_path, path):
    with pytest.raises(UnauthorizedArtifact):
        ResearchGuard(tmp_path, [ArtifactSpec("bad", path, "0" * 64)], forbidden=["private"])


def test_unknown_artifact_and_missing_file(tmp_path):
    guard, path = synthetic_guard(tmp_path)
    with pytest.raises(UnauthorizedArtifact):
        guard.load("unlisted")
    path.unlink()  # synthetic fixture only
    with pytest.raises(IntegrityError):
        guard.load("fixture")


@pytest.mark.parametrize("content,suffix", [
    ("Date,value\n2024-01-01,1\n", ".csv"),
    ("strategy,2024\nsynthetic,1\n", ".csv"),
    ('{"date": "2024-01-01"}', ".json"),
    ("date: 2024-01-01\n", ".yaml"),
])
def test_synthetic_post_cutoff_inputs_rejected(tmp_path, content, suffix):
    guard, _ = synthetic_guard(tmp_path, content, suffix)
    with pytest.raises(CutoffViolation):
        guard.load("fixture")


def test_parquet_metadata_cutoff_precedes_performance_read(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.parquet"
    pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "synthetic": [1.]}).to_parquet(path)
    guard = ResearchGuard(tmp_path, [ArtifactSpec("bad", path.name, sha256_file(path))])
    monkeypatch.setattr(pd, "read_parquet", lambda *_: pytest.fail("Performance must not be read"))
    with pytest.raises(CutoffViolation):
        guard.load("bad")


def test_cutoff_cannot_be_lifted(tmp_path):
    with pytest.raises(CutoffViolation):
        ResearchGuard(tmp_path, [], cutoff="2024-01-01")


def test_output_date_scanner_on_synthetic_notebook(tmp_path):
    path = tmp_path / "synthetic.ipynb"
    path.write_text('{"outputs": ["2024-01-01"]}', encoding="utf-8")
    with pytest.raises(CutoffViolation):
        assert_notebook_safe(path)


@pytest.mark.parametrize("value", [-0.00001, -0.0, 0.0])
def test_french_formatting_no_negative_zero(value):
    assert formatting.num(value, 1) == "0,0"
    assert formatting.pct(value, 1) == "0,0\N{NO-BREAK SPACE}%"


def test_frontier_keeps_all_portfolio_labels_and_single_risk_toggle(lab):
    charts.setup()
    fig = charts.frontier_figure(lab, lab.ids)
    assert [t.text[0] for t in fig.data] == list(IDS)
    assert len(fig.layout.updatemenus) == 1
    assert len(fig.layout.updatemenus[0].buttons) == 2


@pytest.mark.parametrize("metric", list(charts.ROLLING))
def test_rolling_annotations_stay_inside_visible_history(lab, metric):
    charts.setup()
    fig = charts.rolling_figure(lab, lab.ids, metric)
    start, end = map(pd.Timestamp, fig.layout.xaxis.range)
    assert end <= pd.Timestamp("2023-12-29")
    assert all(start <= pd.Timestamp(a.x) <= end for a in fig.layout.annotations)


def test_widget_selection_and_controls_do_not_reload_or_simulate(lab, monkeypatch):
    from portfolio_lab.v2 import ui
    assert ui.HAS_WIDGETS
    monkeypatch.setattr(ui, "display", lambda *a, **k: SimpleNamespace(update=lambda *_: None))
    monkeypatch.setattr(ui, "load_lab", lambda *_: pytest.fail("No reload from a view control"))
    session = ui.LabSession(lab)
    selector = session.selector()
    session.frontier()
    session.rolling()
    session.allocation()
    session.select(IDS)
    assert session.selection == list(IDS)
    session._buttons["N07"].click()
    assert "N07" not in session.selection
    control = session.views["rolling"].controls["Indicateur"]
    control.value = "r5"
    assert session.rendered["rolling"].layout.title.text.startswith("<b>CAGR glissant sur 5 ans")
    session.views["allocation"].controls["Portefeuille"].value = "B2M"
    assert "B2M" in session.rendered["allocation"].layout.title.text
    session.select([])
    assert not session.rendered["rolling"].data
    assert selector is not None
