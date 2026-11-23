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
        if message.id != "IN-015":  # recorded with a quote not in the message (kept as-is)
            assert analysis.extraction is not None, message.id


def test_kpi_from_committed_fixtures_matches_plan_records() -> None:
    """The real (recorded) Agent A answers give the §8 KPI records, not just the counts."""
    from datetime import datetime

    from app.core.timeutil import IL_TZ
    from app.kpi.compute import compute_pack
    from app.kpi.window import WEEK_UNDER_REVIEW
    from app.pipeline import build_world

    if not FIXTURES.directory.is_dir():
        return
    bundle = seed()
    analyses = {m.id: analyze_message(m, client=None, fixtures=FIXTURES) for m in bundle.inbound}
    world = build_world(
        bundle.crm, bundle.inbound, bundle.decisions, analyses,
        [e.contact_email for e in bundle.events],
    )  # fmt: skip
    pack = compute_pack(
        world, bundle.events, bundle.feed_status, WEEK_UNDER_REVIEW,
        datetime.now(IL_TZ),
    )  # fmt: skip
    records = {m.key: [r.record_id for r in m.records] for m in pack.metrics}
    assert records == {
        "qls": ["SD-001", "SD-002", "SD-004", "SD-008", "SD-009"],
        "meetings_booked": ["PE-003", "PE-004", "PE-007", "PE-010"],
        "meetings_held": ["PE-002", "PE-005", "PE-008"],
        "opportunities": ["PE-009", "PE-011"],
    }
