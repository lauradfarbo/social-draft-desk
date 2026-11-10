#!/usr/bin/env python3
"""Structural plan checks for the next plan weeks (planner).

Usage:
  python3 plan_check.py calendar.json facts.json [proof_log.json] [--config workspace.json]
                        [--milestones milestones.json] [--as-of YYYY-MM-DD] [--weeks 4]

calendar.json: the calendar table, {"values": [[headers], [row 2], ...]}, header row first.
facts.json: the facts sheet table. Used for dependency facts.
proof_log.json: optional, the proof log table. Used for early proof risks (15 to 28 days out).
milestones.json: optional, the Milestones tab. A milestone with Confirmed "Cancelled" lists its
  remaining Proposed, Planned, Draft ready and Approved rows once in cancelled_milestones and
  brief_risks, so the approver can set them to Cancelled in one go. A row belongs to a milestone
  when its Notes say "Milestone: <milestone name>." or its Title / angle contains the milestone's
  short name (the text before ":" or " (").

Weeks: every "Week N" is the ISO week of the row's Date; the Week column is not read. Odd and even
weeks alternate from calendar.alternation_anchor_week ({"year", "week"}, default 2026 week 1), so
week 53 and week 1 still alternate. A config with only plan.week1_monday anchors on that Monday
as week 1.

Every check reads its rule from workspace.json. A missing key skips that check:
  plan.known_deviations    Row IDs that intentionally break the cadence (no cadence notes)
  plan.posts_per_week      [min, max] posts a week on the configured channels
  plan.proof_slot          {"weekday": "Tue", "odd_weeks": "<proof type>", "even_weeks": "<proof type>"}
  plan.proof_slots         [{"weekday": "Tue", "type": "<proof type>"}, ...]: every week, one slot per entry
                           (used instead of proof_slot when set). An Advisor row (calendar.proof_types.Advisor)
                           fills a Customer proof slot. A proof slot a person asked to change (Notes "Changed
                           from <proof type> ... as asked") is a decision, not a gap. A proof row on its slot
                           day that shares the date with another post is listed once in brief_risks.
  plan.blog_pair           {"weekday": "Wed", "weeks": "odd" | "even" | "all"}: blog and teaser, same day
  plan.rotation_slot       {"weekday": "Thu", "types": [...]}: the post on that day is one of these types
  plan.no_repeat_in_week   content type words that may appear once a week only (for example "POV", "Poll")
  plan.dependencies        [{"fact_id", "deadline", "label", "hold_regex", "row_regex", "milestone_type"}]: rows
                           that depend on a fact not yet approved get a note after the deadline; the brief warns
                           from 7 days before. A row depends on it from its Content type or Title / angle, or an
                           explicit note (the fact ID, or "depends on the <label>"). The hold is lifted when the
                           fact is approved, when a Milestones row of milestone_type has Confirmed Yes, or for one
                           row when its Notes hold requests.hold_lift_word (default CONFIRMED) with a date
  plan.precedence          "dated_events_first" (default) or "off": a dated event (Content type matching
                           plan.dated_event_regex, default "event|webinar") takes its day over an unconnected blog
                           pair; precedence_moves gives each blog or teaser row a new date on the next free same
                           weekday, with a note. A blog is connected when its title shares the event's title start
                           or names the event's Row ID or milestone
  company.holiday_market   US, UK or NL: public holidays on posting days and holiday weeks are flagged.
                           Any other market: the holiday check is skipped and the output says so
  company.approver.name, channels, calendar.*, facts.*, run.plan_check_weeks

Fallback post rows (backups under their original) are not slots and are ignored.
Cancelled and Backlog rows (set by a person) are decisions, not gaps: they still count as present for the
"missing slot" and "fewer than the minimum" checks, but get no notes, are left out of the
"more than the maximum" and repeat checks, and are never named in brief_risks.

Also flags a conditional swap note ("If the <blog> link is not in Notes ... by the morning of
DD MMM YY") whose date no longer matches the blog row's current date.

Prints a JSON plan. It writes nothing; the orchestrator writes Notes and What's missing.
Sentences are fixed text so a re-run can tell whether a row already carries the note.
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CANON = ["Proposed", "Planned", "Draft ready", "Fallback post", "Approved", "Posted", "Cancelled", "Backlog"]
LEGACY = ["Proposed", "Planned", "Draft ready", "Approved", "Posted", "Cancelled"]
DATE_IN_TEXT = re.compile(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(?:\s+\d{2,4})?\b"
                          r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", re.I)
TYPED_ORDER = ["day_first"]
VALUE_FLAGS = {"--config", "--milestones", "--as-of", "--weeks"}
WD = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
COND = re.compile(r"If the (.+?) link is not in Notes.*?by the morning of (\d{2} [A-Z]{3} \d{2})", re.S)


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


def parse_date(s):
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


def wd_index(s):
    s = (s or "").strip().lower()[:3]
    return WD.index(s) if s in WD else None


# ---- Public holidays (built in: US, UK, NL) ----

def nth_weekday(y, m, wd, n):
    d = date(y, m, 1)
    d += timedelta(days=(wd - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def last_weekday(y, m, wd):
    d = date(y, m + 1, 1) - timedelta(days=1) if m < 12 else date(y, 12, 31)
    return d - timedelta(days=(d.weekday() - wd) % 7)


def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(y, month, day)


def us_holidays(y):
    return {
        date(y, 1, 1): "New Year's Day",
        nth_weekday(y, 1, 0, 3): "Martin Luther King Jr. Day",
        nth_weekday(y, 2, 0, 3): "Presidents' Day",
        last_weekday(y, 5, 0): "Memorial Day",
        date(y, 6, 19): "Juneteenth",
        date(y, 7, 4): "Independence Day",
        nth_weekday(y, 9, 0, 1): "Labor Day",
        nth_weekday(y, 10, 0, 2): "Columbus Day",
        date(y, 11, 11): "Veterans Day",
        nth_weekday(y, 11, 3, 4): "Thanksgiving Day",
        date(y, 12, 25): "Christmas Day",
    }


def uk_holidays(y):
    """England and Wales bank holidays, with weekend substitute days."""
    e = easter(y)
    out = {
        e - timedelta(days=2): "Good Friday",
        e + timedelta(days=1): "Easter Monday",
        nth_weekday(y, 5, 0, 1): "Early May bank holiday",
        last_weekday(y, 5, 0): "Spring bank holiday",
        last_weekday(y, 8, 0): "Summer bank holiday",
    }
    ny = date(y, 1, 1)
    out[ny + timedelta(days={5: 2, 6: 1}.get(ny.weekday(), 0))] = "New Year's Day" + (" (substitute day)" if ny.weekday() > 4 else "")
    xmas, box = date(y, 12, 25), date(y, 12, 26)
    if xmas.weekday() == 5:
        out[date(y, 12, 27)], out[date(y, 12, 28)] = "Christmas Day (substitute day)", "Boxing Day (substitute day)"
    elif xmas.weekday() == 6:
        out[date(y, 12, 26)], out[date(y, 12, 27)] = "Boxing Day", "Christmas Day (substitute day)"
    elif xmas.weekday() == 4:
        out[xmas], out[date(y, 12, 28)] = "Christmas Day", "Boxing Day (substitute day)"
    else:
        out[xmas], out[box] = "Christmas Day", "Boxing Day"
    return out


def nl_holidays(y):
    e = easter(y)
    kd = date(y, 4, 27)
    if kd.weekday() == 6:
        kd = date(y, 4, 26)
    out = {
        date(y, 1, 1): "New Year's Day",
        e - timedelta(days=2): "Good Friday",
        e: "Easter Sunday",
        e + timedelta(days=1): "Easter Monday",
        kd: "King's Day",
        e + timedelta(days=39): "Ascension Day",
        e + timedelta(days=49): "Whit Sunday",
        e + timedelta(days=50): "Whit Monday",
        date(y, 12, 25): "Christmas Day",
        date(y, 12, 26): "Second Day of Christmas",
    }
    if y % 5 == 0:
        out[date(y, 5, 5)] = "Liberation Day"
    return out


HOLIDAYS = {"US": us_holidays, "UK": uk_holidays, "GB": uk_holidays, "NL": nl_holidays}


def load(path):
    v = json.load(open(path, encoding="utf-8"))
    return v.get("values", v) if isinstance(v, dict) else v


def rows(values):
    hdr = values[0]
    out = []
    for n, r in enumerate(values[1:], start=2):
        r = list(r) + [""] * (len(hdr) - len(r))
        d = dict(zip(hdr, r))
        d["_row"] = n
        d["_date"] = parse_date(d.get("Date", ""))
        d["_week"] = None  # set from the Date in main()
        out.append(d)
    return out


def depends(row, dep):
    """A row depends on a fact from its type or title, or from an explicit note."""
    text = " ".join(row.get(k, "") or "" for k in ("Title / angle", "Content type")).lower()
    notes = (row.get("Notes", "") or "").lower()
    rx = dep.get("row_regex")
    if rx and re.search(rx, text, re.I):
        return True
    label = (dep.get("label") or "").lower()
    fid = (dep.get("fact_id") or "").lower()
    if label and label in text:
        return True
    if fid and re.search(r"\b" + re.escape(fid) + r"\b", text + " " + notes):
        return True
    return bool(label and re.search(r"depends on the " + re.escape(label), notes))


def hold_lifted_in_notes(row, word):
    for line in re.split(r"(?<=[.!?])\s+|\n", row.get("Notes", "") or ""):
        if re.search(r"\b" + re.escape(word) + r"\b", line) and DATE_IN_TEXT.search(line):
            return True
    return False


def monday_of(d):
    return d - timedelta(days=d.weekday())


def main(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    TYPED_ORDER[0] = cfg_get(cfg, "dates.typed_order", "day_first")
    who = cfg_get(cfg, "company.approver.name", "") or "The approver"
    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in VALUE_FLAGS
        else:
            pos.append(a)
    as_of = date.fromisoformat(argv[argv.index("--as-of") + 1]) if "--as-of" in argv else date.today()
    weeks_n = int(argv[argv.index("--weeks") + 1]) if "--weeks" in argv else int(cfg_get(cfg, "run.plan_check_weeks", 4))
    milestones = load(argv[argv.index("--milestones") + 1]) if "--milestones" in argv else None
    cal = [r for r in rows(load(pos[0])) if r.get("Status") != st["Fallback post"]]  # backups are not slots
    facts_v = load(pos[1])
    proof = load(pos[2]) if len(pos) > 2 else None

    team = re.compile(cfg_get(cfg, "calendar.team_owned_regex", r"Publish|Newsletter|Distribute"), re.I)
    teaser = re.compile(cfg_get(cfg, "calendar.teaser_regex", r"LinkedIn teaser"), re.I)
    blog_id = re.compile(cfg_get(cfg, "calendar.blog_id_regex", r"^(Blog \d+)"), re.I)
    proof_types = cfg_get(cfg, "calendar.proof_types", {"Partner": "Partner Win", "Customer": "Customer Proof"})
    channels = [c.lower() for c in cfg_get(cfg, "channels", ["LinkedIn"])]
    known = set(cfg_get(cfg, "plan.known_deviations", []))
    plan_cfg = cfg_get(cfg, "plan", {})
    approved_vals = cfg_get(cfg, "facts.approved_values", ["Approved", "Approved with edits"])

    # Facts: status by ID.
    fh = [h.strip() for h in facts_v[0]]
    id_c, st_c = cfg_get(cfg, "facts.id_col", "ID"), cfg_get(cfg, "facts.status_col", "Status")
    i_id, i_st = (fh.index(id_c) if id_c in fh else 0), (fh.index(st_c) if st_c in fh else 3)
    fstat = {}
    for r in facts_v[1:]:
        r = list(r) + [""] * len(fh)
        if r[i_id].strip():
            fstat[r[i_id].strip().upper()] = r[i_st].strip()

    def proof_kind(ct):
        for k, v in proof_types.items():
            if v and v.lower() in (ct or "").lower():
                return k
        return None

    def slot_kind(ct):
        """Proof key for slot checks: an Advisor row fills a Customer slot."""
        k = proof_kind(ct)
        return "Customer" if k == "Advisor" and "Customer" in proof_types else k

    def is_blog(r):
        ct = r.get("Content type", "") or ""
        return bool(blog_id.search(ct)) and bool(team.search(ct)) and not teaser.search(ct)

    def is_post(r):
        ct = r.get("Content type", "") or ""
        return not team.search(ct) and any(c in (r.get("Channel", "") or "").lower() for c in channels)

    # Week numbering: ISO weeks for labels; odd and even alternate from a fixed anchor week.
    anc = cfg_get(cfg, "calendar.alternation_anchor_week", None)
    w1 = plan_cfg.get("week1_monday")
    if isinstance(anc, dict) and anc.get("year") and anc.get("week"):
        anchor_monday, anchor_no = date.fromisocalendar(int(anc["year"]), int(anc["week"]), 1), int(anc["week"])
    elif w1:
        anchor_monday, anchor_no = monday_of(date.fromisoformat(w1)), 1  # plan week 1 from plan.week1_monday
    else:
        anchor_monday, anchor_no = date.fromisocalendar(2026, 1, 1), 1
    checks, brief, row_notes, notes_out = [], [], [], []
    for r in cal:
        if r["_date"]:
            r["_week"] = monday_of(r["_date"])  # the Monday of the row's week identifies the week

    def is_odd(monday):
        return bool((anchor_no + (monday - anchor_monday).days // 7) % 2)

    def iso_no(monday):
        return monday.isocalendar()[1]

    market = (cfg_get(cfg, "company.holiday_market", "") or "").upper()
    hol_fn = HOLIDAYS.get(market)
    if not hol_fn:
        notes_out.append(f"Holiday check skipped: no built-in public holidays for market '{market or 'not set'}'. "
                         "The planner judges holidays from the plan rules.")

    def holidays_between(a, b):
        if not hol_fn:
            return {}
        out = {}
        for y in {a.year, b.year}:
            out.update({d: n for d, n in hol_fn(y).items() if a <= d <= b})
        return out

    first = monday_of(as_of)
    weeks = [first + timedelta(weeks=i) for i in range(weeks_n)]
    in_scope = [r for r in cal if r["_week"] in weeks and r["_date"]]
    tag = f"Planner {fmt(as_of)}:"
    off_plan = (st["Cancelled"], st["Backlog"])
    lift_word = cfg_get(cfg, "requests.hold_lift_word", "CONFIRMED")
    mtypes = set()
    if milestones:
        mh0 = [h.strip().lower() for h in milestones[0]]
        i_t0 = mh0.index("type") if "type" in mh0 else 1
        i_c0 = mh0.index("confirmed") if "confirmed" in mh0 else 4
        for m in milestones[1:]:
            m = list(m) + [""] * len(mh0)
            if m[i_c0].strip().lower() == "yes" and m[i_t0].strip():
                mtypes.add(m[i_t0].strip().lower())

    def note(r, text, missing="", kind_="rule"):
        if r.get("Status") in off_plan:
            return  # a person's decision: no notes on cancelled or backlog rows
        already = text in (r.get("Notes", "") or "")
        row_notes.append({"row": r["_row"], "row_id": r.get("Row ID", ""), "kind": kind_, "note": f"{tag} {text}",
                          "body": text, "whats_missing": missing, "already_noted": already,
                          "status": r.get("Status", ""), "date": fmt(r["_date"]) if r["_date"] else ""})

    ps = plan_cfg.get("proof_slot") or {}
    pss = [x for x in (plan_cfg.get("proof_slots") or []) if isinstance(x, dict) and x.get("type")]
    conv_rx = re.compile(r"Changed from (" + "|".join(re.escape(v) for v in proof_types.values() if v) + r")\b.*?as asked", re.I | re.S) \
        if any(proof_types.values()) else None
    bp = plan_cfg.get("blog_pair") or {}
    rot = plan_cfg.get("rotation_slot") or {}
    ppw = plan_cfg.get("posts_per_week")
    nrw = plan_cfg.get("no_repeat_in_week") or []

    for monday in weeks:
        sunday = monday + timedelta(days=6)
        wr = [r for r in in_scope if r["_week"] == monday and r.get("Status") != "Declined"]
        live = [r for r in wr if r.get("Status") != st["Proposed"]]  # includes Cancelled and Backlog: present for gap checks
        active = [r for r in live if r.get("Status") not in off_plan]
        hol = holidays_between(monday, sunday)
        label = f"Week {iso_no(monday)} ({fmt(monday)})"
        if not wr:
            brief.append(f"{label}: no rows on the calendar.")
            continue
        odd = is_odd(monday)
        converted = [r for r in live if conv_rx and conv_rx.search(r.get("Notes", "") or "")]

        # Proof slots.
        if pss:
            proofs = [r for r in live if slot_kind(r.get("Content type"))]
            checks.append(f"{label}: proof slots")
            for slot in pss:
                key = next((k for k, v in proof_types.items() if v and v.lower() == slot["type"].lower()), None)
                day = wd_index(slot.get("weekday"))
                mine = [r for r in proofs if slot_kind(r.get("Content type")) == key]
                if not mine and not converted and not hol:
                    brief.append(f"{label} has no {slot['type']} slot; the plan puts one on "
                                 f"{FULL[day] if day is not None else 'its day'} every week.")
                for r in mine:
                    if r.get("Row ID") in known or day is None or (monday + timedelta(days=day)) in hol:
                        continue
                    if r["_date"].weekday() != day:
                        note(r, f"The {slot['type']} slot is planned for {FULL[day]}; this row is on a {r['_date'].strftime('%A')}.")
                    elif r.get("Status") not in off_plan:
                        others = [o for o in active if o is not r and o["_date"] == r["_date"] and is_post(o)]
                        if others:
                            brief.append(f"{fmt(r['_date'])}: the {slot['type']} slot ({r.get('Row ID')}) shares the day with "
                                         f"{', '.join(o.get('Row ID', '') for o in others)}. {who} to decide which runs.")
        elif ps:
            want_type = ps.get("odd_weeks") if odd else ps.get("even_weeks")
            want_day = wd_index(ps.get("weekday"))
            proofs = [r for r in live if proof_kind(r.get("Content type"))]
            checks.append(f"{label}: proof slot")
            if not proofs and not converted:
                brief.append(f"{label} has no proof slot; the plan needs one every week.")
            want_key = next((k for k, v in proof_types.items() if v and want_type and v.lower() == want_type.lower()), None)
            for r in proofs:
                if r.get("Row ID") in known:
                    continue
                if want_type and want_type.lower() not in r["Content type"].lower() and slot_kind(r["Content type"]) != want_key:
                    note(r, f"Plan rules put {want_type} in {'odd' if odd else 'even'} weeks; this week has {r['Content type']}. {who} to confirm or swap.")
                slot_day = monday + timedelta(days=want_day) if want_day is not None else None
                if want_day is not None and r["_date"].weekday() != want_day and slot_day not in hol:
                    note(r, f"The proof slot is planned for {FULL[want_day]}; this row is on a {r['_date'].strftime('%A')}.")

        # Blog pair.
        pubs = [r for r in live if is_blog(r)]
        teas = [r for r in live if teaser.search(r.get("Content type", "") or "")]
        if bp:
            mode = (bp.get("weeks") or "all").lower()
            blog_week = mode == "all" or (mode == "odd" and odd) or (mode == "even" and not odd)
            checks.append(f"{label}: blog pair")
            if blog_week and not (pubs and teas):
                brief.append(f"{label} is a blog week but the calendar has {'no blog' if not pubs else 'no teaser'}.")
            if not blog_week:
                for r in pubs:
                    if r.get("Row ID") not in known:
                        note(r, f"Plan rules put the blog pair in {mode} weeks; this blog is in {'an odd' if odd else 'an even'} week. {who} to confirm.")
            bday = wd_index(bp.get("weekday"))
            for r in pubs:
                if bday is not None and r["_date"].weekday() != bday and r.get("Row ID") not in known:
                    note(r, f"The blog is planned for {FULL[bday]}; this row is on a {r['_date'].strftime('%A')}.")
        for t in teas:
            if pubs and not [p for p in pubs if p["_date"] == t["_date"]]:
                note(t, "The teaser should go out on the same day as its blog, a few hours after it.")

        # Post count and repeats.
        present = [r for r in live if is_post(r)]
        posts = [r for r in active if is_post(r)]
        if ppw and len(ppw) == 2:
            checks.append(f"{label}: post count")
            if len(posts) > ppw[1]:
                brief.append(f"{label} has {len(posts)} posts; the plan allows up to {ppw[1]}.")
            if len(present) < ppw[0]:
                if hol:
                    checks.append(f"{label}: minimum post count not applied (public holiday week)")
                else:
                    brief.append(f"{label} has {len(present)} post(s); the plan baseline is {ppw[0]}.")
        for word in nrw:
            same = [r for r in posts if re.search(r"\b" + re.escape(word) + r"\b", r.get("Content type", "") or "", re.I)]
            checks.append(f"{label}: one {word} a week")
            if len(same) > 1:
                ids = ", ".join(r.get("Row ID", "") for r in same)
                for r in same[1:]:
                    note(r, f"{label} has more than one {word} ({ids}); the plan allows one a week. {who} to move one or change its type.")
        if rot and wd_index(rot.get("weekday")) is not None and rot.get("types"):
            rd = wd_index(rot["weekday"])
            checks.append(f"{label}: {FULL[rd]} rotation")
            for r in posts:
                ct = r.get("Content type", "") or ""
                if r["_date"].weekday() == rd and not proof_kind(ct) and not teaser.search(ct) and r.get("Row ID") not in known \
                        and not any(t.lower() in ct.lower() for t in rot["types"]):
                    note(r, f"The {FULL[rd]} slot rotates {', '.join(rot['types'])}; this row is {ct}. {who} to confirm.")

        # Public holidays.
        if hol:
            checks.append(f"{label}: public holidays ({market})")
            names = ", ".join(f"{n} ({fmt(d)})" for d, n in sorted(hol.items()))
            brief.append(f"{label} includes {market} public holidays: {names}. The plan rules say how holiday weeks run.")
            for r in active:
                if r["_date"] in hol:
                    note(r, f"{fmt(r['_date'])} is {hol[r['_date']]} ({market} public holiday). {who} to confirm the date or move the post.")

    # Dated dependencies.
    for dep in plan_cfg.get("dependencies") or []:
        fid = (dep.get("fact_id") or "").upper()
        lab = dep.get("label") or f"fact {fid}"
        if fstat.get(fid) in approved_vals:
            continue
        mt = (dep.get("milestone_type") or "").strip().lower()
        if mt and mt in mtypes:
            checks.append(f"Dependency: {lab} (fact {fid}) lifted by a confirmed {dep.get('milestone_type')} milestone")
            continue
        try:
            deadline = date.fromisoformat(dep.get("deadline"))
        except (TypeError, ValueError):
            deadline = None
        checks.append(f"Dependency: {lab} (fact {fid})")
        dep_rows = [r for r in cal if r["_date"] and r["_date"] >= as_of and r.get("Status") == st["Planned"] and depends(r, dep)
                    and not hold_lifted_in_notes(r, lift_word)]
        if deadline and as_of >= deadline:
            for r in dep_rows:
                if r["_week"] in weeks:
                    note(r, f"The {lab} (fact {fid}) is still not approved after the {fmt(deadline)} deadline, so this row cannot run as planned.",
                         missing=f"{who} to confirm the {lab} (fact {fid}), or approve the proposed swap.", kind_="dependency_swap")
        if deadline and as_of >= deadline - timedelta(days=7) and dep_rows:
            ids = ", ".join(r.get("Row ID", "") for r in dep_rows)
            state = f"the {fmt(deadline)} deadline has passed" if as_of >= deadline else f"the deadline is {fmt(deadline)}"
            brief.append(f"The {lab} (fact {fid}) is not approved and {state}. Dependent rows: {ids}. {who} to decide.")

    # Conditional swap notes whose blog date no longer matches the blog row.
    checks.append("Conditional swap dates")
    for r in cal:
        if r.get("Status") in off_plan or not r["_date"] or r["_date"] < as_of:
            continue
        for m in COND.finditer(r.get("Notes", "") or ""):
            name, when = m.group(1).strip(), parse_date(m.group(2))
            blog = next((b for b in cal if is_blog(b) and b.get("Status") not in off_plan
                         and blog_id.search(b.get("Content type", "")).group(1).lower() == name.lower()), None)
            if blog and blog["_date"] and when and blog["_date"] != when:
                note(r, f"The conditional swap note names {fmt(when)}, but {name} ({blog.get('Row ID')}) is now dated {fmt(blog['_date'])}. "
                        f"{who} to confirm; the note needs the new date.", kind_="conditional_swap_date")

    # Proof lined up ahead: slots 15 to 28 days out with no item of that type logged.
    if proof is not None and len(proof) > 0:
        ph = [h.strip().lower() for h in proof[0]]
        def ci(name, dflt):
            return next((i for i, h in enumerate(ph) if h.startswith(name)), dflt)
        i_t, i_s, i_u = ci("type", 1), ci("sign-off status", 6), ci("used in calendar row", 9)
        logged = {k.lower(): 0 for k in proof_types}
        for r in proof[1:]:
            r = list(r) + [""] * len(ph)
            t = r[i_t].strip().lower()
            if t in logged and r[i_s].strip().lower() in ("yes", "pending") and not r[i_u].strip():
                logged[t] += 1
        for r in in_scope:
            k = proof_kind(r.get("Content type"))
            if k and r.get("Status") == st["Planned"] and not r.get("Proof item") and 15 <= (r["_date"] - as_of).days <= 28 \
                    and logged.get(k.lower(), 0) == 0:
                brief.append(f"{r.get('Row ID')} ({fmt(r['_date'])}): no {proof_types[k]} item is logged yet, signed off or pending. "
                             f"{who} to line one up now.")

    # Cancelled milestones: list their remaining rows once.
    cancelled_ms = []
    if milestones:
        mh = [h.strip().lower() for h in milestones[0]]
        i_name = mh.index("milestone") if "milestone" in mh else 0
        i_conf = mh.index("confirmed") if "confirmed" in mh else 4
        for m in milestones[1:]:
            m = list(m) + [""] * len(mh)
            name = m[i_name].strip()
            if not name or m[i_conf].strip().lower() != "cancelled":
                continue
            short = re.split(r":|,| \(", name)[0].strip().lower()
            tied = []
            for r in cal:
                if r.get("Status") not in (st["Proposed"], st["Planned"], st["Draft ready"], st["Approved"]) or not r["_date"] or r["_date"] < as_of:
                    continue
                tag_hit = f"milestone: {name.lower()}" in (r.get("Notes", "") or "").lower()
                title_hit = len(short) >= 4 and short in (r.get("Title / angle", "") or "").lower()
                if tag_hit or title_hit:
                    tied.append({"row": r["_row"], "row_id": r.get("Row ID", ""), "date": fmt(r["_date"]),
                                 "status": r.get("Status", ""), "match": "tag" if tag_hit else "title"})
            checks.append(f"Cancelled milestone: {name}")
            cancelled_ms.append({"milestone": name, "rows": tied})
            if tied:
                ids = ", ".join(f"{t['row_id']} ({t['date']}, {t['status']})" for t in tied)
                brief.append(f"Milestone \"{name}\" is Cancelled. Its rows are still on the calendar: {ids}. "
                             f"{who} to set them to Cancelled in one go, or keep any that should stay.")

    # Dated events first: an event with a fixed date takes its day over an unconnected blog pair.
    precedence = []
    if (plan_cfg.get("precedence") or "dated_events_first") == "dated_events_first":
        ev_rx = re.compile(plan_cfg.get("dated_event_regex") or r"\bevent\b|\bwebinar\b", re.I)

        def is_event(r):
            ct = r.get("Content type", "") or ""
            return bool(ev_rx.search(ct)) and not is_blog(r) and not teaser.search(ct)
        busy = (st["Cancelled"], st["Backlog"], st["Proposed"])
        events = [r for r in cal if r["_date"] and r["_date"] >= as_of and is_event(r) and r.get("Status") not in busy]
        taken = {r["_date"] for r in cal if r["_date"] and r.get("Status") not in off_plan and (is_blog(r) or is_event(r))}
        for ev in sorted(events, key=lambda x: x["_date"]):
            evtxt = ((ev.get("Title / angle") or "") + " " + (ev.get("Notes") or "")).lower()
            ms = re.search(r"milestone: ([^.]+)\.", evtxt)
            pair = [r for r in cal if r["_date"] == ev["_date"] and (is_blog(r) or teaser.search(r.get("Content type", "") or ""))
                    and r.get("Status") not in off_plan + (st["Posted"],)]
            moving = []
            for r in pair:
                title = (r.get("Title / angle") or "").lower()
                rtxt = title + " " + (r.get("Notes") or "").lower()
                ev_id = (ev.get("Row ID") or "").lower()
                linked = bool((len(title) >= 10 and title[:20] in evtxt) or (ev_id and ev_id in rtxt)
                              or (ms and f"milestone: {ms.group(1)}." in rtxt))
                if not linked:
                    moving.append(r)
            if not moving:
                continue
            nd = ev["_date"] + timedelta(days=7)
            while nd in taken:
                nd += timedelta(days=7)
            taken.add(nd)
            for r in moving:
                if r.get("Row ID") in known:
                    continue
                precedence.append({"row": r["_row"], "row_id": r.get("Row ID", ""), "from": fmt(r["_date"]), "to": nd.isoformat(),
                                   "event": ev.get("Row ID", ""),
                                   "note": f"Moved from {fmt(r['_date'])} to {fmt(nd)}: {ev.get('Row ID', '')} "
                                           f"({(ev.get('Title / angle') or '')[:60]}) takes that day (dated events first)."})
        checks.append("Dated events first")

    print(json.dumps({"as_of": fmt(as_of), "weeks": [iso_no(m) for m in weeks], "holiday_market": market or None,
                      "row_notes": row_notes, "brief_risks": brief, "checks_run": checks, "notes": notes_out,
                      "cancelled_milestones": cancelled_ms, "precedence_moves": precedence}, indent=2, ensure_ascii=False))
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
    if not _usage_ok(sys.argv, 2):
        sys.exit(2)
    sys.exit(main(sys.argv))
