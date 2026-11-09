"""LLM judge: checks each gold key fact against an answer.
It sees the gold facts and the answer (with its quoted evidence), not the
transcripts, so it measures 'did the answer get the expected facts', while
grounding is measured separately and deterministically by the quote verifier."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from sci import llm
from sci.config import STRONG_MODEL
from sci.models import Answer


class FactGrade(BaseModel):
    fact_no: int
    grade: Literal["present", "partial", "absent", "contradicted"]
    reason: str


class Grades(BaseModel):
    grades: list[FactGrade]


SYSTEM = """You grade an answer from a sales-call Q&A system against expected key facts.
For each numbered key fact decide:
present = the answer clearly states it (wording may differ);
partial = the answer gets part of it or states it vaguely;
absent = not in the answer;
contradicted = the answer states something incompatible with it.
Grade only against the answer text and its quoted evidence. Be strict: do not give credit for facts that are merely implied."""


def render_answer(a: Answer) -> str:
    lines = [a.answer]
    for i, c in enumerate(a.claims, 1):
        lines.append(f"[{i}] {c.text}")
        lines.extend(f'    - {e.call_id} {e.company}, {e.speaker}: "{e.quote}"' for e in c.evidence)
    for c in a.conflicts:
        lines.append(f"CONFLICT: {c.topic} {c.description}")
    for a_ in a.assumptions:
        lines.append(f"ASSUMPTION: {a_}")
    if a.not_covered:
        lines.append("NOT COVERED: " + "; ".join(a.not_covered))
    return "\n".join(lines)


def judge(question: str, key_facts: list[str], answer: Answer) -> list[FactGrade]:
    if not key_facts:
        return []
    facts = "\n".join(f"{i}. {f}" for i, f in enumerate(key_facts, 1))
    out = llm.structured(step="judge", model=STRONG_MODEL, system=SYSTEM,
                         user=f"Question: {question}\n\nKey facts:\n{facts}\n\nAnswer:\n{render_answer(answer)}",
                         schema=Grades)
    return out.grades
