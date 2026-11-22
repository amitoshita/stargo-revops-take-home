"""PII-safe logging.

Rule: log record ids, hashes, statuses and counts only. As a second line of defence,
a filter redacts anything that looks like an email address or a LinkedIn URL.
"""

from __future__ import annotations

import hashlib
import logging
import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_LINKEDIN = re.compile(r"(https?://)?([a-z]{2,3}\.)?linkedin\.com/\S*", re.IGNORECASE)


def short_hash(value: str) -> str:
    """Stable 12-char hash for correlating records in logs without exposing content."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def redact(text: str) -> str:
    return _LINKEDIN.sub("[linkedin]", _EMAIL.sub("[email]", text))


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # httpx logs full request URLs at INFO; keep it quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
