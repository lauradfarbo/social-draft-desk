#!/usr/bin/env python3
"""Turn news the approver gave in Notes or on the Ideas tab into new proof log rows.

Usage:
  python3 proof_log_add.py proof_log.json new_items.json --config workspace.json [--as-of YYYY-MM-DD]

Runs only when the config has proof.approver_word_is_signoff set to true. Otherwise it writes
nothing, prints {"refused": ...} and exits 3: the approver's word is not a sign-off for this
client, so agents never add proof log rows. Flag "Log this in the proof log with sign-off" in
What's missing instead.

proof_log.json: the Proof log tab (A1:J) as {"values": [[headers], ...]}, header row first.
new_items.json: what the main session found, one object per piece of news:
  [{"type": "Partner" | "Customer" | "Advisor",   (a key of calendar.proof_types)
    "organization": "Northgate Facilities",   exact public name as written; Advisor: "<person>, <organization>"
    "what_happened": "...",                    the approver's words, nothing added
    "quote": "",                               only a quote given word for word, with who said it
    "source": "W11-02 Notes" | "Ideas row 3",
    "noted": "2026-03-09",                     the date the news was added: the date written in the
                                               note, else Date added on Ideas, else the run date
    "public_from": "",                         only if one was given; blank means the noted date
    "by": "Sam Ortega"}]                       who wrote it (default company.approver.name)

workspace.json: uses proof.approver_word_is_signoff, calendar.proof_types (default Partner,
Customer, Advisor) and company.approver.name.

A plan or a hope ("we expect to sign X") is not news: the main session leaves it out.
The script writes nothing. It prints:
  {"rows": [[A..J values]], "range": "<tab>!A<n>:J<m>", "skipped": [...], "brief_lines": [...],
   "reviewer_notes": {"<organization>": "..."}}
Sign-off status is Yes, Sign-off from is "<by> (<source>)", Logged by is "Agents, from <by>'s
<source>", dates are YYYY-MM-DD. An item already in the log (same Type and Organization, ignoring
case and a "(TEST ...)" tag) is skipped and reported, so the same news is never logged twice.
Rows go below the last filled row; a row a person wrote is never edited. Write the rows with one
update to "range", read them back, then reread the proof log before matching.
Exit codes: 0 done, 2 usage error, 3 refused by the config.
"""
import json
import re
import sys
from datetime import date

DEFAULT_TYPES = ["Partner", "Customer", "Advisor"]
NEEDED = ["Date logged", "Type", "Organization", "What happened", "Approved quote (verbatim)",
          "Sign-off from (name)", "Sign-off status", "Can go public from", "Logged by"]
QUOTE_RE = re.compile(r'^[“"](.+?)[”"]\s*(?:-|–|,|\()\s*(.+?)\)?\s*$', re.S)
TEST_MARK = re.compile(r"\s*\(TEST\b[^)]*\)\s*$", re.I)


def fmt(d):
    return f"{d.day:02d} {d.strftime('%b').upper()} {d.strftime('%y')}"


def load(p):
    with open(p, encoding="utf-8") as f:
        v = json.load(f)
    return v.get("values", v) if isinstance(v, dict) else v


def arg_value(argv, flag):
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def key(t, org):
    return (str(t or "").strip().lower(), TEST_MARK.sub("", str(org or "")).strip().lower())


def main(argv):
    with open(arg_value(argv, "--config"), encoding="utf-8") as f:
        cfg = json.load(f)
    pc = cfg.get("proof", {}) or {}
    if pc.get("approver_word_is_signoff") is not True:
        print(json.dumps({"refused": "proof.approver_word_is_signoff is not true in workspace.json, so agents "
                          "never add proof log rows. Flag 'Log this in the proof log with sign-off' in "
                          "What's missing instead.", "rows": [], "range": ""}, indent=2))
        return 3

    cal = cfg.get("calendar", {}) or {}
    types = {k.strip().lower(): k.strip() for k in (cal.get("proof_types") or {k: k for k in DEFAULT_TYPES})}
    approver = str(((cfg.get("company", {}) or {}).get("approver", {}) or {}).get("name", "")).strip() or "Approver"
    tab = ((cfg.get("sources", {}) or {}).get("proof_log", {}) or {}).get("tab") or "Proof log"

    vals = load(argv[1])
    hdr, rows = [str(h) for h in vals[0]], vals[1:]
    missing = [h for h in NEEDED if h not in hdr]
    if missing:
        sys.stderr.write("Proof log is missing columns: " + ", ".join(missing) + "\n")
        return 2
    col = {h: i for i, h in enumerate(hdr)}
    as_of = date.fromisoformat(arg_value(argv, "--as-of")) if arg_value(argv, "--as-of") else date.today()

    last, have = 1, set()
    for n, r in enumerate(rows, start=2):
        r = list(r) + [""] * (len(hdr) - len(r))
        if any(str(x).strip() for x in r):
            last = n
            have.add(key(r[col["Type"]], r[col["Organization"]]))

    out, skipped, brief, notes = [], [], [], {}
    for it in load(argv[2]):
        t = types.get(str(it.get("type") or "").strip().lower())
        org = str(it.get("organization") or "").strip()
        what = str(it.get("what_happened") or "").strip()
        q = str(it.get("quote") or "").strip()
        why = None
        if not t:
            why = "type must be one of: " + ", ".join(types.values())
        elif not org or not what:
            why = "organization and what_happened are needed"
        elif key(t, org) in have:
            why = "already in the proof log"
        elif q and not QUOTE_RE.match(q):
            why = "quote must be word for word in quotation marks with who said it"
        if not why:
            try:
                noted = date.fromisoformat(it["noted"]) if it.get("noted") else as_of
                pub = date.fromisoformat(it["public_from"]) if it.get("public_from") else noted
            except ValueError:
                why = "noted and public_from must be YYYY-MM-DD"
        if why:
            skipped.append({**it, "reason": why})
            continue
        by = str(it.get("by") or approver).strip()
        src = str(it.get("source") or "").strip()
        row = [""] * len(hdr)
        row[col["Date logged"]] = noted.isoformat()
        row[col["Type"]] = t
        row[col["Organization"]] = org
        row[col["What happened"]] = what
        row[col["Approved quote (verbatim)"]] = q
        row[col["Sign-off from (name)"]] = f"{by} ({src})" if src else by
        row[col["Sign-off status"]] = "Yes"
        row[col["Can go public from"]] = pub.isoformat()
        row[col["Logged by"]] = f"Agents, from {by}'s {src}" if src else f"Agents, from {by}"
        out.append(row)
        have.add(key(t, org))
        where = f" from {by}'s {src}" if src else f" from {by}"
        brief.append(f"Logged {t.lower()} {org} in the proof log{where} ({fmt(noted)}); public from {fmt(pub)}.")
        notes[org] = f"Sign-off: {by}'s word. Confirm {org} is happy to be named before posting."

    first = last + 1
    rng = f"{tab}!A{first}:{chr(ord('A') + len(hdr) - 1)}{first + len(out) - 1}" if out else ""
    print(json.dumps({"rows": out, "range": rng, "skipped": skipped, "brief_lines": brief,
                      "reviewer_notes": notes}, indent=2, ensure_ascii=False))
    return 0


def _usage_ok(argv, n, required=("--config",)):
    """Print the usage message instead of a traceback when arguments are missing."""
    flags_no_value = {"--help", "-h"}
    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a not in flags_no_value
        else:
            pos.append(a)
    missing = [r for r in required if arg_value(argv, r) is None]
    if "-h" in argv or "--help" in argv or len(pos) < n or missing:
        sys.stderr.write((__doc__ or "").strip() + "\n")
        return False
    return True


if __name__ == "__main__":
    if not _usage_ok(sys.argv, 2):
        sys.exit(2)
    sys.exit(main(sys.argv))
