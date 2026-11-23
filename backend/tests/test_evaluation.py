"""Eval harness and the committed fixtures (offline)."""

from __future__ import annotations

from app.agents.analyzer import analyze_message
from app.agents.evaluation import evaluate, render_markdown
from app.agents.fixtures import FixtureStore
from app.core.config import REPO_ROOT
from app.core.enums import AnalysisMode
from tests.helpers import labelled_analyses, seed
from tests.seed_labels import LABELS

FIXTURES = FixtureStore(REPO_ROOT / "backend" / "fixtures" / "agent_a")


def test_labels_agree_with_themselves() -> None:
    report = evaluate(LABELS, labelled_analyses(seed()))
    assert report.compared == len(LABELS)
    assert all(f.agree == f.total for f in report.fields)
    assert f"| intent | {len(LABELS)}/{len(LABELS)} |" in render_markdown(report)


def test_disagreement_is_listed_by_record_id() -> None:
    analyses = labelled_analyses(seed())
    changed = LABELS["IN-009"].model_copy(update={"interest_level": "soft_positive"})
    analyses["IN-009"] = analyses["IN-009"].model_copy(update={"extraction": changed})
    report = evaluate(LABELS, analyses)
    interest = next(f for f in report.fields if f.name == "interest_level")
    assert interest.misses == ["IN-009: label='meeting_request' got='soft_positive'"]


def test_committed_fixtures_load_and_validate() -> None:
    """Every committed fixture matches its seed message and passes validation."""
    if not FIXTURES.directory.is_dir():
        return  # fixtures not recorded yet
    for message in seed().inbound:
        if message.id not in LABELS:
            continue
        analysis = analyze_message(message, client=None, fixtures=FIXTURES)
        assert analysis.mode == AnalysisMode.RECORDED_FIXTURE, message.id
