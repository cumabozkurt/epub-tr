"""LLM engines: OpenCode CLI (free Zen models), Ollama (local), OpenAI-compatible APIs."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading

import requests

from .base import Engine, EngineError, EngineUnavailable, RateLimited, env

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
RATE_RE = re.compile(r"Rate limit exceeded|FreeUsageLimitError|free tier can only be used|Too Many Requests|quota", re.I)

OPENCODE_FREE_MODELS = [
    # order of preference for literary quality (checked with `opencode models`, 2026-10)
    "opencode/big-pickle",
    "opencode/nemotron-3-ultra-free",
    "opencode/longcat-2.5-preview-free",
    "opencode/mimo-v2.6-flash-free",
    "opencode/muse-spark-1.3-contributor-free",
    "opencode/space-bunny-free",
    "opencode/ling-3.0-flash-fin-free",
    "opencode/nemotron-3.5-lightning-free",
]


class OpenCode(Engine):
    """Runs ``opencode run`` non-interactively.

    A private working directory with an ``opencode.json`` defines a tool-less
    ``epubtr`` agent whose system prompt is the literary-translation prompt, so
    the coding-agent prompt/tools of the default *build* agent are not used.
    ``--title`` avoids the extra title-generation request.
    """

    name = "opencode"
    is_llm = True
    default_workers = 2
    _setup_lock = threading.Lock()

    def __init__(self, **kw):
        super().__init__(**kw)
        self.model = self.model or env("EPUB_TR_OPENCODE_MODEL") or OPENCODE_FREE_MODELS[0]
        self.timeout = int(self.opts.get("timeout") or env("EPUB_TR_OPENCODE_TIMEOUT", 600))
        self.bin = env("OPENCODE_BIN") or shutil.which("opencode") or os.path.expanduser("~/.opencode/bin/opencode")
        self.workdir = os.path.join(os.path.expanduser("~/.cache/epub-tr"), "opencode-agent")
        self.fallback_models = [m for m in OPENCODE_FREE_MODELS if m != self.model] if self.opts.get("auto_model", True) else []

    def check(self):
        if not self.bin or not os.path.exists(self.bin):
            raise EngineUnavailable("opencode not installed: npm i -g opencode-ai  (or curl -fsSL https://opencode.ai/install | bash)")

    def _write_agent(self, system: str) -> str:
        """Each distinct system prompt gets its own agent dir (prompt is static per run)."""
        import hashlib
        h = hashlib.sha1(system.encode()).hexdigest()[:10]
        d = os.path.join(self.workdir, h)
        with self._setup_lock:
            if not os.path.exists(os.path.join(d, "opencode.json")):
                os.makedirs(d, exist_ok=True)
                cfg = {
                    "$schema": "https://opencode.ai/config.json",
                    "share": "disabled",
                    "autoupdate": False,
                    "agent": {
                        "epubtr": {
                            "mode": "primary",
                            "description": "Literary book translator (no tools)",
                            "prompt": system,
                            "temperature": 0.3,
                            "tools": {"*": False},
                        }
                    },
                }
                with open(os.path.join(d, "opencode.json"), "w") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
        return d

    def complete(self, system: str, user: str) -> str:
        d = self._write_agent(system)
        models = [self.model] + list(self.fallback_models)
        last_err = None
        for m in models:
            try:
                out = self._run(d, m, user)
                if m != self.model:
                    self.model = m  # stick to the model that works
                return out
            except RateLimited as e:
                last_err = e
                continue
        raise last_err or EngineError("opencode: no model worked")

    def _run(self, d, model, user):
        cmd = [self.bin, "run", "--pure", "--dir", d, "--agent", "epubtr", "--title", "epub-tr", "--format", "json",
               "--print-logs", "--log-level", "ERROR", "-m", model, user]
        # NB: opencode resolves its project directory from $PWD, not from the real cwd -> set both,
        # otherwise it picks up the caller's directory and fails with "UnknownError".
        env_ = {**os.environ, "PWD": d, "OPENCODE_DISABLE_AUTOUPDATE": "1"}
        p = subprocess.Popen(cmd, cwd=d, env=env_, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             stdin=subprocess.DEVNULL)
        out_lines, err_lines, limited = [], [], threading.Event()

        def read_out():
            for line in p.stdout:
                out_lines.append(line)

        def read_err():
            # opencode retries 429s internally for a long time -> fail fast instead
            for line in p.stderr:
                err_lines.append(line)
                if RATE_RE.search(line):
                    limited.set()
                    p.kill()

        ts = [threading.Thread(target=read_out, daemon=True), threading.Thread(target=read_err, daemon=True)]
        for t in ts:
            t.start()
        try:
            p.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            raise EngineError(f"opencode timed out after {self.timeout}s ({model})")
        for t in ts:
            t.join(5)
        err_all = "".join(err_lines)
        if limited.is_set():
            m = RATE_RE.search(err_all)
            raise RateLimited(f"opencode {model}: {m.group(0) if m else 'rate limited'}")
        text, errors = parse_opencode_json("".join(out_lines))
        err_all += " ".join(errors)
        if not text.strip():
            if RATE_RE.search(err_all):
                raise RateLimited(f"opencode {model}: rate limited")
            raise EngineError(f"opencode {model}: empty output (exit {p.returncode}): {ANSI_RE.sub('', err_all)[-400:]}")
        return text


def parse_opencode_json(stdout: str):
    """Collect assistant text parts from ``opencode run --format json`` event lines."""
    texts, errors = [], []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        typ = ev.get("type")
        part = ev.get("part") or {}
        if typ == "text" and isinstance(part, dict) and part.get("text"):
            texts.append(part["text"])
        elif typ == "error":
            errors.append(json.dumps(ev.get("error", ev))[:500])
    if not texts and stdout.strip() and not stdout.lstrip().startswith("{"):
        texts.append(ANSI_RE.sub("", stdout))
    return "".join(texts), errors


class Ollama(Engine):
    """Local Ollama server (OLLAMA_HOST, default http://localhost:11434)."""

    name = "ollama"
    is_llm = True
    default_workers = 1

    def __init__(self, **kw):
        super().__init__(**kw)
        self.model = self.model or env("EPUB_TR_OLLAMA_MODEL", "gemma3:4b")
        self.host = env("OLLAMA_HOST", "http://localhost:11434")
        if not self.host.startswith("http"):
            self.host = "http://" + self.host

    def check(self):
        try:
            r = requests.get(self.host + "/api/tags", timeout=5)
            names = [m["name"] for m in r.json().get("models", [])]
        except Exception:
            raise EngineUnavailable(f"ollama not running at {self.host}")
        if self.model not in names and self.model + ":latest" not in names:
            raise EngineUnavailable(f"ollama model {self.model} not pulled (have: {names})")

    def complete(self, system, user):
        try:
            r = requests.post(self.host + "/api/chat", json={
                "model": self.model, "stream": False,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"temperature": 0.3, "repeat_penalty": 1.1,
                            "num_ctx": int(env("EPUB_TR_OLLAMA_CTX", 8192)),
                            # cap output: a looping small model must not run forever
                            "num_predict": int(env("EPUB_TR_OLLAMA_MAX_TOKENS", 0)) or max(512, len(user))},
            }, timeout=int(env("EPUB_TR_OLLAMA_TIMEOUT", 1800)))
        except requests.RequestException as e:
            raise EngineError(f"ollama: {e}")
        if r.status_code != 200:
            raise EngineError(f"ollama HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["message"]["content"]


OPENAI_PRESETS = {
    # name: (base_url, key env var, default model)
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "meta-llama/llama-3.3-70b-instruct:free"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", "gemini-2.5-flash"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY", "mistral-small-latest"),
    "openai": (env("OPENAI_BASE_URL", "https://api.openai.com/v1"), "OPENAI_API_KEY", "gpt-4o-mini"),
}


class OpenAICompatible(Engine):
    """Any OpenAI-compatible chat API (OpenRouter free models, Gemini free tier, Groq, ...)."""

    is_llm = True
    default_workers = 2

    def __init__(self, preset="openai", **kw):
        super().__init__(**kw)
        self.name = preset
        base, keyvar, model = OPENAI_PRESETS[preset]
        self.base = env(f"EPUB_TR_{preset.upper()}_BASE_URL", base)
        self.keyvar = keyvar
        self.model = self.model or env(f"EPUB_TR_{preset.upper()}_MODEL", model)

    def check(self):
        if not env(self.keyvar):
            raise EngineUnavailable(f"set {self.keyvar} to use {self.name}")

    def complete(self, system, user):
        try:
            r = requests.post(self.base.rstrip("/") + "/chat/completions",
                              headers={"Authorization": f"Bearer {env(self.keyvar)}"},
                              json={"model": self.model, "temperature": 0.3,
                                    "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user}]}, timeout=600)
        except requests.RequestException as e:
            raise EngineError(f"{self.name}: {e}")
        if r.status_code == 429:
            raise RateLimited(f"{self.name}: 429")
        if r.status_code != 200:
            raise EngineError(f"{self.name} HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["choices"][0]["message"]["content"]
