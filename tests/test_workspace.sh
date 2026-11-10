#!/usr/bin/env bash
# Tests for skills/workspace-setup/scripts/check_workspace.py
# Uses only fixtures under tests/fixtures/workspace/ and the template, so changes to other
# areas' fixtures do not affect it.
set -u
cd "$(dirname "$0")/.."
S=skills/workspace-setup/scripts/check_workspace.py
F=tests/fixtures/workspace
pass=0; fail=0
check() { if [ "$1" = "$2" ]; then echo "ok   $3"; pass=$((pass+1)); else echo "FAIL $3 (exit $1, expected $2)"; fail=$((fail+1)); fi; }
has() { echo "$1" | grep -qF -- "$2"; check $? 0 "$3"; }
hasnt() { echo "$1" | grep -qF -- "$2"; check $? 1 "$3"; }

python3 $S >/dev/null 2>&1; check $? 2 "usage without arguments"

# Basic checks
python3 $S $F/complete.json >/dev/null; check $? 0 "complete config passes"
out=$(python3 $S $F/complete.json)
has "$out" '"warnings": []' "complete config has no warnings"
python3 $S templates/workspace.example.json >/dev/null; check $? 1 "template with placeholders fails"
out=$(python3 $S templates/workspace.example.json)
has "$out" "no TEST copy" "missing TEST copy reported"
hasnt "$out" "run.full_run" "template keys are valid"
hasnt "$out" "calendar.statuses" "template statuses are valid"
python3 $S $F/bad_regex.json >/dev/null; check $? 1 "bad regex and non-Monday week 1 fail"
has "$(python3 $S $F/bad_regex.json)" "not a Monday" "non-Monday reported"
has "$(python3 $S $F/missing_sources.json)" "Required source 'calendar'" "missing required source reported"

# A minimal config passes: every run, requests, proof and learning key is optional
python3 $S $F/v1_config.json >/dev/null; check $? 0 "config without optional keys passes"
out=$(python3 $S $F/v1_config.json)
has "$out" "no Fallback post, Backlog" "six-value status list warned"

# calendar.tabs object form for guarded tabs
T=$(mktemp -d)
python3 -c "import json,sys;c=json.load(open('$F/complete.json'));c['calendar']['tabs']['ideas']={'tab':'Post ideas','key':'Idea','status':'Status'};json.dump(c,open('$T/obj.json','w'));c['calendar']['tabs']['agent_log']={'tab':'Log'};json.dump(c,open('$T/obj_bad.json','w'))"
python3 $S $T/obj.json >/dev/null; check $? 0 "calendar.tabs object form for a guarded tab passes"
python3 $S $T/obj_bad.json >/dev/null; check $? 1 "calendar.tabs object form for another tab fails"
rm -rf "$T"

# Bad values
python3 $S $F/bad_v2.json >/dev/null; check $? 1 "bad values fail"
out=$(python3 $S $F/bad_v2.json)
has "$out" "run.full_run.weekday 'Mon'" "bad full run weekday"
has "$out" "run.full_run.time must be HH:MM" "bad full run time"
has "$out" "run.requests_runs.weekdays" "bad requests weekdays"
has "$out" "run.requests_runs.time must be HH:MM" "bad requests time"
has "$out" "dates.typed_order" "bad typed date order"
has "$out" "calendar.week_numbering must be iso" "non-ISO week numbering"
has "$out" "alternation_anchor_week" "week 54 anchor refused"
has "$out" "agent_statuses has Approved" "agents may not set Approved"
has "$out" "request_columns has Status" "asks may not change Status"
has "$out" "requests.enabled must be true or false" "non-boolean requests.enabled"
has "$out" "notes.agent_lines_kept" "agent_lines_kept of 0 refused"
has "$out" "must not include Yes" "Yes cannot mean not signed off"
has "$out" "edit_learning.examples_per_draft" "examples_per_draft out of range"
has "$out" "series.draft_within_days" "string draft_within_days refused"
has "$out" "plan.precedence" "unknown precedence refused"
has "$out" "run.weekday and run.full_run.weekday differ" "legacy run.weekday mismatch warned"

# Warnings that do not fail
python3 $S $F/warnings_v2.json >/dev/null; check $? 0 "warning-only config passes"
out=$(python3 $S $F/warnings_v2.json)
has "$out" "approver_word_is_signoff is on" "sign-off option on is warned"
has "$out" "both the full run day and a requests run day" "overlapping run days warned"
has "$out" "'Jordan Blake', who is not in company.people" "unknown requester warned"

echo "passed $pass, failed $fail"
[ $fail -eq 0 ]
