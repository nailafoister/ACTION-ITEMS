#!/usr/bin/env bash
# Build docs/index.html from data/ inputs and push to GitHub Pages branch.
# Fetch fresh Sheet + Jira via Cursor Agent (MCP) before running this script.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

XLSX="${ROOT}/data/general-tracker.xlsx"
JIRA_INIT2="${ROOT}/data/jira-init2.json"
JIRA_OPEX="${ROOT}/data/jira-opex.json"

for f in "$XLSX" "$JIRA_INIT2" "$JIRA_OPEX"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing: $f"
    echo "Run Cursor Agent Phase 1 first to download Sheet/Jira into data/, or copy files manually."
    exit 1
  fi
done

mkdir -p docs
python3 "${ROOT}/scripts/phase1_build.py" \
  --xlsx "$XLSX" \
  --jira-init2 "$JIRA_INIT2" \
  --jira-opex "$JIRA_OPEX"

if git remote get-url origin | grep -qE 'ghp_|://[^/]+:[^@]+@'; then
  echo "ERROR: origin URL must not contain a token (ghp_…) or user:password@. Fix with:"
  echo "  git remote set-url origin https://github.com/nailafoister/ACTION-ITEMS.git"
  exit 1
fi

git add docs/index.html
if git diff --cached --quiet; then
  echo "No changes to docs/index.html; skipping commit."
  exit 0
fi

git commit -m "Auto-update action items dashboard [Triggered by Team Run]"
git push origin main

echo "Done. Live site: https://nailafoister.github.io/ACTION-ITEMS/#Naila-Foister"
