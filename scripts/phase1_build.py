#!/usr/bin/env python3
"""Build docs/index.html and docs/tracking-data.json from Sheet + Jira inputs."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import openpyxl

SHEET_ID = "1qw-UoMqKG2tWO5JNwDYo2bSQzecFJaJJ"
SHEET_GID = 2
JIRA_BASE = "https://gm-sdv.atlassian.net/browse"
LIVE_URL = "https://nailafoister.github.io/ACTION-ITEMS/#Naila-Foister"
CURSOR_REFRESH_DEFAULT = "cursor://anysphere.cursor-deeplink/automations"

SOURCE_GENERAL = "General tracker"
SOURCE_INIT2 = "Init 2 Execution Meeting"
SOURCE_OPEX = "Operating Plan Execution"

CLOSED_STATUSES = frozenset(
    s.lower()
    for s in (
        "Completed",
        "Complete",
        "Duplicate",
        "Done",
        "Resolved",
        "Closed",
        "Cancelled",
    )
)

OPEN_SHEET = frozenset({"new", "in progress"})


def normalize_owner(raw: str | None) -> str:
    if not raw or not str(raw).strip():
        return "Unassigned"
    name = str(raw).strip()
    # First line only for multi-line owner cells
    name = name.split("\n")[0].strip()
    # Strip parenthetical pronouns (e.g. She/her/hers) from display names
    name = re.sub(
        r"\s*\((?:She|He|They)/[^)]+\)\s*$",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    if name.lower() == "naila":
        return "Naila Foister"
    return name


def owner_anchor(owner: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", owner).strip("-")
    return f"#{slug}"


def sheet_row_link(row_num: int) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
        f"#gid={SHEET_GID}&range=B{row_num}"
    )


def parse_sheet(xlsx_path: Path) -> tuple[list[dict], list[dict]]:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb["Action Items"]
    open_items: list[dict] = []
    closed_items: list[dict] = []
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or len(row) < 6:
            continue
        action = row[1]
        if not action or not str(action).strip():
            continue
        action_s = str(action).strip()
        if "Click to open in JIRA" in action_s:
            continue
        status = row[5]
        status_s = str(status).strip() if status is not None else ""
        owner_cell = row[2]
        owners = []
        if owner_cell:
            for part in str(owner_cell).split("\n"):
                o = normalize_owner(part)
                if o and o != "Unassigned":
                    owners.append(o)
        if not owners:
            owners = ["Unassigned"]
        due = row[6]
        timing = ""
        if due:
            if hasattr(due, "strftime"):
                timing = f"Due {due.strftime('%Y-%m-%d')}"
            else:
                timing = f"Due {due}"
        item = {
            "title": action_s,
            "owners": owners,
            "status": status_s,
            "timing": timing,
            "source": SOURCE_GENERAL,
            "link": sheet_row_link(idx),
            "link_label": f"Sheet row {idx}",
        }
        st_lower = status_s.lower()
        if st_lower in CLOSED_STATUSES or st_lower == "complete":
            closed_items.append(item)
        elif st_lower in OPEN_SHEET or st_lower not in CLOSED_STATUSES:
            # Treat unknown non-closed as open
            if st_lower in OPEN_SHEET or status_s:
                open_items.append(item)
    wb.close()
    return open_items, closed_items


def jira_is_closed(status: dict | None) -> bool:
    if not status:
        return False
    cat = status.get("statusCategory") or {}
    return cat.get("key") == "done" or status.get("name", "").lower() in CLOSED_STATUSES


def parse_jira_files(init2_path: Path, opex_path: Path) -> tuple[list[dict], list[dict]]:
    open_items: list[dict] = []
    closed_items: list[dict] = []

    def load(path: Path) -> list[dict]:
        if not path.exists():
            return []
        with path.open() as f:
            data = json.load(f)
        return data.get("issues", data if isinstance(data, list) else [])

    def process(issues: list[dict], source: str) -> None:
        for issue in issues:
            fields = issue.get("fields", {})
            parent = (fields.get("parent") or {}).get("key", "")
            if source == SOURCE_INIT2 and parent != "AVSV-2461":
                continue
            if source == SOURCE_OPEX and parent != "AVSV-1965":
                continue
            status = fields.get("status") or {}
            assignee = fields.get("assignee")
            owner = (
                normalize_owner(assignee.get("displayName"))
                if assignee
                else "Unassigned"
            )
            key = issue.get("key", "")
            item = {
                "title": fields.get("summary", key),
                "owners": [owner],
                "status": status.get("name", ""),
                "timing": "",
                "source": source,
                "link": f"{JIRA_BASE}/{key}",
                "link_label": key,
            }
            if jira_is_closed(status):
                closed_items.append(item)
            else:
                open_items.append(item)

    init2_issues = load(init2_path)
    opex_issues = load(opex_path)
    process(init2_issues, SOURCE_INIT2)
    process(opex_issues, SOURCE_OPEX)
    return open_items, closed_items


def split_jira_all(all_path: Path, init2_out: Path, opex_out: Path) -> None:
    """Split combined Jira search into init2 and opex JSON files."""
    with all_path.open() as f:
        data = json.load(f)
    issues = data.get("issues", [])
    init2 = [i for i in issues if (i.get("fields", {}).get("parent") or {}).get("key") == "AVSV-2461"]
    opex = [i for i in issues if (i.get("fields", {}).get("parent") or {}).get("key") == "AVSV-1965"]
    init2_out.write_text(json.dumps({"issues": init2}, indent=2))
    opex_out.write_text(json.dumps({"issues": opex}, indent=2))


def expand_by_owner(items: list[dict]) -> list[dict]:
    expanded = []
    for item in items:
        for owner in item["owners"]:
            copy = {**item, "owner": owner}
            expanded.append(copy)
    return expanded


def build_dashboard(
    open_active: list[dict],
    closed_all: list[dict],
    cursor_url: str,
    updated: datetime,
) -> str:
    by_owner: dict[str, list[dict]] = defaultdict(list)
    for item in open_active:
        by_owner[item["owner"]].append(item)

    owners_sorted = sorted(by_owner.keys(), key=lambda o: (-len(by_owner[o]), o.lower()))

    source_keys = [SOURCE_GENERAL, SOURCE_INIT2, SOURCE_OPEX]
    source_colors = {
        SOURCE_GENERAL: "#4da3ff",
        SOURCE_INIT2: "#7bdcb5",
        SOURCE_OPEX: "#f78fb3",
    }

    counts_by_owner_source: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item in open_active:
        counts_by_owner_source[item["owner"]][item["source"]] += 1

    summary_rows = []
    for owner in owners_sorted:
        total = len(by_owner[owner])
        parts = []
        for src in source_keys:
            c = counts_by_owner_source[owner][src]
            if c:
                parts.append(f"{src}: {c}")
        summary_rows.append(
            f"<tr><td>{html.escape(owner)}</td><td>{total}</td>"
            f"<td>{html.escape(', '.join(parts))}</td>"
            f'<td><a href="{owner_anchor(owner)}">View tasks</a></td></tr>'
        )

    owner_sections = []
    for owner in owners_sorted:
        rows = []
        for item in sorted(by_owner[owner], key=lambda x: (x["source"], x["title"])):
            rows.append(
                "<tr>"
                f"<td>{html.escape(item['title'])}</td>"
                f"<td>{html.escape(item['source'])}</td>"
                f"<td>{html.escape(item['status'])}</td>"
                f"<td>{html.escape(item['timing'])}</td>"
                f'<td><a href="{html.escape(item["link"])}" target="_blank" rel="noopener">'
                f"{html.escape(item['link_label'])}</a></td>"
                "</tr>"
            )
        owner_sections.append(
            f'<section class="owner-block" id="{owner_anchor(owner)[1:]}">'
            f"<h3>{html.escape(owner)}</h3>"
            "<table><thead><tr><th>Action item</th><th>Source</th><th>Status</th>"
            "<th>Timing</th><th>Link</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></section>"
        )

    bar_labels = owners_sorted
    bar_datasets = []
    for src in source_keys:
        data = [counts_by_owner_source[o][src] for o in bar_labels]
        links = [owner_anchor(o) if counts_by_owner_source[o][src] else "" for o in bar_labels]
        bar_datasets.append(
            {
                "label": src,
                "data": data,
                "backgroundColor": source_colors[src],
                "anchorLinks": links,
            }
        )

    open_count = len(open_active)
    closed_count = len(closed_all)
    ts = updated.strftime("%A, %B %d, %Y, %I:%M %p UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Open Action Items Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a2332;
      --text: #e8edf5;
      --muted: #9aa8bc;
      --accent: #4da3ff;
      --border: #2b3a52;
      --callout: #1e2d46;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      background: linear-gradient(160deg, #0b1020 0%, #121a28 45%, #0f1419 100%);
      color: var(--text);
      line-height: 1.45;
    }}
    main {{ max-width: 1140px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }}
    h1 {{ margin: 0 0 0.75rem; font-size: 1.85rem; }}
    .callout {{
      background: var(--callout);
      border: 1px solid var(--border);
      border-left: 4px solid var(--accent);
      padding: 0.85rem 1rem;
      border-radius: 8px;
      margin-bottom: 1rem;
    }}
    .meta {{ color: var(--muted); margin: 0.5rem 0 1.25rem; }}
    .charts {{
      display: grid;
      grid-template-columns: 1fr 1.4fr;
      gap: 1rem;
      margin: 1.25rem 0 2rem;
    }}
    @media (max-width: 900px) {{ .charts {{ grid-template-columns: 1fr; }} }}
    .chart-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
    }}
    .chart-card h2 {{ margin: 0 0 0.75rem; font-size: 1rem; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
      margin: 0.75rem 0 1.5rem;
    }}
    th, td {{
      padding: 0.65rem 0.75rem;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
      text-align: left;
    }}
    th {{ background: #223047; color: #d5e2f5; font-size: 0.85rem; }}
    tr:last-child td {{ border-bottom: none; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    h2.section {{ margin-top: 2rem; font-size: 1.25rem; }}
    h3 {{ margin: 1.75rem 0 0.35rem; font-size: 1.05rem; }}
    .owner-block {{ scroll-margin-top: 1rem; }}
    .live-link {{ margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <main>
    <div class="callout">
      💡 Need real-time data? You can
      <a href="{html.escape(cursor_url)}">manually refresh this dashboard</a>
      anytime directly from your own Cursor editor without triggering a Slack alert.
    </div>
    <h1>Open Action Items Dashboard</h1>
    <p class="meta"><strong>Last Updated:</strong> {html.escape(ts)}</p>
    <p class="live-link">
      <strong>Live deployment:</strong>
      <a href="{LIVE_URL}" target="_blank" rel="noopener">{LIVE_URL}</a>
    </p>
    <p class="meta">
      Sources:
      <a href="https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={SHEET_GID}">General tracker</a> ·
      <a href="{JIRA_BASE}/AVSV-2461">Init 2 Execution (AVSV-2461)</a> ·
      <a href="{JIRA_BASE}/AVSV-1965">Operating Plan (AVSV-1965)</a>.
      Active items exclude Completed, Duplicate, Done, Resolved, Closed, and Cancelled.
    </p>

    <div class="charts">
      <div class="chart-card">
        <h2>Open vs closed (all sources)</h2>
        <canvas id="pieChart" height="220"></canvas>
      </div>
      <div class="chart-card">
        <h2>Active items by owner and source (click a segment for task breakdown)</h2>
        <canvas id="stackedBar" height="220"></canvas>
      </div>
    </div>

    <h2 class="section">Owner summary</h2>
    <table>
      <thead>
        <tr><th>Owner</th><th>Active items</th><th>By source</th><th>Breakdown</th></tr>
      </thead>
      <tbody>
        {"".join(summary_rows)}
      </tbody>
    </table>

    <h2 class="section">Open items by owner</h2>
    {"".join(owner_sections)}
  </main>
  <script>
    const pieCtx = document.getElementById('pieChart');
    new Chart(pieCtx, {{
      type: 'pie',
      data: {{
        labels: ['Open action items', 'Closed action items'],
        datasets: [{{
          data: [{open_count}, {closed_count}],
          backgroundColor: ['#4da3ff', '#5c6778'],
        }}],
      }},
      options: {{
        plugins: {{ legend: {{ position: 'bottom' }} }},
      }},
    }});

    const barLabels = {json.dumps(bar_labels)};
    const barDatasets = {json.dumps(bar_datasets)};
    const stackedCtx = document.getElementById('stackedBar');
    const stackedChart = new Chart(stackedCtx, {{
      type: 'bar',
      data: {{
        labels: barLabels,
        datasets: barDatasets.map((ds) => ({{
          label: ds.label,
          data: ds.data,
          backgroundColor: ds.backgroundColor,
          anchorLinks: ds.anchorLinks,
        }})),
      }},
      options: {{
        responsive: true,
        scales: {{
          x: {{ stacked: true }},
          y: {{ stacked: true, beginAtZero: true, ticks: {{ precision: 0 }} }},
        }},
        plugins: {{
          legend: {{ position: 'bottom' }},
          tooltip: {{
            callbacks: {{
              afterLabel: (ctx) => {{
                const link = ctx.dataset.anchorLinks[ctx.dataIndex];
                return link ? 'Click segment to jump to breakdown' : '';
              }},
            }},
          }},
        }},
        onClick: (evt, elements) => {{
          if (!elements.length) return;
          const el = elements[0];
          const link = stackedChart.data.datasets[el.datasetIndex].anchorLinks[el.index];
          if (link) window.location.hash = link.slice(1);
        }},
      }},
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path, required=True)
    parser.add_argument("--jira-init2", type=Path, required=True)
    parser.add_argument("--jira-opex", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("docs/index.html"))
    parser.add_argument("--tracking", type=Path, default=Path("docs/tracking-data.json"))
    args = parser.parse_args()

    import os

    cursor_url = os.environ.get("CURSOR_AUTOMATION_URL", CURSOR_REFRESH_DEFAULT)
    now = datetime.now(timezone.utc)

    sheet_open, sheet_closed = parse_sheet(args.xlsx)
    jira_open, jira_closed = parse_jira_files(args.jira_init2, args.jira_opex)

    open_expanded = expand_by_owner(sheet_open + jira_open)
    closed_expanded = expand_by_owner(sheet_closed + jira_closed)

    html_out = build_dashboard(open_expanded, closed_expanded, cursor_url, now)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_out, encoding="utf-8")

    tracking: dict[str, Any] = {
        "updated": now.isoformat(),
        "open_count": len(open_expanded),
        "closed_count": len(closed_expanded),
        "owners_with_open_items": sorted({i["owner"] for i in open_expanded}),
    }
    args.tracking.write_text(json.dumps(tracking, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} ({tracking['open_count']} open, {tracking['closed_count']} closed)")


if __name__ == "__main__":
    main()
