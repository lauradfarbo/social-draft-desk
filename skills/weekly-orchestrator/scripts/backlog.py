#!/usr/bin/env python3
"""Backlog moves, Calendar sort and hidden Cancelled rows (weekly orchestrator).

A person sets Status Backlog on any Calendar row that is not Posted. The run moves the row, whole, to the
Backlog tab. To bring a post back, the person sets its Status on the Backlog tab to Planned (optionally
with a date in its Notes, for example "use on 2/12/26" or "02 DEC 26"; numeric dates follow
dates.typed_order). The run moves it back to the Calendar as Planned, on that date or in the best free
slot, and the drafter redrafts it there. Rows are moved, never deleted: the copy is written and read
back before the source row is removed.

Usage:
  python3 backlog.py plan calendar.json backlog_tab.json [--config workspace.json] [--as-of YYYY-MM-DD]
      calendar.json: Calendar A1:V; backlog_tab.json: Backlog A1:X. Both saved exactly as returned.
      Prints {"out": [...], "in": [...], "brief_lines": [...], "backlog_count": N}:
        out  Calendar rows with Status Backlog: "values" are the 24 Backlog tab cells (A:V as on the Calendar,
             Status Backlog, Action needed and Draft empty, W Moved to Backlog = run date, X Was dated, both
             YYYY-MM-DD). Write them below the last Backlog row, read back, then run deletes.
        in   Backlog rows with Status Planned: "date" (the requested date, else the best free slot) and
             "values", the 22 Calendar cells (Date YYYY-MM-DD, Status Planned, null in the formula columns,
             Week = ISO week of the new date, one Notes line). Write them below the last Calendar row (never
             append_values), read back, then run deletes.
  python3 backlog.py deletes plan.json cal_status.json cal_ids.json bl_status.json bl_ids.json --cal-sheet <id> --bl-sheet <id>
      Fresh reads, just before deleting, of the Status (B) and Row ID (M) columns of the Calendar and the
      Backlog tab. Prints {"requests": [...deleteDimension, bottom-up...], "refused": [...]}. A row is deleted
      only when its Row ID is found once, its Status is still Backlog (Calendar) or Planned (Backlog tab), and
      its copy has been read back on the other tab. Send requests in one update_spreadsheet call. Exit 1 when
      anything is refused.
  python3 backlog.py sort calendar.json --sheet <id>
      Prints {"requests": [sortRange]} that sorts the Calendar rows by Date, then AM/PM, then Row ID (so
      <id>-FB sits under <id>). Row 1 (headers) is never sorted, and the formula columns' row 2 formulas
      stay in row 2. Hidden rows do not move with their data, so always run hide straight after a sort.
  python3 backlog.py hide calendar.json --sheet <id> [--hidden 13,19] [--config workspace.json]
      --hidden: Calendar row numbers hidden now (Sheets get_spreadsheet rowMetadata hiddenByUser).
      Prints {"requests": [...], "hidden_count": N, "shown_count": N}: every Cancelled row is hidden and every
      hidden row that is no longer Cancelled is shown again. Hiding changes no cell value. Cancelled rows are
      never named in agent output, so only counts are printed.

Best free slot (in): the first date from run date + 7 days, up to 13 weeks ahead, on a weekday the content
type already uses on the Calendar (most used first), else the plan's rotation and proof slot weekdays, else
Thursday, Tuesday, Monday; and holding no other active post on the same channel. Short weeks (the year-end
weeks, plus Thanksgiving week when company.holiday_market is US) allow Monday and Tuesday only. A requested
date before the run date is ignored and the slot rule applies.

Config (all optional): calendar.statuses, calendar.team_owned_regex, calendar.formula_columns,
calendar.tabs, notes.agent_prefix (Agents), dates.typed_order, company.holiday_market,
plan.rotation_slot.weekday, plan.proof_slot.weekday.
"""
import json
import os
import re
import sys
from collections import Counter
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from request_scan import (agent_re, cfg_get, fmt, load, load_config, parse_cell_date, person_date,  # noqa: E402
                          positional, statuses)

WD = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
EXTRA = ["Moved to Backlog", "Was dated"]


def arg(argv, k, default=None):
    return argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else default


def short_week(d, cfg):
    """Year-end weeks, plus Thanksgiving week for a US market: Monday and Tuesday only."""
    y = d.year
    marks = [date(y, 12, 25), date(y, 1, 1), date(y + 1, 1, 1)]
    if (cfg_get(cfg, "company.holiday_market", "") or "").upper() == "US":
        nov1 = date(y, 11, 1)
        marks.append(nov1 + timedelta(days=(3 - nov1.weekday()) % 7 + 21))
    return any(m.isocalendar()[:2] == d.isocalendar()[:2] for m in marks)


def weekday_of(s):
    return WD.get((s or "").strip()[:3].lower())


def cal_rows(values):
    hdr = values[0]
    out = []
    for n, r in enumerate(values[1:], start=2):
        r = list(r) + [""] * (len(hdr) - len(r))
        out.append((n, dict(zip(hdr, r))))
    return hdr, out


def family(ct):
    return re.sub(r"\s+", " ", re.sub(r"\d+", "", ct or "")).strip().lower()


def slot_days(ct, crows, cfg, order):
    use = Counter(parse_cell_date(r.get("Date"), order).weekday() for _, r in crows
                  if family(r.get("Content type")) == family(ct) and parse_cell_date(r.get("Date"), order))
    days = [d for d, _ in use.most_common()]
    for k in ("plan.rotation_slot.weekday", "plan.proof_slot.weekday"):
        w = weekday_of(cfg_get(cfg, k, ""))
        if w is not None and w not in days:
            days.append(w)
    for w in (3, 1, 0):
        if w not in days:
            days.append(w)
    return days


def best_slot(days, busy, as_of, cfg):
    start = as_of + timedelta(days=7)
    for wk in range(14):
        monday = start - timedelta(days=start.weekday()) + timedelta(weeks=wk)
        for wd in days:
            d = monday + timedelta(days=wd)
            if d < start or (short_week(d, cfg) and wd > 1) or d in busy:
                continue
            return d, f"best free slot ({d.strftime('%A')})"
    return start, "no free slot in 13 weeks; to be moved by hand"


def plan(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    order = cfg_get(cfg, "dates.typed_order", "day_first")
    prefix = (cfg_get(cfg, "notes.agent_prefix", "Agents") or "Agents").strip()
    team = re.compile(cfg_get(cfg, "calendar.team_owned_regex", r"Publish|Newsletter|Distribute"))
    formula = cfg_get(cfg, "calendar.formula_columns", ["Action needed", "Draft"]) or []
    pos = positional(argv)
    cal, bl = load(pos[0]), load(pos[1])
    as_of = date.fromisoformat(arg(argv, "--as-of")) if "--as-of" in argv else date.today()
    hdr, crows = cal_rows(cal)
    bhdr = bl[0] if bl else hdr + EXTRA
    _, brows = cal_rows([bhdr] + bl[1:]) if bl else (bhdr, [])
    busy = {}
    for _, r in crows:
        d = parse_cell_date(r.get("Date"), order)
        if d and r.get("Status") not in (st["Cancelled"], st["Backlog"]) and not team.search(r.get("Content type", "") or ""):
            busy.setdefault((r.get("Channel") or "").strip().lower(), set()).add(d)
    out, inn, lines = [], [], []
    for n, r in crows:
        if r.get("Status") != st["Backlog"]:
            continue
        vals = [r.get(h, "") for h in hdr]
        for c in formula:
            if c in hdr:
                vals[hdr.index(c)] = ""
        was = parse_cell_date(r.get("Date"), order)
        vals += [as_of.isoformat(), was.isoformat() if was else r.get("Date", "")]
        out.append({"calendar_row": n, "row_id": r.get("Row ID", ""), "values": vals})
        lines.append(f"{r.get('Row ID')}: moved to the Backlog tab (was {fmt(was) if was else r.get('Date', '')}).")
    agent = agent_re(cfg)
    for n, r in brows:
        if r.get("Status") != st["Planned"]:
            continue
        ct = r.get("Content type", "")
        notes = r.get("Notes", "") or ""
        person = agent.split(notes)[0] if agent.search(notes) else notes  # agent lines carry run dates, skip them
        want = person_date(person, as_of, order)
        ch_busy = busy.setdefault((r.get("Channel") or "").strip().lower(), set())
        if want and want >= as_of:
            d, why = want, "the date asked on the Backlog tab"
        else:
            d, why = best_slot(slot_days(ct, crows, cfg, order), ch_busy, as_of, cfg)
        ch_busy.add(d)
        vals = [r.get(h, "") for h in hdr]
        vals[hdr.index("Date")] = d.isoformat()
        vals[hdr.index("Status")] = st["Planned"]
        for c in formula:
            if c in hdr:
                vals[hdr.index(c)] = None
        if "Week" in hdr:
            vals[hdr.index("Week")] = str(d.isocalendar()[1])
        line = f"{prefix} {fmt(as_of)}: Back from the Backlog on {d.strftime('%a')} {fmt(d)} ({why}), as asked on the Backlog tab."
        vals[hdr.index("Notes")] = (notes.strip() + " " + line).strip()
        inn.append({"backlog_row": n, "row_id": r.get("Row ID", ""), "date": fmt(d), "reason": why,
                    "redraft": bool((r.get("Draft URL") or "").strip()), "values": vals})
        lines.append(f"{r.get('Row ID')}: back from the Backlog on {fmt(d)} ({why}).")
    left = sum(1 for _, r in brows if r.get("Status") not in (st["Planned"],) and (r.get("Row ID") or "").strip()) + len(out)
    print(json.dumps({"as_of": fmt(as_of), "backlog_header": hdr + EXTRA, "out": out, "in": inn,
                      "backlog_count": left, "brief_lines": lines}, indent=1, ensure_ascii=False))
    return 0


def col(p):
    return [(r[0] if r else "") for r in load(p)]


def deletes(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    pos = positional(argv)
    p = json.load(open(pos[0], encoding="utf-8"))
    cb, cm, bb, bm = (col(a) for a in pos[1:5])
    cal_sheet = int(arg(argv, "--cal-sheet"))
    bl_sheet = int(arg(argv, "--bl-sheet"))
    reqs, refused = [], []

    def find(ids, rid):
        hits = [i for i, v in enumerate(ids) if v == rid]
        return hits[0] if len(hits) == 1 else None

    cal_del, bl_del = [], []
    for o in p.get("out", []):
        i = find(cm, o["row_id"])
        if i is None or (cb[i] if i < len(cb) else "") != st["Backlog"]:
            refused.append({"row_id": o["row_id"], "tab": "Calendar", "reason": "Row ID not found once, or Status is no longer Backlog."})
        elif find(bm, o["row_id"]) is None:
            refused.append({"row_id": o["row_id"], "tab": "Calendar", "reason": "Copy not found on the Backlog tab; not deleted."})
        else:
            cal_del.append(i)
    for o in p.get("in", []):
        i = find(bm, o["row_id"])
        if i is None or (bb[i] if i < len(bb) else "") != st["Planned"]:
            refused.append({"row_id": o["row_id"], "tab": "Backlog", "reason": "Row ID not found once, or Status is no longer Planned."})
        elif find(cm, o["row_id"]) is None:
            refused.append({"row_id": o["row_id"], "tab": "Backlog", "reason": "Copy not found on the Calendar; not deleted."})
        else:
            bl_del.append(i)
    for sheet, idx in ((cal_sheet, cal_del), (bl_sheet, bl_del)):
        for i in sorted(idx, reverse=True):  # bottom-up, so earlier rows never shift
            reqs.append({"deleteDimension": {"range": {"sheetId": sheet, "dimension": "ROWS", "startIndex": i, "endIndex": i + 1}}})
    print(json.dumps({"requests": reqs, "refused": refused}, indent=1))
    return 1 if refused else 0


def hide(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    hdr, crows = cal_rows(load(positional(argv)[0]))
    sheet = int(arg(argv, "--sheet"))
    hidden = set()
    if "--hidden" in argv:
        hidden = {int(x) for x in (arg(argv, "--hidden", "") or "").split(",") if x.strip()}
    reqs, h, s = [], 0, 0
    for n, r in crows:
        canc = r.get("Status") == st["Cancelled"]
        if canc and n not in hidden:
            want, h = True, h + 1
        elif not canc and n in hidden:
            want, s = False, s + 1
        else:
            continue
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sheet, "dimension": "ROWS", "startIndex": n - 1, "endIndex": n},
                                                   "properties": {"hiddenByUser": want}, "fields": "hiddenByUser"}})
    print(json.dumps({"requests": reqs, "hidden_count": h, "shown_count": s}, indent=1))
    return 0


def sort(argv):
    hdr, crows = cal_rows(load(positional(argv)[0]))
    sheet = int(arg(argv, "--sheet"))
    last = max((n for n, r in crows if (r.get("Date") or "").strip()), default=1)
    ci = {h: i for i, h in enumerate(hdr)}
    specs = [{"dimensionIndex": ci["Date"], "sortOrder": "ASCENDING"}]
    if "AM/PM" in ci:
        specs.append({"dimensionIndex": ci["AM/PM"], "sortOrder": "ASCENDING"})
    specs.append({"dimensionIndex": ci["Row ID"], "sortOrder": "ASCENDING"})
    req = {"sortRange": {"range": {"sheetId": sheet, "startRowIndex": 1, "endRowIndex": last, "startColumnIndex": 0,
                                   "endColumnIndex": len(hdr)}, "sortSpecs": specs}}
    print(json.dumps({"requests": [req]}, indent=1))
    return 0


if __name__ == "__main__":
    need = {"plan": 2, "deletes": 5, "hide": 1, "sort": 1}
    if len(sys.argv) < 3 or sys.argv[1] not in need or len(positional(sys.argv[2:])) < need[sys.argv[1]] \
            or (sys.argv[1] in ("hide", "sort") and "--sheet" not in sys.argv) \
            or (sys.argv[1] == "deletes" and ("--cal-sheet" not in sys.argv or "--bl-sheet" not in sys.argv)):
        sys.stderr.write(__doc__.strip() + "\n")
        sys.exit(2)
    sys.exit({"plan": plan, "deletes": deletes, "hide": hide, "sort": sort}[sys.argv[1]](sys.argv[2:]) or 0)
