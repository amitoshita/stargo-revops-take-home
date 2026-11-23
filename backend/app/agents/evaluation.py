"""Compare Agent A outputs against hand labels, field by field (the labelled eval set)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from app.agents.schemas import AgentAOutput, MessageAnalysis
from app.ingest.normalize import normalize_country, normalize_vertical

Getter = Callable[[AgentAOutput], object]


def _evidence_fields(output: AgentAOutput) -> object:
    return frozenset(e.field for e in output.evidence) & {"interest", "data_problem"}


FIELDS: dict[str, Getter] = {
    "language": lambda o: o.language,
    "intent": lambda o: o.intent.value,
    "interest_level": lambda o: o.interest_level,
    "problem_category": lambda o: o.problem_category.value,
    "volume_stated": lambda o: o.volume_stated,
    "timing": lambda o: o.timing,
    "instruction_attempt": lambda o: o.instruction_attempt,
    "buyer_role (stated?)": lambda o: o.buyer_role is not None,
    "data_problem (stated?)": lambda o: o.data_problem is not None,
    "facts.country": lambda o: normalize_country(o.company_facts.country),
    "facts.employees": lambda o: o.company_facts.employees,
    "facts.vertical": lambda o: normalize_vertical(o.company_facts.vertical),
    "facts.is_software_vendor": lambda o: o.company_facts.is_software_vendor,
    "evidence for interest/problem": _evidence_fields,
}


@dataclass
class FieldScore:
    name: str
    agree: int = 0
    total: int = 0
    misses: list[str] = field(default_factory=list)  # "IN-009: label=… got=…"


@dataclass
class EvalReport:
    fields: list[FieldScore]
    failures: dict[str, str]  # inbound_id -> failure kind (no extraction to compare)
    compared: int


def _show(value: object) -> str:
    if isinstance(value, frozenset):
        return "{" + ", ".join(sorted(str(v) for v in value)) + "}"
    return repr(value)


def evaluate(
    labels: Mapping[str, AgentAOutput], analyses: Mapping[str, MessageAnalysis]
) -> EvalReport:
    scores = {name: FieldScore(name) for name in FIELDS}
    failures: dict[str, str] = {}
    compared = 0
    for inbound_id, label in sorted(labels.items()):
        analysis = analyses.get(inbound_id)
        if analysis is None or analysis.extraction is None:
            kind = "missing"
            if analysis is not None and analysis.failure is not None:
                kind = analysis.failure.kind
            elif analysis is not None and analysis.injection_signals:
                kind = "injection stop"
            failures[inbound_id] = kind
            continue
        compared += 1
        for name, get in FIELDS.items():
            expected, got = get(label), get(analysis.extraction)
            score = scores[name]
            score.total += 1
            if expected == got:
                score.agree += 1
            else:
                score.misses.append(f"{inbound_id}: label={_show(expected)} got={_show(got)}")
    return EvalReport(fields=list(scores.values()), failures=failures, compared=compared)


def render_markdown(report: EvalReport) -> str:
    lines = [
        f"Compared {report.compared} messages with an extraction.",
        "",
        "| Field | Agree | Disagreements |",
        "|---|---|---|",
    ]
    for score in report.fields:
        misses = "; ".join(score.misses) or "—"
        lines.append(f"| {score.name} | {score.agree}/{score.total} | {misses} |")
    if report.failures:
        lines += ["", "No extraction (counted as needs review):", ""]
        lines += [f"- {k}: {v}" for k, v in sorted(report.failures.items())]
    return "\n".join(lines) + "\n"
