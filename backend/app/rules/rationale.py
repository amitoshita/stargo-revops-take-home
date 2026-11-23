"""One-line rationale built from evidence only (a template, never an LLM)."""

from __future__ import annotations

from app.core.enums import Status
from app.rules.schemas import QLChecklist

MAX_LEN = 400


def _clip(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_rationale(status: Status, reason: str, checklist: QLChecklist | None) -> str:
    if checklist is None:
        return _clip(f"{status.value}: {reason}", MAX_LEN)
    conds = checklist.first_four()
    if status in (Status.DISQUALIFIED, Status.NURTURE) and checklist.failing:
        evidence_from = [conds[name] for name in checklist.failing]
    else:
        evidence_from = [c for c in (conds["C3"], conds["C4"]) if c.status == "pass"]
    evidence = next((c.evidence[0] for c in evidence_from if c.evidence), None)
    if status == Status.QL:
        line = "QL: all five conditions pass"
    elif status == Status.QL_CANDIDATE:
        gaps = checklist.unknown
        line = (
            "QL candidate: C1–C4 pass, awaiting sales acceptance"
            if not gaps
            else (f"QL candidate: accepted, but {', '.join(gaps)} unknown")
        )
    elif status == Status.DISQUALIFIED:
        failing = checklist.failing or ["C5"]
        details = "; ".join(
            f"{name} {(conds.get(name) or checklist.c5_sales_acceptance).reason}"
            for name in failing
        )
        line = f"Disqualified: {details}"
    elif status == Status.NURTURE:
        parts = [f"{name} {conds[name].reason}" for name in checklist.failing]
        if checklist.unknown:
            parts.append(f"{', '.join(checklist.unknown)} unknown")
        line = "Nurture: " + "; ".join(parts)
    else:
        line = f"{status.value}: {reason}"
    if evidence:
        line += f". Evidence: {_clip(evidence)}"
    return _clip(line, MAX_LEN)
