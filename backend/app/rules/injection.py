"""Layer 1 prompt-injection detection: deterministic patterns, checked before any LLM call.

Only pattern names are returned and logged, never the matched text.
"""

from __future__ import annotations

import re

_PATTERNS: dict[str, re.Pattern[str]] = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in {
        "ignore_instructions": (
            r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}"
            r"\b(previous|prior|above|earlier|all|your|the)\b[^.\n]{0,20}"
            r"\b(instructions?|rules?|prompts?|guidelines?|directions?)\b"
        ),
        "system_note": r"\b(system|developer|admin)\s*(note|prompt|message|override|instruction)",
        "addresses_ai": r"\b(to|dear|hey|attention)\s+(the\s+)?(ai|assistant|bot|llm|model)\b",
        "role_play": r"\b(you are now|act as|pretend to be|from now on you)\b",
        "prompt_exfiltration": (
            r"\b(reveal|print|show|include|output|repeat|leak)\b[^.\n]{0,30}"
            r"\b(system\s+prompt|prompt|instructions)\b"
        ),
        "set_status": (
            r"\b(mark|set|classify|label|flag)\b[^.\n]{0,30}\b(as\s+)?"
            r"(qualified|ql|hot|priority|a-?lead|approved)\b"
        ),
        "set_score": r"\b(score|priority)\s+(of|to|=|:)\s*\d{1,3}\b",
        "set_owner": r"\broute\s+(it|this|me|the\s+lead)?\s*to\b",
        "jailbreak": r"\b(jailbreak|developer mode|dan mode|new instructions)\b",
        # Non-English variants of "ignore previous instructions".
        "ignore_nl": r"\bnegeer\b[^.\n]{0,30}\b(instructies|regels)\b",
        "ignore_de": r"\bignorier\w*\b[^.\n]{0,30}\b(anweisungen|regeln)\b",
        "ignore_he": r"התעלם[^.\n]{0,30}(הוראות|כללים|הנחיות)",
        "ignore_fr": r"\bignore[rz]?\b[^.\n]{0,30}\b(instructions|consignes|règles)\b",
    }.items()
}


def detect_instruction_attempt(*texts: str | None) -> list[str]:
    """Names of matched patterns across the given texts (subject, body). Empty = clean."""
    combined = "\n".join(t for t in texts if t)
    return sorted(name for name, pattern in _PATTERNS.items() if pattern.search(combined))
