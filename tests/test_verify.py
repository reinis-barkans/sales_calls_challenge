"""Answer verifier: offline (entailment is monkeypatched or disabled)."""
from sci.models import Claim, Conflict, DraftAnswer, VerifiedEvidence
from sci.query import verify as V


def _ev(fid: str) -> VerifiedEvidence:
    return VerifiedEvidence(finding_id=fid, turn_id="CALL-001#T063", call_id="CALL-001", company="Acme Logistics",
                            speaker="Maya Chen", side="vendor", role="Account Executive", ts="06:31",
                            quote="Salesforce, Slack, Snowflake")


def _draft(answer: str, claims: list[tuple[str, list[str]]]) -> DraftAnswer:
    return DraftAnswer(answer=answer, claims=[Claim(text=t, finding_ids=f) for t, f in claims],
                       conflicts=[], not_covered=[], assumptions=[])


def test_removed_claim_sentence_is_deleted_not_relabelled():
    d = _draft("Acme uses Salesforce [C1]. Pinewood is moving to HubSpot [C2].",
               [("Acme uses Salesforce", ["F1"]), ("Pinewood is moving to HubSpot", ["F99"])])
    summary, claims, _, removed, _ = V.verify(d, [_ev("F1")], run_entailment=False)
    assert summary == "Acme uses Salesforce [1]."
    assert "HubSpot" not in summary
    assert [c.text for c in claims] == ["Acme uses Salesforce"]
    assert any("summary sentence" in r["reason"] for r in removed)


def test_uncited_summary_sentence_is_deleted():
    d = _draft("Residency came up on all 10 prospect calls. Acme said it has no requirement [C1].",
               [("Acme has no residency requirement", ["F1"])])
    summary, *_ = V.verify(d, [_ev("F1")], run_entailment=False)
    assert summary == "Acme said it has no requirement [1]."


def test_marker_after_full_stop_stays_with_its_sentence():
    d = _draft("Acme uses Salesforce. [C1] Ember needs Okta. [C2]",
               [("Acme uses Salesforce", ["F1"]), ("Ember needs Okta", ["F2"])])
    summary, *_ = V.verify(d, [_ev("F1"), _ev("F2")], run_entailment=False)
    assert summary == "Acme uses Salesforce [1]. Ember needs Okta [2]."


def test_all_sentences_dropped_falls_back_to_claims():
    d = _draft("Yes.", [("Acme uses Salesforce", ["F1"])])
    summary, *_ = V.verify(d, [_ev("F1")], run_entailment=False)
    assert summary == "Acme uses Salesforce [1]."


def test_no_surviving_claims_gives_fixed_message():
    d = _draft("Pinewood is moving to HubSpot [C1].", [("Pinewood is moving to HubSpot", ["F99"])])
    summary, claims, _, _, confidence = V.verify(d, [_ev("F1")], run_entailment=False)
    assert claims == [] and confidence == "none" and summary == V.NOT_ANSWERED


def test_missing_entailment_verdict_fails_closed(monkeypatch):
    # The checker returns a verdict for claim 1 only; claim 2 was skipped.
    monkeypatch.setattr(V, "entailment", lambda kept: {1: V.Verdict(claim_id="K1", verdict="supported", reason="ok")})
    d = _draft("Acme uses Salesforce [C1]. Ember needs Okta [C2].",
               [("Acme uses Salesforce", ["F1"]), ("Ember needs Okta", ["F2"])])
    summary, claims, _, removed, _ = V.verify(d, [_ev("F1"), _ev("F2")], run_entailment=True)
    assert [c.text for c in claims] == ["Acme uses Salesforce"]
    assert any(r["reason"] == "entailment: no verdict returned" for r in removed)
    assert "Okta" not in summary


def test_summary_drops_do_not_count_towards_claim_removal_rate():
    d = _draft("Framing sentence. Acme uses Salesforce [C1]. More framing.", [("Acme uses Salesforce", ["F1"])])
    *_, confidence = V.verify(d, [_ev("F1")], run_entailment=False)
    assert confidence == "high"


def test_conflict_needs_two_valid_findings():
    d = _draft("Acme uses Salesforce [C1].", [("Acme uses Salesforce", ["F1"])])
    d.conflicts = [Conflict(topic="SSO", description="x", finding_ids=["F1", "F99"])]
    _, _, conflicts, _, _ = V.verify(d, [_ev("F1")], run_entailment=False)
    assert conflicts == []
