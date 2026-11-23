"""Assemble per-person lead contexts from stored records and run the rules over them.

Pure functions over records: no I/O, no LLM. The API and the agent runner call these.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.agents.schemas import AnalysisFailure, MessageAnalysis
from app.core.enums import AnalysisMode
from app.ingest.identity import IdentityIndex, Person, build_company_index, build_identity
from app.ingest.normalize import email_domain, is_free_email_domain
from app.ingest.schemas import CompanyRecord, CrmContact, InboundMessage, SalesDecision
from app.rules.context import LeadContext, sort_decisions
from app.rules.schemas import Assessment
from app.rules.status import assess


@dataclass(frozen=True)
class World:
    identity: IdentityIndex
    companies: dict[str, CompanyRecord]
    decisions_by_person: dict[str, list[SalesDecision]]
    leads: dict[str, LeadContext]  # only people with at least one inbound


def _company_for(person: Person, companies: Mapping[str, CompanyRecord]) -> CompanyRecord | None:
    if person.crm and person.crm.company_domain:
        return companies.get(person.crm.company_domain)
    for email in sorted(person.emails):
        domain = email_domain(email)
        if domain and not is_free_email_domain(domain):
            return companies.get(domain)
    return None


def _free_email(person: Person) -> bool:
    domains = [email_domain(e) for e in person.emails]
    return bool(domains) and all(is_free_email_domain(d) for d in domains)


def _not_analysed(inbound_id: str) -> MessageAnalysis:
    """A stored message without an analysis must never be judged on the others: needs review."""
    return MessageAnalysis(
        inbound_id=inbound_id,
        mode=AnalysisMode.RULES_ONLY,
        extraction=None,
        failure=AnalysisFailure(kind="not_analysed", detail="no analysis stored for this message"),
    )


def build_world(
    crm: Iterable[CrmContact],
    inbound: Iterable[InboundMessage],
    decisions: Iterable[SalesDecision],
    analyses: Mapping[str, MessageAnalysis],
    event_emails: Iterable[str] = (),
) -> World:
    crm_list, inbound_list, decision_list = list(crm), list(inbound), list(decisions)
    identity = build_identity(
        crm_list, inbound_list, [d.contact_email for d in decision_list] + list(event_emails)
    )
    companies = build_company_index(crm_list)

    by_person: dict[str, list[SalesDecision]] = {}
    for decision in decision_list:
        person = identity.person_for_email(decision.contact_email)
        if person is not None:
            by_person.setdefault(person.person_id, []).append(decision)
    by_person = {pid: sort_decisions(ds) for pid, ds in by_person.items()}

    leads: dict[str, LeadContext] = {}
    for pid, person in identity.persons.items():
        if not person.inbound:
            continue
        leads[pid] = LeadContext(
            person_id=pid,
            crm=person.crm,
            company=_company_for(person, companies),
            free_email=_free_email(person),
            inbound=list(person.inbound),
            analyses=[analyses.get(m.id) or _not_analysed(m.id) for m in person.inbound],
            decisions=by_person.get(pid, []),
        )
    return World(identity, companies, by_person, leads)


def assess_all(world: World) -> dict[str, Assessment]:
    return {pid: assess(ctx) for pid, ctx in world.leads.items()}
