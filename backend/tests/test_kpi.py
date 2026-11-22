"""KPI counting and the reporting window. The golden test is docs/PLAN.md §8."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.core.enums import AnalysisMode, Source
from app.core.timeutil import parse_aware
from app.ingest.loader import SeedBundle
from app.ingest.schemas import SalesDecision
from app.ingest.validate import parse_decision
from app.kpi.compute import compute_pack
from app.kpi.export import CRO_HEADING, export, render
from app.kpi.schemas import KpiPack
from app.kpi.window import WEEK_UNDER_REVIEW, ReportingWindow
from app.pipeline import assess_all
from tests.helpers import seed, seed_world

GENERATED = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)


def pack_for(bundle: SeedBundle, window: ReportingWindow = WEEK_UNDER_REVIEW) -> KpiPack:
    world = seed_world(bundle)
    return compute_pack(
        world, assess_all(world), bundle.events, bundle.feed_status, window, GENERATED,
        [AnalysisMode.LLM],
    )  # fmt: skip


def ids(pack: KpiPack, key: str) -> list[str]:
    return [r.record_id for r in pack.metric(key).records]  # type: ignore[arg-type]


# ---- window ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("stamp", "inside"),
    [
        ("2026-10-04T00:00:00+03:00", True),  # Sunday 00:00 IL, first instant
        ("2026-10-03T21:00:00Z", True),  # same instant written in UTC
        ("2026-10-03T20:59:59Z", False),  # Saturday 23:59:59 IL
        ("2026-10-08T20:30:00Z", True),  # IN-017: Thu 23:30 IL
        ("2026-10-08T20:59:59Z", True),  # Thu 23:59:59 IL
        ("2026-10-08T21:00:00Z", False),  # Fri 00:00 IL
        ("2026-10-08T21:30:00Z", False),  # IN-018: UTC says Thursday, IL is Friday
        ("2026-10-09T10:00:00+03:00", False),  # PE-012, Friday
        ("2026-10-02T16:40:00+03:00", False),  # IN-002, previous Friday
    ],
)
def test_window_converts_to_israel_time(stamp: str, inside: bool) -> None:
    assert WEEK_UNDER_REVIEW.contains(parse_aware(stamp)) is inside


def test_window_must_start_on_sunday() -> None:
    with pytest.raises(ValueError):
        ReportingWindow(date(2026, 10, 5))


def test_window_after_dst_change_uses_plus_two() -> None:
    week = ReportingWindow(date(2026, 10, 25))  # IL switches to UTC+2 on 25 Oct 2026
    assert week.start.utcoffset() is not None
    assert week.contains(parse_aware("2026-10-29T21:59:00Z"))  # Thu 23:59 IL (+02:00)
    assert not week.contains(parse_aware("2026-10-29T22:00:00Z"))  # Fri 00:00 IL


# ---- golden pack (PLAN §8) ---------------------------------------------------


def test_golden_kpi_pack() -> None:
    pack = pack_for(seed())
    assert ids(pack, "qls") == ["SD-001", "SD-002", "SD-004", "SD-008", "SD-009"]
    assert ids(pack, "meetings_booked") == ["PE-003", "PE-004", "PE-007", "PE-010"]
    assert ids(pack, "meetings_held") == ["PE-002", "PE-005", "PE-008"]
    assert ids(pack, "opportunities") == ["PE-009", "PE-011"]
    assert [(m.actual, m.target) for m in pack.metrics] == [(5, 25), (4, 15), (3, 12), (2, 5)]
    assert [r.record_id for r in pack.expansion.accepted] == ["SD-005"]
    assert [r.record_id for r in pack.expansion.meetings_booked] == ["PE-006"]


def test_golden_sources() -> None:
    rows = {row.source: row for row in pack_for(seed()).by_source}
    counts = {src: row.count for src, row in rows.items()}
    assert counts == {
        Source.EVENT_EMAIL: 2,
        Source.PAID: 1,
        Source.HISTORICAL_REACTIVATION: None,  # unknown, not 0
        Source.NEW_CONNECTION: 0,
        Source.WARM_NETWORK: 1,
        Source.ORGANIC_REFERRAL: 1,
        "source not recorded": 0,
    }
    # Pieter: earliest is IN-002 (event-email), not IN-003 (new-connection).
    # Anouk: earliest is IN-001 (event-email), not IN-021 (paid).
    event_email = {r.name: r.detail for r in rows[Source.EVENT_EMAIL].records}
    assert event_email == {
        "Pieter Claes": "earliest inbound IN-002",
        "Anouk de Vries": "earliest inbound IN-001",
    }


def test_golden_exclusions_are_explained() -> None:
    reasons = {e.record_id: e.reason for e in pack_for(seed()).excluded}
    assert "superseded" in reasons["SD-003"]  # Rachel logged twice, counted once
    assert "outside the week" in reasons["SD-010"]  # Priya, decided 11 Oct
    assert "outside the week" in reasons["SD-011"]  # Felix, decided 24 Sep
    assert reasons["SD-006"] == "rejected"  # Wim
    assert "disqualified" in reasons["SD-007"] and "C3" in reasons["SD-007"]  # Tom
    assert "outside the week" in reasons["PE-001"]
    assert "outside the week" in reasons["PE-012"]
    assert "queued" in reasons["IN-018"]  # Marcus, Friday inbound
    assert "needs review" in reasons["IN-010"]
    assert "not evidence" in reasons["HS-1014"]  # Lukas, CRM "QL"


# ---- replaying decisions (R29, R36) -----------------------------------------


def _accept_marcus(bundle: SeedBundle, decided_at: str) -> SeedBundle:
    decision = parse_decision(
        {"id": "UI-SD-001", "contact_email": "m.hale@meridianhaulage.co.uk",
         "decision": "accepted", "decided_by": "Leo", "decided_at": decided_at},
        origin="ui",
    )  # fmt: skip
    assert isinstance(decision, SalesDecision)
    bundle.decisions.append(decision)
    return bundle


def test_ui_acceptance_inside_week_counts() -> None:
    pack = pack_for(_accept_marcus(seed(), "2026-10-08T18:00:00+03:00"))
    assert pack.metric("qls").actual == 6
    assert "UI-SD-001" in ids(pack, "qls")


def test_ui_acceptance_after_week_does_not_change_this_week() -> None:
    bundle = _accept_marcus(seed(), "2026-10-11T09:30:00+03:00")
    assert pack_for(bundle).metric("qls").actual == 5
    # The Friday inbound counts in the week it was accepted.
    next_week = pack_for(bundle, ReportingWindow(date(2026, 10, 11)))
    assert set(ids(next_week, "qls")) == {"SD-010", "UI-SD-001"}  # Priya + Marcus


def test_later_rejection_removes_ql() -> None:
    bundle = seed()
    reject = parse_decision(
        {"id": "UI-SD-002", "contact_email": "noam@ashdodbay.co.il", "decision": "rejected",
         "decided_by": "Noa", "decided_at": "2026-10-08T12:00:00+03:00"},
        origin="ui",
    )  # fmt: skip
    assert isinstance(reject, SalesDecision)
    bundle.decisions.append(reject)
    assert pack_for(bundle).metric("qls").actual == 4


def test_ql_counted_once_per_person() -> None:
    pack = pack_for(seed())
    people = [r.person_id for r in pack.metric("qls").records]
    assert len(people) == len(set(people))


# ---- export ------------------------------------------------------------------


def test_markdown_export_preserves_cro_note(tmp_path: Path) -> None:
    pack = pack_for(seed())
    path = tmp_path / "KPI_PACK.md"
    first = export(pack, path)
    assert "| QLs | 5 | 25 | -20 |" in first
    assert "| historical-reactivation | unknown |" in first
    path.write_text(first.split(CRO_HEADING)[0] + CRO_HEADING + "\n\nMy note.\n")
    assert export(pack, path).rstrip().endswith("My note.")


def test_markdown_has_no_emails() -> None:
    assert "@" not in render(pack_for(seed()))
