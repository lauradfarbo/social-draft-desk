#!/usr/bin/env python3
"""Build the subagent bundles for one weekly run (weekly orchestrator).

Usage:
  python3 make_bundles.py <run dir> <plugin root> plan|draft|proof|redraft|check|fallback [options]

  plan                                  -> <run dir>/plan/
  draft  --rows W11-03,W11-04 [--select select.json] [--proof-rows 0,7]  -> <run dir>/draft/<Row ID>/
         --select: rows with "gaps" in select_rows.py output also get gaps.json ({"gaps", "placeholders"}):
         the drafter writes the full post anyway, each missing item as [square-bracket text].
         --proof-rows on draft: an Advisor proof log row per row (match_proof.py), 0 for none. The item
         goes into proof_item.json and first in person_items.json.
  proof  --rows W11-01 --proof-rows 4   -> <run dir>/proof/<Row ID>/  (proof log row per slot, same order)
  redraft --from draft/<Row ID> --previous <file.json> --fixes <file.json>  -> <run dir>/redraft/<Row ID>-2/
  check  --draft <file.json> [--proof-row N] [--suffix -2] [--content-type T]  -> <run dir>/check/<Row ID><suffix>/
  fallback --rows W12-01 --swaps swaps_final.json  -> <run dir>/fallback/<Row ID>/
      A short-form drafter bundle for the proposed swap, not the original row. row.json takes the
      swap's type and its angle as Title / angle, with Status Planned and What's missing empty; the
      original row goes in fallback.json. The post becomes its own row under the original
      (<Row ID>-FB, Status Fallback post). swaps_final.json: swap_slots.py "swaps" with "angle" (and
      "chapter" when the config lists chapters) filled by the orchestrator.
      Check it with: check --draft <file> --suffix -fb --content-type "<swap type>".

  Add --shadow to draft and proof in a shadow run: row.json then carries Status Planned (so the
  drafting skill's Status check passes) and the real Status under "Live status". Nothing is written.

<run dir>/shared/ must hold workspace.json, calendar.json, proof_log.json, facts.json, rules.md,
plan_rules.md, voice.md and assets.txt, and may hold long_form.md (the long-form source as text),
the client's chapter map (file name from sources.long_form.chapter_map, default chapter-map.md;
copied into bundles as chapter-map.md), milestones.json, approver_notes.json (the "From the
approver's notes" tab: Date added, From, For, Fact, Link, Used in, Add to facts sheet?) and
approver_edits.json (the Approver edits tab: Date captured, Row ID, Content type, Status, Size of
edit, Original draft, Approver's text, What changed, Draft URL), each saved as returned.
Every bundle gets workspace.json. Draft, proof and fallback bundles also get long_form.md and
chapter-map.md when present, recent.txt and visuals_recent.txt (Visual of every other row within
visuals.no_repeat_weeks either side). Check bundles get assets.txt and visuals_recent.txt.
Draft, proof, fallback and check bundles get person_items.json when there is anything to put in it:
the facts the approver gave (approver_notes.json, word for word), plus the Milestones row (with its
Notes) of every milestone linked to the row (named in its Notes, Title / angle or Sources, or of the
milestone_type of a plan.dependencies entry the row depends on). Each item counts as approved for
drafting and as a figure source; it never authorizes naming a person or company. These bundles also
get milestones.json, and check bundles get row.json (for holds).
With edit_learning.enabled (default true), draft, proof and fallback bundles get approver_edits.json:
up to edit_learning.examples_per_draft (default 3) of the approver's latest edited posts, same content
type first, each with the original draft, the approver's text and what changed (style only), and
approver_prompt_edits.json: the latest three image prompt edits (Content type starting "Image prompt").
The script writes facts_approved.json ([{"id", "claim", "comments"}], column names from facts.*)
in shared/ on first use. It copies files; it never edits them. Prints the bundle paths it made.
"""
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
VALUE_FLAGS = {"--rows", "--proof-rows", "--from", "--previous", "--fixes", "--draft", "--proof-row",
               "--suffix", "--content-type", "--swaps", "--config", "--select"}
CHECK_KEYS = ("row_id", "content_type", "type", "post", "first_comment", "alternate_hook", "visual",
              "visual_alternatives", "image_prompt", "image_alt_prompt", "image_alt_subject",
              "poll_question", "poll_options", "fact_ids")


def cfg_get(cfg, path, default):
    cur = cfg
    for k in path.split("."):
        if not isinstance(cur, dict) or cur.get(k) is None:
            return default
        cur = cur[k]
    return cur


def load(p):
    v = json.load(open(p, encoding="utf-8"))
    return v.get("values", v) if isinstance(v, dict) else v


def table(values):
    hdr = values[0]
    out = []
    for n, r in enumerate(values[1:], start=2):
        r = list(r) + [""] * (len(hdr) - len(r))
        out.append({"_row": n, **dict(zip(hdr, r))})
    return out


def parse_date(s):
    for f in ("%a %d %b %y", "%d %b %y", "%Y-%m-%d"):
        try:
            return datetime.strptime((s or "").strip().title() if "%b" in f else (s or "").strip(), f).date()
        except ValueError:
            pass
    return None


def cp(src, dst_dir, name=None):
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy(src, os.path.join(dst_dir, name or os.path.basename(src)))


def cp_if(src, dst_dir, name=None):
    if os.path.exists(src):
        cp(src, dst_dir, name)


def arg(argv, k, default=None):
    return argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else default


def write_recent_visuals(cal, rid, rd, path, weeks, off_plan):
    """visuals_recent.txt: Row ID | date | Visual of every other row within the window either side."""
    with open(path, "w", encoding="utf-8") as fh:
        for r in cal:
            d = parse_date(r.get("Date"))
            v = (r.get("Visual") or "").strip()
            for seg in (r.get("Notes") or "").split("Orchestrator "):
                if "Fallback draft" in seg and "Visual:" in seg:  # visual of a fallback draft
                    v = (v + " | Fallback " + seg.split("Visual:", 1)[1].split(" Status stays")[0]).strip(" |")
            if r.get("Row ID") == rid or not d or not rd or not v or r.get("Status") in off_plan:
                continue
            if rd - timedelta(weeks=weeks) <= d <= rd + timedelta(weeks=weeks):
                fh.write(f"{r.get('Row ID')} | {d.isoformat()} | {v}\n")


def main(argv):
    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in VALUE_FLAGS
        else:
            pos.append(a)
    run, root, mode = pos[0], pos[1], pos[2]
    sh = os.path.join(run, "shared")
    ws = os.path.join(sh, "workspace.json")
    if not os.path.exists(ws):
        sys.exit(f"{ws} is missing. Copy the run's workspace.json into shared/ first.")
    cfg = json.load(open(ws, encoding="utf-8"))
    sts = cfg_get(cfg, "calendar.statuses", None)
    if isinstance(sts, dict):
        off_plan = (sts.get("Cancelled", "Cancelled"), sts.get("Backlog", "Backlog"))
    elif isinstance(sts, list) and len(sts) == 6 and "Cancelled" not in sts:
        off_plan = (sts[5], "Backlog")
    elif isinstance(sts, list) and len(sts) == 8 and "Cancelled" not in sts:
        off_plan = (sts[6], sts[7])
    else:
        off_plan = ("Cancelled", "Backlog")
    weeks = int(cfg_get(cfg, "visuals.no_repeat_weeks", 8))
    label = cfg_get(cfg, "swaps.source_label", "Long-form")
    who = cfg_get(cfg, "company.approver.name", "") or "The approver"
    chapter_map = os.path.basename(cfg_get(cfg, "sources.long_form.chapter_map", "chapter-map.md"))
    skills = os.path.join(root, "skills")
    orch = os.path.join(skills, "weekly-orchestrator", "scripts")

    fa = os.path.join(sh, "facts_approved.json")
    if not os.path.exists(fa):
        id_c = cfg_get(cfg, "facts.id_col", "ID")
        claim_c = cfg_get(cfg, "facts.claim_col", "Claim")
        st_c = cfg_get(cfg, "facts.status_col", "Status")
        com_c = cfg_get(cfg, "facts.comments_col", "Approver comments")
        ok = cfg_get(cfg, "facts.approved_values", ["Approved", "Approved with edits"])
        facts = table(load(os.path.join(sh, "facts.json")))
        keep = [{"id": f.get(id_c, ""), "claim": f.get(claim_c, ""), "comments": f.get(com_c, "")}
                for f in facts if f.get(st_c) in ok and f.get(id_c)]
        json.dump(keep, open(fa, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    cal = table(load(os.path.join(sh, "calendar.json")))
    made = []

    # Facts the approver gave in Notes or on the Ideas tab ("From the approver's notes" tab).
    person = []
    if os.path.exists(os.path.join(sh, "approver_notes.json")):
        for r in table(load(os.path.join(sh, "approver_notes.json"))):
            fact = r.get("Fact", "") or next((v for k, v in r.items() if isinstance(k, str) and k.startswith("Fact")), "")
            if str(fact).strip() and str(r.get("Date added", "")).strip():
                person.append({"row": f"approver notes row {r['_row']}", "date_added": r.get("Date added", ""),
                               "from": r.get("From", ""), "for": r.get("For", ""), "detail": fact,
                               "link": r.get("Link", "")})
    sel = {}
    if arg(argv, "--select"):
        sel = {x["row_id"]: x for x in json.load(open(arg(argv, "--select"), encoding="utf-8")).get("rows", [])}

    miles = []  # Milestones rows that still stand; their Notes are the approver's words for linked rows
    if os.path.exists(os.path.join(sh, "milestones.json")):
        for m in table(load(os.path.join(sh, "milestones.json"))):
            if (m.get("Milestone") or "").strip() and (m.get("Confirmed") or "").strip().lower() != "cancelled":
                miles.append(m)
    deps = cfg_get(cfg, "plan.dependencies", []) or []

    def dep_hit(row, dep):
        text = " ".join(str(row.get(k, "") or "") for k in ("Title / angle", "Content type")).lower()
        rx, lab = dep.get("row_regex"), (dep.get("label") or "").lower()
        return bool((rx and re.search(rx, text, re.I)) or (lab and lab in text))

    def milestone_items(row):
        if not row:
            return []
        hay = " ".join(str(row.get(k, "") or "") for k in ("Notes", "Title / angle", "Sources")).lower()
        out = []
        for m in miles:
            name = m["Milestone"].strip()
            mtype = (m.get("Type") or "").strip().lower()
            linked = name.lower() in hay or any(mtype and (d.get("milestone_type") or "").strip().lower() == mtype
                                                and dep_hit(row, d) for d in deps)
            if linked:
                det = f"{name}. {m.get('Type', '')}. Start {m.get('Start date', '')}" + (f", end {m['End date']}" if m.get("End date") else "")
                det += f". Confirmed: {m.get('Confirmed', '')}." + (f" Notes: {m['Notes']}" if (m.get("Notes") or "").strip() else "")
                out.append({"row": f"Milestones row {m['_row']}", "date_added": "", "from": "Milestones tab",
                            "for": name, "detail": det, "link": ""})
        return out

    def add_person(d, row=None, first=None):
        items = (first or []) + person + milestone_items(row)
        if items:
            json.dump(items, open(os.path.join(d, "person_items.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        cp_if(os.path.join(sh, "milestones.json"), d)

    # The approver's edits (Approver edits tab): drafters write the way the approver edits.
    edits, prompt_edits = [], []
    n_ex = int(cfg_get(cfg, "edit_learning.examples_per_draft", 3))
    if cfg_get(cfg, "edit_learning.enabled", True) is not False and os.path.exists(os.path.join(sh, "approver_edits.json")):
        latest = {}
        for e in table(load(os.path.join(sh, "approver_edits.json"))):
            txt = e.get("Approver's text", "") or e.get("Approver text", "")
            if not str(txt).strip():
                continue
            e["_text"] = txt
            if (e.get("Content type") or "").startswith("Image prompt"):
                prompt_edits.append(e)
            else:
                latest.pop(e.get("Row ID"), None)
                latest[e.get("Row ID")] = e  # later rows win: the newest version of each post, newest last
        edits = list(latest.values())[::-1]

    def add_edits(d, ctype):
        if prompt_edits:
            json.dump([{"row_id": e.get("Row ID"), "original_prompt": e.get("Original draft"), "approvers_prompt": e["_text"],
                        "what_changed": e.get("What changed")} for e in prompt_edits[-3:][::-1]],
                      open(os.path.join(d, "approver_prompt_edits.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        if not edits or n_ex <= 0:
            return
        key = (ctype or "").split(" - ")[0]
        same = [e for e in edits if (e.get("Content type") or "").split(" - ")[0] == key]
        pick = (same + [e for e in edits if e not in same])[:n_ex]
        json.dump([{"row_id": e.get("Row ID"), "content_type": e.get("Content type"), "size": e.get("Size of edit"),
                    "what_changed": e.get("What changed"), "original_draft": e.get("Original draft"),
                    "approvers_text": e["_text"]} for e in pick],
                  open(os.path.join(d, "approver_edits.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    if mode == "plan":
        d = os.path.join(run, "plan")
        for f in ("workspace.json", "calendar.json", "facts.json", "proof_log.json", "plan_rules.md", "rules.md", "milestones.json"):
            cp_if(os.path.join(sh, f), d)
        cp(os.path.join(orch, "plan_check.py"), d)
        made.append(d)

    swaps = {}
    if mode == "fallback":
        sw = json.load(open(arg(argv, "--swaps"), encoding="utf-8"))
        swaps = {x["row_id"]: x for x in (sw.get("swaps", sw) if isinstance(sw, dict) else sw)}
    if mode in ("draft", "proof", "fallback"):
        ids = [x for x in (arg(argv, "--rows", "") or "").split(",") if x]
        prows = [int(x) for x in (arg(argv, "--proof-rows", "") or "").split(",") if x]
        proof = table(load(os.path.join(sh, "proof_log.json"))) if mode == "proof" or (mode == "draft" and prows) else []
        need_ch = bool(cfg_get(cfg, "swaps.chapters", []))
        for i, rid in enumerate(ids):
            row = next((r for r in cal if r.get("Row ID") == rid), None)
            if row is None:
                sys.exit(f"Row ID {rid} not found on the calendar.")
            d = os.path.join(run, mode, rid)
            os.makedirs(d, exist_ok=True)
            if "--shadow" in argv:
                row = {**row, "Live status": row.get("Status", ""), "Status": "Planned"}
            fb = None
            if mode == "fallback":
                x = swaps.get(rid)
                if not x or not x.get("angle") or (need_ch and not x.get("chapter")):
                    sys.exit(f"{rid}: no swap with angle{' and chapter' if need_ch else ''} in --swaps.")
                ch = f", {label} ch{x['chapter']}" if x.get("chapter") else ""
                fb = {"row_id": rid, "date": row.get("Date"), "original_content_type": row.get("Content type"),
                      "original_title": row.get("Title / angle"), "swap_type": x["type"], "angle": x["angle"],
                      "chapter": x.get("chapter"), "conditional": x.get("conditional", ""),
                      "note": "Fallback draft for a proposed swap. Draft the swap post, not the original row. "
                              f"It goes on its own row under {rid} ({rid}-FB, Status Fallback post). {who} uses it by "
                              f"setting it to Approved and {rid} to Cancelled."}
                row = {**row, "Content type": x["type"], "Title / angle": x["angle"],
                       "Spec": f"Fallback for {row.get('Content type')}: {x['type']}{ch}.",
                       "Status": "Planned", "What's missing": "", "Notes": ""}
            json.dump(row, open(os.path.join(d, "row.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            for f in ("workspace.json", "rules.md", "voice.md", "facts_approved.json", "assets.txt", "long_form.md"):
                cp_if(os.path.join(sh, f), d)
            cp_if(os.path.join(sh, chapter_map), d, "chapter-map.md")
            rd = parse_date(row.get("Date"))

            def near(r):
                rdt = parse_date(r.get("Date"))
                return r.get("Row ID") != rid and rdt and rd and rd - timedelta(weeks=weeks) <= rdt <= rd + timedelta(days=14)
            base = (row.get("Content type", "") or "").split(" - ")[0]
            recent = [r for r in cal if (r.get("Content type", "") or "").split(" - ")[0] == base and near(r)]
            lf_rows = [r for r in cal if label.lower() in ((r.get("Sources", "") or "") + (r.get("Content type", "") or "")).lower() and near(r)]
            with open(os.path.join(d, "recent.txt"), "w", encoding="utf-8") as fh:
                for r in {x["Row ID"]: x for x in recent + lf_rows if x.get("Status") not in off_plan}.values():
                    fh.write(f"{r['Row ID']} | {r.get('Content type')} | {r.get('Sources')}\n")
            write_recent_visuals(cal, rid, rd, os.path.join(d, "visuals_recent.txt"), weeks, off_plan)
            if fb:
                json.dump(fb, open(os.path.join(d, "fallback.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            add_person(d, row)
            add_edits(d, row.get("Content type"))
            if mode == "draft" and i < len(prows) and prows[i]:  # Advisor proof item for an advisory row
                it = next((p for p in proof if p["_row"] == prows[i]), None)
                if it is None:
                    sys.exit(f"Proof log row {prows[i]} not found.")
                json.dump(it, open(os.path.join(d, "proof_item.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
                add_person(d, row, [{"row": f"proof log row {prows[i]}", "date_added": it.get("Date logged", ""),
                                     "from": "proof log", "for": rid, "detail": it.get("What happened", ""),
                                     "quote": it.get("Approved quote (verbatim)", ""), "can_name": "Yes (proof log)",
                                     "organization": it.get("Organization", ""), "link": "",
                                     "signed_off_by": it.get("Sign-off from (name)", "")}])
            if sel.get(rid, {}).get("gaps") and mode != "fallback":
                json.dump({"gaps": sel[rid]["gaps"], "placeholders": sel[rid].get("placeholders", [])},
                          open(os.path.join(d, "gaps.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            src = "proof-intake" if mode == "proof" else "short-form-drafter"
            cp_if(os.path.join(skills, src, "SKILL.md"), d, "proof_skill.md" if mode == "proof" else "drafter_skill.md")
            for sub in ("references", "scripts"):
                folder = os.path.join(skills, src, sub)
                if os.path.isdir(folder):
                    for f in os.listdir(folder):
                        if os.path.isfile(os.path.join(folder, f)):
                            cp(os.path.join(folder, f), d)
            if mode == "proof":
                cp_if(os.path.join(skills, "short-form-drafter", "references", "post-types.md"), d)
                n = prows[i]
                item = next(p for p in proof if p["_row"] == n)
                json.dump(item, open(os.path.join(d, "proof_item.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            made.append(d)

    if mode == "redraft":
        src = os.path.join(run, arg(argv, "--from"))
        d = os.path.join(run, "redraft", os.path.basename(src.rstrip("/")) + "-2")
        shutil.copytree(src, d, dirs_exist_ok=True)
        cp(ws, d)
        shutil.copy(arg(argv, "--previous"), os.path.join(d, "previous.json"))
        shutil.copy(arg(argv, "--fixes"), os.path.join(d, "fixes.json"))
        made.append(d)

    if mode == "check":
        dj = json.load(open(arg(argv, "--draft"), encoding="utf-8"))
        rid = dj["row_id"]
        row = next((r for r in cal if r.get("Row ID") == rid), {})
        if arg(argv, "--content-type"):
            dj["content_type"] = arg(argv, "--content-type")  # fallback drafts: the swap type
        dj.setdefault("content_type", row.get("Content type", ""))
        d = os.path.join(run, "check", rid + (arg(argv, "--suffix", "") or ""))
        os.makedirs(d, exist_ok=True)
        json.dump({k: dj.get(k) for k in CHECK_KEYS if k in dj}, open(os.path.join(d, "draft.json"), "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False)
        for f in ("workspace.json", "facts.json", "rules.md", "voice.md", "assets.txt"):
            cp_if(os.path.join(sh, f), d)
        write_recent_visuals(cal, rid, parse_date(row.get("Date")), os.path.join(d, "visuals_recent.txt"), weeks, off_plan)
        for f in ("check_compliance.py", "check_draft.py"):
            cp_if(os.path.join(orch, f), d)
        add_person(d, row)
        if row:
            rj = {k: v for k, v in row.items() if k != "_row"}
            if arg(argv, "--content-type"):  # a fallback draft: the swap, not the original row
                rj.update({"Content type": arg(argv, "--content-type"), "Notes": "", "Title / angle": ""})
            json.dump(rj, open(os.path.join(d, "row.json"), "w", encoding="utf-8"),
                      indent=1, ensure_ascii=False)
        if arg(argv, "--proof-row"):
            proof = table(load(os.path.join(sh, "proof_log.json")))
            item = next(p for p in proof if p["_row"] == int(arg(argv, "--proof-row")))
            json.dump(item, open(os.path.join(d, "proof_item.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        made.append(d)

    print(json.dumps({"bundles": made}, indent=1))
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
