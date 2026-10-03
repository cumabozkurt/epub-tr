"""Engine registry."""
from __future__ import annotations

from .base import Engine, EngineError, EngineUnavailable, RateLimited  # noqa: F401
from .llm import OPENAI_PRESETS, Ollama, OpenAICompatible, OpenCode
from .mt import Argos, GoogleFree, LibreTranslate, Lingva, MyMemory, TranslatorsLib


class Echo(Engine):
    """Test engine: returns the input unchanged (structure tests)."""
    name = "echo"

    def translate_one(self, text):
        return text


ENGINES = {
    "opencode": ("LLM via OpenCode CLI free Zen models (opencode run)", lambda **kw: OpenCode(**kw)),
    "ollama": ("Local LLM via Ollama (default gemma3:4b)", lambda **kw: Ollama(**kw)),
    "google": ("Google Translate, free web endpoints", lambda **kw: GoogleFree(**kw)),
    "bing": ("Microsoft Bing Translator (free, via `translators`)", lambda **kw: TranslatorsLib("bing", **kw)),
    "yandex": ("Yandex Translate (free, via `translators`)", lambda **kw: TranslatorsLib("yandex", **kw)),
    "modernmt": ("ModernMT (free, via `translators`)", lambda **kw: TranslatorsLib("modernMt", **kw)),
    "mymemory": ("MyMemory API (free quota, MYMEMORY_EMAIL raises it)", lambda **kw: MyMemory(**kw)),
    "lingva": ("Lingva Translate public instance (LINGVA_URL)", lambda **kw: Lingva(**kw)),
    "libretranslate": ("LibreTranslate server (LIBRETRANSLATE_URL[, _API_KEY])", lambda **kw: LibreTranslate(**kw)),
    "argos": ("Argos Translate, fully offline", lambda **kw: Argos(**kw)),
    "echo": ("No-op engine for testing", lambda **kw: Echo(**kw)),
}
for _p in OPENAI_PRESETS:
    ENGINES[_p] = (f"OpenAI-compatible API preset '{_p}' (needs {OPENAI_PRESETS[_p][1]})",
                   (lambda p: (lambda **kw: OpenAICompatible(preset=p, **kw)))(_p))


def make_engine(name: str, **kw) -> Engine:
    name = name.lower()
    if name not in ENGINES:
        raise SystemExit(f"unknown engine {name!r}; choose from: {', '.join(ENGINES)}")
    return ENGINES[name][1](**kw)
