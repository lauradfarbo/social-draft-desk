#!/usr/bin/env python3
"""Row guard for writes to the Ideas, Milestones and approver's notes tabs (calendar builder).

Usage:
  python3 tab_guard.py before.json fresh.json writes.json --key "Idea (one line)" [--config workspace.json]
  python3 tab_guard.py before.json fresh.json writes.json --key "Milestone" [--config workspace.json]
  python3 tab_guard.py before.json fresh.json writes.json --key "Date added" [--config workspace.json]

--key "Date added" guards the "From the approver's notes" tab (key Date added, checked cell Fact).

before.json: the tab (Ideas A1:H, Milestones A1:G or the approver's notes tab A1:G) as read at the start
             of the run, saved exactly as returned ({"values": [[headers], [row2], ...]} or a bare list).
fresh.json:  the same range read again just before writing, saved the same way.
writes.json: [{"row": 5, "col": "Status", "value": "Scheduled"}, ...]  (col is the header name)

Someone may delete, insert or sort rows on these tabs while a run is in progress. For each write the
script checks that, on that row, the key cell (the Idea text, or the Milestone name), the status cell
(Ideas Status, Milestones Confirmed, or the approver's Fact) and the target cell are the same in fresh.json as in
before.json. If they are, the write is accepted with its exact range. If not, every write on that row
is skipped (a row is written in full or not at all), with one plain line per row for the weekly brief
(for example a person set Declined or Cancelled during the run). The tab name comes from --key, so a
write can never land on the wrong tab. The builder writes only the accepted ranges.

Optional config: calendar.tabs in workspace.json renames the tabs, for example
  {"ideas": "Ideas", "milestones": "Milestones", "approver_notes": "From the approver's notes"}
A value may also be an object that renames the columns too:
  {"ideas": {"tab": "Ideas", "key": "Idea (one line)", "status": "Status"}}
A missing key uses these defaults. A tab name with a space or quote is quoted in the range
('From the approver''s notes'!F3).

Prints {"accepted": [{"range", "value"}], "skipped": [{"row", "col", "reason"}], "brief_lines": [...]}.
Exit 0 if every write was accepted, 1 if anything was skipped, 2 on a usage or input error.
Writes nothing.
"""
import json
import sys

DEFAULT_TABS = {
    "ideas": {"tab": "Ideas", "key": "Idea (one line)", "status": "Status"},
    "milestones": {"tab": "Milestones", "key": "Milestone", "status": "Confirmed"},
    "approver_notes": {"tab": "From the approver's notes", "key": "Date added", "status": "Fact"},
}


def load(p):
    with open(p, encoding="utf-8") as f:
        v = json.load(f)
    return v.get("values", []) if isinstance(v, dict) else v


def tab_map(config_path):
    tabs = {k: dict(v) for k, v in DEFAULT_TABS.items()}
    if config_path:
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError) as e:
            raise SystemExit(f"Cannot read config {config_path}: {e}")
        custom = ((cfg.get("calendar") or {}).get("tabs") or {})
        for k in tabs:
            if isinstance(custom.get(k), dict):
                tabs[k].update({kk: vv for kk, vv in custom[k].items() if vv})
            elif isinstance(custom.get(k), str) and custom[k].strip():
                tabs[k]["tab"] = custom[k].strip()
    return {v["key"]: (v["tab"], v["status"]) for v in tabs.values()}


def sheet_ref(tab):
    if tab.replace("_", "").isalnum():
        return tab
    return "'" + tab.replace("'", "''") + "'"


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def cell(rows, r, c):
    if 0 <= r - 1 < len(rows):
        row = rows[r - 1]
        return str(row[c]) if c < len(row) and row[c] is not None else ""
    return ""


def arg(argv, name):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def main(argv):
    key = arg(argv, "--key")
    if len(argv) < 6 or key is None:
        sys.stderr.write((__doc__ or "").strip() + "\n")
        return 2
    tabs = tab_map(arg(argv, "--config"))
    if key not in tabs:
        sys.stderr.write(f"--key must be one of {list(tabs)}.\n")
        return 2
    tab, status_col = tabs[key]
    try:
        before, fresh = load(argv[1]), load(argv[2])
        with open(argv[3], encoding="utf-8") as f:
            writes = json.load(f)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"Cannot read input: {e}\n")
        return 2
    if not before:
        sys.stderr.write("before.json has no header row.\n")
        return 2
    hdr = before[0]
    if key not in hdr or (fresh and fresh[0] != hdr):
        sys.stderr.write(f"Key column '{key}' not in the header, or the fresh read has a different header.\n")
        return 2
    ki = hdr.index(key)
    si = hdr.index(status_col) if status_col in hdr else None
    acc, skipped, lines, bad_rows = [], [], [], {}
    for w in writes:  # first pass: find rows that moved or changed during the run
        row, col = int(w["row"]), w["col"]
        if col not in hdr or row < 2:
            continue
        ci = hdr.index(col)
        was, now = cell(before, row, ki), cell(fresh, row, ki)
        reason = None
        if not was or was != now:
            reason = (f"row {row} on {tab} no longer holds '{was[:60]}' (now '{now[:60]}'): "
                      "a row was deleted, inserted or sorted during the run")
        elif si is not None and cell(before, row, si) != cell(fresh, row, si):
            reason = (f"{status_col} on {tab} row {row} ('{was[:60]}') was changed by a person during the run "
                      f"(now '{cell(fresh, row, si)}')")
        elif cell(before, row, ci) != cell(fresh, row, ci):
            reason = f"{col} on {tab} row {row} ('{was[:60]}') was changed by a person during the run"
        if reason and row not in bad_rows:
            bad_rows[row] = reason
            lines.append(f"{tab} write skipped: {reason}. Nothing written to this row; the next run checks it again.")
    for w in writes:  # second pass: a row is written in full or not at all
        row, col = int(w["row"]), w["col"]
        if col not in hdr:
            skipped.append({**w, "reason": f"Unknown column '{col}'."})
            continue
        if row < 2:
            skipped.append({**w, "reason": "Row 1 is the header and is never written."})
            continue
        if row in bad_rows:
            skipped.append({**w, "reason": bad_rows[row] + "."})
            continue
        acc.append({"range": f"{sheet_ref(tab)}!{col_letter(hdr.index(col))}{row}", "value": w.get("value", "")})
    print(json.dumps({"accepted": acc, "skipped": skipped, "brief_lines": lines}, indent=2, ensure_ascii=False))
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
