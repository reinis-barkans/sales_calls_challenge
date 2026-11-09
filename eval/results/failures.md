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
