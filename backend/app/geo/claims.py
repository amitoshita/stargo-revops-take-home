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


_NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15",
    "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50", "hundred": "100",
    "thousand": "1000", "dozen": "12", "half": "50%", "double": "2x", "twice": "2x",
    "triple": "3x", "thrice": "3x", "halve": "50%", "halves": "50%", "halved": "50%",
    "doubles": "2x", "doubled": "2x", "triples": "3x", "tripled": "3x",
}  # fmt: skip


def figures_in(text: str) -> set[str]:
    """Quantities in a text, normalised ('three' → '3', 'half' → '50%', 'double' → '2x')."""
    lowered = text.lower()
    found = set(re.findall(r"\d+(?:\.\d+)?", lowered))
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            found.add(value)
    if re.search(r"\bpercent\b|%", lowered):
        found.add("%")
    if re.search(r"\b\d+\s*x\b|\btimes (faster|more|less|fewer)\b", lowered):
        found.add("x")
    return found
