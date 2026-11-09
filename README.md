# Sales Call Intelligence

Ask questions about 20 OrbitFlow sales-call transcripts and get answers you can check: every claim comes with the call, speaker, timestamp, turn ID and a quote that has been verified word for word against the transcript.

```
$ uv run sci ask "Which customers mentioned integrations with Salesforce?"
ANSWER  Five prospects raised Salesforce in an integration context: Acme Logistics, DeltaWorks ... [1]
CLAIMS & EVIDENCE
  [3] Ember Financial listed Salesforce among required integrations ...  (strong)
      CALL-005 Ember Financial · Noah Williams (customer, VP Operations Technology) · 15:24 · T108
        "Salesforce, Snowflake, Slack, Okta, Jira, and an internal event bus. Required: all of those ..."
NOT COVERED  ...
calls read: CALL-001, ... CALL-011 ...   (Lumen's Salesforce *outage* was read and correctly excluded)
```

---

## Setup and run

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 for the project) and an Anthropic API key.

```bash
uv sync                                   # or: make setup
cp .env.example .env                      # then set ANTHROPIC_API_KEY
uv run sci ask "Why did customers who left decide to leave?"
uv run sci ask "..." --show-removed       # also list claims the verifier removed
uv run sci ask "..." --json               # machine-readable answer
uv run pytest -q                          # 22 offline tests (parser, quote verifier, call picking)
```

`artifacts/` is committed (turns, extracted facts, chunk embeddings), so you don't have to run ingest yourself. The LLM response cache (`artifacts/llm_cache/`) is gitignored: it fills up with one file per call, so a fresh clone makes live API calls for questions (cents each). To rebuild the facts from scratch: `uv run sci ingest` (about 1 minute, cents). The first query on a new machine downloads the small embedding model (bge-small, ~130 MB).

**Evaluation**

```bash
uv run python eval/run_eval.py                          # all 3 systems -> eval/results/results.md
uv run python eval/run_eval.py --systems pipeline --only Q03,Q07
```

Each run writes `eval/results/results.md` (the summary tables), `results.json` (per-question answers and grades) and one trace per question in `eval/results/traces/`.

---

## Approach

```
INGEST (offline, cached)
  calls/*.txt + manifest ─► parse turns (CALL-006#T066, speaker, vendor/customer side, role)
                          ─► 8-turn chunks ─► BM25 index + bge-small embeddings
                          ─► per-call LLM extraction ─► facts (entity, context, statement, quote) ─► quote-verified

QUERY
  question ─► 1 resolve (Haiku): companies, call-type filters, search terms, per-call reading instruction
           ─► 2 pick calls (code): metadata ∪ fact matches ∪ BM25 ∪ vectors; each call records why it was picked
           ─► 3 read each picked call IN FULL, separately, in parallel (Haiku) ─► findings + verbatim quotes
                  └─ each quote is checked against the cited turn in code; anything that fails is dropped
           ─► 4 nothing verified? ─► "not covered" response from code; the answering model is never called
           ─► 5 combine (Sonnet): sees ONLY verified findings + counts computed in code; claims cite finding IDs
           ─► 6 verify: drop claims citing no valid finding ─► entailment check (Haiku) ─► confidence by rules
           ─► answer + evidence + conflicts + not-covered + assumptions   (+ trace JSON)
```

The idea: **pick calls cheaply and deterministically, read the picked calls in full, and only let the answering model see evidence that has been verified in code.**

## Key decisions

| Decision | Alternative considered | Why |
|---|---|---|
| **Read each picked call in full, separately** | Naive RAG (top-k chunks); put all 20 transcripts in one prompt | Chunks lose surrounding context (an answer next to the question it replies to) and miss passing mentions. Putting everything in one prompt costs ~95K tokens per question, mixes calls up (wrong speaker or company), and stops working once the data outgrows the context window. Reading one call at a time gives the model a narrow job, and cost grows with the number of calls picked rather than the size of the dataset. Both alternatives are run as baselines in the eval. |
| **Calls are picked in code, not by an LLM** | Let a router LLM choose the calls | Whether the right calls get read is the main limit on answer quality, so it should be deterministic and testable (`tests/test_candidates.py`). Each picked call records why it was picked, which makes misses easy to diagnose. |
| **Extracted facts are an index, not evidence** | Answer list questions straight from extracted facts | Extraction is lossy, so facts are only used to pick calls (and to make spoken prices searchable: "eighteen hundred a month" → £1,800). Every claim in an answer cites a full read of the call. |
| **Verbatim quote check in code** | Ask the model to cite accurately | A quote has to match the cited turn after normalisation (tags like `[pause]` stripped, "..." allowed, at most ±1 neighbouring turn, **one speaker only**). Invented or misattributed quotes can't get through. |
| **Claims cite finding IDs, not new quotes** | The combine step writes its own quotes | The final model can only point at evidence that has already been verified. It cannot add a new quote. |
| **"Not covered" response from code** | Ask the model to say "I don't know" | If no verified finding exists, the answering model is never called, so there is nothing for it to make up. |
| **Entailment check per claim** | Trust any claim that has a real quote | A genuine quote can still be misread (e.g. a Salesforce *outage* read as an integration). A cheap Haiku check removes claims the quotes don't support. |
| **Confidence from rules** | The model rates its own confidence | Based on stated vs inferred findings, entailment verdicts, conflicts and how many claims were removed. |
| **Per-call reading instruction** | Pass the raw question to every reader | Found during testing: a reader that sees one call can't spot a *cross-call* contradiction, so it dropped Leo Grant's "SAML SSO is Enterprise" as irrelevant. The resolve step now tells readers what raw material to collect ("every claim OrbitFlow staff make about plans/features...") and the combine step does the comparison. |
| **BM25 + local embeddings** | Embeddings only | Exact names matter here (Salesforce, Tray.io, BAA). Embeddings (bge-small via ONNX, no API key) only *add* calls above a similarity floor tuned on this data. Absent topics like "Gong" score at most 0.62 and real ones 0.65–0.72, so I keep them as a recall source rather than the main signal. |
| **Haiku for the high-volume steps, Sonnet for combine and judge, effort `low`** | Sonnet everywhere | Reading and extraction make up most of the calls, and the verifier keeps their failure modes in check. |
| **Prompt caching (1h TTL) on transcripts, corpus and catalogue** | No caching | Transcripts never change, and the same call is read for many questions. A second question on a call cost 2.2K cached tokens instead of full price, and latency fell from 10.2s to 3.3s. |
| **Disk cache for LLM responses** (local, gitignored) | — | Eval re-runs on the same machine are free and reproducible (current models don't accept `temperature`). |

## Assumptions

- Speaker attribution in the transcripts is correct, as the dataset README states. The system relies on it for vendor vs customer reasoning.
- Users are sales managers who want answers they can check, not polished prose. Evidence and caveats matter more than fluency.
- The company named in a question is resolved against the manifest. A close match ("Acme Corp" → Acme Logistics) is answered with the assumption stated. An unknown company ("Northwind") is declined rather than answered from other calls.
- "Prospects", "renewals", "customers who left" and "cold calls" map to the call sub-type in `stage`. The manifest's `call_type` only distinguishes *Prospect* from *Existing customer*.
- English-only, static dataset of 20 calls. Growth and streaming ingest are covered under *With more time*.

## Evaluation

**What I measure, and why.** 18 gold questions (`eval/questions.yaml`), each label checked against the transcripts with grep and by reading. They cover single-call lookups, an alias, list questions, themes, comparisons, conflicts, a near miss (HIPAA → the BAA discussion in CALL-002) and three questions the system should decline. The planted traps all appear: Lumen's Salesforce outage, Alastair's SSO and native-connector claims against other reps, Verity's stated reason for leaving vs the real one, the Trafford practice count corrected from 14 to 11, and "Acme Corp".

| Metric | How | Why |
|---|---|---|
| Selection recall | expected calls ⊆ calls read | Whether the right calls get read is the main limit; measured separately from answer quality |
| Cited-call recall / list precision | expected vs cited calls | List questions: did it find all of them and only them |
| False matches | cites a `must_not_cite` call | Catches keyword traps (Lumen's Salesforce outage) |
| Citation validity | verbatim-verified / all citations, before removal | How often each system invents or misquotes evidence (baselines' quotes go through the same checker) |
| Abstention accuracy | declined iff expected | Requirement 3: no answer when the data doesn't contain one, and no false declines |
| Conflict recall | conflicts reported where expected | Requirement 3: contradictions are shown, not smoothed over |
| Fact score | LLM judge (Sonnet) per key fact: present / partial / absent / contradicted | Answer quality. The judge sees the gold facts and the answer, not the transcripts. Grounding is measured separately, in code |
| Tokens / latency | from API usage | Cost and scaling trade-off between the three systems |

**Systems compared:** `pipeline` (this system), `naive_rag` (top 8 BM25 chunks → Sonnet), `full_context` (all 20 transcripts in a cached prompt → Sonnet).

### Results (run 2; full tables in [eval/results/results.md](eval/results/results.md), run 1 in `results_run1.md`)

| Metric | pipeline | naive RAG | full context |
|---|---|---|---|
| Fact score (judge) | **98%** (run 1: 87%) | 63% | 93% |
| Selection recall | 100% | 69% | 100% |
| Cited-call recall | 100% | 66% | 99% |
| Citation validity (before removal) | 99% | 100% | 100% |
| Abstention accuracy (3 should-decline + 15 should-answer) | **100%** | 83% | **100%** |
| Conflict recall | **100%** | 75% | **100%** |
| Avg input tokens / question | 80K | 4K | 168K |
| Avg latency, uncached (run 1) | 22 s | 5 s | 9 s |

**What this shows**

- **Naive RAG is not good enough.** It missed both churn reasons, missed the vendor inconsistency, declined questions it should have answered (Q06, Q07, Q18) and found 0 of 7 expected calls for "which competitors". Top-k chunks can't answer questions that span the dataset.
- **Full context is a strong baseline at this size.** It beat the pipeline in run 1 (93% vs 87%). It is simple and fast, because one cached prompt holds all 20 calls. Its problems are scale and cost: ~168K input tokens on *every* question whatever its scope, and it stops working once the corpus outgrows the context window.
- **The pipeline matches or beats it at about half the input tokens**, and its cost grows with the number of calls picked (a single-company question reads 1 call), not with the size of the dataset. Every claim it makes is backed by a quote verified in code, and "not covered" never involves the answering model.
- **Run 1 → run 2:** the fix came from reading the failures, not from retrieval: one gold-label error, and a combine prompt that had become too terse. Retrieval, reading and verification were unchanged. See [eval/results/failures.md](eval/results/failures.md).
- **Caveat:** run 2 was tuned on the same 18 questions, with no held-out set, and the baselines got no tuning, so treat 98% as optimistic. One question ≈ 6 points.
- **Citation validity is high for all three**, because current models quote well when they have the text. The verifier's value is the guarantee, plus what it removes on harder cases (it rejected a cross-speaker stitched quote during development).
- **Metric limits** (in failures.md): `must_not_cite` flags the pipeline for citing Lumen *in order to exclude it*, and list precision is low because `expected_calls` is a minimal subset for broad list questions.

## Known limitations

- **Cross-call reasoning depends on the reading instruction.** Readers see one call each. If the resolve step writes a poor reading instruction, statements that only matter in comparison get dropped (the vendor-inconsistency failure, now fixed for that question type but not guaranteed in general).
- **Call picking is only as good as its sources.** A call that mentions a topic only in words that match no alias, no extracted fact and no nearby embedding won't be read. Recall is favoured (low BM25 cutoff), which costs extra Haiku reads.
- **Verbose answers on broad questions.** Combine tends to list weak secondary cases alongside the main finding. The verifier removes unsupported claims but can't judge what matters most.
- **Judgement questions** ("most likely to purchase") are answered from cited buying signals, but the ranking is still the model's judgement.
- **The entailment check is itself a model.** A subtle misreading can pass it. Planted traps are covered by the eval, but new kinds of misreading may not be.
- **Small, self-written gold set** (18 questions, written by the system's author). The judge is an LLM and hasn't been calibrated against hand grades.
- **Entity labels from extraction are noisy** (e.g. some non-SSO vendor claims are tagged `SSO`). This only affects which calls get picked (more calls read), not the evidence in answers.

## With more time

**Another day**
- Calibrate the judge against ~10 hand-graded answers, and grow the gold set with questions written by someone other than me.
- Run the eval with parts of the system switched off (no vectors, no facts, no entailment) to show what each part contributes.
- Make answers more concise: rank claims and cap secondary ones, then measure fact score against length.
- Show the trace in the CLI (why each call was read, what was rejected) as a debugging view.

**Production**
- **Scale (10K+ calls):** picking calls already keeps per-question cost flat for specific questions. For theme questions across thousands of calls, answer from the facts table and fully read a stratified sample, saying so in the answer. Move facts and vectors to Postgres + pgvector, and run reads through a queue or the Batches API.
- **New calls arriving continuously:** ingest one call at a time (parse → extract → verify → index), triggered by an event. Prompt versions are stored per step, so a schema change triggers background re-extraction.
- **Security and privacy:** transcripts contain personal data and commercial pricing. Redact personal data before sending to the LLM, or use zero-retention processing in the EU. Apply access control (team or region) as a metadata filter *before* call picking, so evidence can't leak across permissions. Keep an audit log of questions and the calls each answer touched. Transcripts are untrusted input (prompt injection): the verifier limits the damage, because answers can only cite real turns.
- **Models:** `llm.py` is the only module that knows the provider. A cheaper or self-hosted reader model (e.g. open weights) can be swapped in and judged by the eval on citation validity, false declines and fact score.
- **Monitoring:** track the verified-quote rate, removal rate, decline rate and cache hit rate per release as quality signals.

---

## Repository layout

```
src/sci/
  config.py  models.py  llm.py  quotes.py  aliases.json  cli.py
  ingest/   parse.py  chunk.py  index.py (BM25 + vectors)  extract.py
  query/    resolve.py  candidates.py  read.py  combine.py  verify.py  pipeline.py
  baselines/ naive_rag.py  full_context.py  common.py
eval/       questions.yaml  run_eval.py  judge.py  results/
tests/      test_parse.py  test_quotes.py  test_candidates.py
artifacts/  turns.jsonl  facts.json  cards.json  chunk_vectors_*.npy  (llm_cache/ gitignored)
```

## Dataset (provided)

20 fictional transcripts for OrbitFlow, a workflow-automation vendor: prospect calls 001–010, renewals 011–013, churn post-mortems 014–015, cold calls 016–020. Each transcript has a header, a `TRANSCRIPT` marker, then one turn per line as `[MM:SS] Speaker Name: text`. The company field is `PROSPECT:` or `CUSTOMER:` depending on call type. `manifest.json` carries company, industry, size, call type, stage, date, duration and participants. The case brief is in `instructions.md`.
