"""Data model. Turn IDs (e.g. "CALL-006#T045") are the backbone: every piece of
evidence carries them and the verifiers check against them."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Side = Literal["vendor", "customer"]


class Participant(BaseModel):
    name: str
    role: str
    company: str


class Call(BaseModel):
    call_id: str
    company: str
    industry: str
    company_size: str
    call_type: str          # Prospect | Renewal | Churn post-mortem | Cold call
    stage: str
    date: str
    duration_minutes: int
    participants: list[Participant]
    file: str

    @property
    def category(self) -> str:
        """Manifest call_type is only Prospect / Existing customer; the sub-type lives in `stage`."""
        if self.stage.startswith("Cold call"):
            return "Cold call"
        if self.stage.startswith("Renewal"):
            return "Renewal"
        if self.stage.startswith("Churn"):
            return "Churn post-mortem"
        return "Prospect"


class Turn(BaseModel):
    turn_id: str            # CALL-006#T045
    call_id: str
    idx: int
    ts: str                 # "07:23"
    seconds: int
    speaker: str
    side: Side
    role: str
    text: str


class Chunk(BaseModel):
    chunk_id: str
    call_id: str
    turn_ids: list[str]
    text: str


# ---------- ingest-time extraction ----------

FactType = Literal[
    "integration", "competitor", "objection", "pricing", "vendor_claim",
    "buying_signal", "risk", "requirement", "outcome", "next_step", "friction",
]
FactContext = Literal[
    "uses", "required", "evaluating", "replaced_by", "previously_used",
    "incident", "asked_about", "claimed_by_vendor", "other",
]


class Fact(BaseModel):
    type: FactType
    entity: str = Field(description="Canonical name of the tool/competitor/topic, e.g. 'Salesforce', 'SSO', 'pricing'")
    context: FactContext = Field(description="HOW it came up. A Salesforce outage is 'incident', not 'uses'.")
    statement: str = Field(description="One-sentence normalised fact. Write spoken numbers as digits too, e.g. 'eighteen hundred a month (£1,800/month)'.")
    speaker: str
    turn_ids: list[str]
    quote: str = Field(description="Verbatim excerpt from the cited turn, <= 25 words")


class CallCard(BaseModel):
    summary: str = Field(description="<= 120 words")
    tech_stack: list[str]
    competitors: list[str]
    key_objections: list[str]
    outcome: str
    next_steps: list[str]


class Extraction(BaseModel):
    card: CallCard
    facts: list[Fact]


class StoredFact(Fact):
    fact_id: str
    call_id: str
    side: Side
    verified: bool


# ---------- query time ----------

class EntityResolution(BaseModel):
    mention: str
    resolved_to: Optional[str] = Field(description="Exact company name from the catalogue, or null if no match")
    confidence: Literal["high", "medium", "low"]


class Resolution(BaseModel):
    question_type: Literal["lookup", "list", "theme", "compare", "judgement", "out_of_scope"]
    companies: list[EntityResolution] = Field(description="Customer/prospect companies the question names")
    call_types: list[Literal["Prospect", "Renewal", "Churn post-mortem", "Cold call"]] = Field(
        description="Restrict to these call types only if the question clearly implies them; else empty")
    search_terms: list[str] = Field(description="Keywords/entities to search for, incl. synonyms (e.g. 'SSO', 'SAML', 'single sign-on')")
    read_instruction: str = Field(description=(
        "What a reader who sees ONE call in isolation should extract so the findings can later be compared or "
        "aggregated across calls. For comparison/consistency/'most common'/'differences' questions, ask for the "
        "underlying statements (e.g. 'every claim OrbitFlow staff make about plans, features, connectors, security "
        "or pricing'), never for the comparison itself, which a single call cannot show."))
    assumptions: list[str]


class Finding(BaseModel):
    claim: str
    context: str = Field(description="How/why this came up, e.g. 'outage, not an integration'")
    turn_ids: list[str]
    quote: str = Field(description="Verbatim excerpt from the cited turn(s)")
    speaker: str
    stated_or_inferred: Literal["stated", "inferred"]


class CallReading(BaseModel):
    relevant: bool
    findings: list[Finding]


class Claim(BaseModel):
    text: str
    finding_ids: list[str] = Field(description="IDs of the findings that support this claim, e.g. ['F3','F7']")


class Conflict(BaseModel):
    topic: str
    description: str
    finding_ids: list[str]


class DraftAnswer(BaseModel):
    answer: str = Field(description="2-6 sentence summary. Reference claims as [C1], [C2]...; no facts that are not in a claim")
    claims: list[Claim]
    conflicts: list[Conflict]
    not_covered: list[str] = Field(description="Parts of the question the evidence does not answer")
    assumptions: list[str]


class VerifiedEvidence(BaseModel):
    finding_id: str
    turn_id: str
    call_id: str
    company: str
    speaker: str
    side: Side
    role: str
    ts: str
    quote: str
    context: str = ""
    stated_or_inferred: str = "stated"


class VerifiedClaim(BaseModel):
    text: str
    evidence: list[VerifiedEvidence]
    support: Literal["strong", "moderate", "weak"]


class Answer(BaseModel):
    question: str
    answer: str
    claims: list[VerifiedClaim]
    conflicts: list[Conflict]
    not_covered: list[str]
    assumptions: list[str]
    confidence: Literal["high", "medium", "low", "none"]
    calls_considered: list[str]
    calls_cited: list[str]
    removed_claims: list[dict] = []
    covered: bool = True
    trace_id: Optional[str] = None
