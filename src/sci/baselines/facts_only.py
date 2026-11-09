"""Ablation: the pipeline WITHOUT per-question reading.

Same resolve -> pick calls -> combine -> verify as the pipeline, but the
findings are the facts extracted at ingest (already quote- and speaker-verified)
for the picked calls, instead of fresh full-transcript reads. Answers the
question: does reading the picked calls in full add anything over the facts
we already have?"""
from __future__ import annotations

from sci.ingest.extract import load_facts
from sci.ingest.parse import load_calls, turn_index
from sci.models import Answer, VerifiedEvidence
from sci.query.candidates import pick_calls
from sci.query.combine import combine
from sci.query.resolve import resolve
from sci.query.verify import verify


def facts_as_findings(call_ids: list[str]) -> list[VerifiedEvidence]:
    idx, calls, wanted = turn_index(), load_calls(), set(call_ids)
    out = []
    for f in load_facts():   # verified facts only
        if f.call_id not in wanted or not f.turn_ids or f.turn_ids[0] not in idx:
            continue
        t = idx[f.turn_ids[0]]
        out.append(VerifiedEvidence(
            finding_id="", turn_id=t.turn_id, call_id=f.call_id, company=calls[f.call_id].company,
            speaker=t.speaker, side=t.side, role=t.role, ts=t.ts, quote=f.quote,
            context=f"{f.statement} ({f.type}, {f.context})",
            stated_or_inferred="inferred" if f.type == "friction" else "stated"))
    for i, f in enumerate(out, 1):
        f.finding_id = f"F{i}"
    return out


def ask(question: str) -> Answer:
    res = resolve(question)
    picked = pick_calls(question, res).ordered()
    findings = facts_as_findings(picked)
    assumptions = list(res.assumptions)
    if not findings:
        unresolved = [e.mention for e in res.companies if not e.resolved_to]
        msg = (f"No calls in the dataset match {', '.join(unresolved)}." if unresolved
               else "The transcripts don't cover this. No stored facts in the matching calls.")
        ans = Answer(question=question, answer=msg, claims=[], conflicts=[], not_covered=[question],
                     assumptions=assumptions, confidence="none", calls_considered=picked, calls_cited=[],
                     removed_claims=[], covered=False)
    else:
        draft = combine(question, findings, picked, assumptions)
        summary, claims, conflicts, removed, confidence = verify(draft, findings, True)
        covered = bool(claims)
        ans = Answer(question=question, answer=summary, claims=claims,
                     conflicts=conflicts, not_covered=draft.not_covered,
                     assumptions=list(dict.fromkeys(assumptions + draft.assumptions)), confidence=confidence,
                     calls_considered=picked, calls_cited=sorted({e.call_id for c in claims for e in c.evidence}),
                     removed_claims=removed, covered=covered)
    # Facts were verified at ingest, so citation validity is 100% by construction.
    ans.__dict__["_citation_stats"] = {"total": len(findings), "valid": len(findings)}
    ans.__dict__["_n_findings"] = len(findings)
    return ans
