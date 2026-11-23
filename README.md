# Stargo RevOps take-home

A small app that turns raw GTM signals into qualified, routed leads, an honest weekly KPI
pack, and a ranked list of AI-visibility gaps with a validated content brief.

> Draft. Amit edits the final wording. `PROCESS.md` and the CRO note in `KPI_PACK.md` are
> written by hand.

## Quick start

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 24.

```bash
# backend (http://127.0.0.1:8000)
cd backend
uv sync
uv run uvicorn app.main:app

# frontend (http://localhost:5173, proxies /api to the backend)
cd frontend
npm ci
npm run dev
```

On first start the backend creates `backend/stargo.db`, loads `data/` and analyses the
seed messages. Delete the file to start over.

**No key needed.** Without a key the app runs end to end in **rules-only fallback mode**
(shown in a banner):
- Seed messages use recorded LLM answers (`backend/fixtures/`), labelled "recorded fixture".
- Pasted messages are read by keyword rules. These are English only; anything else goes
  to `needs review`.
- Drafts and the brief use templates.

**With a key**, copy `.env.example` to `.env` and set `GROQ_API_KEY`. Pasted messages,
reply drafts and a regenerated brief then use Groq `openai/gpt-oss-120b`.

```bash
cd backend
uv run python -m scripts.export_kpi        # writes KPI_PACK.md (keeps the CRO note)
uv run python -m scripts.eval_agent_a      # fixtures vs hand labels (offline)
uv run python -m scripts.eval_heldout      # held-out set (offline, from recordings)
uv run python -m scripts.record_fixtures   # re-record seed answers (needs a key)
uv run python -m scripts.record_brief      # re-record the LLM brief (needs a key)
```

## Checks

```bash
cd backend && uv run ruff check . && uv run mypy && uv run pytest
cd frontend && npx tsc -b && npx eslint . && npx vitest run
```

The tests are fully offline. Outbound sockets are blocked in `conftest.py`, and LLM calls
use a fake. There are about 400 backend tests and 18 frontend tests.

## How it works

```
seed files / paste form
   → ingest: validate (reject with reasons) → normalize → identity (email / LinkedIn only)
   → injection check (code; a hit stops here: needs review, no LLM call)
   → Agent A: recorded fixture | LLM | keyword fallback
        JSON → Pydantic schema → every evidence quote must be in the message
        any failure → needs review
   → rules (code): exclusions → QL gate C1–C5 → status → owner → score → rationale
   → Agent B: packages the rules result; LLM writes only the reply draft, from Agent A's
     fields and CRM facts, never the raw message; a draft is stored, never sent
   → storage (SQLite) → KPI (window in Asia/Jerusalem, record ids for every number)
GEO (separate): ai_answers.json → findings → gap ranking → brief (LLM | template)
   → claim validator (code) blocks or flags
```

**Code vs LLM.** The LLM reads free text (Agent A) and writes prose: reply drafts and the
brief. Everything that must be exact or auditable is code: validation, identity, time, the
QL gate, exclusions, routing, scoring, the rationale, the KPI, GEO detection and the claim
validator.

**Folders.** `backend/app/{ingest, rules, agents, kpi, geo, storage, api}` follow
CLAUDE.md. `app/core/` holds config, time, enums and logging. `app/pipeline.py` builds
per-person lead contexts and is pure. `app/service.py` wires storage, agents, rules and
KPI together for the API.

**Safety.**
- Message text is delimited and treated as data.
- A layer-1 pattern check runs before any LLM call, and Agent A reports a layer-2 flag.
- Message content cannot change rules, scores, owners or prompts.
- Logs carry record ids and hashes only; there's a test for this.
- The only outbound call is the allowlisted LLM host, over https.
- The UI renders message text as text, never as HTML.

**Styling.** Plain CSS with colour tokens and a light and dark scheme, and no UI framework.
Five views don't justify a dependency, and the 390 px layout needs only stacked cards and
tables that scroll inside their card.

## Decisions and evaluation

- `docs/PLAN.md`: the approved plan, with the record-by-record walk-through and the
  expected KPI.
- `docs/ASSUMPTIONS.md`: every decision and assumption.
- `docs/AGENT_A_EVAL.md`: Agent A against hand labels (in-sample) and a held-out set run
  once after the prompt was frozen. It includes the overfitting risk and the main known
  weakness: rate quoting vs a buyer benchmarking carrier quotes.

## Deviations from the plan

- **LLM model.** The plan named Groq `llama-3.3-70b-versatile`. Groq no longer serves it
  (HTTP 404, "model does not exist"), so the app uses Groq `openai/gpt-oss-120b`. The
  provider choice (decision Q11) is unchanged. Set it with `LLM_MODEL` in `.env`.
- **Extra modules.** `app/core/`, `app/pipeline.py` and `app/service.py` are not in
  CLAUDE.md's folder list. They keep `api/` thin and the rules pure.
- **Status mapping.** Revised after the plan by Amit's decisions: Q12 was replaced (D12),
  and D17 (region-only C1 failure → nurture) was added. Tom is `nurture` (owner Leo), not
  `disqualified`.
- **Rachel's QL record.** The QL record is SD-004, her latest decision. SD-003 is listed
  as superseded. The plan listed SD-003 with SD-004 as the duplicate.
- **Drafts are on request.** A reply draft is generated when a person clicks "Draft a
  reply", not automatically. A GET never calls the LLM, and startup makes no LLM calls.
- **Frontend tooling.** ESLint instead of the template's oxlint, as CLAUDE.md asks.
  TypeScript is pinned to 6.0 because typescript-eslint does not support 7 yet.
- **Brief generation.** If Groq's JSON mode rejects a long reply, it retries once without
  JSON mode. The reply is still parsed, schema-validated and checked by the validator.

## Known limitations

- The keyword fallback reads English only; other languages go to `needs review`, by design.
- The claim validator checks tags, figures and the BC-5 rules, not meaning. A paraphrase
  that goes slightly beyond its source can pass, so a human reviews before publishing.
- Unknown vendors outside `known_competitors` are not detected in AI answers.
- A person outside the CRM keeps their id when a later message adds an email or LinkedIn
  URL. If two people who already exist are later merged by a shared key, one id goes away;
  their decisions survive because they are keyed by email.
- Decisions are keyed by email, so a LinkedIn-only sender cannot be accepted until an email
  is known. The API says so.
- A blank `GROQ_API_KEY=` in the shell environment does not override a key in `.env`.
  Remove the key from `.env` to run without it.
