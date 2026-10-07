"""SQLite translation cache (also gives resume support for free)."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time


def default_cache_path() -> str:
    base = os.environ.get("EPUB_TR_CACHE") or os.path.join(
        os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "epub-tr", "cache.sqlite3")
    os.makedirs(os.path.dirname(base), exist_ok=True)
    return base


class Cache:
    def __init__(self, path: str | None = None, enabled: bool = True):
        self.enabled = enabled
        self.path = path or default_cache_path()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        if enabled:
            self.db = sqlite3.connect(self.path, check_same_thread=False, timeout=60)
            self.db.execute("PRAGMA busy_timeout=60000")
            for attempt in range(20):  # several processes may open the cache at once
                try:
                    self.db.execute("PRAGMA journal_mode=WAL")
                    break
                except sqlite3.OperationalError:
                    time.sleep(0.5 + attempt * 0.2)
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS tr (key TEXT PRIMARY KEY, engine TEXT, model TEXT, stage TEXT,"
                " src TEXT, tgt TEXT, source TEXT, result TEXT, created REAL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS glossary (book TEXT, term TEXT, target TEXT, PRIMARY KEY(book, term))")
            self.db.commit()

    def close(self):
        if self.enabled:
            with self._lock:
                self.db.close()

    @staticmethod
    def key(engine, model, stage, src, tgt, text) -> str:
        return hashlib.sha256("\x1f".join([engine, model or "", stage, src, tgt, text]).encode()).hexdigest()

    def get(self, engine, model, stage, src, tgt, text):
        if not self.enabled:
            return None
        k = self.key(engine, model, stage, src, tgt, text)
        with self._lock:
            row = self.db.execute("SELECT result FROM tr WHERE key=?", (k,)).fetchone()
        if row:
            self.hits += 1
            return row[0]
        self.misses += 1
        return None

    def put(self, engine, model, stage, src, tgt, text, result):
        if not self.enabled or result is None:
            return
        k = self.key(engine, model, stage, src, tgt, text)
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO tr VALUES (?,?,?,?,?,?,?,?,?)",
                            (k, engine, model, stage, src, tgt, text, result, time.time()))
            self.db.commit()

    # glossary persistence (per book) -> consistent names across resumed runs
    def load_glossary(self, book: str) -> dict:
        if not self.enabled:
            return {}
        with self._lock:
            rows = self.db.execute("SELECT term, target FROM glossary WHERE book=?", (book,)).fetchall()
        return dict(rows)

    def save_glossary(self, book: str, glossary: dict):
        if not self.enabled:
            return
        with self._lock:
            self.db.executemany("INSERT OR REPLACE INTO glossary VALUES (?,?,?)",
                                [(book, k, v) for k, v in glossary.items()])
            self.db.commit()
