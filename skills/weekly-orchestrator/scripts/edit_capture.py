#!/usr/bin/env python3
"""Capture the approver's edits to drafts so the drafters learn from them (weekly orchestrator).

Usage:
  python3 edit_capture.py calendar.json tab_texts.json approver_edits.json [--config workspace.json]
                          [--as-of YYYY-MM-DD] [--prompts prompts.json]

calendar.json:        the Calendar table {"values": [[headers], ...]} saved exactly as returned.
tab_texts.json:       {"<Row ID>": "<text above the dashed line now in the draft tab>"} for every row with
                      Status Draft ready, Fallback post, Approved or Posted and a Draft URL (extract_final.py
                      per tab). Rows in docs nobody changed since the last brief are left out.
approver_edits.json:  the Approver edits tab A1:I as returned (header row first; may hold only the header).
prompts.json:         optional {"<Row ID>": {"now": "<image prompt line>", "original": "<image prompt as drafted>"}}
                      from extract_final.py. An edited prompt is logged as its own row with Content type
                      "Image prompt: <content type>".

Each run compares the tab text with Original draft. When they differ, the edit is logged once per
version: an edit already logged with the same text is skipped, a later change logs a new row.

Prints {"rows": [[...]], "range": "<Approver edits tab>!A<n>:I<m>", "brief_lines": [...]}. Writes nothing.
Columns: Date captured, Row ID, Content type, Status, Size of edit (Light edit or Rewrite, with the share
of the original's words kept), Original draft, Approver's text, What changed (filled by the main session
in one or two plain sentences, from the difference), Draft URL.

Config (all optional): edit_learning.enabled (true; false prints nothing to log), company.approver.name,
calendar.statuses, calendar.tabs.approver_edits (Approver edits).
"""
import difflib
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from request_scan import cfg_get, fmt, load, load_config, statuses  # noqa: E402

REWRITE_BELOW = 0.5  # share of the original's words kept


def a1_tab(name):
    return name if re.fullmatch(r"[A-Za-z0-9_]+", name) else "'" + name.replace("'", "''") + "'"


def table(values):
    hdr = values[0]
    return hdr, [dict(zip(hdr, list(r) + [""] * (len(hdr) - len(r)))) for r in values[1:]]


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def main(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    who = (cfg_get(cfg, "company.approver.name", "") or "the approver").strip()
    tab = a1_tab(cfg_get(cfg, "calendar.tabs.approver_edits", "Approver edits"))
    pos = [a for i, a in enumerate(argv[1:], start=1)
           if not a.startswith("--") and argv[i - 1] not in ("--config", "--as-of", "--prompts")]
    if cfg_get(cfg, "edit_learning.enabled", True) is False:
        print(json.dumps({"rows": [], "range": "", "brief_lines": [], "enabled": False}, indent=2))
        return 0
    _, cal = table(load(pos[0]))
    tabs = json.load(open(pos[1], encoding="utf-8"))
    ehdr_vals = load(pos[2])
    hdr, logged = table(ehdr_vals) if ehdr_vals else ([], [])
    text_col = next((h for h in hdr if h.endswith("text")), hdr[6] if len(hdr) > 6 else "Approver's text")
    as_of = date.fromisoformat(argv[argv.index("--as-of") + 1]) if "--as-of" in argv else date.today()
    seen = {(r.get("Row ID"), norm(r.get(text_col))) for r in logged}
    want = (st["Draft ready"], st["Fallback post"], st["Approved"], st["Posted"])
    rows, brief = [], []
    for r in cal:
        rid, s = r.get("Row ID", ""), r.get("Status", "")
        if s not in want or rid not in tabs:
            continue
        orig, now = r.get("Original draft", "") or "", tabs[rid] or ""
        if not orig.strip() or not now.strip() or norm(orig) == norm(now) or (rid, norm(now)) in seen:
            continue
        a, b = norm(orig).split(), norm(now).split()
        kept = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()) / max(len(a), 1)
        size = "Rewrite" if kept < REWRITE_BELOW else "Light edit"
        rows.append([fmt(as_of), rid, r.get("Content type", ""), s, f"{size} ({round(kept * 100)}% of the draft's words kept)",
                     orig, now, "", r.get("Draft URL", "")])
        brief.append(f"{rid} ({r.get('Content type', '')}): {who}'s {size.lower()} captured for the drafters.")
    if "--prompts" in argv:
        pr = json.load(open(argv[argv.index("--prompts") + 1], encoding="utf-8"))
        byid = {r.get("Row ID", ""): r for r in cal}
        for rid, p in pr.items():
            now, orig = (p.get("now") or "").strip(), (p.get("original") or "").strip()
            if not now or not orig or norm(now) == norm(orig) or (rid, norm(now)) in seen:
                continue
            r = byid.get(rid, {})
            rows.append([fmt(as_of), rid, "Image prompt: " + r.get("Content type", ""), r.get("Status", ""), "Prompt edit",
                         orig, now, "", r.get("Draft URL", "")])
            brief.append(f"{rid}: {who}'s image prompt edit captured for the drafters.")
    first = len(ehdr_vals) + 1 if ehdr_vals else 2
    print(json.dumps({"rows": rows, "range": f"{tab}!A{first}:I{first + len(rows) - 1}" if rows else "",
                      "brief_lines": brief}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    vals = [a for i, a in enumerate(sys.argv[1:], start=1)
            if not a.startswith("--") and sys.argv[i - 1] not in ("--config", "--as-of", "--prompts")]
    if len(vals) < 3 or "-h" in sys.argv:
        sys.stderr.write(__doc__.strip() + "\n")
        sys.exit(2)
    sys.exit(main(sys.argv))
