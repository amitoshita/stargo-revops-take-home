"""Turn a service snapshot into API shapes. Presentation only: no rules are decided here."""

from __future__ import annotations

from typing import Literal

from app.agents.agent_b import wants_draft
from app.api.schemas import LeadDetail, LeadRow, MessageOut
from app.core.timeutil import to_il
from app.kpi.compute import person_name
from app.service import Service, Snapshot, ran_modes

CompanySource = Literal["crm", "crm_company_record", "stated", "none"]


def _company(snap: Snapshot, person_id: str) -> tuple[str | None, CompanySource]:
    ctx = snap.world.leads[person_id]
    if ctx.crm and ctx.crm.company_name:
        return ctx.crm.company_name, "crm"
    if ctx.company and ctx.company.name:
        return ctx.company.name, "crm_company_record"
    for analysis in reversed(ctx.analyses):
        if analysis.extraction and analysis.extraction.company_facts.company_name:
            return analysis.extraction.company_facts.company_name, "stated"
    return None, "none"


def lead_row(snap: Snapshot, person_id: str) -> LeadRow:
    ctx = snap.world.leads[person_id]
    assessment = snap.assessments[person_id]
    latest = ctx.inbound[-1]
    company, company_source = _company(snap, person_id)
    return LeadRow(
        person_id=person_id,
        name=person_name(snap.world.identity.persons[person_id]),
        company=company,
        company_source=company_source,
        channel=latest.channel,
        received_at=to_il(latest.received_at),
        message_count=len(ctx.inbound),
        status=assessment.status,
        owner=assessment.owner,
        score=assessment.score,
        band=assessment.band,
        analysis_modes=ran_modes(ctx.analyses),
        expansion=assessment.expansion,
        accepted_by=assessment.accepted_by.decided_by if assessment.accepted_by else None,
    )


def lead_rows(snap: Snapshot) -> list[LeadRow]:
    rows = [lead_row(snap, pid) for pid in snap.world.leads]
    return sorted(rows, key=lambda r: r.received_at, reverse=True)


def lead_detail(service: Service, snap: Snapshot, person_id: str) -> LeadDetail:
    ctx = snap.world.leads[person_id]
    company, company_source = _company(snap, person_id)
    assessment = snap.assessments[person_id]
    return LeadDetail(
        person_id=person_id,
        name=person_name(snap.world.identity.persons[person_id]),
        company=company,
        company_source=company_source,
        crm=ctx.crm,
        messages=[
            MessageOut(
                id=m.id,
                origin=m.origin,
                channel=m.channel,
                source=m.source,
                received_at=to_il(m.received_at),
                subject=m.subject,
                body=m.body,
                analysis=snap.analyses.get(m.id),
            )
            for m in ctx.inbound
        ],
        assessment=assessment,
        decisions=ctx.decisions,
        draft=service.stored_draft(snap, person_id),
        draft_available=wants_draft(assessment, service.latest_extraction(snap, person_id)),
    )
