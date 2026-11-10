#!/usr/bin/env python3
"""Keep a series in order when a person moves or cancels one of its posts (weekly orchestrator).

A series is a set of rows whose Notes or Title / angle say "N of M" (for example "customer story 2 of 4",
"post 1 of 3") and share a content type family (digits ignored, so "Blog 3 - Publish" and "Blog 4 -
Publish" are one family).

Rules:
- Moved: a person moved post k to a later date. Every later post that now falls on or before the post in
  front of it moves to the next date on the series' usual weekday after that post. In short weeks (the
  year-end weeks, plus Thanksgiving week when company.holiday_market is US) only Monday and Tuesday are
  used.
- Cancelled: a person set post k to Cancelled since the last run. The series is pushed back one slot:
  post k's content (What to post, Title / angle, Spec, What's missing) moves to the row of post k+1, and
  so on; the last post's content goes to a new Proposed row on the next matching date after the last
  row. The Cancelled row itself is never written and never named in any output line. To drop a post
  without shifting, the person writes the drop word (requests.series_drop_word, default "drop") in its
  Notes before setting it to Cancelled.
- Backlog: no shift (the post is kept on the Backlog tab); one brief line notes the gap.
Clashes (another active post on the same channel and date) are listed for the Notes line, never avoided
silently.

Usage:
  python3 series_shift.py calendar.json snapshot.json [--config workspace.json] [--as-of YYYY-MM-DD]
      calendar.json: Calendar A1:V; snapshot.json: Agent snapshot (snapshot.py). Saved as returned.
      Prints {"writes": [...], "new_rows": [...], "notes": {Row ID: sentence}, "notes_meta": {...},
              "brief_lines": [...], "_internal": {...}}:
        writes: calendar_writes.py items with "request": "series shift" and "series": true (allowed on
          Planned, Proposed and Draft ready rows). Rows whose content changed and have a draft get
          "redraft": true in notes_meta, so the run redrafts them into a v2 tab.
        new_rows: Calendar values each (Date YYYY-MM-DD, Status Proposed, null in the formula columns, the
          next free Row ID for that ISO week); write them below the last row like the calendar builder does.
        _internal: counts for run checks only; never quote them.

Config (all optional): requests.series_drop_word (drop), calendar.statuses, calendar.team_owned_regex,
calendar.formula_columns, company.approver.name, company.holiday_market, notes.agent_prefix,
dates.typed_order.
"""
import json
import os
import re
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backlog import family, short_week  # noqa: E402
from request_scan import cfg_get, fmt, load, load_config, parse_cell_date, split_notes, statuses  # noqa: E402

NOFM = re.compile(r"\b(\d{1,2})\s+of\s+(\d{1,2})\b", re.I)
CONTENT = ("What to post", "Title / angle", "Spec", "What's missing")


def table(v):
    if not v:
        return [], []
    h = v[0]
    out = []
    for n, r in enumerate(v[1:], start=2):
        r = list(r) + [""] * (len(h) - len(r))
        d = dict(zip(h, r))
        d["_row"] = n
        out.append(d)
    return h, out


def next_slot(after, weekday, cfg):
    """First date after `after` on `weekday`; in short weeks the Monday or Tuesday of that week instead."""
    d = after + timedelta(days=1)
    for _ in range(120):
        if short_week(d, cfg):
            if weekday <= 1 and d.weekday() == weekday:
                return d
            if weekday > 1 and d.weekday() in (0, 1):
                return d
        elif d.weekday() == weekday:
            return d
        d += timedelta(days=1)
    return after + timedelta(days=7)


def nofm(r):
    txt = (r.get("Title / angle") or "") + " " + (r.get("Notes") or "")
    m = NOFM.search(txt)
    return (int(m.group(1)), int(m.group(2))) if m else None


def next_row_id(cal, d):
    wk = d.isocalendar()[1]
    seqs = [int(m.group(1)) for r in cal for m in [re.fullmatch(r"W%02d-(\d{2})" % wk, (r.get("Row ID") or "").strip())] if m]
    return "W%02d-%02d" % (wk, max(seqs, default=0) + 1)


def main(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    order = cfg_get(cfg, "dates.typed_order", "day_first")
    drop = (cfg_get(cfg, "requests.series_drop_word", "drop") or "drop").strip()
    team = re.compile(cfg_get(cfg, "calendar.team_owned_regex", r"Publish|Newsletter|Distribute"))
    formula = cfg_get(cfg, "calendar.formula_columns", ["Action needed", "Draft"]) or []
    who = (cfg_get(cfg, "company.approver.name", "") or "The approver").strip()
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in ("--config", "--as-of"))]
    hdr, cal = table(load(pos[0]))
    _, snap = table(load(pos[1]))
    snap = {s["Key"]: s for s in snap if s.get("Kind") == "row"}
    out = {"writes": [], "new_rows": [], "notes": {}, "notes_meta": {}, "brief_lines": [],
           "_internal": {"dropped": 0, "pushed_back": 0, "moved": 0}}
    if not snap or not hdr:
        print(json.dumps(out, indent=1))
        return 0
    gone = (st["Cancelled"], st["Backlog"], st["Posted"])
    pd = lambda r: parse_cell_date(r.get("Date"), order)  # noqa: E731
    series = {}
    for r in cal:
        nm = nofm(r)
        if nm and r.get("Row ID"):
            series.setdefault((family(r.get("Content type")), nm[1]), []).append((nm[0], r))
    active = [r for r in cal if r.get("Status") not in (st["Cancelled"], st["Backlog"]) and pd(r)]

    eff = {}  # Row ID -> date after this run's moves

    def clashes(d, rid, channel):
        return [x["Row ID"] for x in active if eff.get(x.get("Row ID"), pd(x)) == d and x.get("Row ID") != rid
                and (x.get("Channel") or "") == (channel or "") and not team.search(x.get("Content type", "") or "")]

    for (fam, m), members in series.items():
        members.sort(key=lambda t: t[0])
        wds = [pd(t[1]).weekday() for t in members if pd(t[1]) and not short_week(pd(t[1]), cfg)]
        home = max(set(wds), key=wds.count) if wds else None  # the series' usual weekday
        for i, (n, r) in enumerate(members):
            s = snap.get(r["Row ID"])
            if not s:
                continue
            was, now = parse_cell_date(s.get("Date"), order), pd(r)
            if r.get("Status") == st["Cancelled"] and s.get("Status") != st["Cancelled"]:
                person = " ".join(t for a, t in split_notes(r.get("Notes") or "", cfg) if not a)
                if re.search(r"\b" + re.escape(drop) + r"\b", person, re.I):
                    out["_internal"]["dropped"] += 1  # the series keeps its dates; nothing to say
                    continue
                later = [t for t in members[i + 1:] if t[1].get("Status") not in gone]
                content = {c: r.get(c, "") for c in CONTENT if c in hdr}
                for n2, r2 in later:
                    nxt = {c: r2.get(c, "") for c in content}
                    for c, v in content.items():
                        if v != r2.get(c, ""):
                            out["writes"].append({"row": r2["_row"], "col": c, "value": v, "request": "series shift",
                                                  "series": True, "by": "series"})
                    out["notes"][r2["Row ID"]] = ("Series moved back one slot: this row now carries the post "
                                                  "that was planned on the row before it.")
                    out["notes_meta"][r2["Row ID"]] = {"redraft": bool((r2.get("Draft URL") or "").strip())}
                    content = nxt
                last = later[-1][1] if later else None
                ld = pd(last) if last else None
                if ld:
                    nd = next_slot(ld, home if home is not None else ld.weekday(), cfg)
                    vals = [last.get(h, "") for h in hdr]
                    vals[hdr.index("Date")] = nd.isoformat()
                    vals[hdr.index("Status")] = st["Proposed"]
                    for c in formula:
                        if c in hdr:
                            vals[hdr.index(c)] = None
                    for c in ("Draft URL", "Original draft", "Final text", "Published link", "Proof item"):
                        if c in hdr:
                            vals[hdr.index(c)] = ""
                    for c, v in content.items():
                        vals[hdr.index(c)] = v
                    rid = next_row_id(cal, nd)
                    if "Row ID" in hdr:
                        vals[hdr.index("Row ID")] = rid
                    if "Week" in hdr:
                        vals[hdr.index("Week")] = str(nd.isocalendar()[1])
                    vals[hdr.index("Notes")] = f"Series moved back one slot; this new row carries the last post of the series ({m} of {m})."
                    cl = clashes(nd, rid, last.get("Channel"))
                    out["new_rows"].append({"after_row_id": last["Row ID"], "row_id": rid, "date": fmt(nd),
                                            "values": vals, "clashes": cl})
                    cal.append({h: v for h, v in zip(hdr, vals)})
                    out["brief_lines"].append(f"Series ({len(members)} posts, from {later[0][1]['Row ID']}): pushed back "
                                              f"one slot ({len(later)} rows changed, new Proposed row {rid} on {fmt(nd)}).")
                out["_internal"]["pushed_back"] += 1
            elif r.get("Status") == st["Backlog"] and s.get("Status") != st["Backlog"]:
                out["brief_lines"].append(f"{r['Row ID']} (post {n} of {m}) went to the Backlog; the series keeps its dates.")
            elif was and now and now > was and r.get("Status") not in gone:
                prev, moves = now, []
                for n2, r2 in members[i + 1:]:
                    if r2.get("Status") in gone:
                        continue
                    d2 = pd(r2)
                    if d2 and d2 <= prev:
                        nd = next_slot(prev, home if home is not None else d2.weekday(), cfg)
                        moves.append((r2, d2, nd))
                        eff[r2["Row ID"]] = nd
                        prev = nd
                    elif d2:
                        prev = d2
                for r2, d2, nd in moves:  # clashes use every row's date after the moves
                    out["writes"].append({"row": r2["_row"], "col": "Date", "value": nd.isoformat(),
                                          "request": "series shift", "series": True, "by": "series"})
                    cl = clashes(nd, r2["Row ID"], r2.get("Channel"))
                    out["notes"][r2["Row ID"]] = (f"Moved from {fmt(d2)} to {fmt(nd)} to keep the series in order after "
                                                  f"{r['Row ID']} moved to {fmt(now)}."
                                                  + (f" {fmt(nd)} also holds {', '.join(cl)}; {who} to decide which runs." if cl else ""))
                if moves:
                    out["_internal"]["moved"] += 1
                    out["brief_lines"].append(f"{r['Row ID']} moved to {fmt(now)}: later posts in the series moved to keep their order.")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    args = [a for i, a in enumerate(sys.argv[1:], start=1)
            if not a.startswith("--") and sys.argv[i - 1] not in ("--config", "--as-of")]
    if len(args) < 2 or "-h" in sys.argv:
        sys.stderr.write(__doc__.strip() + "\n")
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
