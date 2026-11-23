"""Record Agent A replies for the seed inbound from the real LLM (docs/ASSUMPTIONS.md D6).

Usage (from backend/):  uv run python -m scripts.record_fixtures [--only IN-001 IN-002] [--force]

- Reads the key from the environment or the repo's .env. Never prints it.
- Messages stopped by layer-1 injection detection are not sent to the LLM and get no fixture.
- Existing fixtures for unchanged messages are kept unless --force is given.
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
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between calls")
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
        result, raw = run_agent_a(
            client,
            ref=message.id,
            subject=message.subject,
            body=message.body,
            channel=message.channel.value,
        )
        failure = result if isinstance(result, AnalysisFailure) else None
        store.save(
            RecordedReply(
                inbound_id=message.id,
                model=settings.llm_model,
                prompt_version=PROMPT_VERSION,
                recorded_at=datetime.now(UTC),
                message_sha256=message_hash(message.subject, message.body),
                raw=raw,
                error=failure.kind if failure and raw is None else None,
            )
        )
        outcome = f"{failure.kind} ({failure.detail})" if failure else "ok"
        print(f"{message.id}: recorded, validation {outcome}")
        time.sleep(args.pause)
    return 0


if __name__ == "__main__":
    sys.exit(main())
