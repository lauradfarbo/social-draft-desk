#!/usr/bin/env python3
"""Column lock for calendar writes (weekly orchestrator). The orchestrator is the only writer to
the calendar, and every write goes through this script first.

Usage:
  python3 calendar_writes.py plan before.json writes.json [--log agent_log.json] [--config workspace.json]
  python3 calendar_writes.py guard before.json writes.json fresh_b.json fresh_jm.json [--log agent_log.json] [--config workspace.json]
  python3 calendar_writes.py verify before.json after.json writes.json [--guard guard.json] [--config workspace.json]
  python3 calendar_writes.py weeksync before.json [--config workspace.json]
  python3 calendar_writes.py shadow before.json writes.json [--config workspace.json]
  python3 calendar_writes.py verify before.json after.json --shadow [--config workspace.json]

--log: the Agent log tab (Date moved, Row ID, Agent, Text, Reason moved), saved as returned. A Notes
  line already moved to the log is not appended again. Pass the same --log to plan and guard.
weeksync: prints Week writes for every row whose Week is not the ISO week of its Date (a person moved
  the Date by hand). Cancelled and Backlog rows are skipped. The Row ID never changes.

before.json / after.json: the calendar table, {"values": [[headers], [row 2], ...]}, header row first.
writes.json: [{"row": 25, "col": "Notes", "value": "...", "by": "planner"}, ...]
  A Status write also carries "check": "pass" (the checker verdict) and needs a Draft URL write for the row.
  col is the header name. Notes and Sources are append-only: give only the new sentence(s);
  the script joins them to the existing text with a space (Sources with "; ").

Config (workspace.json, all optional, generic defaults):
  sources.calendar.tab           tab name used in ranges (default calendar.tabs.calendar, then "Calendar")
  calendar.statuses              [Proposed, Planned, Draft ready, Fallback post, Approved, Posted, Cancelled,
                                 Backlog] labels, in that order (a list of six is also read)
  calendar.proof_types           {"Partner": "Partner Win", "Customer": "Customer Proof", "Advisor": "..."}
  calendar.proof_placeholders    {"Partner Win": "Partner news (to confirm)", ...}
  calendar.formula_columns       columns that recalculate on their own (default ["Action needed", "Draft"])
  calendar.request_columns       columns a person's ask may change (default Date, What to post, Pillar,
                                 Channel, Title / angle, Content type, Spec)
  notes.agent_prefix             agent line prefix (default "Agents"), notes.agent_lines_kept (default 1)

Allowed writes:
  Status          only to Draft ready, only from Planned
  Visual, What's missing, Draft URL       set
  Notes, Sources                           append only (or a tidy, below)
  Original draft  only if empty, or replaced by a v2 redraft: "v2": true with a Draft URL write for the
                  same row in the batch that points to a different tab
  Final text      only if empty and Status is Posted
  Proof item      proof slots and Advisor rows (calendar.proof_types)
  Title / angle   only while it holds a proof placeholder (or on a request)
  Week            only the ISO week of the row's Date. When a request moves a Date into another week,
                  plan adds the Week write itself. The Row ID never changes.
Requests: a write that carries "request": "<where the person asked, for example 'W11-02 Notes' or
  'Ideas row 4'>" may set any request column on a Planned or Proposed row. Date is written as
  YYYY-MM-DD so it stays a real date; a request column is never cleared. A series shift
  (series_shift.py) carries "series": true as well and may also change Date, Title / angle and Spec
  on a Draft ready row.
Tidy: {"row", "col": "Notes" or "Sources", "value": <whole new cell>, "tidy": true} replaces the cell
  (built by notes_tidy.py). Notes must keep every part a person wrote, word for word and in order,
  plus at most notes.agent_lines_kept agent lines; the moved agent lines go to the Agent log first.
  Sources may only lose duplicates. guard refuses a tidy when the cell changed during the run.
Fallback rows: {"insert_after": "W12-01", "values": {"Row ID": "W12-01-FB", "Status": "Fallback post",
  "Date": "YYYY-MM-DD", ...}} adds a full row directly under the original row. Row ID must be
  <original>-FB and Status Fallback post; the original must exist, must not be Cancelled or Backlog
  and must not already have a -FB row. Week is set from the Date; formula columns are null. plan
  prints "inserts", bottom-up, each with "after_row", "values" (one per column, null for formula
  columns), "insert_request" (Sheets insertDimension; add the sheetId) and "range". Write every cell
  write first, then the inserts in the order given, so earlier row numbers never shift. The approver
  uses a fallback by setting it to Approved and the original to Cancelled.
Everything else is refused: What to post, Pillar, Channel, Content type, Spec and Date without a
request, Action needed, Draft, Row ID, AM/PM, Published link, and any row that does not exist.
Rows with Status Cancelled or Backlog (set by a person) are never written.

guard: rows can move while a run is in progress (a person deletes, inserts or sorts rows).
  plan prints "guard_ranges", for example ["Calendar!B13:B20", "Calendar!J13:M20"] (Status, and
  Notes, What's missing, Sources and Row ID of the target rows). Read each range just before
  writing, save each exactly as returned ({"range": ..., "values": ...}) and run guard with them.
  For each accepted write it confirms the Row ID still matches the snapshot and that Status has
  not changed (a person may have set Cancelled); if not, the write is refused. Notes and Sources
  are re-appended to the current cell value, so a person's edit made during the run is kept. A
  What's missing cell a person changed during the run is refused.
  For each insert it confirms the original row still sits at after_row and is not Cancelled.
  guard prints {"accepted", "inserts", "refused", "changed_by_person", "plan_refused"} and exits 1 only
  when "refused" is not empty. Write only guard's accepted values, save its output as guard.json and
  pass it to verify with --guard. With --guard, verify matches rows by Row ID and lists
  deleted_row_ids, added_row_ids and a count of moved_rows instead of every shifted cell. Fallback
  rows from guard's inserts are checked too (fallback_rows_added, fallback_row_problems: missing,
  a value that differs, or not directly under the original row).

plan prints {"accepted": [...], "inserts": [...], "refused": [...], "guard_ranges": [...]}; exit 1 if any refused.
verify prints every cell that changed between before and after and is not an accepted write; exit 1 if any.
shadow runs the same lock check and prints {"would_write", "would_refuse", "brief_lines"}: one plain
  line per cell for the shadow brief. Nothing is written in shadow mode.
verify --shadow works on any table saved the same way (calendar, proof log): every changed cell is
  reported, because a shadow run writes nothing.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from datetime import datetime

CANON = ["Proposed", "Planned", "Draft ready", "Fallback post", "Approved", "Posted", "Cancelled", "Backlog"]
LEGACY = ["Proposed", "Planned", "Draft ready", "Approved", "Posted", "Cancelled"]
SET = {"Visual", "What's missing", "Draft URL"}
APPEND = {"Notes": " ", "Sources": "; "}
REQUEST_COLS = ["Date", "What to post", "Pillar", "Channel", "Title / angle", "Content type", "Spec"]
SERIES_COLS = {"Date", "Title / angle", "Spec"}
AGENTS = ["Agents", "Orchestrator", "Planner", "Proof intake", "Calendar builder", "Drafter", "Checker"]
VALUE_FLAGS = {"--config", "--guard", "--log"}
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def load_config(argv):
    p = argv[argv.index("--config") + 1] if "--config" in argv and argv.index("--config") + 1 < len(argv) else None
    if not p:
        for c in (os.path.join(HERE, "workspace.json"), "workspace.json"):
            if os.path.exists(c):
                p = c
                break
    if not p:
        return {}
    return json.load(open(p, encoding="utf-8"))


def cfg_get(cfg, path, default):
    cur = cfg
    for k in path.split("."):
        if not isinstance(cur, dict) or cur.get(k) is None:
            return default
        cur = cur[k]
    return cur


def statuses(cfg):
    s = cfg_get(cfg, "calendar.statuses", None)
    if isinstance(s, dict):
        return {k: s.get(k, k) for k in CANON}
    if isinstance(s, list) and set(CANON) <= set(s):
        return {k: k for k in CANON}
    if isinstance(s, list) and len(s) == len(CANON):
        return dict(zip(CANON, s))
    if isinstance(s, list) and len(s) == len(LEGACY):
        return {**{k: k for k in CANON}, **dict(zip(LEGACY, s))}
    return {k: k for k in CANON}


class Ctx:
    def __init__(self, cfg):
        self.st = statuses(cfg)
        self.off_plan = (self.st["Cancelled"], self.st["Backlog"])
        self.proof_types = list(cfg_get(cfg, "calendar.proof_types", {"Partner": "Partner Win", "Customer": "Customer Proof"}).values())
        self.placeholders = tuple(cfg_get(cfg, "calendar.proof_placeholders", {}).values())
        self.tab = cfg_get(cfg, "sources.calendar.tab", cfg_get(cfg, "calendar.tabs.calendar", "Calendar"))
        self.formula = set(cfg_get(cfg, "calendar.formula_columns", ["Action needed", "Draft"]))
        self.request_cols = set(cfg_get(cfg, "calendar.request_columns", REQUEST_COLS))
        self.typed_order = cfg_get(cfg, "dates.typed_order", "day_first")
        prefix = cfg_get(cfg, "notes.agent_prefix", "Agents")
        names = [prefix] + [a for a in AGENTS if a != prefix]
        self.agent = re.compile(r"(?:" + "|".join(re.escape(a) for a in names) + r") \d\d [A-Z]{3} \d\d(?: \([^)]*\))?:")
        self.person = re.compile(r"[A-Z][a-z]+(?: [A-Z][a-z]+)?, \d{1,2} [A-Za-z]{3} \d\d:")
        self.lines_kept = int(cfg_get(cfg, "notes.agent_lines_kept", 1))
        self.logged = {}  # Row ID -> texts already moved to the Agent log (--log)

    def load_log(self, path):
        vals = load(path)
        if not vals:
            return
        hdr = [h.strip().lower() for h in vals[0]]
        i_id = hdr.index("row id") if "row id" in hdr else 1
        i_tx = hdr.index("text") if "text" in hdr else 3
        for r in vals[1:]:
            r = list(r) + [""] * len(hdr)
            if r[i_tx].strip():
                self.logged.setdefault(r[i_id].strip(), set()).add(r[i_tx].strip())

    def split_notes(self, notes):
        """[(is_agent, text)] segments in order. A segment starts at an agent or a person prefix."""
        starts = {m.start(): False for m in self.person.finditer(notes)}
        starts.update({m.start(): True for m in self.agent.finditer(notes)})
        marks = sorted(starts.items())
        segs = []
        first = marks[0][0] if marks else len(notes)
        if notes[:first].strip():
            segs.append((False, notes[:first].strip()))
        for i, (start, agent) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(notes)
            if notes[start:end].strip():
                segs.append((agent, notes[start:end].strip()))
        return segs

    def parse_date(self, s):
        s = (s or "").strip()
        num = ("%m/%d/%y", "%m/%d/%Y") if self.typed_order == "month_first" else ("%d/%m/%y", "%d/%m/%Y", "%d.%m.%y", "%d.%m.%Y")
        for f in ("%Y-%m-%d", "%a %d %b %y", "%d %b %y", "%d %b %Y") + num:
            try:
                return datetime.strptime(s.title() if "%b" in f else s, f).date()
            except ValueError:
                pass
        return None

    def same(self, col, want, got):
        """Dates are written YYYY-MM-DD and read back as displayed (Tue 17 MAR 26)."""
        if (want or "") == (got or ""):
            return True
        if col == "Date" and want and ISO.fullmatch(str(want)):
            d = self.parse_date(got)
            return bool(d and d.isoformat() == want)
        return False


def tidy_problem(cx, col, cur, val):
    """A tidy replaces Notes or Sources. Notes keep every part a person wrote, in order, and may add
    only agent text; Sources may only lose duplicate entries."""
    if col == "Sources":
        old = [p.strip().lower() for p in cur.split(";") if p.strip()]
        new = [p.strip().lower() for p in val.split(";") if p.strip()]
        if set(old) != set(new) or len(new) != len(set(new)):
            return "A Sources tidy may only remove duplicate entries."
        return None
    pos, rest = 0, val
    for agent, text in cx.split_notes(cur):
        if agent:
            continue
        i = val.find(text, pos)
        if i < 0:
            return "Tidy would drop or change text a person wrote in Notes. Not written."
        pos = i + len(text)
        rest = rest.replace(text, "", 1)
    rest = rest.strip()
    if rest and (not cx.agent.match(rest) or len(cx.agent.findall(rest)) > cx.lines_kept):
        return f"A tidy may add only {cx.lines_kept} agent line(s), each starting '<agent> DD MMM YY:'."
    return None


def load(p):
    v = json.load(open(p, encoding="utf-8"))
    return v.get("values", v) if isinstance(v, dict) else v


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def grid(values):
    hdr = values[0]
    return hdr, [list(r) + [""] * (len(hdr) - len(r)) for r in values]


def plan(before, writes, cx):
    """Column lock. Returns (accepted cell writes, refused, inserts)."""
    hdr, g = grid(before)
    acc, ref = [], []
    merged = {}
    rid_i = hdr.index("Row ID") if "Row ID" in hdr else None
    st = cx.st
    cells = [w for w in writes if "insert_after" not in w]
    inserts = [w for w in writes if "insert_after" in w]

    def batch(row, col):
        return [x for x in cells if int(x.get("row", 0) or 0) == row and x.get("col") == col]

    for w in cells:
        row, col, val = int(w["row"]), w["col"], w.get("value", "")
        why = None
        if col not in hdr:
            why = f"Unknown column '{col}'."
        elif row < 2 or row > len(g):
            why = f"Row {row} does not exist; the orchestrator never adds rows (fallback rows use insert_after)."
        if why:
            ref.append({**w, "reason": why})
            continue
        ci = hdr.index(col)
        cur = merged.get((row, col), g[row - 1][ci])
        r = dict(zip(hdr, g[row - 1]))
        ct = r.get("Content type", "")
        rid = g[row - 1][rid_i] if rid_i is not None else ""
        if r.get("Status") in cx.off_plan:
            ref.append({**w, "reason": f"Status is {r.get('Status')} (set by a person); agents never write to the row."})
            continue
        req = str(w.get("request") or "").strip()
        if col == "Week":
            dw = next((x.get("value") for x in batch(row, "Date") if x.get("request")), None)
            d = cx.parse_date(dw or (r.get("Date") if "Date" in hdr else ""))
            if not d or str(val).strip() != str(d.isocalendar()[1]):
                why = "Week must be the ISO week of the row's Date (plan sets it when a Date moves)."
        elif req and col in cx.request_cols:
            series_ok = w.get("series") and r.get("Status") == st["Draft ready"] and col in SERIES_COLS
            if r.get("Status") not in (st["Planned"], st["Proposed"]) and not series_ok:
                why = (f"Request edits apply only to {st['Planned']} or {st['Proposed']} rows (Status is '{r.get('Status')}')."
                       if not w.get("series") else f"A series shift changes only {', '.join(sorted(SERIES_COLS))} on a {st['Draft ready']} row.")
            elif col == "Date" and not ISO.fullmatch(str(val or "")):
                why = "Date is written as YYYY-MM-DD so it stays a real date."
            elif not str(val).strip():
                why = f"{col} cannot be cleared."
        elif col == "Status":
            if val != st["Draft ready"]:
                why = f"Agents set Status only to {st['Draft ready']} (asked: '{val}'); fallback rows are added with insert_after."
            elif r.get("Status") != st["Planned"]:
                why = f"Status is '{r.get('Status')}', not {st['Planned']}."
            elif w.get("check") != "pass":
                why = "Draft ready needs the compliance checker's pass on this write (\"check\": \"pass\")."
            elif not batch(row, "Draft URL"):
                why = "Draft ready needs a Draft URL write for the same row in this batch."
        elif col in SET:
            pass
        elif col in APPEND and w.get("tidy"):
            why = tidy_problem(cx, col, cur, val)
        elif col in APPEND:
            if val.strip() and val.strip() in cur:
                continue  # already there: skip silently, no duplicate notes
            if col == "Notes" and val.strip() in cx.logged.get(rid, set()):
                continue  # this line was tidied into the Agent log already; do not bring it back
            val = (cur + APPEND[col] + val).strip("; ").strip() if cur.strip() else val
        elif col == "Original draft":
            new_url = next((x.get("value", "") for x in batch(row, "Draft URL")), "")
            cur_url = r.get("Draft URL", "")
            if cur.strip() and not (w.get("v2") and new_url and new_url != cur_url):
                why = ("Original draft is written once; it is replaced only by a v2 redraft "
                       "(\"v2\": true with a Draft URL write to the new tab).")
        elif col == "Final text":
            if r.get("Status") != st["Posted"]:
                why = "Final text is copied only when Status is Posted."
            elif cur.strip():
                why = "Final text is already filled."
        elif col == "Proof item":
            if not any(p and p in ct for p in cx.proof_types):
                why = "Proof item is only for proof slots and Advisor rows."
        elif col == "Title / angle":
            if cur not in cx.placeholders:
                why = "Title / angle changes only while it holds the proof placeholder, or on a person's request."
        elif col in cx.request_cols:
            why = f"{col} changes only on a person's request: add \"request\" naming where they asked."
        else:
            why = f"Column '{col}' is locked for agents."
        if why:
            ref.append({**w, "reason": why})
            continue
        merged[(row, col)] = str(val).strip() if col == "Week" else val
    if "Week" in hdr:  # a moved Date carries its ISO week
        for (row, col), val in list(merged.items()):
            d = cx.parse_date(val) if col == "Date" else None
            if d and (row, "Week") not in merged and g[row - 1][hdr.index("Week")].strip() != str(d.isocalendar()[1]):
                merged[(row, "Week")] = str(d.isocalendar()[1])
    for (row, col), val in merged.items():
        acc.append({"range": f"{cx.tab}!{col_letter(hdr.index(col))}{row}", "row": row, "col": col, "value": val,
                    "row_id": g[row - 1][rid_i] if rid_i is not None else ""})
    ins, iref = plan_inserts(hdr, g, inserts, cx)
    return acc, ref + iref, ins


def plan_inserts(hdr, g, inserts, cx):
    """Fallback rows directly under their original row. Returns (inserts bottom-up, refused)."""
    if "Row ID" not in hdr or "Status" not in hdr:
        return [], [{**w, "reason": "The table has no Row ID or Status column."} for w in inserts]
    rid_i, st_i = hdr.index("Row ID"), hdr.index("Status")
    ids = {r[rid_i]: n + 1 for n, r in enumerate(g) if n and r[rid_i]}
    out, ref = [], []
    for w in inserts:
        after, vals = w.get("insert_after", ""), dict(w.get("values", {}))
        new_id = vals.get("Row ID", "")
        why = None
        if after not in ids:
            why = f"Original row {after} not found."
        elif new_id != f"{after}-FB":
            why = f"Fallback Row ID must be {after}-FB."
        elif new_id in ids or any(x["row_id"] == new_id for x in out):
            why = f"{new_id} already exists; a row has one fallback row at a time."
        elif vals.get("Status") != cx.st["Fallback post"]:
            why = f"A fallback row is added with Status {cx.st['Fallback post']}."
        elif g[ids[after] - 1][st_i] in cx.off_plan:
            why = f"Original row is {g[ids[after] - 1][st_i]}; no fallback."
        elif [k for k in vals if k not in hdr]:
            why = f"Unknown columns: {[k for k in vals if k not in hdr]}."
        elif not ISO.fullmatch(str(vals.get("Date") or "")):
            why = "Date is written as YYYY-MM-DD."
        if why:
            ref.append({**w, "reason": why})
            continue
        if "Week" in hdr:
            vals["Week"] = str(cx.parse_date(vals["Date"]).isocalendar()[1])
        row = [None if h in cx.formula else vals.get(h, "") for h in hdr]
        n = ids[after]
        out.append({"after_row": n, "after_row_id": after, "row_id": new_id, "values": row,
                    "insert_request": {"insertDimension": {"range": {"dimension": "ROWS", "startIndex": n, "endIndex": n + 1},
                                                           "inheritFromBefore": True}},
                    "range": f"{cx.tab}!A{n + 1}:{col_letter(len(hdr) - 1)}{n + 1}"})
    out.sort(key=lambda x: -x["after_row"])
    return out, ref


def guard_ranges(acc, hdr, cx, ins=()):
    """Ranges to read fresh just before writing: Status and Notes to Row ID of the target rows."""
    rows = [a["row"] for a in acc] + [i["after_row"] for i in ins]
    if not rows:
        return []
    lo, hi = min(rows), max(rows)
    b = col_letter(hdr.index("Status"))
    return [f"{cx.tab}!{b}{lo}:{b}{hi}",
            f"{cx.tab}!{col_letter(hdr.index('Notes'))}{lo}:{col_letter(hdr.index('Row ID'))}{hi}"]


def parse_a1(rng):
    m = re.search(r"!\$?([A-Z]+)\$?(\d+)", rng or "")
    if not m:
        return None, None
    c = 0
    for ch in m.group(1):
        c = c * 26 + ord(ch) - 64
    return c - 1, int(m.group(2))


def guard(before, writes, fresh_list, cx):
    """Re-check every accepted write against fresh reads of guard_ranges."""
    hdr, g = grid(before)
    acc, ref, ins = plan(before, writes, cx)
    fresh, covered = {}, set()
    for raw in fresh_list:
        rng = raw.get("range", "") if isinstance(raw, dict) else ""
        vals = raw.get("values", []) if isinstance(raw, dict) else raw
        c0, r0 = parse_a1(rng)
        if c0 is None:
            raise SystemExit("guard: a fresh read has no range (save each read exactly as returned).")
        m = re.search(r":\$?([A-Z]+)\$?(\d+)", rng)
        c1 = parse_a1("!" + m.group(1) + m.group(2))[0] if m else c0
        r1 = int(m.group(2)) if m else r0 + len(vals) - 1
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                covered.add((r, c))
                row = vals[r - r0] if r - r0 < len(vals) else []
                fresh[(r, c)] = row[c - c0] if c - c0 < len(row) else ""
    rid_i, st_i = hdr.index("Row ID"), hdr.index("Status")
    ok, bad, changed = [], [], []
    seen = set()
    for a in acc:
        row, col = a["row"], a["col"]
        ci = hdr.index(col)
        if (row, rid_i) not in covered:
            bad.append({**a, "reason": "Row not in the fresh read; read guard_ranges again."})
            continue
        now_id = fresh.get((row, rid_i), "")
        if now_id != a["row_id"]:
            bad.append({**a, "reason": f"Row ID changed: expected {a['row_id']}, found '{now_id}' (row deleted, inserted or sorted during the run). Not written."})
            continue
        if (row, st_i) not in covered:
            bad.append({**a, "reason": "Status not in the fresh reads; read every guard_ranges range and pass each file."})
            continue
        if fresh[(row, st_i)] != g[row - 1][st_i]:
            bad.append({**a, "reason": f"Status changed during the run ('{g[row - 1][st_i]}' to '{fresh[(row, st_i)]}'). Not written."})
            continue
        b = g[row - 1][ci]
        if (row, ci) in covered:
            cur = fresh[(row, ci)]
            if cur != b:
                if (row, col) not in seen:
                    changed.append({"cell": a["range"], "row_id": a["row_id"], "col": col})
                    seen.add((row, col))
                if col in APPEND and any(w.get("tidy") for w in writes if "row" in w and int(w["row"]) == row and w.get("col") == col):
                    bad.append({**a, "reason": f"{col} changed during the run, so the tidy is skipped this time. Not written."})
                    continue
                if col in APPEND:
                    add = [w.get("value", "").strip() for w in writes if "row" in w and int(w["row"]) == row and w["col"] == col]
                    add = [x for x in add if x and x not in cur and x not in cx.logged.get(a["row_id"], set())]
                    val = cur
                    for x in add:
                        val = (val + APPEND[col] + x).strip("; ").strip() if val.strip() else x
                    if val == cur:
                        continue
                    a = {**a, "value": val}
                else:
                    bad.append({**a, "reason": f"{col} was changed by a person during the run. Not written."})
                    continue
        ok.append(a)
    ins_ok = []
    for i in ins:
        n = i["after_row"]
        if (n, rid_i) not in covered or (n, st_i) not in covered:
            bad.append({"insert": i["row_id"], "reason": "Original row not in the fresh reads; read guard_ranges again. Fallback row not added."})
        elif fresh.get((n, rid_i)) != i["after_row_id"]:
            bad.append({"insert": i["row_id"], "reason": f"Row {n} now holds '{fresh.get((n, rid_i))}', not {i['after_row_id']}. Fallback row not added."})
        elif fresh.get((n, st_i)) in cx.off_plan:
            bad.append({"insert": i["row_id"], "reason": "The original row was taken off the plan during the run. Fallback row not added."})
        else:
            ins_ok.append(i)
    return ok, bad, changed, ref, ins_ok


def positional(argv):
    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in VALUE_FLAGS
        else:
            pos.append(a)
    return pos


def main(argv):
    cx = Ctx(load_config(argv))
    pos = positional(argv)
    need = {"plan": 3, "verify": 3 if "--shadow" in argv else 4, "shadow": 3, "guard": 4, "weeksync": 2}
    if not pos or pos[0] not in need or len(pos) < need[pos[0]]:
        sys.stderr.write(__doc__.strip() + "\n")
        return 2
    if "--log" in argv and argv.index("--log") + 1 < len(argv):
        cx.load_log(argv[argv.index("--log") + 1])
    mode = pos[0]
    if mode == "weeksync":
        hdr, g = grid(load(pos[1]))
        out = []
        if "Week" in hdr and "Date" in hdr and "Status" in hdr:
            for n, r in enumerate(g[1:], start=2):
                d = cx.parse_date(r[hdr.index("Date")])
                if d and r[hdr.index("Status")] not in cx.off_plan and r[hdr.index("Week")].strip() != str(d.isocalendar()[1]):
                    out.append({"row": n, "col": "Week", "value": str(d.isocalendar()[1]), "by": "week sync",
                                "row_id": r[hdr.index("Row ID")] if "Row ID" in hdr else ""})
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if mode == "plan":
        before = load(pos[1])
        acc, ref, ins = plan(before, json.load(open(pos[2], encoding="utf-8")), cx)
        print(json.dumps({"accepted": acc, "inserts": ins, "refused": ref,
                          "guard_ranges": guard_ranges(acc, grid(before)[0], cx, ins)}, indent=2, ensure_ascii=False))
        return 1 if ref else 0
    if mode == "guard":
        fresh = [json.load(open(p, encoding="utf-8")) for p in pos[3:]]
        ok, bad, changed, pref, ins = guard(load(pos[1]), json.load(open(pos[2], encoding="utf-8")), fresh, cx)
        print(json.dumps({"accepted": ok, "inserts": ins, "refused": bad, "changed_by_person": changed, "plan_refused": pref},
                         indent=2, ensure_ascii=False))
        return 1 if bad else 0
    if mode == "shadow":
        before = load(pos[1])
        writes = json.load(open(pos[2], encoding="utf-8"))
        acc, ref, ins = plan(before, writes, cx)
        hdr, g = grid(before)
        rid = hdr.index("Row ID") if "Row ID" in hdr else None
        lines, raw = [], {}
        for w in writes:
            if w.get("col") in APPEND and not w.get("tidy"):
                raw.setdefault((int(w["row"]), w["col"]), []).append(w.get("value", "").strip())
        for a in acc:
            who = g[a["row"] - 1][rid] if rid is not None else f"row {a['row']}"
            if a["col"] in APPEND and (a["row"], a["col"]) in raw:
                label, val = f"{a['col']} (add)", " ".join(raw[(a["row"], a["col"])])
            else:
                label, val = a["col"], a["value"]
            val = str(val).replace("\n", " ")
            lines.append(f"{who} {label}: {val[:160] + ('...' if len(val) > 160 else '')}")
        for i in ins:
            lines.append(f"{i['row_id']}: fallback row would be added under {i['after_row_id']}")
        for r in ref:
            if "row" not in r:
                orig = next((x for x in g[1:] if rid is not None and x[rid] == r.get("insert_after")), None)
                if orig is not None and orig[hdr.index("Status")] in cx.off_plan:
                    continue  # never mention a Cancelled or Backlog row
                lines.append(f"{r.get('insert_after', '')} fallback row: would be refused ({r['reason']})")
                continue
            ok_row = rid is not None and 2 <= int(r["row"]) <= len(g)
            if ok_row and g[int(r["row"]) - 1][hdr.index("Status")] in cx.off_plan:
                continue  # Cancelled and Backlog rows are never mentioned in agent output
            who = g[int(r["row"]) - 1][rid] if ok_row else f"row {r['row']}"
            lines.append(f"{who} {r['col']}: would be refused ({r['reason']})")
        print(json.dumps({"mode": "shadow", "would_write": acc, "would_insert": ins, "would_refuse": ref, "brief_lines": lines},
                         indent=2, ensure_ascii=False))
        return 0
    # verify
    before, after = load(pos[1]), load(pos[2])
    acc, _, exp_ins = plan(before, [] if "--shadow" in argv else json.load(open(pos[3], encoding="utf-8")), cx)
    gd = {}
    if "--guard" in argv:
        gd = json.load(open(argv[argv.index("--guard") + 1], encoding="utf-8"))
        acc = gd.get("accepted", [])
        exp_ins = gd.get("inserts", [])
    ok = {(a["row"], a["col"]): a["value"] for a in acc}
    hdr, gb = grid(before)
    person, person_rows = set(), set()
    if gd:
        person = {c["cell"].split("!")[-1] for c in gd.get("changed_by_person", [])}
        person_rows = {int(r["row"]) for r in gd.get("refused", []) if "row" in r and "changed during the run" in r.get("reason", "")}
    by_person = []
    _, ga = grid(after)
    bad, mismatched = [], []
    moved = {}
    if (gd or exp_ins) and "Row ID" in hdr:
        # Match rows by Row ID, so a row deleted or inserted by a person is reported once,
        # not as hundreds of changed cells. Cell names use the before-row number.
        rid = hdr.index("Row ID")
        aft = {}
        for r in ga[1:]:
            r = list(r) + [""] * (len(hdr) - len(r))
            if r[rid]:
                aft[r[rid]] = r
        bef_ids = [r[rid] for r in gb[1:] if r[rid]]
        exp = {i["row_id"]: i for i in exp_ins}
        moved = {"deleted_row_ids": [x for x in bef_ids if x not in aft],
                 "added_row_ids": [x for x in aft if x not in set(bef_ids) and x not in exp]}
        ins_bad = []
        for x, i in exp.items():
            if x not in aft:
                ins_bad.append({"row_id": x, "problem": "fallback row not found"})
                continue
            for ci, h in enumerate(hdr):
                want = i["values"][ci] if ci < len(i["values"]) else None
                if want is None or h in cx.formula:
                    continue
                if not cx.same(h, want, aft[x][ci]):
                    ins_bad.append({"row_id": x, "col": h, "want": str(want)[:60], "found": str(aft[x][ci])[:60]})
            p_after = [n for n, r in enumerate(ga) if len(r) > rid and r[rid] == i["after_row_id"]]
            p_new = [n for n, r in enumerate(ga) if len(r) > rid and r[rid] == x]
            if p_after and p_new and p_new[0] != p_after[0] + 1:
                ins_bad.append({"row_id": x, "problem": "fallback row is not directly under its original row"})
        moved["fallback_rows_added"] = sorted(exp)
        moved["fallback_row_problems"] = ins_bad
        pairs = []
        for i in range(1, len(gb)):
            if gb[i][rid] in aft:
                pairs.append((i, gb[i], aft[gb[i][rid]]))
            elif not gb[i][rid] and i < len(ga) and not (list(ga[i]) + [""] * len(hdr))[rid]:
                pairs.append((i, gb[i], ga[i]))  # rows without a Row ID: compare by position
        new_pos = {r[rid]: n for n, r in enumerate(ga) if len(r) > rid and r[rid]}
        old_pos = {r[rid]: n for n, r in enumerate(gb) if r[rid]}
        moved["moved_rows"] = sum(1 for x in bef_ids if x in new_pos and new_pos[x] - old_pos[x]
                                  != sum(1 for i in exp.values() if i["after_row"] < old_pos[x] + 1))
        ga_by_before = {i: ra for i, _, ra in pairs}
        ga = [ga[0]] + [ga_by_before.get(i, [""] * len(hdr)) for i in range(1, len(gb))]
    for i in range(1, max(len(gb), len(ga))):
        rb = gb[i] if i < len(gb) else [""] * len(hdr)
        ra = ga[i] if i < len(ga) else [""] * len(hdr)
        ra = list(ra) + [""] * (len(hdr) - len(ra))
        if moved and not any(ra) and rb[hdr.index("Row ID")] in moved.get("deleted_row_ids", []):
            continue
        for ci, h in enumerate(hdr):
            if h in cx.formula:
                continue
            if (rb[ci] or "") != (ra[ci] or ""):
                cell = f"{col_letter(ci)}{i + 1}"
                if (i + 1, h) in ok:
                    if not cx.same(h, ok[(i + 1, h)], ra[ci]):
                        mismatched.append({"cell": cell, "col": h})
                elif cell in person or (i + 1) in person_rows:
                    by_person.append({"cell": cell, "col": h})
                else:
                    bad.append({"cell": cell, "col": h, "before": rb[ci][:60], "after": ra[ci][:60]})
    missing = []
    if len(ga) >= max([a["row"] for a in acc] + [0]):
        missing = [{"cell": a["range"]} for a in acc
                   if not cx.same(a["col"], a["value"], (list(ga[a["row"] - 1]) + [""] * len(hdr))[hdr.index(a["col"])])]
    out = {"unexpected_changes": bad, "value_mismatch": mismatched, "not_written": missing}
    if gd or exp_ins:
        if gd:
            out["changed_by_person_during_run"] = by_person
        out.update(moved)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 1 if (bad or mismatched or missing or moved.get("deleted_row_ids") or moved.get("added_row_ids")
                 or moved.get("fallback_row_problems")) else 0


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv or len(positional(sys.argv)) < 1:
        sys.stderr.write((__doc__ or "").strip() + "\n")
        sys.exit(2)
    sys.exit(main(sys.argv))
