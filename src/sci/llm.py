"""Thin Anthropic client.

- Structured output via `messages.parse(output_format=<pydantic model>)` (API-side
  structured outputs; current Sonnet rejects forced tool_choice).
- Prompt caching: a stable `cached_context` block (e.g. a transcript) is sent
  before the varying part of the prompt with a cache breakpoint, and the system
  prompt can be cached too. Min cacheable prefix on current Haiku/Sonnet is 512 tokens.
- Disk cache keyed by (model, step, prompt version, inputs) so eval re-runs are
  free and reproducible (sampling params can't be set on current models).
- Usage logging incl. cache read/write tokens.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Optional, TypeVar

from pydantic import BaseModel

from sci.config import CACHE_TTL, EFFORT, LLM_CACHE, PROMPT_VERSIONS

T = TypeVar("T", bound=BaseModel)

_client = None
_lock = threading.Lock()
USAGE: list[dict] = []   # per-call usage log, read by the pipeline/eval

MIN_MAX_TOKENS = 8000    # thinking is on by default and spends from max_tokens
MAX_NONSTREAM_TOKENS = 16000


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(max_retries=4)
    return _client


def _cache_path(key: str):
    return LLM_CACHE / key[:2] / f"{key}.json"


def _cc() -> dict:
    return {"type": "ephemeral", "ttl": CACHE_TTL}


def structured(*, step: str, model: str, system: str, user: str, schema: type[T],
               max_tokens: int = MIN_MAX_TOKENS, cache_system: bool = False,
               cached_context: Optional[str] = None) -> T:
    """Call `model` and return a validated instance of `schema`.

    cached_context: stable text placed before `user` in the user turn, with a cache
    breakpoint after it (prefix = system + cached_context).
    cache_system: put a cache breakpoint on the system prompt.
    """
    version = PROMPT_VERSIONS[step]
    key = hashlib.sha256(json.dumps(
        [model, EFFORT, step, version, system, cached_context or "", user, schema.__name__]).encode()).hexdigest()
    path = _cache_path(key)
    if path.exists():
        data = json.loads(path.read_text())
        USAGE.append({**data["usage"], "step": step, "model": model, "cached": True})
        return schema.model_validate(data["output"])

    sys_block = [{"type": "text", "text": system, **({"cache_control": _cc()} if cache_system else {})}]
    content = []
    if cached_context:
        content.append({"type": "text", "text": cached_context, "cache_control": _cc()})
    content.append({"type": "text", "text": user})

    budget = min(max(max_tokens, MIN_MAX_TOKENS), MAX_NONSTREAM_TOKENS)
    last = None
    for attempt in range(2):
        t0 = time.time()
        resp = _get_client().messages.parse(
            model=model, max_tokens=budget, system=sys_block,
            messages=[{"role": "user", "content": content}], output_format=schema,
            output_config={"effort": EFFORT},
        )
        u = resp.usage
        cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
        usage = {"input_tokens": u.input_tokens + cache_read + cache_write,
                 "uncached_input_tokens": u.input_tokens, "cache_read_tokens": cache_read,
                 "cache_write_tokens": cache_write, "output_tokens": u.output_tokens,
                 "latency_s": round(time.time() - t0, 2)}
        USAGE.append({**usage, "step": step, "model": model, "cached": False})
        out = resp.parsed_output
        if out is not None:
            with _lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"output": out.model_dump(), "usage": usage}))
            return out
        last = resp.stop_reason
        if resp.stop_reason == "max_tokens":
            budget = MAX_NONSTREAM_TOKENS
        elif resp.stop_reason == "refusal":
            break
    raise RuntimeError(f"{step}: no structured output (stop_reason={last})")


def usage_summary(entries: list[dict]) -> dict:
    live = [e for e in entries if not e.get("cached")]
    return {
        "llm_calls": len(entries),
        "input_tokens": sum(e["input_tokens"] for e in entries),
        "cache_read_tokens": sum(e.get("cache_read_tokens", 0) for e in entries),
        "cache_write_tokens": sum(e.get("cache_write_tokens", 0) for e in entries),
        "output_tokens": sum(e["output_tokens"] for e in entries),
        "uncached_calls": len(live),
    }
