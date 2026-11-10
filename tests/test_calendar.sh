#!/usr/bin/env bash
# Tests for the calendar-builder scripts against fictional Brightwell fixtures.
# Usage: bash tests/test_calendar.sh   (exits non-zero on any failure)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$ROOT/skills/calendar-builder/scripts"
F="$ROOT/tests/fixtures/calendar"
EX="$ROOT/skills/calendar-builder/examples/sample-rows.json"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fails=0

check() {  # check <name> <expected exit> <actual exit> [<file> <pattern that must appear>]
  local name="$1" want="$2" got="$3"
  if [ "$want" != "$got" ]; then
    echo "FAIL $name: exit $got, expected $want"; fails=$((fails + 1)); return
  fi
  if [ $# -ge 5 ] && ! grep -qE -- "$5" "$4"; then
    echo "FAIL $name: output does not match '$5'"; fails=$((fails + 1)); return
  fi
  echo "ok   $name"
}

# Usage text on missing arguments
python3 "$S/tab_guard.py" >/dev/null 2>"$TMP/u1"; check "tab_guard usage" 2 $? "$TMP/u1" "Usage"
python3 "$S/verify_calendar.py" >/dev/null 2>"$TMP/u2"; check "verify_calendar usage" 2 $? "$TMP/u2" "Usage"
python3 "$S/build_calendar.py" >/dev/null 2>"$TMP/u3"; check "build_calendar usage" 2 $? "$TMP/u3" "Usage"

# tab_guard: nothing changed, every write accepted
python3 "$S/tab_guard.py" "$F/ideas_before.json" "$F/ideas_fresh_same.json" "$F/ideas_writes.json" \
  --key "Idea (one line)" --config "$F/workspace.json" >"$TMP/g1"
check "tab_guard accepts unchanged rows" 0 $? "$TMP/g1" '"range": "Ideas!G2"'
grep -q '"range": "Ideas!F3"' "$TMP/g1" && echo "ok   tab_guard exact range for row 3" || { echo "FAIL tab_guard row 3 range"; fails=$((fails + 1)); }

# tab_guard: row 2 Status set to Declined, rows 3 and 4 sorted during the run
python3 "$S/tab_guard.py" "$F/ideas_before.json" "$F/ideas_fresh_changed.json" "$F/ideas_writes.json" \
  --key "Idea (one line)" >"$TMP/g2"
check "tab_guard skips changed rows" 1 $? "$TMP/g2" "Status on Ideas row 2"
grep -q "deleted, inserted or sorted" "$TMP/g2" && echo "ok   tab_guard reports sorted row" || { echo "FAIL tab_guard sorted row"; fails=$((fails + 1)); }
python3 -c "import json,sys; d=json.load(open('$TMP/g2')); sys.exit(0 if d['accepted']==[] and len(d['skipped'])==5 and len(d['brief_lines'])==2 else 1)"
check "tab_guard writes a row in full or not at all" 0 $?

# tab_guard: milestone cancelled during the run
python3 "$S/tab_guard.py" "$F/milestones_before.json" "$F/milestones_fresh.json" "$F/milestones_writes.json" \
  --key "Milestone" >"$TMP/g3"
check "tab_guard milestone cancelled" 1 $? "$TMP/g3" "Confirmed on Milestones row 2"

# tab_guard: the approver's notes tab (quoted tab name), unchanged and with a Fact changed during the run
python3 "$S/tab_guard.py" "$F/notes_before.json" "$F/notes_fresh_same.json" "$F/notes_writes.json" \
  --key "Date added" --config "$F/workspace.json" >"$TMP/g4"
check "tab_guard approver notes accepted" 0 $? "$TMP/g4" "\"range\": \"'From the approver''s notes'!F3\""
python3 "$S/tab_guard.py" "$F/notes_before.json" "$F/notes_fresh_changed.json" "$F/notes_writes.json" \
  --key "Date added" >"$TMP/g5"
check "tab_guard approver notes fact changed" 1 $? "$TMP/g5" "Fact on From the approver's notes row 3"
python3 -c "import json,sys; d=json.load(open('$TMP/g5')); sys.exit(0 if len(d['accepted'])==1 and d['accepted'][0]['range'].endswith('!F2') else 1)"
check "tab_guard approver notes keeps the unchanged row" 0 $?

# tab_guard: a tab renamed in calendar.tabs (string value)
python3 -c "import json; c=json.load(open('$F/workspace.json')); c['calendar']['tabs']['ideas']='Post ideas'; json.dump(c, open('$TMP/ws_tabs.json','w'))"
python3 "$S/tab_guard.py" "$F/ideas_before.json" "$F/ideas_fresh_same.json" "$F/ideas_writes.json" \
  --key "Idea (one line)" --config "$TMP/ws_tabs.json" >"$TMP/g6"
check "tab_guard renamed tab" 0 $? "$TMP/g6" "\"range\": \"'Post ideas'!G2\""

# tab_guard: unknown key
python3 "$S/tab_guard.py" "$F/milestones_before.json" "$F/milestones_fresh.json" "$F/milestones_writes.json" \
  --key "Nope" >/dev/null 2>&1
check "tab_guard rejects unknown key" 2 $?

# verify_calendar: matching JSON export (formatted dates, ISO weeks, a Fallback post row left out)
python3 "$S/verify_calendar.py" "$F/plan_layout.txt" "$F/calendar.json" --config "$F/workspace.json" --expect 13 >"$TMP/v1"
check "verify_calendar match (json)" 0 $? "$TMP/v1" "Mismatches: 0"
grep -q "Plan rows parsed: 13; calendar rows: 13" "$TMP/v1" && echo "ok   verify_calendar parses wrapped rows, skips -FB" || { echo "FAIL verify_calendar row count"; fails=$((fails + 1)); }
python3 "$S/verify_calendar.py" "$F/plan_layout.txt" "$F/calendar.json" >"$TMP/v5"
check "verify_calendar without plan.week1_monday" 0 $? "$TMP/v5" "Mismatches: 0"

# verify_calendar: plan week numbers in Week and Row ID instead of ISO weeks
python3 "$S/verify_calendar.py" "$F/plan_layout.txt" "$F/calendar_planweeks.json" --config "$F/workspace.json" >"$TMP/v4"
check "verify_calendar rejects plan week numbers" 1 $? "$TMP/v4" "W01-01\) Week column: plan=10 calendar=1"
grep -q "Row ID week: plan='W10-' calendar='W01-'" "$TMP/v4" && echo "ok   verify_calendar checks Row ID week" || { echo "FAIL verify_calendar Row ID week"; fails=$((fails + 1)); }

# verify_calendar: two mismatches and a wrong stated count
python3 "$S/verify_calendar.py" "$F/plan_layout.txt" "$F/calendar_mismatch.json" --expect 14 >"$TMP/v2"
check "verify_calendar mismatch" 1 $? "$TMP/v2" "Mismatches: 3"
grep -q "W10-03) AM/PM" "$TMP/v2" && grep -q "W11-02) title" "$TMP/v2" && echo "ok   verify_calendar names each mismatch" || { echo "FAIL verify_calendar mismatch lines"; fails=$((fails + 1)); }

# build_calendar (needs openpyxl) and an end-to-end verify on the .xlsx
if python3 -c "import openpyxl" 2>/dev/null; then
  python3 "$S/build_calendar.py" "$EX" "$TMP/cal.xlsx" --config "$F/workspace.json" >"$TMP/b1" 2>"$TMP/b1e"
  check "build_calendar builds" 0 $? "$TMP/b1" "14 rows, 2 backlog rows, 2 milestones, 2 ideas"
  [ ! -s "$TMP/b1e" ] && echo "ok   build_calendar maps every content type" || { echo "FAIL build_calendar warnings: $(cat "$TMP/b1e")"; fails=$((fails + 1)); }
  python3 "$S/verify_calendar.py" "$F/plan_layout.txt" "$TMP/cal.xlsx" --config "$F/workspace.json" >"$TMP/v3"
  check "verify_calendar match (xlsx)" 0 $? "$TMP/v3" "Mismatches: 0"
  python3 - "$TMP/cal.xlsx" <<'PYEOF'
import sys
from openpyxl import load_workbook
wb = load_workbook(sys.argv[1])
assert wb.sheetnames == ["This Week", "Calendar", "Backlog", "Ideas", "Milestones", "From the approver's notes",
                         "Agent log", "Approver edits", "Agent snapshot", "How to use"], wb.sheetnames
assert wb["Agent snapshot"].sheet_state == "hidden"
assert [c.value for c in wb["Agent snapshot"][1]][:2] == ["Kind", "Key"]
assert [c.value for c in wb["From the approver's notes"][1]][3] == "Fact"
assert wb["From the approver's notes"]["D2"].value.startswith("Most sites")
ws = wb["Calendar"]
hdr = [c.value for c in ws[1]]
assert len(hdr) == 22 and hdr[0] == "Date" and hdr[21] == "Original draft", hdr
assert ws["M2"].value == "W10-01" and ws["N2"].value == 10, (ws["M2"].value, ws["N2"].value)
assert ws["C2"].value == "LinkedIn post: partner news" and ws["D2"].value == "Partner & Customer Proof"
assert ws["G2"].value is None and ws["H2"].value is None
ids = [ws.cell(r, 13).value for r in range(2, ws.max_row + 1)]
assert ids[ids.index("W11-01") + 1] == "W11-01-FB", ids
row = {v: r for r, v in enumerate(ids, 2)}
assert ws.cell(row["W11-01-FB"], 2).value == "Fallback post"
assert ws.cell(row["W12-04"], 3).value == "LinkedIn post: Guide promotion"
assert ws.cell(row["W10-02"], 10).value.startswith("The team writes this")
assert all(ws.cell(r, 14).value == ws.cell(r, 1).value.isocalendar()[1] for r in range(2, ws.max_row + 1))
bl = wb["Backlog"]
bh = [c.value for c in bl[1]]
assert bh[:22] == hdr and bh[22:] == ["Moved to Backlog", "Was dated"], bh
assert bl["C2"].value == "LinkedIn post: advisory board announcement" and bl["D2"].value == "PR & Press"
assert bl["C3"].value == "LinkedIn post: partner recruitment" and bl["D3"].value == "Partner & Customer Proof"
how = [r[1] for r in wb["How to use"].iter_rows(min_row=2, values_only=True)]
assert len(how) == 16 and "day first: 2/12/26" in how[7] and "Backlog" in how[10] and '"drop"' in how[11], how
first = list(ws.conditional_formatting)[0]
assert str(first.sqref).startswith("A2:L") and first.rules[0].formula == ['$B2="Fallback post"'], first.sqref
print("ok   build_calendar layout, tabs, ISO weeks, fallback and backlog")
PYEOF
  [ $? -eq 0 ] || { echo "FAIL build_calendar layout"; fails=$((fails + 1)); }

  # Row IDs never reused across years; a Fallback post sits directly under its original
  python3 "$S/build_calendar.py" "$F/rows_years.json" "$TMP/years.xlsx" >/dev/null 2>"$TMP/b2e"
  check "build_calendar rows across years" 0 $?
  python3 -c "
from openpyxl import load_workbook
ws = load_workbook('$TMP/years.xlsx')['Calendar']
ids = [ws.cell(r, 13).value for r in range(2, ws.max_row + 1)]
assert ids == ['W02-01', 'W02-02', 'W02-03', 'W02-04', 'W02-04-FB', 'W02-05'], ids
" && echo "ok   build_calendar continues seq after an earlier year" || { echo "FAIL build_calendar seq across years"; fails=$((fails + 1)); }

  # Input errors: a Fallback post without -FB, a week that is not the ISO week
  python3 -c "
import json; d = json.load(open('$F/rows_years.json')); d['rows'][3]['row_id'] = 'W02-09'; json.dump(d, open('$TMP/bad_fb.json', 'w'))"
  python3 "$S/build_calendar.py" "$TMP/bad_fb.json" "$TMP/x.xlsx" >/dev/null 2>"$TMP/b3e"
  check "build_calendar rejects a fallback without -FB" 2 $? "$TMP/b3e" "needs Row ID <original>-FB"
  python3 -c "
import json; d = json.load(open('$F/rows_years.json')); d['rows'][0]['week'] = 1; json.dump(d, open('$TMP/bad_wk.json', 'w'))"
  python3 "$S/build_calendar.py" "$TMP/bad_wk.json" "$TMP/x.xlsx" >/dev/null 2>"$TMP/b4e"
  check "build_calendar rejects a non-ISO week" 2 $? "$TMP/b4e" "not the calendar \(ISO\) week"

  # How to use follows dates.typed_order and requests.enabled
  python3 -c "
import json; c = json.load(open('$F/workspace.json')); c['dates'] = {'typed_order': 'month_first'}; c['requests']['enabled'] = False
json.dump(c, open('$TMP/ws_mf.json', 'w'))"
  python3 "$S/build_calendar.py" "$EX" "$TMP/cal3.xlsx" --config "$TMP/ws_mf.json" >/dev/null 2>&1
  python3 -c "
from openpyxl import load_workbook
how = [r[1] for r in load_workbook('$TMP/cal3.xlsx')['How to use'].iter_rows(min_row=2, values_only=True)]
assert len(how) == 14 and any('month first: 12/2/26' in h for h in how) and not any('plain words' in h for h in how), how
" && echo "ok   build_calendar How to use follows config" || { echo "FAIL build_calendar How to use config"; fails=$((fails + 1)); }

  python3 "$S/build_calendar.py" "$EX" "$TMP/cal2.xlsx" --config "$F/workspace.json" --sheets-formulas >/dev/null 2>&1
  python3 -c "
from openpyxl import load_workbook
ws = load_workbook('$TMP/cal2.xlsx')['Calendar']
g = ws['G2'].value
assert 'Publish|Newsletter|Distribute' in g and ws['H2'].value.startswith('=ARRAYFORMULA')
assert 'Moves to the Backlog tab on the next run' in g and 'Backup post: to use it' in g
assert 'Review the draft; to finish it, see What' in g and g.count('(') == g.count(')'), g
" && echo "ok   build_calendar --sheets-formulas" || { echo "FAIL build_calendar --sheets-formulas"; fails=$((fails + 1)); }
else
  echo "skip build_calendar tests (openpyxl not installed)"
fi

echo
if [ "$fails" -gt 0 ]; then echo "$fails test(s) failed"; exit 1; fi
echo "All calendar tests passed"
