"""Owner routing (QLS §5)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import Region, Status
from app.rules.context import LeadContext
from app.rules.exclusions import Exclusion
from app.rules.ql_gate import region_fact

TRIAGE = "Triage queue"
FOUNDERS = "Founders"

OWNER_BY_REGION: dict[Region, str] = {
    Region.BENELUX: "Dana",
    Region.NORDICS: "Dana",
    Region.UK: "Leo",
    Region.DACH: "Leo",
    Region.SINGAPORE: "Mei",
    Region.APAC_OTHER: "Mei",
    Region.US: "Sam",
    Region.ISRAEL: "Noa",
    Region.OTHER: TRIAGE,
}


@dataclass(frozen=True)
class Route:
    owner: str | None
    basis: str


def region_route(ctx: LeadContext) -> Route:
    region = region_fact(ctx)
    if region is None:
        return Route(TRIAGE, "region unknown")
    owner = OWNER_BY_REGION[region.value]
    return Route(owner, f"region {region.value.value} ({region.label()})")


def account_route(ctx: LeadContext) -> Route | None:
    crm = ctx.crm
    if crm and (crm.is_customer or crm.open_deal_id) and crm.owner:
        kind = "customer" if crm.is_customer else f"deal {crm.open_deal_id}"
        return Route(crm.owner, f"CRM owner ({kind})")
    return None


def route(ctx: LeadContext, status: Status, exclusion: Exclusion | None) -> Route:
    if status in (Status.DISQUALIFIED, Status.SUPPRESSED):
        return Route(None, f"{status.value}: no owner")
    if status == Status.EXCLUDED:
        if exclusion and exclusion.kind in ("customer", "open_deal"):
            return account_route(ctx) or Route(TRIAGE, "account owner missing in CRM")
        if exclusion and exclusion.kind == "investor":
            return Route(FOUNDERS, "investor enquiry")
        return Route(None, "excluded: no owner")
    # QL, QL candidate, nurture, needs review: the account owner if any, else the region.
    return account_route(ctx) or region_route(ctx)
