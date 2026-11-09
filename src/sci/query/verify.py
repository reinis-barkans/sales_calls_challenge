"""Step 6: final checks on the drafted answer.

1. Code: every claim must cite >=1 existing, verified finding; invalid IDs are
   dropped and claims left without evidence are removed.
2. LLM entailment (cheap model): does the cited evidence actually support the
   claim? Catches 'real quote, wrong meaning'. Unsupported claims are removed.
3. Rules: support per claim and overall confidence come from evidence
   properties, not from the model's self-assessment.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from sci import llm
from sci.config import FAST_MODEL
from sci.models import Claim, DraftAnswer, VerifiedClaim, VerifiedEvidence


class Verdict(BaseModel):
    claim_id: str
    verdict: Literal["supported", "partial", "unsupported"]
    reason: str


class Verdicts(BaseModel):
    verdicts: list[Verdict]


ENTAIL_SYSTEM = """You check whether evidence supports claims. For each claim you get the quotes (with speaker and context) it cites.
supported = the quotes clearly support the claim as written.
partial = they support the gist but the claim overstates, generalises or adds detail not in the quotes.
unsupported = the quotes do not support the claim, or contradict it, or the claim misreads the context (e.g. treats a mention as usage).
Judge only against the quotes given, not against what you think is true."""


def check_citations(draft: DraftAnswer, findings: dict[str, VerifiedEvidence]):
    """Return ([(claim_no, claim, evidence)], removed). claim_no is 1-based, as in the [C#] markers."""
    kept, removed = [], []
    for n, c in enumerate(draft.claims, 1):
        ev = [findings[i] for i in dict.fromkeys(fid.strip() for fid in c.finding_ids) if i in findings]
        if ev:
            kept.append((n, c, ev))
        else:
            removed.append({"claim": c.text, "cited": c.finding_ids, "reason": "no valid finding cited"})
    return kept, removed


def entailment(kept: list[tuple[int, Claim, list[VerifiedEvidence]]]) -> dict[int, Verdict]:
    """claim_no -> verdict."""
    if not kept:
        return {}
    blocks = []
    for n, c, ev in kept:
        quotes = "\n".join(f'   - {e.speaker} ({e.side}, {e.company}): "{e.quote}"  [context: {e.context}]' for e in ev)
        blocks.append(f"K{n}: {c.text}\n{quotes}")
    out = llm.structured(step="entail", model=FAST_MODEL, system=ENTAIL_SYSTEM,
                         user="\n\n".join(blocks), schema=Verdicts)
    res = {}
    for v in out.verdicts:
        m = re.search(r"\d+", v.claim_id)
        if m:
            res[int(m.group())] = v
    return res


def support_level(ev: list[VerifiedEvidence], verdict: str) -> str:
    stated = [e for e in ev if e.stated_or_inferred == "stated"]
    if not stated:
        return "weak"
    if verdict == "partial" or len(stated) < len(ev):
        return "moderate"
    return "strong"


def verify(draft: DraftAnswer, findings: list[VerifiedEvidence], run_entailment: bool = True):
    fmap = {f.finding_id: f for f in findings}
    kept, removed = check_citations(draft, fmap)
    verdicts = entailment(kept) if run_entailment else {}

    claims: list[VerifiedClaim] = []
    renumber_map: dict[int, int] = {}
    for n, c, ev in kept:
        v = verdicts.get(n)
        verdict = v.verdict if v else "supported"
        if verdict == "unsupported":
            removed.append({"claim": c.text, "cited": c.finding_ids, "reason": f"entailment: {v.reason}"})
            continue
        claims.append(VerifiedClaim(text=c.text, evidence=ev, support=support_level(ev, verdict)))
        renumber_map[n] = len(claims)

    # Re-number [C#] markers in the summary; flag markers of removed claims.
    def renumber(m: re.Match) -> str:
        new = renumber_map.get(int(m.group(1)))
        return f"[{new}]" if new else "[claim removed: unsupported]"
    summary = re.sub(r"\[C(\d+)\]", renumber, draft.answer)

    valid_conflicts = [c for c in draft.conflicts if sum(f in fmap for f in c.finding_ids) >= 2]
    removal_rate = len(removed) / len(draft.claims) if draft.claims else 0.0
    confidence = confidence_level(claims, valid_conflicts, removal_rate)
    return summary, claims, valid_conflicts, removed, confidence


def confidence_level(claims: list[VerifiedClaim], conflicts: list, removal_rate: float) -> str:
    if not claims:
        return "none"
    strong = sum(c.support == "strong" for c in claims) / len(claims)
    weak = sum(c.support == "weak" for c in claims) / len(claims)
    if removal_rate > 0.3 or weak > 0.5:
        return "low"
    if strong >= 0.6 and removal_rate <= 0.1:
        return "high" if not conflicts else "medium"
    return "medium"
