#!/usr/bin/env bash
# Tests for the weekly-orchestrator scripts backlog, edit_capture, notes_tidy, request_scan, save_result,
# series_shift and snapshot, against fictional Brightwell fixtures.
# Usage: bash tests/test_orchestrator_new.sh   (exits non-zero on any failure)
set -u
export PYTHONDONTWRITEBYTECODE=1
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$ROOT/skills/weekly-orchestrator/scripts"
F="$ROOT/tests/fixtures/orchestrator_new"
CFG="$F/workspace.json"
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
py() {  # py <name> <python assertions>
  if python3 -c "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi
}
cfgvar() {  # cfgvar <out> <python statement on c>
  python3 -c "import json; c=json.load(open('$CFG')); $2; json.dump(c, open('$1','w'))"
}
AS="--as-of 2026-03-16"

# ---- Usage text on missing arguments ----
for s in backlog edit_capture notes_tidy request_scan save_result series_shift snapshot; do
  python3 "$S/$s.py" >"$TMP/u_$s" 2>&1; check "$s usage" 2 $? "$TMP/u_$s" "Usage"
done
python3 "$S/backlog.py" hide "$F/calendar.json" >"$TMP/u_hide" 2>&1; check "backlog hide needs --sheet" 2 $? "$TMP/u_hide" "Usage"

# ---- request_scan ----
python3 "$S/request_scan.py" "$F/calendar.json" --config "$CFG" --ideas "$F/ideas.json" $AS > "$TMP/req.json"
check "request_scan runs" 0 $? "$TMP/req.json" '"notes_asks"'
py "request_scan finds plain asks, holds, standing and team lines" "
import json; d=json.load(open('$TMP/req.json')); a={x['row_id']:x for x in d['notes_asks']}
assert a['W12-02']['kind']=='ask' and not a['W12-02']['handled'] and a['W12-02']['ask'].startswith('Can we make this'), a['W12-02']
assert a['W13-02']['kind']=='standing' and a['W13-02']['handled']
assert a['W14-01']['kind']=='possible_ask' and 'hospital trust' in a['W14-01']['ask']
assert a['W14-02']['kind']=='hold_lift' and a['W14-02']['lift_date']=='23 APR 26'
assert a['W15-02']['from']=='Priya Nair' and a['W15-02']['accepted'] is False
assert 'W12-03' not in a, 'builder boilerplate is not an ask'
assert not any(x['row_id'] in ('W15-01','W16-01','W14-03','W12-04') for x in d['notes_asks']), 'Cancelled, Backlog, Posted skipped'
assert d['open_asks']==2, d['open_asks']
i={x['idea']:x for x in d['ideas']}
assert len(i)==2 and i['Behind the scenes at the data team']['accepted'] is False
"
cfgvar "$TMP/cfg_team.json" "c['requests']['from']=['approver','team']; c['dates']['typed_order']='month_first'"
python3 "$S/request_scan.py" "$F/calendar.json" --config "$TMP/cfg_team.json" --ideas "$F/ideas.json" $AS > "$TMP/req2.json"
py "request_scan: team asks accepted, month-first dates" "
import json; d=json.load(open('$TMP/req2.json')); a={x['row_id']:x for x in d['notes_asks']}
assert a['W15-02']['accepted'] is True and all(x['accepted'] for x in d['ideas'])
assert 'lift_date' not in a['W14-02'] or a['W14-02']['kind']!='hold_lift', a['W14-02']
"
cfgvar "$TMP/cfg_off.json" "c['requests']['enabled']=False"
python3 "$S/request_scan.py" "$F/calendar.json" --config "$TMP/cfg_off.json" $AS > "$TMP/req3.json"
py "request_scan disabled by config" "
import json; d=json.load(open('$TMP/req3.json')); assert d['enabled'] is False and d['notes_asks']==[]"
python3 "$S/request_scan.py" "$F/calendar.json" $AS > "$TMP/req4.json"
check "request_scan runs with no config" 0 $? "$TMP/req4.json" '"W12-02"'

# ---- backlog plan ----
python3 "$S/backlog.py" plan "$F/calendar.json" "$F/backlog_tab.json" --config "$CFG" $AS > "$TMP/bplan.json"
check "backlog plan runs" 0 $? "$TMP/bplan.json" '"out"'
py "backlog plan: out and in rows" "
import json; d=json.load(open('$TMP/bplan.json'))
o=d['out']; assert [x['row_id'] for x in o]==['W14-03'] and len(o[0]['values'])==24
v=o[0]['values']; assert v[1]=='Backlog' and v[6]=='' and v[7]=='' and v[22]=='2026-03-16' and v[23]=='2026-04-03'
i={x['row_id']:x for x in d['in']}
assert i['W10-02']['date']=='02 APR 26' and 'asked' in i['W10-02']['reason']
w=i['W10-02']['values']; assert len(w)==22 and w[1]=='Planned' and w[6] is None and w[7] is None and w[13]=='14'
assert w[9].startswith('Use on 2/4/26 please. Agents 16 MAR 26: Back from the Backlog')
p=i['W09-01']; assert 'best free slot' in p['reason'] and p['values'][0]=='2026-03-23', p
assert d['backlog_count']==2
assert not any('W15-01' in l or 'W16-01' in l for l in d['brief_lines'])
"
cfgvar "$TMP/cfg_mf.json" "c['dates']['typed_order']='month_first'"
python3 "$S/backlog.py" plan "$F/calendar.json" "$F/backlog_tab.json" --config "$TMP/cfg_mf.json" $AS > "$TMP/bplan2.json"
py "backlog plan: month-first date in the past falls back to the best slot" "
import json; d=json.load(open('$TMP/bplan2.json')); i={x['row_id']:x for x in d['in']}
assert 'best free slot' in i['W10-02']['reason'], i['W10-02']['reason']"

# ---- backlog deletes: copy read back before delete ----
python3 "$S/backlog.py" deletes "$TMP/bplan.json" "$F/cal_b.json" "$F/cal_m.json" "$F/bl_b.json" "$F/bl_m.json" \
  --cal-sheet 0 --bl-sheet 7 > "$TMP/bdel.json"
check "backlog deletes with copies read back" 0 $? "$TMP/bdel.json" '"deleteDimension"'
py "backlog deletes: bottom-up, right rows" "
import json; d=json.load(open('$TMP/bdel.json')); r=[(x['deleteDimension']['range']['sheetId'], x['deleteDimension']['range']['startIndex']) for x in d['requests']]
assert r==[(0,9),(7,2),(7,1)], r
assert d['refused']==[]"
python3 "$S/backlog.py" deletes "$TMP/bplan.json" "$F/cal_b.json" "$F/cal_m.json" "$F/bl_b.json" "$F/bl_m_nocopy.json" \
  --cal-sheet 0 --bl-sheet 7 > "$TMP/bdel2.json"
check "backlog deletes refuses without the copy" 1 $? "$TMP/bdel2.json" 'Copy not found on the Backlog tab'
py "backlog deletes: source row kept when its copy is missing" "
import json; d=json.load(open('$TMP/bdel2.json'))
assert not any(x['deleteDimension']['range']['sheetId']==0 for x in d['requests'])"

# ---- backlog hide and sort ----
python3 "$S/backlog.py" hide "$F/calendar.json" --sheet 0 --hidden 3,10 --config "$CFG" > "$TMP/hide.json"
check "backlog hide runs" 0 $? "$TMP/hide.json" '"hiddenByUser"'
py "backlog hide: Cancelled hidden, others shown, no Row IDs named" "
import json; d=json.load(open('$TMP/hide.json'))
h=sorted((x['updateDimensionProperties']['range']['startIndex'], x['updateDimensionProperties']['properties']['hiddenByUser']) for x in d['requests'])
assert h==[(2,False),(9,False),(10,True),(13,True)], h
assert d['hidden_count']==2 and d['shown_count']==2
s=json.dumps(d); assert 'W15-01' not in s and 'W16-01' not in s"
python3 "$S/backlog.py" sort "$F/calendar.json" --sheet 0 > "$TMP/sort.json"
check "backlog sort runs" 0 $? "$TMP/sort.json" '"sortRange"'
py "backlog sort: Date, AM/PM, Row ID below the header" "
import json; r=json.load(open('$TMP/sort.json'))['requests'][0]['sortRange']
assert r['range']['startRowIndex']==1 and r['range']['endRowIndex']==16 and r['range']['endColumnIndex']==22
assert [s['dimensionIndex'] for s in r['sortSpecs']]==[0,14,12]"

# ---- snapshot save and compare ----
python3 "$S/snapshot.py" save "$F/calendar_prev.json" "$F/milestones_prev.json" --config "$CFG" --as-of 2026-03-09 > "$TMP/snap.json"
check "snapshot save runs" 0 $? "$TMP/snap.json" "Agent snapshot'!A1:L18"
py "snapshot save: fingerprints text, keeps Date and Status" "
import json; d=json.load(open('$TMP/snap.json')); v=d['values']
assert v[0]==['Kind','Key','Date','Status','What to post','Pillar','Channel','Title / angle','Content type','Spec','Confirmed','Saved']
r={x[1]:x for x in v[1:] if x[0]=='row'}
assert r['W12-01'][2]=='Tue 17 MAR 26' and r['W12-01'][3]=='Planned' and r['W12-01'][7].startswith('#') and r['W12-01'][11]=='09 MAR 26'
m={x[1]:x for x in v[1:] if x[0]=='milestone'}; assert m['Spring webinar'][10]=='No'"
python3 -c "import json; d=json.load(open('$TMP/snap.json')); d['values']+= [['row','W99-01']+['']*10]*3; json.dump(d, open('$TMP/snap_long.json','w'))"
python3 "$S/snapshot.py" save "$F/calendar_prev.json" "$F/milestones_prev.json" "$TMP/snap_long.json" --config "$CFG" > "$TMP/snap_pad.json"
py "snapshot save pads to clear a longer old snapshot" "
import json; d=json.load(open('$TMP/snap_pad.json')); assert len(d['values'])==21 and d['values'][-1]==['']*12, len(d['values'])"
python3 "$S/snapshot.py" compare "$F/calendar.json" "$F/milestones.json" "$TMP/snap.json" --config "$CFG" > "$TMP/cmp.json"
check "snapshot compare runs" 0 $? "$TMP/cmp.json" '"row_changes"'
py "snapshot compare detects hand edits" "
import json; d=json.load(open('$TMP/cmp.json')); assert d['first_run'] is False
r={x['row_id']:x for x in d['row_changes']}
assert set(r)=={'W12-01','W12-02'}, set(r)
assert r['W12-01']['changed']=={'Date':['Tue 17 MAR 26','Wed 25 MAR 26']}
assert r['W12-02']['changed']['Title / angle'][1]=='make this a call-out to installers' and r['W12-02']['instruction']==['Title / angle']
m={x['milestone']:x for x in d['milestone_changes']}
assert m['Facilities Expo 2026']['changed']['Start date']==['12 MAY 26','19 MAY 26'] and m['Spring webinar']['confirmed_now'] is True
s=json.dumps(d); assert 'W15-01' not in s and 'W16-01' not in s and 'W14-03' not in s"
python3 "$S/snapshot.py" compare "$F/calendar_prev.json" "$F/milestones_prev.json" "$TMP/snap.json" --config "$CFG" > "$TMP/cmp0.json"
py "snapshot compare: no change, nothing reported" "
import json; d=json.load(open('$TMP/cmp0.json')); assert d['row_changes']==[] and d['milestone_changes']==[]"
python3 "$S/snapshot.py" compare "$F/calendar.json" "$F/milestones.json" "$TMP/missing.json" > "$TMP/cmp1.json"
py "snapshot compare: missing snapshot is a first run" "
import json; d=json.load(open('$TMP/cmp1.json')); assert d['first_run'] is True and d['row_changes']==[]"

# ---- series_shift ----
python3 "$S/series_shift.py" "$F/calendar.json" "$TMP/snap.json" --config "$CFG" $AS > "$TMP/ser.json"
check "series_shift runs" 0 $? "$TMP/ser.json" '"series shift"'
py "series_shift on move keeps order and lists clashes" "
import json; d=json.load(open('$TMP/ser.json'))
dw={w['row']:w['value'] for w in d['writes'] if w['col']=='Date'}
assert dw=={6:'2026-03-31', 8:'2026-04-07'}, dw
assert all(w['series'] is True and w['request']=='series shift' for w in d['writes'])
assert 'W15-03' in d['notes']['W14-01'] and 'Sam Ortega to decide' in d['notes']['W14-01']
assert 'also holds' not in d['notes']['W13-01']
"
py "series_shift on cancel pushes the series back one slot" "
import json; d=json.load(open('$TMP/ser.json'))
t={(w['row'],w['col']):w['value'] for w in d['writes'] if w['col']!='Date'}
assert t[(15,'Title / angle')].startswith('Advisory board post 1 of 3') and t[(16,'Title / angle')].startswith('Advisory board post 2 of 3')
assert t[(15,'Spec')]=='Photo of the panel' and t[(16,\"What's missing\")]=='Finance lead name'
assert not any(w['row']==14 for w in d['writes']), 'the Cancelled row is never written'
n=d['new_rows']; assert len(n)==1 and n[0]['row_id']=='W19-01' and n[0]['date']=='07 MAY 26'
v=n[0]['values']; assert v[1]=='Proposed' and v[5].startswith('Advisory board post 3 of 3') and v[6] is None and v[13]=='19' and v[20]==''
s=json.dumps({k:d[k] for k in ('notes','brief_lines','new_rows')}); assert 'W16-01' not in s and 'W15-01' not in s, 'Cancelled rows never named'
assert d['_internal']['pushed_back']==1
"
python3 "$S/series_shift.py" "$F/calendar_drop.json" "$TMP/snap.json" --config "$CFG" $AS > "$TMP/ser2.json"
py "series_shift on cancel with drop keeps the dates" "
import json; d=json.load(open('$TMP/ser2.json'))
assert all(w['col']=='Date' for w in d['writes']) and d['new_rows']==[] and d['_internal']['dropped']==1
assert not any('W16-01' in l for l in d['brief_lines'])"
cfgvar "$TMP/cfg_drop.json" "c['requests']['series_drop_word']='skip'"
python3 "$S/series_shift.py" "$F/calendar_drop.json" "$TMP/snap.json" --config "$TMP/cfg_drop.json" $AS > "$TMP/ser3.json"
py "series_shift uses the configured drop word" "
import json; d=json.load(open('$TMP/ser3.json')); assert len(d['new_rows'])==1 and d['_internal']['dropped']==0"
python3 "$S/series_shift.py" "$F/calendar.json" "$TMP/missing.json" > "$TMP/ser4.json"
py "series_shift with no snapshot does nothing" "
import json; d=json.load(open('$TMP/ser4.json')); assert d['writes']==[] and d['new_rows']==[]"

# ---- edit_capture ----
python3 "$S/edit_capture.py" "$F/calendar.json" "$F/tab_texts.json" "$F/approver_edits.json" --config "$CFG" $AS \
  --prompts "$F/prompts.json" > "$TMP/edits.json"
check "edit_capture runs" 0 $? "$TMP/edits.json" "Approver edits'!A3:I5"
py "edit_capture: light edit, rewrite, prompt edit; skips unchanged and Cancelled" "
import json; d=json.load(open('$TMP/edits.json')); r=[(x[1],x[2],x[4].split(' (')[0]) for x in d['rows']]
assert r==[('W12-04','Industry POV','Rewrite'),('W13-02','Poll','Light edit'),('W13-02','Image prompt: Poll','Prompt edit')], r
assert all(x[7]=='' for x in d['rows']) and 'Sam Ortega' in d['brief_lines'][0]
s=json.dumps(d); assert 'W15-01' not in s and 'W15-02' not in s"
python3 -c "
import json; e=json.load(open('$F/approver_edits.json')); d=json.load(open('$TMP/edits.json')); e['values']+=d['rows']
json.dump(e, open('$TMP/edits_logged.json','w'))"
python3 "$S/edit_capture.py" "$F/calendar.json" "$F/tab_texts.json" "$TMP/edits_logged.json" --config "$CFG" $AS \
  --prompts "$F/prompts.json" > "$TMP/edits2.json"
py "edit_capture logs each version once" "
import json; d=json.load(open('$TMP/edits2.json')); assert d['rows']==[] and d['range']==''"
cfgvar "$TMP/cfg_noedit.json" "c['edit_learning']['enabled']=False"
python3 "$S/edit_capture.py" "$F/calendar.json" "$F/tab_texts.json" "$F/approver_edits.json" --config "$TMP/cfg_noedit.json" > "$TMP/edits3.json"
py "edit_capture off by config" "
import json; d=json.load(open('$TMP/edits3.json')); assert d['rows']==[] and d['enabled'] is False"

# ---- notes_tidy ----
python3 "$S/notes_tidy.py" "$F/calendar.json" --report --config "$CFG" > "$TMP/tidy_rep.json"
check "notes_tidy report runs" 0 $? "$TMP/tidy_rep.json" '"agent_lines": 2'
python3 "$S/notes_tidy.py" "$F/calendar.json" "$F/current.json" --config "$CFG" $AS --log "$F/agent_log.json" > "$TMP/tidy.json"
check "notes_tidy runs" 0 $? "$TMP/tidy.json" '"tidy": true'
py "notes_tidy never drops a person's words" "
import json; d=json.load(open('$TMP/tidy.json')); w={(x['row'],x['col']):x['value'] for x in d['writes']}
assert w[(5,'Notes')]=='Can we make this about heat pump reporting instead? Agents 16 MAR 26: Retitled as asked in Notes; drafts this run.'
assert w[(8,'Notes')].startswith('Could we use the hospital trust story here? Agents 16 MAR 26:'), w[(8,'Notes')]
assert w[(7,'Notes')].startswith('Sam Ortega, 12 MAR 26: Keep this one short. Agents 16 MAR 26: Draft ready')
assert w[(6,'Notes')]=='Agents 16 MAR 26: Waiting for the customer story sign-off; drafts once it is logged.'
assert w[(6,'Sources')]=='Facts A01; long-form ch2'
assert not any(x['row']==11 for x in d['writes']), 'Cancelled row never written'
logged=[(r[1],r[3]) for r in d['log_rows']]
assert ('W13-01','Agents 16 MAR 26: Still waiting for sign-off.') in logged
assert ('W13-01','Agents 09 MAR 26: Waiting for the customer story.') not in logged, 'already in the Agent log'
assert ('W14-01','Agents 09 MAR 26: Waiting for the customer story.') in logged
assert d['log_range']==\"'Agent log'!A3:E6\", d['log_range']
"
cfgvar "$TMP/cfg_keep2.json" "c['notes']['agent_lines_kept']=2"
python3 "$S/notes_tidy.py" "$F/calendar.json" "$F/current.json" --config "$TMP/cfg_keep2.json" $AS > "$TMP/tidy2.json"
py "notes_tidy keeps one older agent line when agent_lines_kept is 2" "
import json; d=json.load(open('$TMP/tidy2.json')); w={(x['row'],x['col']):x['value'] for x in d['writes']}
assert w[(6,'Notes')]=='Agents 16 MAR 26: Still waiting for sign-off. Agents 16 MAR 26: Waiting for the customer story sign-off; drafts once it is logged.', w[(6,'Notes')]"
python3 "$S/notes_tidy.py" "$F/calendar.json" "$F/current_bad.json" --config "$CFG" $AS > "$TMP/tidy3.json" 2>&1
check "notes_tidy refuses a current line without the agent prefix" 1 $? "$TMP/tidy3.json" 'agent prefix'
python3 -c "
from importlib import util; import sys; sys.path.insert(0, '$S'); import notes_tidy as t
new, moved = t.tidy_notes('Agents 02 MAR 26: Proposed. Tom Adeyemi, 05 MAR 26: Keep the plant room photo. Agents 09 MAR 26: Planned.', 'Agents 16 MAR 26: Ready.', {})
assert new=='Tom Adeyemi, 05 MAR 26: Keep the plant room photo. Agents 16 MAR 26: Ready.', new
assert moved==['Agents 02 MAR 26: Proposed.', 'Agents 09 MAR 26: Planned.'], moved
" && echo "ok   notes_tidy keeps a person's line between agent lines" || { echo "FAIL notes_tidy person line between agent lines"; fails=$((fails + 1)); }

# ---- save_result ----
export SAVE_RESULT_TRANSCRIPTS="$F/*.jsonl"
python3 "$S/save_result.py" tool "$TMP/sr1.json" get_values "Calendar!A1:V" > "$TMP/sr1.out"
check "save_result tool, latest" 0 $? "$TMP/sr1.json" 'Thu 19 MAR 26'
python3 "$S/save_result.py" tool "$TMP/sr2.json" get_values "Calendar!A1:V" 2 > "$TMP/sr2.out"
check "save_result tool, second latest" 0 $? "$TMP/sr2.json" 'Tue 17 MAR 26'
python3 "$S/save_result.py" report "$TMP/sr3.json" '"row_id": "W12-02"' > "$TMP/sr3.out"
check "save_result report" 0 $? "$TMP/sr3.json" '"status": "pass"'
python3 "$S/save_result.py" tool "$TMP/sr4.json" read_doc nothing > "$TMP/sr4.out"
check "save_result no match" 1 $? "$TMP/sr4.out" 'no result'
unset SAVE_RESULT_TRANSCRIPTS
python3 "$S/save_result.py" tool "$TMP/sr5.json" get_values "Calendar!A1:V" --transcript "$F/transcript.jsonl" > "$TMP/sr5.out"
check "save_result tool, explicit --transcript" 0 $? "$TMP/sr5.json" 'Thu 19 MAR 26'
(cd "$TMP" && HOME="$TMP" python3 "$S/save_result.py" tool "$TMP/sr6.json" get_values "Calendar!A1:V") > "$TMP/sr6.out" 2>&1
check "save_result reads no other project's transcripts" 2 $? "$TMP/sr6.out" 'No session transcript found'

echo
if [ "$fails" -gt 0 ]; then echo "$fails test(s) failed"; exit 1; fi
echo "All orchestrator_new tests passed"
