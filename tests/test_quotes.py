from sci.ingest.parse import load_turns
from sci.quotes import fix_turn_id, match_quote, normalise


def _tid(call_id: str, needle: str) -> str:
    return next(t.turn_id for t in load_turns()[call_id] if needle in t.text)


def test_exact_quote_matches():
    tid = _tid("CALL-006", "SSO's included on all our plans")
    m = match_quote("SSO's included on all our plans, that's standard", [tid])
    assert m and m[0].speaker == "Alastair McCrae"


def test_quote_with_case_punct_and_ellipsis():
    tid = _tid("CALL-012", "SAML SSO is Enterprise")
    assert match_quote("saml sso is enterprise ... that's the one that would actually hurt", [tid])


def test_altered_quote_rejected():
    tid = _tid("CALL-006", "SSO's included on all our plans")
    assert match_quote("SSO is included on the Enterprise plan only", [tid]) is None


def test_wrong_call_rejected():
    tid = _tid("CALL-001", "")  # any turn in a different call
    assert match_quote("SSO's included on all our plans, that's standard", [tid]) is None


def test_fake_turn_id_rejected():
    assert match_quote("SSO's included on all our plans", ["CALL-006#T999"]) is None


def test_neighbour_turn_tolerance():
    tid = _tid("CALL-006", "SSO's included on all our plans")
    call, n = tid.split("#T")
    prev = f"{call}#T{int(n) - 1:03d}"
    assert match_quote("SSO's included on all our plans", [prev])


def test_tiny_quote_rejected():
    tid = _tid("CALL-006", "SSO's included on all our plans")
    assert match_quote("SSO", [tid]) is None


def test_tags_stripped():
    assert normalise("Well [pause] the BAA — is the gate.") == "well the baa is the gate"


def test_fix_turn_id():
    assert fix_turn_id("T45", "CALL-006") == "CALL-006#T045"
    assert fix_turn_id("CALL-006#T045") == "CALL-006#T045"


def test_cross_speaker_stitched_quote_rejected():
    # Found live: a reader joined Dermot's line and Maya's reply with '...'.
    t_dermot = _tid("CALL-016", "we're not looking at anything")
    assert match_quote("we're not looking at anything ... I won't call you again this year", [t_dermot]) is None


def test_short_quote_accepted_only_as_whole_turn():
    short = next(t for t in load_turns()["CALL-019"] if t.text.strip() == "Eleven.")
    assert match_quote("Eleven.", [short.turn_id])
    long_tid = _tid("CALL-019", "Across eleven practices")
    assert match_quote("eleven", [long_tid]) is None
