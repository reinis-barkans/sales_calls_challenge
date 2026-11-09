"""Call picking is deterministic given a Resolution, so it is tested without an LLM."""
from sci.models import EntityResolution, Resolution
from sci.query.candidates import pick_calls


def _res(**kw):
    base = dict(question_type="lookup", companies=[], call_types=[], search_terms=[], read_instruction="", assumptions=[])
    base.update(kw)
    return Resolution(**base)


def test_named_company_reads_only_that_call():
    r = _res(companies=[EntityResolution(mention="Acme Corp", resolved_to="Acme Logistics", confidence="medium")])
    assert pick_calls("What did Acme Corp say?", r).ordered() == ["CALL-001"]


def test_unknown_company_picks_nothing():
    r = _res(companies=[EntityResolution(mention="Northwind", resolved_to=None, confidence="low")])
    assert pick_calls("What did Northwind say about pricing?", r).ordered() == []


def test_call_type_filter_includes_all_of_type():
    r = _res(question_type="theme", call_types=["Churn post-mortem"])
    assert set(pick_calls("Why did customers leave?", r).ordered()) >= {"CALL-014", "CALL-015"}


def test_salesforce_search_covers_expected_calls():
    r = _res(question_type="list", search_terms=["Salesforce"])
    picked = set(pick_calls("Which customers mentioned integrations with Salesforce?", r).ordered())
    assert {"CALL-001", "CALL-004", "CALL-005", "CALL-009", "CALL-010"} <= picked


def test_absent_term_picks_nothing():
    r = _res(search_terms=["Gong"])
    assert pick_calls("Did anyone mention Gong?", r).ordered() == []


def test_company_name_match_ignores_case_and_spacing():
    r = _res(companies=[EntityResolution(mention="acme", resolved_to="acme  LOGISTICS", confidence="medium")])
    assert pick_calls("What did acme say?", r).ordered() == ["CALL-001"]


def test_non_catalogue_company_name_picks_nothing():
    # Found in review: a resolver output that isn't an exact catalogue name ("Acme Logistics Ltd")
    # fell through to a dataset-wide search and picked 15 calls about other companies.
    r = _res(companies=[EntityResolution(mention="Acme", resolved_to="Acme Logistics Ltd", confidence="medium")],
             search_terms=["workflow"])
    assert pick_calls("What did Acme say about their workflow?", r).ordered() == []
    from sci.query.candidates import unmatched_companies
    assert unmatched_companies(r) == ["Acme"]


def test_company_with_several_calls_reads_all(monkeypatch):
    from sci.query import candidates as C
    from sci.ingest.parse import load_calls
    calls = dict(load_calls())
    calls["CALL-099"] = calls["CALL-001"].model_copy(update={"call_id": "CALL-099"})
    monkeypatch.setattr(C, "load_calls", lambda: calls)
    r = _res(companies=[EntityResolution(mention="Acme", resolved_to="Acme Logistics", confidence="high")])
    assert C.pick_calls("What did Acme say?", r).ordered() == ["CALL-001", "CALL-099"]


def test_partial_name_unique_match_reads_that_company_and_states_assumption():
    r = _res(companies=[EntityResolution(mention="Acme", resolved_to="Acme", confidence="medium")])
    cand = pick_calls("What did Acme say?", r)
    assert cand.ordered() == ["CALL-001"]
    assert any("Acme Logistics" in a for a in cand.assumptions)


def test_exact_name_adds_no_assumption():
    r = _res(companies=[EntityResolution(mention="Acme", resolved_to="Acme Logistics", confidence="high")])
    assert pick_calls("What did Acme say?", r).assumptions == []


def test_partial_name_matching_several_companies_picks_nothing():
    # "Group" is in both Lumen Retail Group and Trafford Dental Group: refuse to guess.
    r = _res(companies=[EntityResolution(mention="Group", resolved_to="Group", confidence="low")], search_terms=["pricing"])
    assert pick_calls("What did Group say about pricing?", r).ordered() == []


def test_partial_match_is_whole_words_only():
    for name in ["Acm", "cme Logistics", "ac"]:
        r = _res(companies=[EntityResolution(mention=name, resolved_to=name, confidence="low")])
        assert pick_calls(f"What did {name} say?", r).ordered() == [], name
