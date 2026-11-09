"""Step 3: read each picked call in full, in isolation and in parallel, and
return quote-verified findings. One call per prompt keeps the model's job
narrow (is this call relevant, and what exactly does it say?) and prevents
cross-call attribution mistakes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sci import llm
from sci.config import FAST_MODEL, MAX_PARALLEL
from sci.ingest.parse import load_calls, render_transcript, turn_index
from sci.models import CallReading, VerifiedEvidence
from sci.quotes import fix_turn_id, match_quote

SYSTEM = """You read ONE sales call transcript of OrbitFlow (a workflow automation vendor) and extract everything in it that helps answer a question.
Each line starts with a turn ID (e.g. T045), timestamp, speaker and side (vendor = OrbitFlow staff, customer = the prospect/customer).

Rules:
- Only report what this transcript supports. If it contains nothing relevant, return relevant=false and no findings. Do not stretch: a passing mention of a word is not the same as the topic (e.g. a Salesforce OUTAGE is not a Salesforce INTEGRATION). Put the nuance in `context`.
- Every finding cites turn IDs (format T045) and a VERBATIM quote copied from those turns (you may use '...' to skip words within ONE speaker's words). A quote must come from a single speaker; never stitch two speakers together. Never paraphrase inside the quote.
- Mark findings stated (someone said it) or inferred (your reading of tone, outcome, or implication). Prefer stated.
- Distinguish who said it: what OrbitFlow staff claim about their product is different from what customers say.
- If a speaker corrects or contradicts themselves or someone else, report both statements.
- If a stated reason differs from what the conversation shows as the real reason, report both.
- Be complete: include every relevant finding, typically 1-8."""


def _found_any(quote: str, tids: list[str]) -> bool:
    """True if the text occurs in the window at all, ignoring attribution."""
    idx = turn_index()
    from sci.quotes import normalise
    frag = normalise(quote)
    turns = [idx[t] for t in tids if t in idx]
    return bool(frag) and any(frag in normalise(t.text) for t in turns)


def read_call(call_id: str, question: str, hints: list[str], instruction: str = "") -> tuple[list[VerifiedEvidence], list[dict]]:
    hint = f"\nRelated terms: {', '.join(hints)}" if hints else ""
    task = (f"\nWhat to extract from THIS call (other calls are read separately and compared later; "
            f"report relevant statements even if they look unremarkable on their own): {instruction}") if instruction else ""
    reading = llm.structured(step="read", model=FAST_MODEL, system=SYSTEM,
                             cached_context=render_transcript(call_id),   # reused across questions
                             user=f"---\nQuestion: {question}{task}{hint}",
                             schema=CallReading, max_tokens=8000)
    if not reading.relevant:
        return [], []
    idx = turn_index()
    company = load_calls()[call_id].company
    ok, rejected = [], []
    for f in reading.findings:
        tids = [t for t in (fix_turn_id(x, call_id) for x in f.turn_ids) if t in idx]
        matched = match_quote(f.quote, tids, speaker=f.speaker) if tids else None
        if not matched:
            # Distinguish "not there" from "there, but said by someone else / ambiguous".
            anywhere = match_quote(f.quote, tids) if tids else None
            reason = ("quote not found in cited turns" if anywhere is None and not _found_any(f.quote, tids)
                      else f"speaker mismatch or ambiguous attribution (reader said {f.speaker})")
            rejected.append({"call_id": call_id, "claim": f.claim, "quote": f.quote, "turn_ids": f.turn_ids,
                             "speaker": f.speaker, "reason": reason})
            continue
        t = matched[0]
        ok.append(VerifiedEvidence(finding_id="", turn_id=t.turn_id, call_id=call_id, company=company,
                                   speaker=t.speaker, side=t.side, role=t.role, ts=t.ts, quote=f.quote,
                                   context=f"{f.claim} — {f.context}", stated_or_inferred=f.stated_or_inferred))
    return ok, rejected


def read_calls(call_ids: list[str], question: str, hints: list[str], instruction: str = ""):
    with ThreadPoolExecutor(MAX_PARALLEL) as pool:
        results = list(pool.map(lambda c: read_call(c, question, hints, instruction), call_ids))
    findings, rejected = [], []
    for ok, rej in results:
        findings.extend(ok)
        rejected.extend(rej)
    for i, f in enumerate(findings, 1):
        f.finding_id = f"F{i}"
    return findings, rejected
