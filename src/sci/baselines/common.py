"""Shared output schema for baselines so the eval scores every system the same way.
Baseline citations are NOT trusted: the eval runs them through the same quote
matcher, which measures how often each approach fabricates evidence."""
from __future__ import annotations

from pydantic import BaseModel, Field

from sci.models import Answer, VerifiedClaim, VerifiedEvidence
from sci.ingest.parse import load_calls, turn_index
from sci.quotes import fix_turn_id, match_quote

BASELINE_RULES = """Answer using ONLY the transcript material provided. Cite evidence for every claim as call ID + turn ID + a verbatim quote.
If the material does not answer the question, say so and set covered=false. Flag disagreements between sources in `conflicts`."""


class Citation(BaseModel):
    call_id: str
    turn_id: str = Field(description="e.g. T045")
    quote: str


class BClaim(BaseModel):
    text: str
    citations: list[Citation]


class BaselineAnswer(BaseModel):
    answer: str
    claims: list[BClaim]
    conflicts: list[str]
    covered: bool


def to_answer(question: str, b: BaselineAnswer, considered: list[str]) -> Answer:
    """Convert to the common Answer type. Claims keep only citations that verify;
    the raw counts are stored for the citation-validity metric."""
    idx = turn_index()
    calls = load_calls()
    claims, total, valid = [], 0, 0
    for c in b.claims:
        ev = []
        for cit in c.citations:
            total += 1
            tid = fix_turn_id(cit.turn_id, cit.call_id)
            m = match_quote(cit.quote, [tid]) if tid in idx else None
            if m:
                valid += 1
                t = m[0]
                ev.append(VerifiedEvidence(finding_id="", turn_id=t.turn_id, call_id=t.call_id,
                                           company=calls[t.call_id].company, speaker=t.speaker, side=t.side,
                                           role=t.role, ts=t.ts, quote=cit.quote))
        claims.append(VerifiedClaim(text=c.text, evidence=ev, support="strong" if ev else "weak"))
    from sci.models import Conflict
    ans = Answer(question=question, answer=b.answer, claims=claims,
                 conflicts=[Conflict(topic="", description=x, finding_ids=[]) for x in b.conflicts],
                 not_covered=[] if b.covered else [question], assumptions=[],
                 confidence="medium" if b.covered else "none", calls_considered=considered,
                 calls_cited=sorted({e.call_id for c in claims for e in c.evidence}), covered=b.covered)
    ans.__dict__["_citation_stats"] = {"total": total, "valid": valid}
    return ans
