"""Per-call LLM extraction -> CallCard + Facts, each fact quote-verified against
the source. Facts are an *index* (used to pick calls and to count), never
evidence in answers: answers cite the full per-call reads."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from sci import llm
from sci.config import CARDS_FILE, FACTS_FILE, FAST_MODEL, MAX_PARALLEL
from sci.ingest.parse import load_calls, render_transcript, turn_index
from sci.models import CallCard, Extraction, StoredFact
from sci.quotes import fix_turn_id, match_quote

SYSTEM = """You extract structured facts from one B2B sales call transcript for a sales-intelligence index.
The vendor is OrbitFlow (a workflow automation platform). Each line starts with a turn ID like T045.

Rules:
- Extract only what was actually said. Every fact cites >=1 turn ID (format T045) and a VERBATIM quote of <=25 words copied from that turn, from a single speaker. Do not paraphrase inside the quote.
- Attribute by side. Anything an OrbitFlow person asserts about the product, plans, pricing, security, certifications, connectors or roadmap is type=vendor_claim, context=claimed_by_vendor, with the rep as speaker. Capture these thoroughly: they are used to detect inconsistent vendor answers across calls.
- Record HOW an entity came up in `context`. A Salesforce outage is context=incident, not uses. A tool they left is previously_used; a tool they moved to is replaced_by; a competitor under evaluation is evaluating.
- Extract EVERY third-party tool, system, integration and competitor mentioned, however briefly (type=integration or competitor). Passing mentions matter.
- If a customer corrects or contradicts themselves (e.g. a number revised, or 'that wasn't the real reason'), capture both statements as separate facts and say so in the statement.
- Write numbers both as spoken and as digits in `statement`, e.g. "eighteen hundred a month (£1,800/month)".
- Use canonical entity names: Salesforce, HubSpot, Zapier, Workato, Tray.io, Power Automate, MuleSoft, Make, Retool Workflows, Gainsight, SSO, SCIM, SOC 2, data residency, pricing, etc.
- Record interpersonal friction as type=friction, entity=friction, from ANY speaker (vendor or customer, including between colleagues): curt, dismissive, sarcastic, condescending or hostile remarks, talking over someone, visible frustration or tension. `statement` says who did what to whom and how it was received. NOT friction: apologies, joining late, hedges, worries, self-corrections, polite disagreement or tough questions asked politely. Only tag remarks a neutral listener would call sharp, mocking or unfriendly.
- Aim for completeness over brevity: typically 20-60 facts for a long call."""


def _extract_one(call_id: str) -> tuple[CallCard, list[StoredFact], dict]:
    ex = llm.structured(step="extract", model=FAST_MODEL, system=SYSTEM,
                        user=render_transcript(call_id), schema=Extraction, max_tokens=16000, cache_system=True)
    idx = turn_index()
    facts: list[StoredFact] = []
    ok = 0
    for i, f in enumerate(ex.facts):
        tids = [fix_turn_id(t, call_id) for t in f.turn_ids]
        tids = [t for t in tids if t in idx]
        matched = match_quote(f.quote, tids, speaker=f.speaker) if tids else None
        if matched:
            ok += 1
            tids = [t.turn_id for t in matched]
        side = idx[tids[0]].side if tids else ("vendor" if f.type == "vendor_claim" else "customer")
        speaker = idx[tids[0]].speaker if matched else f.speaker
        facts.append(StoredFact(**{**f.model_dump(), "turn_ids": tids, "speaker": speaker},
                                fact_id=f"{call_id}#F{i + 1:03d}", call_id=call_id, side=side, verified=bool(matched)))
    stats = {"call_id": call_id, "facts": len(facts), "verified": ok}
    return ex.card, facts, stats


def run_extraction() -> list[dict]:
    calls = list(load_calls())
    with ThreadPoolExecutor(MAX_PARALLEL) as pool:
        results = list(pool.map(_extract_one, calls))
    cards = {cid: card.model_dump() for cid, (card, _, _) in zip(calls, results)}
    facts = [f.model_dump() for _, fs, _ in results for f in fs]
    CARDS_FILE.write_text(json.dumps(cards, indent=1))
    FACTS_FILE.write_text(json.dumps(facts, indent=1))
    load_facts.cache_clear()
    load_cards.cache_clear()
    return [s for _, _, s in results]


@lru_cache
def load_facts(include_unverified: bool = False) -> list[StoredFact]:
    if not FACTS_FILE.exists():
        return []
    facts = [StoredFact(**f) for f in json.loads(FACTS_FILE.read_text())]
    return facts if include_unverified else [f for f in facts if f.verified]


@lru_cache
def load_cards() -> dict[str, CallCard]:
    if not CARDS_FILE.exists():
        return {}
    return {k: CallCard(**v) for k, v in json.loads(CARDS_FILE.read_text()).items()}
