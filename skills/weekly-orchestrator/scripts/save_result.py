#!/usr/bin/env python3
"""Save a connector result or a subagent's JSON return to a file exactly as returned (weekly orchestrator).

Usage:
  python3 save_result.py tool <out.json> <tool name part> <input part> [n] [--transcript <file.jsonl>]
      The n-th latest (default 1) result of a tool call whose name contains <tool name part> and whose
      input contains <input part>, for example:
        save_result.py tool before.json get_values "Calendar!A1:V"
        save_result.py tool docs/rules.json read_doc <doc id part>
      A result too large for the conversation is saved by the app to a file; this script reads that
      file when the transcript only holds the pointer.
  python3 save_result.py report <out.json> <text part> [--transcript <file.jsonl>]
      The latest JSON object in a subagent's final report that contains <text part>, for example
        save_result.py report returns/W11-02.json '"row_id": "W11-02"'
      (spacing inside the JSON is ignored when matching).

Why: every Sheets and Docs read is saved exactly as returned, and retyping a large table by hand is how
cells get changed by accident. The results are already in the session transcript; this copies them
byte for byte. Never retype a person's cell text into a write. Writes only <out.json>. Exit 1 if
nothing matches (or the latest matching call failed: read again).

What it reads (nothing else):
  - One transcript: the file given with --transcript, or else the newest *.jsonl file directly in the
    Claude project folder for the current working directory (~/.claude/projects/<working directory with
    every character other than a letter or digit replaced by "-">/). That newest file is the current
    session. Other projects and older sessions are never read.
  - A file the app saved a large tool result to, only when that transcript names it in the result.
  - SAVE_RESULT_TRANSCRIPTS (an environment variable) is a test override only: a glob of transcript
    files to search instead, newest last. Leave it unset in real runs.
Exit 2 with this text if the arguments are missing or no transcript is found.
"""
import glob
import json
import os
import re
import sys


TRANSCRIPT = None  # set from --transcript


def transcripts():
    if TRANSCRIPT:
        return [TRANSCRIPT] if os.path.isfile(TRANSCRIPT) else []
    only = os.environ.get("SAVE_RESULT_TRANSCRIPTS")
    if only:  # test override only: a glob of transcript files to search instead
        return sorted(glob.glob(only), key=os.path.getmtime)[-3:]
    slug = re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
    folder = os.path.join(os.path.expanduser("~"), ".claude", "projects", slug)
    files = sorted(glob.glob(os.path.join(folder, "*.jsonl")), key=os.path.getmtime)
    return files[-1:]  # the current session only


def walk_strings(o, out):
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            walk_strings(v, out)
    elif isinstance(o, list):
        for v in o:
            walk_strings(v, out)


def result_text(cc):
    if isinstance(cc, list):
        cc = "".join(x.get("text", "") for x in cc if isinstance(x, dict) and x.get("type") == "text")
    cc = cc or ""
    m = re.search(r"(?:saved to|Full output saved to):?\s*(\S+\.(?:txt|json))", cc)
    if m and os.path.exists(m.group(1)) and ("exceeds" in cc or "persisted-output" in cc):
        return open(m.group(1), encoding="utf-8").read()
    return cc


def tool_mode(out, tname, needle, nth):
    uses, results = [], {}
    for f in transcripts():
        for line in open(f, encoding="utf-8"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            c = (d.get("message") or {}).get("content")
            if not isinstance(c, list):
                continue
            for b in c:
                if b.get("type") == "tool_use" and tname in b.get("name", "") and needle in json.dumps(b.get("input"), ensure_ascii=False):
                    uses.append(b["id"])
                elif b.get("type") == "tool_result":
                    results[b.get("tool_use_id")] = b.get("content")
    hits = [u for u in uses if u in results]
    if len(hits) < nth:
        print(json.dumps({"error": f"no result for {tname} / {needle}", "found": len(hits)}))
        return 1
    text = result_text(results[hits[-nth]])
    if re.search(r"Quota exceeded|^Error", text[:200]):
        print(json.dumps({"error": "the latest matching call failed; read again", "text": text[:200]}))
        return 1
    open(out, "w", encoding="utf-8").write(text)
    print(json.dumps({"saved": out, "chars": len(text)}))
    return 0


def report_mode(out, needle):
    squash = lambda t: re.sub(r"\s+", "", t)
    want = squash(needle)
    found = None
    for f in transcripts():
        for line in open(f, encoding="utf-8"):
            if want[:20] not in squash(line).replace('\\"', '"') and needle[:20] not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            strs = []
            walk_strings(d, strs)
            for s in strs:
                i = s.find("{")
                while i != -1:
                    try:
                        obj, _ = json.JSONDecoder().raw_decode(s[i:])
                        if want in squash(json.dumps(obj, ensure_ascii=False)):
                            found = obj
                    except ValueError:
                        pass
                    i = s.find("{", i + 1)
    if found is None:
        print(json.dumps({"error": f"no report containing {needle}"}))
        return 1
    json.dump(found, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({"saved": out}))
    return 0


def main(argv):
    global TRANSCRIPT
    argv = list(argv)
    if "--transcript" in argv:
        i = argv.index("--transcript")
        if i + 1 >= len(argv):
            sys.stderr.write(__doc__.strip() + "\n")
            return 2
        TRANSCRIPT = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) < 4 or argv[1] not in ("tool", "report") or (argv[1] == "tool" and len(argv) < 5):
        sys.stderr.write(__doc__.strip() + "\n")
        return 2
    if not transcripts():
        sys.stderr.write("No session transcript found. Pass --transcript <file.jsonl>.\n\n" + __doc__.strip() + "\n")
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(argv[2])), exist_ok=True)
    if argv[1] == "tool":
        return tool_mode(argv[2], argv[3], argv[4], int(argv[5]) if len(argv) > 5 else 1)
    return report_mode(argv[2], argv[3])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
