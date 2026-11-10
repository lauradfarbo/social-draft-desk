#!/usr/bin/env python3
"""Decide what the weekly run does with each calendar row (weekly orchestrator).

Usage:
  python3 select_rows.py calendar.json [--config workspace.json] [--facts facts.json]
                         [--milestones milestones.json] [--as-of YYYY-MM-DD] [--horizon 13]
                         [--briefs YYYY-MM-DD,...] [--updates YYYY-MM-DD,...]
                         [--mode full|requests] [--touched W11-02,...] [--series-days 14]
                         [--rerun] [--shadow]

calendar.json: the calendar table, {"values": [[headers], [row 2], ...]}, header row first.
--briefs: dates of the weekly briefs already in the briefs folder of the mode in use (from their
  titles). A date may appear more than once when a rerun brief exists.
--updates: dates of the "Update - DD MMM YY" briefs already there (requests runs), for the suffix.
--milestones: the Milestones tab. A milestone whose Type is a dependency's milestone_type and whose
  Confirmed is Yes lifts that hold.
--mode requests: the light requests run. Also used, without the flag, when a weekly brief for the
  run date already exists (a second run on the same day handles only what changed).
--touched: in requests mode, the Row IDs an open ask, a hand edit, a new idea, a Backlog move or a
  series shift touched (from request_scan.py, snapshot.py compare, backlog.py and series_shift.py).
--rerun: the person asked for a full rerun on the same day: no switch to requests mode, and the
  brief name gets " (2)" (or the next number).
--shadow: shadow mode. Rows that are Planned, Draft ready, Approved or Posted are all selected
  for drafting, because live rows are still produced by hand. Proposed and team-owned rows are
  still never drafted. Each item carries live_status.

Config (workspace.json, all optional, generic defaults):
  company.approver.name, run.horizon_days, run.full_run.weekday (or run.weekday), channels,
  calendar.team_owned_regex, calendar.proof_types (Partner, Customer, Advisor),
  calendar.teaser_regex, calendar.blog_id_regex, calendar.statuses, facts.id_col,
  facts.status_col, facts.approved_values, series.draft_within_days, requests.hold_lift_word,
  dates.typed_order, plan.dependencies (fact_id, label, optional row_regex, hold_regex,
  milestone_type): a Planned row whose Content type or Title / angle match row_regex, name the
  label or name the fact ID, or whose Notes name the fact ID or say it depends on the label, is on
  hold while the fact is not approved. The hold is lifted by the fact turning approved, by a
  Milestones row of the dependency's milestone_type with Confirmed Yes, or, for one row, by the
  hold-lift word (default CONFIRMED) with a date in its Notes.

Prints a JSON plan. It writes nothing.

Row actions for rows dated from the run date to run date + horizon days, plus overdue rows:
  draft          Planned row on a configured channel for the short-form drafter. Always drafted:
                 a missing link, fact, name or photo becomes a [bracketed] gap. Such rows carry
                 "gaps" (what a person must provide, for What's missing) and "placeholders" (the
                 bracket text the drafter puts in the post). Advisor rows carry proof_type
                 "Advisor": match_proof.py may give them an item.
  proof          Planned Partner or Customer proof slot for proof intake
  team_owned     content the team produces (team_owned_regex): never drafted
  proposed       Status Proposed: not drafted, flagged for the approver
  blocked        Planned, but on a dependency hold or not on a drafted channel (reason given).
                 Only hard rules and holds block a draft.
  in_review      Draft ready or Approved: nothing to do
  refresh        Draft ready base draft whose blog-link gap can now be filled: redraft into a
                 " v2" tab; Status stays Draft ready, Draft URL moves to the v2 tab and Original
                 draft is replaced with "v2": true
  fallback_row   Status Fallback post: a backup row under its original; nothing to do, never overdue
  overdue        Date passed and not Posted: listed in the brief
Series rows (Notes say "post N of M") are selected up to series.draft_within_days (default 14)
ahead and carry "series": true when beyond the horizon. A series row further out is drafted once
its details arrive; the orchestrator adds it itself.
Cancelled and Backlog rows (set by a person) are skipped everywhere and never appear in this
output, so they never reach the brief, the run summary or a notification. "_internal" holds
counts for run checks only; never quote it.
Also:
  final_text       Posted rows with a Draft URL and an empty Final text (any date)
  missed_runs      full-run days since the last brief with no brief
  approved_gaps    Approved rows due within 2 days whose What's missing still lists something other
                   than images (a headshot, a logo or a permission still counts: it needs consent)
  same_day_brief   true when a weekly brief for the run date already exists
  run_mode         "full" or "requests" (requests when asked, or on a second run the same day)
  brief_title      "Weekly brief - DD MMM YY" (full) or "Update - DD MMM YY" (requests), with any suffix
  requests         requests-mode inputs: the sources to read, the steps to skip, the touched rows,
                   the refresh rows, and nothing_to_do (write only the snapshot and stop)
  first_full_run_of_month  true when no weekly brief exists earlier in the run date's month
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CANON = ["Proposed", "Planned", "Draft ready", "Fallback post", "Approved", "Posted", "Cancelled", "Backlog"]
LEGACY = ["Proposed", "Planned", "Draft ready", "Approved", "Posted", "Cancelled"]
VALUE_FLAGS = {"--config", "--facts", "--milestones", "--as-of", "--horizon", "--briefs", "--updates",
               "--mode", "--touched", "--series-days"}
URL = re.compile(r"https?://\S+")
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
SERIES = re.compile(r"\bpost \d+ of \d+\b", re.I)
GAP = re.compile(r"\[[^\]]{2,80}\]")
IMAGE = re.compile(r"photo|image|graphic|visual|video|picture|header", re.I)
CONSENT = re.compile(r"headshot|logo|permission", re.I)
DATE_IN_TEXT = re.compile(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(?:\s+\d{2,4})?\b"
                          r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", re.I)
TYPED_ORDER = ["day_first"]


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


def approver(cfg, cap=True):
    n = cfg_get(cfg, "company.approver.name", "")
    return n if n else ("The approver" if cap else "the approver")


def parse_date(s):
    """Displayed (Tue 17 MAR 26), written (2026-03-17) or typed (day or month first, per dates.typed_order)."""
    s = (s or "").strip()
    num = ("%m/%d/%y", "%m/%d/%Y") if TYPED_ORDER[0] == "month_first" else ("%d/%m/%y", "%d/%m/%Y", "%d.%m.%y", "%d.%m.%Y")
    for f in ("%a %d %b %y", "%d %b %y", "%Y-%m-%d", "%d %b %Y") + num:
        try:
            return datetime.strptime(s.title() if "%b" in f else s, f).date()
        except ValueError:
            pass
    return None


def fmt(d):
    return f"{d.day:02d} {d.strftime('%b').upper()} {d.strftime('%y')}"  # zero-padded: 03 NOV 26


def arg(argv, k, default=None):
    return argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else default


def load(path):
    v = json.load(open(path, encoding="utf-8"))
    return v.get("values", v) if isinstance(v, dict) else v


def facts_status(path, cfg):
    fv = load(path)
    hdr = [h.strip() for h in fv[0]]
    id_c, st_c = cfg_get(cfg, "facts.id_col", "ID"), cfg_get(cfg, "facts.status_col", "Status")
    i_id = hdr.index(id_c) if id_c in hdr else 0
    i_st = hdr.index(st_c) if st_c in hdr else 3
    out = {}
    for r in fv[1:]:
        r = list(r) + [""] * len(hdr)
        if r[i_id].strip():
            out[r[i_id].strip().upper()] = r[i_st].strip()
    return out


def confirmed_types(path):
    """Milestone Types with at least one row Confirmed Yes (lower case)."""
    mv = load(path)
    if not mv:
        return set()
    mh = [h.strip().lower() for h in mv[0]]
    i_t = mh.index("type") if "type" in mh else 1
    i_c = mh.index("confirmed") if "confirmed" in mh else 4
    out = set()
    for m in mv[1:]:
        m = list(m) + [""] * len(mh)
        if m[i_c].strip().lower() == "yes" and m[i_t].strip():
            out.add(m[i_t].strip().lower())
    return out


def depends(row, dep):
    """A row depends on a fact from its type or title, or from an explicit note."""
    text = " ".join(row.get(k, "") or "" for k in ("Title / angle", "Content type")).lower()
    notes = (row.get("Notes", "") or "").lower()
    label = (dep.get("label") or "").lower()
    fid = (dep.get("fact_id") or "").lower()
    rx = dep.get("row_regex")
    if rx and re.search(rx, text, re.I):
        return True
    if label and label in text:
        return True
    if fid and re.search(r"\b" + re.escape(fid) + r"\b", text + " " + notes):
        return True
    if label and re.search(r"depends on the " + re.escape(label), notes):
        return True
    hr = dep.get("hold_regex")
    return bool(hr and label and label in notes and re.search(hr, notes, re.I))


def hold_lifted_in_notes(row, word):
    for line in re.split(r"(?<=[.!?])\s+|\n", row.get("Notes", "") or ""):
        if re.search(r"\b" + re.escape(word) + r"\b", line) and DATE_IN_TEXT.search(line):
            return True
    return False


def main(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    TYPED_ORDER[0] = cfg_get(cfg, "dates.typed_order", "day_first")
    who = approver(cfg)
    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in VALUE_FLAGS
        else:
            pos.append(a)
    v = load(pos[0])
    as_of = date.fromisoformat(arg(argv, "--as-of")) if "--as-of" in argv else date.today()
    horizon = int(arg(argv, "--horizon", cfg_get(cfg, "run.horizon_days", 13)))
    series_days = int(arg(argv, "--series-days", cfg_get(cfg, "series.draft_within_days", 14)))
    shadow = "--shadow" in argv
    briefs = [date.fromisoformat(x) for x in (arg(argv, "--briefs", "") or "").split(",") if x.strip()]
    updates = [date.fromisoformat(x) for x in (arg(argv, "--updates", "") or "").split(",") if x.strip()]
    touched = [x.strip() for x in (arg(argv, "--touched", "") or "").split(",") if x.strip()]
    team = re.compile(cfg_get(cfg, "calendar.team_owned_regex", r"Publish|Newsletter|Distribute"), re.I)
    ptypes = cfg_get(cfg, "calendar.proof_types", {"Partner": "Partner Win", "Customer": "Customer Proof"})
    slot_types = [p for k, p in ptypes.items() if p and k != "Advisor"]
    advisor_type = ptypes.get("Advisor")
    proof_re = re.compile("|".join(re.escape(p) for p in slot_types), re.I) if slot_types else None
    teaser = re.compile(cfg_get(cfg, "calendar.teaser_regex", r"LinkedIn teaser"), re.I)
    blog_id = re.compile(cfg_get(cfg, "calendar.blog_id_regex", r"^(Blog \d+)"), re.I)
    channels = [c.lower() for c in cfg_get(cfg, "channels", ["LinkedIn"])]
    weekday = str(cfg_get(cfg, "run.full_run.weekday", cfg_get(cfg, "run.weekday", "Monday"))).strip().lower()
    run_wd = WEEKDAYS.index(weekday) if weekday in WEEKDAYS else 0
    lift_word = cfg_get(cfg, "requests.hold_lift_word", "CONFIRMED")
    approved_vals = cfg_get(cfg, "facts.approved_values", ["Approved", "Approved with edits"])
    fstat = facts_status(arg(argv, "--facts"), cfg) if arg(argv, "--facts") else None
    mtypes = confirmed_types(arg(argv, "--milestones")) if arg(argv, "--milestones") else set()
    deps = cfg_get(cfg, "plan.dependencies", [])
    open_deps = [d for d in deps if fstat is not None
                 and fstat.get((d.get("fact_id") or "").upper()) not in approved_vals
                 and not (d.get("milestone_type") and d["milestone_type"].strip().lower() in mtypes)]

    same = briefs.count(as_of)
    rerun = "--rerun" in argv
    requests_mode = (arg(argv, "--mode", "full") == "requests") or (same > 0 and not rerun)

    hdr = v[0]
    rows = []
    for n, r in enumerate(v[1:], start=2):
        r = list(r) + [""] * (len(hdr) - len(r))
        d = dict(zip(hdr, r))
        d["_row"], d["_date"] = n, parse_date(d.get("Date"))
        rows.append(d)

    def blog_of(r, m):
        if not m:
            return None
        return next((b for b in rows if b is not r and blog_id.search(b.get("Content type", "") or "")
                     and blog_id.search(b.get("Content type", "")).group(1).lower() == m.group(1).lower()
                     and not teaser.search(b.get("Content type", ""))
                     and b.get("Status") not in (st["Cancelled"], st["Backlog"])), None)

    end = as_of + timedelta(days=horizon)
    plan, final_text, gaps = [], [], []
    cancelled = backlog = 0
    for r in rows:
        if not r["_date"]:
            continue
        s, ct, notes = r.get("Status", ""), r.get("Content type", ""), r.get("Notes", "") or ""
        if s == st["Cancelled"]:
            cancelled += 1
            continue
        if s == st["Backlog"]:
            backlog += 1  # backlog.py moves the row to the Backlog tab
            continue
        overdue = r["_date"] < as_of
        wm = (r.get("What's missing") or "").strip()
        if s == st["Approved"] and wm and 0 <= (r["_date"] - as_of).days <= 2:
            items = [i.strip() for i in re.split(r"(?<=[.;])\s+", wm) if i.strip()]
            still = [i for i in items if CONSENT.search(i) or not IMAGE.search(i)]
            if still:
                gaps.append({"row": r["_row"], "row_id": r.get("Row ID"), "date": fmt(r["_date"]), "whats_missing": " ".join(still),
                             "brief_line": f"{r.get('Row ID')} ({fmt(r['_date'])}) is Approved but What's missing still says: "
                                           f"\"{' '.join(still)}\". {who} to confirm it is resolved before it posts."})
        if s == st["Posted"]:
            if r.get("Draft URL") and not r.get("Final text"):
                final_text.append({"row": r["_row"], "row_id": r.get("Row ID"), "draft_url": r.get("Draft URL")})
            if not (shadow and not overdue and r["_date"] <= end):
                continue
        base = {"row": r["_row"], "row_id": r.get("Row ID"), "date": fmt(r["_date"]), "week": str(r["_date"].isocalendar()[1]),
                "content_type": ct, "status": s, "title": r.get("Title / angle")}
        if s == st["Fallback post"]:
            if as_of <= r["_date"] <= end:
                plan.append({**base, "action": "fallback_row"})
            continue
        series = bool(SERIES.search(notes)) and s == st["Planned"] and not r.get("Draft URL")
        if not overdue and r["_date"] > end and not (series and r["_date"] <= as_of + timedelta(days=series_days)):
            continue
        item = dict(base)
        if shadow:
            item["live_status"] = s
            if s in (st["Draft ready"], st["Approved"], st["Posted"]):
                s = st["Planned"]  # shadow drafts these too; nothing is written to the row
        dep = next((d for d in open_deps if depends(r, d)), None)
        if dep and hold_lifted_in_notes(r, lift_word):
            dep = None
        if overdue:
            item["action"] = "overdue"
        elif team.search(ct):
            item["action"] = "team_owned"
        elif s == st["Proposed"]:
            item["action"] = "proposed"
            item["reason"] = f"Status is Proposed: {who} to review and set Planned before it can be drafted."
        elif s in (st["Draft ready"], st["Approved"]):
            item["action"] = "in_review"
            left = GAP.findall(r.get("Original draft", "") or "")
            if left and s == st["Draft ready"]:
                item["gaps_left"] = left
                m = blog_id.search(ct) if teaser.search(ct) else None
                blog = blog_of(r, m)
                link = URL.findall(blog.get("Notes", "") or "") if blog else []
                ph = f"[{m.group(1)} link]".lower() if m else None
                if link and ph and any(g.lower() == ph for g in left):
                    item.update(action="refresh", blog_link=link[-1], blog_row_id=blog.get("Row ID"),
                                reason="Base draft had a gap; the blog link is now in Notes. Redraft into a v2 tab.")
        elif s != st["Planned"]:
            item["action"] = "blocked"
            item["reason"] = f"Status '{s}' is not one the run acts on."
        elif channels and not any(c in (r.get("Channel", "") or "").lower() for c in channels):
            item["action"] = "blocked"
            item["reason"] = "Channel is not one the agents draft for."
        elif proof_re and proof_re.search(ct):
            item["action"] = "proof"
        elif dep:
            item["action"] = "blocked"
            item["reason"] = f"On hold: {dep.get('label') or 'dependency'} (fact {dep.get('fact_id')}) is not approved. Not drafted."
        elif teaser.search(ct):
            m = blog_id.search(ct)
            blog = blog_of(r, m)
            link = URL.findall(blog.get("Notes", "") or "") if blog else []
            label = m.group(1) if m else "blog"
            item["action"] = "draft"
            if link:
                item["blog_link"] = link[-1]
                item["blog_row_id"] = blog.get("Row ID")
            else:  # base draft with the link as a gap
                miss = f"Published {label} link in Notes on {blog.get('Row ID') if blog else 'the blog row'}."
                item["gaps"] = [miss]
                item["placeholders"] = [f"[{label} link]"]
                item["whats_missing"] = miss
                item["reason"] = (f"Published {label} link is not in Notes on the blog row "
                                  f"({blog.get('Row ID') if blog else 'not found'}); drafted with the link as a gap.")
        else:
            item["action"] = "draft"
        if item["action"] == "draft":
            if wm and "gaps" not in item:
                item["gaps"] = [wm]  # drafted anyway; the drafter brackets what is missing
            if advisor_type and advisor_type.lower() in ct.lower():
                item["proof_type"] = "Advisor"
        if series:
            item["series_note"] = SERIES.search(notes).group(0)
            if r["_date"] > end:
                item["series"] = True
        plan.append(item)

    missed = []
    if briefs and not requests_mode:
        last = max(briefs)
        d = last + timedelta(days=(run_wd - last.weekday()) % 7 or 7)
        while d <= as_of:
            if d not in briefs and d != as_of:
                missed.append(fmt(d))
            d += timedelta(days=7)

    refresh = [p["row_id"] for p in plan if p["action"] == "refresh"]
    req = None
    if requests_mode:
        window = as_of + timedelta(days=series_days)
        keep = set(touched) | set(refresh)
        plan = [p for p in plan if p["row_id"] in keep and (p.get("series") or parse_date(p["date"]) <= window
                                                          or p["action"] == "overdue")]
        n_up = updates.count(as_of)
        req = {"active": True, "reason": "requests mode" if arg(argv, "--mode") == "requests" else "second run on the same day",
               "window_days": series_days,
               "inputs": [
                   {"name": "asks", "from": "request_scan.py", "what": "open asks in Notes and on the Ideas tab"},
                   {"name": "hand_edits", "from": "snapshot.py compare", "what": "row_changes and milestone_changes since the last run"},
                   {"name": "ideas", "from": "the Ideas tab", "what": "new ideas"},
                   {"name": "backlog", "from": "backlog.py plan", "what": "rows set to Backlog, and Backlog rows set to Planned"},
                   {"name": "series", "from": "series_shift.py", "what": "series posts that moved or were cancelled"}],
               "skip": ["planner", "fallbacks", "monthly run", "voice guide proposals"],
               "touched": touched, "refresh": refresh,
               "nothing_to_do": not plan,
               "brief_only_if_changed": True}
        title = f"Update - {fmt(as_of)}" + (f" ({n_up + 1})" if n_up else "")
    else:
        title = f"Weekly brief - {fmt(as_of)}" + (f" ({same + 1})" if same and rerun else "")
    month_runs = [b for b in briefs if b.year == as_of.year and b.month == as_of.month and b < as_of]

    acts = ("draft", "proof", "team_owned", "proposed", "blocked", "in_review", "refresh", "fallback_row", "overdue")
    out = {"mode": "shadow" if shadow else "normal", "as_of": fmt(as_of), "window": f"{fmt(as_of)} to {fmt(end)}",
           "run_mode": "requests" if requests_mode else "full",
           "same_day_brief": same > 0, "brief_title": title,
           "brief_suffix": f" ({same + 1})" if same and rerun else "",
           "first_full_run_of_month": not requests_mode and not month_runs,
           "rows": plan, "final_text": final_text, "missed_runs": missed, "approved_gaps": gaps,
           "counts": {a: sum(1 for p in plan if p["action"] == a) for a in acts},
           "_internal": {"cancelled_skipped": cancelled, "backlog_skipped": backlog}}
    if req:
        out["requests"] = req
    print(json.dumps(out, indent=2, ensure_ascii=False))
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
    if not _usage_ok(sys.argv, 1):
        sys.exit(2)
    sys.exit(main(sys.argv))
