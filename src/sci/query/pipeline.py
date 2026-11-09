"""Orchestration: resolve -> pick calls -> read each in full -> (short-circuit if
nothing verified) -> combine -> verify. Every run writes a trace so a bad answer
can be attributed to the stage that caused it."""
from __future__ import annotations

import hashlib
import json
import time

from sci import llm
from sci.config import TRACES
from sci.ingest.index import get_index
from sci.ingest.parse import load_calls
from sci.models import Answer
from sci.query.candidates import pick_calls
from sci.query.combine import combine
from sci.query.read import read_calls
from sci.query.resolve import resolve
from sci.query.verify import verify


def _closest_material(question: str, terms: list[str], k: int = 3) -> list[str]:
    hits = get_index().search(question + " " + " ".join(terms), k=k)
    calls = load_calls()
    return [f"{c.call_id} ({calls[c.call_id].company}) turns {c.turn_ids[0].split('#')[1]}-{c.turn_ids[-1].split('#')[1]}"
            for c, _ in hits]


def ask(question: str, run_entailment: bool = True, write_trace: bool = True) -> Answer:
    t0 = time.time()
    usage_start = len(llm.USAGE)
    trace: dict = {"question": question}

    res = resolve(question)
    trace["resolution"] = res.model_dump()
    assumptions = list(res.assumptions)

    cand = pick_calls(question, res)
    picked = cand.ordered()
    trace["candidates"] = {cid: sorted(r) for cid, r in cand.calls.items()}
    trace["search_terms"] = cand.terms

    findings, rejected = read_calls(picked, question, cand.terms, res.read_instruction) if picked else ([], [])
    trace["findings"] = [f.model_dump() for f in findings]
    trace["rejected_findings"] = rejected

    unresolved = [e.mention for e in res.companies if not e.resolved_to]
    if not findings:
        # Deterministic not-covered path: the answering model is never called.
        if unresolved:
            msg = f"No calls in the dataset match {', '.join(unresolved)}; nothing to answer from."
        elif picked:
            msg = f"The transcripts don't cover this. I read {len(picked)} candidate call(s) and found no supporting evidence."
        else:
            msg = "The transcripts don't cover this. No call matched the question's entities or terms."
        closest = _closest_material(question, cand.terms) if not unresolved else []
        ans = Answer(question=question, answer=msg, claims=[], conflicts=[],
                     not_covered=[question] + ([f"Closest related material: {', '.join(closest)}"] if closest else []),
                     assumptions=assumptions, confidence="none", calls_considered=picked, calls_cited=[],
                     removed_claims=rejected, covered=False)
    else:
        draft = combine(question, findings, picked, assumptions)
        trace["draft"] = draft.model_dump()
        summary, claims, conflicts, removed, confidence = verify(draft, findings, run_entailment)
        cited = sorted({e.call_id for c in claims for e in c.evidence})
        covered = bool(claims)   # with no surviving claims, verify() returns a fixed not-answered message
        ans = Answer(question=question, answer=summary, claims=claims, conflicts=conflicts,
                     not_covered=draft.not_covered, assumptions=list(dict.fromkeys(assumptions + draft.assumptions)),
                     confidence=confidence, calls_considered=picked, calls_cited=cited,
                     removed_claims=removed, covered=covered)

    usage = llm.usage_summary(llm.USAGE[usage_start:])
    trace["usage"] = {**usage, "latency_s": round(time.time() - t0, 2)}
    trace["answer"] = ans.model_dump()
    if write_trace:
        tid = hashlib.sha1(question.encode()).hexdigest()[:10]
        TRACES.mkdir(parents=True, exist_ok=True)
        (TRACES / f"{tid}.json").write_text(json.dumps(trace, indent=1, default=str))
        ans.trace_id = tid
    ans.__dict__["_trace"] = trace
    return ans
