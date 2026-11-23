"""Held-out eval: frozen Agent A prompt on tests/heldout_messages.md, through the full pipeline.

Usage (from backend/):
  uv run python -m scripts.eval_heldout --record   # one live LLM call per message, saved
  uv run python -m scripts.eval_heldout --write ../docs/AGENT_A_EVAL.md   # offline

The prompt must not be tuned on these messages. Recordings carry the prompt version, so a
later prompt change shows up as a mismatch instead of silently reusing old answers.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app.agents.agent_a import PROMPT_VERSION, parse_output, run_agent_a
from app.agents.fixtures import FixtureStore, RecordedReply, message_hash
from app.agents.heldout import HeldoutCase, parse_heldout
from app.agents.llm_client import GroqClient
from app.agents.schemas import AgentAOutput, AnalysisFailure, MessageAnalysis
from app.core.config import REPO_ROOT, load_settings
from app.core.enums import AnalysisMode
from app.ingest.loader import load_seed
from app.ingest.schemas import InboundMessage
from app.pipeline import assess_all, build_world
from app.rules.injection import detect_instruction_attempt

HELDOUT = REPO_ROOT / "backend" / "tests" / "heldout_messages.md"
MARKER = "## Held-out set"
FINDINGS = "## Findings"

# Expected-label errors, confirmed by Amit after the run. The held-out file is not edited;
# these are applied only to the second score so both are visible. (case, field) ->
# (corrected expectation, reason).
_DOMAIN = (
    "routed from the email's country domain; D-add / QLS §3: region only from a stated country"
)
_NAME = "vertical assumed from the company name; QLS §3: vertical stays unknown unless stated"
LABEL_ERRORS: dict[tuple[str, str], tuple[str, str]] = {
    ("H1", "owner"): ("Triage queue", _DOMAIN),
    ("H1", "status"): ("nurture", f"{_DOMAIN}; {_NAME}"),
    ("H3", "owner"): ("Triage queue", _DOMAIN),
    ("H3", "status"): ("nurture", f"{_DOMAIN}; {_NAME}"),
    ("H6", "owner"): ("Triage queue", _DOMAIN),
}


def _record(cases: list[HeldoutCase], store: FixtureStore, pause: float) -> None:
    settings = load_settings()
    if not settings.llm_api_key:
        raise SystemExit("No GROQ_API_KEY found (env or .env). Nothing recorded.")
    print(f"Key loaded: yes. Model: {settings.llm_model}. Prompt: {PROMPT_VERSION}.")
    client = GroqClient.from_settings(settings)
    for case in cases:
        for message in case.inbound():
            if detect_instruction_attempt(message.subject, message.body):
                print(f"{message.id}: layer-1 injection stop, not sent")
                continue
            for attempt in range(1, 4):
                result, raw = run_agent_a(
                    client, ref=message.id, subject=None, body=message.body,
                    channel=message.channel.value,
                )  # fmt: skip
                limited = isinstance(result, AnalysisFailure) and result.detail == "HTTP 429"
                if not limited or attempt == 3:
                    break
                time.sleep(30)
            if raw is None:
                print(f"{message.id}: NOT recorded (call failed)")
                continue
            store.save(
                RecordedReply(
                    inbound_id=message.id,
                    model=settings.llm_model,
                    prompt_version=PROMPT_VERSION,
                    recorded_at=datetime.now(UTC),
                    message_sha256=message_hash(None, message.body),
                    raw=raw,
                )
            )
            outcome = result.kind if isinstance(result, AnalysisFailure) else "ok"
            print(f"{message.id}: recorded, validation {outcome}")
            time.sleep(pause)


def _analyse(message: InboundMessage, store: FixtureStore) -> MessageAnalysis:
    signals = detect_instruction_attempt(message.subject, message.body)
    if signals:
        return MessageAnalysis(
            inbound_id=message.id, mode=AnalysisMode.LLM, extraction=None, failure=None,
            injection_signals=signals,
        )  # fmt: skip
    recorded = store.get(message.id, None, message.body)
    outcome: AgentAOutput | AnalysisFailure
    if recorded is None or recorded.raw is None:
        outcome = AnalysisFailure(kind="model_error", detail="no recording")
    elif recorded.prompt_version != PROMPT_VERSION:
        outcome = AnalysisFailure(kind="model_error", detail="recorded with another prompt")
    else:
        outcome = parse_output(recorded.raw, None, message.body)
    return MessageAnalysis(
        inbound_id=message.id,
        mode=AnalysisMode.RECORDED_FIXTURE,
        extraction=outcome if isinstance(outcome, AgentAOutput) else None,
        failure=outcome if isinstance(outcome, AnalysisFailure) else None,
    )


def evaluate(cases: list[HeldoutCase], store: FixtureStore) -> str:
    settings = load_settings(read_dotenv=False)
    bundle = load_seed(settings.data_dir)
    inbound = [m for case in cases for m in case.inbound()]
    analyses = {m.id: _analyse(m, store) for m in inbound}
    world = build_world(bundle.crm, inbound, [], analyses)
    assessments = assess_all(world)

    rows: list[str] = []
    agree = total = corrected_agree = 0
    for case in cases:
        messages = case.inbound()
        person = world.identity.person_for_email(messages[0].email or "")
        assessment = assessments.get(person.person_id) if person else None
        latest = next(
            (analyses[m.id].extraction for m in reversed(messages) if analyses[m.id].extraction),
            None,
        )
        got: dict[str, str] = {
            "status": assessment.status.value if assessment else "—",
            "owner": (assessment.owner or "—") if assessment else "—",
        }
        if latest is not None:
            got |= {
                "intent": latest.intent.value,
                "intent (latest)": latest.intent.value,
                "problem": latest.problem_category.value,
                "buyer_role": latest.buyer_role or "—",
                "language": latest.language,
            }
        failures = [a.failure.kind for m in messages if (a := analyses[m.id]).failure]
        for key, expected in case.expected.items():
            value = got.get(key, "—")
            same = value.casefold() == expected.casefold()
            fix = LABEL_ERRORS.get((case.case_id, key))
            corrected = fix[0] if fix else expected
            agree += same
            corrected_agree += value.casefold() == corrected.casefold()
            total += 1
            note = f"label error → {corrected}" if fix else ""
            rows.append(
                f"| {case.case_id} | {key} | {expected} | {value} | {'✔' if same else '✘'} "
                f"| {note} |"
            )
        if failures:
            rows.append(f"| {case.case_id} | analysis | — | failed: {', '.join(failures)} | | |")
        if assessment is not None:
            rows.append(f"| {case.case_id} | rationale | | {assessment.rationale} | | |")

    lines = [
        MARKER,
        "",
        f"Prompt `{PROMPT_VERSION}` frozen before this run. {len(cases)} cases, "
        f"{len(inbound)} messages, through the full pipeline (identity → rules → routing).",
        "",
        f"- Agreement as recorded (expected labels unchanged): **{agree}/{total}**.",
        f"- Agreement with the expected-label errors corrected: **{corrected_agree}/{total}**.",
        "",
        "| Case | Field | Expected | Got | Same | Note |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        "### Expected-label errors",
        "",
        "The held-out file is unchanged. These expected values contradict decided rules, so the",
        "second score uses the corrected value; the first score keeps the original label.",
        "",
        *(f"- {c} {f}: expected '{next(x.expected[f] for x in cases if x.case_id == c)}', "
          f"corrected '{v}'. Reason: {r}." for (c, f), (v, r) in LABEL_ERRORS.items()),
        "",
    ]  # fmt: skip
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="call the LLM and save replies")
    parser.add_argument("--pause", type=float, default=8.0)
    parser.add_argument("--write", type=Path, default=None, help="replace the held-out section")
    args = parser.parse_args(argv)

    settings = load_settings(read_dotenv=False)
    store = FixtureStore(settings.fixtures_dir / "heldout")
    cases = parse_heldout(HELDOUT)
    if args.record:
        _record(cases, store, args.pause)
    text = evaluate(cases, store)
    print(text)
    if args.write:
        current = args.write.read_text(encoding="utf-8") if args.write.exists() else ""
        head = current.split(MARKER)[0].rstrip()
        tail = FINDINGS + current.split(FINDINGS, 1)[1] if FINDINGS in current else ""
        parts = [p for p in (head, text.rstrip(), tail.rstrip()) if p]
        args.write.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
