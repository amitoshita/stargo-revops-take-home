"""Score recorded Agent A fixtures against the hand labels, then compare downstream results.

Usage (from backend/):  uv run python -m scripts.eval_agent_a [--write ../docs/AGENT_A_EVAL.md]

Offline: reads fixtures only, never calls the LLM.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from app.agents.analyzer import analyze_message
from app.agents.evaluation import evaluate, render_markdown
from app.agents.fixtures import FixtureStore
from app.agents.schemas import MessageAnalysis
from app.core.config import load_settings
from app.core.timeutil import IL_TZ
from app.ingest.loader import SeedBundle, load_seed
from app.kpi.compute import compute_pack
from app.kpi.window import WEEK_UNDER_REVIEW
from app.pipeline import assess_all, build_world
from tests.helpers import labelled_analyses
from tests.seed_labels import LABELS


def _downstream(
    bundle: SeedBundle, analyses: dict[str, MessageAnalysis]
) -> tuple[dict[str, str], str]:
    world = build_world(
        bundle.crm, bundle.inbound, bundle.decisions, analyses,
        [e.contact_email for e in bundle.events],
    )  # fmt: skip
    assessments = assess_all(world)
    statuses = {
        pid: f"{a.status.value} / {a.owner or '—'}" for pid, a in sorted(assessments.items())
    }
    pack = compute_pack(
        world, assessments, bundle.events, bundle.feed_status, WEEK_UNDER_REVIEW,
        datetime.now(IL_TZ),
    )  # fmt: skip
    kpi = " / ".join(str(m.actual) for m in pack.metrics)
    return statuses, kpi


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", type=Path, default=None, help="also write the report here")
    args = parser.parse_args(argv)

    settings = load_settings(read_dotenv=False)
    bundle = load_seed(settings.data_dir)
    store = FixtureStore(settings.fixtures_dir / "agent_a")
    fixture_analyses = {
        m.id: analyze_message(m, client=None, fixtures=store) for m in bundle.inbound
    }
    not_fixture = [
        i for i, a in fixture_analyses.items() if a.mode.value != "recorded fixture"
        and not a.injection_signals
    ]  # fmt: skip

    report = evaluate(LABELS, fixture_analyses)
    label_status, label_kpi = _downstream(bundle, labelled_analyses(bundle))
    fixture_status, fixture_kpi = _downstream(bundle, fixture_analyses)

    lines = ["# Agent A eval: recorded fixtures vs hand labels", ""]
    if not_fixture:
        lines += [f"Warning: no valid fixture for {', '.join(not_fixture)} (fallback used).", ""]
    lines += ["## Per field", "", render_markdown(report), "## Downstream (status / owner)", ""]
    lines += ["| Person | With labels | With fixtures | Same |", "|---|---|---|---|"]
    for pid in sorted(set(label_status) | set(fixture_status)):
        a, b = label_status.get(pid, "—"), fixture_status.get(pid, "—")
        lines.append(f"| {pid} | {a} | {b} | {'✔' if a == b else '✘'} |")
    lines += [
        "",
        "## KPI (QLs / booked / held / opportunities)",
        "",
        f"- With labels: {label_kpi}",
        f"- With fixtures: {fixture_kpi}",
        "",
    ]
    text = "\n".join(lines)
    print(text)
    if args.write:
        args.write.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
