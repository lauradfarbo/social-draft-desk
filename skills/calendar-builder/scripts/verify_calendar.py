#!/usr/bin/env python3
"""First-run check: compare the calendar export with the plan's schedule text, row by row.

Usage:
  python3 verify_calendar.py <plan_layout.txt> <calendar.json | calendar.xlsx> [--config workspace.json] [--expect N]

plan_layout.txt: the plan saved with `pdftotext -layout plan.pdf plan_layout.txt`.
calendar.json:   the Calendar tab as {"values": [[headers], [row2], ...]} (Sheets get_values shape).
calendar.xlsx:   or the calendar file exported as .xlsx (read with the standard library, Calendar tab).
--expect N:      the number of dated line items the plan says it has. A different count is a mismatch.

Each schedule line in the plan text starts with the week number, a weekday and a day and month, and
an optional (AM) or (PM), for example "  3   Tue 17 Mar (AM)   Blog 2 - Publish   Website  ...".
Wrapped text on the following lines is joined to the field above it. By default the third field is
the content type and the last field is the title. A plan with another layout sets plan.pdf in
workspace.json (every key optional):
  {"row_regex": "...", "stop_regex": "...", "content_type_field": 2, "title_field": -1}
row_regex must have groups for week (1), weekday (2), day and month (3) and AM or PM (5).
stop_regex matches lines that end a row's wrapped text (a repeated table header, a totals line).

The plan numbers its weeks 1, 2, 3 and so on; the calendar holds the calendar (ISO) week of each Date in
Week and in the Row ID (W{iso week:02d}-{seq:02d}). Plan week 1 starts on plan.week1_monday, or on the
Monday of the first row's week when that key is missing. For each row the script checks that the plan
week maps to the ISO week of the calendar Date, that Week equals that ISO week, and that the Row ID
starts with W{iso week:02d}-. Backup rows (Row ID ending -FB, Status Fallback post) are not in the plan
and are left out of the comparison.

Checks week, weekday, date, AM/PM, content type and title for every row, in order. Prints one line per
mismatch and the count. Exit 0 if there are none, 1 if there are mismatches, 2 on a usage or input
error. Writes nothing and fixes nothing.
"""
import json
import re
import sys
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree as ET

DEFAULT_ROW = r"^\s*(\d{1,2})\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (\d{1,2} [A-Za-z]{3})( \((AM|PM)\))?\s"
DEFAULT_STOP = r"^\s*(Wk|Week)\s+Date\b"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def arg(argv, name):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def positional(argv):
    out, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
            continue
        if a in ("--config", "--expect"):
            skip = True
            continue
        out.append(a)
    return out


def load_config(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_plan(text, cfg):
    pdf = ((cfg.get("plan") or {}).get("pdf") or {})
    row_re = re.compile(pdf.get("row_regex") or DEFAULT_ROW)
    stop_re = re.compile(pdf.get("stop_regex") or DEFAULT_STOP)
    ct_i = int(pdf.get("content_type_field", 2))
    ti_i = int(pdf.get("title_field", -1))
    field_re = re.compile(r"\S+(?: \S+)*")
    lines = text.split("\n")
    rows, i = [], 0
    while i < len(lines):
        m = row_re.match(lines[i])
        if not m:
            i += 1
            continue
        fields = [(f.start(), f.group()) for f in field_re.finditer(lines[i])]
        starts = [s for s, _ in fields]
        texts = [[t] for _, t in fields]
        j = i + 1
        while j < len(lines) and lines[j].strip() and not row_re.match(lines[j]) and not stop_re.match(lines[j]):
            for f in field_re.finditer(lines[j]):
                cands = [n for n, s in enumerate(starts) if s <= f.start() + 3]
                texts[max(cands) if cands else 0].append(f.group())
            j += 1
        full = [" ".join(t) for t in texts]

        def pick(k):
            try:
                return full[k]
            except IndexError:
                return ""
        rows.append({"week": int(m.group(1)), "dow": m.group(2), "date": m.group(3),
                     "ampm": m.group(5) or "", "ctype": pick(ct_i), "title": pick(ti_i), "line": i + 1})
        i = j
    return rows


def col_index(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path, tab="Calendar"):
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rid = None
        for s in wb.find("m:sheets", NS):
            if s.get("name") == tab:
                rid = s.get(REL)
        if rid is None:
            raise ValueError(f"No '{tab}' tab in {path}")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        target = target.lstrip("/")
        target = target if target.startswith("xl/") else "xl/" + target
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        sheet = ET.fromstring(z.read(target))
    rows = []
    for r in sheet.iter(f"{{{NS['m']}}}row"):
        idx = int(r.get("r")) - 1
        while len(rows) <= idx:
            rows.append([])
        out = rows[idx]
        for c in r.findall("m:c", NS):
            ci = col_index(c.get("r"))
            t = c.get("t")
            if t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
            else:
                v = c.find("m:v", NS)
                val = "" if v is None else (v.text or "")
                if t == "s" and val != "":
                    val = shared[int(val)]
            while len(out) <= ci:
                out.append("")
            out[ci] = val
    return rows


def read_calendar(path):
    if path.lower().endswith(".xlsx"):
        return read_xlsx(path)
    with open(path, encoding="utf-8") as f:
        v = json.load(f)
    return v.get("values", []) if isinstance(v, dict) else v


def to_date(v):
    s = str(v).strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return date(1899, 12, 30) + timedelta(days=int(float(s)))
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(?:[A-Za-z]{3},?\s+)?(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{2}|\d{4})", s)
    if m:
        y = int(m.group(3))
        y = y + 2000 if y < 100 else y
        return date(y, MONTHS.index(m.group(2).title()) + 1, int(m.group(1)))
    return datetime.fromisoformat(s).date()


def cell(row, i):
    return str(row[i]).strip() if i is not None and i < len(row) and row[i] is not None else ""


def main(argv):
    pos = positional(argv)
    if len(pos) < 2 or "-h" in argv or "--help" in argv:
        sys.stderr.write((__doc__ or "").strip() + "\n")
        return 2
    try:
        cfg = load_config(arg(argv, "--config"))
        with open(pos[0], encoding="utf-8") as f:
            plan = parse_plan(f.read(), cfg)
        values = read_calendar(pos[1])
    except (OSError, ValueError, KeyError, StopIteration, zipfile.BadZipFile) as e:
        sys.stderr.write(f"Cannot read input: {e}\n")
        return 2
    if not values:
        sys.stderr.write("The calendar export is empty.\n")
        return 2
    hdr = [str(h).strip() for h in values[0]]
    need = ["Date", "Week", "AM/PM", "Content type", "Title / angle", "Row ID"]
    missing = [h for h in need if h not in hdr]
    if missing:
        sys.stderr.write(f"Calendar header is missing: {', '.join(missing)}\n")
        return 2
    col = {h: n for n, h in enumerate(hdr)}
    status_i = col.get("Status")
    sheet = [r for r in values[1:] if cell(r, col["Date"]) and not cell(r, col["Row ID"]).upper().endswith("-FB")
             and cell(r, status_i) != "Fallback post"]
    w1 = (cfg.get("plan") or {}).get("week1_monday")
    try:
        week1 = date.fromisoformat(w1) if w1 else None
    except ValueError:
        sys.stderr.write(f"plan.week1_monday '{w1}' is not a YYYY-MM-DD date.\n")
        return 2

    print(f"Plan rows parsed: {len(plan)}; calendar rows: {len(sheet)}")
    issues = 0
    expect = arg(argv, "--expect")
    if expect is not None and int(expect) != len(plan):
        issues += 1
        print(f"MISMATCH count: plan states {expect} rows, parsed {len(plan)}")
    if len(plan) != len(sheet):
        issues += 1
        print(f"MISMATCH count: plan {len(plan)} rows, calendar {len(sheet)} rows")
    for n, (p, s) in enumerate(zip(plan, sheet), 1):
        try:
            d = to_date(cell(s, col["Date"]))
        except ValueError:
            d = None
        wk = cell(s, col["Week"])
        try:
            wk = int(float(wk))
        except ValueError:
            pass
        iso = d.isocalendar()[1] if d else None
        if week1 is None and d is not None:
            week1 = d - timedelta(days=d.weekday()) - timedelta(weeks=p["week"] - 1)
        plan_iso = (week1 + timedelta(weeks=p["week"] - 1)).isocalendar()[1] if week1 else p["week"]
        checks = {
            "week (plan order)": (plan_iso, iso),
            "Week column": (iso, wk),
            "Row ID week": (f"W{iso:02d}-" if iso else "", cell(s, col["Row ID"])[:4]),
            "weekday": (p["dow"], DAYS[d.weekday()] if d else cell(s, col["Date"])),
            "date": (p["date"], f"{d.day} {MONTHS[d.month - 1]}" if d else cell(s, col["Date"])),
            "AM/PM": (p["ampm"], cell(s, col["AM/PM"])),
            "content type": (p["ctype"], cell(s, col["Content type"])),
            "title": (p["title"], cell(s, col["Title / angle"])),
        }
        for k, (a, b) in checks.items():
            if str(a).strip() != str(b).strip():
                issues += 1
                print(f"MISMATCH row {n} ({cell(s, col['Row ID']) or 'no Row ID'}) {k}: plan={a!r} calendar={b!r}")
    print(f"Mismatches: {issues}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
