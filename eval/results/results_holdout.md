# Evaluation results (holdout set)

Gold set: 10 questions (eval/holdout.yaml).

| Metric | pipeline | naive_rag | full_context | facts_only |
|---|---|---|---|---|
| Fact score (judge) | 83% | 78% | 86% | 88% |
| Selection recall | 100% | 90% | 100% | 100% |
| Cited-call recall | 100% | 90% | 100% | 100% |
| List precision | 60% | 100% | 100% | 86% |
| False matches (must_not_cite) | 0 | 0 | 0 | 0 |
| Citation validity | 98% | 98% | 100% | 100% |
| Abstention accuracy | 100% | 100% | 100% | 90% |
| Conflict recall | 100% | 100% | 100% | 100% |
| Avg input tokens / question | 45,792 | 4,021 | 167,841 | 28,842 |
| Avg latency (s, uncached) | 23 | 6 | 10 | 14 |
| Errors | 0 | 0 | 0 | 0 |

## Per question

| Q | Category | pipeline facts / abst / cited-recall | naive_rag facts / abst / cited-recall | full_context facts / abst / cited-recall | facts_only facts / abst / cited-recall |
|---|---|---|---|---|---|
| H01 | lookup | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| H02 | lookup | 67% / ✓ / 100% | 100% / ✓ / 100% | 83% / ✓ / 100% | 67% / ✓ / 100% |
| H03 | alias | 75% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 75% / ✓ / 100% |
| H04 | list | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| H05 | decline | – / ✓ / – | – / ✓ / – | – / ✓ / – | – / ✗ / – |
| H06 | decline | – / ✓ / – | – / ✓ / – | – / ✓ / – | – / ✓ / – |
| H07 | conflict | 75% / ✓ / 100% | 75% / ✓ / 100% | 75% / ✓ / 100% | 75% / ✓ / 100% |
| H08 | multi_hop | 83% / ✓ / 100% | 17% / ✓ / 67% | 83% / ✓ / 100% | 83% / ✓ / 100% |
| H09 | theme | 83% / ✓ / 100% | 67% / ✓ / 50% | 83% / ✓ / 100% | 100% / ✓ / 100% |
| H10 | judgement | 83% / ✓ / 100% | 67% / ✓ / 100% | 67% / ✓ / 100% | 100% / ✓ / 100% |
