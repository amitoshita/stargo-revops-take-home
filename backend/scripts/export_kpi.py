"""Write KPI_PACK.md at the repo root from the app's stored records (same path as the API).

Usage (from backend/):  uv run python -m scripts.export_kpi [--week 2026-10-04] [--db PATH]

Uses its own database by default (a fresh seed: recorded fixtures, no LLM call), so the
pack reflects the seed data plus nothing else. Pass --db to export from the app database.
An existing "Note to the CRO" in the file is preserved.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import replace
from datetime import date
from pathlib import Path

from app.core.config import REPO_ROOT, load_settings
from app.kpi.window import WEEK_UNDER_REVIEW
from app.service import Service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", type=date.fromisoformat, default=WEEK_UNDER_REVIEW.sunday)
    parser.add_argument("--db", type=Path, default=None, help="export from this database")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "KPI_PACK.md")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        settings = load_settings(read_dotenv=False)
        settings = replace(settings, db_path=args.db or Path(tmp) / "export.db")
        service = Service(settings, use_llm=False)
        service.bootstrap()
        service.export_kpi(args.week, args.out)
        pack = service.kpi(args.week)
    print(f"Wrote {args.out} for week {args.week}.")
    for metric in pack.metrics:
        refs = ", ".join(r.record_id for r in metric.records)
        print(f"  {metric.label}: {metric.actual}/{metric.target}  [{refs}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
