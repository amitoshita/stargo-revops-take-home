# PROCESS.md

This is how I worked on this assignment with AI tools: what I planned, what I let the agent do, where I stopped it, and how I checked what it built.

## Tools I used

- **Claude Code** in my repo, as the coding agent. First Plan Mode, then auto mode with checkpoints where it had to stop and show me results.
- **A separate Claude chat**, as a second opinion. I used it to understand the brief, review the agent's plans and reports, help me write some of my prompts, and draft the held-out test messages. I kept it separate on purpose, so I had a reviewer that never saw the code being written.
- **Groq** (`openai/gpt-oss-120b`) as the LLM inside the app.

## Planning

Before I opened Claude Code, I read `ql_standard.md` and `brand_context.md` myself and counted the KPI pack for 4–8 Oct by hand. I got 5 QLs (6 if Tom Becker passes C3), 4 meetings booked, 3 held, 2 opportunities, and historical-reactivation as unknown. I wanted my own answer key before the agent gave me one.

Then I wrote the project rules in `CLAUDE.md`. The main ones: keep the layers separate, validate every agent output with Pydantic, Agent B never sees the raw message, a failed analysis is always `needs review`, no PII in logs, tests run offline, and stop after every phase.

In Plan Mode I asked for a full `docs/PLAN.md`: every requirement mapped to a test, which parts are code and which are LLM, the schemas, the scoring formulas, a walk-through of every seed record, and a list of open questions for me.

One problem came up right away. The agent had read my notes, which included my hand-counted numbers. If it just copied them, comparing its plan to my count would prove nothing. So I told it:

> "Important: you saw expected KPI numbers in STARGO_PLAYBOOK.md. Ignore them completely. Derive everything independently from the spec and the data files in this repo, showing your reasoning per record, so I can compare your result with my own hand count."

Its numbers matched mine, and every one came with the records behind it.

## Decisions I made

The plan had 12 open questions, and the agent asked 4 more before running on its own. I answered all of them, and they are in `docs/ASSUMPTIONS.md`. In most cases I took the recommendation. These are the ones where I disagreed or changed it:

- **Felix Wagner.** The plan wanted to mark him `needs review`. I said no. QLS §5 uses `needs review` only for a failed analysis or a message that tries to instruct the system, and Felix has no inbound message at all. He is not a lead. His meetings and opportunity still count as acquisition.
- **People who aren't in the CRM.** The plan had no routing for them. I added: take the region from the country they state (marked unverified), and if there is none, send them to the Triage queue.
- **Scope.** I cut the LLM-written rationale, the LLM check for wrong claims and the property-based tests. The estimate went from about 25 hours to about 18.
- **Tom Becker, accepted by sales but failing C3.** At first I chose `disqualified`. Then I noticed that this made an accepted lead look *worse* than an unaccepted lead with the same problem, which makes no sense. So I made one rule for both: fail C1 or C2 → disqualified; fail C3 or C4 → nurture with an owner. Tom is nurture under Leo. He still shows "accepted by Leo", and he is not a QL.
- **Partnership messages.** The agent wanted to exclude all of them. I changed it to exclude based on *who* is writing (a competitor or vendor), not on the word "partnership".
- **Several messages from the same person.** I agreed to combine evidence from all of them, but interest follows the *latest* message. If someone asked for a demo and later wrote "we went with another vendor", they are not interested anymore.
- **Regions outside the ICP.** The agent's rule meant that the "outside ICP → Triage queue" row in QLS §5 could never happen. I changed it: if C1 fails only because of the region, the lead is nurture in the Triage queue.

## Where I let the agent run

Once the plan was approved, I let it build all the phases in auto mode, with two stops:

> "Mandatory checkpoints (STOP and show me): 1. After Phase 4 (KPI): show the golden test output and the generated KPI_PACK.md numbers next to §8 of the plan. 2. Before Phase 5 recorded fixtures: stop and tell me to put my Groq key in .env (I will create the file myself, never ask me to paste the key)."

I let it do the boilerplate, storage, API, UI and tests. I kept for myself the rule decisions, checking the KPI against my count, the eval labels, manual testing, the CRO note and this file.

## How I checked its work

**The eval labels.** At the first checkpoint I saw that the golden test was using labels the agent had written itself (`seed_labels.py`). It was also going to grade the LLM against those same labels. So I went through all 19 against the original messages and fixed four. The important one: Yossi's country was "Haifa", and that would have broken routing to Israel. After that, the agent enforced "a country, not a city" in the schema, not only in the prompt.

**The right number for the wrong reasons.** After recording real Groq answers, the KPI was still 5, which looked fine. But the eval showed these were **five different people**. The model counted Tom (it read "benchmarking carrier quotes" as rate quoting) and dropped Yossi (it didn't read "I own a 40-person brokerage" as Owner). The two mistakes cancelled out. I fixed the prompt only with definitions that are already in the spec (QLS C2 says owner/founder, and BC-3a describes quoting for your own customers). I also added a test that pins the exact QL records, not just the count.

**A held-out set.** If you keep fixing a prompt until it passes the same 19 messages, you can't tell whether it learned the rules or just these cases. So I had the separate chat draft six new messages, checked the expected answers myself, and told the agent to run them only once, after the prompt was frozen, and not to tune on them. The model got 10 of 11 extraction fields right. The one miss was a retailer comparing carrier quotes, labelled as rate quoting. That showed my Tom fix didn't carry over to a new message, so I documented it as the main known weakness instead of tuning again. The same run found a real bug (retailers weren't mapped to "shipper"), and it found mistakes in **my own** expected answers: I had assumed routing by email domain, which goes against my own rule. The eval doc shows both scores.

**An independent reviewer.** At the end I ran a fresh agent session that hadn't written the code and asked it to review the repo against the rubric. It found 11 issues, including holes in the claim validator, a stale draft, form values echoed back in 422 errors and a missing feed counted as 0. All were fixed, each with a test.

**Testing it myself, like a reviewer.** I followed the README from a clean database, first without a key and then with one, and did what the brief says the reviewers will do. These are bugs I found that the 400+ tests didn't:

- **Last week's pack changed after the fact.** Messages and decisions from today showed up in the 4–8 Oct lists. When the agent looked into it, the problem was bigger: rejecting Pieter today would have removed him from October's QLs. Now the pack is built only from what was known before the next week started.
- **A perfect lead got disqualified.** A Hebrew message from an operations manager at an Israeli freight forwarder was disqualified, because the LLM wrote "logistics" and the code didn't know the word, so C1 *failed*. The fix: a value the code doesn't recognise is unknown, never a fail. I also added more ICP synonyms.
- **The reply draft promised too much.** It said the product would "eliminate the manual data entry", and nothing in the brand context supports that. Reply drafts now go through the same claim checks as the brief, and they are written in the lead's language.
- **Hebrew showed left-to-right** in the UI, with the punctuation in the wrong place.
- **A garbage or injected follow-up could remove an accepted QL** from the KPI. I changed the rule: a message that fails or is flagged gets a visible review flag, but it doesn't add or remove any evidence.
- **A LinkedIn-only sender couldn't be accepted**, even though the brief allows a blank email.

## A mistake the agent made

I asked the agent to delete an empty `GROQ_API_KEY=` line in `.env`. It deleted the line with my real key too, and there was no backup. It told me right away and stopped. I created a new key and added a rule to `CLAUDE.md`: never edit `.env` or any file with secrets, just tell me the exact line and I'll change it myself. My takeaway: don't let an agent edit files that can't be restored.

## What I would do differently

- Write the held-out messages **before** the first version of the prompt, so the prompt never sees any labelled examples first.
- Start testing by hand earlier. Most of the real bugs came from pasting messages the system had never seen, not from the test suite.
- Keep a time log while I work, instead of rebuilding it at the end.
