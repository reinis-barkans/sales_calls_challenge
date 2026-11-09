"""Step 1: resolve the question against the call catalogue (entities, call-type
filters, search terms). Small, cheap, structured LLM call."""
from __future__ import annotations

from sci import llm
from sci.config import FAST_MODEL
from sci.ingest.parse import load_calls
from sci.models import Resolution

SYSTEM = """You prepare a question for a search system over sales call transcripts of OrbitFlow, a workflow automation vendor.
Call types: Prospect (new business), Renewal (existing customers), Churn post-mortem (customers who left), Cold call. The catalogue below gives each call's type.

Resolve company names the question mentions to the EXACT name in the catalogue. Partial or variant names (e.g. "Acme Corp") map to the closest catalogue company with confidence=medium and an assumption stating the mapping. If nothing matches, resolved_to=null.
Only set call_types when the question clearly implies them: "prospects"/"new business" -> Prospect; "renewal"/"existing customers" -> Renewal; "left"/"churned"/"lost customers" -> Churn post-mortem; "cold calls" -> Cold call. Questions about "customers" in general -> empty.
"Compare renewals vs new business" -> both Renewal and Prospect.
search_terms: the concrete entities/topics to look for, with synonyms (e.g. pricing -> price, cost, budget, discount; SSO -> SAML, single sign-on). Do not include generic words.
read_instruction: each call is read separately by a reader who cannot see other calls. Tell it what raw material to extract. Example: for "Has the vendor given inconsistent answers?" -> "Extract every factual claim OrbitFlow staff make about the product: plans/tiers and what each includes, features, connectors, security/compliance, pricing, roadmap, including hedges and corrections." For simple lookups, restate the question.
question_type=out_of_scope only if the question is not about these sales calls at all."""


def resolve(question: str) -> Resolution:
    catalogue = "\n".join(f"{c.call_id}: {c.company} ({c.category}, {c.stage}, {c.industry})" for c in load_calls().values())
    return llm.structured(step="resolve", model=FAST_MODEL, system=f"{SYSTEM}\n\nCatalogue:\n{catalogue}",
                          cache_system=True, user=f"Question: {question}", schema=Resolution)
