"""HTTP routes. Thin: parse the request, call the service, shape the response."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse

from app.agents.schemas import AgentBOutput
from app.api.schemas import (
    CrmActivityRow,
    DecisionRequest,
    IngestErrorsOut,
    LeadDetail,
    LeadRow,
    ModeOut,
    PasteRequest,
    PasteResult,
    SuppressionRow,
)
from app.api.views import lead_detail, lead_row, lead_rows
from app.ingest.schemas import SalesDecision
from app.kpi.schemas import KpiPack
from app.kpi.window import WEEK_UNDER_REVIEW
from app.service import Service

router = APIRouter(prefix="/api")


def get_service(request: Request) -> Service:
    service: Service = request.app.state.service
    return service


ServiceDep = Annotated[Service, Depends(get_service)]
WeekParam = Annotated[date, Query(description="Sunday that starts the week (Asia/Jerusalem)")]


@router.get("/mode")
def mode(service: ServiceDep) -> ModeOut:
    return ModeOut.model_validate(service.mode())


@router.get("/leads")
def leads(service: ServiceDep) -> list[LeadRow]:
    return lead_rows(service.snapshot())


@router.get("/leads/{person_id}")
def lead(person_id: str, service: ServiceDep) -> LeadDetail:
    snap = service.snapshot()
    service.require_lead(snap, person_id)  # 404 if unknown
    return lead_detail(service, snap, person_id)


@router.post("/inbound", status_code=201)
def paste(body: PasteRequest, service: ServiceDep) -> PasteResult:
    message, person_id = service.paste(body.model_dump())
    snap = service.snapshot()
    return PasteResult(
        inbound_id=message.id,
        person_id=person_id,
        analysis=snap.analyses[message.id],
        lead=lead_row(snap, person_id),
    )


@router.post("/leads/{person_id}/decisions", status_code=201)
def decide(person_id: str, body: DecisionRequest, service: ServiceDep) -> SalesDecision:
    return service.decide(person_id, body.decision, body.decided_by, body.decided_at, body.note)


@router.post("/leads/{person_id}/draft", status_code=201)
def draft(person_id: str, service: ServiceDep) -> AgentBOutput:
    return service.draft(person_id)


@router.get("/kpi")
def kpi(service: ServiceDep, week: WeekParam = WEEK_UNDER_REVIEW.sunday) -> KpiPack:
    return service.kpi(week)


@router.get("/kpi/markdown", response_class=PlainTextResponse)
def kpi_markdown(service: ServiceDep, week: WeekParam = WEEK_UNDER_REVIEW.sunday) -> str:
    return service.kpi_markdown(week)


@router.get("/suppression-log")
def suppression_log(service: ServiceDep) -> list[SuppressionRow]:
    return [SuppressionRow.model_validate(row) for row in service.suppression_log()]


@router.get("/crm-activity")
def crm_activity(service: ServiceDep) -> list[CrmActivityRow]:
    return [CrmActivityRow.model_validate(row) for row in service.crm_contacts_with_activity()]


@router.get("/ingest-errors")
def ingest_errors(service: ServiceDep) -> IngestErrorsOut:
    return IngestErrorsOut(errors=service.ingest_errors())
