# Stargo RevOps take-home

Amit Levy · RevOps Engineer (AI-native Marketing Brain) take-home

A small app that turns raw GTM signals into qualified, routed leads, an honest weekly KPI
pack, and a ranked list of AI-visibility gaps with a validated content brief.

## Setup and run

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

**Without a key (default).** Nothing to configure. The app runs end to end in
**rules-only fallback mode**, shown in a banner:
- Seed messages use recorded LLM answers (`backend/fixtures/`), labelled "recorded fixture".
- Pasted messages are read by keyword rules. These are English only; anything else goes
  to `needs review`.
- Reply drafts use templates. The GEO brief shown is the recorded LLM brief (labelled "recorded fixture"); with a key it can be regenerated.

**With a key.** Copy `.env.example` to `.env` **in the repository root** (next to this
README, not in `backend/`) and set `GROQ_API_KEY`. Restart the backend. Pasted messages,
reply drafts and a regenerated brief then use Groq `openai/gpt-oss-120b`.

```bash
cp .env.example .env    # from the repository root, then edit GROQ_API_KEY
```

Scripts (run from `backend/`):

```bash
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

All tests run offline. Outbound sockets are blocked in `conftest.py`, and LLM calls use a
fake.

The five areas the brief asks for (all in `backend/tests/`):
- QL gate: `test_rules_units.py` (each condition and status rule) and `test_rules_seed.py`
  (every seed lead against the plan).
- Identity matching: `test_loader_identity.py` and `test_normalize.py`.
- Reporting window across time zones: `test_kpi.py` (`test_window_converts_to_israel_time`,
  `test_window_after_dst_change_uses_plus_two`).
- KPI counting: `test_kpi.py` (`test_golden_kpi_pack` and the per-rule tests).
- LLM failure path: `test_agents.py` (`test_bad_replies_become_failures` for invalid JSON,
  `test_a_failed_only_message_is_needs_review_never_ql_or_disqualified`) and
  `test_rules_units.py` (`test_failed_analysis_is_needs_review_never_ql`).

## Architecture

```
seed files / paste form
   → ingest: validate (reject with reasons) → normalize → identity (email / LinkedIn only)
   → injection check (code; a hit stops that message here: flagged, no LLM call)
   → Agent A: recorded fixture | LLM | keyword fallback
        JSON → Pydantic schema → every evidence quote must be in the message
        any failure → that message is flagged
   → rules (code), on usable messages only (analysed, no instruction attempt):
        exclusions → QL gate C1–C5 → status → owner → score → rationale
        flagged messages add no evidence and remove none; no usable message → needs review
   → Agent B: packages the rules result; LLM writes only the reply draft, from Agent A's
     fields and CRM facts, never the raw message; a draft is stored, never sent
   → storage (SQLite) → KPI (window in Asia/Jerusalem, record ids for every number)
GEO (separate): ai_answers.json → findings → gap ranking → brief (LLM | template)
   → claim validator (code) blocks or flags
```

**Folders.** `backend/app/{ingest, rules, agents, kpi, geo, storage, api}` follow
CLAUDE.md. `app/core/` holds config, time, enums and logging. `app/pipeline.py` builds
per-person lead contexts and is pure. `app/service.py` wires storage, agents, rules and
KPI together for the API.

**Several messages from one person.** The lead is judged on its usable messages only. A
message whose analysis failed, or that contains an instruction attempt, becomes a "needs
review" flag with its message id and reason. The flag shows in the queue, on the lead page
and in the KPI caveats. It does not change the status, owner, score or KPI.

**Sales decisions** belong to a person and are matched by normalized email or LinkedIn
URL, so a LinkedIn-only sender can be accepted and counts once. The latest decision wins;
the history stays visible.

**Safety.**
- Message text is delimited and treated as data.
- A pattern check runs before any LLM call, and Agent A also reports an instruction flag.
- Message content cannot change rules, scores, owners or prompts.
- Logs carry record ids and hashes only; there's a test for this.
- The only outbound call is the allowlisted LLM host, over https.
- The UI renders message text as text, never as HTML.

## Deterministic vs LLM

The LLM does two things: it reads free text (Agent A) and writes prose (reply drafts and
the GEO brief). Everything that must be exact or auditable is code.

| Part | Who | Why |
|---|---|---|
| Validation, normalization, identity, time window | Code | Must be exact and repeatable |
| Injection check (first layer) | Code | The model under attack can't be trusted to report it |
| Agent A extraction (language, intent, role, problem, facts, quotes) | LLM, keyword fallback | Free text in any language |
| Evidence quotes are really in the message | Code | Catches invented quotes |
| Exclusions, QL gate C1–C5, status, routing | Code | Must be auditable |
| Priority score and rationale | Code | Explainable field by field; rationale built from evidence only |
| Reply draft | LLM, template fallback | Prose; checked in code, and a human approves it |
| KPI pack | Code | Numbers must be reproducible and traceable |
| GEO mentions, owned citations, competitors, look-alikes, wrong claims | Code | String and domain matching against BC-5 categories |
| Gap ranking | Code | Formula |
| Content brief | LLM, template fallback | Prose |
| Claim validator | Code | Must block; can't trust the generator |

## Scoring formulas

### Lead priority score (0–100)

Computed only for `QL`, `QL candidate` and `nurture`. Excluded, suppressed, disqualified
and needs-review leads have no score. The score never changes the status: the QL gate
decides first. An unknown input scores 0 and is labelled "unknown", not "fail".

| Factor | Max | Points |
|---|---:|---|
| Interest | 30 | demo, pricing or pilot request 30 · asks for a call 22 · soft positive 10 · declined or none 0 |
| Problem fit | 25 | a problem Stargo solves (BC-3) with a stated volume or time cost 25 · solved problem, no volume 18 · related but not a listed pain 6 · none 0 |
| Buyer | 20 | C-level, VP, Director, Head, or owner/founder 20 · Manager 14 · below manager 4 · unknown 0 |
| Company fit | 15 | ICP vertical 6 + ICP region 5 + 20 or more employees 4; a fact stated only by the sender (unverified) gets half, rounded down (3, 2, 2) |
| Timing | 10 | this week, next week or two, or this quarter 10 · later 4 · none stated 0 |

Bands (a label for reps, not a status): 70 or more = A, 40–69 = B, under 40 = nurture
band. The lead page shows each factor with its basis.

### GEO gap score

```
gap(prompt) = priority × Σ over engines g(state) × fit
```

- `g`: owned (mentioned and cited from stargo.co) 0 · mentioned without an owned citation
  0.5 · absent 1 · wrong claim 1.5.
- `fit`: 1 if a BC-3 product answers the prompt's need, else 0.
- Ties: more distinct competitors first, then prompt id.

Why:
- Priority is the weight the team already set.
- Summing over engines rewards breadth.
- A wrong claim is worse than silence because it mis-sells.
- An unowned mention is half a win, because we don't control the source.
- `fit` keeps the brief from inventing a product: P8 (rate benchmarking for shippers)
  scores 0.

Look-alike domains and wrong claims also go to a separate risk table, so a low-priority
prompt can't bury them. The top gap is P6, "alternatives to Laneframe" (score 9).

## Key assumptions and trade-offs

Every decision is in `docs/ASSUMPTIONS.md`. The ones that shape behaviour most:

- **No country, no guess.** A lead with no stated country goes to the Triage queue instead
  of being guessed from the email domain. Cost: more manual triage. Gain: no lead is routed
  to the wrong rep on a guess.
- **Acceptance doesn't override the standard.** An accepted lead that fails C3 or C4 is
  `nurture` with its owner, not a QL. The decision stays visible. The status follows the QL
  standard, not the sales relationship. (Tom Becker: accepted by Leo, C3 fails.)
- **Messages can't remove a QL.** A failed or flagged message adds a review flag but never
  removes an existing QL, so message content can't change the KPI.
- **A past week's pack is fixed.** It is built only from what was known before the next
  reporting week began. Later activity can't change its numbers or lists.
- **Unknown is not zero.** The historical-reactivation feed was not received, so its
  source count is "unknown" and the pack carries a caveat.
- **Recorded fixtures for seed messages.** Seed analyses were captured once from the real
  LLM and committed, so the no-key run gives the same KPI as the keyed run.

## What I cut

- **HubSpot dry-run sync (bonus).** Not built. Time went to the core parts and the failure
  paths, which the brief scores higher.
- The other bonus, a labelled eval set, is done: see `docs/AGENT_A_EVAL.md`.
- Nothing from parts 1–6 was cut.

## With more time

- Build the HubSpot dry-run sync: the exact CRM v3 payloads for contact updates, lead
  status and owner.
- A larger held-out set, labelled by someone other than me.
- A meaning-level check for the brief and reply drafts, on top of the current tag, figure
  and word-list checks.
- Detect vendors outside `known_competitors` in AI answers.
- Keyword fallback for Hebrew and other languages, so fewer messages go to `needs review`
  in no-key mode.
- Re-run the GEO prompts on a schedule and track the gap scores week over week.

## Styling

Plain CSS with colour tokens and light and dark schemes, no UI framework: five views and
a 390 px layout don't justify a dependency.

## Deviations from the plan

- **LLM model.** The plan named Groq `llama-3.3-70b-versatile`. Groq no longer serves it
  (HTTP 404, "model does not exist"), so the app uses Groq `openai/gpt-oss-120b`. The
  provider choice (decision Q11) is unchanged. Set it with `LLM_MODEL` in `.env`.
- **Extra modules.** `app/core/`, `app/pipeline.py` and `app/service.py` are not in
  CLAUDE.md's folder list. They keep `api/` thin and the rules pure.
- **Status mapping.** Revised after the plan by my decisions: Q12 was replaced (D12),
  and D17 (region-only C1 failure → nurture) was added. Tom is `nurture` (owner Leo), not
  `disqualified`.
- **Rachel's QL record.** The QL record is SD-004, her latest decision. SD-003 is listed
  as superseded. The plan listed SD-003 with SD-004 as the duplicate.
- **Drafts are on request.** A reply draft is generated when a person clicks "Draft a
  reply", not automatically. A GET never calls the LLM, and startup makes no LLM calls.
- **Frontend tooling.** ESLint instead of the template's oxlint, as CLAUDE.md asks.
  TypeScript is pinned to 6.0 because typescript-eslint does not support 7 yet.
- **Multi-message rule (D16).** The plan made a lead `needs review` if any of its messages
  failed analysis or contained an instruction attempt. Revised by my decision: such a
  message is a visible flag and changes nothing; only a lead with no usable message is
  `needs review`.
- **Decisions by person.** The plan keyed decisions by contact email. They now match a
  person by email or LinkedIn, as the brief allows either to be blank.
- **Brief generation.** If Groq's JSON mode rejects a long reply, it retries once without
  JSON mode. The reply is still parsed, schema-validated and checked by the validator.

## Known limitations

- The keyword fallback reads English only; other languages go to `needs review`, by design.
  It reads company facts only from the sender's own description ("a German freight
  forwarder", "a Singapore 3PL", "based in Haifa"), never from the email domain.
- Groq's free tier rate-limits bursts. On HTTP 429 the client waits for `Retry-After`
  (at most 10 s) and retries once. If it is still limited, that message is flagged
  `needs review` with the reason shown; nothing is guessed.
- The claim validator checks tags, figures and the BC-5 rules, not meaning. A paraphrase
  that goes slightly beyond its source can pass, so a human reviews before publishing.
- The outcome-promise check on reply drafts is a word list (English and a few Hebrew
  words). The prompt rule is the main defence, and every draft needs human approval
  anyway. A paraphrase that isn't on the list can get through; a figure that isn't from
  PP-1 to PP-3 is always caught.
- Unknown vendors outside `known_competitors` are not detected in AI answers.
- A person outside the CRM keeps their id when a later message adds an email or LinkedIn
  URL. If two people who already exist are later merged by a shared key, one id goes away;
  their decisions survive because they re-attach by email or LinkedIn.
- A blank `GROQ_API_KEY=` in the shell environment does not override a key in `.env`.
  Remove the key from `.env` to run without it.

## More detail

- `docs/PLAN.md`: the approved plan, with the record-by-record walk-through and the
  expected KPI.
- `docs/ASSUMPTIONS.md`: every decision and assumption.
- `docs/AGENT_A_EVAL.md`: Agent A against hand labels (in-sample) and a held-out set run
  once after the prompt was frozen, with the overfitting risk and the main known weakness:
  rate quoting vs a buyer benchmarking carrier quotes.
- `KPI_PACK.md`: the exported pack for Sun 4 – Thu 8 Oct 2026, with the CRO note.
- `PROCESS.md`: how I worked with AI tooling.
