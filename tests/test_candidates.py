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
