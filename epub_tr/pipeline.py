"""Translation pipeline: chunking, context, glossary, polish pass, cache, concurrency, fallback."""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import prompts
from .blocks import TOKEN_RE, TagMismatch, validate
from .engines.base import Engine, EngineError, EngineUnavailable, RateLimited

log = logging.getLogger("epub_tr")

SEG_RE = re.compile(r'<seg\s+id\s*=\s*"?(\d+)"?\s*>(.*?)</seg\s*>', re.S | re.I)
OUTER_RE = re.compile(r"<g(\d+)>(.*)</g\1>", re.S)
GLOSS_RE = re.compile(r"<glossary>(.*?)(?:</glossary>|$)", re.S | re.I)
NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)?)\b")
COMMON_CAPS = {"The", "And", "But", "For", "She", "His", "Her", "They", "There", "Then", "When", "What", "Which",
               "This", "That", "With", "Christmas", "Mr", "Mrs", "Miss", "God", "Sir", "Madame", "Yes", "Not",
               "Oh", "One", "Two", "Monday", "Sunday", "January", "December", "English", "American"}


def detect_names(texts, limit=40):
    """Very cheap proper-noun detector: capitalised mid-sentence words never seen lowercase."""
    caps, lower = Counter(), set()
    for t in texts:
        for w in re.findall(r"\b[a-z][a-z]+\b", t):
            lower.add(w)
        for sent in re.split(r"(?<=[.!?\"“”])\s+", t):
            words = sent.split()
            for w in words[1:]:
                m = NAME_RE.fullmatch(w.strip(",.;:!?\"'“”‘’()—-"))
                if m:
                    caps[m.group(1)] += 1
    names = [w for w, c in caps.most_common() if c >= 2 and w.lower() not in lower and w not in COMMON_CAPS]
    return names[:limit]


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.engine_segments = Counter()
        self.failures = Counter()
        self.errors = []
        self.calls = Counter()
        self.tag_issues = 0
        self.polished = 0

    def add_error(self, engine, msg):
        with self.lock:
            self.failures[engine] += 1
            if len(self.errors) < 50:
                self.errors.append(f"{engine}: {msg}")


class Translator:
    def __init__(self, engines: list[Engine], cache, source="en", target="tr", workers=None,
                 chunk_chars=2500, context_paras=3, polish=False, polish_engine: Engine | None = None,
                 dialogue="quotes", glossary=None, book_id="book", retries=3, progress=None):
        if not engines:
            raise ValueError("no engines")
        self.engines = engines
        self.primary = engines[0]
        self.cache = cache
        self.src, self.tgt = source, target
        self.workers = workers or self.primary.default_workers
        self.chunk_chars = chunk_chars
        self.context_paras = context_paras
        self.polish = polish
        self.polish_engine = polish_engine or (self.primary if self.primary.is_llm else None)
        self.dialogue = dialogue
        self.book_id = book_id
        self.retries = retries
        self.progress = progress
        self.stats = Stats()
        self.glossary = dict(cache.load_glossary(book_id)) if cache else {}
        self.glossary.update(glossary or {})
        self.gloss_lock = threading.Lock()
        self.names = []
        self.cache_models = {e.name: e.model_id for e in engines}
        rules = prompts.rules_for(target, dialogue)
        self.system = prompts.SYSTEM_PROMPT.format(src=prompts.lang_name(source), tgt=prompts.lang_name(target), rules=rules)
        self.polish_system = prompts.POLISH_SYSTEM.format(src=prompts.lang_name(source), tgt=prompts.lang_name(target), rules=rules)

    # ------------------------------------------------------------ helpers
    def _stage(self, engine):
        if engine.is_llm:
            return "llm-polished" if (self.polish and self.polish_engine) else "llm"
        return "mt"

    def _cache_get(self, engine, seg):
        if not self.cache:
            return None
        return self.cache.get(engine.name, self.cache_models.get(engine.name, ""), self._stage(engine),
                              self.src, self.tgt, seg.source)

    def _cache_put(self, engine, seg, result):
        if self.cache:
            self.cache.put(engine.name, self.cache_models.get(engine.name, ""), self._stage(engine),
                           self.src, self.tgt, seg.source, result)

    def _tick(self, n):
        if self.progress:
            self.progress(n)

    def _call_with_retries(self, engine, fn):
        last = None
        for attempt in range(self.retries):
            try:
                with self.stats.lock:
                    self.stats.calls[engine.name] += 1
                return fn()
            except EngineUnavailable:
                raise
            except RateLimited as e:
                last = e
                self.stats.add_error(engine.name, str(e))
                time.sleep(min(90, 15 * (2 ** attempt)))
            except (EngineError, TagMismatch, KeyError, ValueError) as e:
                last = e
                self.stats.add_error(engine.name, str(e))
                time.sleep(2 * (2 ** attempt))
        raise EngineError(f"{engine.name} failed after {self.retries} attempts: {last}")

    # ------------------------------------------------------------ public
    def run(self, docs_segments: list[list]):
        all_segs = [s for d in docs_segments for s in d]
        self.names = detect_names([s.enc.plain() for s in all_segs if s.kind == "text"])
        if self.primary.is_llm:
            self._run_llm(docs_segments)
        else:
            self._run_mt(all_segs)
        harmonize_toc(all_segs)
        if self.cache:
            self.cache.save_glossary(self.book_id, self.glossary)
        return self.stats

    # ------------------------------------------------------------ MT
    def _run_mt(self, segs):
        todo = []
        for s in segs:
            r = self._cache_get(self.primary, s)
            if r is not None:
                s.translation, s.engine = self._rewrap(self.primary, s, r), self.primary.name
                self.stats.engine_segments[self.primary.name + " (cache)"] += 1
                self._tick(1)
            else:
                todo.append(s)
        batches, cur, size = [], [], 0
        for s in todo:
            if cur and (size + len(s.source) > self.primary.max_chars or len(cur) >= 25):
                batches.append(cur)
                cur, size = [], 0
            cur.append(s)
            size += len(s.source)
        if cur:
            batches.append(cur)
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = [ex.submit(self._unit, b, None) for b in batches]
            for f in as_completed(futs):
                f.result()

    def _mt_translate(self, engine, segs):
        texts = [s.source if engine.supports_tags else s.enc.plain() for s in segs]
        res = self._call_with_retries(engine, lambda: engine.translate_batch(texts))
        if len(res) != len(segs):
            raise EngineError("result count mismatch")
        return [self._rewrap(engine, s, r) for s, r in zip(segs, res)]

    @staticmethod
    def _rewrap(engine, seg, r):
        """Tag-less engines: re-wrap segments whose whole content is one inline element
        (e.g. <a id=..>Title</a> in a TOC) so links/anchors keep their text."""
        if not r:
            return r
        # LLMs like to wrap short titles in quotes the source does not have
        q = '"“”«»'
        src_plain = seg.enc.plain()
        rr = r.strip()
        if len(rr) > 2 and rr[0] in q and rr[-1] in q and src_plain[:1] not in q and rr.count('"') + rr.count('“') + rr.count('”') == 2:
            r = rr[1:-1].strip()
        if TOKEN_RE.search(r):
            return r
        m = OUTER_RE.fullmatch(seg.source)
        if m and "<" not in m.group(2):
            return f"<g{m.group(1)}>{r}</g{m.group(1)}>"
        return r

    # ------------------------------------------------------------ unit with fallback chain
    def _unit(self, segs, ctx):
        """Translate one unit (list of segments) trying engines in order."""
        try:
            self._unit_inner(segs, ctx)
        finally:
            self._tick(len(segs))

    def _unit_inner(self, segs, ctx):
        last = None
        for engine in self.engines:
            try:
                if engine.is_llm:
                    res = self._llm_translate(engine, segs, ctx)
                else:
                    res = self._mt_translate(engine, segs)
                for s, r in zip(segs, res):
                    if r is None:
                        continue
                    r = self._rewrap(engine, s, r)
                    s.translation, s.engine = r, engine.name
                    self._cache_put(engine, s, r)
                    if s.enc.has_tags:
                        try:
                            validate(r, s.enc)
                        except TagMismatch:
                            self.stats.tag_issues += 1
                n_done = sum(1 for s in segs if s.translation)
                with self.stats.lock:
                    self.stats.engine_segments[engine.name] += n_done
                missing = [s for s in segs if not s.translation]
                if missing and engine is not self.engines[-1]:
                    segs = missing
                    continue
                return
            except (EngineError, EngineUnavailable) as e:
                last = e
                log.warning("engine %s failed for %d segments: %s", engine.name, len(segs), e)
                self.stats.add_error(engine.name, f"unit failed: {e}")
                continue
        log.error("all engines failed for unit starting %s: %s", segs[0].uid, last)

    # ------------------------------------------------------------ LLM
    def _run_llm(self, docs_segments):
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = [ex.submit(self._llm_doc, d) for d in docs_segments if d]
            for f in as_completed(futs):
                f.result()

    def _chunks(self, segs):
        cur, size = [], 0
        for s in segs:
            if cur and size + len(s.source) > self.chunk_chars:
                yield cur
                cur, size = [], 0
            cur.append(s)
            size += len(s.source)
        if cur:
            yield cur

    def _llm_doc(self, segs):
        ctx = []  # list of (source, translation) for continuity
        for chunk in self._chunks(segs):
            cached = [self._cache_get(self.primary, s) for s in chunk]
            if all(c is not None for c in cached):
                for s, c in zip(chunk, cached):
                    s.translation, s.engine = self._rewrap(self.primary, s, c), self.primary.name
                self.stats.engine_segments[self.primary.name + " (cache)"] += len(chunk)
                self._tick(len(chunk))
            else:
                self._unit(chunk, ctx)
            for s in chunk:
                if s.translation:
                    ctx.append((s.enc.plain(), s.translation))
            ctx[:] = ctx[-self.context_paras:]

    def _glossary_for(self, text):
        with self.gloss_lock:
            if len(self.glossary) <= 40:
                g = dict(self.glossary)
            else:
                g = {k: v for k, v in self.glossary.items() if k in text}
        names = [n for n in self.names if n in text and n not in g]
        return g, names

    def _context_for(self, ctx):
        out, budget = [], 1500
        for src, tr in reversed(ctx or []):
            if budget <= 0:
                break
            out.insert(0, (src[:budget], tr[:budget]))
            budget -= len(src) + len(tr)
        return out

    def _llm_translate(self, engine, segs, ctx, depth=0):
        joined = " ".join(s.source for s in segs)
        gl, names = self._glossary_for(joined)
        user = prompts.USER_TEMPLATE.format(
            glossary_part=prompts.glossary_part(gl, names),
            context_part=prompts.context_part(self._context_for(ctx)),
            src=prompts.lang_name(self.src), tgt=prompts.lang_name(self.tgt),
            segments=prompts.format_segments((i + 1, s.source) for i, s in enumerate(segs)))

        def call():
            out = engine.complete(self.system, user)
            found = {int(i): t.strip() for i, t in SEG_RE.findall(out)}
            if not found:
                raise EngineError(f"no <seg> in output: {out[:200]!r}")
            return out, found

        out, found = self._call_with_retries(engine, call)
        self._merge_glossary(out)
        res = [found.get(i + 1) for i in range(len(segs))]
        missing = [i for i, r in enumerate(res) if not r]
        if missing and depth < 2:
            sub = [segs[i] for i in missing]
            log.info("%d segments missing in LLM output, retrying them", len(sub))
            subres = self._llm_translate(engine, sub, ctx, depth + 1)
            for i, r in zip(missing, subres):
                res[i] = r
        if self.polish and self.polish_engine and any(res):
            res = self._polish(segs, res)
        return res

    def _polish(self, segs, draft):
        engine = self.polish_engine
        idx = [i for i, d in enumerate(draft) if d]
        gl, names = self._glossary_for(" ".join(segs[i].source for i in idx))
        user = prompts.POLISH_TEMPLATE.format(
            glossary_part=prompts.glossary_part(gl, names), src=prompts.lang_name(self.src),
            tgt=prompts.lang_name(self.tgt),
            original=prompts.format_segments((i + 1, segs[i].source) for i in idx),
            draft=prompts.format_segments((i + 1, draft[i]) for i in idx))
        try:
            out = self._call_with_retries(engine, lambda: engine.complete(self.polish_system, user))
        except EngineError as e:
            log.warning("polish pass failed, keeping draft: %s", e)
            return draft
        found = {int(i): t.strip() for i, t in SEG_RE.findall(out)}
        res = list(draft)
        for i in idx:
            p = found.get(i + 1)
            if not p:
                continue
            if segs[i].enc.has_tags:
                try:
                    validate(p, segs[i].enc)
                except TagMismatch:
                    continue
            res[i] = p
            self.stats.polished += 1
        return res

    def _merge_glossary(self, out):
        m = GLOSS_RE.search(out)
        if not m:
            return
        with self.gloss_lock:
            for line in m.group(1).splitlines():
                if "=>" not in line:
                    continue
                k, v = [x.strip(" -*•\t\"'") for x in line.split("=>", 1)]
                if k and v and len(k) < 60 and len(v) < 80 and k not in self.glossary:
                    self.glossary[k] = v


def harmonize_toc(segs):
    """Make TOC / nav labels identical to the translated chapter headings they point to."""
    heads = {}
    for s in segs:
        if s.kind == "heading" and s.translation:
            heads.setdefault(s.enc.plain().strip().lower(), TOKEN_RE.sub("", s.translation).strip())
    for s in segs:
        if s.kind != "toc" and not (s.doc is not None and s.doc.is_nav):
            continue
        t = heads.get(s.enc.plain().strip().lower())
        if not t:
            continue
        m = OUTER_RE.fullmatch(s.source)
        s.translation = f"<g{m.group(1)}>{t}</g{m.group(1)}>" if (m and "<" not in m.group(2)) else (
            t if not s.enc.has_tags else s.translation)
