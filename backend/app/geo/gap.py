"""Ranked gap list (plan §6) and a separate brand-risk table.

gap(prompt) = priority × Σ_engines g(state) × fit
  g: owned 0 · mentioned without an owned citation 0.5 · absent 1 · wrong claim 1.5
  fit: 1 if a BC-3 product answers the prompt's need, else 0 (a gap we cannot fill with
  approved claims is not a content gap).
Ties: more distinct competitors first, then prompt id.

Why: priority is the business weight the team already set; summing over engines rewards
breadth; a wrong claim is worse than silence because it mis-sells; an unowned mention is
half a win because we do not control the source; fit stops the brief inventing a product.
"""

from __future__ import annotations

from collections import defaultdict

from app.geo.schemas import AnswerState, Finding, GapScore, RiskItem

FORMULA = (
    "gap = priority × Σ over engines of g(state) × fit; g: owned 0, mentioned without owned "
    "citation 0.5, absent 1, wrong claim 1.5; fit = 1 if a BC-3 product answers the need, "
    "else 0; ties broken by number of competitors present"
)
G: dict[AnswerState, float] = {"owned": 0.0, "mentioned_unowned": 0.5, "absent": 1.0, "wrong": 1.5}

# Cluster → the approved product that answers it (brand_context.md BC-3). None = no product.
FIT: dict[str, str | None] = {
    "rate-quoting": "BC-3a Rate Quoting Agent",
    "competitive": "BC-3a Rate Quoting Agent (freight pricing)",
    "document-extraction": "BC-3b Document Extraction",
    "air-cargo": "BC-3b Document Extraction (air waybills), PP-3",
    "invoice-audit": "BC-3c Invoice and Contract Reconciliation",
    "trade-finance": "BC-3d Trade Document Checking",
    "brand": "BC-1 Positioning",
    "shipper": None,  # rate benchmarking: no BC-3 product
}


def rank_gaps(findings: list[Finding]) -> list[GapScore]:
    by_prompt: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_prompt[finding.prompt_id].append(finding)
    unranked: list[GapScore] = []
    for prompt_id, group in by_prompt.items():
        first = group[0]
        product = FIT.get(first.cluster)
        fit = 1 if product else 0
        basis = product or "no BC-3 product for this need"
        state_sum = sum(G[f.state] for f in group)
        score = first.priority * state_sum * fit
        per_engine = {f.engine: f.state for f in sorted(group, key=lambda f: f.engine)}
        states = ", ".join(f"{e} {s.replace('_', ' ')}" for e, s in per_engine.items())
        unranked.append(
            GapScore(
                prompt_id=prompt_id,
                prompt=first.prompt,
                cluster=first.cluster,
                priority=first.priority,
                per_engine=per_engine,
                state_sum=state_sum,
                fit=fit,
                fit_basis=basis,
                competitors=sorted({c for f in group for c in f.competitors}),
                score=score,
                rank=0,
                explanation=(
                    f"priority {first.priority} × Σg {state_sum:g} ({states}) × fit {fit} "
                    f"({basis}) = {score:g}"
                ),
            )
        )
    unranked.sort(key=lambda g: (-g.score, -len(g.competitors), g.prompt_id))
    return [g.model_copy(update={"rank": i}) for i, g in enumerate(unranked, start=1)]


def risk_table(findings: list[Finding]) -> list[RiskItem]:
    """Brand-accuracy risks, kept apart so a low-priority prompt cannot bury them."""
    risks: list[RiskItem] = []
    for f in sorted(findings, key=lambda f: f.answer_id):
        for claim in f.wrong_claims:
            risks.append(RiskItem(
                answer_id=f.answer_id, prompt_id=f.prompt_id, engine=f.engine,
                kind="wrong_claim", detail=f"{claim.contradicts} ({claim.rule}): {claim.text}",
            ))  # fmt: skip
        for domain in f.lookalike_domains:
            risks.append(RiskItem(
                answer_id=f.answer_id, prompt_id=f.prompt_id, engine=f.engine,
                kind="lookalike_citation", detail=f"cites look-alike domain {domain}",
            ))  # fmt: skip
    return risks
