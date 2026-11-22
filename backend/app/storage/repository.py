"""SQLite persistence. Records are stored as validated Pydantic JSON with a few key columns.

Everything the app shows is rebuilt from these tables, so a restart loses nothing.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.core.enums import Source
from app.ingest.loader import SeedBundle
from app.ingest.schemas import (
    CrmContact,
    FeedStatus,
    InboundMessage,
    IngestError,
    PipelineEvent,
    SalesDecision,
)

M = TypeVar("M", bound=BaseModel)

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS crm_contacts (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inbound (
    id TEXT PRIMARY KEY, origin TEXT NOT NULL, created_seq INTEGER NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ingest_errors (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY, origin TEXT NOT NULL, created_seq INTEGER NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pipeline_events (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS feed_status (source TEXT PRIMARY KEY, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
    kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY (kind, id)
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---- meta / seeding -------------------------------------------------
    def get_meta(self, key: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return str(row[0]) if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))

    def is_seeded(self) -> bool:
        return self.get_meta("seeded_at") is not None

    def seed(self, bundle: SeedBundle) -> bool:
        """Insert the seed pack once. Returns False if the database was already seeded."""
        if self.is_seeded():
            return False
        with self._conn() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO crm_contacts (id, data) VALUES (?, ?)",
                [(c.record_id, c.model_dump_json()) for c in bundle.crm],
            )
            for message in bundle.inbound:
                self._insert_inbound(conn, message)
            for decision in bundle.decisions:
                self._insert_decision(conn, decision)
            conn.executemany(
                "INSERT OR REPLACE INTO pipeline_events (id, data) VALUES (?, ?)",
                [(e.id, e.model_dump_json()) for e in bundle.events],
            )
            conn.executemany(
                "INSERT OR REPLACE INTO feed_status (source, status) VALUES (?, ?)",
                [(s.value, st) for s, st in bundle.feed_status.items()],
            )
            conn.executemany(
                "INSERT INTO ingest_errors (created_at, data) VALUES (?, ?)",
                [(_now(), e.model_dump_json()) for e in bundle.errors],
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('seeded_at', ?)", (_now(),)
            )
        return True

    # ---- inbound --------------------------------------------------------
    @staticmethod
    def _next_seq(conn: sqlite3.Connection, table: str) -> int:
        row = conn.execute(f"SELECT COALESCE(MAX(created_seq), 0) + 1 FROM {table}").fetchone()
        return int(row[0])

    def _insert_inbound(self, conn: sqlite3.Connection, message: InboundMessage) -> None:
        conn.execute(
            "INSERT INTO inbound (id, origin, created_seq, data) VALUES (?, ?, ?, ?)",
            (
                message.id,
                message.origin,
                self._next_seq(conn, "inbound"),
                message.model_dump_json(),
            ),
        )

    def add_inbound(self, message: InboundMessage) -> None:
        with self._conn() as conn:
            self._insert_inbound(conn, message)

    def next_ui_id(self, prefix: str, table: str) -> str:
        with self._conn() as conn:
            count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE origin = 'ui'").fetchone()[0]
        return f"{prefix}{int(count) + 1:03d}"

    def list_inbound(self) -> list[InboundMessage]:
        return self._list("SELECT data FROM inbound ORDER BY created_seq", InboundMessage)

    # ---- CRM / events / feed ---------------------------------------------
    def list_crm(self) -> list[CrmContact]:
        return self._list("SELECT data FROM crm_contacts ORDER BY id", CrmContact)

    def list_events(self) -> list[PipelineEvent]:
        return self._list("SELECT data FROM pipeline_events ORDER BY id", PipelineEvent)

    def feed_status(self) -> dict[Source, FeedStatus]:
        with self._conn() as conn:
            rows = conn.execute("SELECT source, status FROM feed_status").fetchall()
        return {
            Source(src): ("received" if status == "received" else "not_received")
            for src, status in rows
        }

    # ---- decisions ------------------------------------------------------
    def _insert_decision(self, conn: sqlite3.Connection, decision: SalesDecision) -> None:
        conn.execute(
            "INSERT INTO decisions (id, origin, created_seq, data) VALUES (?, ?, ?, ?)",
            (
                decision.id,
                decision.origin,
                self._next_seq(conn, "decisions"),
                decision.model_dump_json(),
            ),
        )

    def add_decision(self, decision: SalesDecision) -> None:
        with self._conn() as conn:
            self._insert_decision(conn, decision)

    def list_decisions(self) -> list[SalesDecision]:
        return self._list("SELECT data FROM decisions ORDER BY created_seq", SalesDecision)

    # ---- ingest errors --------------------------------------------------
    def add_ingest_error(self, error: IngestError) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO ingest_errors (created_at, data) VALUES (?, ?)",
                (_now(), error.model_dump_json()),
            )

    def list_ingest_errors(self) -> list[IngestError]:
        return self._list("SELECT data FROM ingest_errors ORDER BY seq", IngestError)

    # ---- documents (agent outputs, assessments, KPI packs, GEO) ------------
    def put_doc(self, kind: str, doc_id: str, model: BaseModel) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO documents (kind, id, data, updated_at) VALUES (?, ?, ?, ?)",
                (kind, doc_id, model.model_dump_json(), _now()),
            )

    def get_doc(self, kind: str, doc_id: str, model: type[M]) -> M | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM documents WHERE kind = ? AND id = ?", (kind, doc_id)
            ).fetchone()
        return model.model_validate_json(row[0]) if row else None

    def list_docs(self, kind: str, model: type[M]) -> dict[str, M]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, data FROM documents WHERE kind = ? ORDER BY id", (kind,)
            ).fetchall()
        return {doc_id: model.model_validate_json(data) for doc_id, data in rows}

    def delete_docs(self, kind: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM documents WHERE kind = ?", (kind,))

    # ---- helpers --------------------------------------------------------
    def _list(self, sql: str, model: type[M]) -> list[M]:
        with self._conn() as conn:
            rows = conn.execute(sql).fetchall()
        return [model.model_validate_json(row[0]) for row in rows]
