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
    assumptions: list[str] = field(default_factory=list)       # assumptions made in code (shown in the answer)

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


def _norm(name: str) -> str:
    return " ".join(name.lower().split())


def match_company(name: str | None) -> tuple[str | None, bool]:
    """Resolve a name to ONE catalogue company -> (company, is_partial).

    1. Exact match, ignoring case and spacing ("acme  LOGISTICS").
    2. Otherwise, if the name appears as whole words in exactly one company name
       ("Acme" -> "Acme Logistics"), use it and report it as partial so an
       assumption can be stated. Several matches ("Group") or none -> no match."""
    if not name or len(_norm(name)) < 3:
        return None, False
    companies = {c.company for c in load_calls().values()}
    n = _norm(name)
    exact = [c for c in companies if _norm(c) == n]
    if exact:
        return exact[0], False
    partial = [c for c in companies if f" {n} " in f" {_norm(c)} "]
    return (partial[0], True) if len(partial) == 1 else (None, False)


def calls_for_company(name: str | None) -> list[str]:
    """All call IDs for the catalogue company `name` resolves to (a company can have
    several calls). Unknown, ambiguous or None -> []."""
    company, _ = match_company(name)
    return sorted(cid for cid, c in load_calls().items() if c.company == company) if company else []


def unmatched_companies(res: Resolution) -> list[str]:
    """Mentions that didn't resolve to any call in the catalogue."""
    return [e.mention for e in res.companies if not calls_for_company(e.resolved_to)]


def pick_calls(question: str, res: Resolution) -> Candidates:
    calls = load_calls()
    cand = Candidates()

    company_calls = {cid for e in res.companies for cid in calls_for_company(e.resolved_to)}
    for e in res.companies:
        company, partial = match_company(e.resolved_to)
        if partial:
            cand.assumptions.append(f"'{e.resolved_to}' is assumed to mean {company}, the only company in the dataset with that name.")
    if company_calls:
        # A question about named companies reads exactly those calls.
        for cid in company_calls:
            cand.add(cid, "company")
        return cand
    if res.companies:
        # Named a company we don't have (or the resolver returned a name that isn't in the
        # catalogue): don't fall through to a dataset-wide search and answer about others.
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
