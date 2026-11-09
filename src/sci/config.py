"""Central configuration: paths, model names, budgets, thresholds."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

CALLS_DIR = ROOT / "calls"
MANIFEST = ROOT / "manifest.json"
ARTIFACTS = ROOT / "artifacts"
LLM_CACHE = ARTIFACTS / "llm_cache"
TRACES = ROOT / "eval" / "results" / "traces"

TURNS_FILE = ARTIFACTS / "turns.jsonl"
FACTS_FILE = ARTIFACTS / "facts.json"
CARDS_FILE = ARTIFACTS / "cards.json"
ALIASES_FILE = ROOT / "src" / "sci" / "aliases.json"

FAST_MODEL = os.getenv("SCI_FAST_MODEL", "claude-haiku-5-5")
STRONG_MODEL = os.getenv("SCI_STRONG_MODEL", "claude-sonnet-5-5")
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
# Thinking is on by default on current Haiku/Sonnet; keep it cheap. Part of the disk-cache key.
EFFORT = os.getenv("SCI_EFFORT", "low")

# Bump a version when its prompt changes: it invalidates the disk cache for that step.
PROMPT_VERSIONS = {
    "extract": "v3",
    "resolve": "v3",
    "read": "v3",
    "combine": "v4",
    "entail": "v2",
    "judge": "v1",
    "naive_rag": "v1",
    "full_context": "v1",
}

CHUNK_TURNS = 8
CHUNK_OVERLAP = 2
BM25_TOP_CHUNKS = 40          # chunks considered before rolling up to calls
SEARCH_MIN_SCORE_RATIO = 0.20  # a call's best chunk must score >= ratio * top score to be picked
VECTOR_TOP_CHUNKS = 10
# bge-small cosine. Calibrated on this corpus: absent topics ("Gong") top out ~0.62,
# real topics reach 0.65-0.72. Narrow margin, so vectors only ADD candidates above this floor.
VECTOR_MIN_SIM = 0.65
MAX_PARALLEL = 8
# Prompt-cache TTL for stable prefixes (transcripts, corpus, catalogue). Transcripts never
# change and questions arrive in bursts with gaps > 5 min, so 1h beats the 5m default
# despite the 2x write cost (break-even at ~3 reads of the same prefix).
CACHE_TTL = "1h"
