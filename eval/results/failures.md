# Failure log

Each failure lists the symptom, the stage that caused it (found from the trace in `eval/results/traces/`), and the fix or next step.

## Found while building (before the eval)

| # | Symptom | Stage | Fix |
|---|---|---|---|
| B1 | Call-type filters ("customers who left") never matched any call | Call picking | The manifest's `call_type` is only *Prospect* / *Existing customer*; the sub-type lives in `stage`. Added a derived `Call.category`. Caught by `test_call_type_filter_includes_all_of_type`. |
| B2 | "Did anyone mention Gong?" picked CALL-004 | Call picking (BM25) | The BM25 query included raw question words ("mention"). It now searches the resolved terms only. Regression test `test_absent_term_picks_nothing`. |
| B3 | CALL-005 (Ember, Salesforce required) not picked | Call picking (BM25) | The relative-score cutoff was too strict for brief mentions. Lowered it, accepting more Haiku reads in exchange for recall. |
| B4 | A reader quote joined Dermot's line and Maya's reply with "..."; the matcher accepted it and attributed all of it to Dermot | Quote verifier | Multi-turn matches now require a single speaker; prompts say so too. Regression test `test_cross_speaker_stitched_quote_rejected`. |
| B5 | Trafford's corrected "Eleven." rejected | Quote verifier | Minimum quote length blocked a valid short quote. Short quotes are now accepted when they make up an entire cited turn. |
| B6 | "Has the vendor given inconsistent answers?" missed Alastair (CALL-006) vs Leo (CALL-012) | Reader (design) | A reader sees one call, so Leo's consistent-looking "SAML SSO is Enterprise" was dropped as irrelevant. The resolve step now writes a per-call `read_instruction` asking for the raw material (every product claim by vendor staff), and the combine step compares across calls. This is the main limitation of reading calls separately. |
| B7 | "[pause] It's a related fight." (Darren Wu, CALL-009#T158) was verified as Olivia Grant's T157, where she says the same line, which he echoes | Quote verifier | Tag-stripping made both turns identical and the matcher took the first. It now ranks every match (exact match with tags kept > cited turn > tightest/nearest span), checks the reader's stated speaker, and rejects ties across speakers. On the eval this also rejected 2 previously "verified" findings where the reader put a customer's words in the vendor rep's mouth (Rafael Santos as Leo Grant in CALL-020#T066; Ava Sinclair as Nina Patel in CALL-010). Scores unchanged (run 3). Regression tests `test_echo_*`, `test_wrong_stated_speaker_rejected`. |
| B8 | "Which calls contained rude speech?" read 2 of 20 calls | Call picking (design) | Tone has no keywords, so BM25 and vectors miss it. Extraction now tags `friction` facts (quote and speaker checked; apologies, hedges and polite disagreement excluded), and `aliases.json` maps rude, tense, sarcastic etc. to it. The question now reads 20 calls and cites 19. Also: `llm.py` now retries once on invalid structured output (extraction hit truncated JSON twice). Run 4: pipeline unchanged; naive RAG shifted because its BM25 includes fact text. |

## Eval run 1 → run 2

| Q | Run 1 | Symptom | Stage | Change for run 2 | Run 2 |
|---|---|---|---|---|---|
| Q14 | selection 50% | Expected CALL-012 for a question about *prospects* | **Gold label** | CALL-012 is a renewal; label fixed | 100% |
| Q01, Q09 | facts 50% | Right call, right findings, but the summary dropped specifics (Salesforce in Acme's stack; Verity moved to Workato) | Combine | My earlier "fewer strong claims" instruction over-corrected verbose answers. Rebalanced: keep every distinct fact that answers the question plus the obvious follow-up specifics (who, which vendor, numbers); drop only tangents | 100% |
| Q05 | facts 50% | Oakhill's 4-of-30 seats and the wish for a smaller plan were lost across 16 cited calls | Combine | Same change | 100% |
| Q06 | facts 75% | Verity's real cause stated only partly | Combine | Same change | 100% |

## Still open

| Q | Symptom | Stage | Next step |
|---|---|---|---|
| Q07 | Judge: partial on 2 of 3 facts. The conflict section names Leo Grant / native connectors without tying them to CALL-012 / CALL-006 in the conflict line itself (the claims carry the evidence) | Combine / rendering | Render conflicts with their evidence (call, speaker, quote) instead of only finding IDs. |
| Q03 | `must_not_cite` counts a false match: the answer cites Lumen (CALL-011) **to say it was an outage, not an integration** | **Metric** | Correct behaviour; the metric can't tell excluding a call from claiming it. The judge's key fact for this ("does not present Lumen as an integration") is graded present. Fix the metric by checking claims, not citations. |
| List precision 64% | Answers cite more calls than `expected_calls` | **Metric / gold set** | `expected_calls` for Q04/Q14 is a deliberately minimal core subset (e.g. Zapier appears in 5 calls, residency in 9), so extra correct citations count as imprecise. A complete label set is needed before this number means anything. |
| General | Long answers for broad questions | Combine | The trade-off between coverage and length is real: making it shorter cost facts in run 1. Measure the fact score against answer length. |

## Caveats on the numbers

- **Run 2 was tuned on the same 18 questions it's scored on**, with no held-out set, so the pipeline's 98% is optimistic. The baselines got no tuning.
- The gold set and the system have the same author. The LLM judge hasn't been calibrated against hand grades.
- 18 questions is a smoke test, not a benchmark: one question is about 6 percentage points.

## Run 5: example questions, held-out set, facts-only ablation

Added Q19-Q21 (the instruction examples not covered before) to dev, a 10-question held-out set (`holdout.yaml`, written after the system was frozen and not tuned on), and `facts_only` (the pipeline with stored facts instead of full reads).

| Q | System | Symptom | Stage | Note |
|---|---|---|---|---|
| H02, H03, H07, H09, H10 | pipeline | All *partial*: the summary leaves out a detail the cited evidence contains (Halberd's contained workspace; "Leo accepted it as a fair read"; Verity's two-day onboarding; Pinewood undecided between notice and 6-month renewal) | Combine | Same failure as run 1's terse answers, now on unseen questions. Selection recall, abstention and conflicts were 100%, so this isn't retrieval. **Not fixed**: fixing against held-out questions would spoil them. Next step: a completeness check that compares the summary with the claims. |
| Q21 | pipeline / full ctx / facts | 75%: renewals vs new business misses part of one fact | Combine | Broad compare question; same across systems. |
| Q06, Q09 | facts_only | 50% / 83% vs pipeline 100%: "wasn't why we left" nuance not framed as the real reason | Reading (ablation) | The one place full reads clearly beat stored facts: the stated-vs-real distinction lives in the surrounding conversation. |
| H05 | facts_only | Abstention ✗: answered "no prospect mentioned Copilot" with evidence of which Microsoft products *were* mentioned | **Metric** | A correct, evidence-backed negative; the abstention metric can't tell it apart from a hallucinated answer. Better behaviour than a bare decline, arguably. |

**Overfitting, measured:** pipeline 97% dev vs 83% held-out. **Ablation:** facts_only scored 92% dev and 88% held-out at ~55% of the pipeline's tokens, so per-question full reading adds little except on "why" and nuance questions.

## PR #1 review and runs 6-7

PR #1 grounded the summary (each sentence must cite a surviving claim), made entailment fail closed, and fixed the latency and citation-validity metrics. Reviewing it and re-running found two more bugs:

| # | Symptom | Stage | Fix |
|---|---|---|---|
| B9 | "integrations, e.g. Salesforce [C1]." became "Salesforce [1]." | Verifier (summary grounding) | The sentence splitter treated e.g. / vs. / approx. as sentence ends, deleted the unmarked first half and kept a fragment. Abbreviations are now excluded from splitting. Tests `test_abbreviations_do_not_split_sentences`, `test_real_sentence_ends_still_split`. |
| B10 | After fail-closed, `facts_only` Q04 lost 8 of 9 claims (100% -> 33%); 13 claims lost on dev overall | Verifier (entailment) | Haiku split claims into sub-claims ("K1-1, K1-2...") and stopped partway, so later claims got **no verdict**; before PR #1 these passed as "supported" **unchecked**. Parsing also let a later sub-verdict overwrite an earlier "unsupported". Now: one verdict per claim is requested with the IDs listed; the worst sub-verdict wins; missing verdicts are re-asked once, then fail closed. On the vendor-inconsistency trace all 11 claims now get verdicts, and one is correctly **unsupported**. Tests `test_split_subverdicts_worst_wins`, `test_missing_verdicts_are_retried`. |

**Run 7 (current code):** pipeline 92% dev / 89% held-out; facts_only 92% / 89%; no claims lost to missing verdicts. The earlier 97% / 83% gap was partly unchecked claims and partly noise.

**Noise, measured:** same code, combine re-run (no `temperature` on current models): Q01 1.0 -> 0.5 (Salesforce dropped from the summary). The judge graded Q02's "Acme Corp" assumption, shown to it in both runs, present then absent. Run-to-run differences of 5-10 points are expected; calibrating the judge and averaging several runs would be the fix.

## Code review after run 7

| # | Symptom | Stage | Fix |
|---|---|---|---|
| B11 | A resolver output that isn't an exact catalogue name ("Acme Logistics Ltd", "acme logistics") fell through to a dataset-wide search: 15 calls about other companies picked for a single-company question | Call picking | Only `resolved_to=None` counted as unknown. Names are now matched case/whitespace-insensitively; anything still unmatched picks nothing (and gets the "no calls match" message). A name contained as whole words in exactly one company ("Acme" -> Acme Logistics) is used, with an assumption stated in the answer; a name shared by several companies ("Group") picks nothing. Also fixed: a company could map to only one call. Never triggered in the eval (all traces had exact names); replaying the stored resolution of all 34 traces gives identical picks, so results stand without a re-run. Tests `test_non_catalogue_company_name_picks_nothing`, `test_company_name_match_ignores_case_and_spacing`, `test_company_with_several_calls_reads_all`, `test_partial_name_*`. |
| Open | Conflicts aren't entailment-checked; duplicate finding IDs count twice; the CLI shows finding IDs, not quotes; conflict recall passes on any conflict | Verifier / metric | All conflicts on expected-conflict questions checked by hand and correct. Documented in README limitations. |
