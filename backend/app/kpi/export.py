"""KPI_PACK.md export. A hand-written CRO note at the end of an existing file is preserved."""

from __future__ import annotations

from pathlib import Path

from app.core.timeutil import to_il
from app.kpi.schemas import KpiPack, RecordRef

CRO_HEADING = "## Note to the CRO"
CRO_PLACEHOLDER = "_To be written by hand (150 words or fewer)._"


def _refs(refs: list[RecordRef]) -> str:
    if not refs:
        return "—"
    return "; ".join(f"{r.record_id} {r.name or r.person_id}" for r in refs)


def _week_label(pack: KpiPack) -> str:
    return f"Sun {pack.week_start:%-d %b} – Thu {pack.week_end:%-d %b %Y} ({pack.timezone})"


def render(pack: KpiPack, cro_note: str | None = None) -> str:
    lines = [
        "# Weekly KPI pack",
        "",
        f"**Week:** {_week_label(pack)}  ",
        f"**Generated:** {to_il(pack.generated_at):%Y-%m-%d %H:%M} IL  ",
        f"**Analysis mode:** {', '.join(m.value for m in pack.analysis_modes) or 'n/a'}",
        "",
        "## Acquisition vs target",
        "",
        "| KPI | Actual | Target | Gap | Records |",
        "|---|---:|---:|---:|---|",
    ]
    for m in pack.metrics:
        lines.append(f"| {m.label} | {m.actual} | {m.target} | {m.gap:+d} | {_refs(m.records)} |")

    lines += [
        "",
        "## QLs by first-touch source",
        "",
        "| Source | QLs | Records |",
        "|---|---:|---|",
    ]
    for row in pack.by_source:
        count = "unknown" if row.count is None else str(row.count)
        if row.note and row.count is not None:
            count += f" ({row.note})"
        lines.append(f"| {row.source} | {count} | {_refs(row.records)} |")

    exp = pack.expansion
    lines += [
        "",
        "## Expansion (existing customers, reported separately)",
        "",
        "| Activity | Count | Records |",
        "|---|---:|---|",
        f"| Accepted | {len(exp.accepted)} | {_refs(exp.accepted)} |",
        f"| Meetings booked | {len(exp.meetings_booked)} | {_refs(exp.meetings_booked)} |",
        f"| Meetings held | {len(exp.meetings_held)} | {_refs(exp.meetings_held)} |",
        f"| Opportunities | {len(exp.opportunities)} | {_refs(exp.opportunities)} |",
        "",
        "## Not counted this week",
        "",
        "| Record | Person | Why |",
        "|---|---|---|",
    ]
    for ex in pack.excluded:
        lines.append(f"| {ex.record_id} | {ex.name or '—'} | {ex.reason.replace('|', '/')} |")

    lines += ["", "## Caveats", ""]
    lines += [f"- {c}" for c in pack.caveats] or ["- None."]
    lines += ["", CRO_HEADING, "", (cro_note or CRO_PLACEHOLDER).strip(), ""]
    return "\n".join(lines)


def existing_cro_note(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if CRO_HEADING not in text:
        return None
    note = text.split(CRO_HEADING, 1)[1].strip()
    return None if not note or note == CRO_PLACEHOLDER else note


def export(pack: KpiPack, path: Path) -> str:
    content = render(pack, existing_cro_note(path))
    path.write_text(content, encoding="utf-8")
    return content
