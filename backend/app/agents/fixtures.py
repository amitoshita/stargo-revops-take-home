"""Recorded Agent A replies for the seed inbound (docs/ASSUMPTIONS.md D6).

Each file holds the raw model text captured once from the real LLM, plus the model, prompt
version and a hash of the message it answered. On load the raw text goes through the same
validation as a live reply (JSON → schema → quote check). A fixture whose message hash no
longer matches is ignored, so an edited message is never analysed with a stale answer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


def message_hash(subject: str | None, body: str) -> str:
    return hashlib.sha256(f"{subject or ''}\n{body}".encode()).hexdigest()


class RecordedReply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    inbound_id: str
    model: str
    prompt_version: str
    recorded_at: datetime
    message_sha256: str
    raw: str | None  # None when the recording call itself failed
    error: str | None = None  # failure kind, when raw is None


@dataclass(frozen=True)
class FixtureStore:
    directory: Path

    def path_for(self, inbound_id: str) -> Path:
        return self.directory / f"{inbound_id}.json"

    def get(self, inbound_id: str, subject: str | None, body: str) -> RecordedReply | None:
        path = self.path_for(inbound_id)
        if not path.is_file():
            return None
        try:
            reply = RecordedReply.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            return None
        if reply.message_sha256 != message_hash(subject, body):
            return None
        return reply

    def save(self, reply: RecordedReply) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(reply.inbound_id)
        data = json.loads(reply.model_dump_json())
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
