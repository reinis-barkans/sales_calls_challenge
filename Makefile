UV ?= uv

.PHONY: setup ingest ask eval test
setup:            ## install Python 3.12 + deps into .venv
	$(UV) sync

ingest:           ## parse + extract facts (cached in artifacts/; already committed)
	$(UV) run sci ingest

ask:              ## make ask Q="Which competitors were mentioned?"
	$(UV) run sci ask "$(Q)"

eval:             ## run gold set on pipeline + both baselines -> eval/results/results.md
	$(UV) run python eval/run_eval.py

test:
	$(UV) run pytest -q
