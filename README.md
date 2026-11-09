# Sales Call Intelligence

Ask questions about 20 OrbitFlow sales-call transcripts. Every claim in an answer cites the call, speaker, timestamp, turn ID and a quote **verified word for word in code**. If nothing verifies, the system declines.

```
$ uv run sci ask "Which customers mentioned integrations with Salesforce?"
ANSWER  Five prospects raised Salesforce in an integration context: Acme Logistics, DeltaWorks ... [1]
  [3] Ember Financial listed Salesforce among required integrations ...  (strong)
      CALL-005 Ember Financial · Noah Williams (customer, VP Operations Technology) · 15:24 · T108
        "Salesforce, Snowflake, Slack, Okta, Jira, and an internal event bus. Required: all of those ..."
calls read: CALL-001, ... CALL-011   (Lumen's Salesforce *outage* was read and correctly excluded)
```

## Setup and run

Requires [uv](https://docs.astral.sh/uv/) (installs Python 3.12) and an Anthropic API key.

```bash
uv sync
cp .env.example .env                      # set ANTHROPIC_API_KEY
uv run sci ask "Why did customers who left decide to leave?"   # add --json or --show-removed
uv run pytest -q                          # no API key needed: parser, quote verifier, answer verifier, call picking
                                          # (call-picking tests download the bge-small model on first run)
```

`artifacts/` (turns, extracted facts, embeddings) is committed, so you don't need to run ingest. The LLM response cache is gitignored, so a fresh clone makes live calls (cents per question). The first query downloads the bge-small embedding model (~130 MB). To rebuild the facts: `uv run sci ingest`.

**Evaluation**

```bash
make eval            # dev set (21 Qs), 3 systems -> eval/results/results.md
make eval-holdout    # held-out set (10 Qs)       -> eval/results/results_holdout.md
uv run python eval/run_eval.py --systems pipeline --only Q03,Q07
```

Each run writes per-question answers and grades (`results*.json`), plus a trace per question in `eval/results/traces/`.

## Approach

```
INGEST (once, cached)   parse turns (CALL-006#T066, speaker, side, role) ─► BM25 + bge-small over 8-turn chunks
                        ─► per-call extraction (Haiku) ─► typed facts incl. tone/friction, each quote-verified
QUERY   1 resolve (Haiku): companies, call types, search terms, what each reader should extract
        2 pick calls (code): metadata ∪ fact matches ∪ BM25 ∪ vectors, each with the reason it was picked
        3 read each picked call IN FULL, in parallel (Haiku) ─► findings; quote + speaker checked in code
        4 nothing verified? ─► "not covered" response from code (no answering model)
        5 combine (Sonnet): sees only verified findings; every claim cites finding IDs
        6 verify: drop uncited claims, entailment check per claim (fails closed), drop summary
          sentences without a surviving citation, confidence by rules ─► answer + trace
```

## Key decisions

| Decision | Why (alternative) |
|---|---|
| **Read picked calls in full, one per prompt** | Chunks lose context and passing mentions (naive RAG); one prompt with every transcript costs ~170K tokens per question and doesn't scale. Both run as baselines. The `facts_only` ablation shows full reads mainly pay off on "why" and nuance questions (see Results). |
| **Calls are picked in code** | Whether the right calls get read limits everything else, so it's deterministic, unit-tested and records why each call was picked. |
| **Quotes and speakers verified in code** | Must match the cited turn (±1 turn, one speaker, the reader's stated speaker). Invented or misattributed quotes are rejected. |
| **Claims cite finding IDs; "not covered" decided by code** | The answering model can't add evidence, and has nothing to make up from. The summary is grounded too: a summary sentence without a citation, or citing a removed claim, is deleted, so the headline can't say more than the verified claims. |
| **Entailment check + rule-based confidence** | A real quote can still be misread (Lumen's Salesforce *outage* ≠ integration). Confidence comes from stated vs inferred evidence, conflicts and removals, not from the model's own rating. |
| **Facts are an index, not evidence** | Extraction is lossy, so facts help pick calls (incl. tone via `friction` tags); answers cite full reads. |
| **Haiku for reading, Sonnet for combining, effort low; prompt caching** | Most calls are reads, and the verifier limits their errors. Cached transcripts cut repeat reads to cached-token prices. |

## Assumptions

- Transcript speaker attribution is correct. Users are sales managers who want answers they can check, not polished prose.
- Company names are resolved against the manifest. A close match ("Acme Corp" → Acme Logistics) is answered with the assumption stated; an unknown company is declined.
- "Prospects / renewals / customers who left / cold calls" map to the manifest's `stage` (its `call_type` only has Prospect / Existing customer).

## Evaluation

**Two gold sets**, each label checked against the transcripts:
- **dev** (`questions.yaml`, 21 Qs): the instruction examples plus traps (Lumen's outage, Alastair vs Leo on SSO, Verity's stated vs real reason for leaving, Trafford's 14 → 11 practices, "Acme Corp", should-decline questions). I tuned on this set.
- **held-out** (`holdout.yaml`, 10 Qs): written after the system was frozen and **never tuned on**. This is the honest number.

| Metric | Why |
|---|---|
| Selection recall (expected calls were read) | Measures retrieval separately from answer quality |
| Cited recall / list precision / false matches | List questions: all of them, only them, no keyword traps |
| Citation validity (before removal) | How often each system misquotes (baselines go through the same checker) |
| Abstention accuracy, conflict recall | Requirement 3: decline when the data has no answer, and surface contradictions |
| Fact score (Sonnet judge per gold fact) | Answer quality; grounding is measured in code, not by the judge |
| Tokens / latency | Cost and scaling trade-off |

Compared against `naive_rag` (top 8 BM25 chunks), `full_context` (all 20 transcripts in one cached prompt) and `facts_only`, an ablation: the same pipeline, but it answers from the facts stored at ingest instead of reading the picked calls.

### Results (run 7, current code; full tables in `eval/results/results*.md`, failure analysis in `failures.md`)

| | pipeline | naive RAG | full context | facts only |
|---|---|---|---|---|
| Fact score, dev (21, tuned on) | **92%** | 60% | **92%** | **92%** |
| **Fact score, held-out (10, never tuned on)** | **89%** | 78% | 86% | **89%** |
| Selection recall, dev / held-out | 100 / 100% | 66 / 90% | 100 / 100% | 100 / 100% |
| Abstention, dev / held-out | 100 / 100% | 76 / 100% | 100 / 100% | 100 / 90%¹ |
| Conflict recall, dev / held-out | 100 / 100% | 50 / 100% | 100 / 100% | 100 / 100% |
| Citation validity (before removal) | 99% | 99% | 100% | 100%² |
| Avg input tokens / question, dev | 94K | 4K | 168K | 52K |
| Latency / question, held-out (live)³ | 22 s | 6 s | 10 s | 14 s |

¹ For "Did any prospect mention Microsoft Copilot?" it gave a correct, evidence-backed *no* instead of declining; the metric counts that as a failure. ² By construction: stored facts were verified at ingest. ³ From runs that made live calls (pipeline run 6, others run 5); re-runs hit the disk cache, and `run_eval.py` only times questions with no cache hits.

**What this shows**
- **Naive RAG fails on anything spanning calls** (dev 60%, conflicts 50%). The lookup-heavy held-out set flatters it.
- **Full context is strong at 20 calls** but costs ~168K tokens on every question and doesn't scale.
- **The pipeline holds up on unseen questions** (dev 92%, held-out 89%), with 100% selection recall, abstention and conflict recall on both. An earlier 97% on dev was inflated: it included claims the entailment check had silently skipped (failures.md B10) and favourable run noise. The remaining misses are *partial* grades, where the summary leaves out a detail its own evidence contains: a combine-step weakness.
- **Reading picked calls in full mostly matches answering from stored facts** (`facts_only`: same scores at ~55% of the tokens). Reading wins where nuance sits in the surrounding conversation: the real vs stated reason for churn (Q06 100% vs 50%, Q09 100% vs 83%) and the cross-call vendor inconsistency (Q07 100% vs 67%). That supports the production design below: answer from facts by default, and read in full for why, nuance or comparison questions.
- **Noise is large.** Current models don't accept `temperature`, so re-running combine on unchanged code moved single questions by up to 50 points (Q01). The uncalibrated judge also graded the same "Acme Corp" assumption present in one run and absent in the next (Q02). Treat differences under ~10 points as noise.

## Known limitations

- **Readers see one call each.** Cross-call comparisons depend on the resolve step asking readers for the right raw material.
- **Call picking misses topics with no matching alias, fact or embedding.** Tone works through `friction` tags (search alone found 2 of 20 rude calls), but untagged behaviours still rely on search.
- **Interpretation isn't verified.** Quotes and speakers are; a reader's "sarcastic" or "curt" is marked `inferred` and lowers confidence. The entailment check is itself a model.
- **Broad answers run long**, and judgement questions ("most likely to buy") are still the model's judgement.
- **Small, self-written gold sets**; the judge hasn't been calibrated against hand grades.

## With more time

**Another day:** calibrate the judge against hand grades; get questions written by someone else; ablations (no vectors, no facts, no entailment); rank and cap secondary claims to shorten answers.

**Production**
- **Scale moves the reading to ingest.** Re-reading picked calls on every question is the most accurate option at 20 calls, but it costs the same on every question. At 10K+ calls: read each call once at ingest into verified facts and tags (Postgres + pgvector), answer lists, counts and themes from them, re-read only to drill into a few calls, and backfill new tags across all calls with the Batches API. Trade-off: extraction keeps only what it's asked for, so it should collect broadly. The verification layer and the eval carry over unchanged.
- **Streaming ingest:** process each call as it arrives (parse → extract → verify → index). Versioned prompts trigger re-extraction in the background.
- **Security:** redact personal data or use zero-retention processing; apply access control as a filter *before* picking calls; keep an audit log. Transcripts are untrusted input, and answers can only cite real turns.
- **Monitoring:** track verified-quote, removal and decline rates per release. `llm.py` is the only provider-specific module, so cheaper reader models can be compared on the eval.

## Layout

```
src/sci/   cli.py llm.py quotes.py models.py config.py aliases.json
           ingest/ (parse chunk index extract)  query/ (resolve candidates read combine verify pipeline)  baselines/
eval/      questions.yaml holdout.yaml run_eval.py judge.py results/ (results*.md, failures.md, traces/)
tests/     artifacts/ (turns, facts, cards, vectors; llm_cache/ gitignored)
```
