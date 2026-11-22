# PLAN — Stargo RevOps take-home

> Execution note: plan mode lets me write only this file. Once you approve, the single action is to copy this file verbatim to `~/stargo-revops/docs/PLAN.md`. No code, no commit. Then I stop.
>
> Revision 2: your decisions on Q1–Q11 are folded in (§9), along with routing for unknown senders and the simplifications. Target is ~16–18 h.

## Context
This is option 2 of the setup. The repo (`ac191ec`) holds the spec, data and CLAUDE.md. Before any code, we need a plan you can check against your own hand count. I derived everything below from the repo files only: the spec, `ql_standard.md` (QLS), `brand_context.md` (BC), `DATA_README.md`, the three data files and CLAUDE.md. I did not use the playbook's numbers. Every number in §8 traces back to record ids in §7.

Abbreviations: QLS §n = ql_standard section n. C1–C5 = the five QL conditions. IL = Asia/Jerusalem.

---

## 1. Requirements checklist

| # | Requirement (source) | Module | Test |
|---|---|---|---|
| R1 | Load `crm_export.csv` + `gtm_events.json` on first run (brief §1) | ingest/loader | test_loader: 19 CRM, 21 inbound, 11 SD, 12 PE loaded; idempotent second run |
| R2 | Paste new inbound: name, email or LinkedIn (either blank), channel, text, optional received time (default now), optional source (blank = not recorded) (brief §1) | api/inbound + ingest | test_paste: defaults applied; `source=None` kept as None |
| R3 | Pasted message goes through the same pipeline as seed data (brief §1) | pipeline orchestrator | test_pipeline_same_path: seed and UI input call one function |
| R4 | Normalize emails, LinkedIn URLs, domains: lowercase, strip `www.`/subdomains, keep `.co.uk/.com.sg/.co.il` (QLS §3) | ingest/normalize | test_normalize_domain (table-driven) |
| R5 | Reject invalid records with a clear message, never crash (brief §1) | ingest/validate | test_invalid: IN-019 rejected with reason; app continues |
| R6 | One person counted once; match only by normalized email / LinkedIn, never by name, city or company (QLS §3) | ingest/identity | test_identity: IN-002+IN-003 merge, IN-001+IN-021 merge, IN-010 ≠ Felix |
| R7 | Free email domains don't identify a company; stated facts marked unverified; no invented firmographics (QLS §3) | ingest/normalize + rules/ql_gate | test_free_domain: Yossi → company unknown, stated facts unverified |
| R8 | Unknown stays unknown (None), never 0 (QLS §3, CLAUDE.md) | all schemas | test_unknown: blank employees → None |
| R9 | Agent A output: language, intent (10-value enum), buyer role, data problem, company facts, evidence quotes (brief §2) | agents/agent_a | test_agent_a_schema |
| R10 | Agent B output: score 0–100 + per-factor breakdown, status, all 5 conditions checked, owner, one-line rationale tied to evidence, optional draft (brief §2) | agents/agent_b + rules | test_agent_b_output |
| R11 | Agent B never receives the raw message (brief §2, CLAUDE.md) | agents/agent_b | test_agent_b_no_raw_text: fake LLM asserts body absent from prompt |
| R12 | Schema-validate every agent output before use; invalid → needs review (brief §2, CLAUDE.md) | agents/validation | test_invalid_json_needs_review |
| R13 | QL gate and exclusions are auditable (brief §2) | rules/ql_gate, rules/exclusions | test_checklist_has_evidence_per_condition |
| R14 | Unhappy path: model error, timeout, invalid JSON, non-English, hidden instructions → app keeps working (brief §2) | agents/llm_client + fallback | test_timeout, test_garbage, test_unreachable, test_hebrew |
| R15 | Message content never changes rules, scores, owners or prompts (brief §2, CLAUDE.md) | rules/injection + agents | test_injection_IN010: needs review, owner unaffected, no draft |
| R16 | A failed analysis is `needs review`, never QL or disqualified (brief §2, QLS §5) | rules/status | test_failed_never_ql (table-driven over failure kinds: timeout, invalid JSON, garbage, unreachable, schema-invalid) |
| R17 | QL = all of C1–C5; accepted but failing C1–C4 → not QL, decision kept, failing condition shown (QLS §1) | rules/ql_gate | test_acceptance_does_not_override |
| R18 | C1–C4 met without C5 → `QL candidate` (QLS §1) | rules/ql_gate | test_candidate (Marcus) |
| R19 | Unverified stated facts can satisfy a condition when flagged (QLS §1) | rules/ql_gate | test_unverified_passes_flagged (Yossi) |
| R20 | Exclusions: customers → expansion; open deal created before first inbound AND before acceptance → deal owner; researched-only; competitors/vendors, investors, job seekers/students, auto-replies; unsubscribes suppressed with no draft (QLS §2) | rules/exclusions | test_exclusions (one case each) |
| R21 | A deal created after acceptance is an acquisition opportunity (QLS §2) | rules/exclusions + kpi | test_post_acceptance_deal (Felix D-2231) |
| R22 | A CRM "QL" status is not evidence (QLS §2) | rules/exclusions | test_crm_ql_status_ignored (Lukas) |
| R23 | Priority score 0–100, explainable per field, never overrides the gate; bands A ≥70 / B 40–69 / nurture <40 (QLS §4) | rules/scoring | test_score_breakdown_sums, test_score_not_gate |
| R24 | Statuses limited to the 7 in QLS §5 | schemas | enum test |
| R25 | `needs review` on analysis failure OR an instruction attempt (QLS §5) | rules/status | covered by R15/R16 |
| R26 | Routing table by region; customers/open deals → CRM owner; investors → Founders; disqualified → no owner; needs review keeps account/region owner (QLS §5) | rules/routing | test_routing (table-driven) |
| R26b | Senders not in the CRM: region from the stated country (unverified); no country → Triage queue (your decision) | rules/routing | test_routing_unknown_sender: pasted message from an unknown person at an unknown company → Triage queue; same with a stated "Rotterdam" → Dana (unverified) |
| R27 | KPI week Sun 00:00 – Thu 23:59 IL; convert every timestamp to IL before comparing (QLS §6) | kpi/window | test_window_tz: IN-017 inside, IN-018 outside, PE-012 outside |
| R28 | QLs count by `decided_at`, once per person (QLS §6) | kpi/compute | test_ql_dedup (SD-003/004) |
| R29 | Fri/Sat inbound stays queued with its original timestamp and counts when accepted (QLS §6) | kpi + storage | test_friday_inbound (Marcus accepted later in UI) |
| R30 | Booked/held/opps count by their own event date, any cohort (QLS §6) | kpi/compute | test_pipeline_counts |
| R31 | Acquisition KPIs exclude customers + pre-existing deals; expansion on its own line (QLS §6) | kpi/compute | test_expansion_line (Mark) |
| R32 | Source = source of the person's earliest inbound; none → "source not recorded"; never borrow (QLS §6) | kpi/source | test_source_earliest (Pieter → event-email; Anouk → event-email) |
| R33 | Feed not received → unknown, not 0 (QLS §6) | kpi/source | test_historical_reactivation_unknown |
| R34 | Targets 25/15/12/5; honest shortfall (QLS §6) | kpi/compute | golden KPI test |
| R35 | Every KPI number traceable to records (brief §3) | kpi + api + UI | test_record_ids_present |
| R36 | Pack recomputed from stored decisions; UI Accept/Reject counts only if `decided_at` is in the week (brief §3) | kpi + storage | test_ui_decision_past_vs_current |
| R37 | GEO: per prompt × engine: mentioned, cited from an owned domain, competitors present, look-alikes, wrong claims (brief §4) | geo/analyze | test_geo: P2-PER not owned; P5 CHA/GEM wrong |
| R38 | Ranked gap list with a defined, justified formula (brief §4) | geo/gap | test_gap_ranking |
| R39 | LLM brief for the top gap per BC-7; every claim cites BC/PP; unsupported claims blocked/flagged (brief §4, BC-5/7) | geo/brief + geo/validator | test_validator_blocks_untagged_roi, test_competitor_claim_blocked |
| R40 | Persist leads, agent outputs, decisions, KPI pack; survives restart (brief §5) | storage | test_persistence_restart |
| R41 | UI: queue (name, company, channel, IL time, badge, status, owner); detail; Accept/Reject with editable `decided_at`; KPI view with drill-down; AI visibility view; 390 px readable (brief §6) | frontend | vitest: IL time format, badge |
| R42 | Tests offline with a fake LLM (brief, CLAUDE.md) | tests/conftest | network-blocking fixture |
| R43 | Free/local LLM; `.env.example`; runs end to end with no key, labelled fallback (brief tech) | agents/llm_client, config | test_no_key_mode |
| R44 | Nothing sent; drafts stored only, human approval label (brief, QLS §7) | agents/agent_b + UI | test_no_send_path (no SMTP/HTTP besides LLM) |
| R45 | Logs: no bodies, emails, names, LinkedIn URLs, prompts — ids and hashes only (brief review §6, CLAUDE.md) | logging config | test_logs_pii_free (caplog scan) |
| R46 | Only network call = configured LLM endpoint (brief review §6) | agents/llm_client | test_single_endpoint |
| R47 | Deliverables: README, PROCESS.md (yours), KPI_PACK.md with a CRO note ≤150 words (brief) | kpi/export + docs | test_kpi_md_export |

---

## 2. Architecture and data flow

```
 seed files ─┐                      UI paste form ─┐
 (CSV, JSON) │                                     │
             ▼                                     ▼
       ┌───────────────────────── ingest/ ──────────────────────────┐
       │ 1 validate (Pydantic) ──invalid──► ingest_errors (reason)  │
       │ 2 normalize: email, LinkedIn, domain, country→region, IL tz│
       │ 3 identity match → person_id (email | LinkedIn only)       │
       │   + CRM link + company link by domain (company ≠ person)   │
       └───────────────────────────┬────────────────────────────────┘
                                   ▼
       ┌──────────── rules/injection (deterministic) ───────────────┐
       │ instruction attempt? ─yes─► status=needs review,           │
       │                            owner=account/region, no LLM    │
       └───────────────────────────┬────────────────────────────────┘
                                   ▼ no
       ┌──────────── agents/agent_a (LLM | rules fallback) ─────────┐
       │ input: message text (delimited, untrusted) + CRM facts     │
       │ output JSON ─► Pydantic AgentAOutput ─► evidence quotes    │
       │ must be substrings of the message (code check)             │
       │ any failure (timeout/invalid/garbage) ─► needs review      │
       └───────────────────────────┬────────────────────────────────┘
                                   ▼ validated AgentAOutput (no raw text after here)
       ┌──────────── rules/ (deterministic, auditable) ─────────────┐
       │ exclusions → QL checklist C1–C5 → status → routing → score │
       └───────────────────────────┬────────────────────────────────┘
                                   ▼
       ┌──────────── agents/agent_b ────────────────────────────────┐
       │ code: assembles AgentBOutput from the rules results;       │
       │ rationale = code template from the evidence                │
       │ LLM: reply draft only, from AgentAOutput + CRM facts;      │
       │ validated; template draft in fallback; no draft if         │
       │ suppressed/excluded/disqualified/needs review              │
       └───────────────────────────┬────────────────────────────────┘
                                   ▼
       storage/ (SQLite): persons, crm_contacts, inbound, analyses,
                          decisions, pipeline_events, kpi_packs,
                          geo_findings, briefs, ingest_errors
                                   ▼
       kpi/: window(IL) → QLs by decided_at, pipeline by event date,
             expansion line, sources (feed_status) → KpiPack + record ids
             → KPI_PACK.md export

       geo/ (independent branch): ai_answers.json → findings → gap rank
             → brief (LLM | template) → claim validator → storage

       api/ (FastAPI, thin)  ◄──►  frontend/ (React + TS + Vite)
```

**Key point:** the KPI never reads the message text. It reads only stored statuses, checklists, decisions and events. A UI Accept triggers a rules rerun for that person (no new LLM call), then a KPI recompute.

---

## 3. Deterministic vs LLM split

| Component | Who | Reason |
|---|---|---|
| Validation, normalization, identity | Code | Must be exact and repeatable; it's spec'd as rules |
| Timezone / window | Code | Arithmetic; zoneinfo |
| Injection detection (layer 1) | Code | Cannot rely on the model being attacked to report the attack |
| Agent A extraction (language, intent, role, problem, facts, quotes) | LLM, with a rules fallback | Free text in any language; this is the only part that needs language understanding |
| Evidence-quote verification | Code | Catches hallucinated quotes cheaply |
| Seniority from job title | Code (keyword map) | Titles are short and the rule (manager+, owner <200) is mechanical |
| Problem category → BC-3 product | LLM proposes a category from a closed enum; code maps it to C3 pass/fail | Closed enum keeps it auditable |
| Exclusions, QL gate C1–C5, status | Code | Spec demands auditability; must not drift |
| Routing | Code | Lookup table |
| Priority score | Code | Must be explainable field by field |
| Rationale line | Code template from evidence only | Must tie to evidence; a template guarantees that |
| Reply draft | LLM (template in fallback) | Generative; a human approves it anyway |
| KPI computation + export | Code | Numbers must be reproducible |
| GEO mention / owned citation / competitors / look-alikes | Code | String and domain matching |
| GEO wrong-claim detection | Code only (BC-5 category rules) | BC-5 categories (carrier, travel…) are enumerable |
| Gap scoring | Code | Formula |
| Content brief | LLM (template fallback) | Generative |
| Claim validator | Code | Must block; can't trust the generator |

---

## 4. Pydantic schemas (summary)

Common enums: `Channel = form_fill | email_reply | linkedin_dm | other`; `Source = event-email | paid | historical-reactivation | new-connection | warm-network | organic/referral`; `Status` = the 7 from QLS §5; `Intent` = the 10 from the brief; `Region = benelux | nordics | uk | dach | singapore_apac | us | israel | other`; `Tri = pass | fail | unknown`.

- **InboundMessage**: `id: str`, `origin: seed|ui`, `channel: Channel`, `source: Source | None` (None = not recorded), `received_at: AwareDatetime`, `from_name: str|None`, `from_email: str|None`, `linkedin_url: str|None`, `subject: str|None`, `body: str`. Validators: at least one of email/LinkedIn; email syntactically valid with a dotted domain; LinkedIn must be `linkedin.com/in/<slug>`; body non-empty after strip; naive datetime rejected. Derived (NormalizedInbound): `email_norm`, `linkedin_norm`, `email_domain`, `is_free_domain: bool`, `company_domain_norm: str|None`, `received_at_il`, `body_sha256`.
- **CrmContact**: `record_id`, `first_name`, `last_name`, `email_norm: str|None`, `job_title: str|None`, `linkedin_norm: str|None`, `company_name: str|None`, `company_domain_norm: str|None`, `country_code: str|None` (ISO-2), `region: Region|None`, `vertical: str|None` (slug), `employees: int|None`, `lifecycle_stage: str|None`, `lead_status: str|None`, `is_customer: bool`, `open_deal_id: str|None`, `open_deal_created: date|None`, `owner: str|None`, `last_activity_date: date|None`.
- **AgentAOutput**: `language: str` (ISO 639-1), `intent: Intent`, `buyer_role: str|None`, `data_problem: str|None`, `problem_category: rate_quoting|document_extraction|invoice_reconciliation|trade_document_checking|other|none`, `company_facts: StatedFacts{company_name, employees: int|None, country: str|None, vertical: str|None}` (all "stated"), `timing: str|None`, `instruction_attempt: bool` (layer 2), `evidence: list[Evidence{field: str, quote: str (≤200), translation: str|None}]` (max 6). Extra fields forbidden.
- **QLCondition**: `status: Tri`, `evidence: list[str]`, `source: crm|message|sales_decision|none`, `verified: bool`, `reason: str`.
- **QLChecklist**: `c1_company_fit`, `c2_relevant_buyer`, `c3_data_problem`, `c4_expressed_interest`, `c5_sales_acceptance: QLCondition`; computed `all_pass`, `c1_to_c4_pass`, `failing: list[str]`.
- **AgentBOutput**: `score: int|None` (0–100; None when not scored), `band: A|B|nurture|None`, `breakdown: list[ScoreFactor{name, points: int, max: int, basis: str, unknown: bool}]`, `status: Status`, `exclusion_reason: str|None`, `checklist: QLChecklist`, `owner: str|None`, `rationale: str` (≤200), `reply_draft: str|None`, `draft_requires_human_approval: Literal[True]`, `mode: llm|rules_only`, `analysis_error: str|None`.
- **SalesDecision**: `id`, `origin: seed|ui`, `contact_email_norm`, `person_id: str|None`, `decision: accepted|rejected`, `decided_by: str`, `decided_at: AwareDatetime`, `note: str|None`.
- **PipelineEvent**: `id`, `type: meeting_booked|meeting_held|opportunity_created`, `contact_email_norm`, `person_id: str|None`, `occurred_at: AwareDatetime`.
- **KpiPack**: `week_start: date`, `week_end: date`, `tz: str`, `generated_at`, `mode`, `metrics: list[KpiMetric{key, actual: int|None, target: int|None, record_ids: list[str]}]`, `by_source: list[SourceRow{source: Source|"not_recorded", count: int|None, feed_status, person_ids, record_ids}]`, `expansion: ExpansionLine{accepted: list[str], meetings_booked: list[str], meetings_held: list[str], opportunities: list[str]}`, `excluded: list[ExcludedRecord{record_id, reason}]`, `caveats: list[str]`.
- **GeoFinding**: `answer_id`, `prompt_id`, `engine`, `priority: int`, `cluster`, `stargo_mentioned: bool`, `owned_citation: bool`, `owned_urls`, `lookalike_hits: list[str]`, `competitors: list[str]` (canonical), `other_vendors: list[str]`, `wrong_claims: list[WrongClaim{text, contradicts: str (BC id)}]`, `state: owned|mentioned_unowned|absent|wrong`.
- **GapScore**: `prompt_id`, `per_engine: dict[engine, state]`, `fit: float`, `score: float`, `rank: int`, `explanation: str`.
- **ContentBrief**: `prompt_id`, `title`, `direct_answer` (40–60 words), `sections: list[Section{heading, paragraphs: list[Claimed{text, refs: list[str]}]}]` (3–5), `faq: list[FAQ{question, answer: list[Claimed]}]` (3–5), `schema_org_type: str`, `mode: llm|template`, `flags: list[ValidatorFlag{location, rule, severity: block|warn, text}]`, `publishable: bool`.

---

## 5. Proposed priority score (0–100)

The score is computed only when status ∈ {QL candidate, QL, nurture}. It is `None` for excluded, suppressed, disqualified and needs review: the gate decides first, so the score can never promote a lead. An unknown input scores 0 points and is labelled "unknown", not "fail".

| Factor | Max | Points |
|---|---|---|
| Interest (C4 strength) | 30 | demo / pricing / pilot explicit 30 · call / meeting 22 · soft positive ("happy to chat") 10 · none 0 |
| Problem fit (C3) | 25 | maps to a BC-3 product AND a stated volume or time cost 25 · maps, no volume 18 · related but not a listed pain 6 · none 0 |
| Buyer (C2) | 20 | C-level / VP / Director / Head / Owner-founder <200 20 · Manager 14 · below manager 4 · unknown 0 |
| Company fit (C1) | 15 | ICP vertical 6 + ICP region 5 + 20+ employees 4; unverified facts get half points |
| Timing | 10 | explicit near-term ("this week", "next week", "this quarter") 10 · vague 4 · none 0 |

Bands: ≥70 A, 40–69 B, <40 nurture (labels only; status comes from the gate). The UI shows each row of the breakdown with its basis (evidence quote or CRM field).

## 6. Proposed GEO gap formula

For each answer (prompt × engine), the state contributes `g`:
- `owned` (Stargo mentioned AND cited from an owned domain) = 0
- `mentioned_unowned` (mentioned but cited from no domain or a look-alike) = 0.5
- `absent` = 1
- `wrong` (a claim about "Stargo" that contradicts BC, e.g. carrier or travel) = 1.5

`gap(p) = priority_p × Σ_engines g × fit_p`. Tie-break: number of distinct competitors in the answers.

`fit_p` = 1 if the prompt's need maps to a BC-3 product, 0 if Stargo has no product for it. A gap you cannot fill with approved claims isn't a content gap.

**Justification:**
- Priority is the business weight the team already assigned.
- Summing over engines rewards breadth: missing on 3 of 3 is worse than 1 of 3.
- A wrong claim is worse than silence because it actively mis-sells.
- An unowned mention is half a win, because we don't control the source.
- Fit stops the brief generator from inventing a product (BC-5).

Brand-accuracy risks (look-alikes, wrong claims) also go in a separate **risk table**, so they aren't buried by low priority.

Applied to the data:

| Prompt | Pri | CHA | PER | GEM | Σg | fit | gap |
|---|---|---|---|---|---|---|---|
| P6 alternatives to Laneframe (pricing) | 3 | absent | absent | absent | 3 | 1 (BC-3a) | **9** |
| P2 BoL extraction | 3 | absent | mentioned_unowned (stargo-shipping.com look-alike) | absent | 2.5 | 1 (BC-3b) | 7.5 |
| P1 spot quoting from email | 3 | absent | owned | absent | 2 | 1 | 6 |
| P3 invoice reconciliation | 2 | absent | absent | absent | 3 | 1 (BC-3c) | 6 |
| P4 trade finance doc checking | 2 | absent | owned | absent | 2 | 1 (BC-3d) | 4 |
| P5 Stargo reviews (brand) | 1 | wrong (holiday app, stargo-travel look-alike) | owned | wrong (ocean carrier, no citation) | 3 | 1 | 3 |
| P7 AWB digitization | 1 | absent | absent | owned | 2 | 1 (BC-3b, PP-3) | 2 |
| P8 rate benchmarking for shippers | 2 | absent | absent | absent | 3 | 0 (no BC product) | 0 |

The top gap is P6. It's a competitive prompt, so BC-5 applies: "Laneframe" may appear only in the title and the FAQ question, and the answer is about Stargo (BC-3a, PP-1). P1 and P3 tie at 6; the competitor tie-break puts P1 first (3 competitors vs 2).

Competitor canonicalization: "Laneframe Docs" and "Laneframe Market Data" → Laneframe; "QuoteHarbor Audit" → QuoteHarbor; "DocuFreight Finance" → DocuFreight. "ClearDoc Trade" (P4-CHA) isn't in `known_competitors` → `other_vendors`.

Owned check: normalized host == `stargo.co` or ends with `.stargo.co`. Never "contains stargo".

---

## 7. Walk-through of every seed record

**Window:** [Sun 2026-10-04 00:00, Fri 2026-10-09 00:00) IL. Israel is on IDT (UTC+3) for every date in the data; DST ends Sun 25 Oct 2026 (verified with zoneinfo). So `+03:00` stamps are already IL, and `Z` stamps get +3 h.

**Normalization used:**
- email: trim + lowercase
- LinkedIn: lowercase, drop scheme, `www.`, trailing `/`, query → `linkedin.com/in/<slug>`
- country: `Netherlands`→NL, `United Kingdom`→UK

### 7a. Inbound (21)

| Id | Received (raw → IL) | In week? | Identity | Key facts | Status | Owner |
|---|---|---|---|---|---|---|
| IN-001 | 10-04 09:12+03 → Sun 09:12 | yes | email → HS-1001 Anouk (P-Anouk) | NL forwarder 850; Head of Pricing; ~400 spot rate requests/wk, 3–4 h each (rate quoting); demo request; next week | **QL** (C5 = SD-002) | Dana |
| IN-002 | 10-02 16:40+03 → **Fri** 16:40 | no (Fri, queued) | email → HS-1004 Pieter | BE carrier 2200; Commercial Director; re-keys ~1,500 docs/mo into TMS (doc extraction); asks for a call | **QL** (C5 = SD-001) | Dana |
| IN-003 | 10-05 11:20**Z** → Mon 14:20 | yes | LinkedIn `linkedin.com/in/pieterclaes-bcl` (trailing `/` + `www.` stripped) → HS-1004 → same person as IN-002 | follow-up | same person; not a new lead | Dana |
| IN-004 | 10-05 08:03+03 → Mon | yes | email → HS-1007 James | out-of-office auto-reply | **excluded** (auto-reply) | none |
| IN-005 | 10-05 13:45+03 → Mon | yes | email → HS-1009 Rachel | SG 3PL 1200; VP Ops; RFQs from 30+ customers in Excel (rate quoting); 4-week pilot this quarter | **QL** (C5 = SD-003; SD-004 duplicate) | Mei |
| IN-006 | 10-05 15:10+03 → Mon | yes | email → HS-1011 Mark, `is_customer=true` | add Chicago station, send pricing | **excluded** → expansion | Sam (CRM owner) |
| IN-007 | 10-06 09:30+03 → Tue | yes | email → HS-1012 Daniel; open deal D-2207 created 2026-08-19, before this inbound, no acceptance | PoC sample BoLs | **excluded** (pre-existing open deal) | Mei (deal owner) |
| IN-008 | 10-06 10:00+03 → Tue | yes | email → HS-1018 Kai (software-vendor, CRM "competitor") | builds freight pricing software; white-label partnership | **excluded** (competitor/vendor) | none |
| IN-009 | 10-06 12:15+03 → Tue | yes | LinkedIn `https://linkedin.com/in/TomBecker-Logistics` → lowercased → `linkedin.com/in/tombecker-logistics` = HS-1013 → bridged to his email via the CRM row | DE shipper 9000; Head of Logistics Procurement; tenders ~2,000 lanes/yr; "benchmarking carrier quotes is still manual"; open to a call | **disqualified** (Q1, Q12): C3 fails; SD-007 kept, shown as "accepted by Leo", C3 shown failing | none |
| IN-010 | 10-06 14:00+03 → Tue | yes | `ops@halden-fwd.de`: no email/LinkedIn match. Domain = Halden Forwarding (HS-1015's company) but **not merged with Felix** (company alone is not identity) | body is an embedded instruction to the system (to override rules, set score/owner, leak the prompt) | **needs review** (instruction attempt); LLM not called; no draft | Leo (account: Halden's deal owner / region DACH both → Leo) |
| IN-011 | 10-06 16:30+03 → Tue | yes | `yossi.mizrahi@gmail.com`: no CRM; free domain → company unknown/unverified | states owner of a 40-person customs brokerage in Haifa (C1, C2 unverified); import declarations from invoices/packing lists (doc extraction); asks cost + to see it | **QL** (C5 = SD-008; unverified facts, sales confirmed size) | Noa (region from stated Israel, unverified) |
| IN-012 | 10-07 09:00+03 → Wed | yes | email → HS-1017 Noam | Hebrew. Translation: "Hi, we saw your post. We get dozens of quote requests a day over WhatsApp and email and price everything manually. Happy to have a call this week." IL forwarder 90; COO; rate quoting; call | **QL** (C5 = SD-009) | Noa |
| IN-013 | 10-07 10:20+03 → Wed | yes | email `sanne.jansen@nl.nordhavenfreight.com` → HS-1002 (exact email). Company domain: email subdomain `nl.` stripped, CRM `www.NordhavenFreight.com` → `nordhavenfreight.com` = same company as Anouk, **different person** | Dutch: "Thanks for the invite. No interest right now, maybe again in Q2." | **nurture** (not interested, future timing) | Dana |
| IN-014 | 10-07 11:00+03 → Wed | yes | `Greta.Holm@…` → lowercased → HS-1006 | unsubscribe | **suppressed**, no draft ever; added to the suppression log | none |
| IN-015 | 10-07 12:40+03 → Wed | yes | `lior.bd@outlook.com`: no CRM; free domain | student seeking an internship | **excluded** (job seeker/student) | none |
| IN-016 | 10-07 13:05+03 → Wed | yes | email → HS-1019 Hannah (investor) | asks about the funding round | **excluded** (investor) | Founders |
| IN-017 | 10-08 20:30**Z** → **Thu 23:30** | **yes** (inside by 29 min) | email → HS-1016 Priya | US shipper 20000; Director of Transportation; carrier invoice reconciliation; "show us how" | **QL**, but its acceptance SD-010 is 10-11 (next week) | Sam |
| IN-018 | 10-08 21:30**Z** → **Fri 10-09 00:30** | **no** (UTC date says Thu; IL is Fri) | email → HS-1008 Marcus | UK trucking 400; Pricing Manager; rate cards in ~40 spreadsheets (rate quoting); demo | **QL candidate** (no decision), queued | Leo |
| IN-019 | 10-04 18:00+03 → Sun | n/a | `asdf@asdf` (no dotted domain), empty subject and body | junk | **rejected at ingest**: "invalid email; empty message". Stored in ingest_errors, not a lead | — |
| IN-020 | 10-05 09:00+03 → Mon | yes | email → HS-1005 Wim | BE carrier; Customer Service **Team Lead** (below manager → C2 fail); manual booking entry; "happy to chat if useful" | **disqualified** (C2 fails; SD-006 rejected) | none |
| IN-021 | 10-05 12:00+03 → Mon | yes | `Anouk.DeVries@NordhavenFreight.com` → lowercased → HS-1001 = same person as IN-001 | repeat demo request, source `paid` | same person; source stays **event-email** (earliest = IN-001) | Dana |

### 7b. Sales decisions (11)

| Id | Person (match) | decided_at IL | In week? | Effect |
|---|---|---|---|---|
| SD-001 | Pieter (email) | Sun 10-04 10:05 | yes | QL ✔ (C1–C4 pass) |
| SD-002 | Anouk | Mon 10-05 09:40 | yes | QL ✔ |
| SD-003 | Rachel | Tue 10-06 08:15 | yes | QL ✔ |
| SD-004 | Rachel (`Rachel.Lim@` → lowercased) | Tue 10-06 08:16 | yes | duplicate: same person, counted once |
| SD-005 | Mark (customer) | Tue 10-06 11:00 | yes | expansion line, not an acquisition QL |
| SD-006 | Wim | Tue 10-06 12:00 | yes | rejected → no QL. The note mentions Pieter; no merge |
| SD-007 | Tom (email = HS-1013) | Wed 10-07 09:00 | yes | not QL: C3 fails (Q1); decision kept, failing condition shown |
| SD-008 | Yossi | Wed 10-07 15:00 | yes | QL ✔ (unverified facts, human-checked) |
| SD-009 | Noam | Wed 10-07 16:20 | yes | QL ✔ |
| SD-010 | Priya | **Sun 10-11** 09:00 | **no** (next week) | QL in week of 10-11 |
| SD-011 | Felix | Thu 09-24 12:00 | no | earlier week; CRM contact only, no lead status (Q3) |

### 7c. Pipeline events (12)

| Id | Type | Person | occurred IL | In week? | Counted as |
|---|---|---|---|---|---|
| PE-001 | booked | Felix | Mon 09-28 10:00 | no | — |
| PE-002 | held | Felix | Sun 10-04 11:00 | yes | acquisition held (deal D-2231 is after acceptance SD-011 → acquisition) |
| PE-003 | booked | Pieter | Sun 10-04 10:30 | yes | acquisition booked |
| PE-004 | booked | Anouk | Mon 10-05 10:00 | yes | acquisition booked |
| PE-005 | held | Pieter | Tue 10-06 14:00 | yes | acquisition held |
| PE-006 | booked | Mark | Wed 10-07 09:30 | yes | **expansion** booked |
| PE-007 | booked | Rachel | 10-07 05:00**Z** → Wed 08:00 | yes | acquisition booked |
| PE-008 | held | Anouk | Wed 10-07 15:00 | yes | acquisition held |
| PE-009 | opp | Felix | Wed 10-07 17:00 | yes | acquisition opportunity |
| PE-010 | booked | Tom | Thu 10-08 11:00 | yes | acquisition booked (not a customer or pre-existing deal; meetings aren't gated on QL; see Q2) |
| PE-011 | opp | Pieter | Thu 10-08 15:00 | yes | acquisition opportunity |
| PE-012 | booked | Noam | **Fri 10-09** 10:00 | **no** | — |

### 7d. CRM rows (19)

| Row | Normalization notes | Role in pipeline |
|---|---|---|
| HS-1001 Anouk | — | lead; QL |
| HS-1002 Sanne | domain `www.NordhavenFreight.com`→`nordhavenfreight.com`; `Netherlands`→NL; `Freight Forwarder`→`freight-forwarder`; employees blank on the row → 850 "from CRM company record" (HS-1001, same normalized domain) (Q5) | nurture |
| HS-1003 Erik | — | researched-only (no inbound, no decision) → not a lead, not counted |
| HS-1004 Pieter | — | QL (two inbound, one person) |
| HS-1005 Wim | last activity 2025-11 | disqualified |
| HS-1006 Greta | — | suppressed |
| HS-1007 James | — | excluded (auto-reply); not suppressed: they may reply after 12 Oct |
| HS-1008 Marcus | `United Kingdom`→UK; `Meridian Haulage Ltd` = same domain as HS-1007 | QL candidate (Friday inbound) |
| HS-1009 Rachel | — | QL |
| HS-1010 Sofia | — | researched-only |
| HS-1011 Mark | customer | expansion |
| HS-1012 Daniel | open deal D-2207 2026-08-19 | excluded: pre-existing deal, owner Mei |
| HS-1013 Tom | LinkedIn bridges IN-009 to SD-007 | accepted, not QL (C3 fails) |
| HS-1014 Lukas | lifecycle `salesqualifiedlead`, status "QL (imported 2026-08)" | researched-only; **CRM "QL" ignored** |
| HS-1015 Felix | open deal D-2231 2026-10-07, after SD-011 (09-24) → acquisition opp | no inbound in export → **not in the lead queue, no lead status**. Shown as a CRM contact "accepted 2026-09-24 (earlier week)". PE-002 + PE-009 count as acquisition (Q3) |
| HS-1016 Priya | — | QL, next week's count |
| HS-1017 Noam | — | QL |
| HS-1018 Kai | `other`/`competitor` | excluded |
| HS-1019 Hannah | investor | excluded, Founders |

People not in the CRM: Yossi (IN-011), Lior (IN-015), the `ops@halden-fwd.de` sender (IN-010). Rejected record: IN-019.

---

## 8. KPI pack for Sun 4 – Thu 8 Oct 2026 (derived from §7)

| KPI | Actual | Target | Gap | Records |
|---|---|---|---|---|
| QLs (acquisition) | **5** | 25 | −20 | Pieter SD-001, Anouk SD-002, Rachel SD-003(+SD-004 dup), Yossi SD-008, Noam SD-009 |
| Meetings booked | **4** | 15 | −11 | PE-003, PE-004, PE-007, PE-010 |
| Meetings held | **3** | 12 | −9 | PE-002, PE-005, PE-008 |
| Opportunities created | **2** | 5 | −3 | PE-009, PE-011 |
| Expansion (separate line) | 1 acceptance, 1 meeting booked | — | — | SD-005, PE-006 (Mark, Tidewater) |

**QLs by first-touch source:**

| Source | Count | Basis |
|---|---|---|
| event-email | 2 | Pieter (earliest IN-002, Fri 10-02, *not* IN-003 new-connection), Anouk (earliest IN-001, *not* IN-021 paid) |
| paid | 1 | Rachel (IN-005) |
| organic/referral | 1 | Yossi (IN-011) |
| warm-network | 1 | Noam (IN-012) |
| new-connection | 0 | Tom (IN-009) is not a QL (Q1) |
| historical-reactivation | **unknown** | feed_status = not_received |
| source not recorded | 0 | — |

**Excluded from this week, with reason:**
- SD-010 Priya: decided 10-11.
- SD-011 Felix: decided 09-24.
- SD-006 Wim: rejected.
- SD-007 Tom: accepted, fails C3 (Q1).
- SD-005 Mark: expansion.
- PE-001: 09-28.
- PE-012: Fri 10-09.
- PE-006: expansion.
- Lukas: CRM "QL" is not evidence.
- Marcus: queued QL candidate.

**Caveat for the pack:** totals are a lower bound for any channel fed by the missing historical-reactivation feed.

---


## 9. Decisions (yours)

These go into `docs/ASSUMPTIONS.md` at the start of Phase 0, in your words.

| # | Decision |
|---|---|
| Q1 | Tom fails C3. Benchmarking is not a listed pain and BC-3 has no product for it. Accepted but not QL, C3 shown failing. QL = 5. |
| Q2 | Pipeline events count by their own date for any person who isn't a customer or a pre-existing deal. Booked = 4. |
| Q3 | Felix gets no lead status. `needs review` is only for a failed analysis or an instruction attempt (QLS §5), and Felix has no inbound in the data. He is not in the lead queue. He appears as a CRM contact "accepted 2026-09-24 (earlier week)". PE-002 and PE-009 count as acquisition (deal created after acceptance). |
| Q4 | No owner for excluded/suppressed, except investor → Founders. Keep a suppression log. |
| Q5 | Sanne = nurture. Company facts may come from the CRM company record via the normalized domain, labelled "from CRM company record". Sources are never inherited. |
| Q6 | Recorded Agent A fixtures for the 21 seed inbound: captured once from the real LLM, committed, labelled "recorded fixture", with a script to regenerate them. Rules-only for pasted messages when there is no key. |
| Q7 | Half-open window [Sun 00:00, Fri 00:00) IL. |
| Q8 | Latest decision wins, with visible history. |
| Q9 | Wim fails C2 → disqualified. |
| Q10 | Brief for P6 under BC-5. |
| Q11 | Groq. |
| Add. | Senders not in the CRM: region from the stated country (marked unverified); no country → Triage queue. Test with a pasted message from an unknown person at an unknown company. |
| Simpl. | Rationale = code template from evidence only. GEO wrong-claim detection = code only. Table-driven tests, no property-style tests. Target ~16–18 h. |
| Q12 | An accepted lead that fails C1–C4 → `disqualified`, no owner (literal QLS §5). The decision stays visible as "accepted by <rep>" with the failing condition shown; its pipeline events stay on record. (Tom: accepted by Leo, C3 fails, PE-010 still counts per Q2.) |

---

## 10. Phased build order (STOP after each phase)

| Phase | Scope | Est. |
|---|---|---|
| 0 | Tooling: pyproject (FastAPI, Pydantic v2, pytest, ruff, mypy), Vite+TS skeleton, `.env.example`, PII-safe logging, offline test fixture; write ASSUMPTIONS.md | 0.75 h |
| 1 | ingest/: schemas, validation, normalization, identity/person graph, company-record facts, loader + ingest_errors | 2.5 h |
| 2 | storage/: SQLite repository, idempotent seeding, restart test | 1 h |
| 3 | rules/: injection detector, exclusions, QL checklist, status, routing (incl. unknown senders), score, rationale template | 2.5 h |
| 4 | kpi/: window, computation, sources/feed status, KPI_PACK.md export; golden test = §8 numbers | 2 h |
| 5 | agents/: Groq client (timeout, one retry, endpoint allowlist), Agent A prompt + schema + quote check, rules-only fallback, recorded fixtures + regen script, Agent B assembly + draft; failure-path tests | 2.75 h |
| 6 | api/: thin FastAPI routes (leads, detail, paste, decide, kpi, geo, mode, suppression log) | 1 h |
| 7 | geo/: findings, gap formula, risk table, brief (LLM + template), claim validator | 2 h |
| 8 | frontend/: queue, detail, decide, paste, KPI with drill-down, AI visibility, mode banner, 390 px; vitest | 2.5 h |
| 9 | Hardening: independent review agent, clean-clone no-key run, chaos tests, README draft (you write PROCESS.md + CRO note) | 1 h |
| | **Total** | **~18 h** |

**Cut first if short on time, in order:**
1. LLM-generated brief (keep template brief + validator).
2. AI visibility UI view (keep the API + a section in KPI_PACK.md).
3. KPI drill-down in the UI (keep record ids in the API + md).
4. The bonus items: never started.

Never cut: the QL gate, identity, the window, KPI, a failure path, injection handling, PII-free logs, no-key mode.

## Verification (for this planning step)
- After approval: `docs/PLAN.md` exists and is byte-identical to this file. `git status` shows only `docs/PLAN.md` as new. No other files are touched.
- You compare §7–§8 to your hand count. Any mismatch is resolved from the records before Phase 0.
- Decisions in §9 get logged in `docs/ASSUMPTIONS.md` at the start of Phase 0.
