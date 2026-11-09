"""Parse transcripts + manifest into Calls and Turns."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from sci.config import CALLS_DIR, MANIFEST, TURNS_FILE
from sci.models import Call, Turn

TURN_RE = re.compile(r"^\[(\d\d):(\d\d)\] ([^:]+): (.*)$")
VENDOR = "OrbitFlow"


@lru_cache
def load_calls() -> dict[str, Call]:
    rows = json.loads(MANIFEST.read_text())
    return {
        r["call_id"]: Call(company=r["prospect_company"], **{k: v for k, v in r.items() if k != "prospect_company"})
        for r in rows
    }


def parse_call(call: Call) -> list[Turn]:
    text = (CALLS_DIR / call.file).read_text()
    header, sep, body = text.partition("\nTRANSCRIPT\n")
    if not sep:
        raise ValueError(f"{call.file}: no TRANSCRIPT marker")
    header_company = re.search(r"^(?:PROSPECT|CUSTOMER): (.+)$", header, re.M)
    if not header_company or header_company.group(1).strip() != call.company:
        raise ValueError(f"{call.file}: header company does not match manifest")

    people = {p.name: p for p in call.participants}
    turns: list[Turn] = []
    for line in body.splitlines():
        m = TURN_RE.match(line)
        if not m:
            continue  # blank lines + synthetic-data disclaimer
        mm, ss, speaker, utterance = m.groups()
        p = people.get(speaker)
        if p is None:
            raise ValueError(f"{call.file}: unknown speaker {speaker!r}")
        idx = len(turns) + 1
        turns.append(Turn(
            turn_id=f"{call.call_id}#T{idx:03d}", call_id=call.call_id, idx=idx,
            ts=f"{mm}:{ss}", seconds=int(mm) * 60 + int(ss), speaker=speaker,
            side="vendor" if p.company == VENDOR else "customer", role=p.role, text=utterance,
        ))
    return turns


@lru_cache
def load_turns() -> dict[str, list[Turn]]:
    """call_id -> ordered turns. Parsed from source (fast, deterministic)."""
    return {cid: parse_call(c) for cid, c in load_calls().items()}


@lru_cache
def turn_index() -> dict[str, Turn]:
    return {t.turn_id: t for turns in load_turns().values() for t in turns}


def render_transcript(call_id: str) -> str:
    """Transcript with turn IDs inline, as given to LLMs."""
    c = load_calls()[call_id]
    head = f"{call_id} | {c.company} | {c.category} | {c.stage} | {c.date}\nParticipants: " + "; ".join(
        f"{p.name} ({p.role}, {p.company})" for p in c.participants)
    lines = [f"{t.turn_id.split('#')[1]} [{t.ts}] {t.speaker} ({t.side}): {t.text}" for t in load_turns()[call_id]]
    return head + "\n\n" + "\n".join(lines)


def write_turns() -> int:
    TURNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with TURNS_FILE.open("w") as f:
        for turns in load_turns().values():
            for t in turns:
                f.write(t.model_dump_json() + "\n")
                n += 1
    return n
