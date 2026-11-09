"""Step 6: final checks on the drafted answer.

1. Code: every claim must cite >=1 existing, verified finding; invalid IDs are
   dropped and claims left without evidence are removed.
2. LLM entailment (cheap model): does the cited evidence actually support the
   claim? Catches 'real quote, wrong meaning'. Unsupported claims are removed.
3. Rules: support per claim and overall confidence come from evidence
   properties, not from the model's self-assessment.
4. Code: the summary is grounded too. Every summary sentence must carry [C#]
   markers of claims that survived steps 1-2; sentences with no marker, or with a
   marker of a removed claim, are deleted (not just re-labelled), so removed or
   uncited content never reaches the reader.
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
Judge only against the quotes given, not against what you think is true.
Return EXACTLY ONE verdict per claim, using its ID exactly as given (K1, K2, ...). Judge each claim as a whole against all of its quotes; do not split a claim into parts. Cover every claim listed."""


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


_SEVERITY = {"supported": 0, "partial": 1, "unsupported": 2}


def _parse_verdicts(out: "Verdicts", wanted: set[int]) -> dict[int, Verdict]:
    """claim_no -> verdict. If the model still splits a claim into parts ('K1-2'),
    the WORST part wins, so a later 'supported' can't hide an 'unsupported'."""
    res: dict[int, Verdict] = {}
    for v in out.verdicts:
        m = re.search(r"\d+", v.claim_id)
        if not m or int(m.group()) not in wanted:
            continue
        n = int(m.group())
        if n not in res or _SEVERITY[v.verdict] > _SEVERITY[res[n].verdict]:
            res[n] = v
    return res


def _entail_call(kept, attempt: int):
    blocks = []
    for n, c, ev in kept:
        quotes = "\n".join(f'   - {e.speaker} ({e.side}, {e.company}): "{e.quote}"  [context: {e.context}]' for e in ev)
        blocks.append(f"K{n}: {c.text}\n{quotes}")
    ids = ", ".join(f"K{n}" for n, _, _ in kept)
    user = "\n\n".join(blocks) + f"\n\nReturn {len(kept)} verdicts, one for each of: {ids}."
    if attempt:
        user += f"\n(retry {attempt}: these claims were missing a verdict)"
    return llm.structured(step="entail", model=FAST_MODEL, system=ENTAIL_SYSTEM, user=user, schema=Verdicts)


def entailment(kept: list[tuple[int, Claim, list[VerifiedEvidence]]]) -> dict[int, Verdict]:
    """claim_no -> verdict. Claims the checker skips are asked about once more;
    anything still without a verdict is left out, and verify() fails closed on it."""
    res: dict[int, Verdict] = {}
    todo = list(kept)
    for attempt in range(2):
        if not todo:
            break
        res.update(_parse_verdicts(_entail_call(todo, attempt), {n for n, _, _ in todo}))
        todo = [k for k in todo if k[0] not in res]
    return res


def support_level(ev: list[VerifiedEvidence], verdict: str) -> str:
    stated = [e for e in ev if e.stated_or_inferred == "stated"]
    if not stated:
        return "weak"
    if verdict == "partial" or len(stated) < len(ev):
        return "moderate"
    return "strong"


NOT_ANSWERED = "The findings don't answer this question reliably; see NOT COVERED."

_MARKER = re.compile(r"\[C(\d+)\]")
# A marker placed after the full stop ("...requirement. [C1]") belongs to the sentence before it.
_TRAILING_MARKERS = re.compile(r"([.!?])((?:\s*\[C\d+\])+)")
# Split after . ! ? + whitespace, but not after common abbreviations: splitting
# "integrations, e.g. Salesforce [C1]." would drop the unmarked first half and
# leave a fragment. ("etc." is left out on purpose: it usually ends a sentence.)
_ABBREVS = ("e.g.", "i.e.", "vs.", "approx.", "incl.", "cf.", "Mr.", "Ms.", "Mrs.", "Dr.", "St.", "Inc.", "Ltd.", "Co.", "No.")
_SENTENCE_END = re.compile(
    "".join(rf"(?<!\b{re.escape(a)})" for a in _ABBREVS + tuple(a.capitalize() for a in _ABBREVS if a[0].islower()))
    + r"(?<=[.!?])\s+")


def ground_summary(text: str, renumber_map: dict[int, int]) -> tuple[str, list[str]]:
    """Keep only summary sentences whose [C#] markers all point at surviving claims.

    Returns (summary with markers renumbered to [1], [2]..., dropped sentences).
    A sentence with no marker is unverified prose; a sentence citing a removed
    claim still contains that claim's content. Both are dropped."""
    text = _TRAILING_MARKERS.sub(lambda m: f"{m.group(2)}{m.group(1)}", text.strip())
    kept, dropped = [], []
    for sent in (s for s in _SENTENCE_END.split(text) if s.strip()):
        nums = [int(x) for x in _MARKER.findall(sent)]
        if nums and all(n in renumber_map for n in nums):
            kept.append(_MARKER.sub(lambda m: f"[{renumber_map[int(m.group(1))]}]", sent))
        else:
            dropped.append(sent)
    return " ".join(kept), dropped


def verify(draft: DraftAnswer, findings: list[VerifiedEvidence], run_entailment: bool = True):
    fmap = {f.finding_id: f for f in findings}
    kept, removed = check_citations(draft, fmap)
    verdicts = entailment(kept) if run_entailment else {}

    claims: list[VerifiedClaim] = []
    renumber_map: dict[int, int] = {}
    for n, c, ev in kept:
        v = verdicts.get(n)
        if run_entailment and v is None:
            # Fail closed: a claim the checker skipped has not been checked.
            removed.append({"claim": c.text, "cited": c.finding_ids, "reason": "entailment: no verdict returned"})
            continue
        verdict = v.verdict if v else "supported"
        if verdict == "unsupported":
            removed.append({"claim": c.text, "cited": c.finding_ids, "reason": f"entailment: {v.reason}"})
            continue
        claims.append(VerifiedClaim(text=c.text, evidence=ev, support=support_level(ev, verdict)))
        renumber_map[n] = len(claims)
    # Claim removal rate only; dropped summary sentences are logged below but don't count here.
    removal_rate = len(removed) / len(draft.claims) if draft.claims else 0.0

    summary, dropped = ground_summary(draft.answer, renumber_map)
    for s in dropped:
        removed.append({"claim": s, "cited": _MARKER.findall(s),
                        "reason": "summary sentence without a surviving claim citation"})
    if claims and not summary:
        # Every sentence was dropped: fall back to the verified claims themselves.
        summary = " ".join(f"{c.text.rstrip('.')} [{i}]." for i, c in enumerate(claims, 1))
    if not claims:
        summary = NOT_ANSWERED

    valid_conflicts = [c for c in draft.conflicts if sum(f in fmap for f in c.finding_ids) >= 2]
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
