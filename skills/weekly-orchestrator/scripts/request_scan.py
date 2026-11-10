#!/usr/bin/env python3
"""Find what people have asked for in plain words, so the run does it (weekly orchestrator).

Usage:
  python3 request_scan.py calendar.json [--config workspace.json] [--ideas ideas.json] [--as-of YYYY-MM-DD]
                          [--days 91] [--back 14]

calendar.json: the Calendar table {"values": [[headers], [row 2], ...]} saved exactly as returned.
ideas.json:    the Ideas tab A1:H, saved the same way.

Prints {"notes_asks": [...], "open_asks": N, "ideas": [...]}. It writes nothing.

notes_asks: for each Calendar row dated from --back days ago to --days ahead (not Posted, Cancelled or
  Backlog), every part of Notes an agent did not write. There are no set phrases: any plain sentence a
  person wrote ("Can we move this to Friday?", "Make this about heat pumps instead.") is an ask.
  Agent text is a segment that starts with an agent prefix ("<notes.agent_prefix> 03 NOV 26:", or a role
  name such as "Planner 03 NOV 26:") and runs to the next prefix. Everything else is a person's.
  Each item has:
    kind      "ask"        a plain-language request: the main session decides what it means and acts
              "hold_lift"  the hold lift word (requests.hold_lift_word, default CONFIRMED) with a date:
                           the hold on this row is lifted; "lift_date" is the date read (dates.typed_order)
              "standing"   "On hold (...)", or a signed, dated decision ("Sam Ortega, 14 MAR 26: ...") already
                           handled: keep following it. A signed line not yet handled is an "ask".
              "info"       a link a person added (for example a published blog link): use it, no row change
              "possible_ask" a question or "please" sentence inside an agent segment: a person may have
                           typed after an agent line with no prefix. Read it and judge.
    handled   true when a later agent segment on the row (or a Notes line naming "<Row ID> Notes"
              elsewhere) says "as asked".
    from      the name in a signed line ("Priya Nair, 12 MAR 26: ..."), else "" (unsigned Notes text is
              treated as the approver's)
    accepted  false when requests.from does not include who wrote it (team members, when only the
              approver's asks count). The main session lists those in the brief instead of acting.
  Builder boilerplate the calendar builder writes without a prefix ("The team writes this; agents do
  not draft it.", "From Ideas tab: ...") is ignored.
ideas: Ideas rows with Idea filled and Status blank or New, with "accepted" as above.

Config (all optional): notes.agent_prefix (Agents), requests.enabled (true), requests.from (["approver"];
  add "team" to accept asks from company.people), requests.hold_lift_word (CONFIRMED),
  company.approver.name, company.people, calendar.statuses, calendar.tabs, dates.typed_order (day_first).
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROLES = ["Planner", "Orchestrator", "Proof intake", "Drafter", "Calendar builder", "Checker", "Agents"]
DATE_PART = r"\d{1,2} [A-Za-z]{3} \d\d(?: \([^)]*\))?:"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
CANON = ["Proposed", "Planned", "Draft ready", "Fallback post", "Approved", "Posted", "Cancelled", "Backlog"]
BUILDER = re.compile(r"^(Monthly run|Milestone run|Ideas run|Milestone change run|The team writes this|Team writes this|"
                     r"Agents do not draft it|Agent drafts this once|From Ideas tab:|Milestone: )", re.I)
QUESTION = re.compile(r"(\?\s*$|^\s*(please|pls)\b|\bplease\b)", re.I)

# ---- shared helpers (kept in this file so the script runs alone) ----


def load_config(argv):
    p = argv[argv.index("--config") + 1] if "--config" in argv and argv.index("--config") + 1 < len(argv) else None
    if not p:
        for c in (os.path.join(HERE, "workspace.json"), "workspace.json"):
            if os.path.exists(c):
                p = c
                break
    try:
        return json.load(open(p, encoding="utf-8")) if p else {}
    except (OSError, ValueError):
        return {}


VALUE_FLAGS = {"--config", "--ideas", "--as-of", "--days", "--back", "--log", "--prompts", "--sheet", "--hidden",
               "--cal-sheet", "--bl-sheet"}


def positional(argv):
    """Arguments that are not flags or flag values, in order."""
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
        elif a in VALUE_FLAGS:
            skip = True
        elif not a.startswith("--"):
            out.append(a)
    return out


def cfg_get(cfg, path, default):
    cur = cfg
    for k in path.split("."):
        if not isinstance(cur, dict) or cur.get(k) is None:
            return default
        cur = cur[k]
    return cur


def statuses(cfg):
    """Canonical status -> the label used in this workspace."""
    s = cfg_get(cfg, "calendar.statuses", None)
    if isinstance(s, dict):
        return {k: s.get(k, k) for k in CANON}
    return {k: k for k in CANON}


def agent_names(cfg):
    pre = (cfg_get(cfg, "notes.agent_prefix", "Agents") or "Agents").strip()
    return [pre] + [r for r in ROLES if r != pre]


def agent_re(cfg):
    names = "|".join(re.escape(n) for n in agent_names(cfg))
    return re.compile(r"(?:%s) %s" % (names, DATE_PART))


def any_prefix_re(cfg):
    names = "|".join(re.escape(n) for n in agent_names(cfg))
    return re.compile(r"(?:(?:%s)|[A-Z][a-z]+(?: [A-Z][a-z'\-]+)?,) %s" % (names, DATE_PART))


def load(p):
    try:
        v = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return v.get("values", v) if isinstance(v, dict) else (v or [])


def table(values):
    if not values:
        return []
    hdr = values[0]
    return [{"_row": n, **dict(zip(hdr, list(r) + [""] * (len(hdr) - len(r))))} for n, r in enumerate(values[1:], start=2)]


def year4(y):
    y = int(y)
    return y + 2000 if y < 100 else y


def parse_cell_date(s, order="day_first"):
    s = (s or "").strip()
    for f in ("%a %d %b %y", "%d %b %y", "%Y-%m-%d", "%a %d %b %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s.title() if "%b" in f else s, f).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        d, mo = (b, a) if order == "month_first" else (a, b)
        try:
            return date(year4(m.group(3)), mo, d)
        except ValueError:
            return None
    return None


def person_date(text, as_of, order="day_first"):
    """First date in a person's words. Numeric dates follow dates.typed_order (2/12/26 is 02 DEC 26 day first)."""
    text = text or ""
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?\b", text)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), m.group(3)
        d, mo = (b, a) if order == "month_first" else (a, b)
        try:
            return date(year4(y) if y else as_of.year, mo, d)
        except ValueError:
            pass
    pats = [r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]{3,9})\.?,?\s*(\d{4}|\d{2}(?!\d))?",
            r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4}|\d{2}(?!\d))?"]
    for i, p in enumerate(pats):
        for m in re.finditer(p, text):
            dd, mon = (m.group(1), m.group(2)) if i == 0 else (m.group(2), m.group(1))
            if mon[:3].lower() not in MONTHS:
                continue
            y = m.group(3)
            try:
                dt = date(year4(y) if y else as_of.year, MONTHS[mon[:3].lower()], int(dd))
            except ValueError:
                continue
            return dt if y or dt >= as_of else date(dt.year + 1, dt.month, dt.day)
    return None


def fmt(d):
    return f"{d.day:02d} {d.strftime('%b').upper()} {d.strftime('%y')}"


# ---- notes ----


def split_notes(notes, cfg=None):
    """Return [(is_agent, text)] segments in order. A segment runs from one prefix to the next."""
    cfg = cfg or {}
    notes = notes or ""
    agent, anyp = agent_re(cfg), any_prefix_re(cfg)
    marks = [(m.start(), bool(agent.match(notes, m.start()))) for m in anyp.finditer(notes)]
    segs = []
    first = marks[0][0] if marks else len(notes)
    if notes[:first].strip():
        segs.append((False, notes[:first].strip()))
    for i, (start, is_agent) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(notes)
        segs.append((is_agent, notes[start:end].strip()))
    return segs


def sentences(text):
    return [x for x in re.split(r"(?<=[.!?])\s+", text or "") if x.strip()]


def who_may_ask(cfg):
    """Names whose asks count, lowercased. None means anyone."""
    frm = cfg_get(cfg, "requests.from", ["approver"])
    frm = [frm] if isinstance(frm, str) else list(frm or [])
    if any(str(f).lower() in ("anyone", "all", "*") for f in frm):
        return None
    names = set()
    appr = (cfg_get(cfg, "company.approver.name", "") or "").strip()
    for f in frm:
        f = str(f).strip()
        if f.lower() == "approver":
            if appr:
                names.add(appr.lower())
                names.add(appr.split()[0].lower())
        elif f.lower() == "team":
            for p in cfg_get(cfg, "company.people", []) or []:
                names.add(p.lower())
                names.add(p.split()[0].lower())
        elif f:
            names.add(f.lower())
            names.add(f.split()[0].lower())
    return names


def accepted(name, allowed):
    if allowed is None or not (name or "").strip():
        return True  # unsigned text in Notes is the approver's
    return name.strip().lower() in allowed


def classify(text, cfg, as_of, order, handled):
    word = (cfg_get(cfg, "requests.hold_lift_word", "CONFIRMED") or "").strip()
    signed = re.match(r"^([A-Z][a-z]+(?: [A-Z][a-z'\-]+)?), " + DATE_PART, text)
    body = text[signed.end():] if signed else text
    if word and re.search(r"\b" + re.escape(word) + r"\b", body, re.I):
        d = person_date(body, as_of, order)
        if d:
            return "hold_lift", d
    if re.match(r"^On hold \(", text) or (signed and handled):
        # A hold, or a signed decision already acted on, stays in force. A new signed line is an ask.
        return "standing", None
    if re.search(r"https?://", text) and len(re.sub(r"https?://\S+", "", text).split()) <= 8:
        return "info", None
    return "ask", None


def main(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    order = cfg_get(cfg, "dates.typed_order", "day_first")
    cal = table(load(positional(argv[1:])[0]))
    as_of = date.fromisoformat(argv[argv.index("--as-of") + 1]) if "--as-of" in argv else date.today()
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 91
    back = int(argv[argv.index("--back") + 1]) if "--back" in argv else 14
    out = {"as_of": as_of.isoformat(), "enabled": True, "notes_asks": [], "open_asks": 0, "ideas": []}
    if cfg_get(cfg, "requests.enabled", True) is False:
        out["enabled"] = False
        print(json.dumps(out, indent=2))
        return 0
    allowed = who_may_ask(cfg)
    skip = (st["Posted"], st["Cancelled"], st["Backlog"])
    agent_segs = {id(r): [t for a, t in split_notes(r.get("Notes", ""), cfg) if a] for r in cal}
    for r in cal:
        d = parse_cell_date(r.get("Date"), order)
        if not d or r.get("Status") in skip or not (as_of - timedelta(days=back) <= d <= as_of + timedelta(days=days)):
            continue
        rid = r.get("Row ID", "")
        segs = split_notes(r.get("Notes", ""), cfg)
        elsewhere = " ".join(t for o in cal if o is not r for t in agent_segs[id(o)])
        for i, (is_agent, text) in enumerate(segs):
            later = " ".join(t for a, t in segs[i + 1:] if a)
            handled = bool(re.search(r"\bas asked\b", later, re.I)) or bool(
                rid and re.search(re.escape(f"{rid} Notes") + r".{0,200}?\bas asked\b", elsewhere, re.I))
            base = {"row": r["_row"], "row_id": rid, "date": r.get("Date"), "status": r.get("Status"),
                    "content_type": r.get("Content type")}
            if is_agent:
                # A person may have typed straight after an agent line, without a prefix.
                sents = sentences(text)
                extra = [s for s in sents[1:] if QUESTION.search(s)]
                if extra:
                    out["notes_asks"].append({**base, "ask": " ".join(extra), "kind": "possible_ask",
                                              "handled": handled, "from": "", "accepted": True})
                continue
            allsents = sentences(text)
            if allsents and BUILDER.match(allsents[0].strip()):
                continue  # the builder wrote this whole note (its later sentences carry no prefix)
            sents = [x for x in allsents if not BUILDER.match(x.strip())]
            if not sents:
                continue
            text = " ".join(sents)
            kind, lift = classify(text, cfg, as_of, order, handled)
            signed = re.match(r"^([A-Z][a-z]+(?: [A-Z][a-z'\-]+)?), " + DATE_PART, text)
            name = signed.group(1) if signed else ""
            item = {**base, "ask": text, "kind": kind, "handled": handled, "from": name,
                    "accepted": accepted(name, allowed)}
            if lift:
                item["lift_date"] = fmt(lift)
            out["notes_asks"].append(item)
    out["open_asks"] = sum(1 for a in out["notes_asks"]
                           if not a["handled"] and a["accepted"] and a["kind"] in ("ask", "hold_lift"))
    if "--ideas" in argv:
        rows = table(load(argv[argv.index("--ideas") + 1]))

        def col(r, start):
            for k in r:
                if k.startswith(start):
                    return r.get(k) or ""
            return ""
        for r in rows:
            idea = col(r, "Idea").strip()
            if idea and col(r, "Status").strip() in ("", "New"):
                by = col(r, "Added by").strip()
                out["ideas"].append({"row": r["_row"], "idea": idea, "added_by": by, "date_added": col(r, "Date added"),
                                     "wanted_by": col(r, "Wanted by"), "link": col(r, "Link"),
                                     "accepted": accepted(by, allowed)})
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if not positional(sys.argv[1:]) or "-h" in sys.argv:
        sys.stderr.write(__doc__.strip() + "\n")
        sys.exit(2)
    sys.exit(main(sys.argv))
