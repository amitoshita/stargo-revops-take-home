"""Priority score 0–100 (QLS §4). Explainable per factor; never changes the status."""

from __future__ import annotations

from app.core.enums import ICP_REGIONS, SOLVED_PROBLEMS, ProblemCategory
from app.ingest.normalize import ICP_VERTICALS
from app.rules.context import LeadContext
from app.rules.ql_gate import employees_fact, region_fact, title_fact, vertical_fact
from app.rules.schemas import Band, ScoreFactor
from app.rules.seniority import classify_level


def interest_factor(ctx: LeadContext) -> ScoreFactor:
    for e in reversed(ctx.extractions):
        if e.interest_level == "explicit_request":
            return ScoreFactor(
                name="Interest", points=30, max=30, basis="asks for a demo, pricing or pilot"
            )
        if e.interest_level == "meeting_request":
            return ScoreFactor(name="Interest", points=22, max=30, basis="asks for a call")
        if e.interest_level == "soft_positive":
            return ScoreFactor(name="Interest", points=10, max=30, basis="soft positive reply")
        if e.interest_level == "declined":
            return ScoreFactor(name="Interest", points=0, max=30, basis="declined")
    return ScoreFactor(name="Interest", points=0, max=30, basis="no request")


def problem_factor(ctx: LeadContext) -> ScoreFactor:
    solved = [e for e in ctx.extractions if e.problem_category in SOLVED_PROBLEMS]
    if any(e.volume_stated for e in solved):
        return ScoreFactor(
            name="Problem fit", points=25, max=25, basis="solved problem with stated volume"
        )
    if solved:
        return ScoreFactor(name="Problem fit", points=18, max=25, basis="solved problem")
    if any(e.problem_category == ProblemCategory.OTHER for e in ctx.extractions):
        return ScoreFactor(name="Problem fit", points=6, max=25, basis="related, not a listed pain")
    return ScoreFactor(name="Problem fit", points=0, max=25, basis="unknown", unknown=True)


def buyer_factor(ctx: LeadContext) -> ScoreFactor:
    title = title_fact(ctx)
    if title is None:
        return ScoreFactor(name="Buyer", points=0, max=20, basis="unknown", unknown=True)
    level = classify_level(title.value)
    points = {"senior": 20, "owner": 20, "manager": 14, "below_manager": 4, "unknown": 0}[level]
    return ScoreFactor(
        name="Buyer",
        points=points,
        max=20,
        basis=f"{title.value} ({title.label()})",
        unknown=level == "unknown",
    )


def company_factor(ctx: LeadContext) -> ScoreFactor:
    points, notes, unknown = 0, [], False
    vertical, employees, region = vertical_fact(ctx), employees_fact(ctx), region_fact(ctx)
    for fact, full, ok, label in (
        (vertical, 6, vertical is not None and vertical.value in ICP_VERTICALS, "vertical"),
        (region, 5, region is not None and region.value in ICP_REGIONS, "region"),
        (employees, 4, employees is not None and employees.value >= 20, "size"),
    ):
        if fact is None:
            unknown = True
            notes.append(f"{label} unknown")
        elif ok:
            points += full if fact.verified else full // 2
            notes.append(f"{label} ok" + ("" if fact.verified else " (unverified, half)"))
        else:
            notes.append(f"{label} outside ICP")
    return ScoreFactor(
        name="Company fit", points=points, max=15, basis="; ".join(notes), unknown=unknown
    )


def timing_factor(ctx: LeadContext) -> ScoreFactor:
    for e in reversed(ctx.extractions):
        if e.timing in ("this_week", "next_weeks", "this_quarter"):
            return ScoreFactor(name="Timing", points=10, max=10, basis=e.timing.replace("_", " "))
        if e.timing == "later":
            return ScoreFactor(name="Timing", points=4, max=10, basis="later")
    return ScoreFactor(name="Timing", points=0, max=10, basis="none stated")


def band_for(score: int) -> Band:
    return "A" if score >= 70 else ("B" if score >= 40 else "nurture")


def score(ctx: LeadContext) -> tuple[int, Band, list[ScoreFactor]]:
    factors = [
        interest_factor(ctx),
        problem_factor(ctx),
        buyer_factor(ctx),
        company_factor(ctx),
        timing_factor(ctx),
    ]
    total = sum(f.points for f in factors)
    return total, band_for(total), factors
