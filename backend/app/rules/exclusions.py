"""Never a new-acquisition QL (QLS §2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from app.core.enums import Intent
from app.core.timeutil import to_il
from app.ingest.normalize import VENDOR_VERTICALS
from app.ingest.schemas import CrmContact
from app.rules.context import LeadContext

ExclusionKind = Literal[
    "customer", "open_deal", "competitor_vendor", "investor", "job_seeker", "auto_reply"
]

LABELS: dict[ExclusionKind, str] = {
    "customer": "existing customer (expansion)",
    "open_deal": "open deal created before first inbound and acceptance",
    "competitor_vendor": "competitor or vendor",
    "investor": "investor enquiry",
    "job_seeker": "job seeker or student",
    "auto_reply": "auto-reply",
}


@dataclass(frozen=True)
class Exclusion:
    kind: ExclusionKind
    evidence: str

    @property
    def label(self) -> str:
        return LABELS[self.kind]


def is_pre_existing_deal(
    crm: CrmContact | None, first_inbound: date | None, first_acceptance: datetime | None
) -> bool:
    """Deal created before the first inbound AND before the first acceptance (IL dates).

    A deal with neither an inbound nor an acceptance to compare against is pre-existing.
    """
    if crm is None or crm.open_deal_id is None or crm.open_deal_created is None:
        return False
    anchors = [d for d in (first_inbound, first_acceptance and to_il(first_acceptance).date()) if d]
    return all(crm.open_deal_created < anchor for anchor in anchors)


def _is_vendor(ctx: LeadContext) -> str | None:
    crm = ctx.crm
    if crm and crm.lead_status and "competitor" in crm.lead_status.lower():
        return "CRM lead status: competitor"
    if crm and crm.vertical in VENDOR_VERTICALS:
        return f"CRM vertical: {crm.vertical}"
    if ctx.company and ctx.company.vertical in VENDOR_VERTICALS:
        return f"CRM company record vertical: {ctx.company.vertical}"
    if any(e.company_facts.is_software_vendor for e in ctx.extractions):
        return "sender states they build competing or adjacent software"
    return None


def find_exclusion(ctx: LeadContext) -> Exclusion | None:
    crm = ctx.crm
    if crm and crm.is_customer:
        return Exclusion("customer", f"{crm.record_id} is_customer = true")
    if is_pre_existing_deal(crm, ctx.first_inbound_date, ctx.first_acceptance_at):
        assert crm is not None
        return Exclusion("open_deal", f"deal {crm.open_deal_id} created {crm.open_deal_created}")
    vendor = _is_vendor(ctx)
    if vendor:
        return Exclusion("competitor_vendor", vendor)
    intents = [e.intent for e in ctx.extractions]
    if Intent.INVESTOR in intents or (crm and crm.vertical == "investor"):
        return Exclusion("investor", "investor enquiry")
    if Intent.JOB_SEEKER in intents:
        return Exclusion("job_seeker", "job or internship request")
    if intents and all(i == Intent.AUTO_REPLY for i in intents):
        return Exclusion("auto_reply", "every message is an automatic reply")
    return None
