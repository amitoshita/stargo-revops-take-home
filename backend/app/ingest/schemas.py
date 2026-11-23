"""Validated, normalized records produced by ingest."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.core.enums import Channel, Region, Source

Origin = Literal["seed", "ui"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InboundMessage(_Frozen):
    id: str
    origin: Origin
    channel: Channel
    source: Source | None  # None = source not recorded
    received_at: AwareDatetime
    from_name: str | None
    email: str | None  # normalized
    linkedin: str | None  # normalized: linkedin.com/in/<slug>
    subject: str | None
    body: str = Field(min_length=1, max_length=5000)

    @property
    def identity_keys(self) -> list[str]:
        return [key for key in (self.email, self.linkedin) if key]


class CrmContact(_Frozen):
    record_id: str
    first_name: str | None
    last_name: str | None
    email: str | None
    job_title: str | None
    linkedin: str | None
    company_name: str | None
    company_domain: str | None  # normalized registrable domain
    country: str | None  # ISO alpha-2
    region: Region | None
    vertical: str | None
    employees: int | None
    lifecycle_stage: str | None
    lead_status: str | None
    is_customer: bool
    open_deal_id: str | None
    open_deal_created: date | None
    owner: str | None
    last_activity_date: date | None

    @property
    def full_name(self) -> str | None:
        name = " ".join(part for part in (self.first_name, self.last_name) if part)
        return name or None


class SalesDecision(_Frozen):
    """Matched to a person by normalized email or LinkedIn (either may be blank, not both)."""

    id: str
    origin: Origin
    contact_email: str | None  # normalized; seed decisions always carry one
    decision: Literal["accepted", "rejected"]
    decided_by: str
    decided_at: AwareDatetime
    note: str | None
    contact_linkedin: str | None = None  # normalized: linkedin.com/in/<slug>
    person_id: str | None = None  # the person it was recorded for (UI decisions; reference only)

    @model_validator(mode="after")
    def _has_contact(self) -> SalesDecision:
        if not self.contact_email and not self.contact_linkedin:
            raise ValueError("a decision needs a contact email or LinkedIn URL")
        return self

    @property
    def identity_keys(self) -> tuple[str | None, str | None]:
        return self.contact_email, self.contact_linkedin


PipelineEventType = Literal["meeting_booked", "meeting_held", "opportunity_created"]


class PipelineEvent(_Frozen):
    id: str
    type: PipelineEventType
    contact_email: str  # normalized
    occurred_at: AwareDatetime


class IngestError(_Frozen):
    record_ref: str  # record id if present, else a hash; never message content
    kind: Literal["inbound", "crm", "decision", "pipeline_event"]
    reasons: list[str]


FeedStatus = Literal["received", "not_received"]


class CompanyRecord(_Frozen):
    """Company facts aggregated from CRM rows sharing a normalized domain."""

    domain: str
    name: str | None
    country: str | None
    region: Region | None
    vertical: str | None
    employees: int | None
    source_record_ids: list[str]
