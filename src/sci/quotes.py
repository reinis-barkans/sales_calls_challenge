"""Deterministic quote matching shared by the ingest and answer verifiers.

A quote is accepted only if (after normalisation) it is a substring of the cited
turn, or of the cited turn joined with its neighbours (sentences often break
across turns). Models routinely drop stage directions like [pause] and use
'...' for elisions, so we strip tags and treat '...' as a split point: every
fragment must appear, in order.
"""
from __future__ import annotations

import re
from typing import Optional

from sci.ingest.parse import load_turns, turn_index
from sci.models import Turn

_TAG = re.compile(r"\[[a-z ]+\]")
_NONWORD = re.compile(r"[^a-z0-9£$%]+")
_ELLIPSIS = re.compile(r"\.\.\.|…|\[\.\.\.\]")
_TID = re.compile(r"^(CALL-\d{3})#T(\d{3})$")


def normalise(s: str) -> str:
    s = _TAG.sub(" ", s.lower()).replace("’", "'").replace("—", " ").replace("–", " ")
    s = s.replace("'", "")
    return " ".join(_NONWORD.sub(" ", s).split())


def fix_turn_id(tid: str, call_id: Optional[str] = None) -> str:
    """Accept 'T045' or 'CALL-006#T45' forms from models."""
    tid = tid.strip()
    m = re.match(r"^(?:(CALL-\d{3})#)?T(\d+)$", tid)
    if not m:
        return tid
    cid = m.group(1) or call_id or ""
    return f"{cid}#T{int(m.group(2)):03d}"


def _fragments_in_order(fragments: list[str], hay: str) -> bool:
    pos = 0
    for frag in fragments:
        i = hay.find(frag, pos)
        if i < 0:
            return False
        pos = i + len(frag)
    return True


def match_quote(quote: str, turn_ids: list[str], window: int = 1) -> Optional[list[Turn]]:
    """Return the turns that contain the quote, or None if it can't be found.

    Searches the cited turns (+/- `window` neighbours) as one joined span.
    """
    idx = turn_index()
    cited = [idx[t] for t in turn_ids if t in idx]
    if not cited:
        return None
    fragments = [normalise(f) for f in _ELLIPSIS.split(quote)]
    fragments = [f for f in fragments if f]
    if not fragments:
        return None
    if sum(len(f) for f in fragments) < 8:
        # Very short quotes ("Eleven.") are only accepted as an entire cited turn.
        whole = [t for t in cited if normalise(t.text) == " ".join(fragments)]
        return whole[:1] or None
    call_turns = load_turns()[cited[0].call_id]
    lo = max(min(t.idx for t in cited) - 1 - window, 0)
    hi = min(max(t.idx for t in cited) + window, len(call_turns))
    span = call_turns[lo:hi]
    # Prefer the tightest matching span: single turns first, then pairs, then the whole window.
    # A multi-turn match must be ONE speaker (a sentence broken across their turns);
    # a quote stitched from two speakers would make speaker attribution wrong.
    for size in range(1, len(span) + 1):
        for start in range(0, len(span) - size + 1):
            sub = span[start:start + size]
            if len({t.speaker for t in sub}) > 1:
                continue
            if _fragments_in_order(fragments, normalise(" ".join(t.text for t in sub))):
                return sub
    return None
