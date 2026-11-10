#!/usr/bin/env python3
"""Keep Notes short: move agent lines that are no longer current to the Agent log tab (weekly orchestrator).

Usage:
  python3 notes_tidy.py calendar.json --report [--config workspace.json]
      Rows whose Notes hold agent lines: {"report": [...]}.
  python3 notes_tidy.py calendar.json current.json [--config workspace.json] [--as-of YYYY-MM-DD]
      Builds the tidy writes and the Agent log rows.

calendar.json: the Calendar table {"values": [[headers], ...]} saved exactly as returned.
current.json:  [{"row_id": "W11-02", "current": "Agents 16 MAR 26: <where the row stands now, what is still open>",
                 "reason": "optional: why the older lines moved"}]
  The main session writes "current" for each row it tidies: what the row is now, what is still open
  (carry forward any open issue from the moved lines), and the draft or backup link only if it is not
  already in Draft URL. Plain words, no history.

What stays in Notes, in its original order and word for word: every part a person wrote (anything
without an agent prefix, including signed decisions such as "Sam Ortega, 14 MAR 26: ..." and the
builder's short standard lines, and any question or "please" sentence typed straight after an agent
line), then the newest (notes.agent_lines_kept - 1) older agent lines, then
the one "current" line. A person's words are never dropped: the script checks that every person
segment is still in the new Notes and stops (exit 1) if one is not.
What moves: every other agent segment ("<notes.agent_prefix> DD MMM YY: ...", or a role name such as
"Planner DD MMM YY: ..."), copied word for word to the Agent log tab: Date moved, Row ID, Agent, Text,
Reason moved. Nothing is deleted.

Sources: duplicate entries (split on "; ") are removed, first occurrence kept, in order.

Prints {"writes": [...], "log_rows": [[...]], "log_range": "<Agent log tab>!A<n>:E<m>" (with --log)}.
The writes carry "tidy": true and go through calendar_writes.py plan and its Row ID check like any other write.
Write the log rows to the Agent log tab first, read them back, then the Notes. Writes nothing itself.
Pass --log agent_log.json (the Agent log tab A1:E as returned) to skip lines already logged and get
the next free range.

Config (all optional): notes.agent_prefix (Agents), notes.agent_lines_kept (1), calendar.statuses,
calendar.tabs.agent_log (Agent log).
"""
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from request_scan import (QUESTION, agent_names, cfg_get, fmt, load, load_config, positional,  # noqa: E402
                          sentences, split_notes, statuses, table)


def a1_tab(name):
    return name if re.fullmatch(r"[A-Za-z0-9_]+", name) else "'" + name.replace("'", "''") + "'"


def tidy_notes(notes, current, cfg, kept=1):
    segs = split_notes(notes or "", cfg)
    agent_idx = [i for i, (a, _) in enumerate(segs) if a]
    stay_agent = set(agent_idx[-(kept - 1):]) if kept > 1 and agent_idx else set()
    keep, moved, person = [], [], []
    for i, (a, t) in enumerate(segs):
        if not a or i in stay_agent:
            keep.append(t)
            if not a:
                person.append(t)
            continue
        # A person may have typed a question straight after an agent line, with no prefix: keep it in Notes.
        sents = sentences(t)
        typed = [x for x in sents[1:] if QUESTION.search(x)]
        if typed:
            keep.extend(typed)
            person.extend(typed)
            t = " ".join(x for x in sents if x not in typed)
        moved.append(t)
    new = " ".join(keep + ([current.strip()] if current and current.strip() else []))
    for t in person:  # never drop a person's words
        if t not in new:
            raise ValueError(f"person text would be lost: {t[:60]}")
    return new, moved


def dedupe_sources(src):
    seen, out = set(), []
    for part in [p.strip() for p in (src or "").split(";")]:
        if part and part.lower() not in seen:
            seen.add(part.lower())
            out.append(part)
    return "; ".join(out)


def main(argv):
    cfg = load_config(argv)
    st = statuses(cfg)
    pos = positional(argv[1:])
    rows = table(load(pos[0]))
    names = agent_names(cfg)
    agent_name = re.compile(r"^(%s)\b" % "|".join(re.escape(n) for n in names))
    if "--report" in argv:
        rep = []
        for r in rows:
            segs = split_notes(r.get("Notes", "") or "", cfg)
            n = sum(1 for a, _ in segs if a)
            if n:
                rep.append({"row": r["_row"], "row_id": r.get("Row ID"), "status": r.get("Status"), "agent_lines": n,
                            "notes_chars": len(r.get("Notes", "") or ""),
                            "sources_dupes": dedupe_sources(r.get("Sources", "")) != (r.get("Sources", "") or "").strip()})
        print(json.dumps({"report": rep}, indent=2, ensure_ascii=False))
        return 0
    if len(pos) < 2:
        sys.stderr.write(__doc__.strip() + "\n")
        return 2
    cur = {c["row_id"]: c for c in json.load(open(pos[1], encoding="utf-8"))}
    as_of = date.fromisoformat(argv[argv.index("--as-of") + 1]) if "--as-of" in argv else date.today()
    kept = int(cfg_get(cfg, "notes.agent_lines_kept", 1) or 1)
    log_vals = load(argv[argv.index("--log") + 1]) if "--log" in argv else []
    logged = {(str(r[1]).strip(), str(r[3]).strip()) for r in log_vals[1:] if len(r) > 3}
    writes, log = [], []
    for r in rows:
        c = cur.get(r.get("Row ID"))
        if not c or r.get("Status") in (st["Cancelled"], st["Backlog"]):
            continue
        if not c.get("current", "").strip() or not agent_name.match(c["current"].strip()):
            sys.stderr.write(f"{r.get('Row ID')}: current must start with an agent prefix, "
                             f"for example '{names[0]} {fmt(as_of)}:'.\n")
            return 1
        try:
            new, moved = tidy_notes(r.get("Notes", ""), c["current"], cfg, kept)
        except ValueError as e:
            sys.stderr.write(f"{r.get('Row ID')}: {e}\n")
            return 1
        if new != (r.get("Notes", "") or ""):
            writes.append({"row": r["_row"], "col": "Notes", "value": new, "tidy": True, "by": "orchestrator"})
        for t in moved:
            if (str(r.get("Row ID")), t) in logged:
                continue
            m = agent_name.match(t)
            log.append([fmt(as_of), r.get("Row ID"), m.group(1) if m else "", t,
                        c.get("reason") or "Replaced by the current line in Notes."])
        s2 = dedupe_sources(r.get("Sources", ""))
        if s2 != (r.get("Sources", "") or "").strip():
            writes.append({"row": r["_row"], "col": "Sources", "value": s2, "tidy": True, "by": "orchestrator"})
    out = {"writes": writes, "log_rows": log}
    if "--log" in argv and log:
        first = max(len(log_vals), 1) + 1
        tab = a1_tab(cfg_get(cfg, "calendar.tabs.agent_log", "Agent log"))
        out["log_range"] = f"{tab}!A{first}:E{first + len(log) - 1}"
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3 or not positional(sys.argv[1:]) or "-h" in sys.argv:
        sys.stderr.write(__doc__.strip() + "\n")
        sys.exit(2)
    sys.exit(main(sys.argv))
