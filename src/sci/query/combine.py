"""Step 5: combine verified findings into an answer. The model sees ONLY the
findings (never raw transcripts or its own knowledge) plus counts computed in code."""
from __future__ import annotations

from collections import defaultdict

from sci import llm
from sci.config import STRONG_MODEL
from sci.ingest.parse import load_calls
from sci.models import DraftAnswer, VerifiedEvidence

SYSTEM = """You answer a sales manager's question about OrbitFlow's sales calls using ONLY the numbered findings provided.
Each finding was extracted from a transcript and its quote has been verified against the source.

Rules:
- Every claim must cite the finding IDs that support it. Never state anything that no finding supports. No general knowledge.
- The `answer` is a short summary that references claims as [C1], [C2]... in the order of the claims list. It may contain no facts beyond the claims. EVERY sentence must end with the [C#] markers of the claims it rests on, including short framing sentences ("Yes [C1][C2]."); the verifier deletes any sentence without a marker, or citing a claim it removes.
- Keep what was said separate from what is inferred; when a claim rests on 'inferred' findings, say so in the claim text ("appears to", "suggests").
- Be precise about context: a mention is not the same as usage, an outage is not an integration, a stated reason is not necessarily the real reason.
- When findings disagree (across calls, across vendor reps, or within one call), record each disagreement in `conflicts` with the finding IDs on both sides. For questions about the vendor, compare what different OrbitFlow reps claimed on the same topic.
- Use the provided counts for any "how many / most common" statements; do not count yourself.
- If the findings answer only part of the question, answer that part and list the rest in not_covered. If they do not answer it at all, say so in `answer`, return no claims, and explain in not_covered.
- Include every distinct fact in the findings that answers the question, including the specifics a manager would ask next (who, which vendor/competitor, numbers, dates, what happened next). Leave out tangents, background, and "X was consistent" filler. Put the strongest, most important claims first.
- Name companies and speakers so the manager can check them. Be concise."""


def format_findings(findings: list[VerifiedEvidence]) -> str:
    calls = load_calls()
    lines = []
    for f in findings:
        c = calls[f.call_id]
        lines.append(f"[{f.finding_id}] {f.call_id} {c.company} ({c.category}, {c.stage}) | {f.speaker} "
                     f"({f.side}, {f.role}) {f.turn_id.split('#')[1]} [{f.ts}] | {f.stated_or_inferred}\n"
                     f"    finding: {f.context}\n    quote: \"{f.quote}\"")
    return "\n".join(lines)


def counts(findings: list[VerifiedEvidence], considered: list[str]) -> str:
    calls = load_calls()
    by_type: dict[str, set[str]] = defaultdict(set)
    for f in findings:
        by_type[calls[f.call_id].category].add(calls[f.call_id].company)
    considered_by_type: dict[str, int] = defaultdict(int)
    for cid in considered:
        considered_by_type[calls[cid].category] += 1
    rows = [f"- {t}: {len(cos)} of {considered_by_type[t]} calls read had relevant findings ({', '.join(sorted(cos))})"
            for t, cos in sorted(by_type.items())]
    return "Counts (computed in code):\n" + "\n".join(rows)


def combine(question: str, findings: list[VerifiedEvidence], considered: list[str], assumptions: list[str]) -> DraftAnswer:
    user = (f"Question: {question}\n\n"
            + (f"Assumptions already made: {'; '.join(assumptions)}\n\n" if assumptions else "")
            + f"{counts(findings, considered)}\n\nFindings:\n{format_findings(findings)}")
    return llm.structured(step="combine", model=STRONG_MODEL, system=SYSTEM, user=user,
                          schema=DraftAnswer, max_tokens=12000)
