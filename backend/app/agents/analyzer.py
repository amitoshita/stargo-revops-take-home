"""Choose how one inbound message is analysed and always return a MessageAnalysis.

Order:
1. Layer-1 injection detection (code). A hit stops here: no LLM call, needs review.
2. A recorded fixture for a seed message (matching message hash).
3. The live LLM, when a key is configured.
4. The rules-only fallback.
Any failure in 2–4 is returned as an AnalysisFailure, which the rules turn into needs review.
"""

from __future__ import annotations

import logging

from app.agents import fallback
from app.agents.agent_a import parse_output, run_agent_a
from app.agents.fixtures import FixtureStore
from app.agents.llm_client import LLMClient
from app.agents.schemas import AgentAOutput, AnalysisFailure, MessageAnalysis
from app.core.enums import AnalysisMode
from app.ingest.schemas import InboundMessage
from app.rules.injection import detect_instruction_attempt

log = logging.getLogger(__name__)


def _result(
    message: InboundMessage, mode: AnalysisMode, outcome: AgentAOutput | AnalysisFailure
) -> MessageAnalysis:
    failure = outcome if isinstance(outcome, AnalysisFailure) else None
    extraction = outcome if isinstance(outcome, AgentAOutput) else None
    log.info(
        "agent_a ref=%s mode=%s outcome=%s",
        message.id, mode.value, failure.kind if failure else "ok",
    )  # fmt: skip
    return MessageAnalysis(inbound_id=message.id, mode=mode, extraction=extraction, failure=failure)


def analyze_message(
    message: InboundMessage,
    *,
    client: LLMClient | None,
    fixtures: FixtureStore | None,
) -> MessageAnalysis:
    signals = detect_instruction_attempt(message.from_name, message.subject, message.body)
    if signals:
        log.info("agent_a ref=%s injection_signals=%s", message.id, ",".join(signals))
        mode = AnalysisMode.LLM if client else AnalysisMode.RULES_ONLY
        return MessageAnalysis(
            inbound_id=message.id,
            mode=mode,
            extraction=None,
            failure=None,
            injection_signals=signals,
        )

    if fixtures is not None and message.origin == "seed":
        recorded = fixtures.get(message.id, message.subject, message.body)
        if recorded is not None:
            outcome: AgentAOutput | AnalysisFailure
            if recorded.raw is None:
                outcome = AnalysisFailure(
                    kind="model_error", detail=f"recorded call failed: {recorded.error}"
                )
            else:
                outcome = parse_output(recorded.raw, message.subject, message.body)
            return _result(message, AnalysisMode.RECORDED_FIXTURE, outcome)

    if client is not None:
        outcome, _ = run_agent_a(
            client,
            ref=message.id,
            subject=message.subject,
            body=message.body,
            channel=message.channel.value,
        )
        return _result(message, AnalysisMode.LLM, outcome)

    return _result(
        message, AnalysisMode.RULES_ONLY, fallback.extract(message.subject, message.body)
    )
