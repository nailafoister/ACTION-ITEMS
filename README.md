# ACTION-ITEMS Dashboard

Static GitHub Pages dashboard for open SW Validation action items from the **general tracker** Google Sheet and Jira epics **AVSV-2461** (Init 2) and **AVSV-1965** (Operating Plan).

**Live site:** https://nailafoister.github.io/ACTION-ITEMS/#Naila-Foister

## Sources

| Source | URL |
|--------|-----|
| Google Sheet | https://docs.google.com/spreadsheets/d/1qw-UoMqKG2tWO5JNwDYo2bSQzecFJaJJ/edit |
| Jira Init 2 | https://gm-sdv.atlassian.net/browse/AVSV-2461 |
| Jira Op Plan | https://gm-sdv.atlassian.net/browse/AVSV-1965 |

Active items exclude statuses such as Completed, Duplicate, Done, Resolved, Closed, and Cancelled.

## Prerequisites (each teammate)

1. Clone this repo and open the folder in **Cursor**.
2. Connect MCP in Cursor:
   - **Atlassian** → `gm-sdv.atlassian.net` (Jira read access)
   - **Google Drive** → read access to the tracker spreadsheet
3. Authenticate **GitHub** on your machine (no tokens in repo or prompts):
   ```bash
   gh auth login
   ```
   Or use SSH:
   ```bash
   git remote set-url origin git@github.com:nailafoister/ACTION-ITEMS.git
   ```
4. Python 3 + `openpyxl`:
   ```bash
   pip install openpyxl
   ```

## Refresh the dashboard (manual — no Slack)

**Option A — Cursor Agent (recommended)**

Open Agent chat in this repo. The rule `.cursor/rules/action-items-dashboard.md` applies automatically. Ask:

> Run Phase 1 only: refresh data from Sheet and Jira, rebuild `docs/index.html`, commit and push. Skip Phase 2.

**Option B — After data files exist**

If `data/general-tracker.xlsx`, `data/jira-init2.json`, and `data/jira-opex.json` are already present (e.g. from a prior agent run):

```bash
./scripts/refresh_dashboard.sh
```

The agent must still fetch fresh Sheet/Jira data periodically; the shell script only builds HTML and pushes git.

## Scheduled run + Slack (team automation)

Use a **Cursor Automation** (scheduled) on this repo with:

- `IS_AUTOMATED_TRIGGER=true` in the automation environment
- Slack MCP → `#asv_team`
- Same Phase 1 + Phase 2 instructions as in `.cursor/rules/action-items-dashboard.md`

Manual refreshes must **not** set `IS_AUTOMATED_TRIGGER` so Slack is not notified.

Optional: set `CURSOR_AUTOMATION_URL` when building so the dashboard callout opens your team automation:

```bash
export CURSOR_AUTOMATION_URL="cursor://anysphere.cursor-deeplink/automations/<automation-id>"
```

## Repository layout

| Path | Purpose |
|------|---------|
| `scripts/phase1_build.py` | Build `docs/index.html` + `docs/tracking-data.json` |
| `scripts/refresh_dashboard.sh` | Build + commit + push (uses local `data/` inputs) |
| `docs/index.html` | Published GitHub Pages site |
| `.cursor/rules/action-items-dashboard.md` | Agent instructions for Phase 1 / 2 |

## Remove a leaked GitHub token (important)

If a personal access token (`ghp_…`) was ever pasted into chat, automation prompts, or git URLs:

1. **Revoke it immediately:** GitHub → **Settings** → **Developer settings** → **Personal access tokens** → delete/revoke the token.
2. **Check git remote** (must not contain `@` or `ghp_`):
   ```bash
   cd "/path/to/ACTION-ITEMS"
   git remote -v
   git remote set-url origin https://github.com/nailafoister/ACTION-ITEMS.git
   ```
3. **Clear stored credentials:**
   ```bash
   # If you used git credential-store:
   cat ~/.git-credentials   # remove any line containing github.com and ghp_
   # macOS Keychain: search "github.com" in Keychain Access and delete old entries
   gh auth logout -h github.com && gh auth login
   ```
4. **Search the repo** (should be clean):
   ```bash
   git grep -i ghp_ || echo "No token strings in tracked files"
   ```
5. **Cursor:** Edit any **Automation** or saved prompt that embedded a token; remove it and use `gh auth login` instead.
6. Create a **new** PAT only if needed, with minimal scope (`repo` for this repository), and never commit or paste it into agent prompts.

This repository intentionally does **not** store GitHub tokens.
