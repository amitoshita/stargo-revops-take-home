"""Build the GEO report from ai_answers.json and render its markdown summary."""

from __future__ import annotations

import json
from pathlib import Path

from app.geo.analyze import analyse_answer
from app.geo.gap import FORMULA, rank_gaps, risk_table
from app.geo.schemas import AiAnswer, ContentBrief, GeoReport

ENGINES = ("ChatGPT", "Perplexity", "Gemini")


def competitors(path: Path) -> list[str]:
    meta = json.loads(path.read_text(encoding="utf-8"))["meta"]
    return [str(c) for c in meta.get("known_competitors", [])]


def build_report(path: Path) -> GeoReport:
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data["meta"]
    findings = [
        analyse_answer(
            AiAnswer.model_validate(raw),
            meta["brand"],
            list(meta["own_domains"]),
            list(meta["known_competitors"]),
        )
        for raw in data["answers"]
    ]
    return GeoReport(
        findings=findings, gaps=rank_gaps(findings), risks=risk_table(findings), formula=FORMULA
    )


def render_markdown(report: GeoReport, brief: ContentBrief | None, top: int = 3) -> str:
    lines = [
        "## AI visibility (GEO)",
        "",
        f"Gap formula: {report.formula}.",
        "",
        "| Rank | Prompt | Score | ChatGPT | Perplexity | Gemini |",
        "|---:|---|---:|---|---|---|",
    ]
    for gap in report.gaps[:top]:
        cells = " | ".join(gap.per_engine.get(e, "—").replace("_", " ") for e in ENGINES)
        lines.append(f"| {gap.rank} | {gap.prompt_id} {gap.prompt} | {gap.score:g} | {cells} |")
    if report.risks:
        lines += ["", "Brand-accuracy risks:", ""]
        lines += [f"- {r.answer_id}: {r.detail}" for r in report.risks]
    if brief is not None:
        state = "publishable" if brief.publishable else "blocked by the claim validator"
        lines += [
            "",
            f"Content brief for the top gap ({brief.prompt_id}): '{brief.draft.title}' "
            f"({brief.mode}, {state}, {len(brief.flags)} flag(s)).",
        ]
    return "\n".join(lines)
