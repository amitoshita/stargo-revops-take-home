"""Runtime configuration from environment variables (optionally a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_LLM_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_LLM_MODEL = "llama-3.3-70b-versatile"


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines, no interpolation. Existing env vars win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str
    llm_timeout_s: float
    db_path: Path
    data_dir: Path
    fixtures_dir: Path

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)


def load_settings(*, read_dotenv: bool = True) -> Settings:
    if read_dotenv:
        _load_dotenv(REPO_ROOT / ".env")
    key = os.environ.get("GROQ_API_KEY", "").strip() or None
    return Settings(
        llm_api_key=key,
        llm_base_url=os.environ.get("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/"),
        llm_model=os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL),
        llm_timeout_s=float(os.environ.get("LLM_TIMEOUT_S", "20")),
        db_path=Path(os.environ.get("DB_PATH", str(REPO_ROOT / "backend" / "stargo.db"))),
        data_dir=Path(os.environ.get("DATA_DIR", str(REPO_ROOT / "data"))),
        fixtures_dir=Path(os.environ.get("FIXTURES_DIR", str(REPO_ROOT / "backend" / "fixtures"))),
    )
