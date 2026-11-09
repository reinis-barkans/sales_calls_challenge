from sci.ingest.chunk import build_chunks
from sci.ingest.parse import load_calls, load_turns, render_transcript


def test_all_calls_parse():
    turns = load_turns()
    assert len(turns) == 20
    assert all(len(v) > 0 for v in turns.values())


def test_known_turn_counts():
    turns = load_turns()
    assert len(turns["CALL-016"]) == 23
    assert len(turns["CALL-008"]) == 312


def test_timestamps_monotonic_and_sides():
    for cid, turns in load_turns().items():
        secs = [t.seconds for t in turns]
        assert secs == sorted(secs), cid
        assert {t.side for t in turns} == {"vendor", "customer"}, cid


def test_customer_label_variants():
    calls = load_calls()
    assert calls["CALL-011"].company == "Lumen Retail Group"   # CUSTOMER: header
    assert calls["CALL-001"].company == "Acme Logistics"       # PROSPECT: header


def test_render_has_turn_ids():
    assert "T001 [00:00]" in render_transcript("CALL-001")


def test_chunks_cover_every_turn():
    covered = {t for c in build_chunks() for t in c.turn_ids}
    all_turns = {t.turn_id for ts in load_turns().values() for t in ts}
    assert covered == all_turns
