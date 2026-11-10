#!/usr/bin/env python3
"""Get a post's final text from its draft tab (weekly orchestrator).

Usage:
  python3 extract_final.py doc.json <tab URL or tab ID>

doc.json: the Docs read_doc response, saved as returned.
Prints the tab text above the dashed line ("----------"), trailing blank lines removed,
exactly as the approver left it. Exit 1 if the tab or the dashed line is missing.

When the reviewer notes below the dashed line hold both image prompt lines
("Image prompt (edit this ...): <text>" and "Image prompt as drafted ...: <text>"), it also prints
image_prompt (as the approver left it) and image_prompt_original, so edit_capture.py --prompts can
learn from the approver's prompt edits.

Prints {"tab_id", "final_text"[, "image_prompt", "image_prompt_original"]}.
"""
import json
import re
import sys


def tabs(node):
    for t in node.get("tabs", []) + node.get("childTabs", []):
        yield t
        yield from tabs(t)


def main(argv):
    d = json.load(open(argv[1], encoding="utf-8"))
    d = d.get("content", d)
    m = re.search(r"tab=(t\.[\w-]+)", argv[2])
    tab_id = m.group(1) if m else argv[2]
    tab = next((t for t in tabs(d) if t.get("tabProperties", {}).get("tabId") == tab_id), None)
    if not tab:
        print(json.dumps({"error": f"tab {tab_id} not found"}))
        return 1
    text = ""
    for el in tab["documentTab"]["body"]["content"]:
        for pe in el.get("paragraph", {}).get("elements", []):
            text += pe.get("textRun", {}).get("content", "")
    if "\n----------\n" not in "\n" + text:
        print(json.dumps({"error": "dashed line not found"}))
        return 1
    final = ("\n" + text).split("\n----------\n")[0][1:].rstrip("\n ")
    out = {"tab_id": tab_id, "final_text": final}
    notes = ("\n" + text).split("\n----------\n", 1)[1]
    m1 = re.search(r"^Image prompt \(edit this[^:]*:[ \t]*(.*)$", notes, re.M)
    m2 = re.search(r"^Image prompt as drafted[^:]*:[ \t]*(.*)$", notes, re.M)
    if m1 and m2:
        out["image_prompt"], out["image_prompt_original"] = m1.group(1).strip(), m2.group(1).strip()
    print(json.dumps(out, ensure_ascii=False))
    return 0


def _usage_ok(argv, n):
    flags_no_value = {"--shadow", "--live", "--help", "-h"}
    pos, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a not in flags_no_value
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
