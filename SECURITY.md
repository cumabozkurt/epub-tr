# Security Policy · Güvenlik Politikası

## Supported versions / Desteklenen sürümler

| Version | Supported |
|---|---|
| 1.1.x | ✅ |
| < 1.1 | ❌ (please upgrade / lütfen yükseltin) |

## What epub-tr does / epub-tr ne yapar

- It reads an EPUB (a ZIP of XHTML) with `lxml` and `ebooklib` and writes a new file. The input is never modified.
- It sends **book text** to the engine you choose. Online engines (Google, Bing, OpenCode Zen and others)
  see the text you translate. For private books, use `ollama` or `argos`, which run fully local.
- API keys are read only from environment variables. They are never written to the cache, logs, stats or dumps.
- The SQLite cache (`~/.cache/epub-tr/cache.sqlite3`) stores source and translated text. Delete it, or
  use `--no-cache`, for sensitive material.

## Reporting a vulnerability / Güvenlik açığı bildirme

Please report privately via **[GitHub → Security → Report a vulnerability](https://github.com/cumabozkurt/epub-tr/security/advisories/new)**.
Examples: XML entity expansion or path traversal from a crafted EPUB, or a key leaking into a log.
Do not open a public issue with details. Expect a first reply within 7 days.

Lütfen gizli olarak **GitHub → Security → Report a vulnerability** üzerinden bildirin (bağlantı yukarıda).
Örnekler: hazırlanmış bir EPUB'dan XML varlık genişletme ya da dizin geçişi, veya bir anahtarın günlüğe
sızması. Ayrıntıları herkese açık bir sorunda paylaşmayın. İlk yanıt en geç 7 gün içinde gelir.
