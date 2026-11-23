"""Record the LLM content brief for the top GEO gap (labelled "recorded fixture" in the app).

Usage (from backend/):  uv run python -m scripts.record_brief

Reads the key from the environment or the repo's .env and never prints it. Prints the
validator outcome only.
"""

from __future__ import annotations

import sys
import tempfile
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.agents.fixtures import RecordedReply
from app.core.config import load_settings
from app.geo.brief import BRIEF_PROMPT_VERSION, generate_brief, parse_brief
from app.service import Service


def main() -> int:
    settings = load_settings()
    if not settings.llm_api_key:
        print("No GROQ_API_KEY found (env or .env). Nothing recorded.")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        service = Service(replace(settings, db_path=Path(tmp) / "brief.db"))
        assert service.client is not None
        top = service.geo_report().gaps[0]
        print(f"Key loaded: yes. Model: {settings.llm_model}. Top gap: {top.prompt_id}.")
        for attempt in range(1, 4):
            result, raw = generate_brief(service.client, top, service._claims)
            if raw is not None or attempt == 3:
                break
            print(f"Attempt {attempt} failed ({result}); waiting 60s (rate limit).")
            time.sleep(60)
        if raw is None:
            print(f"Not recorded: {result}")
            return 1
        path = service.brief_fixture_path(top.prompt_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        reply = RecordedReply(
            inbound_id=top.prompt_id,
            model=settings.llm_model,
            prompt_version=BRIEF_PROMPT_VERSION,
            recorded_at=datetime.now(UTC),
            message_sha256=service.brief_input_hash(top.prompt_id),
            raw=raw,
        )
        path.write_text(reply.model_dump_json(indent=2) + "\n", encoding="utf-8")
        parsed = parse_brief(raw)
        if isinstance(parsed, str):
            print(f"Recorded, but unusable: {parsed}")
            return 0
        brief = service._assemble(parsed, top.prompt_id, "recorded fixture", settings.llm_model)
        print(f"Recorded {path.name}: publishable={brief.publishable}, flags={len(brief.flags)}")
        for flag in brief.flags:
            print(f"  [{flag.severity}] {flag.location}: {flag.rule}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
