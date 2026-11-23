"""Request and response models for the HTTP API. Shapes only; no business logic."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.schemas import AgentBOutput, MessageAnalysis
from app.core.enums import AnalysisMode, Channel, Source, Status
from app.ingest.schemas import CrmContact, IngestError, PipelineEvent, SalesDecision
from app.rules.schemas import Assessment, Band, ReviewFlag


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PasteRequest(_In):
    from_name: str | None = Field(default=None, max_length=200)
    from_email: str | None = Field(default=None, max_length=320)
    linkedin_url: str | None = Field(default=None, max_length=300)
    channel: Channel = Channel.OTHER
    source: Source | None = None  # blank = source not recorded
    subject: str | None = Field(default=None, max_length=300)
    body: str = Field(default="", max_length=20_000)  # length rule enforced by ingest
    received_at: str | None = None  # ISO with offset; default now


class DecisionRequest(_In):
    decision: Literal["accepted", "rejected"]
    decided_by: str = Field(min_length=1, max_length=100)
    decided_at: str | None = None  # ISO with offset; default now
    note: str | None = Field(default=None, max_length=1000)


class ModeOut(BaseModel):
    llm_enabled: bool
    label: str
    model: str | None
    seed_analysis: str
    pasted_analysis: str


class LeadRow(BaseModel):
    person_id: str
    name: str | None
    company: str | None
    company_source: Literal["crm", "crm_company_record", "stated", "none"]
    channel: Channel
    received_at: datetime  # latest inbound, Asia/Jerusalem
    message_count: int
    status: Status
    owner: str | None
    score: int | None
    band: Band | None
    analysis_modes: list[AnalysisMode]
    expansion: bool
    accepted_by: str | None
    review_flags: list[ReviewFlag]  # messages awaiting a human; they change nothing until then


class MessageOut(BaseModel):
    id: str
    origin: str
    channel: Channel
    source: Source | None
    received_at: datetime  # Asia/Jerusalem
    subject: str | None
    body: str
    analysis: MessageAnalysis | None


class LeadDetail(BaseModel):
    person_id: str
    name: str | None
    company: str | None
    company_source: str
    crm: CrmContact | None
    messages: list[MessageOut]
    assessment: Assessment
    decisions: list[SalesDecision]
    draft: AgentBOutput | None
    draft_available: bool


class PasteResult(BaseModel):
    inbound_id: str
    person_id: str
    analysis: MessageAnalysis
    lead: LeadRow


class SuppressionRow(BaseModel):
    person_id: str
    name: str | None
    inbound_id: str
    requested_at: datetime


class CrmActivityRow(BaseModel):
    person_id: str
    name: str | None
    company: str | None
    decisions: list[SalesDecision]
    events: list[PipelineEvent]
    note: str


class ErrorOut(BaseModel):
    detail: list[str]


class IngestErrorsOut(BaseModel):
    errors: list[IngestError]


class WeekQuery(BaseModel):
    week: date
