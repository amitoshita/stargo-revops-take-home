"""Buyer level and function from a job title (QLS §1 condition 2)."""

from __future__ import annotations

import re
from typing import Literal

Level = Literal["senior", "manager", "owner", "below_manager", "unknown"]

_BELOW_FIRST = re.compile(r"\b(assistant|intern|student|junior|trainee|apprentice)\b")
_OWNER = re.compile(r"\b(owner|founder|co-?founder|proprietor)\b|\bi own\b")
_SENIOR = re.compile(
    r"\b(ceo|coo|cfo|cto|cio|cco|cdo|cpo|chief|president|vp|vice[- ]president|svp|evp|"
    r"director|head|managing director|general manager|partner|principal)\b"
)
_MANAGER = re.compile(r"\bmanager\b|\bmgr\b")
_BELOW = re.compile(
    r"\b(team lead|lead|supervisor|analyst|specialist|coordinator|associate|executive|"
    r"representative|agent|clerk|administrator|officer|engineer|developer|consultant)\b"
)
# Functions that do not own pricing, operations, procurement, commercial, finance or digital.
_IRRELEVANT_FUNCTION = re.compile(
    r"\b(marketing|hr|human resources|people|talent|recruit\w*|legal|communications|pr|brand)\b"
)


def classify_level(title: str | None) -> Level:
    if not title or not title.strip():
        return "unknown"
    t = title.lower()
    if _BELOW_FIRST.search(t):
        return "below_manager"
    if _OWNER.search(t):
        return "owner"
    if _SENIOR.search(t):
        return "senior"
    if _MANAGER.search(t):
        return "manager"
    if _BELOW.search(t):
        return "below_manager"
    return "unknown"


def irrelevant_function(title: str | None) -> bool:
    return bool(title and _IRRELEVANT_FUNCTION.search(title.lower()))
