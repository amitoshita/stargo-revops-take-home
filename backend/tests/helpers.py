"""Shared test helpers."""

from __future__ import annotations

from pathlib import Path

from app.ingest.loader import SeedBundle, load_seed

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def seed() -> SeedBundle:
    return load_seed(DATA_DIR)
