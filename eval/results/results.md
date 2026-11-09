# Evaluation results

Gold set: 18 questions (eval/questions.yaml).

| Metric | pipeline | naive_rag | full_context |
|---|---|---|---|
| Fact score (judge) | 98% | 69% | 93% |
| Selection recall | 100% | 71% | 100% |
| Cited-call recall | 100% | 68% | 99% |
| List precision | 64% | 50% | 75% |
| False matches (must_not_cite) | 1 | 0 | 0 |
| Citation validity | 99% | 99% | 100% |
| Abstention accuracy | 100% | 83% | 100% |
| Conflict recall | 100% | 50% | 100% |
| Avg input tokens / question | 81,769 | 3,995 | 167,837 |
| Avg latency (s, uncached) | 3 | 5 | 0 |
| Errors | 0 | 0 | 0 |

## Per question

| Q | Category | pipeline facts / abst / cited-recall | naive_rag facts / abst / cited-recall | full_context facts / abst / cited-recall |
|---|---|---|---|---|
| Q01 | lookup | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q02 | alias | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q03 | list | 100% / ✓ / 100% | 75% / ✓ / 80% | 100% / ✓ / 100% |
| Q04 | list | 100% / ✓ / 100% | 25% / ✓ / 0% | 100% / ✓ / 86% |
| Q05 | theme | 100% / ✓ / 100% | 0% / ✓ / 0% | 75% / ✓ / 100% |
| Q06 | theme | 100% / ✓ / 100% | 25% / ✓ / 50% | 75% / ✓ / 100% |
| Q07 | compare | 67% / ✓ / 100% | 0% / ✗ / 0% | 67% / ✓ / 100% |
| Q08 | multi_hop | 100% / ✓ / 100% | 38% / ✗ / 20% | 100% / ✓ / 100% |
| Q09 | lookup | 100% / ✓ / 100% | 67% / ✓ / 100% | 83% / ✓ / 100% |
| Q10 | conflict | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q11 | lookup | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q12 | lookup | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q13 | near_miss | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q14 | theme | 100% / ✓ / 100% | 100% / ✓ / 100% | 100% / ✓ / 100% |
| Q15 | decline | – / ✓ / – | – / ✓ / – | – / ✓ / – |
| Q16 | decline | – / ✓ / – | – / ✓ / – | – / ✓ / – |
| Q17 | decline | – / ✓ / – | – / ✓ / – | – / ✓ / – |
| Q18 | judgement | 100% / ✓ / – | 100% / ✗ / – | 92% / ✓ / – |
