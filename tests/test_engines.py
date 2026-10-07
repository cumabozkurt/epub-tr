"""Engine adapters with the network mocked out (no request leaves the machine)."""
import json
import os
import stat
import sys

import pytest
import requests

from epub_tr.engines import ENGINES, make_engine
from epub_tr.engines import llm as llm_mod
from epub_tr.engines import mt as mt_mod
from epub_tr.engines.base import EngineError, EngineUnavailable, RateLimited, env
from epub_tr.engines.llm import OPENCODE_FREE_MODELS, OpenCode, parse_opencode_json
from epub_tr.engines.mt import _pack, _split_bytes


class Resp:
    def __init__(self, status=200, data=None, text=""):
        self.status_code = status
        self._data = data
        self.text = text or json.dumps(data)

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if an unmocked request is attempted."""
    def boom(*a, **k):
        raise AssertionError(f"unexpected network call: {a} {k}")
    for mod in (mt_mod, llm_mod):
        monkeypatch.setattr(mod.requests, "get", boom)
        monkeypatch.setattr(mod.requests, "post", boom)
    return monkeypatch


# ------------------------------------------------------------------ registry
def test_registry_contains_all_documented_engines():
    for name in ("opencode", "ollama", "google", "bing", "yandex", "modernmt", "mymemory", "lingva",
                 "libretranslate", "argos", "echo", "openrouter", "gemini", "groq", "mistral", "openai"):
        assert name in ENGINES


def test_make_engine_unknown_and_case_insensitive():
    assert make_engine("GOOGLE").name == "google"
    with pytest.raises(SystemExit):
        make_engine("nope")


def test_env_treats_empty_as_unset(monkeypatch):
    monkeypatch.setenv("EPUB_TR_X", "")
    assert env("EPUB_TR_X", "d") == "d"
    monkeypatch.setenv("EPUB_TR_X", "v")
    assert env("EPUB_TR_X", "d") == "v"


def test_echo_engine():
    assert make_engine("echo").translate_batch(["a <g1>b</g1>"]) == ["a <g1>b</g1>"]


# ------------------------------------------------------------------ helpers
def test_pack_respects_limit():
    assert list(_pack(["aaaa", "bb", "cc", "dddddd"], 6)) == [[0, 1], [2], [3]]


@pytest.mark.parametrize("text", [
    "Short. Sentences! Here?",
    "word " * 300,
    "x" * 1500,                       # one huge "word": used to recurse forever
    ("ğüşiöç" * 120) + ". Son.",      # multi-byte characters
])
def test_split_bytes(text):
    chunks = _split_bytes(text, 480)
    assert all(0 < len(c.encode()) <= 480 for c in chunks)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


# ------------------------------------------------------------------ Google
def test_google_clients5_batch(no_network):
    seen = []

    def post(url, params=None, data=None, headers=None, timeout=None):
        seen.append((url, params, data))
        return Resp(200, [q.upper() + " &#39;x&#39;" for q in data["q"]])
    no_network.setattr(mt_mod.requests, "post", post)
    g = make_engine("google", source="en", target="tr")
    assert g.translate_batch(["a <g1>b</g1>", "c"]) == ["A <G1>B</G1> 'x'", "C 'x'"]
    assert seen[0][1] == {"client": "dict-chrome-ex", "sl": "en", "tl": "tr"}


def test_google_auto_language_shape(no_network):
    no_network.setattr(mt_mod.requests, "post", lambda *a, **k: Resp(200, [["Merhaba", "en"]]))
    assert make_engine("google").translate_batch(["Hello"]) == ["Merhaba"]


def test_google_count_mismatch(no_network):
    no_network.setattr(mt_mod.requests, "post", lambda *a, **k: Resp(200, ["one"]))
    with pytest.raises(EngineError):
        make_engine("google").translate_batch(["a", "b"])


def test_google_network_error(no_network):
    def post(*a, **k):
        raise requests.ConnectionError("down")
    no_network.setattr(mt_mod.requests, "post", post)
    with pytest.raises(EngineError):
        make_engine("google").translate_batch(["a"])


def test_google_http_error_uses_deep_translator_fallback(no_network):
    no_network.setattr(mt_mod.requests, "post", lambda *a, **k: Resp(503, {}, "unavailable"))
    no_network.setattr(mt_mod.GoogleFree, "_deep", lambda self, q: "deep:" + q)
    assert make_engine("google").translate_batch(["a", "b"]) == ["deep:a", "deep:b"]


# ------------------------------------------------------------------ MyMemory / Lingva / LibreTranslate
def test_mymemory_ok_and_email(no_network, monkeypatch):
    calls = []

    def get(url, params=None, timeout=None):
        calls.append(params)
        return Resp(200, {"responseStatus": 200, "responseData": {"translatedText": "Merhaba &amp; dünya"}})
    no_network.setattr(mt_mod.requests, "get", get)
    monkeypatch.setenv("MYMEMORY_EMAIL", "me@example.com")
    assert make_engine("mymemory").translate_one("Hello & world") == "Merhaba & dünya"
    assert calls[0]["langpair"] == "en|tr" and calls[0]["de"] == "me@example.com"


def test_mymemory_long_text_is_split(no_network):
    sizes = []

    def get(url, params=None, timeout=None):
        sizes.append(len(params["q"].encode()))
        return Resp(200, {"responseStatus": 200, "responseData": {"translatedText": "ok"}})
    no_network.setattr(mt_mod.requests, "get", get)
    out = make_engine("mymemory").translate_one("y" * 2000)
    assert out.split() == ["ok"] * len(sizes) and max(sizes) <= 480 and len(sizes) >= 5


def test_mymemory_quota(no_network):
    no_network.setattr(mt_mod.requests, "get", lambda *a, **k: Resp(200, {
        "responseStatus": 429, "responseData": {"translatedText": "MYMEMORY WARNING: YOU USED ALL"}}))
    with pytest.raises(RateLimited):
        make_engine("mymemory").translate_one("Hello")


def test_lingva_tries_instances(no_network, monkeypatch):
    monkeypatch.delenv("LINGVA_URL", raising=False)
    urls = []

    def get(url, timeout=None, headers=None):
        urls.append(url)
        if len(urls) == 1:
            return Resp(500, {}, "err")
        if len(urls) == 2:
            return Resp(200, {"translation": "Hello world"})  # untranslated echo -> rejected
        return Resp(200, {"translation": "Merhaba dünya"})
    no_network.setattr(mt_mod.requests, "get", get)
    assert make_engine("lingva").translate_one("Hello world") == "Merhaba dünya"
    assert len(urls) == 3 and "/api/v1/en/tr/Hello%20world" in urls[0]


def test_lingva_custom_instance_failure(no_network, monkeypatch):
    monkeypatch.setenv("LINGVA_URL", "https://lingva.example")
    no_network.setattr(mt_mod.requests, "get", lambda url, **k: Resp(404, {}, "nf"))
    with pytest.raises(EngineError, match="HTTP 404"):
        make_engine("lingva").translate_one("Hi")


def test_libretranslate(no_network, monkeypatch):
    monkeypatch.setenv("LIBRETRANSLATE_URL", "http://lt.local:5000/")
    monkeypatch.setenv("LIBRETRANSLATE_API_KEY", "k")
    sent = {}

    def post(url, json=None, timeout=None):
        sent.update(url=url, **json)
        return Resp(200, {"translatedText": "Merhaba"})
    no_network.setattr(mt_mod.requests, "post", post)
    no_network.setattr(mt_mod.requests, "get", lambda url, timeout=None: Resp(200, []))
    e = make_engine("libretranslate")
    e.check()
    assert e.translate_one("Hello") == "Merhaba"
    assert sent["url"] == "http://lt.local:5000/translate" and sent["api_key"] == "k" and sent["format"] == "html"
    no_network.setattr(mt_mod.requests, "post", lambda *a, **k: Resp(429, {}, "slow down"))
    with pytest.raises(RateLimited):
        e.translate_one("Hello")


def test_libretranslate_unreachable(no_network):
    def get(*a, **k):
        raise requests.ConnectionError("refused")
    no_network.setattr(mt_mod.requests, "get", get)
    with pytest.raises(EngineUnavailable):
        make_engine("libretranslate").check()


def test_translators_lib_missing_or_errors(monkeypatch):
    e = make_engine("bing")
    fake = type(sys)("translators")

    def tt(text, **kw):
        if text == "rate":
            raise RuntimeError("HTTP 429 Too Many Requests")
        if text == "empty":
            return ""
        return f"{kw['translator']}:{text}"
    fake.translate_text = tt
    monkeypatch.setitem(sys.modules, "translators", fake)
    e.check()
    assert e.translate_one("hi") == "bing:hi"
    with pytest.raises(RateLimited):
        e.translate_one("rate")
    with pytest.raises(EngineError):
        e.translate_one("empty")
    monkeypatch.setitem(sys.modules, "translators", None)
    with pytest.raises(EngineUnavailable):
        e.check()


def test_argos_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "argostranslate", None)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", None)
    with pytest.raises(EngineUnavailable):
        make_engine("argos").check()


# ------------------------------------------------------------------ Ollama / OpenAI-compatible
def test_ollama_check_and_complete(no_network, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:11434")
    monkeypatch.setenv("EPUB_TR_OLLAMA_MAX_TOKENS", "")
    no_network.setattr(llm_mod.requests, "get", lambda url, timeout=None: Resp(200, {"models": [{"name": "gemma3:4b"}]}))
    body = {}

    def post(url, json=None, timeout=None):
        body.update(url=url, **json)
        return Resp(200, {"message": {"content": '<seg id="1">Merhaba</seg>'}})
    no_network.setattr(llm_mod.requests, "post", post)
    o = make_engine("ollama")
    assert o.host == "http://127.0.0.1:11434"
    o.check()
    assert o.complete("sys", "user text") == '<seg id="1">Merhaba</seg>'
    assert body["url"].endswith("/api/chat") and body["model"] == "gemma3:4b" and body["stream"] is False
    assert body["messages"][0] == {"role": "system", "content": "sys"} and body["options"]["num_predict"] >= 512


def test_ollama_model_not_pulled_or_down(no_network):
    no_network.setattr(llm_mod.requests, "get", lambda url, timeout=None: Resp(200, {"models": [{"name": "x:1b"}]}))
    with pytest.raises(EngineUnavailable, match="not pulled"):
        make_engine("ollama", model="gemma3:4b").check()

    def down(*a, **k):
        raise requests.ConnectionError("refused")
    no_network.setattr(llm_mod.requests, "get", down)
    with pytest.raises(EngineUnavailable, match="not running"):
        make_engine("ollama").check()
    no_network.setattr(llm_mod.requests, "post", lambda *a, **k: Resp(500, {}, "oom"))
    with pytest.raises(EngineError, match="HTTP 500"):
        make_engine("ollama").complete("s", "u")


@pytest.mark.parametrize("preset, keyvar", [("openrouter", "OPENROUTER_API_KEY"), ("gemini", "GEMINI_API_KEY"),
                                            ("groq", "GROQ_API_KEY"), ("mistral", "MISTRAL_API_KEY")])
def test_openai_compatible_presets(no_network, monkeypatch, preset, keyvar):
    monkeypatch.delenv(keyvar, raising=False)
    e = make_engine(preset)
    with pytest.raises(EngineUnavailable, match=keyvar):
        e.check()
    monkeypatch.setenv(keyvar, "test-key")
    e.check()
    seen = {}

    def post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, auth=headers["Authorization"], model=json["model"])
        return Resp(200, {"choices": [{"message": {"content": "çıktı"}}]})
    no_network.setattr(llm_mod.requests, "post", post)
    assert e.complete("s", "u") == "çıktı"
    assert seen["url"].endswith("/chat/completions") and seen["auth"] == "Bearer test-key" and seen["model"]
    no_network.setattr(llm_mod.requests, "post", lambda *a, **k: Resp(429, {}, "rate"))
    with pytest.raises(RateLimited):
        e.complete("s", "u")


def test_openai_model_override(monkeypatch):
    monkeypatch.setenv("EPUB_TR_GROQ_MODEL", "my-model")
    assert make_engine("groq").model == "my-model"
    assert make_engine("groq", model="cli-model").model == "cli-model"


# ------------------------------------------------------------------ OpenCode
def test_parse_opencode_json_events():
    out = "\n".join([
        json.dumps({"type": "step_start", "part": {}}),
        json.dumps({"type": "text", "part": {"text": '<seg id="1">Bir</seg>'}}),
        "not json {",
        json.dumps({"type": "text", "part": {"text": '\n<seg id="2">İki</seg>'}}),
        json.dumps({"type": "error", "error": {"name": "APIError", "message": "x"}}),
    ])
    text, errors = parse_opencode_json(out)
    assert text == '<seg id="1">Bir</seg>\n<seg id="2">İki</seg>' and "APIError" in errors[0]


def test_parse_opencode_plain_text_fallback():
    text, errors = parse_opencode_json("\x1b[32mplain answer\x1b[0m")
    assert text == "plain answer" and errors == []


def test_opencode_defaults_and_missing_binary(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCODE_BIN", str(tmp_path / "missing-opencode"))
    monkeypatch.delenv("EPUB_TR_OPENCODE_MODEL", raising=False)
    oc = OpenCode()
    assert oc.model == OPENCODE_FREE_MODELS[0] and oc.model not in oc.fallback_models
    with pytest.raises(EngineUnavailable):
        oc.check()


def test_opencode_agent_config_is_utf8(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    oc = OpenCode()
    oc.workdir = str(tmp_path / "agents")
    d = oc._write_agent("Türkçe sistem istemi: ğüşıöç")
    with open(os.path.join(d, "opencode.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    agent = cfg["agent"]["epubtr"]
    assert agent["prompt"].endswith("ğüşıöç") and agent["tools"] == {"*": False} and cfg["share"] == "disabled"
    assert oc._write_agent("Türkçe sistem istemi: ğüşıöç") == d  # cached per prompt


def _fake_opencode(tmp_path, body):
    script = tmp_path / "opencode"
    script.write_text(f"#!{sys.executable}\nimport sys, json\nargs = sys.argv[1:]\n{body}\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


posix_only = pytest.mark.skipif(os.name == "nt", reason="fake opencode binary is a POSIX script")


@posix_only
def test_opencode_run_with_fake_binary(monkeypatch, tmp_path):
    body = ('model = args[args.index("-m") + 1]\n'
            'print(json.dumps({"type": "text", "part": {"text": "<seg id=\\"1\\">" + model + "</seg>"}}))')
    monkeypatch.setenv("OPENCODE_BIN", _fake_opencode(tmp_path, body))
    oc = OpenCode(model="opencode/big-pickle")
    oc.workdir = str(tmp_path / "agents")
    oc.check()
    assert oc.complete("sys", '<seg id="1">Hi</seg>') == '<seg id="1">opencode/big-pickle</seg>'


@posix_only
def test_opencode_rate_limit_switches_model(monkeypatch, tmp_path):
    body = ('model = args[args.index("-m") + 1]\n'
            'if model == "opencode/big-pickle":\n'
            '    sys.stderr.write("ERROR FreeUsageLimitError: Rate limit exceeded\\n"); sys.stderr.flush()\n'
            '    import time; time.sleep(5); sys.exit(1)\n'
            'print(json.dumps({"type": "text", "part": {"text": "ok from " + model}}))')
    monkeypatch.setenv("OPENCODE_BIN", _fake_opencode(tmp_path, body))
    oc = OpenCode(model="opencode/big-pickle")
    oc.workdir = str(tmp_path / "agents")
    assert oc.complete("sys", "u") == "ok from " + OPENCODE_FREE_MODELS[1]
    assert oc.model == OPENCODE_FREE_MODELS[1]  # sticks to the model that worked


@posix_only
def test_opencode_empty_output_and_timeout(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCODE_BIN", _fake_opencode(tmp_path, 'sys.stderr.write("boom\\n")'))
    oc = OpenCode(auto_model=False)
    oc.workdir = str(tmp_path / "agents")
    with pytest.raises(EngineError, match="empty output"):
        oc.complete("s", "u")
    monkeypatch.setenv("OPENCODE_BIN", _fake_opencode(tmp_path, "import time; time.sleep(30)"))
    oc = OpenCode(auto_model=False, timeout=1)
    oc.workdir = str(tmp_path / "agents")
    with pytest.raises(EngineError, match="timed out"):
        oc.complete("s", "u")


@posix_only
def test_opencode_empty_output_switches_model(monkeypatch, tmp_path):
    """Seen in a real run: a free model returned nothing (exit 0) again and again."""
    body = ('model = args[args.index("-m") + 1]\n'
            'if model == "opencode/big-pickle":\n'
            '    sys.exit(0)\n'
            'print(json.dumps({"type": "text", "part": {"text": "ok from " + model}}))')
    monkeypatch.setenv("OPENCODE_BIN", _fake_opencode(tmp_path, body))
    oc = OpenCode(model="opencode/big-pickle")
    oc.workdir = str(tmp_path / "agents")
    assert oc.complete("sys", "u") == "ok from " + OPENCODE_FREE_MODELS[1]
