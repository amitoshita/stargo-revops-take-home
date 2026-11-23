"""Assess one person: exclusions → QL gate → status → owner → score → rationale.

Precedence (docs/ASSUMPTIONS.md D16): unsubscribe anywhere → suppressed; an instruction
attempt or a failed analysis anywhere → needs review; then exclusions; then the gate.
"""

from __future__ import annotations

from dataclasses import replace

from app.core.enums import Intent, Status
from app.rules.context import LeadContext
from app.rules.exclusions import find_exclusion
from app.rules.ql_gate import build_checklist
from app.rules.rationale import build_rationale
from app.rules.routing import route
from app.rules.schemas import AcceptedBy, Assessment, Band, QLChecklist, ScoreFactor
from app.rules.scoring import score

SCORED_STATUSES = frozenset({Status.QL, Status.QL_CANDIDATE, Status.NURTURE})


def _gate_status(checklist: QLChecklist, ctx: LeadContext) -> tuple[Status, str]:
    """D12/D13: one map for accepted and not-yet-accepted leads; acceptance never overrides."""
    latest = ctx.latest_decision
    if latest is not None and latest.decision == "rejected":
        return Status.DISQUALIFIED, "gate:rejected_by_sales"
    accepted = latest is not None and latest.decision == "accepted"
    if checklist.c1_to_c4_pass:
        return (
            (Status.QL, "gate:all_pass")
            if accepted
            else (Status.QL_CANDIDATE, "gate:awaiting_acceptance")
        )
    prefix = "gate:accepted_but_" if accepted else "gate:"
    hard = [
        name
        for name in checklist.failing
        if name == "C2" or (name == "C1" and not checklist.c1_fails_only_on_region)
    ]
    if hard:  # C2 fails, or C1 fails on vertical or size
        return Status.DISQUALIFIED, prefix + "fails_" + "_".join(hard)
    if checklist.failing:  # C3/C4 fail, or C1 fails only on region (D17)
        return Status.NURTURE, prefix + "fails_" + "_".join(checklist.failing)
    if accepted:
        return Status.QL_CANDIDATE, "gate:accepted_with_unknowns"  # D14
    return Status.NURTURE, "gate:incomplete"


def _accepted_by(ctx: LeadContext) -> AcceptedBy | None:
    latest = ctx.latest_decision
    if latest is None or latest.decision != "accepted":
        return None
    return AcceptedBy(
        decision_id=latest.id, decided_by=latest.decided_by, decided_at=latest.decided_at
    )


def assess(ctx: LeadContext) -> Assessment:
    exclusion = None
    checklist: QLChecklist | None = None

    if any(e.intent == Intent.UNSUBSCRIBE for e in ctx.extractions):
        status, reason = Status.SUPPRESSED, "suppressed:unsubscribe"
    elif any(a.instruction_attempt for a in ctx.analyses):
        status, reason = Status.NEEDS_REVIEW, "needs_review:instruction_attempt"
    elif any(a.failure is not None for a in ctx.analyses):
        kinds = sorted({a.failure.kind for a in ctx.analyses if a.failure})
        status, reason = Status.NEEDS_REVIEW, "needs_review:analysis_failed:" + ",".join(kinds)
    elif (exclusion := find_exclusion(ctx)) is not None:
        status, reason = Status.EXCLUDED, f"excluded:{exclusion.kind}"
        checklist = build_checklist(ctx)
    else:
        checklist = build_checklist(ctx)
        status, reason = _gate_status(checklist, ctx)

    # An instruction attempt must not influence the owner: route on CRM facts only.
    routing_ctx = replace(ctx, analyses=[]) if status == Status.NEEDS_REVIEW else ctx
    owner = route(routing_ctx, status, exclusion)
    total: int | None = None
    band: Band | None = None
    factors: list[ScoreFactor] = []
    if status in SCORED_STATUSES:
        total, band, factors = score(ctx)

    readable = exclusion.label if exclusion else reason.split(":", 1)[-1].replace("_", " ")
    return Assessment(
        status=status,
        reason=reason,
        checklist=checklist,
        owner=owner.owner,
        owner_basis=owner.basis,
        score=total,
        band=band,
        breakdown=factors,
        rationale=build_rationale(status, readable, checklist),
        accepted_by=_accepted_by(ctx),
        expansion=exclusion is not None and exclusion.kind == "customer",
    )
