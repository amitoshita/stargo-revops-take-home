"""GEO (AI visibility) records: answers, findings, gaps, risks, content brief, validator flags."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AnswerState = Literal["owned", "mentioned_unowned", "absent", "wrong"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AiAnswer(_Strict):
    answer_id: str
    prompt_id: str
    prompt: str
    cluster: str
    priority: int = Field(ge=0)
    engine: str
    captured_at: datetime
    answer_text: str
    citations: list[str]


class WrongClaim(_Strict):
    text: str  # the sentence from the engine's answer
    contradicts: str  # BC id, e.g. "BC-5"
    rule: str  # which part of the rule, e.g. "not a carrier"


class Finding(_Strict):
    answer_id: str
    prompt_id: str
    prompt: str
    engine: str
    priority: int
    cluster: str
    stargo_mentioned: bool
    owned_citation: bool
    owned_urls: list[str]
    lookalike_domains: list[str]  # cited hosts that imitate the brand (not owned)
    competitors: list[str]  # canonical names
    wrong_claims: list[WrongClaim]
    state: AnswerState


class GapScore(_Strict):
    prompt_id: str
    prompt: str
    cluster: str
    priority: int
    per_engine: dict[str, AnswerState]
    state_sum: float
    fit: int  # 1 if a BC-3 product answers the need, else 0
    fit_basis: str
    competitors: list[str]
    score: float
    rank: int
    explanation: str


class RiskItem(_Strict):
    answer_id: str
    prompt_id: str
    engine: str
    kind: Literal["wrong_claim", "lookalike_citation"]
    detail: str


class Claimed(_Strict):
    text: str = Field(min_length=1, max_length=600)
    refs: list[str] = Field(default_factory=list)  # BC / PP ids


class BriefSection(_Strict):
    heading: str = Field(min_length=1, max_length=120)
    paragraphs: list[Claimed] = Field(min_length=1, max_length=6)


class FaqItem(_Strict):
    question: str = Field(min_length=1, max_length=200)
    answer: list[Claimed] = Field(min_length=1, max_length=4)


class ContentBriefDraft(_Strict):
    """What the generator (LLM or template) must return."""

    title: str = Field(min_length=1, max_length=160)
    direct_answer: Claimed
    sections: list[BriefSection] = Field(min_length=1, max_length=8)
    faq: list[FaqItem] = Field(min_length=1, max_length=8)
    schema_org_type: str = Field(min_length=1, max_length=40)


class ValidatorFlag(_Strict):
    location: str  # e.g. "sections[1].paragraphs[0]"
    rule: str  # e.g. "BC-5 competitor statement"
    severity: Literal["block", "warn"]
    text: str  # the offending text (engine/brief text, never lead data)


class ContentBrief(_Strict):
    prompt_id: str
    draft: ContentBriefDraft
    mode: Literal["llm", "recorded fixture", "template"]
    model: str | None
    flags: list[ValidatorFlag]
    publishable: bool
    generated_at: datetime


class GeoReport(_Strict):
    findings: list[Finding]
    gaps: list[GapScore]
    risks: list[RiskItem]
    formula: str
