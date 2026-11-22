"""Every seed lead against docs/PLAN.md §7 (with the hand labels as Agent A output)."""

from __future__ import annotations

import pytest

from app.core.enums import Status
from app.pipeline import assess_all
from tests.helpers import seed, seed_world

# person (CRM id, or the inbound id for people outside the CRM) → (status, owner)
EXPECTED: dict[str, tuple[Status, str | None]] = {
    "HS-1001": (Status.QL, "Dana"),  # Anouk
    "HS-1002": (Status.NURTURE, "Dana"),  # Sanne, not interested now
    "HS-1004": (Status.QL, "Dana"),  # Pieter
    "HS-1005": (Status.DISQUALIFIED, None),  # Wim, rejected + team lead
    "HS-1006": (Status.SUPPRESSED, None),  # Greta, unsubscribe
    "HS-1007": (Status.EXCLUDED, None),  # James, auto-reply
    "HS-1008": (Status.QL_CANDIDATE, "Leo"),  # Marcus, Friday inbound, no decision
    "HS-1009": (Status.QL, "Mei"),  # Rachel
    "HS-1011": (Status.EXCLUDED, "Sam"),  # Mark, customer → expansion
    "HS-1012": (Status.EXCLUDED, "Mei"),  # Daniel, pre-existing deal
    "HS-1013": (Status.DISQUALIFIED, None),  # Tom, accepted but C3 fails (D1, D12)
    "HS-1016": (Status.QL, "Sam"),  # Priya (accepted 10-11)
    "HS-1017": (Status.QL, "Noa"),  # Noam
    "HS-1018": (Status.EXCLUDED, None),  # Kai, competitor
    "HS-1019": (Status.EXCLUDED, "Founders"),  # Hannah, investor
    "IN-010": (Status.NEEDS_REVIEW, "Leo"),  # instruction attempt, Halden domain → DACH
    "IN-011": (Status.QL, "Noa"),  # Yossi, unverified facts
    "IN-015": (Status.EXCLUDED, None),  # Lior, student
}


def _person_key_map() -> dict[str, str]:
    world = seed_world()
    keys: dict[str, str] = {}
    for pid, ctx in world.leads.items():
        keys[ctx.crm.record_id if ctx.crm else ctx.inbound[0].id] = pid
    return keys


def test_lead_set_matches_plan() -> None:
    assert set(_person_key_map()) == set(EXPECTED)


@pytest.mark.parametrize(("key", "expected"), sorted(EXPECTED.items()))
def test_seed_status_and_owner(key: str, expected: tuple[Status, str | None]) -> None:
    world = seed_world()
    assessments = assess_all(world)
    pid = _person_key_map()[key]
    result = assessments[pid]
    assert (result.status, result.owner) == expected, result.rationale


def test_researched_only_contacts_are_not_leads() -> None:
    leads = _person_key_map()
    for record in ("HS-1003", "HS-1010", "HS-1014", "HS-1015"):  # incl. Lukas (CRM "QL")
        assert record not in leads


def test_tom_keeps_decision_and_shows_failing_c3() -> None:
    tom = assess_all(seed_world())["HS-1013"]
    assert tom.checklist is not None
    assert tom.checklist.failing == ["C3"]
    assert tom.accepted_by is not None and tom.accepted_by.decided_by == "Leo"
    assert tom.score is None


def test_yossi_passes_with_unverified_facts() -> None:
    world = seed_world()
    pid = _person_key_map()["IN-011"]
    yossi = assess_all(world)[pid]
    assert yossi.checklist is not None
    c1 = yossi.checklist.c1_company_fit
    assert c1.status == "pass" and not c1.verified
    assert any("unverified" in e for e in c1.evidence)
    assert world.leads[pid].company is None  # free email → no company record


def test_sanne_uses_company_record_size_labelled() -> None:
    sanne = assess_all(seed_world())["HS-1002"]
    assert sanne.checklist is not None
    assert any("from CRM company record" in e for e in sanne.checklist.c1_company_fit.evidence)


def test_injection_never_reaches_rules_or_draft() -> None:
    world = seed_world()
    pid = _person_key_map()["IN-010"]
    result = assess_all(world)[pid]
    assert result.checklist is None and result.score is None
    assert world.leads[pid].analyses[0].extraction is None


def test_expansion_flag_only_for_customer() -> None:
    results = assess_all(seed_world())
    assert [pid for pid, a in results.items() if a.expansion] == ["HS-1011"]


def test_scores_only_for_scored_statuses() -> None:
    for result in assess_all(seed_world()).values():
        if result.status in (Status.QL, Status.QL_CANDIDATE, Status.NURTURE):
            assert result.score is not None
            assert result.score == sum(f.points for f in result.breakdown)
        else:
            assert result.score is None


def test_bundle_unchanged_by_assessment() -> None:
    bundle = seed()
    before = [m.model_dump() for m in bundle.inbound]
    assess_all(seed_world(bundle))
    assert [m.model_dump() for m in bundle.inbound] == before
