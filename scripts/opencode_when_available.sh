#!/bin/sh
# Waits until the OpenCode Zen free-tier quota for this IP is available again, then translates the
# whole test book with the opencode engine (draft run + polish run) and writes a comparison file.
# usage: nohup scripts/opencode_when_available.sh &   (log: out/logs/opencode-wait.log)
cd "$(dirname "$0")/.." && . .venv/bin/activate
LOG=out/logs/opencode-wait.log
MODEL=${EPUB_TR_OPENCODE_MODEL:-opencode/big-pickle}
for i in $(seq 1 96); do   # up to ~16 hours, every 10 minutes
  echo "$(date '+%F %T') probe $i" >> $LOG
  if epub-tr translate samples/pg7256.epub -e opencode -m "$MODEL" --limit 2 --retries 1 --no-toc \
       -o /tmp/oc_probe.epub -q >> $LOG 2>&1; then
    echo "$(date '+%F %T') quota available, running full book" >> $LOG
    epub-tr translate samples/pg7256.epub -e opencode -m "$MODEL" -o out/magi.opencode.tr.epub \
      --stats out/logs/opencode.json --dump out/logs/opencode.jsonl -q > out/logs/opencode.log 2>&1
    epub-tr translate samples/pg7256.epub -e opencode -m "$MODEL" --polish -o out/magi.opencode-polish.tr.epub \
      --stats out/logs/opencode-polish.json --dump out/logs/opencode-polish.jsonl -q > out/logs/opencode-polish.log 2>&1
    epub-tr translate samples/pg7256.epub -e opencode -m "$MODEL" --polish --bilingual -o out/magi.opencode-polish.bilingual.epub \
      -q > out/logs/opencode-bilingual.log 2>&1
    python scripts/compare.py 2:0 2:13 2:27 2:44 > out/logs/opencode-comparison.md
    for f in out/magi.opencode*.epub; do epubcheck "$f" >> out/logs/opencode-epubcheck.log 2>&1; done
    echo "$(date '+%F %T') done" >> $LOG
    exit 0
  fi
  sleep 600
done
