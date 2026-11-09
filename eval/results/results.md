# Evaluation results (dev set)

Gold set: 21 questions (eval/questions.yaml).

| Metric | pipeline | naive_rag | full_context | facts_only |
|---|---|---|---|---|
| Fact score (judge) | 97% | 60% | 92% | 92% |
| Selection recall | 100% | 66% | 100% | 100% |
| Cited-call recall | 100% | 62% | 98% | 100% |
| List precision | 64% | 50% | 75% | 64% |
| False matches (must_not_cite) | 1 | 0 | 0 | 1 |
| Citation validity | 99% | 99% | 100% | 100% |
| Abstention accuracy | 100% | 76% | 100% | 100% |
| Conflict recall | 100% | 50% | 100% | 100% |
| Avg input tokens / question | 94,838 | 4,024 | 167,837 | 52,382 |
| Avg latency (s, uncached) | 5 | 1 | 2 | 16 |
| Errors | 0 | 0 | 0 | 0 |

## Per question

| Q | Category | pipeline facts / abst / cited-recall | naive_rag facts / abst / cited-recall | full_context facts / abst / cited-recall | facts_only facts / abst / cited-recall |
|---|---|---|---|---|---|
| Q01 | lookup | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q02 | alias | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q03 | list | 100% / ✓ / 100% | 75% / ✓ / 80% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q04 | list | 100% / ✓ / 100% | 25% / ✓ / 0% | 100% / ✓ / 86% | 100% / ✓ / 100% |
| Q05 | theme | 100% / ✓ / 100% | 0% / ✓ / 0% | 75% / ✓ / 100% | 100% / ✓ / 100% |
| Q06 | theme | 100% / ✓ / 100% | 25% / ✓ / 50% | 75% / ✓ / 100% | 50% / ✓ / 100% |
| Q07 | compare | 67% / ✓ / 100% | 0% / ✗ / 0% | 67% / ✓ / 100% | 67% / ✓ / 100% |
| Q08 | multi_hop | 100% / ✓ / 100% | 38% / ✗ / 20% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q09 | lookup | 100% / ✓ / 100% | 67% / ✓ / 100% | 83% / ✓ / 100% | 83% / ✓ / 100% |
| Q10 | conflict | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q11 | lookup | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q12 | lookup | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q13 | near_miss | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q14 | theme | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q15 | decline | – / ✓ / – | – / ✓ / – | – / ✓ / – | – / ✓ / – |
| Q16 | decline | – / ✓ / – | – / ✓ / – | – / ✓ / – | – / ✓ / – |
| Q17 | decline | – / ✓ / – | – / ✓ / – | – / ✓ / – | – / ✓ / – |
| Q18 | judgement | 100% / ✓ / – | 100% / ✗ / – | 92% / ✓ / – | 100% / ✓ / – |
| Q19 | theme | 100% / ✓ / 100% | 12% / ✗ / 29% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q20 | theme | 100% / ✓ / 100% | 38% / ✓ / 50% | 88% / ✓ / 75% | 88% / ✓ / 100% |
| Q21 | compare | 75% / ✓ / 100% | 0% / ✗ / 33% | 75% / ✓ / 100% | 75% / ✓ / 100% |
