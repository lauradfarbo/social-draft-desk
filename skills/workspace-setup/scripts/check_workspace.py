#!/usr/bin/env python3
"""Validate a workspace.json before any agent uses it (workspace-setup).

Usage:
  python3 check_workspace.py workspace.json

Checks:
  errors    required sections and sources missing, unknown platform or kind, a write target
            (calendar, proof_log, drafts_folder, briefs_folder) with no TEST copy, placeholder
            values such as "<Sheet ID>", regexes that do not compile, bad word counts or dates, and
            bad values: run schedule (weekdays, HH:MM times), typed date order, week numbering, the
            alternation anchor week, statuses (agents may set only Proposed, Draft ready and
            Fallback post), request columns, tab names, proof types, requests, notes, proof
            sign-off, edit learning and series settings, plan precedence (all optional)
  warnings  recommended sources missing, docs with no expect_phrase, a missing approver,
            empty competitor or avoid lists, a full run day that is also
            a requests run day, approver_word_is_signoff turned on, unknown tab or proof keys
Prints {"ok": bool, "errors": [...], "warnings": [...], "sources": {...}}. Exit 1 on any error.
Writes nothing.
"""
import json
import re
import sys
from datetime import date

PLATFORMS = {"google_drive", "notion", "github", "sharepoint", "local", "url", "manual"}
KINDS = {"doc", "table", "file", "folder", "repo"}
REQUIRED = ["rules", "voice_guide", "facts_sheet", "calendar", "drafts_folder", "briefs_folder"]
RECOMMENDED = ["plan_rules", "proof_log", "long_form", "assets", "agent_register"]
WRITE_TARGETS = ["calendar", "proof_log", "drafts_folder", "briefs_folder"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DEFAULT_STATUSES = ["Proposed", "Planned", "Draft ready", "Fallback post", "Approved", "Posted",
                    "Cancelled", "Backlog"]
AGENT_STATUSES = {"Proposed", "Draft ready", "Fallback post"}
REQUEST_COLUMNS = {"Date", "What to post", "Pillar", "Channel", "Title / angle", "Content type", "Spec"}
GUARDED_TABS = {"ideas", "milestones", "approver_notes"}
TAB_KEYS = {"calendar", "backlog", "ideas", "milestones", "approver_notes", "agent_log",
            "approver_edits", "agent_snapshot", "this_week", "how_to_use"}
PROOF_KEYS = {"Partner", "Customer", "Advisor"}
PLACEHOLDER = re.compile(r"^<.*>$|https?://www\.notion\.so/<")


def is_placeholder(v):
    return isinstance(v, str) and bool(PLACEHOLDER.search(v.strip()))


def check_regex(where, pattern, errors):
    try:
        re.compile(pattern, re.I)
    except re.error as e:
        errors.append(f"{where}: regex does not compile ({e}).")


def sect(cfg, key):
    v = cfg.get(key)
    return v if isinstance(v, dict) else {}


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def str_list(v):
    return isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)


def check_int(where, v, lo, hi, errors):
    if v is None:
        return
    if not is_int(v) or v < lo or (hi is not None and v > hi):
        rng = f"{lo} or more" if hi is None else f"{lo} to {hi}"
        errors.append(f"{where} must be a whole number, {rng}.")


def check_bool(where, v, errors):
    if v is not None and not isinstance(v, bool):
        errors.append(f"{where} must be true or false.")


def check_v2(cfg, errors, warnings):
    """Light checks on the run, requests, proof and learning keys. Every key is optional; a missing key uses the default."""

    run = sect(cfg, "run")
    full = run.get("full_run")
    full_day = None
    if full is not None:
        if not isinstance(full, dict):
            errors.append("run.full_run must be an object with weekday and time.")
        else:
            full_day = full.get("weekday")
            if full_day is not None and full_day not in WEEKDAYS:
                errors.append(f"run.full_run.weekday '{full_day}' is not a weekday name (Monday to Sunday).")
            if full.get("time") is not None and not TIME.match(str(full["time"])):
                errors.append("run.full_run.time must be HH:MM (24-hour).")
    if run.get("weekday") and full_day and run["weekday"] != full_day:
        warnings.append("run.weekday and run.full_run.weekday differ: scripts use run.full_run.weekday.")
    req = run.get("requests_runs")
    if req is not None:
        if not isinstance(req, dict):
            errors.append("run.requests_runs must be an object with weekdays and time.")
        else:
            days = req.get("weekdays")
            if days is not None:
                if not isinstance(days, list) or any(d not in WEEKDAYS for d in days):
                    errors.append("run.requests_runs.weekdays must be a list of weekday names (Monday to Sunday).")
                elif full_day in days:
                    warnings.append(f"{full_day} is both the full run day and a requests run day: "
                                    "the requests run that day only handles what changed after the full run.")
            if req.get("time") is not None and not TIME.match(str(req["time"])):
                errors.append("run.requests_runs.time must be HH:MM (24-hour).")

    order = sect(cfg, "dates").get("typed_order")
    if order is not None and order not in ("day_first", "month_first"):
        errors.append("dates.typed_order must be day_first or month_first.")

    cal = sect(cfg, "calendar")
    wn = cal.get("week_numbering")
    if wn is not None and wn != "iso":
        errors.append("calendar.week_numbering must be iso (the only numbering supported).")
    anchor = cal.get("alternation_anchor_week")
    if anchor is not None:
        ok = isinstance(anchor, dict) and is_int(anchor.get("year")) and is_int(anchor.get("week"))
        if ok:
            try:
                date.fromisocalendar(anchor["year"], anchor["week"], 1)
            except ValueError:
                ok = False
        if not ok:
            errors.append("calendar.alternation_anchor_week must be {\"year\": YYYY, \"week\": 1 to 53} "
                          "and a week that exists in that year.")
    statuses = cal.get("statuses")
    if statuses is not None:
        if not str_list(statuses):
            errors.append("calendar.statuses must be a list of names.")
            statuses = None
        else:
            if "Cancelled" not in statuses:
                errors.append("calendar.statuses must include Cancelled: people drop a post with it.")
            missing = [x for x in DEFAULT_STATUSES if x not in statuses and x != "Cancelled"]
            if missing:
                warnings.append(f"calendar.statuses has no {', '.join(missing)}: those steps will not run.")
    agent = cal.get("agent_statuses")
    if agent is not None:
        if not str_list(agent):
            errors.append("calendar.agent_statuses must be a list of names.")
        else:
            bad = [x for x in agent if x not in AGENT_STATUSES]
            if bad:
                errors.append(f"calendar.agent_statuses has {', '.join(bad)}: agents may set only "
                              "Proposed, Draft ready and Fallback post. People set the rest.")
            if statuses:
                absent = [x for x in agent if x not in statuses]
                if absent:
                    errors.append(f"calendar.agent_statuses has {', '.join(absent)}, which is not in calendar.statuses.")
    rc = cal.get("request_columns")
    if rc is not None:
        if not str_list(rc):
            errors.append("calendar.request_columns must be a list of column names.")
        else:
            bad = [x for x in rc if x not in REQUEST_COLUMNS]
            if bad:
                errors.append(f"calendar.request_columns has {', '.join(bad)}: asks may change only "
                              f"{', '.join(sorted(REQUEST_COLUMNS))}.")
    tabs = cal.get("tabs")
    if tabs is not None:
        def tab_name(k, v):
            if isinstance(v, str) and v.strip():
                return v.strip()
            if k in GUARDED_TABS and isinstance(v, dict) and isinstance(v.get("tab"), str) and v["tab"].strip():
                return v["tab"].strip()
            return None
        if not isinstance(tabs, dict) or not all(tab_name(k, v) for k, v in tabs.items()):
            errors.append("calendar.tabs must map tab keys to tab names (ideas, milestones and approver_notes "
                          "may also be {\"tab\", \"key\", \"status\"} objects).")
        else:
            unknown = sorted(set(tabs) - TAB_KEYS)
            if unknown:
                warnings.append(f"calendar.tabs has unknown keys {unknown}; scripts ignore them.")
            names = [tab_name(k, v).lower() for k, v in tabs.items()]
            if len(names) != len(set(names)):
                errors.append("calendar.tabs gives two keys the same tab name.")
    pt = cal.get("proof_types")
    if pt is not None:
        if not isinstance(pt, dict) or not all(isinstance(v, str) and v.strip() for v in pt.values()):
            errors.append("calendar.proof_types must map Partner, Customer and Advisor to content types.")
        else:
            unknown = sorted(set(pt) - PROOF_KEYS)
            if unknown:
                warnings.append(f"calendar.proof_types has unknown proof types {unknown}.")

    rq = cfg.get("requests")
    if rq is not None:
        if not isinstance(rq, dict):
            errors.append("requests must be an object.")
        else:
            check_bool("requests.enabled", rq.get("enabled"), errors)
            frm = rq.get("from")
            if frm is not None:
                if not str_list(frm):
                    errors.append("requests.from must be a list: approver, team, or names from company.people.")
                else:
                    people = sect(cfg, "company").get("people") or []
                    for who in frm:
                        if who not in ("approver", "team") and who not in people:
                            warnings.append(f"requests.from names '{who}', who is not in company.people.")
            for k in ("series_drop_word", "hold_lift_word"):
                if k in rq and not (isinstance(rq[k], str) and rq[k].strip()):
                    errors.append(f"requests.{k} must be a word.")

    nt = cfg.get("notes")
    if nt is not None:
        if not isinstance(nt, dict):
            errors.append("notes must be an object.")
        else:
            if "agent_prefix" in nt and not (isinstance(nt["agent_prefix"], str) and nt["agent_prefix"].strip()):
                errors.append("notes.agent_prefix must be a word.")
            check_int("notes.agent_lines_kept", nt.get("agent_lines_kept"), 1, 5, errors)

    pr = cfg.get("proof")
    if pr is not None:
        if not isinstance(pr, dict):
            errors.append("proof must be an object.")
        else:
            check_bool("proof.approver_word_is_signoff", pr.get("approver_word_is_signoff"), errors)
            if pr.get("approver_word_is_signoff") is True:
                warnings.append("proof.approver_word_is_signoff is on: agents log news the approver gives "
                                "as signed-off proof. Confirm the approver may sign off for named organizations.")
            nsv = pr.get("not_signed_off_values")
            if nsv is not None:
                if not str_list(nsv):
                    errors.append("proof.not_signed_off_values must be a list of Sign-off status values.")
                elif any(x.strip().lower() == "yes" for x in nsv):
                    errors.append("proof.not_signed_off_values must not include Yes.")
            check_int("proof.advisor_horizon_days", pr.get("advisor_horizon_days"), 1, 366, errors)

    el = cfg.get("edit_learning")
    if el is not None:
        if not isinstance(el, dict):
            errors.append("edit_learning must be an object.")
        else:
            check_bool("edit_learning.enabled", el.get("enabled"), errors)
            check_int("edit_learning.examples_per_draft", el.get("examples_per_draft"), 0, 10, errors)
            check_int("edit_learning.monthly_proposals_max", el.get("monthly_proposals_max"), 0, 10, errors)
            check_int("edit_learning.min_supporting_edits", el.get("min_supporting_edits"), 1, None, errors)
            if el.get("min_supporting_edits") == 1:
                warnings.append("edit_learning.min_supporting_edits is 1: one edit can propose a voice guide change.")

    se = cfg.get("series")
    if se is not None:
        if not isinstance(se, dict):
            errors.append("series must be an object.")
        else:
            check_int("series.draft_within_days", se.get("draft_within_days"), 1, 91, errors)

    plan = sect(cfg, "plan")
    prec = plan.get("precedence")
    if prec is not None and prec != "dated_events_first":
        errors.append("plan.precedence must be dated_events_first (the only value supported).")
    for dep in plan.get("dependencies", []) or []:
        if isinstance(dep, dict) and "milestone_type" in dep and not (
                isinstance(dep["milestone_type"], str) and dep["milestone_type"].strip()):
            errors.append(f"plan dependency {dep.get('fact_id')}: milestone_type must be a Milestones Type value.")


def main(path):
    try:
        cfg = json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "errors": [f"Cannot read {path}: {e}"], "warnings": []}))
        return 1
    errors, warnings, summary = [], [], {}

    for section in ("company", "sources", "writing", "facts", "calendar"):
        if section not in cfg:
            errors.append(f"Section '{section}' is missing.")
    company = cfg.get("company", {})
    if not company.get("name"):
        errors.append("company.name is empty.")
    if not company.get("approver", {}).get("name"):
        warnings.append("No approver named. Notes and the brief will say 'the approver'.")

    sources = cfg.get("sources", {})
    for key in REQUIRED:
        if key not in sources:
            errors.append(f"Required source '{key}' is missing.")
    for key in RECOMMENDED:
        if key not in sources:
            warnings.append(f"Recommended source '{key}' is missing.")
    for key, s in sources.items():
        if key in ("shadow", "other"):
            continue
        if not isinstance(s, dict):
            errors.append(f"sources.{key} must be an object.")
            continue
        kind, plat = s.get("kind"), s.get("platform")
        if kind not in KINDS:
            errors.append(f"sources.{key}.kind '{kind}' is not one of {sorted(KINDS)}.")
        if plat not in PLATFORMS:
            errors.append(f"sources.{key}.platform '{plat}' is not one of {sorted(PLATFORMS)}.")
        if not s.get("live") or is_placeholder(s.get("live")):
            errors.append(f"sources.{key}.live is empty or still a placeholder.")
        if key in WRITE_TARGETS and (not s.get("test") or is_placeholder(s.get("test"))):
            errors.append(f"sources.{key} is written by agents but has no TEST copy.")
        if kind == "doc" and not s.get("expect_phrase"):
            warnings.append(f"sources.{key} has no expect_phrase, so a cut-off read cannot be caught.")
        if kind == "table" and not s.get("tab") and plat == "google_drive":
            warnings.append(f"sources.{key} has no tab name.")
        summary[key] = f"{plat}:{kind}"
    for i, s in enumerate(sources.get("other", []) or []):
        if not s.get("live") or not s.get("use"):
            warnings.append(f"sources.other[{i}] needs 'live' and 'use'.")

    w = cfg.get("writing", {})
    if w.get("spelling") not in ("US", "UK"):
        errors.append("writing.spelling must be US or UK.")
    if w.get("units") not in ("metric", "imperial"):
        errors.append("writing.units must be metric or imperial.")
    for t, rng in (w.get("word_count") or {}).items():
        if not (isinstance(rng, list) and len(rng) == 2 and 0 < rng[0] < rng[1]):
            errors.append(f"writing.word_count.{t} must be [min, max].")
    if not w.get("competitors"):
        warnings.append("writing.competitors is empty: no competitor names will be caught.")
    if not w.get("avoid_terms"):
        warnings.append("writing.avoid_terms is empty.")
    for r in w.get("custom_rules", []) or []:
        if r.get("level") not in ("fail", "warn"):
            errors.append(f"custom rule {r.get('id')}: level must be fail or warn.")
        check_regex(f"custom rule {r.get('id')}", r.get("regex", ""), errors)
        if r.get("unless_regex"):
            check_regex(f"custom rule {r.get('id')} unless", r["unless_regex"], errors)
        if not r.get("message"):
            errors.append(f"custom rule {r.get('id')}: message is empty.")
    for r in w.get("on_hold_topics", []) or []:
        check_regex("on_hold_topics", r.get("regex", ""), errors)
    for c in (w.get("hashtags") or {}).get("conditional", []) or []:
        check_regex("hashtags.conditional", c.get("if_regex", ""), errors)

    cal = cfg.get("calendar", {})
    for k in ("team_owned_regex", "teaser_regex", "event_live_regex"):
        if cal.get(k):
            check_regex(f"calendar.{k}", cal[k], errors)

    plan = cfg.get("plan", {})
    if plan.get("week1_monday"):
        try:
            d = date.fromisoformat(plan["week1_monday"])
            if d.weekday() != 0:
                errors.append("plan.week1_monday is not a Monday.")
        except ValueError:
            errors.append("plan.week1_monday must be YYYY-MM-DD.")
    for dep in plan.get("dependencies", []) or []:
        try:
            date.fromisoformat(dep.get("deadline", ""))
        except ValueError:
            errors.append(f"plan dependency {dep.get('fact_id')}: deadline must be YYYY-MM-DD.")

    check_v2(cfg, errors, warnings)

    print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "sources": summary},
                     indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.stderr.write((__doc__ or "").strip() + "\n")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
