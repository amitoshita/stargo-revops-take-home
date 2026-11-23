"""The QL gate (QLS §1): five conditions, each pass / fail / unknown with evidence.

Precedence for company facts: CRM contact row (verified) → CRM company record for the same
normalized domain (verified, labelled) → what the sender states (unverified).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.schemas import AgentAOutput, Evidence
from app.core.enums import ICP_REGIONS, SOLVED_PROBLEMS, ProblemCategory, Region
from app.core.timeutil import to_il
from app.ingest.normalize import (
    ICP_VERTICALS,
    NON_ICP_VERTICALS,
    country_from_text,
    display_country,
    normalize_country,
    normalize_vertical,
    region_for_country,
)
from app.rules.context import LeadContext
from app.rules.schemas import FactSource, QLChecklist, QLCondition
from app.rules.seniority import classify_level, irrelevant_function

MIN_EMPLOYEES = 20
OWNER_MAX_EMPLOYEES = 200


@dataclass(frozen=True)
class Fact[T]:
    value: T
    source: FactSource

    @property
    def verified(self) -> bool:
        return self.source in ("crm", "crm_company_record")

    def label(self) -> str:
        return {
            "crm": "CRM",
            "crm_company_record": "from CRM company record",
            "message": "stated, unverified",
            "sales_decision": "sales decision",
            "none": "unknown",
        }[self.source]


def _quotes(extractions: list[AgentAOutput], field: str) -> list[str]:
    out: list[str] = []
    for extraction in extractions:
        for ev in extraction.evidence:
            if ev.field == field:
                out.append(_quote_text(ev))
    return out


def _quote_text(ev: Evidence) -> str:
    return f'"{ev.quote}"' + (f" ({ev.translation})" if ev.translation else "")


# ---- company facts ----------------------------------------------------------


def vertical_fact(ctx: LeadContext) -> Fact[str] | None:
    if ctx.crm and ctx.crm.vertical:
        return Fact(ctx.crm.vertical, "crm")
    if ctx.company and ctx.company.vertical:
        return Fact(ctx.company.vertical, "crm_company_record")
    for extraction in reversed(ctx.extractions):
        vertical = normalize_vertical(extraction.company_facts.vertical)
        if vertical:
            return Fact(vertical, "message")
    return None


def employees_fact(ctx: LeadContext) -> Fact[int] | None:
    if ctx.crm and ctx.crm.employees is not None:
        return Fact(ctx.crm.employees, "crm")
    if ctx.company and ctx.company.employees is not None:
        return Fact(ctx.company.employees, "crm_company_record")
    for extraction in reversed(ctx.extractions):
        if extraction.company_facts.employees is not None:
            return Fact(extraction.company_facts.employees, "message")
    return None


def country_fact(ctx: LeadContext) -> Fact[str] | None:
    if ctx.crm and ctx.crm.country:
        return Fact(ctx.crm.country, "crm")
    if ctx.company and ctx.company.country:
        return Fact(ctx.company.country, "crm_company_record")
    for extraction in reversed(ctx.extractions):
        stated = extraction.company_facts.country
        code = normalize_country(stated) or country_from_text(stated)
        if code:
            return Fact(code, "message")
    return None


def region_fact(ctx: LeadContext) -> Fact[Region] | None:
    country = country_fact(ctx)
    if country is None:
        return None
    region = region_for_country(country.value)
    return Fact(region, country.source) if region else None


def title_fact(ctx: LeadContext) -> Fact[str] | None:
    if ctx.crm and ctx.crm.job_title:
        return Fact(ctx.crm.job_title, "crm")
    for extraction in reversed(ctx.extractions):
        if extraction.buyer_role:
            return Fact(extraction.buyer_role, "message")
    return None


# ---- conditions -------------------------------------------------------------


def company_fit(ctx: LeadContext) -> QLCondition:
    vertical, employees, region = vertical_fact(ctx), employees_fact(ctx), region_fact(ctx)
    country = country_fact(ctx)
    parts: list[str] = []
    fails: list[str] = []
    failed_on: list[str] = []
    unknowns: list[str] = []

    if vertical is None:
        unknowns.append("vertical")
    else:
        parts.append(f"vertical {vertical.value} ({vertical.label()})")
        if vertical.value in NON_ICP_VERTICALS:
            fails.append(f"vertical {vertical.value} is not an ICP vertical")
            failed_on.append("vertical")
        elif vertical.value not in ICP_VERTICALS:
            unknowns.append(f"vertical ('{vertical.value}' not recognised)")
    if employees is None:
        unknowns.append("company size")
    else:
        parts.append(f"{employees.value} employees ({employees.label()})")
        if employees.value < MIN_EMPLOYEES:
            fails.append(f"{employees.value} employees is under {MIN_EMPLOYEES}")
            failed_on.append("size")
    if region is None or country is None:
        unknowns.append("region")
    else:
        parts.append(f"country {display_country(country.value)} ({country.label()})")
        if region.value not in ICP_REGIONS:
            fails.append(f"country {display_country(country.value)} is outside ICP regions")
            failed_on.append("region")

    facts = [f for f in (vertical, employees, region) if f is not None]
    verified = bool(facts) and all(f.verified for f in facts) and len(facts) == 3
    source: FactSource = "crm" if verified else ("message" if facts else "none")
    if fails:
        return QLCondition(
            status="fail",
            reason="; ".join(fails),
            evidence=parts,
            source=source,
            verified=verified,
            failed_on=failed_on,
        )
    if unknowns:
        return QLCondition(
            status="unknown",
            reason="unknown: " + ", ".join(unknowns),
            evidence=parts,
            source=source,
            verified=False,
        )
    return QLCondition(
        status="pass",
        reason="ICP vertical, 20+ employees, ICP region",
        evidence=parts,
        source=source,
        verified=verified,
    )


def relevant_buyer(ctx: LeadContext) -> QLCondition:
    title = title_fact(ctx)
    if title is None:
        return QLCondition(status="unknown", reason="no job title or stated role")
    evidence = [f"{title.value} ({title.label()})", *_quotes(ctx.extractions, "buyer_role")]
    common = {"evidence": evidence, "source": title.source, "verified": title.verified}
    if irrelevant_function(title.value):
        return QLCondition(status="fail", reason="role is outside the buying functions", **common)
    level = classify_level(title.value)
    if level in ("senior", "manager"):
        return QLCondition(status="pass", reason="manager level or above", **common)
    if level == "owner":
        employees = employees_fact(ctx)
        if employees is None:
            return QLCondition(status="unknown", reason="owner, company size unknown", **common)
        if employees.value < OWNER_MAX_EMPLOYEES:
            return QLCondition(
                status="pass",
                reason=f"owner/founder at a company under {OWNER_MAX_EMPLOYEES} employees",
                evidence=[*evidence, f"{employees.value} employees ({employees.label()})"],
                source=title.source if title.source != "crm" else employees.source,
                verified=title.verified and employees.verified,
            )
        return QLCondition(
            status="fail", reason="owner title at a 200+ company without a manager role", **common
        )
    if level == "below_manager":
        return QLCondition(status="fail", reason="below manager level", **common)
    return QLCondition(status="unknown", reason="seniority cannot be read from the title", **common)


def data_problem(ctx: LeadContext) -> QLCondition:
    solved = [e for e in ctx.extractions if e.problem_category in SOLVED_PROBLEMS]
    quotes = _quotes(ctx.extractions, "data_problem")
    if solved:
        categories = sorted({e.problem_category.value for e in solved})
        return QLCondition(
            status="pass",
            reason="problem Stargo solves: " + ", ".join(categories),
            evidence=quotes,
            source="message",
            verified=False,
        )
    stated_other = [
        e for e in ctx.extractions if e.problem_category == ProblemCategory.OTHER and e.data_problem
    ]
    if stated_other:
        return QLCondition(
            status="fail",
            reason="stated problem is not one Stargo solves",
            evidence=quotes or [str(stated_other[-1].data_problem)],
            source="message",
            verified=False,
        )
    return QLCondition(status="unknown", reason="no data problem stated")


_POSITIVE = ("explicit_request", "meeting_request", "soft_positive")


def expressed_interest(ctx: LeadContext) -> QLCondition:
    """Follows the person's latest stance: a later decline overrides earlier interest."""
    quotes = _quotes(ctx.extractions, "interest")
    for extraction in reversed(ctx.extractions):
        if extraction.interest_level in _POSITIVE:
            return QLCondition(
                status="pass",
                reason=f"latest stance: {extraction.interest_level.replace('_', ' ')}",
                evidence=quotes,
                source="message",
            )
        if extraction.interest_level == "declined":
            return QLCondition(
                status="fail", reason="latest stance: not interested", evidence=quotes,
                source="message",
            )  # fmt: skip
    return QLCondition(status="fail", reason="no demo, call, pricing or pilot request")


def sales_acceptance(ctx: LeadContext) -> QLCondition:
    latest = ctx.latest_decision
    if latest is None:
        return QLCondition(status="unknown", reason="no sales decision yet")
    when = to_il(latest.decided_at).strftime("%Y-%m-%d %H:%M")
    evidence = [f"{latest.id}: {latest.decision} by {latest.decided_by} at {when} (IL)"]
    if latest.decision == "accepted":
        return QLCondition(
            status="pass", reason="accepted by sales", evidence=evidence,
            source="sales_decision", verified=True,
        )  # fmt: skip
    return QLCondition(
        status="fail", reason="rejected by sales", evidence=evidence,
        source="sales_decision", verified=True,
    )  # fmt: skip


def build_checklist(ctx: LeadContext) -> QLChecklist:
    return QLChecklist(
        c1_company_fit=company_fit(ctx),
        c2_relevant_buyer=relevant_buyer(ctx),
        c3_data_problem=data_problem(ctx),
        c4_expressed_interest=expressed_interest(ctx),
        c5_sales_acceptance=sales_acceptance(ctx),
    )
