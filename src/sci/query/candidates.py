"""Step 2: pick calls, deterministically, from three sources:
  metadata (resolved companies / call types) ∪ extracted-fact matches ∪ BM25 hits ∪ dense-vector hits,
the last two rolled up from chunks to calls.
Each picked call records why. Coverage is a property of this code, not of an LLM."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from sci.config import ALIASES_FILE, SEARCH_MIN_SCORE_RATIO, VECTOR_MIN_SIM, VECTOR_TOP_CHUNKS
from sci.ingest.extract import load_facts
from sci.ingest.index import get_index, get_vector_index, tokenize
from sci.ingest.parse import load_calls
from sci.models import Resolution


@dataclass
class Candidates:
    calls: dict[str, set[str]] = field(default_factory=dict)   # call_id -> reasons
    terms: list[str] = field(default_factory=list)

    def add(self, call_id: str, reason: str):
        self.calls.setdefault(call_id, set()).add(reason)

    def ordered(self) -> list[str]:
        return sorted(self.calls)


@lru_cache
def _aliases() -> dict[str, list[str]]:
    data = json.loads(ALIASES_FILE.read_text())
    data.pop("_comment", None)
    return data


def expand_terms(terms: list[str]) -> list[str]:
    """Add alias variants for any term matching a canonical entity or one of its variants."""
    out = {t.lower() for t in terms}
    for canon, variants in _aliases().items():
        names = {canon.lower(), *variants}
        if out & names or any(t in names for t in out):
            out |= names
    return sorted(out)


def fact_matches(terms: list[str], allowed: set[str] | None) -> dict[str, int]:
    """call_id -> number of verified facts whose entity matches a term (or whose statement contains a multi-word term)."""
    hits: dict[str, int] = {}
    singles = {t for t in terms if " " not in t}
    phrases = [t for t in terms if " " in t]
    for f in load_facts():
        if allowed and f.call_id not in allowed:
            continue
        ent = f.entity.lower()
        ent_toks = set(tokenize(ent))
        stmt = f.statement.lower()
        if ent in terms or ent_toks & singles or any(p in ent or p in stmt for p in phrases):
            hits[f.call_id] = hits.get(f.call_id, 0) + 1
    return hits


def search_calls(query: str, allowed: set[str] | None) -> dict[str, float]:
    """BM25 over chunks, rolled up to call level (best chunk score per call), thresholded relative to the top hit."""
    best: dict[str, float] = {}
    for chunk, score in get_index().search(query, call_ids=allowed):
        best[chunk.call_id] = max(best.get(chunk.call_id, 0), score)
    if not best:
        return {}
    top = max(best.values())
    return {cid: s for cid, s in best.items() if s >= SEARCH_MIN_SCORE_RATIO * top}


def vector_calls(question: str, allowed: set[str] | None) -> dict[str, float]:
    """Dense search on the question text; calls whose best chunk clears an absolute similarity floor."""
    best: dict[str, float] = {}
    for chunk, sim in get_vector_index().search(question, k=VECTOR_TOP_CHUNKS, call_ids=allowed):
        if sim >= VECTOR_MIN_SIM:
            best[chunk.call_id] = max(best.get(chunk.call_id, 0), sim)
    return best


def pick_calls(question: str, res: Resolution) -> Candidates:
    calls = load_calls()
    cand = Candidates()

    companies = [e.resolved_to for e in res.companies if e.resolved_to]
    by_company = {c.company: cid for cid, c in calls.items()}
    company_calls = {by_company[n] for n in companies if n in by_company}
    if company_calls:
        # A question about named companies reads exactly those calls.
        for cid in company_calls:
            cand.add(cid, "company")
        return cand
    if any(e.resolved_to is None for e in res.companies):
        # Named a company we don't have: don't silently answer about others.
        return cand

    allowed = {cid for cid, c in calls.items() if c.category in res.call_types} or None
    if allowed:
        for cid in allowed:
            cand.add(cid, f"call_type:{calls[cid].category}")

    cand.terms = expand_terms(res.search_terms)
    for cid in fact_matches(cand.terms, allowed):
        cand.add(cid, "facts")
    # Search on the resolved terms only: raw question words ("mention", "said") match everything.
    for cid in search_calls(" ".join(cand.terms) or question, allowed):
        cand.add(cid, "search")
    for cid in vector_calls(question, allowed):
        cand.add(cid, "vector")
    return cand
