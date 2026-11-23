"""Unhappy paths: malformed requests, corrupted files, oversized input. The app keeps working."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.core.enums import AnalysisMode
from app.main import create_app
from app.service import Service


def make(tmp_path: Path, fixtures: Path | None = None) -> Service:
    base = load_settings(read_dotenv=False)
    settings = replace(base, db_path=tmp_path / "c.db", llm_api_key=None,
                       fixtures_dir=fixtures or base.fixtures_dir)  # fmt: skip
    return Service(settings)


def test_malformed_requests_get_4xx_not_500(tmp_path: Path) -> None:
    with TestClient(create_app(make(tmp_path))) as api:
        bad_json = api.post(
            "/api/inbound", content=b"{not json", headers={"content-type": "application/json"}
        )
        assert bad_json.status_code == 422
        assert api.post("/api/inbound", json={"body": "x", "admin": True}).status_code == 422
        assert api.post("/api/inbound", json={"channel": "fax", "body": "x"}).status_code == 422
        assert (
            api.post("/api/leads/HS-1001/decisions", json={"decision": "maybe"}).status_code == 422
        )
        assert api.get("/api/kpi", params={"week": "not-a-date"}).status_code == 422
        assert api.get("/api/leads").status_code == 200  # still fine afterwards


def test_oversized_message_is_rejected_with_a_reason(tmp_path: Path) -> None:
    with TestClient(create_app(make(tmp_path))) as api:
        response = api.post("/api/inbound", json={"from_email": "a@b-co.com", "body": "x" * 6000})
        assert response.status_code == 422
        assert response.json()["detail"] == ["message text is longer than 5000 characters"]


def test_corrupt_seed_fixture_falls_back_without_crashing(tmp_path: Path) -> None:
    base = load_settings(read_dotenv=False).fixtures_dir
    fixtures = tmp_path / "fixtures"
    shutil.copytree(base, fixtures)
    (fixtures / "agent_a" / "IN-001.json").write_text("{ this is not json", encoding="utf-8")
    (fixtures / "geo" / "brief_P6.json").write_text("garbage", encoding="utf-8")
    service = make(tmp_path, fixtures)
    service.bootstrap()
    analyses = service.snapshot().analyses
    assert analyses["IN-001"].mode == AnalysisMode.RULES_ONLY  # unreadable fixture ignored
    assert analyses["IN-002"].mode == AnalysisMode.RECORDED_FIXTURE
    assert service.brief().mode == "template"


def test_second_bootstrap_does_not_reanalyse_or_duplicate(tmp_path: Path) -> None:
    service = make(tmp_path)
    service.bootstrap()
    before = service.snapshot()
    service.bootstrap()
    after = service.snapshot()
    assert len(after.world.leads) == len(before.world.leads) == 18
    assert after.analyses == before.analyses
