"""Run the gold set against one or more systems and write eval/results/results.md
plus per-question JSON.

Metrics (deterministic unless noted):
  selection_recall  expected calls that the system put in front of the answering model
  cited_recall      expected calls the final answer actually cites
  cited_precision   cited calls that are expected (list questions only)
  false_match       answer cites a must_not_cite call (known keyword trap)
  citation_validity verbatim-verified citations / all citations, BEFORE any removal
  abstention        declined iff expect_covered is false
  conflict_flagged  answer surfaces a conflict when expect_conflict
  fact_score        LLM judge: present=1, partial=0.5 averaged over key facts
  tokens / latency  per question
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from judge import judge  # noqa: E402
from sci import llm  # noqa: E402

RESULTS = ROOT / "eval" / "results"
SETS = {"dev": "questions.yaml", "holdout": "holdout.yaml"}


def _system(name: str):
    if name == "pipeline":
        from sci.query.pipeline import ask
        return ask
    if name == "naive_rag":
        from sci.baselines.naive_rag import ask
        return ask
    if name == "full_context":
        from sci.baselines.full_context import ask
        return ask
    if name == "facts_only":
        from sci.baselines.facts_only import ask
        return ask
    raise ValueError(name)


def _citation_stats(ans, name: str) -> tuple[int, int]:
    if name != "pipeline":
        s = ans.__dict__.get("_citation_stats", {"total": 0, "valid": 0})
        return s["total"], s["valid"]
    # Pipeline: findings produced by the readers vs those that verified.
    tr = ans.__dict__.get("_trace", {})
    valid = len(tr.get("findings", []))
    rejected = sum(1 for r in tr.get("rejected_findings", []) if r.get("reason", "").startswith("quote"))
    return valid + rejected, valid


def score(q: dict, ans, name: str, usage: dict, latency: float) -> dict:
    exp = set(q.get("expected_calls") or [])
    considered, cited = set(ans.calls_considered), set(ans.calls_cited)
    total, valid = _citation_stats(ans, name)
    row = {
        "id": q["id"], "category": q["category"], "system": name,
        "selection_recall": len(exp & considered) / len(exp) if exp else None,
        "cited_recall": len(exp & cited) / len(exp) if exp else None,
        "cited_precision": (len(exp & cited) / len(cited) if cited else 0.0) if q["category"] == "list" else None,
        "false_match": bool(set(q.get("must_not_cite") or []) & cited) if q.get("must_not_cite") else None,
        "citations": total, "citations_valid": valid,
        "abstention_ok": ans.covered == q.get("expect_covered", True),
        "conflict_flagged": (len(ans.conflicts) > 0) if q.get("expect_conflict") else None,
        "confidence": ans.confidence, "covered": ans.covered,
        "input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"],
        "llm_calls": usage["llm_calls"], "latency_s": round(latency, 1),
        "removed_claims": len(ans.removed_claims),
    }
    grades = judge(q["question"], q.get("key_facts") or [], ans) if q.get("expect_covered", True) else []
    row["fact_score"] = (sum({"present": 1, "partial": 0.5}.get(g.grade, 0) for g in grades) / len(grades)) if grades else None
    row["grades"] = [g.model_dump() for g in grades]
    return row


def run_one(name: str, q: dict) -> dict:
    ask = _system(name)
    start = len(llm.USAGE)
    t0 = time.time()
    try:
        ans = ask(q["question"])
    except Exception as e:  # keep the run going; record the failure
        return {"id": q["id"], "system": name, "category": q["category"], "error": repr(e)}
    latency = time.time() - t0
    # USAGE is shared across threads; attribute by step names only when run sequentially per system.
    usage = llm.usage_summary(llm.USAGE[start:])
    row = score(q, ans, name, usage, latency)
    row["answer"] = ans.model_dump()
    return row


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _fmt(x, pct=True):
    if x is None:
        return "–"
    if isinstance(x, bool):
        return "✓" if x else "✗"
    return f"{x:.0%}" if pct else f"{x:,.0f}"


def summarise(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]
    cit_t = sum(r["citations"] for r in ok)
    cit_v = sum(r["citations_valid"] for r in ok)
    return {
        "questions": len(rows), "errors": len(rows) - len(ok),
        "selection_recall": _mean([r["selection_recall"] for r in ok]),
        "cited_recall": _mean([r["cited_recall"] for r in ok]),
        "list_precision": _mean([r["cited_precision"] for r in ok]),
        "false_matches": sum(1 for r in ok if r["false_match"]),
        "citation_validity": cit_v / cit_t if cit_t else None,
        "abstention_acc": _mean([1.0 if r["abstention_ok"] else 0.0 for r in ok]),
        "conflict_recall": _mean([1.0 if r["conflict_flagged"] else 0.0 for r in ok if r["conflict_flagged"] is not None]),
        "fact_score": _mean([r["fact_score"] for r in ok]),
        "avg_input_tokens": _mean([r["input_tokens"] for r in ok]),
        "avg_latency_s": _mean([r["latency_s"] for r in ok]),
    }


def write_report(all_rows: dict[str, list[dict]], gold: str = "dev"):
    RESULTS.mkdir(parents=True, exist_ok=True)
    systems = list(all_rows)
    sums = {s: summarise(r) for s, r in all_rows.items()}
    metrics = [("Fact score (judge)", "fact_score", True), ("Selection recall", "selection_recall", True),
               ("Cited-call recall", "cited_recall", True), ("List precision", "list_precision", True),
               ("False matches (must_not_cite)", "false_matches", False), ("Citation validity", "citation_validity", True),
               ("Abstention accuracy", "abstention_acc", True), ("Conflict recall", "conflict_recall", True),
               ("Avg input tokens / question", "avg_input_tokens", False), ("Avg latency (s, uncached)", "avg_latency_s", False),
               ("Errors", "errors", False)]
    src = SETS[gold]
    out = [f"# Evaluation results ({gold} set)", "", f"Gold set: {len(next(iter(all_rows.values())))} questions (eval/{src}).", "",
           "| Metric | " + " | ".join(systems) + " |", "|---|" + "---|" * len(systems)]
    for label, key, pct in metrics:
        out.append(f"| {label} | " + " | ".join(_fmt(sums[s][key], pct) for s in systems) + " |")
    out += ["", "## Per question", "", "| Q | Category | " + " | ".join(f"{s} facts / abst / cited-recall" for s in systems) + " |",
            "|---|---|" + "---|" * len(systems)]
    by_id: dict[str, dict[str, dict]] = {}
    for s, rows in all_rows.items():
        for r in rows:
            by_id.setdefault(r["id"], {})[s] = r
    for qid in sorted(by_id):
        cells = []
        for s in systems:
            r = by_id[qid].get(s, {})
            if "error" in r or not r:
                cells.append("ERROR")
            else:
                cells.append(f"{_fmt(r['fact_score'])} / {_fmt(r['abstention_ok'])} / {_fmt(r['cited_recall'])}")
        cat = next(iter(by_id[qid].values())).get("category", "")
        out.append(f"| {qid} | {cat} | " + " | ".join(cells) + " |")
    stem = "results" if gold == "dev" else f"results_{gold}"
    (RESULTS / f"{stem}.md").write_text("\n".join(out) + "\n")
    (RESULTS / f"{stem}.json").write_text(json.dumps({"summary": sums, "rows": all_rows}, indent=1, default=str))
    print("\n".join(out[:len(metrics) + 6]))


def main(systems: list[str], only: list[str], gold: str = "dev", merge: bool = False):
    qs = yaml.safe_load((ROOT / "eval" / SETS[gold]).read_text())
    if only:
        qs = [q for q in qs if q["id"] in only]
    all_rows = {}
    for name in systems:
        print(f"Running {name} on {len(qs)} questions...")
        # Sequential per question so token accounting per question is exact; each pipeline run is internally parallel.
        rows = [run_one(name, q) for q in qs]
        for r in rows:
            if "error" in r:
                print(f"  {r['id']}: ERROR {r['error']}")
        all_rows[name] = rows
    if merge:
        # Add/replace these systems' columns in the existing report instead of overwriting it.
        stem = "results" if gold == "dev" else f"results_{gold}"
        prev = json.loads((RESULTS / f"{stem}.json").read_text())["rows"]
        all_rows = {**{k: v for k, v in prev.items() if k not in all_rows}, **all_rows}
    write_report(all_rows, gold)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--systems", default="pipeline,naive_rag,full_context,facts_only")
    p.add_argument("--only", default="")
    p.add_argument("--set", default="dev", choices=list(SETS), help="dev = tuned-on questions; holdout = never tuned on")
    p.add_argument("--merge", action="store_true", help="keep other systems' rows from the existing results file")
    a = p.parse_args()
    main(a.systems.split(","), [x for x in a.only.split(",") if x], a.set, a.merge)
