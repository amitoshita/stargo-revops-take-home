"""Record Agent A replies for the seed inbound from the real LLM (docs/ASSUMPTIONS.md D6).

Usage (from backend/):  uv run python -m scripts.record_fixtures [--only IN-001 IN-002] [--force]

- Reads the key from the environment or the repo's .env. Never prints it.
- Messages stopped by layer-1 injection detection are not sent to the LLM and get no fixture.
- Existing fixtures for unchanged messages are kept unless --force is given.
- A failed call (timeout, HTTP error) writes nothing; a reply that fails validation is kept,
  because that is a real model answer and the app must show it as needs review.
- Prints record ids and outcomes only, never message content.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime

from app.agents.agent_a import PROMPT_VERSION, run_agent_a
from app.agents.fixtures import FixtureStore, RecordedReply, message_hash
from app.agents.llm_client import GroqClient
from app.agents.schemas import AnalysisFailure
from app.core.config import load_settings
from app.ingest.loader import load_seed
from app.rules.injection import detect_instruction_attempt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", default=None, help="inbound ids to record")
    parser.add_argument("--force", action="store_true", help="overwrite existing fixtures")
    parser.add_argument("--pause", type=float, default=8.0, help="seconds between calls")
    parser.add_argument("--rate-limit-wait", type=float, default=30.0, help="wait after a 429")
    args = parser.parse_args(argv)

    settings = load_settings()
    if not settings.llm_api_key:
        print("No GROQ_API_KEY found (env or .env). Nothing recorded.")
        return 1
    print(f"Key loaded: yes. Model: {settings.llm_model}. Prompt: {PROMPT_VERSION}.")
    client = GroqClient.from_settings(settings)
    store = FixtureStore(settings.fixtures_dir / "agent_a")
    bundle = load_seed(settings.data_dir)

    for message in bundle.inbound:
        if args.only and message.id not in args.only:
            continue
        if detect_instruction_attempt(message.subject, message.body):
            print(f"{message.id}: skipped (layer-1 injection stop, never sent to the LLM)")
            continue
        if not args.force and store.get(message.id, message.subject, message.body):
            print(f"{message.id}: kept existing fixture")
            continue
        for attempt in range(1, 4):
            result, raw = run_agent_a(
                client,
                ref=message.id,
                subject=message.subject,
                body=message.body,
                channel=message.channel.value,
            )
            limited = isinstance(result, AnalysisFailure) and result.detail == "HTTP 429"
            if not limited or attempt == 3:
                break
            print(f"{message.id}: rate limited, waiting {args.rate_limit_wait:g}s")
            time.sleep(args.rate_limit_wait)
        failure = result if isinstance(result, AnalysisFailure) else None
        if raw is None:  # the call itself failed: write nothing, so a rerun retries it
            print(f"{message.id}: NOT recorded, call failed: {failure.kind if failure else '?'}"
                  f" ({failure.detail if failure else ''})")  # fmt: skip
            time.sleep(args.pause)
            continue
        store.save(
            RecordedReply(
                inbound_id=message.id,
                model=settings.llm_model,
                prompt_version=PROMPT_VERSION,
                recorded_at=datetime.now(UTC),
                message_sha256=message_hash(message.subject, message.body),
                raw=raw,
            )
        )
        outcome = f"{failure.kind} ({failure.detail})" if failure else "ok"
        print(f"{message.id}: recorded, validation {outcome}")
        time.sleep(args.pause)
    return 0


if __name__ == "__main__":
    sys.exit(main())
