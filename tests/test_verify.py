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


def test_abbreviations_do_not_split_sentences():
    # Found in review: "e.g." / "vs." / "approx." were treated as sentence ends, so the
    # unmarked first half was deleted and a fragment survived.
    m = {1: 1, 2: 2}
    s, dropped = V.ground_summary("Several prospects need integrations, e.g. Salesforce and SAP [C1].", m)
    assert s == "Several prospects need integrations, e.g. Salesforce and SAP [1]." and not dropped
    s, dropped = V.ground_summary("Mostly price (approx. £1,800/month vs. a £1,000 budget) [C1][C2]. I.e. too high [C2].", m)
    assert s == "Mostly price (approx. £1,800/month vs. a £1,000 budget) [1][2]. I.e. too high [2]." and not dropped


def test_real_sentence_ends_still_split():
    s, dropped = V.ground_summary("Acme uses Salesforce [C1]. Unsupported framing. Ember needs Okta, etc. [C2]", {1: 1, 2: 2})
    assert s == "Acme uses Salesforce [1]. Ember needs Okta, etc [2]." and dropped == ["Unsupported framing."]


def test_split_subverdicts_worst_wins(monkeypatch):
    # Found live: Haiku returned 'K1-1', 'K1-2', ... and the last sub-verdict overwrote the rest.
    out = V.Verdicts(verdicts=[V.Verdict(claim_id="K1-1", verdict="unsupported", reason="no"),
                               V.Verdict(claim_id="K1-2", verdict="supported", reason="ok")])
    assert V._parse_verdicts(out, {1})[1].verdict == "unsupported"


def test_missing_verdicts_are_retried(monkeypatch):
    calls = []
    def fake(todo, attempt):
        calls.append([n for n, _, _ in todo])
        return V.Verdicts(verdicts=[V.Verdict(claim_id=f"K{n}", verdict="supported", reason="ok")
                                    for n, _, _ in todo if attempt or n == 1])
    monkeypatch.setattr(V, "_entail_call", fake)
    kept = [(1, Claim(text="a", finding_ids=["F1"]), []), (2, Claim(text="b", finding_ids=["F1"]), [])]
    assert set(V.entailment(kept)) == {1, 2} and calls == [[1, 2], [2]]
