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


def _keep_tags(s: str) -> str:
    """Like normalise() but keeps stage directions as words ('[pause]' -> 'pause'),
    so a quote that copied the tag can be pinned to the turn that has it."""
    s = s.lower().replace("’", "'").replace("—", " ").replace("–", " ").replace("'", "")
    return " ".join(_NONWORD.sub(" ", s).split())


def speaker_matches(stated: str, actual: str) -> bool:
    """Loose name match: 'Darren' / 'Darren Wu (customer)' vs 'Darren Wu'."""
    a, b = normalise(stated), normalise(actual)
    if not a or not b:
        return False
    return b in a or a in b or a.split()[0] == b.split()[0]


def match_quote(quote: str, turn_ids: list[str], window: int = 1,
                speaker: Optional[str] = None) -> Optional[list[Turn]]:
    """Return the turns that contain the quote, or None if it can't be found
    or can't be attributed unambiguously.

    Searches the cited turns (+/- `window` neighbours). Every matching
    single-speaker span is collected and ranked:
      1. matches with stage directions kept (e.g. '[pause]') beat tag-stripped matches
      2. spans containing a cited turn beat neighbouring turns
      3. tighter spans beat wider ones, nearer beats farther
    If `speaker` is given, only that speaker's spans count. If the best candidates
    tie across different speakers, the quote is ambiguous and rejected: an
    identical line said by two people (an echo) must not be guessed.
    """
    idx = turn_index()
    cited = [idx[t] for t in turn_ids if t in idx]
    if not cited:
        return None
    raw_frags = [f for f in (_keep_tags(x) for x in _ELLIPSIS.split(quote)) if f]
    fragments = [f for f in (normalise(x) for x in _ELLIPSIS.split(quote)) if f]
    if not fragments:
        return None
    cited_idx = {t.idx for t in cited}
    if sum(len(f) for f in fragments) < 8:
        # Very short quotes ("Eleven.") are only accepted as an entire cited turn.
        cands = [[t] for t in cited if normalise(t.text) == " ".join(fragments)]
        min_size = None
    else:
        call_turns = load_turns()[cited[0].call_id]
        lo = max(min(cited_idx) - 1 - window, 0)
        hi = min(max(cited_idx) + window, len(call_turns))
        span = call_turns[lo:hi]
        # A multi-turn match must be ONE speaker (a sentence broken across their turns);
        # a quote stitched from two speakers would make speaker attribution wrong.
        cands = []
        for size in range(1, len(span) + 1):
            for start in range(0, len(span) - size + 1):
                sub = span[start:start + size]
                if len({t.speaker for t in sub}) > 1:
                    continue
                if _fragments_in_order(fragments, normalise(" ".join(t.text for t in sub))):
                    cands.append(sub)
    if speaker:
        cands = [c for c in cands if speaker_matches(speaker, c[0].speaker)]
    if not cands:
        return None

    def rank(sub: list[Turn]):
        raw = _fragments_in_order(raw_frags, _keep_tags(" ".join(t.text for t in sub)))
        has_cited = any(t.idx in cited_idx for t in sub)
        dist = min(abs(t.idx - c) for t in sub for c in cited_idx)
        return (not raw, not has_cited, len(sub), dist)

    cands.sort(key=rank)
    best = rank(cands[0])
    tied_speakers = {c[0].speaker for c in cands if rank(c) == best}
    if len(tied_speakers) > 1:
        return None
    return cands[0]
