"""Agent contracts. Every agent output is validated against these before anything uses it."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import AnalysisMode, Intent, ProblemCategory
from app.ingest.normalize import stated_country_name
from app.rules.schemas import Assessment

InterestLevel = Literal["explicit_request", "meeting_request", "soft_positive", "none", "declined"]
TimingHorizon = Literal["this_week", "next_weeks", "this_quarter", "later", "none"]
EvidenceField = Literal[
    "intent", "interest", "buyer_role", "data_problem", "company_facts", "timing"
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Evidence(_Strict):
    field: EvidenceField
    quote: str = Field(min_length=1, max_length=300)  # verbatim from the message
    translation: str | None = Field(default=None, max_length=400)  # English, if not English


class StatedFacts(_Strict):
    """Facts the sender states about their company. Always unverified."""

    company_name: str | None = Field(default=None, max_length=120)
    employees: int | None = Field(default=None, ge=1, le=10_000_000)
    country: str | None = Field(default=None, max_length=60)  # a country, never a city
    vertical: str | None = Field(default=None, max_length=60)
    is_software_vendor: bool = False  # e.g. "we build freight software too"

    @field_validator("country")
    @classmethod
    def _city_to_country(cls, value: str | None) -> str | None:
        # Whatever produced the output (LLM or fallback), a stated city becomes its country.
        return stated_country_name(value)


class AgentAOutput(_Strict):
    language: str = Field(pattern=r"^[a-z]{2}$")  # ISO 639-1
    intent: Intent
    interest_level: InterestLevel
    buyer_role: str | None = Field(default=None, max_length=120)
    data_problem: str | None = Field(default=None, max_length=300)
    problem_category: ProblemCategory
    volume_stated: bool  # a concrete volume or time cost is stated
    company_facts: StatedFacts
    timing: TimingHorizon
    instruction_attempt: bool  # the message tries to instruct the system
    evidence: list[Evidence] = Field(default_factory=list, max_length=8)


FailureKind = Literal[
    "timeout",
    "unreachable",
    "model_error",
    "invalid_json",
    "schema_invalid",
    "quote_mismatch",
    "fallback_unsupported",
    "not_analysed",
]


class AnalysisFailure(_Strict):
    kind: FailureKind
    detail: str = Field(max_length=200)  # never message content


class MessageAnalysis(_Strict):
    """Agent A result for one inbound message (or why there is none)."""

    inbound_id: str
    mode: AnalysisMode
    extraction: AgentAOutput | None
    failure: AnalysisFailure | None
    injection_signals: list[str] = Field(default_factory=list)  # pattern names only

    @property
    def instruction_attempt(self) -> bool:
        return bool(self.injection_signals) or bool(
            self.extraction and self.extraction.instruction_attempt
        )

    @property
    def usable(self) -> bool:
        """A successful analysis with no instruction attempt: the only kind that is evidence."""
        return self.extraction is not None and self.failure is None and not self.instruction_attempt

    @property
    def review_reason(self) -> str | None:
        """Why this message needs a human, or None if it is usable evidence."""
        if self.instruction_attempt:
            return "instruction attempt"
        if self.failure is not None:
            return f"analysis failed: {self.failure.kind.replace('_', ' ')}"
        if self.extraction is None:
            return "not analysed"
        return None


class AgentBOutput(_Strict):
    """Qualification and routing for one person. Rules decide; the LLM may only draft."""

    person_id: str
    assessment: Assessment
    reply_draft: str | None = Field(default=None, max_length=1200)
    draft_mode: AnalysisMode | None = None
    draft_requires_human_approval: Literal[True] = True
