#!/usr/bin/env python3
"""Mechanical checks for a LinkedIn draft, using the client's rules from workspace.json.

Usage:
  python3 check_draft.py draft.json --config workspace.json [--facts facts.json]
      [--person-items person_items.json] [--milestones milestones.json] [--row row.json]

draft.json:
{
  "post": "full post text, hashtags included",
  "first_comment": "optional text of the first comment",
  "type": "post | founder | poll | video",
  "poll_question": "poll only",
  "poll_options": ["poll only", "..."]
}

workspace.json: the client config. Every client rule comes from its "writing" section
(competitors, avoid_terms, spelling US or UK, spelling_allow, units metric or imperial,
word_count, opening_max_words, hashtags, link_in_first_comment, date_words_warn,
custom_rules, on_hold_topics, emoji, no_em_dash), company.people_first_mention,
plan.dependencies (milestone_type per fact_id), requests.hold_lift_word (default
"CONFIRMED") and facts.* column names. A missing optional key skips that check.
Exceptions: em dashes fail unless no_em_dash is false, links in the body fail unless
link_in_first_comment is false, and a missing date_words_warn uses a built-in launch and
availability word list.

facts.json (optional): the facts sheet, either {"values": [[headers], ...]} with the column
names from the config's "facts" section, or a list of objects ({"id","claim"} as in
facts_approved.json). Approved claims are figure sources.
person_items.json (optional): facts the approver gave in Notes or on the Ideas tab (the
"From the approver's notes" tab), a list of objects. Each counts as approved for drafting and
as a figure source. It never authorizes a name.
milestones.json (optional): the Milestones tab ({"values": ...}, headers include Type and
Confirmed).
row.json (optional): the calendar row being drafted (an object with the calendar headers).
When a file is not given, the script looks for person_items.json, milestones.json, row.json,
facts_approved.json and facts.json in the draft's folder (the bundle convention).

Holds: a topic in writing.on_hold_topics is on hold unless one of these lifts it:
- its fact_id is approved in the facts file;
- a Milestones row whose Type is the topic's milestone_type (on the topic, or on the
  plan.dependencies entry with the same fact_id) has Confirmed Yes;
- the row is about the topic and its Notes hold the hold-lift word (CONFIRMED) with a date.
Without any of these files, every on-hold topic is treated as on hold.

Built-in generic checks: em dash, en dash used as a dash, links in the body, poll limits
(question 140 characters, 2 to 4 options of 30 characters), figures (warning unless the
figure is in an approved claim or a person item; "2" and "02" are the same number; text in
[square brackets] is a gap, not a figure), [bracketed] gaps (warning: list each in What's
missing and fill it before Approved).

Prints a JSON report. Exit code 1 if any check fails, 2 on a usage error.
Fails break a hard rule. Warnings need the drafter or a person to confirm.
This script does not judge claims against the facts sheet; the drafter and the
compliance checker do that.
"""
import json
import os
import re
import sys

# Spelling: the pattern list for the variety that is NOT allowed.
UK_SPELLINGS = [  # failed when writing.spelling is US
    r"\bcolour(s|ed|ful|ing)?\b", r"\bcentre(s|d)?\b", r"\borganis\w*", r"\banalys(e|ed|es|ing)\b",
    r"\boptimis\w*", r"\bprioritis\w*", r"\brecognis\w*", r"\bminimis\w*", r"\bmaximis\w*",
    r"\bstandardis\w*", r"\bsummaris\w*", r"\bcustomis\w*", r"\bauthoris\w*", r"\butilis\w*",
    r"\brealis(e|es|ed|ing)\b", r"\bbehaviour\w*", r"\bfavour\w*", r"\blabour\b", r"\bdefence\b",
    r"\bcatalogue\b", r"\bgrey\b", r"\baluminium\b", r"\bfulfil\b", r"\btravelled\b",
    r"\bmodelling\b", r"\blitre(s)?\b", r"\bmetre(s)?\b", r"\bcentimetre\w*", r"\bkilometre\w*",
    r"\bmillimetre\w*", r"\bprogramme(s)?\b", r"\benrol(s|ment)?\b", r"\bjudgement\b",
    r"\bpractise(s|d)?\b", r"\bhumour\w*", r"\bneighbour\w*", r"\bhonour\w*", r"\bspelt\b",
    r"\bwhilst\b", r"\bamongst\b", r"\bcheque\b", r"\btyre(s)?\b",
]
US_SPELLINGS = [  # failed when writing.spelling is UK
    r"\bcolor(s|ed|ful|ing)?\b", r"\bcenter(s|ed)?\b", r"\borganiz\w*", r"\banalyz(e|ed|es|ing)\b",
    r"\boptimiz\w*", r"\bprioritiz\w*", r"\brecogniz\w*", r"\bminimiz\w*", r"\bmaximiz\w*",
    r"\bstandardiz\w*", r"\bsummariz\w*", r"\bcustomiz\w*", r"\bauthoriz\w*", r"\butiliz\w*",
    r"\brealiz(e|es|ed|ing)\b", r"\bbehavior\w*", r"\bfavor\w*", r"\blabor\b", r"\bdefense\b",
    r"\bcatalog\b", r"\bgray\b", r"\baluminum\b", r"\bfulfill\b", r"\btraveled\b",
    r"\bmodeling\b", r"\bliter(s)?\b", r"\bcentimeter\w*", r"\bkilometer\w*", r"\bmillimeter\w*",
    r"\benrollment\b", r"\bhumor\w*", r"\bneighbor\w*", r"\bhonor\w*",
]

# Units: the pattern list for the system that is NOT allowed. (pattern, level)
IMPERIAL = [  # failed when writing.units is metric
    (r"\bmiles?\b", "fail"), (r"\bfeet\b", "fail"), (r"\d+\s*ft\b", "fail"), (r"\binch(es)?\b", "fail"),
    (r"\d+\s*lbs?\b", "fail"), (r"°\s*f\b", "fail"), (r"\bfahrenheit\b", "fail"), (r"\bmph\b", "fail"),
    (r"\bgallons?\b", "fail"), (r"\bounces?\b", "fail"), (r"\d+\s*oz\b", "fail"), (r"\byards?\b", "fail"),
    (r"\bsquare feet\b|\bsq\.? ?ft\b", "fail"), (r"\d+\s*pounds?\b(?! sterling)", "warn"),
]
METRIC = [  # failed when writing.units is imperial
    (r"\d+\s*(km|kg|cm|mm|ml|kwh/m2)\b", "fail"), (r"\bkilomet(er|re)s?\b", "fail"),
    (r"\bkilograms?\b", "fail"), (r"\bcentimet(er|re)s?\b", "fail"), (r"\bmillimet(er|re)s?\b", "fail"),
    (r"\blit(er|re)s?\b", "fail"), (r"°\s*c\b", "fail"), (r"\bcelsius\b", "fail"), (r"\bkm/h\b", "fail"),
    (r"\bsquare met(er|re)s?\b", "fail"),
]

DEFAULT_DATE_WORDS = ["launch", "available", "availability", "shipping", "ships", "pre-order",
                      "preorder", "in stock", "delivery", "deliveries", "general availability",
                      "goes on sale"]
QUARTER = r"\bq[1-4]\s*20\d\d\b"

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF"
    "\U00002B00-\U00002BFF\U0000FE0F]"
)
LINK = r"https?://|www\."


def words(text):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-\.%]*", text)


def body_without_hashtags(post):
    lines = post.rstrip().split("\n")
    while lines and (lines[-1].strip() == "" or all(t.startswith("#") for t in lines[-1].split())):
        lines.pop()
    return "\n".join(lines)


def term_re(term):
    return r"(?<![\w-])" + re.escape(term.lower()) + r"(?![\w-])"


def safe_search(pattern, text, flags=re.I):
    try:
        return re.search(pattern, text, flags)
    except re.error:
        return None


def load_rows(data):
    """Return a list of dicts from {"values": [...]}, a bare values list or a list of objects."""
    if isinstance(data, dict):
        data = data.get("values", [])
    if not data:
        return []
    if isinstance(data[0], dict):
        return data
    hdr = [str(h) for h in data[0]]
    return [dict(zip(hdr, list(r) + [""] * (len(hdr) - len(r)))) for r in data[1:]]


def approved_facts(facts_rows, cfg):
    """Return (ids, claims text) of approved facts."""
    fc = cfg.get("facts", {}) or {}
    id_col = fc.get("id_col", "ID")
    status_col = fc.get("status_col", "Status")
    claim_col = fc.get("claim_col", "Claim")
    ok = {v.strip().lower() for v in fc.get("approved_values", ["Approved", "Approved with edits"])}
    ids, claims = set(), []
    for r in facts_rows:
        fid = str(r.get(id_col, r.get("id", ""))).strip()
        if not fid:
            continue
        status = r.get(status_col, r.get("status"))
        if status is None or str(status).strip().lower() in ok:
            # A row with no status column is from facts_approved.json: approved by definition.
            ids.add(fid)
            claims.append(str(r.get(claim_col, r.get("claim", ""))))
    return ids, " ".join(claims)


def approved_fact_ids(facts_rows, cfg):
    return approved_facts(facts_rows, cfg)[0]


NUM_RE = re.compile(r"(?<![\w.:/])[$£€]?\s?\d+(?:[.,]\d+)*\s*(?:%|x\b)?(?![\w:/])")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
DATE_RE = re.compile(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(?:\s+\d{2,4})?\b"
                     r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", re.I)
GAP_RE = re.compile(r"\[[^\]]{2,120}\]")


def norm_num(tok):
    """'02' and '2' are the same number; commas, spaces and currency signs are ignored."""
    t = re.sub(r"[,\s+$£€]", "", tok).lower()
    if re.fullmatch(r"\d+", t):
        return t.lstrip("0") or "0"
    m = re.fullmatch(r"(\d+)(.*)", t)
    return (m.group(1).lstrip("0") or "0") + m.group(2) if m else t


def figures_in(text):
    """Number tokens in text, leaving out [gaps], hashtags, times and dates."""
    text = GAP_RE.sub(" ", text)
    text = re.sub(r"#\w+", " ", text)
    text = TIME_RE.sub(" ", text)
    text = DATE_RE.sub(" ", text)
    return [m.group(0).strip() for m in NUM_RE.finditer(text)]


def is_figure(tok):
    """A figure worth tracing: a percentage, multiple, money, or a number other than 0 to 9.
    Years (1900 to 2099) are left to the date checks."""
    if re.search(r"%|x$|[$£€]", tok):
        return True
    t = re.sub(r"[,\s]", "", tok)
    if re.fullmatch(r"(19|20)\d\d", t):
        return False
    return not re.fullmatch(r"0*\d", t)


def topic_milestone_type(topic, cfg):
    if topic.get("milestone_type"):
        return str(topic["milestone_type"])
    fid = topic.get("fact_id")
    for dep in ((cfg.get("plan", {}) or {}).get("dependencies") or []):
        if fid and dep.get("fact_id") == fid and dep.get("milestone_type"):
            return str(dep["milestone_type"])
    return ""


def milestone_confirmed(milestones, mtype):
    if not mtype:
        return False
    for m in milestones or []:
        if str(m.get("Type", "")).strip().lower() == mtype.strip().lower() \
                and str(m.get("Confirmed", "")).strip().lower() == "yes":
            return True
    return False


def notes_lift(row, topic, cfg):
    """The row is about the topic and its Notes hold the hold-lift word with a date."""
    if not row:
        return False
    word = str((cfg.get("requests", {}) or {}).get("hold_lift_word") or "CONFIRMED")
    notes = str(row.get("Notes", ""))
    about = " ".join(str(row.get(k, "")) for k in ("Content type", "Title / angle", "What to post", "Notes"))
    if not topic.get("regex") or not safe_search(topic["regex"], about):
        return False
    for line in re.split(r"(?<=[.!?])\s+|\n", notes):
        if re.search(r"\b" + re.escape(word) + r"\b", line) and DATE_RE.search(line):
            return True
    return False


def check(d, cfg, facts_ids, facts_claims="", person_items=None, milestones=None, row=None):
    w = cfg.get("writing", {}) or {}
    company = cfg.get("company", {}) or {}
    post = d.get("post", "") or ""
    comment = d.get("first_comment", "") or ""
    kind = d.get("type", "post") or "post"
    low = post.lower()
    both = low + "\n" + comment.lower()
    fails, warns = [], []

    # Word count.
    body = body_without_hashtags(post)
    wc = len(words(body))
    counts = w.get("word_count") or {}
    rng = counts.get(kind) or (counts.get("post") if kind == "video" else None)
    if rng and len(rng) == 2:
        lo, hi = rng
        if wc < lo or wc > hi:
            fails.append(f"Word count {wc} (body, hashtags excluded); must be {lo} to {hi}.")

    # Opening.
    first = next((l for l in post.split("\n") if l.strip()), "")
    first_sentence = re.split(r"(?<=[.?!:])\s", first.strip())[0]
    omax = w.get("opening_max_words")
    if omax and len(words(first_sentence)) >= omax:
        fails.append(f"Opening sentence has {len(words(first_sentence))} words; must be under {omax}.")
    if len(first) > 140:
        warns.append(f"Opening line is {len(first)} characters; LinkedIn may cut it before 'more' (about 140).")

    # Punctuation and emoji.
    if w.get("no_em_dash", True) is not False and ("\u2014" in post or "\u2014" in comment):
        fails.append("Em dash found. Use a comma, colon or period.")
    if re.search(r"\s–\s", post + "\n" + comment):
        fails.append("En dash used as a dash. Use a comma, colon or period.")
    if w.get("emoji") is False and (EMOJI.search(post) or EMOJI.search(comment)):
        fails.append("Emoji found.")
    if "!" in post:
        warns.append("Exclamation mark found: only for rare celebratory posts.")

    # Names and terms.
    for c in w.get("competitors") or []:
        if c and re.search(term_re(c), both):
            fails.append(f"Company name '{c}' found. Never name a competitor or consumer brand.")
    for a in w.get("avoid_terms") or []:
        if a and re.search(term_re(a), both):
            fails.append(f"Avoid-list term '{a}'.")

    # Spelling.
    variety = str(w.get("spelling") or "").upper()
    allow = [s.lower() for s in (w.get("spelling_allow") or [])]
    bad = UK_SPELLINGS if variety == "US" else US_SPELLINGS if variety == "UK" else []
    want = "US" if variety == "US" else "UK"
    seen = set()
    for p in bad:
        for m in re.finditer(p, both):
            word = m.group(0)
            if word in seen or any(word in a for a in allow):
                continue
            seen.add(word)
            fails.append(f"Spelling '{word}' is not {want} spelling.")

    # Units.
    system = str(w.get("units") or "").lower()
    unit_list = IMPERIAL if system == "metric" else METRIC if system == "imperial" else []
    for p, level in unit_list:
        m = re.search(p, both)
        if m:
            msg = f"Unit '{m.group(0).strip()}' found; use {system} units."
            (fails if level == "fail" else warns).append(msg if level == "fail" else msg + " Confirm it is not a weight.")

    # Dates that suggest a launch, availability or delivery.
    date_words = w.get("date_words_warn")
    if date_words is None:
        date_words = DEFAULT_DATE_WORDS
    for dw in date_words:
        m = re.search(r"\b" + re.escape(dw.lower()) + r"\w*", both)
        if m:
            warns.append(f"'{m.group(0)}' found: no launch, availability or delivery dates. Confirm it is not a product date.")
    m = re.search(QUARTER, both)
    if m:
        warns.append(f"'{m.group(0)}' found: no launch, availability or delivery dates. Confirm it is not a product date.")

    # Client claim rules.
    for r in w.get("custom_rules") or []:
        pat = r.get("regex")
        if not pat or not safe_search(pat, post + "\n" + comment):
            continue
        if r.get("unless_regex") and safe_search(r["unless_regex"], post + "\n" + comment):
            continue
        msg = f"{r.get('id', 'Rule')}: {r.get('message', 'custom rule matched.')}"
        (warns if str(r.get("level", "fail")).lower() == "warn" else fails).append(msg)

    # On-hold topics.
    for t in w.get("on_hold_topics") or []:
        pat = t.get("regex")
        if not pat or not safe_search(pat, post + "\n" + comment):
            continue
        fid = t.get("fact_id")
        if fid and facts_ids is not None and fid in facts_ids:
            continue  # fact approved: topic no longer on hold
        if milestone_confirmed(milestones, topic_milestone_type(t, cfg)):
            continue  # the dependency's milestone has Confirmed Yes
        if notes_lift(row, t, cfg):
            continue  # a person wrote CONFIRMED with a date in Notes
        fails.append(t.get("message") or "Topic mentioned while it is on hold.")

    # Figures. Text in [square brackets] is a gap, not a figure. Approved claims and person
    # items are figure sources; "2" and "02" are the same number.
    trace = facts_claims or ""
    if person_items:
        trace += " " + json.dumps(person_items, ensure_ascii=False)
    trace_nums = {norm_num(t) for t in figures_in(trace)}
    seen_fig = set()
    for tok in figures_in(post):
        if not is_figure(tok) or norm_num(tok) in trace_nums or norm_num(tok) in seen_fig:
            continue
        seen_fig.add(norm_num(tok))
        warns.append(f"Figure found: '{tok}' is not in an approved fact or person item. It must map to an "
                     "approved fact with a traceable reference, and the source must be named.")

    # Gaps in a base draft.
    gaps = GAP_RE.findall(post + "\n" + comment)
    if gaps:
        warns.append("Base draft with gaps: " + ", ".join(dict.fromkeys(gaps)) +
                     ". List each in What's missing; a person fills them before Approved.")

    # Links.
    if re.search(LINK, post) and w.get("link_in_first_comment", True) is not False:
        fails.append("Link in the post body. External links go in the first comment.")
    if w.get("link_in_first_comment") and re.search(LINK, comment) and "first comment" not in low:
        fails.append("First comment has a link but the post does not say 'Link in the first comment'.")

    # First mention of people.
    pfm = company.get("people_first_mention") or w.get("people_first_mention") or {}
    for key, full in pfm.items():
        # Another person with the same first name (written with a different surname) does not count.
        nxt = re.match(re.escape(key) + r"\s+([A-Z][\w'\-]+)", full)
        own_surname = nxt.group(1) if nxt else None
        m = None
        for c in re.finditer(r"\b" + re.escape(key) + r"\b", post):
            after = re.match(r"\s+([A-Z][\w'\-]+)", post[c.end():])
            if after and after.group(1) != own_surname:
                continue
            m = c
            break
        if not m:
            continue
        i = post.find(full)
        if i < 0 or not (i <= m.start() < i + len(full)):
            fails.append(f"First mention of {key} must be '{full}'.")

    # Hashtags.
    h = w.get("hashtags") or {}
    tags = re.findall(r"#\w+", post)
    tail = post.rstrip().split("\n")[-1] if post.strip() else ""
    tail_tags = re.findall(r"#\w+", tail)
    hmin, hmax = h.get("min"), h.get("max")
    if hmin is not None or hmax is not None:
        lo, hi = hmin or 0, hmax if hmax is not None else 99
        if not (lo <= len(tail_tags) <= hi):
            fails.append(f"{len(tail_tags)} hashtags on the last line; need {lo} to {hi} at the end.")
    tags_low = {t.lower() for t in tags}
    for req in h.get("required") or []:
        if req.lower() not in tags_low:
            fails.append(f"Missing {req}.")
    if tags and len(tags) != len(tail_tags):
        warns.append("Hashtags found inside the body; keep them at the end.")
    for c in h.get("conditional") or []:
        if c.get("tag") and c.get("if_regex") and safe_search(c["if_regex"], body) \
                and c["tag"].lower() not in tags_low:
            warns.append(f"Post matches '{c['if_regex']}': add {c['tag']}.")

    # Polls.
    if kind == "poll":
        q = d.get("poll_question", "") or ""
        opts = d.get("poll_options", []) or []
        if not q or len(q) > 140:
            fails.append("Poll question missing or over 140 characters.")
        if not (2 <= len(opts) <= 4):
            fails.append("Poll needs 2 to 4 options.")
        for o in opts:
            if len(o) > 30:
                fails.append(f"Poll option over 30 characters: '{o}'.")

    return {"word_count": wc, "pass": not fails, "fails": fails, "warnings": warns}


def arg_value(argv, flag):
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bundle_file(argv, flag, folder, names):
    p = arg_value(argv, flag)
    if p:
        return p
    for n in names:
        q = os.path.join(folder, n)
        if os.path.exists(q):
            return q
    return None


def main(argv):
    d = load_json(argv[1])
    cfg = load_json(arg_value(argv, "--config"))
    folder = os.path.dirname(os.path.abspath(argv[1]))
    facts_ids, claims = None, ""
    fp = bundle_file(argv, "--facts", folder, ("facts_approved.json", "facts.json"))
    if fp:
        facts_ids, claims = approved_facts(load_rows(load_json(fp)), cfg)
    pp = bundle_file(argv, "--person-items", folder, ("person_items.json",))
    person = load_json(pp) if pp else None
    mp = bundle_file(argv, "--milestones", folder, ("milestones.json",))
    miles = load_rows(load_json(mp)) if mp else None
    rp = bundle_file(argv, "--row", folder, ("row.json",))
    row = load_json(rp) if rp else None
    if isinstance(row, dict) and "values" in row:
        rows = load_rows(row)
        row = rows[0] if rows else None
    report = check(d, cfg, facts_ids, claims, person, miles, row)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["pass"] else 1


def _usage_ok(argv, n, required=("--config",)):
    """Print the usage message instead of a traceback when arguments are missing."""
    flags_no_value = {"--shadow", "--live", "--help", "-h"}
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
    if not _usage_ok(sys.argv, 1):
        sys.exit(2)
    sys.exit(main(sys.argv))
