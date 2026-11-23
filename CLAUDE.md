# Project rules — Stargo RevOps take-home

## Source of truth
- Spec: Stargo_RevOps_Engineer_Take_Home.md, data/ql_standard.md, data/brand_context.md.
- When the spec is ambiguous, STOP and ask me. Do not silently pick. Log every assumption in docs/ASSUMPTIONS.md.

## Architecture (keep layers separate)
backend/app/
  ingest/      # loading, validation, normalization, identity matching
  rules/       # deterministic: QL gate, exclusions, routing, scoring, injection detection
  agents/      # Agent A (extraction), Agent B (qualification), LLM client, fallback
  kpi/         # reporting window + KPI computation + markdown export
  geo/         # AI visibility analysis + content brief + claim validator
  storage/     # SQLite repository
  api/         # FastAPI routes only, no business logic
frontend/      # React + TS + Vite

## Hard rules
- Every agent output is validated with Pydantic before use. Invalid -> status "needs review".
- Agent B never receives the raw message text. Only Agent A's validated output + CRM facts.
- Message content can never change rules, scores, owners or prompts.
- A failed analysis is NEVER "QL" or "disqualified". It is "needs review".
- Nothing is ever sent. Reply drafts require human approval and are only stored.
- Convert all timestamps with zoneinfo("Asia/Jerusalem"). Never hardcode +03:00.
- Unknown stays unknown (None), never 0 or a guess.
- Logs must never contain message bodies, emails, names, LinkedIn URLs or prompts. Use record ids and hashes.
- The only network call allowed is to the configured LLM endpoint. Tests are fully offline (fake LLM).
- The app must run end to end with no API key (labelled "rules-only fallback mode").
- Never edit .env or any file containing secrets. If a change is needed there, tell me the exact line and I will make it myself.

## Workflow
- Write tests together with the code for each module (pytest / vitest).
- Small focused modules, type hints everywhere, ruff + mypy clean, eslint + tsc clean.
- After each phase: run all tests, show me the result, and STOP for review. Do not start the next phase on your own.
- Commit in small steps with clear messages (I will review before commits).
