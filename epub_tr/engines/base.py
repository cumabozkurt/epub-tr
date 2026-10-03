from __future__ import annotations

import os
import time


class EngineError(RuntimeError):
    """Generic (retryable) engine failure."""


class RateLimited(EngineError):
    """Engine is rate limited / quota exhausted."""


class EngineUnavailable(EngineError):
    """Engine cannot be used at all (missing dependency, key, binary...)."""


class Engine:
    """Base class.

    ``is_llm`` engines receive whole prompts (``complete``); MT engines get
    lists of placeholder-encoded strings (``translate_batch``).
    """

    name = "base"
    is_llm = False
    supports_tags = True          # can keep <g1>..</g1> placeholders
    max_chars = 4500              # per request
    default_workers = 4

    def __init__(self, source="en", target="tr", model=None, **opts):
        self.source = source
        self.target = target
        self.model = model
        self.opts = opts

    @property
    def model_id(self) -> str:
        return self.model or ""

    def check(self) -> None:
        """Raise EngineUnavailable if the engine cannot run."""

    # --- MT interface
    def translate_batch(self, texts: list[str]) -> list[str]:
        return [self.translate_one(t) for t in texts]

    def translate_one(self, text: str) -> str:
        raise NotImplementedError

    # --- LLM interface
    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


def env(name, default=None):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def backoff_sleep(attempt: int, base: float = 2.0, cap: float = 60.0):
    time.sleep(min(cap, base * (2 ** attempt)))
