#!/usr/bin/env python3
"""Independent compliance check for one draft (compliance checker).

Usage:
  python3 check_compliance.py draft.json facts.json [--config workspace.json] [--proof proof_item.json]

Run from the check bundle folder: check_draft.py must sit next to this file. It is called with the
same --config and with --facts facts.json; check_draft.py finds person_items.json, milestones.json
and row.json in the same folder (holds and figure sources). When assets.txt and visuals_recent.txt
sit next to this file, assets files are checked for existence and repeats. Without --config,
workspace.json next to this file is used when present.

person_items.json (optional, next to this file): facts the approver gave in Notes or on the Ideas
tab ("From the approver's notes" tab), and Milestones notes for the row. Each is an approved source
for figures. It never authorizes naming a person or company.

Figures: text inside [square-bracket] gaps is a placeholder a person fills before Approved, not a
figure. "2" and "02" are the same number.

draft.json (what the drafter returned, without its reasoning):
{
  "row_id": "W09-04",
  "content_type": "Poll",
  "type": "post | founder | poll | video",
  "post": "full post text, hashtags included",
  "first_comment": "text or empty",
  "alternate_hook": "one line",
  "visual": "Use: <file> (<asset prefix>/<subfolder>) | Needed: <AI image tool> image of <subject>. Prompt in draft tab. | Needed: <real photo or graphic> | None needed (the poll renders itself)",
  "visual_alternatives": ["optional: other Use: lines the orchestrator may switch to"],
  "image_prompt": "required with an AI image visual; expected on every post that may use a generated image",
  "image_alt_prompt": "required with an AI image visual: a different scene, not a reworded copy",
  "poll_question": "poll only",
  "poll_options": ["poll only"],
  "fact_ids": ["A03", "A05"]
}
facts.json: the facts sheet table, header row first (column names from facts.* in the config).
proof_item.json: optional, the proof log row as an object (proof posts only).

Config (workspace.json, all optional): company.name, company.people, company.approver.name,
facts.*, writing.competitors, writing.spelling, writing.custom_rules (ids used as rule labels),
writing.product_timing ({"level": "fail" | "warn" | "off", "regex": optional, "message": optional};
default: fail on a launch, availability or delivery word next to a time reference),
calendar.proof_types, calendar.event_live_regex, visuals.* (no_repeat_weeks, asset_prefix,
ai_image_tool, real_photo_only_regex, product_reference_photo, product_regex, aspect_ratios).

Prints a JSON report: {"pass": bool, "fixes": [...], "warnings": [...]}. Exit 1 on any fix.
Every fix is numbered and says what to change. Warnings need the checker agent's judgment.
This script writes nothing.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VALUE_FLAGS = {"--config", "--proof"}

MONTHS = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
PRODUCT_TIMING = r"(launch\w*|availab\w*|ship\w*|deliver\w*|on sale|pre-?order\w*|in stock|general availability|go(es)? to market|commercial release)"
TIME_REF = re.compile(
    r"(\bq[1-4]\b|\b(early|mid|late|end of)\s+20\d\d\b|\b20\d\d\b|\bnext (year|quarter|month)\b|\bthis (year|quarter)\b|\b" + MONTHS + r"\b|\bsoon\b|\bcoming weeks\b)"
)
NUMBER = re.compile(r"(?<![\w#.])(\$|£|€)?\d[\d,]*(\.\d+)?\s*(%|x\b|\+)?")
USE_RE = re.compile(r"Use:\s*(.+?\.(?:png|jpe?g|gif|webp|mp4|mov|psd|pptx|docx|pdf|md|mp3))\b", re.I)
WRONG_SPELLING = {
    "US": [r"\bcolour", r"\bcentre", r"\borganis", r"\banalys(e|ed|es|ing)\b", r"\boptimis", r"\bbehaviour",
           r"\bfavour", r"\bgrey\b", r"\bmetre", r"\blitre", r"\bprogramme"],
    "UK": [r"\bcolor", r"\bcenter", r"\borganiz", r"\banalyz", r"\boptimiz", r"\bbehavior", r"\bfavor",
           r"\bgray\b", r"\bmeter(s)?\b", r"\bliter(s)?\b"],
}
_STOP = {"a", "an", "the", "of", "in", "on", "at", "with", "and", "for", "to", "wearing", "image", "photo"}


def load_config(argv):
    p = argv[argv.index("--config") + 1] if "--config" in argv and argv.index("--config") + 1 < len(argv) else None
    if not p:
        for c in (os.path.join(HERE, "workspace.json"), "workspace.json"):
            if os.path.exists(c):
                p = c
                break
    return (json.load(open(p, encoding="utf-8")) if p else {}), p


def cfg_get(cfg, path, default):
    cur = cfg
    for k in path.split("."):
        if not isinstance(cur, dict) or cur.get(k) is None:
            return default
        cur = cur[k]
    return cur


def load_facts(path, cfg):
    values = json.load(open(path, encoding="utf-8"))
    values = values.get("values", values) if isinstance(values, dict) else values
    hdr = [h.strip() for h in values[0]]
    low = [h.lower() for h in hdr]

    def col(key, dflt):
        name = cfg_get(cfg, f"facts.{key}", dflt)
        if name in hdr:
            return hdr.index(name)
        return next((i for i, h in enumerate(low) if h.startswith(dflt.lower())), None)
    i_id, i_status, i_claim = col("id_col", "ID"), col("status_col", "Status"), col("claim_col", "Claim")
    facts = {}
    for r in values[1:]:
        r = list(r) + [""] * (len(hdr) - len(r))
        if i_id is not None and r[i_id].strip():
            facts[r[i_id].strip().upper()] = {"status": r[i_status].strip() if i_status is not None else "",
                                              "claim": r[i_claim].strip() if i_claim is not None else ""}
    return facts


def sentences(text):
    body = re.sub(r"\n#.*$", "", text.strip())
    parts = re.split(r"(?<=[.?!:])\s+|\n+", body)
    return [p.strip() for p in parts if p.strip()]


def numbers_in(text):
    out = []
    for m in NUMBER.finditer(text):
        tok = m.group(0).strip()
        start = m.start()
        before = text[max(0, start - 12):start].lower()
        line_start = text.rfind("\n", 0, start) + 1
        # List markers ("1. ") and chapter references are not figures.
        if text[line_start:start].strip() == "" and re.match(r"\d+\.\s", text[start:start + 4]):
            continue
        if re.search(r"(chapter|ch\.?|step|stage|part|week)\s*$", before):
            continue
        tok = tok.rstrip(",.")
        if re.fullmatch(r"(19|20)\d\d", tok):  # years are dates, not figures
            continue
        if tok not in out:
            out.append(tok)
    return out


def norm_num(tok):
    t = re.sub(r"[,\s+]", "", tok).lower()
    return (t.lstrip("0") or "0") if re.fullmatch(r"\d+", t) else t  # "02" and "2" are the same number


def person_text():
    """person_items.json next to this file, as one lower-case string (a figure source)."""
    p = os.path.join(HERE, "person_items.json")
    if not os.path.exists(p):
        return ""
    try:
        return json.dumps(json.load(open(p, encoding="utf-8")), ensure_ascii=False).lower()
    except (ValueError, OSError):
        return ""


def _ddmmmyy(iso):
    try:
        y, m, d = (int(x) for x in iso.split("-"))
    except ValueError:
        return iso
    return f"{d:02d} {['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'][m - 1]} {y % 100:02d}"


def _tokens(s):
    return {w for w in re.findall(r"[a-z]+", (s or "").lower()) if w not in _STOP}


def _similar(a, b):
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.6


def real_photo_regex(cfg):
    rx = cfg_get(cfg, "visuals.real_photo_only_regex", None)
    if rx:
        return re.compile(rx, re.I)
    parts = [re.escape(v) for v in cfg_get(cfg, "calendar.proof_types", {"Partner": "Partner Win", "Customer": "Customer Proof"}).values() if v]
    ev = cfg_get(cfg, "calendar.event_live_regex", None)
    if ev:
        parts.append(ev)
    return re.compile("|".join(parts), re.I) if parts else None


def check_visuals(draft, vis, fix, warns, cfg):
    weeks = int(cfg_get(cfg, "visuals.no_repeat_weeks", 8))
    prefix = cfg_get(cfg, "visuals.asset_prefix", "Assets")
    tool = cfg_get(cfg, "visuals.ai_image_tool", None)
    ai_any = re.compile(r"(?:" + (re.escape(tool) + "|" if tool else "") + r"AI) image of\s*(.+?)\.(?:\s|$)", re.I)
    ai_line = re.compile(r"^Needed:\s*(?:" + (re.escape(tool) + "|" if tool else "") + r"AI) image of\s*(.+?)\.\s*Prompt in draft tab\.?$", re.I)
    assets_p, recent_p = os.path.join(HERE, "assets.txt"), os.path.join(HERE, "visuals_recent.txt")
    assets = {os.path.basename(l.strip()).lower() for l in open(assets_p, encoding="utf-8") if l.strip()} if os.path.exists(assets_p) else None
    recent = []
    if os.path.exists(recent_p):
        for l in open(recent_p, encoding="utf-8"):
            parts = [x.strip() for x in l.split("|", 2)]
            if len(parts) == 3:
                recent.append([parts[0], _ddmmmyy(parts[1]), parts[2]])
    ct = draft.get("content_type", "") or ""
    real_rx = real_photo_regex(cfg)
    ai_shape = f"\"Needed: {tool} image of <subject>. Prompt in draft tab.\", " if tool else ""
    if not (vis.startswith("Use:") or vis.startswith("Needed:") or vis.startswith("None needed")):
        fix("Visuals", "Visual line missing or malformed.",
            f"Write \"Use: <file> ({prefix}/<subfolder>)\", {ai_shape}or \"Needed: <real photo or graphic>\".")
    if vis.startswith("Use:") and not USE_RE.search(vis):
        fix("Visuals", "Use: line names no file.", f"Write \"Use: <file name with extension> ({prefix}/<subfolder>)\".")

    def file_problem(v):
        m = USE_RE.search(v)
        if not m:
            return None
        f = m.group(1).strip().lower()
        if assets is not None and f not in assets:
            return f"'{m.group(1)}' is not in {prefix}"
        for rid, d, rv in recent:
            if f in [x.strip().lower() for x in USE_RE.findall(rv)]:
                return f"'{m.group(1)}' is already used on {rid} ({d}), within {weeks} weeks"
        return None

    alt = "give an image prompt" if tool else "name the photo or graphic needed"
    if vis.startswith("Use:"):
        prob = file_problem(vis)
        if prob:
            fix("Visuals", f"Visual file {prob}.", f"Pick a file not used within {weeks} weeks, or {alt}.")
    for v in draft.get("visual_alternatives") or []:
        prob = file_problem(v)
        if prob:
            warns.append(f"Alternative visual {prob}: drop it from visual_alternatives (advice, not a fix).")
    is_ai = bool(ai_any.search(vis)) and vis.lower().startswith("needed:")
    g = ai_line.match(vis)
    gp, ga = (draft.get("image_prompt") or "").strip(), (draft.get("image_alt_prompt") or "").strip()
    if is_ai and not tool:
        fix("Visuals", "AI image visual, but the workspace has no AI image tool.", "Write \"Needed: <the photo or graphic, and what it shows>\" and drop the prompts.")
    elif is_ai and not g:
        fix("Visuals", "AI image visual line malformed.", f"Write \"Needed: {tool} image of <subject in up to 12 words>. Prompt in draft tab.\"")
    if g and tool:
        if len(g.group(1).split()) > 12:
            fix("Visuals", "Image subject over 12 words.", "Shorten the subject in the Visual line to 12 words or fewer.")
        if not gp or not ga:
            fix("Visuals", "AI image visual without both prompts.", "Add image_prompt and a different image_alt_prompt.")
        if real_rx and real_rx.search(ct):
            fix("Visuals", f"{ct} needs a real photo, not a generated image.",
                f"Use a {prefix} file or write \"Needed: <the real photo or logo, with permission>\".")
        for rid, d, rv in recent:
            if any(_similar(g.group(1), o) for o in ai_any.findall(rv)):
                fix("Visuals", f"Image subject is close to the one on {rid} ({d}).", "Choose a different setting, task or shot for this post.")
                break
    if not tool and (gp or ga):
        warns.append("Image prompts given, but the workspace has no AI image tool: drop them.")
    if tool and not gp and not (real_rx and real_rx.search(ct)) and not vis.startswith("None needed"):
        warns.append(f"No image_prompt: every post that may use a generated image carries a ready-to-paste {tool} prompt.")

    competitors = [c.lower() for c in cfg_get(cfg, "writing.competitors", [])]
    people = []
    for n in cfg_get(cfg, "company.people", []) + [cfg_get(cfg, "company.approver.name", "")]:
        people += [p for p in re.findall(r"[A-Za-z][A-Za-z'-]+", n or "") if len(p) > 2]
    people_rx = re.compile(r"\b(" + "|".join(re.escape(p) for p in set(people)) + r")\b", re.I) if people else None
    ref = cfg_get(cfg, "visuals.product_reference_photo", None)
    ref_start = (ref.get("prompt_start") if isinstance(ref, dict) else ref) or ""
    prod_rx = cfg_get(cfg, "visuals.product_regex", None) or (ref.get("product_regex") if isinstance(ref, dict) else None)
    ratios = cfg_get(cfg, "visuals.aspect_ratios", ["1.91:1 (1200 x 627)", "1:1 (1080 x 1080)"])
    ratio_tokens = set()
    for r in ratios:
        ratio_tokens |= set(re.findall(r"\d+(?:\.\d+)?:\d+|\d+ x \d+", r))
    ratio_rx = re.compile(r"\b(" + "|".join(re.escape(t) for t in ratio_tokens) + r")\b") if ratio_tokens else None
    spelling = (cfg_get(cfg, "writing.spelling", "") or "").upper()
    for label, p in (("image_prompt", gp), ("image_alt_prompt", ga)):
        if not p or not tool:
            continue
        pl = p.lower()
        if ref_start and prod_rx and re.search(prod_rx, pl, re.I) and not pl.startswith(ref_start.lower()):
            fix("Visuals", f"{label} shows the product without starting from the reference photo.",
                f"Start with \"{ref_start}\" and keep the product exactly as in the photo.")
        for c in competitors:
            if re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", pl):
                fix("Competitors", f"{label} names '{c}'.", "Remove the company or brand name.")
        if people_rx and people_rx.search(p):
            fix("Visuals", f"{label} names a real person.", "Describe a generic person; never a real person's likeness.")
        if re.search(r"certif|compliant", pl):
            fix("Visuals", f"{label} implies certification.", "Remove it.")
        if not re.search(r"no text|no words|no lettering", pl):
            fix("Visuals", f"{label} does not rule out text in the image.", "Add \"No text, logos or watermarks in the image.\"")
        for rx in WRONG_SPELLING.get(spelling, []):
            m = re.search(rx, pl)
            if m:
                fix("Writing rules", f"{label} uses '{m.group(0)}', which is not {spelling} spelling.", f"Use {spelling} spelling.")
                break
        if ratio_rx and not ratio_rx.search(pl):
            warns.append(f"{label} gives no aspect ratio; use one of: {', '.join(ratios)}.")
    if gp and ga and _similar(gp, ga):
        fix("Visuals", "image_alt_prompt is a reworded copy of image_prompt.", "Write the alternative as a different scene, setting or shot.")


def main(argv):
    cfg, cfg_path = load_config(argv)
    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in VALUE_FLAGS
        else:
            pos.append(a)
    draft_p, facts_p = pos[0], pos[1]
    draft = json.load(open(draft_p, encoding="utf-8"))
    facts = load_facts(facts_p, cfg)
    proof = json.load(open(argv[argv.index("--proof") + 1], encoding="utf-8")) if "--proof" in argv else None
    company = cfg_get(cfg, "company.name", "") or "the company"
    who = cfg_get(cfg, "company.approver.name", "") or "the approver"
    approved_vals = cfg_get(cfg, "facts.approved_values", ["Approved", "Approved with edits"])
    rule_ids = {r.get("id"): r for r in cfg_get(cfg, "writing.custom_rules", []) if r.get("id")}

    post = draft.get("post", "")
    comment = draft.get("first_comment", "") or ""
    low = post.lower()
    fixes, warns = [], []

    def fix(rule, issue, change):
        fixes.append({"n": len(fixes) + 1, "rule": rule, "issue": issue, "fix": change})

    # 1. Writing standards and mechanics (shared with the drafters).
    cmd = [sys.executable, os.path.join(HERE, "check_draft.py"), draft_p, "--facts", facts_p]
    if cfg_path:
        cmd += ["--config", cfg_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        base = json.loads(r.stdout)
    except json.JSONDecodeError:
        base = {"fails": ["check_draft.py did not run: " + (r.stderr.strip() or r.stdout.strip())], "warnings": []}
    for f in base.get("fails", []):
        m = re.match(r"([\w-]+):\s", f)
        if m and m.group(1) in rule_ids:
            fix(m.group(1), f, rule_ids[m.group(1)].get("message") or "Use the approved wording named in the rule.")
        elif "company name" in f.lower():
            fix("Competitors", f, f"Remove the name. Compare categories, not companies; name only {company} and, on proof posts, the signed-off organization.")
        else:
            fix("Writing rules", f, "Correct the text so this check passes.")
    warns.extend(base.get("warnings", []))

    # 2. Every cited fact must exist and be approved.
    cited = [x.strip().upper() for x in draft.get("fact_ids", []) if x.strip()]
    if not cited and not proof:
        warns.append(f"No fact IDs cited. Confirm the post makes no factual claim about {company}.")
    approved_text = []
    for fid in cited:
        f = facts.get(fid)
        if not f:
            fix("Facts", f"Fact {fid} is not on the facts sheet.", f"Remove the claim that relies on it, or flag it for {who}.")
        elif f["status"] not in approved_vals:
            fix("Facts", f"Fact {fid} has status {f['status'] or 'blank'}.", "Remove the claim.")
        else:
            approved_text.append(f["claim"].lower())

    # 3. Figures must trace to a cited approved fact, or to the proof item.
    trace = " ".join(approved_text)
    if proof:
        trace += " " + " ".join(str(v) for v in proof.values()).lower()
    trace += " " + person_text()
    trace_nums = {norm_num(t) for t in numbers_in(trace)}
    for tok in numbers_in(re.sub(r"\[[^\]]*\]", " ", post)):  # [bracketed] gaps are not figures
        if norm_num(tok) not in trace_nums:
            fix("Figures", f"Figure '{tok}' does not trace to a cited approved fact or the proof item.",
                "Remove the figure, or cite the approved fact that states it (with its source named in the sentence).")

    # 4. Launch, availability or delivery timing (generic default rule, tunable in the config).
    pt = cfg_get(cfg, "writing.product_timing", {}) or {}
    level = (pt.get("level") or "fail").lower()
    if level != "off":
        timing = re.compile(pt.get("regex") or PRODUCT_TIMING, re.I)
        for s in sentences(post):
            if timing.search(s) and TIME_REF.search(s.lower()):
                msg = f"Product timing stated: \"{s}\""
                if level == "warn":
                    warns.append(msg + " Confirm it is not a launch, availability or delivery date.")
                else:
                    fix("Product timing", msg, pt.get("message") or "Remove the date. No launch, availability or delivery dates in posts.")

    # 5. Named competitors: only the signed-off proof organization may be named.
    org = str((proof or {}).get("Organization", "")).lower()
    issues = " ".join(m["issue"].lower() for m in fixes)
    for c in [c.lower() for c in cfg_get(cfg, "writing.competitors", [])]:
        if re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", low + " " + comment.lower()) and c not in org and c not in issues:
            fix("Competitors", f"Company '{c}' named.", f"Remove it. Name only {company} and, on proof posts, the signed-off organization.")

    # 6. Draft package: alternate hook and visual.
    if not (draft.get("alternate_hook") or "").strip():
        fix("Draft package", "No alternate hook.", "Add one alternate hook with a different angle.")
    vis = (draft.get("visual") or "").strip()
    check_visuals(draft, vis, fix, warns, cfg)

    # 7. Agent-written dates in the first comment or visual line: DD MMM YY.
    for field in (comment, vis):
        if re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", field):
            fix("Dates", f"Numeric date in '{field[:40]}'.", "Write dates as DD MMM YY with an uppercase month (13 OCT 26).")
        m = re.search(r"(?<![\d:])\b(\d) (JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC) (\d\d)\b", field)
        if m:
            fix("Dates", f"Date without a leading zero: '{m.group(0)}'.", f"Write '0{m.group(1)} {m.group(2)} {m.group(3)}' (DD MMM YY, zero-padded).")

    report = {"row_id": draft.get("row_id", ""), "pass": not fixes, "fixes": fixes, "warnings": warns,
              "word_count": base.get("word_count")}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not fixes else 1


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
