"""The approved claims library, parsed from data/brand_context.md (the only source of claims).

Claim sources are BC-1, BC-2, BC-3a–d and PP-1–3. BC-5, BC-6 and BC-7 are rules about
writing, not facts, so they are not citable.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

CITABLE = re.compile(r"^(BC-1|BC-2|BC-3[a-d]?|PP-[1-3])$")


@lru_cache(maxsize=4)
def load_claims(path: Path) -> dict[str, str]:
    """Return {id: text} for every citable claim in the brand context file."""
    claims: dict[str, str] = {}
    section: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if heading := re.match(r"^## (BC-\d+)\b", line):
            section = heading.group(1)
            continue
        if bullet := re.match(r"^- \*\*((?:BC-\d+[a-z]?|PP-\d+))\s*([^*]*)\*\*\s*(.+)$", line):
            name = bullet.group(2).strip().rstrip(".")
            claims[bullet.group(1)] = (f"{name}. " if name else "") + bullet.group(3).strip()
            continue
        if section in ("BC-1", "BC-2") and line and not line.startswith("#"):
            claims[section] = (claims.get(section, "") + " " + line).strip()
    claims["BC-3"] = " ".join(v for k, v in sorted(claims.items()) if k.startswith("BC-3"))
    return {k: v for k, v in claims.items() if CITABLE.match(k)}


def figures_in(text: str) -> set[str]:
    """Numbers as they appear in a text (e.g. '97', '3', '15'), for figure checks."""
    words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
    found = set(re.findall(r"\d+(?:\.\d+)?", text))
    found |= {words[w] for w in re.findall(r"\b(one|two|three|four|five)\b", text.lower())}
    return found
