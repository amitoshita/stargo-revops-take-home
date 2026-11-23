"""Turn raw dicts (seed JSON, CSV rows, UI form) into validated records or clear errors."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from pydantic import ValidationError

from app.core.enums import Channel, Source
from app.core.logging_setup import short_hash
from app.core.timeutil import parse_aware
from app.ingest.normalize import (
    normalize_country,
    normalize_domain,
    normalize_email,
    normalize_linkedin,
    normalize_vertical,
    region_for_country,
)
from app.ingest.schemas import (
    CrmContact,
    InboundMessage,
    IngestError,
    Origin,
    PipelineEvent,
    SalesDecision,
)

MAX_BODY_CHARS = 5000


def _text(raw: Mapping[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ref(raw: Mapping[str, Any], id_key: str) -> str:
    rid = _text(raw, id_key)
    return rid if rid else f"anon-{short_hash(repr(sorted(raw.items(), key=str)))}"


def _timestamp(value: Any, errors: list[str], label: str) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            errors.append(f"{label} has no time zone")
            return None
        return value
    if not value:
        errors.append(f"{label} is missing")
        return None
    try:
        return parse_aware(str(value))
    except ValueError:
        errors.append(f"{label} is not an ISO timestamp with a time zone offset")
        return None


def parse_inbound(raw: Mapping[str, Any], origin: Origin) -> InboundMessage | IngestError:
    """Validate one inbound message. Never raises; returns an IngestError with reasons."""
    errors: list[str] = []
    ref = _ref(raw, "id")

    email: str | None = None
    linkedin: str | None = None
    try:
        email = normalize_email(_text(raw, "from_email"))
    except ValueError:
        errors.append("invalid email address")
    try:
        linkedin = normalize_linkedin(_text(raw, "linkedin_url"))
    except ValueError:
        errors.append("invalid LinkedIn profile URL")
    if email is None and linkedin is None and not errors:
        errors.append("an email address or a LinkedIn URL is required")

    body = _text(raw, "body")
    if body is None:
        errors.append("message text is empty")
    elif len(body) > MAX_BODY_CHARS:
        errors.append(f"message text is longer than {MAX_BODY_CHARS} characters")

    channel_raw = _text(raw, "channel")
    channel: Channel | None = None
    try:
        channel = Channel(channel_raw) if channel_raw else Channel.OTHER
    except ValueError:
        errors.append(f"unknown channel (allowed: {', '.join(c.value for c in Channel)})")

    source_raw = _text(raw, "source")
    source: Source | None = None
    if source_raw:
        try:
            source = Source(source_raw)
        except ValueError:
            errors.append(f"unknown source (allowed: {', '.join(s.value for s in Source)})")

    received_at = _timestamp(raw.get("received_at"), errors, "received_at")

    if errors or body is None or channel is None or received_at is None:
        return IngestError(record_ref=ref, kind="inbound", reasons=errors)
    try:
        return InboundMessage(
            id=ref,
            origin=origin,
            channel=channel,
            source=source,
            received_at=received_at,
            from_name=_text(raw, "from_name"),
            email=email,
            linkedin=linkedin,
            subject=_text(raw, "subject"),
            body=body,
        )
    except ValidationError as exc:
        return IngestError(record_ref=ref, kind="inbound", reasons=[e["msg"] for e in exc.errors()])


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def _date_or_none(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_crm_row(raw: Mapping[str, Any]) -> CrmContact | IngestError:
    errors: list[str] = []
    ref = _ref(raw, "record_id")
    email: str | None = None
    linkedin: str | None = None
    try:
        email = normalize_email(_text(raw, "email"))
    except ValueError:
        errors.append("invalid email address")
    try:
        linkedin = normalize_linkedin(_text(raw, "linkedin_url"))
    except ValueError:
        errors.append("invalid LinkedIn profile URL")
    if errors:
        return IngestError(record_ref=ref, kind="crm", reasons=errors)

    country = normalize_country(_text(raw, "country"))
    return CrmContact(
        record_id=ref,
        first_name=_text(raw, "first_name"),
        last_name=_text(raw, "last_name"),
        email=email,
        job_title=_text(raw, "job_title"),
        linkedin=linkedin,
        company_name=_text(raw, "company_name"),
        company_domain=normalize_domain(_text(raw, "company_domain")),
        country=country,
        region=region_for_country(country),
        vertical=normalize_vertical(_text(raw, "vertical")),
        employees=_int_or_none(_text(raw, "employees")),
        lifecycle_stage=(_text(raw, "lifecycle_stage") or "").lower() or None,
        lead_status=_text(raw, "lead_status"),
        is_customer=(_text(raw, "is_customer") or "").lower() == "true",
        open_deal_id=_text(raw, "open_deal_id"),
        open_deal_created=_date_or_none(_text(raw, "open_deal_created")),
        owner=_text(raw, "owner"),
        last_activity_date=_date_or_none(_text(raw, "last_activity_date")),
    )


def parse_decision(raw: Mapping[str, Any], origin: Origin) -> SalesDecision | IngestError:
    errors: list[str] = []
    ref = _ref(raw, "id")
    email: str | None = None
    linkedin: str | None = None
    try:
        email = normalize_email(_text(raw, "contact_email"))
    except ValueError:
        errors.append("invalid contact email")
    try:
        linkedin = normalize_linkedin(_text(raw, "contact_linkedin"))
    except ValueError:
        errors.append("invalid contact LinkedIn URL")
    if email is None and linkedin is None and not errors:
        errors.append("a contact email or LinkedIn URL is required")
    decision = _text(raw, "decision")
    if decision not in ("accepted", "rejected"):
        errors.append("decision must be 'accepted' or 'rejected'")
    decided_by = _text(raw, "decided_by")
    if decided_by is None:
        errors.append("decided_by is required")
    decided_at = _timestamp(raw.get("decided_at"), errors, "decided_at")
    if errors or (email is None and linkedin is None) or decided_by is None or decided_at is None:
        return IngestError(record_ref=ref, kind="decision", reasons=errors)
    return SalesDecision(
        id=ref,
        origin=origin,
        contact_email=email,
        contact_linkedin=linkedin,
        person_id=_text(raw, "person_id"),
        decision="accepted" if decision == "accepted" else "rejected",
        decided_by=decided_by,
        decided_at=decided_at,
        note=_text(raw, "note"),
    )


_EVENT_TYPES = ("meeting_booked", "meeting_held", "opportunity_created")


def parse_pipeline_event(raw: Mapping[str, Any]) -> PipelineEvent | IngestError:
    errors: list[str] = []
    ref = _ref(raw, "id")
    email: str | None = None
    try:
        email = normalize_email(_text(raw, "contact_email"))
    except ValueError:
        errors.append("invalid contact email")
    if email is None and not errors:
        errors.append("contact email is required")
    event_type = _text(raw, "type")
    if event_type not in _EVENT_TYPES:
        errors.append(f"type must be one of {', '.join(_EVENT_TYPES)}")
    occurred_at = _timestamp(raw.get("occurred_at"), errors, "occurred_at")
    if errors or email is None or occurred_at is None:
        return IngestError(record_ref=ref, kind="pipeline_event", reasons=errors)
    return PipelineEvent.model_validate(
        {"id": ref, "type": event_type, "contact_email": email, "occurred_at": occurred_at}
    )
