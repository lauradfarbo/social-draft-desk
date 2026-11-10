#!/usr/bin/env python3
"""Evergreen swaps and fallback drafts for blocked rows (weekly orchestrator).

Usage:
  python3 swap_slots.py calendar.json select.json match.json [--config workspace.json]
                        [--drafter-blocked W12-01,...] [--backlog backlog.json] [--as-of YYYY-MM-DD]
                        [--days 5] [--max-fallbacks 4]

calendar.json: the calendar table (before.json).
select.json:   output of select_rows.py for the same snapshot.
match.json:    output of proof intake's match_proof.py for the same snapshot.
--backlog:     optional, the Backlog tab table. Each swap then lists backlog_options: Backlog rows of
               the swap type (any type when none match), so the brief can offer a Backlog post first.

Config (workspace.json, all optional): swaps.types, swaps.source_label, swaps.chapters,
swaps.excluded_chapters, run.swap_days, run.max_fallbacks, visuals.no_repeat_weeks,
calendar.teaser_regex, calendar.blog_id_regex, calendar.statuses, company.approver.name,
notes.agent_prefix, dates.typed_order.
--days and --max-fallbacks override the config.

A row is a swap candidate when its date is swap_days (default 5) or fewer away and it cannot be
drafted this run. Base drafts with [bracketed] gaps are drafted, so they are not candidates:
  blocked     Planned row the selection marked blocked (not a dependency hold), or a draft row whose
              drafter returned "blocked" this run (--drafter-blocked)
  proof       proof slot that match_proof.py returned as flag with propose_swap true
  dependency  row on a dependency hold ("On hold:" reason) whose Notes already hold a planner
              "Proposed swap" (the planner proposes these after the deadline; this script never does)
Teaser rows waiting on a blog link get a conditional swap ("If the <blog> link is not in Notes ...").

For each candidate the script picks, in one pass so the run never doubles up:
  type     one of swaps.types: the one used least in the row's ISO week and the next (calendar
           rows, swaps already proposed in Notes and swaps chosen this run), ties in config order
  chapter  a long-form chapter (swaps.chapters minus swaps.excluded_chapters) not in Sources or swap
           Notes of rows from no_repeat_weeks (default 8) before the row to 14 days after, and not
           chosen for another swap this run. None when no chapters are configured.
chapter is the first free chapter; chapters_available lists all free ones. The orchestrator may pick
another listed chapter that suits the type better (chapter-map.md), as long as no other swap this run
uses it. If the row's Notes already hold "Proposed swap: <type> on <angle> (<source label> ch<N>)",
that proposal is kept (existing: true).

A fallback is a full row directly under its original (Row ID <original>-FB, Status Fallback post,
calendar_writes.py "insert_after"). Fallback post rows are not slots: they are left out of the
candidates and the type counts. fallback: true when the row has no -FB row and its Notes do not yet
hold "Fallback draft", up to max_fallbacks per run, nearest date first; a row that already has one
gets fallback_row_exists: true. The orchestrator drafts a fallback post for the rest
(make_bundles.py fallback).

stale_notes lists rows whose current agent line in Notes holds a dated condition that no longer
fits: a teaser condition ("by the morning of DD MMM YY") whose date is not the blog row's current
date (kind teaser_condition), or a cut-off ("by DD MMM YY") that has passed (kind cutoff_passed,
new = the later of today and two days before the row's date). The orchestrator rebuilds that line
from today's dates. Nothing is flagged to the approver.

Prints {"swaps": [...], "fallbacks_skipped": [...], "stale_notes": [...]}. Cancelled and Backlog
rows are never candidates and never named. The script writes nothing.
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CANON = ["Proposed", "Planned", "Draft ready", "Fallback post", "Approved", "Posted", "Cancelled", "Backlog"]
LEGACY = ["Proposed", "Planned", "Draft ready", "Approved", "Posted", "Cancelled"]
VALUE_FLAGS = {"--config", "--drafter-blocked", "--as-of", "--days", "--max-fallbacks", "--backlog"}
AGENTS = ["Agents", "Orchestrator", "Planner", "Proof intake", "Calendar builder", "Drafter", "Checker"]
CH = re.compile(r"\bch(?:apter)?\s?(\d+)\b", re.I)


def load_config(argv):
    p = argv[argv.index("--config") + 1] if "--config" in argv and argv.index("--config") + 1 < len(argv) else None
    if not p:
        for c in (os.path.join(HERE, "workspace.json"), "workspace.json"):
            if os.path.exists(c):
                p = c
                break
    return json.load(open(p, encoding="utf-8")) if p else {}


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


def load(p):
    v = json.load(open(p, encoding="utf-8"))
    return v.get("values", v) if isinstance(v, dict) else v


TYPED_ORDER = ["day_first"]


def parse_date(s):
    """A Date cell as displayed (Tue 17 MAR 26), as written (2026-03-17) or as typed (17/03/26 when
    dates.typed_order is day_first, 03/17/26 when it is month_first)."""
    s = (s or "").strip()
    num = ("%d/%m/%y", "%d/%m/%Y", "%d.%m.%y", "%d.%m.%Y")
    if TYPED_ORDER[0] == "month_first":
        num = ("%m/%d/%y", "%m/%d/%Y")
    for f in ("%a %d %b %y", "%d %b %y", "%Y-%m-%d", "%d %b %Y") + num:
        try:
            return datetime.strptime(s.title() if "%b" in f else s, f).date()
        except ValueError:
            pass
    return None


def fmt(d):
    return f"{d.day:02d} {d.strftime('%b').upper()} {d.strftime('%y')}"


def arg(argv, k, default=None):
    return argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else default


def main(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    TYPED_ORDER[0] = cfg_get(cfg, "dates.typed_order", "day_first")
    skip_st = (st["Cancelled"], st["Backlog"])
    prefix = cfg_get(cfg, "notes.agent_prefix", "Agents")
    names = [prefix] + [a for a in AGENTS if a != prefix]
    agent_line = re.compile(r"(?:" + "|".join(re.escape(a) for a in names) + r") \d\d [A-Z]{3} \d\d(?: \([^)]*\))?:")
    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in VALUE_FLAGS
        else:
            pos.append(a)
    values = load(pos[0])
    sel = json.load(open(pos[1], encoding="utf-8"))
    match = json.load(open(pos[2], encoding="utf-8"))
    as_of = date.fromisoformat(arg(argv, "--as-of")) if "--as-of" in argv else date.today()
    days = int(arg(argv, "--days", cfg_get(cfg, "run.swap_days", 5)))
    cap = int(arg(argv, "--max-fallbacks", cfg_get(cfg, "run.max_fallbacks", 4)))
    label = cfg_get(cfg, "swaps.source_label", "Long-form")
    types = list(cfg_get(cfg, "swaps.types", ["Industry POV", "Poll", f"{label} push"]))
    excluded = {str(c) for c in cfg_get(cfg, "swaps.excluded_chapters", [])}
    chapters = [str(c) for c in cfg_get(cfg, "swaps.chapters", []) if str(c) not in excluded]
    weeks_back = int(cfg_get(cfg, "visuals.no_repeat_weeks", 8))
    teaser = re.compile(cfg_get(cfg, "calendar.teaser_regex", r"LinkedIn teaser"), re.I)
    blog_id = re.compile(cfg_get(cfg, "calendar.blog_id_regex", r"^(Blog \d+)"), re.I)
    existing_re = re.compile(r"Proposed swap: (" + "|".join(re.escape(t) for t in types) + r") on (.+?) \("
                             + re.escape(label) + r" ch(\w+)\)", re.I)

    def kind(ct):
        c = (ct or "").lower()
        return next((t for t in types if t.lower() in c), None)

    hdr = values[0]
    rows = {}
    fb_ids = set()
    for n, r in enumerate(values[1:], start=2):
        r = list(r) + [""] * (len(hdr) - len(r))
        d = dict(zip(hdr, r))
        d["_row"], d["_date"] = n, parse_date(d.get("Date"))
        if d.get("Status") == st["Fallback post"]:  # backup rows under their original are not slots
            fb_ids.add(d.get("Row ID", ""))
            continue
        rows[n] = d
    backlog = []
    if arg(argv, "--backlog"):
        bv = load(arg(argv, "--backlog"))
        for r in bv[1:]:
            r = list(r) + [""] * (len(bv[0]) - len(r))
            b = dict(zip(bv[0], r))
            if b.get("Row ID"):
                backlog.append(b)

    def iso_wk(d):
        return d.isocalendar()[:2] if d else None

    dblocked = [x for x in (arg(argv, "--drafter-blocked", "") or "").split(",") if x]
    cands = []
    for it in sel.get("rows", []):
        if it.get("action") == "draft" and it.get("row_id") in dblocked:
            it = {**it, "action": "blocked", "reason": "drafter returned blocked"}
        if it.get("action") != "blocked":
            continue
        r = rows.get(it["row"])
        if not r or r.get("Status") in skip_st or not r["_date"] or r["_date"] < as_of:
            continue
        if (it.get("reason") or "").startswith("On hold:"):
            if existing_re.search(r.get("Notes", "")):
                cands.append((r, "dependency"))
        elif (r["_date"] - as_of).days <= days:
            cands.append((r, "blocked"))
    for s in match.get("slots", []):
        r = rows.get(s.get("row"))
        if not r or r.get("Status") in skip_st:
            continue
        if s.get("action") == "flag" and (s.get("propose_swap") or existing_re.search(r.get("Notes", ""))):
            if r["_date"] and 0 <= (r["_date"] - as_of).days <= days:
                cands.append((r, "proof"))
    cands.sort(key=lambda c: (c[0]["_date"], c[0]["_row"]))

    chosen, out, skipped = [], [], []
    n_fb = 0
    for r, reason in cands:
        notes = r.get("Notes", "")
        m = existing_re.search(notes)
        item = {"row": r["_row"], "row_id": r.get("Row ID"), "date": fmt(r["_date"]),
                "days_to": (r["_date"] - as_of).days, "reason": reason,
                "original": {"content_type": r.get("Content type"), "title": r.get("Title / angle")}}
        ct = r.get("Content type", "")
        if teaser.search(ct):
            b = blog_id.search(ct)
            name = b.group(1) if b else "blog"
            blog = next((x for x in rows.values() if b and x is not r and blog_id.search(x.get("Content type", "") or "")
                         and blog_id.search(x.get("Content type", "")).group(1).lower() == name.lower()
                         and not teaser.search(x.get("Content type", ""))), None)
            when = blog["_date"] if blog and blog["_date"] else r["_date"]
            item["conditional"] = f"If the {name} link is not in Notes on the blog row by the morning of {fmt(when)}"
        if m:
            t = next((k for k in types if k.lower() == m.group(1).lower()), m.group(1))
            item.update(existing=True, type=t, angle=m.group(2), chapter=m.group(3))
        else:
            wk = iso_wk(r["_date"])  # the ISO week of the Date, never the Week cell
            nxt = iso_wk(r["_date"] + timedelta(days=7))
            counts = {t: 0 for t in types}
            for x in rows.values():
                if iso_wk(x["_date"]) in (wk, nxt) and x.get("Status") not in skip_st:
                    em = existing_re.search(x.get("Notes", ""))
                    if em:
                        counts[next(k for k in types if k.lower() == em.group(1).lower())] += 1
                    elif kind(x.get("Content type")):
                        counts[kind(x.get("Content type"))] += 1
            for c in chosen:
                if c["week"] in (wk, nxt):
                    counts[c["type"]] = counts.get(c["type"], 0) + 1
            t = min(types, key=lambda k: (counts[k], types.index(k)))
            used = {str(c["chapter"]) for c in chosen if c["chapter"] is not None}
            for x in rows.values():
                if x["_date"] and r["_date"] - timedelta(weeks=weeks_back) <= x["_date"] <= r["_date"] + timedelta(days=14):
                    used |= set(CH.findall(x.get("Sources", "")))
                    em = existing_re.search(x.get("Notes", ""))
                    if em:
                        used.add(em.group(3))
            free = [c for c in chapters if c not in used]
            item.update(existing=False, type=t, chapter=free[0] if free else None, chapters_available=free, angle=None)
        chosen.append({"week": iso_wk(r["_date"]), "type": item["type"], "chapter": item["chapter"]})
        if backlog:
            fit = [b for b in backlog if item["type"] and item["type"].lower() in (b.get("Content type") or "").lower()]
            item["backlog_options"] = [{"row_id": b.get("Row ID"), "content_type": b.get("Content type"),
                                        "title": b.get("Title / angle")} for b in (fit or backlog)[:3]]
        has_fb = f"{r.get('Row ID')}-FB" in fb_ids
        if "Fallback draft" in notes or has_fb:
            item["fallback"] = False
            item["fallback_row_exists"] = has_fb
        elif n_fb < cap:
            item["fallback"] = True
            n_fb += 1
        else:
            item["fallback"] = False
            skipped.append(item["row_id"])
        out.append(item)

    # Dated conditions in the current agent line that no longer fit today's calendar.
    stale = []
    for r in rows.values():
        if not r["_date"] or r["_date"] < as_of or r.get("Status") in skip_st + (st["Posted"],):
            continue
        notes = r.get("Notes", "") or ""
        starts = [m.start() for m in agent_line.finditer(notes)]
        if not starts:
            continue
        last = notes[starts[-1]:]
        nxt_person = re.search(r"\s[A-Z][a-z]+(?: [A-Z][a-z]+)?, \d{1,2} [A-Za-z]{3} \d\d:", last)
        if nxt_person:
            last = last[:nxt_person.start()]
        ct = r.get("Content type", "") or ""
        when = r["_date"]
        b = blog_id.search(ct)
        if teaser.search(ct) and b:
            blog = next((x for x in rows.values() if x is not r and blog_id.search(x.get("Content type", "") or "")
                         and blog_id.search(x.get("Content type", "")).group(1).lower() == b.group(1).lower()
                         and not teaser.search(x.get("Content type", ""))), None)
            if blog and blog["_date"]:
                when = blog["_date"]
        for m in re.finditer(r"by the morning of (\d\d [A-Z]{3} \d\d)", last):
            d = parse_date(m.group(1))
            if d and d != when:
                stale.append({"row": r["_row"], "row_id": r.get("Row ID"), "kind": "teaser_condition",
                              "old": m.group(1), "new": fmt(when)})
        for m in re.finditer(r"(?<!morning of )\bby (\d\d [A-Z]{3} \d\d)", last):
            d = parse_date(m.group(1))
            if d and d < as_of:
                stale.append({"row": r["_row"], "row_id": r.get("Row ID"), "kind": "cutoff_passed",
                              "old": m.group(1), "new": fmt(max(as_of, r["_date"] - timedelta(days=2)))})

    print(json.dumps({"as_of": fmt(as_of), "source_label": label, "swaps": out, "fallbacks_skipped": skipped,
                      "stale_notes": stale}, indent=2, ensure_ascii=False))
    return 0


def _usage_ok(argv, n):
    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in VALUE_FLAGS
        else:
            pos.append(a)
    if "-h" in argv or "--help" in argv or len(pos) < n:
        sys.stderr.write((__doc__ or "").strip() + "\n")
        return False
    return True


if __name__ == "__main__":
    if not _usage_ok(sys.argv, 3):
        sys.exit(2)
    sys.exit(main(sys.argv))
