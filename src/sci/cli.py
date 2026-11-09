"""CLI: `sci ingest`, `sci ask "..."`, `sci eval`."""
from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel

from sci.models import Answer

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def ingest():
    """Parse transcripts, run per-call extraction (cached), verify fact quotes."""
    from sci.ingest.extract import run_extraction
    from sci.ingest.parse import write_turns
    n = write_turns()
    console.print(f"Parsed {n} turns.")
    stats = run_extraction()
    total = sum(s["facts"] for s in stats)
    ok = sum(s["verified"] for s in stats)
    for s in stats:
        console.print(f"  {s['call_id']}: {s['facts']} facts, {s['verified']} quote-verified")
    console.print(f"[bold]Extraction: {total} facts, {ok} verified ({ok / max(total, 1):.0%}).[/bold]")


def render(ans: Answer, show_removed: bool = False):
    color = {"high": "green", "medium": "yellow", "low": "red", "none": "red"}[ans.confidence]
    console.print(Panel(ans.answer, title="ANSWER", subtitle=f"confidence: [{color}]{ans.confidence}[/{color}]"))
    if ans.assumptions:
        console.print("[bold]ASSUMPTIONS[/bold]")
        for a in ans.assumptions:
            console.print(f"  • {a}")
    if ans.claims:
        console.print("[bold]CLAIMS & EVIDENCE[/bold]")
        for i, c in enumerate(ans.claims, 1):
            console.print(f"  [{i}] {c.text}  [dim]({c.support})[/dim]")
            for e in c.evidence:
                console.print(f"      [cyan]{e.call_id}[/cyan] {e.company} · {e.speaker} ({e.side}, {e.role}) · "
                              f"{e.ts} · {e.turn_id.split('#')[1]}")
                console.print(f"        [italic]\"{e.quote}\"[/italic]")
    if ans.conflicts:
        console.print("[bold]CONFLICTS[/bold]")
        for c in ans.conflicts:
            console.print(f"  • {c.topic}: {c.description} [dim]({', '.join(c.finding_ids)})[/dim]")
    if ans.not_covered:
        console.print("[bold]NOT COVERED[/bold]")
        for n in ans.not_covered:
            console.print(f"  • {n}")
    if ans.removed_claims:
        console.print(f"[dim]{len(ans.removed_claims)} unsupported claim(s)/finding(s) removed by the verifier.[/dim]")
        if show_removed:
            for r in ans.removed_claims:
                console.print(f"  [dim]- {r.get('claim')}: {r.get('reason')}[/dim]")
    console.print(f"[dim]calls read: {', '.join(ans.calls_considered) or '-'} | trace: eval/results/traces/{ans.trace_id}.json[/dim]")


@app.command()
def ask(question: str, json_out: bool = typer.Option(False, "--json"),
        show_removed: bool = typer.Option(False, "--show-removed"),
        no_entailment: bool = typer.Option(False, "--no-entailment")):
    """Ask a question about the sales calls."""
    from sci.query.pipeline import ask as run
    ans = run(question, run_entailment=not no_entailment)
    if json_out:
        print(json.dumps(ans.model_dump(), indent=1))
    else:
        render(ans, show_removed)


@app.command(name="eval")
def eval_cmd(systems: str = typer.Option("pipeline,naive_rag,full_context"),
             only: str = typer.Option("", help="comma-separated question IDs")):
    """Run the evaluation suite and write eval/results/results.md."""
    import sys
    from sci.config import ROOT
    sys.path.insert(0, str(ROOT / "eval"))
    from run_eval import main
    main(systems.split(","), [q for q in only.split(",") if q])


if __name__ == "__main__":
    app()
