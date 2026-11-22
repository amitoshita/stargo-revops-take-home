"""Everything the rules know about one person. Built from stored records, never from prompts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.agents.schemas import AgentAOutput, MessageAnalysis
from app.core.timeutil import to_il
from app.ingest.schemas import CompanyRecord, CrmContact, InboundMessage, SalesDecision


@dataclass(frozen=True)
class LeadContext:
    person_id: str
    crm: CrmContact | None
    company: CompanyRecord | None  # CRM company record for the person's domain, if any
    free_email: bool  # the sender writes from a free email domain
    inbound: list[InboundMessage]  # oldest first
    analyses: list[MessageAnalysis]  # same order as inbound
    decisions: list[SalesDecision]  # oldest first by decided_at

    @property
    def extractions(self) -> list[AgentAOutput]:
        return [a.extraction for a in self.analyses if a.extraction is not None]

    @property
    def latest_decision(self) -> SalesDecision | None:
        return self.decisions[-1] if self.decisions else None

    @property
    def first_inbound_date(self) -> date | None:
        return to_il(self.inbound[0].received_at).date() if self.inbound else None

    @property
    def first_acceptance_at(self) -> datetime | None:
        accepted = [d.decided_at for d in self.decisions if d.decision == "accepted"]
        return min(accepted) if accepted else None


def sort_decisions(decisions: list[SalesDecision]) -> list[SalesDecision]:
    """Oldest first by decided_at; stable for identical timestamps (creation order kept)."""
    return sorted(decisions, key=lambda d: d.decided_at)
