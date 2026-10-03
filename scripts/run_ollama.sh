#!/bin/sh
# usage: scripts/run_ollama.sh MODEL TAG [extra args]
cd "$(dirname "$0")/.." && . .venv/bin/activate
M=$1; T=$2; shift 2
epub-tr translate samples/pg7256.epub -e ollama -m "$M" --chunk-chars 1500 -o out/magi.$T.tr.epub \
  --stats out/logs/$T.json --dump out/logs/$T.jsonl -q "$@" > out/logs/$T.log 2>&1
