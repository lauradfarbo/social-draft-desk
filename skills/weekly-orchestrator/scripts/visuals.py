#!/usr/bin/env python3
"""Resolve visuals for one weekly run so images are not repeated (weekly orchestrator).

Usage:
  python3 visuals.py before.json assets.txt returns/W03-01.json returns/W03-02-fb.json ... [--config workspace.json] [--weeks 8]

before.json: the calendar table, header row first.
assets.txt:  the assets folder listing (<subfolder>/<file> per line).
returns:     drafter and proof-drafter JSON returns of this run, in the order they were made. When a row
             has several returns (a redraft), only the last one given counts. A file ending in
             -fb.json is a fallback draft and counts against its row's date.

Config (workspace.json, all optional):
  visuals.no_repeat_weeks        window either side (default 8; --weeks overrides)
  visuals.asset_prefix           label of the assets folder in Visual lines (default "Assets")
  visuals.ai_image_tool          name of the AI image tool, or null for none (default null)
  visuals.real_photo_only_regex  content types that need a real photo (default: the proof types and
                                 calendar.event_live_regex)

Rules:
- An assets file ("Use: <file> (<asset prefix>/<subfolder>)") must exist in assets.txt and must not be
  the visual of any other calendar row dated within the window either side (Visual column, or a
  "Visual:" in a fallback Notes line), or of another draft in this run. Fallback post rows count like
  any row; Cancelled and Backlog rows do not. Real drafts are resolved
  first, by date, then fallbacks, so a fallback never takes a file from a real draft. A draft that
  clashes moves to its first free visual_alternatives entry, else to its image prompt (when an AI
  image tool is set). Real-photo content types never move to an AI image: they are reported unresolved.
- With no AI image tool, a draft that has no free file gets "Needed: photo or graphic ..." and
  changed: true, so the approver supplies one. Real-photo content types are still reported unresolved.
- Each resolved item carries visual_alternatives pruned to free files only; write it back with the visual.
- An AI image visual ("Needed: <tool> image of <subject>. Prompt in draft tab.") needs image_prompt and
  image_alt_prompt. Two AI image subjects in the window that share most of their words are reported
  as "similar". When the later draft's image_alt_subject is free, its item gives "swap_prompts": true
  and a new Visual line built from that subject, so the orchestrator swaps the two prompts and the
  line in one step; otherwise the draft is reported unresolved.

Prints {"resolved": [{"row_id", "file", "visual", "changed", "reason"}], "similar": [...], "unresolved": [...]}.
Exit 1 when anything is unresolved. Writes nothing.
"""
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
VALUE_FLAGS = {"--config", "--weeks"}
USE = re.compile(r"Use:\s*(.+?\.(?:png|jpe?g|gif|webp|mp4|mov|psd|pptx|docx|pdf|md|mp3))\b", re.I)
STOP = {"a", "an", "the", "of", "in", "on", "at", "with", "and", "for", "to", "wearing", "image", "photo"}


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


def real_photo_regex(cfg):
    rx = cfg_get(cfg, "visuals.real_photo_only_regex", None)
    if rx:
        return re.compile(rx, re.I)
    parts = [re.escape(v) for v in cfg_get(cfg, "calendar.proof_types", {"Partner": "Partner Win", "Customer": "Customer Proof"}).values() if v]
    ev = cfg_get(cfg, "calendar.event_live_regex", None)
    if ev:
        parts.append(ev)
    return re.compile("|".join(parts), re.I) if parts else None


def calendar_visuals(row):
    """Visual column plus any 'Visual:' named in a fallback Notes line."""
    txt = row.get("Visual", "") or ""
    for seg in re.split(r"(?<=\.)\s+(?=[A-Z][a-z]+ \d\d [A-Z]{3} \d\d:)", row.get("Notes", "") or ""):
        if "Fallback draft" in seg and "Visual:" in seg:
            txt += " | " + seg.split("Visual:", 1)[1]
    return txt


def subject_from_prompt(p):
    m = re.search(r"image of (?:an? |two |three )?(.+?)[,.]", p or "", re.I)
    return " ".join((m.group(1) if m else "workplace scene").split()[:12])


def load(p):
    v = json.load(open(p, encoding="utf-8"))
    return v.get("values", v) if isinstance(v, dict) else v


def skip_statuses(cfg):
    """Cancelled and Backlog labels (rows a person took off the plan): their visuals do not count."""
    sts = cfg_get(cfg, "calendar.statuses", None)
    if isinstance(sts, dict):
        return (sts.get("Cancelled", "Cancelled"), sts.get("Backlog", "Backlog"))
    if isinstance(sts, list) and len(sts) == 6 and "Cancelled" not in sts:
        return (sts[5], "Backlog")  # a six-value status list
    if isinstance(sts, list) and len(sts) == 8 and "Cancelled" not in sts:
        return (sts[6], sts[7])
    return ("Cancelled", "Backlog")


def parse_date(s):
    for f in ("%a %d %b %y", "%d %b %y", "%Y-%m-%d"):
        try:
            return datetime.strptime((s or "").strip().title() if "%b" in f else (s or "").strip(), f).date()
        except ValueError:
            pass
    return None


def file_of(visual):
    m = USE.search(visual or "")
    return m.group(1).strip().lower() if m else None


def files_of(text):
    return [m.strip().lower() for m in USE.findall(text or "")]


def tokens(s):
    return {w for w in re.findall(r"[a-z]+", (s or "").lower()) if w not in STOP}


def similar(a, b):
    ta, tb = tokens(a), tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.6


def main(argv):
    cfg = load_config(argv)
    weeks = int(argv[argv.index("--weeks") + 1]) if "--weeks" in argv else int(cfg_get(cfg, "visuals.no_repeat_weeks", 8))
    tool = cfg_get(cfg, "visuals.ai_image_tool", None)
    prefix = cfg_get(cfg, "visuals.asset_prefix", "Assets")
    real_rx = real_photo_regex(cfg)
    ai_line = re.compile(r"(?:" + (re.escape(tool) + "|" if tool else "") + r"AI) image of\s*(.+?)\.(?:\s|$)", re.I)

    def subject_of(visual):
        m = ai_line.search(visual or "")
        return m.group(1).strip().lower() if m else None

    def subjects_of(text):
        return [m.strip().lower() for m in ai_line.findall(text or "")]

    def ai_visual(subject):
        return f"Needed: {tool} image of {subject}. Prompt in draft tab."

    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in VALUE_FLAGS
        else:
            pos.append(a)
    cal_v = load(pos[0])
    assets = {os.path.basename(l.strip()).lower() for l in open(pos[1], encoding="utf-8") if l.strip()}
    hdr = cal_v[0]
    skip = skip_statuses(cfg)
    cal = []
    for r in cal_v[1:]:
        r = list(r) + [""] * (len(hdr) - len(r))
        d = dict(zip(hdr, r))
        d["_date"] = parse_date(d.get("Date"))
        cal.append(d)
    by_id = {r.get("Row ID"): r for r in cal}

    latest = {}
    for p in pos[2:]:
        d = json.load(open(p, encoding="utf-8"))
        latest[(d.get("row_id"), p.endswith("-fb.json"))] = (p, d)  # a later return for the row wins
    drafts, resolved, sim, unresolved = [], [], [], []
    for (rid, fb), (p, d) in latest.items():
        if d.get("blocked") or not d.get("post"):
            continue
        row = by_id.get(rid, {})
        if not row.get("_date"):
            unresolved.append({"row_id": rid, "file": p, "reason": "Row ID not on the calendar, so the repeat check cannot run."})
            continue
        ct = d.get("content_type") or ("" if fb else row.get("Content type", ""))
        ro = (not fb) and bool(real_rx and real_rx.search(ct or ""))
        drafts.append({"path": p, "row_id": rid, "fb": fb, "date": row["_date"], "d": d, "real_only": ro})
    drafts.sort(key=lambda x: (x["fb"], x["date"], x["row_id"] or ""))

    def window(dt, other):
        return dt and other and abs((other - dt).days) <= weeks * 7

    taken_files, taken_subjects = [], []  # (row_id, date, value) chosen in this run
    for x in drafts:
        d, rid, dt = x["d"], x["row_id"], x["date"]
        used = {}
        for r in cal:
            if r.get("Row ID") == rid or r.get("Status") in skip or not window(dt, r["_date"]):
                continue
            for f in files_of(calendar_visuals(r)):
                used.setdefault(f, r.get("Row ID"))
        for t_rid, t_dt, f in taken_files:
            if t_rid != rid and window(dt, t_dt):
                used.setdefault(f, f"{t_rid} (this run)")

        def free(v):
            f = file_of(v)
            return f is not None and f in assets and f not in used

        options = [d.get("visual", "")] + list(d.get("visual_alternatives") or [])
        pick, reason = None, ""
        for i, v in enumerate(options):
            f = file_of(v)
            if f is None:
                if i == 0 and not subject_of(v) and v.strip():
                    pick = v  # "Needed: <real photo>" or "None needed": no repeat check
                    break
                continue
            if f not in assets:
                reason += f"'{f}' is not in {prefix}. "
                continue
            if f in used:
                reason += f"'{f}' is used on {used[f]} within {weeks} weeks. "
                continue
            pick = v
            break
        if pick is None and not x["real_only"]:
            if tool and d.get("image_prompt"):
                if not d.get("image_alt_prompt"):
                    unresolved.append({"row_id": rid, "file": x["path"], "reason": reason + "AI image visual without both prompts."})
                    continue
                g = d.get("visual", "") if subject_of(d.get("visual", "")) else ""
                pick = g or ai_visual(subject_from_prompt(d.get("image_prompt")))
            elif not tool:
                pick = f"Needed: photo or graphic for this post (no unused file in {prefix} within {weeks} weeks)."
        if pick is None:
            why = f"Real photo needed for this content type; no free {prefix} file. " if x["real_only"] else ""
            unresolved.append({"row_id": rid, "file": x["path"], "reason": (why + reason).strip() or "No usable visual."})
            continue
        item = {"row_id": rid, "file": x["path"], "fallback": x["fb"], "visual": pick, "changed": pick != d.get("visual"),
                "visual_alternatives": [v for v in (d.get("visual_alternatives") or []) if v != pick and free(v)],
                "reason": reason.strip()}
        f = file_of(pick)
        if f:
            taken_files.append((rid, dt, f))
        subj = subject_of(pick)
        if subj and tool:
            like = None
            for r in cal:
                if r.get("Row ID") != rid and r.get("Status") not in skip and window(dt, r["_date"]):
                    for o in subjects_of(calendar_visuals(r)):
                        if similar(subj, o):
                            like = like or r.get("Row ID")
            for t_rid, t_dt, t_subj in taken_subjects:
                if t_rid != rid and window(dt, t_dt) and similar(subj, t_subj):
                    like = like or f"{t_rid} (this run)"
            if like:
                alt_subj = " ".join((d.get("image_alt_subject") or "").split()[:12]).rstrip(".")

                def clash(t):
                    return any(similar(t, o) for r in cal if r.get("Row ID") != rid and window(dt, r["_date"])
                               for o in subjects_of(calendar_visuals(r))) or any(
                        t_rid != rid and window(dt, t_dt) and similar(t, t_s) for t_rid, t_dt, t_s in taken_subjects)
                if alt_subj and d.get("image_alt_prompt") and not clash(alt_subj.lower()):
                    new = ai_visual(alt_subj)
                    sim.append({"row_id": rid, "like": like, "subject": subj, "swap_prompts": True, "new_visual": new})
                    item.update(visual=new, changed=True, swap_prompts=True)
                    subj = alt_subj.lower()
                else:
                    sim.append({"row_id": rid, "like": like, "subject": subj, "swap_prompts": False, "new_visual": ""})
                    unresolved.append({"row_id": rid, "file": x["path"],
                                       "reason": f"AI image subject is close to {like} and no different image_alt_subject is given."})
                    continue
            taken_subjects.append((rid, dt, subj))
        resolved.append(item)

    print(json.dumps({"resolved": resolved, "similar": sim, "unresolved": unresolved}, indent=2, ensure_ascii=False))
    return 1 if unresolved else 0


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
