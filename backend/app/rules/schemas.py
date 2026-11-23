"""Outputs of the deterministic rules layer: QL checklist, score, assessment."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.core.enums import Status

Tri = Literal["pass", "fail", "unknown"]
FactSource = Literal["crm", "crm_company_record", "message", "sales_decision", "none"]
Band = Literal["A", "B", "nurture"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class QLCondition(_Frozen):
    status: Tri
    reason: str
    evidence: list[str] = Field(default_factory=list)
    source: FactSource = "none"
    verified: bool = False
    failed_on: list[str] = Field(default_factory=list)  # e.g. ["region"], ["vertical", "size"]


class QLChecklist(_Frozen):
    c1_company_fit: QLCondition
    c2_relevant_buyer: QLCondition
    c3_data_problem: QLCondition
    c4_expressed_interest: QLCondition
    c5_sales_acceptance: QLCondition

    def first_four(self) -> dict[str, QLCondition]:
        return {
            "C1": self.c1_company_fit,
            "C2": self.c2_relevant_buyer,
            "C3": self.c3_data_problem,
            "C4": self.c4_expressed_interest,
        }

    @property
    def c1_to_c4_pass(self) -> bool:
        return all(c.status == "pass" for c in self.first_four().values())

    @property
    def all_pass(self) -> bool:
        return self.c1_to_c4_pass and self.c5_sales_acceptance.status == "pass"

    @property
    def failing(self) -> list[str]:
        return [name for name, c in self.first_four().items() if c.status == "fail"]

    @property
    def c1_fails_only_on_region(self) -> bool:
        c1 = self.c1_company_fit
        return c1.status == "fail" and c1.failed_on == ["region"]

    @property
    def unknown(self) -> list[str]:
        return [name for name, c in self.first_four().items() if c.status == "unknown"]


class ScoreFactor(_Frozen):
    name: str
    points: int
    max: int
    basis: str
    unknown: bool = False


class AcceptedBy(_Frozen):
    decision_id: str
    decided_by: str
    decided_at: AwareDatetime


class Assessment(_Frozen):
    status: Status
    reason: str  # short machine-friendly reason code, e.g. "excluded:customer"
    checklist: QLChecklist | None  # None when the analysis failed or the lead was excluded early
    owner: str | None
    owner_basis: str
    score: int | None = Field(default=None, ge=0, le=100)
    band: Band | None = None
    breakdown: list[ScoreFactor] = Field(default_factory=list)
    rationale: str = Field(max_length=400)
    accepted_by: AcceptedBy | None = None
    expansion: bool = False
    assessed_at: datetime | None = None
