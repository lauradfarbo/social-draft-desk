#!/usr/bin/env python3
"""Agent snapshot: see what a person changed by hand since the last run (weekly orchestrator).

People may edit the request columns (calendar.request_columns: Date, What to post, Pillar, Channel,
Title / angle, Content type, Spec) straight on the Calendar, and Start date or Confirmed on the
Milestones tab, instead of writing in Notes. The run saves these columns to the hidden Agent snapshot
tab at the end of every run and compares them at the start of the next one. Every difference is a
person's ask. Status is saved too, so series_shift.py can see what was cancelled since.

Usage:
  python3 snapshot.py compare calendar.json milestones.json snapshot.json [--config workspace.json]
      All three saved exactly as returned (Calendar A1:V, Milestones A1:G, Agent snapshot A1:L).
      Prints {"first_run": bool, "row_changes": [...], "milestone_changes": [...], "brief_lines": [...]}.
        row_changes: {"row", "row_id", "status", "drafted", "changed": {col: [before, now]}, "instruction": [cols]}
          for rows that are in the snapshot, are not Posted, Cancelled or Backlog, and differ in a tracked
          column. Text columns are saved as short fingerprints, so "before" reads "(earlier text)".
          "instruction" lists columns whose new value reads like an instruction rather than a value
          ("make this a call-out to installers"): copy it word for word to Notes and act on it as an ask.
        milestone_changes: {"row", "milestone", "changed": {"Start date"|"Confirmed": [before, now]},
          "confirmed_now": bool}. A milestone not in the snapshot is new (the builder's milestone run handles it).
      An empty or missing snapshot means first run: nothing is reported, the run saves one at the end.
  python3 snapshot.py save calendar.json milestones.json [old_snapshot.json] [--config workspace.json] [--as-of YYYY-MM-DD]
      Prints {"range": "<Agent snapshot tab>!A1:<col><n>", "values": [...]}: the whole tab, padded with blank
      rows so rows left from a longer old snapshot are cleared. Write it with one update_values call after
      the verify step, from after.json, so the run's own writes are never reported as a person's.

Snapshot columns: Kind, Key, Date, Status, <request columns other than Date>, Confirmed, Saved.
Config (all optional): calendar.request_columns, calendar.statuses, calendar.tabs.agent_snapshot
(Agent snapshot), dates.typed_order (day_first).
"""
import hashlib
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from request_scan import cfg_get, fmt, load, load_config, parse_cell_date, statuses  # noqa: E402

DEFAULT_COLS = ["Date", "What to post", "Pillar", "Channel", "Title / angle", "Content type", "Spec"]
PLAIN = ("Date", "Status")  # kept as text; the other columns are kept as fingerprints so the tab stays small
INSTRUCTION = re.compile(r"^\s*(please|can we|could we|could you|can you|make (this|it)|change (this|it)|turn (this|it)|"
                         r"move (this|it)|swap|instead of|let's|use this for|do a|write a|draft a)\b|\?\s*$", re.I)


def a1_tab(name):
    return name if re.fullmatch(r"[A-Za-z0-9_]+", name) else "'" + name.replace("'", "''") + "'"


def col_letter(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def tracked(cfg):
    cols = list(cfg_get(cfg, "calendar.request_columns", DEFAULT_COLS) or DEFAULT_COLS)
    if "Date" not in cols:
        cols = ["Date"] + cols
    return ["Date", "Status"] + [c for c in cols if c not in ("Date", "Status")]


def header(cfg):
    return ["Kind", "Key"] + tracked(cfg) + ["Confirmed", "Saved"]


def fp(v):
    v = (v or "").strip()
    return "#" + hashlib.sha1(v.encode("utf-8")).hexdigest()[:10] if v else ""


def table(v):
    if not v:
        return []
    h = v[0]
    out = []
    for n, r in enumerate(v[1:], start=2):
        r = list(r) + [""] * (len(h) - len(r))
        d = dict(zip(h, r))
        d["_row"] = n
        out.append(d)
    return out


def same(col, saved, now, order):
    saved, now = saved or "", now or ""
    if col not in PLAIN and col != "Start date":
        return saved == fp(now) if saved.startswith("#") else saved.strip() == now.strip()
    da, db = parse_cell_date(saved, order), parse_cell_date(now, order)
    if da and db:
        return da == db
    return saved.strip() == now.strip()


def compare(argv, cfg, as_of):
    st = statuses(cfg)
    order = cfg_get(cfg, "dates.typed_order", "day_first")
    cal, mil, snap = table(load(argv[0])), table(load(argv[1])), table(load(argv[2]))
    rows = {s["Key"]: s for s in snap if s.get("Kind") == "row"}
    miles = {s["Key"]: s for s in snap if s.get("Kind") == "milestone"}
    out = {"first_run": not (rows or miles), "row_changes": [], "milestone_changes": [], "brief_lines": []}
    if out["first_run"]:
        print(json.dumps(out, indent=1))
        return 0
    skip = (st["Posted"], st["Cancelled"], st["Backlog"])
    for r in cal:
        rid = (r.get("Row ID") or "").strip()
        if not rid or rid not in rows or r.get("Status") in skip:
            continue
        s = rows[rid]
        ch = {c: [s.get(c, "") if c in PLAIN else "(earlier text)", r.get(c, "")] for c in tracked(cfg)
              if c != "Status" and c in s and not same(c, s.get(c, ""), r.get(c, ""), order)}
        if ch:
            instr = [c for c in ch if c not in PLAIN and INSTRUCTION.search(r.get(c, "") or "")]
            out["row_changes"].append({"row": r["_row"], "row_id": rid, "status": r.get("Status", ""),
                                       "drafted": bool((r.get("Draft URL") or "").strip()), "changed": ch,
                                       "instruction": instr})
            out["brief_lines"].append(f"{rid}: changed by hand ({', '.join(ch)}).")
    for m in mil:
        name = (m.get("Milestone") or "").strip()
        if not name or name not in miles:
            continue
        s = miles[name]
        ch = {}
        if not same("Start date", s.get("Date", ""), m.get("Start date", ""), order):
            ch["Start date"] = [s.get("Date", ""), m.get("Start date", "")]
        if (s.get("Confirmed") or "").strip().lower() != (m.get("Confirmed") or "").strip().lower():
            ch["Confirmed"] = [s.get("Confirmed", ""), m.get("Confirmed", "")]
        if ch:
            out["milestone_changes"].append({"row": m["_row"], "milestone": name, "changed": ch,
                                             "confirmed_now": (m.get("Confirmed") or "").strip().lower() == "yes"})
            out["brief_lines"].append(f"Milestone \"{name}\": changed by hand ({', '.join(ch)}).")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


def save(argv, cfg, as_of):
    cal, mil = table(load(argv[0])), table(load(argv[1]))
    old = load(argv[2]) if len(argv) > 2 else []
    now = fmt(as_of)
    cols = tracked(cfg)
    hdr = header(cfg)
    vals = [hdr]
    for r in cal:
        if (r.get("Row ID") or "").strip():
            vals.append(["row", r["Row ID"].strip()] + [r.get(c, "") if c in PLAIN else fp(r.get(c, "")) for c in cols] + ["", now])
    for m in mil:
        if (m.get("Milestone") or "").strip():
            vals.append(["milestone", m["Milestone"].strip(), m.get("Start date", "")] + [""] * (len(cols) - 1)
                        + [m.get("Confirmed", ""), now])
    while len(vals) < len(old):
        vals.append([""] * len(hdr))
    tab = a1_tab(cfg_get(cfg, "calendar.tabs.agent_snapshot", "Agent snapshot"))
    print(json.dumps({"range": f"{tab}!A1:{col_letter(len(hdr))}{len(vals)}", "values": vals}, ensure_ascii=False))
    return 0


def positional(argv):
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
            continue
        if a in ("--config", "--as-of"):
            skip = True
            continue
        out.append(a)
    return out


if __name__ == "__main__":
    args = positional(sys.argv[1:])
    if len(args) < 3 or args[0] not in ("compare", "save") or (args[0] == "compare" and len(args) < 4):
        sys.stderr.write(__doc__.strip() + "\n")
        sys.exit(2)
    cfg = load_config(sys.argv)
    fn = {"compare": compare, "save": save}[args[0]]
    as_of = date.fromisoformat(sys.argv[sys.argv.index("--as-of") + 1]) if "--as-of" in sys.argv else date.today()
    sys.exit(fn(args[1:], cfg, as_of))
