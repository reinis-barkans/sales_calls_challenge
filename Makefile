UV ?= uv

.PHONY: setup ingest ask eval eval-holdout test
setup:            ## install Python 3.12 + deps into .venv
	$(UV) sync

ingest:           ## parse + extract facts (cached in artifacts/; already committed)
	$(UV) run sci ingest

ask:              ## make ask Q="Which competitors were mentioned?"
	$(UV) run sci ask "$(Q)"

eval:             ## dev gold set (21 Qs) on pipeline + 3 comparison systems -> eval/results/results.md
	$(UV) run python eval/run_eval.py --set dev

eval-holdout:     ## held-out set (10 Qs, never tuned on) -> eval/results/results_holdout.md
	$(UV) run python eval/run_eval.py --set holdout

test:
	$(UV) run pytest -q
