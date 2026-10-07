"""Free machine-translation engines (no API key needed)."""
from __future__ import annotations

import html
import urllib.parse

import requests

from .base import Engine, EngineError, EngineUnavailable, RateLimited, env

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}


def _pack(texts, max_chars):
    """Group texts into batches whose total length stays under max_chars."""
    batch, size = [], 0
    for i, t in enumerate(texts):
        if batch and size + len(t) > max_chars:
            yield batch
            batch, size = [], 0
        batch.append(i)
        size += len(t)
    if batch:
        yield batch


def _split_bytes(text, limit):
    """Split text into pieces of at most ``limit`` UTF-8 bytes: sentence boundaries first, then
    words, then characters (a single over-long sentence or word must not cause endless recursion)."""
    import re
    pieces = []
    for unit in re.split(r"(?<=[.!?;])\s+", text):
        if len(unit.encode()) <= limit:
            pieces.append(unit)
            continue
        for word in unit.split():
            while len(word.encode()) > limit:
                cut = limit
                while len(word[:cut].encode()) > limit:
                    cut -= 1
                pieces.append(word[:cut])
                word = word[cut:]
            pieces.append(word)
    chunks, cur = [], ""
    for p in pieces:
        cand = (cur + " " + p).strip() if cur else p
        if cur and len(cand.encode()) > limit:
            chunks.append(cur)
            cur = p
        else:
            cur = cand
    if cur:
        chunks.append(cur)
    return chunks


class GoogleFree(Engine):
    """Google Translate without key.

    1. ``clients5.google.com/translate_a/t`` (Chrome dictionary extension endpoint,
       accepts several ``q`` values per request and keeps HTML-ish tags), then
    2. ``deep-translator``'s GoogleTranslator as fallback.
    """

    name = "google"
    max_chars = 4500
    default_workers = 4

    def translate_batch(self, texts):
        out = [None] * len(texts)
        for idx in _pack(texts, self.max_chars):
            res = self._clients5([texts[i] for i in idx])
            for i, r in zip(idx, res):
                out[i] = r
        return out

    def _clients5(self, qs):
        try:
            r = requests.post("https://clients5.google.com/translate_a/t",
                              params={"client": "dict-chrome-ex", "sl": self.source, "tl": self.target},
                              data={"q": qs}, headers=UA, timeout=30)
        except requests.RequestException as e:
            raise EngineError(f"google network error: {e}")
        if r.status_code == 429:
            return [self._deep(q) for q in qs]
        if r.status_code != 200:
            try:
                return [self._deep(q) for q in qs]
            except Exception:
                raise EngineError(f"google HTTP {r.status_code}")
        data = r.json()
        res = []
        for item in data:
            if isinstance(item, list):  # [translation, detected_lang] when sl=auto
                item = item[0]
            res.append(html.unescape(item) if "&#" in item else item)
        if len(res) != len(qs):
            raise EngineError("google: result count mismatch")
        return res

    def _deep(self, q):
        try:
            from deep_translator import GoogleTranslator
            from deep_translator.exceptions import TooManyRequests
        except ImportError:
            raise EngineUnavailable("deep-translator not installed")
        try:
            return GoogleTranslator(source=self.source, target=self.target).translate(q)
        except TooManyRequests as e:
            raise RateLimited(str(e))
        except Exception as e:
            raise EngineError(f"google(deep-translator): {e}")


class TranslatorsLib(Engine):
    """Bing / Yandex / ModernMT / Reverso ... through the `translators` package (GPL-3, optional)."""

    max_chars = 1000
    default_workers = 2

    def __init__(self, provider, **kw):
        super().__init__(**kw)
        self.provider = provider
        self.name = provider.lower()

    def check(self):
        try:
            import translators  # noqa: F401
        except ImportError:
            raise EngineUnavailable("pip install translators")

    def translate_one(self, text):
        import translators as ts
        try:
            r = ts.translate_text(text, translator=self.provider, from_language=self.source,
                                  to_language=self.target, timeout=30)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "Too Many" in msg:
                raise RateLimited(msg[:200])
            raise EngineError(f"{self.provider}: {msg[:200]}")
        if not r:
            raise EngineError(f"{self.provider}: empty result")
        return r


class MyMemory(Engine):
    """MyMemory public API. Anonymous quota ~5k chars/day per IP; set MYMEMORY_EMAIL for 50k/day."""

    name = "mymemory"
    max_chars = 480
    supports_tags = True
    default_workers = 2

    def translate_one(self, text):
        if len(text.encode()) > 500:
            return " ".join(self.translate_one(c) for c in _split_bytes(text, 480))
        params = {"q": text, "langpair": f"{self.source}|{self.target}"}
        if env("MYMEMORY_EMAIL"):
            params["de"] = env("MYMEMORY_EMAIL")
        try:
            r = requests.get("https://api.mymemory.translated.net/get", params=params, timeout=30)
            data = r.json()
        except Exception as e:
            raise EngineError(f"mymemory: {e}")
        out = data.get("responseData", {}).get("translatedText") or ""
        if "MYMEMORY WARNING" in out or data.get("responseStatus") in (429, "429"):
            raise RateLimited("mymemory: daily free quota exhausted")
        if data.get("responseStatus") not in (200, "200"):
            raise EngineError(f"mymemory: {data.get('responseDetails')}")
        return html.unescape(out)


class Lingva(Engine):
    """Lingva Translate (privacy front-end for Google). LINGVA_URL to choose an instance."""

    name = "lingva"
    max_chars = 1500
    default_workers = 2
    INSTANCES = ["https://lingva.ml", "https://lingva.lunar.icu", "https://translate.plausibility.cloud"]

    def translate_one(self, text):
        insts = [env("LINGVA_URL")] if env("LINGVA_URL") else self.INSTANCES
        last = None
        for inst in insts:
            try:
                url = f"{inst.rstrip('/')}/api/v1/{self.source}/{self.target}/" + urllib.parse.quote(text, safe="")
                r = requests.get(url, timeout=30, headers=UA)
                if r.status_code == 200:
                    tr = r.json().get("translation", "")
                    if tr and tr.strip() != text.strip():
                        return tr
                    last = "returned untranslated text (upstream blocked)"
                else:
                    last = f"HTTP {r.status_code}"
            except Exception as e:
                last = str(e)
        raise EngineError(f"lingva: {last}")


class LibreTranslate(Engine):
    """LibreTranslate server. LIBRETRANSLATE_URL (default http://localhost:5000) [+ LIBRETRANSLATE_API_KEY]."""

    name = "libretranslate"
    max_chars = 2000

    def check(self):
        url = env("LIBRETRANSLATE_URL", "http://localhost:5000").rstrip("/") + "/languages"
        try:
            requests.get(url, timeout=5).raise_for_status()
        except Exception as e:
            raise EngineUnavailable(f"libretranslate not reachable at {url} ({e.__class__.__name__}); "
                                    "run `pip install libretranslate && libretranslate` or set LIBRETRANSLATE_URL")

    def translate_one(self, text):
        url = env("LIBRETRANSLATE_URL", "http://localhost:5000").rstrip("/") + "/translate"
        payload = {"q": text, "source": self.source, "target": self.target, "format": "html"}
        if env("LIBRETRANSLATE_API_KEY"):
            payload["api_key"] = env("LIBRETRANSLATE_API_KEY")
        try:
            r = requests.post(url, json=payload, timeout=60)
        except requests.RequestException as e:
            raise EngineUnavailable(f"libretranslate not reachable at {url}: {e}")
        if r.status_code == 429:
            raise RateLimited("libretranslate 429")
        if r.status_code != 200:
            raise EngineError(f"libretranslate HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["translatedText"]


class Argos(Engine):
    """Offline Argos Translate (OpenNMT/CTranslate2). Installs the en->tr model on first use."""

    name = "argos"
    supports_tags = False
    max_chars = 3000
    default_workers = 1
    _ready = False

    def check(self):
        try:
            import argostranslate.translate  # noqa: F401
        except ImportError:
            raise EngineUnavailable("pip install argostranslate")
        self._ensure()

    def _ensure(self):
        if Argos._ready:
            return
        import argostranslate.package as pkg
        import argostranslate.translate as tr
        langs = {lang.code: lang for lang in tr.get_installed_languages()}
        src, tgt = langs.get(self.source), langs.get(self.target)
        if src and tgt and src.get_translation(tgt):
            Argos._ready = True
            return
        pkg.update_package_index()
        cand = [p for p in pkg.get_available_packages() if p.from_code == self.source and p.to_code == self.target]
        if not cand:
            raise EngineUnavailable(f"no argos model {self.source}->{self.target}")
        pkg.install_from_path(cand[0].download())
        Argos._ready = True

    def translate_one(self, text):
        self._ensure()
        import argostranslate.translate as tr
        return tr.translate(text, self.source, self.target)
