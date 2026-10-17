---
description: Open action items dashboard — Phase 1 (always) and Phase 2 (Slack, automated only)
globs:
alwaysApply: true
---

# Action Items Dashboard Automation

Use when the user asks to refresh, update, or run Phase 1 / Phase 2 for the ACTION-ITEMS dashboard.

## Context sources

- **Sheet:** `1qw-UoMqKG2tWO5JNwDYo2bSQzecFJaJJ` (Action Items tab)
- **Jira:** parent `AVSV-2461`, parent `AVSV-1965` on `gm-sdv.atlassian.net`

## Phase 1 (always run)

1. Fetch Sheet (Google Drive MCP) and Jira issues (Atlassian MCP).
2. **Active items:** exclude statuses Completed, Complete, Duplicate, Done, Resolved, Closed, Cancelled (case-insensitive). Assign owner on each active row.
3. Write standalone `docs/index.html` with:
   - Callout: "💡 Need real-time data? …" with link on **manually refresh this dashboard** using `CURSOR_AUTOMATION_URL` env at build time or default `cursor://anysphere.cursor-deeplink/automations`
   - **Last Updated:** current date/time
   - Pie chart: open vs closed (all sources)
   - Stacked bar: owner × source, click → owner breakdown with Sheet/Jira deep links
   - Live link: https://nailafoister.github.io/ACTION-ITEMS/#Naila-Foister
4. Run `python3 scripts/phase1_build.py` with inputs under `data/` (save fetched JSON/xlsx there).
5. Git (no tokens in URLs):
   - `git add docs/index.html`
   - `git commit -m "Auto-update action items dashboard [Triggered by Team Run]"` (skip if no diff)
   - `git push origin main` — use the user's existing `gh` or SSH auth; never embed `ghp_` in commands.

## Phase 2 (conditional)

Run **only** if environment variable `IS_AUTOMATED_TRIGGER=true`.

1. Slack channel `#asv_team`
2. Tag Slack users matching Phase 1 active owners (lookup via Slack MCP); use plain text for non-users (e.g. "Int. V3 DRIS")
3. Message template includes dashboard link https://nailafoister.github.io/ACTION-ITEMS/#Naila-Foister and manual Cursor refresh note

If `IS_AUTOMATED_TRIGGER` is unset or not `true`, **skip Phase 2 entirely**.

## Security

Never write GitHub PATs to files, `git remote` URLs, commit messages, or chat. Use `gh auth login` or SSH.
