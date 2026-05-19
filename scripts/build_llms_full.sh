#!/usr/bin/env bash
# Regenerate /var/www/html/llms-full.txt from current AIGEN spec/blog/docs corpus.
# Per llmstxt.org "full" extension: a single self-contained markdown file
# inlining every resource that /llms.txt links to, so LLM crawlers
# (GPTBot, ClaudeBot, Google-Extended, PerplexityBot) can ingest in one fetch.
#
# Run after specs/blog/docs change. Idempotent. Requires sudo for the install step.

set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="/tmp/llms-full.txt"
DEST="/var/www/html/llms-full.txt"

cd "$REPO"

{
  echo "# AIGEN — llms-full.txt"
  echo
  echo "> Full content of all resources linked from /llms.txt, inlined for LLM crawler ingestion."
  echo "> Per llmstxt.org spec. License: CC0 (specs) / CC-BY-4.0 (blog/docs)."
  echo "> Generated: $(date -u +%FT%TZ)"
  echo "> Canonical: https://cryptogenesis.duckdns.org/llms-full.txt"
  echo
  echo "---"
  echo
} > "$OUT"

append() {
  local label="$1" path="$2"
  if [[ ! -f "$path" ]]; then return; fi
  {
    echo "## $label"
    echo
    echo "_Source: \`$path\`_"
    echo
    cat "$path"
    echo
    echo
    echo "---"
    echo
  } >> "$OUT"
}

append "/llms.txt — index" /var/www/html/llms.txt
append "AIP-1 (Open Agent Bounty Protocol — Core)" specs/AIP-1.md
append "AIP-2 (Mission Type Registry)" specs/AIP-2.md
append "AIP-3 (Cross-chain Reputation)" specs/AIP-3.md
append "Thesis essay (2026-05-15) — Open Agent Economy" blog/2026-05-15-open-agent-economy.md
append "SECOND_IMPLEMENTATION.md — Federation guide" docs/SECOND_IMPLEMENTATION.md
append "READING_JOURNAL.md — How to read the autopilot journal" docs/READING_JOURNAL.md

size=$(wc -c < "$OUT")
echo "built: $OUT ($size bytes)"

if [[ "${1:-}" == "--install" ]]; then
  sudo cp "$OUT" "$DEST"
  sudo chmod 644 "$DEST"
  echo "installed: $DEST"
  curl -s -o /dev/null -w "live: HTTP %{http_code} size=%{size_download}\n" https://cryptogenesis.duckdns.org/llms-full.txt
fi
