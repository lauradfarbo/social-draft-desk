#!/usr/bin/env bash
# Tests for the weekly-orchestrator scripts against fictional Brightwell fixtures.
# Usage: bash tests/test_orchestrator.sh   (exits non-zero on any failure)
set -u
export PYTHONDONTWRITEBYTECODE=1
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$ROOT/skills/weekly-orchestrator/scripts"
F="$ROOT/tests/fixtures/orchestrator"
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
absent() {  # absent <name> <file> <pattern that must not appear>
  if grep -qE -- "$3" "$2"; then echo "FAIL $1: found '$3'"; fails=$((fails + 1)); else echo "ok   $1"; fi
}
py() { python3 -c "$1"; }

# check_draft.py comes from the short-form drafter; the orchestrator keeps a copy for check bundles.
if [ ! -f "$S/check_draft.py" ]; then
  echo "FAIL check_draft.py is missing from $S (copy it from skills/short-form-drafter/scripts)"; fails=$((fails + 1))
fi

# ---- Usage text on missing arguments ----
for s in calendar_writes select_rows plan_check swap_slots visuals make_bundles check_compliance extract_final doc_text; do
  python3 "$S/$s.py" >/dev/null 2>"$TMP/u_$s"; check "$s usage" 2 $? "$TMP/u_$s" "Usage"
done

# ---- select_rows ----
python3 "$S/select_rows.py" "$F/calendar.json" --config "$CFG" --facts "$F/facts.json" --milestones "$F/milestones.json" \
  --as-of 2026-03-16 --briefs 2026-03-02 > "$TMP/select.json"; check "select_rows runs" 0 $? "$TMP/select.json" '"W13-01"'
py "
import json; d=json.load(open('$TMP/select.json')); a={r['row_id']:r['action'] for r in d['rows']}
want={'W11-02':'overdue','W12-01':'proof','W12-02':'team_owned','W12-03':'draft','W12-04':'in_review',
      'W12-06':'blocked','W13-01':'draft','W13-02':'proof','W13-03':'proposed','W13-04':'draft','W13-05':'team_owned',
      'W13-06':'team_owned','W13-07':'refresh','W14-06':'draft'}
assert a==want, a
assert d['missed_runs']==['09 MAR 26'], d['missed_runs']
assert [x['row_id'] for x in d['final_text']]==['W11-01']
assert [x['row_id'] for x in d['approved_gaps']]==['W12-04'] and 'Sam Ortega to confirm' in d['approved_gaps'][0]['brief_line']
assert d['run_mode']=='full' and d['same_day_brief'] is False and d['brief_title']=='Weekly brief - 16 MAR 26' and 'requests' not in d
assert 'stop' not in d and d['first_full_run_of_month'] is False
assert 'cancelled' not in d['counts'] and d['_internal']=={'cancelled_skipped':1,'backlog_skipped':1}
r={x['row_id']:x for x in d['rows']}
assert r['W12-06']['reason'].startswith('On hold:'), r['W12-06']
assert 'Sam Ortega to review' in r['W13-03']['reason']
t=r['W12-03']; assert t['placeholders']==['[Blog 2 link]'] and 'W12-02' in t['gaps'][0] and t['whats_missing']==t['gaps'][0], t
f=r['W13-07']; assert f['blog_link']=='https://brightwell.example.com/blog/audit-trail' and f['gaps_left']==['[Blog 4 link]'], f
s=r['W14-06']; assert s['series'] is True and s['series_note']=='post 1 of 3' and s['proof_type']=='Advisor', s
assert all(x['week']==str(int(x['row_id'][1:3])) for x in d['rows']), [(x['row_id'],x['week']) for x in d['rows']]
" ; check "select_rows actions, base drafts, refresh, series, gaps, final text, missed runs" 0 $?
absent "select_rows never names the Cancelled or Backlog row" "$TMP/select.json" 'W12-05|W13-09|"Cancelled"|"Backlog"'

python3 "$S/select_rows.py" "$F/calendar.json" --config "$CFG" --as-of 2026-03-16 --briefs 2026-03-09,2026-03-16 \
  --touched W13-04 > "$TMP/same.json"
check "select_rows second run on the same day switches to requests mode" 0 $? "$TMP/same.json" '"run_mode": "requests"'
py "
import json; d=json.load(open('$TMP/same.json'))
assert d['same_day_brief'] is True and d['brief_title']=='Update - 16 MAR 26' and 'stop' not in d
q=d['requests']; assert q['active'] and q['reason']=='second run on the same day' and q['window_days']==14
assert {i['name'] for i in q['inputs']}=={'asks','hand_edits','ideas','backlog','series'} and 'planner' in q['skip']
assert sorted(x['row_id'] for x in d['rows'])==['W13-04','W13-07'] and q['refresh']==['W13-07'] and not q['nothing_to_do']
assert d['missed_runs']==[]
"; check "select_rows requests inputs: sources, skips, touched and refresh rows only" 0 $?
python3 "$S/select_rows.py" "$F/calendar.json" --config "$CFG" --as-of 2026-03-17 --mode requests --updates 2026-03-17 > "$TMP/req.json"
py "
import json; d=json.load(open('$TMP/req.json')); q=d['requests']
assert d['brief_title']=='Update - 17 MAR 26 (2)' and q['reason']=='requests mode' and [x['row_id'] for x in d['rows']]==['W13-07']
"; check "select_rows requests mode without touched rows keeps refresh rows; Update suffix" 0 $?
py "
import json; v=json.load(open('$F/calendar.json')); h=v['values'][0]
for r in v['values'][1:]:
    if r[h.index('Row ID')]=='W13-07': r[h.index('Original draft')]='Audit season is closer than it looks.'
json.dump(v,open('$TMP/cal_norefresh.json','w'))"
python3 "$S/select_rows.py" "$TMP/cal_norefresh.json" --config "$CFG" --as-of 2026-03-16 --mode requests > "$TMP/req0.json"
check "select_rows requests mode with nothing open says nothing_to_do" 0 $? "$TMP/req0.json" '"nothing_to_do": true'
python3 "$S/select_rows.py" "$F/calendar.json" --config "$CFG" --as-of 2026-03-16 --briefs 2026-03-16 --rerun > "$TMP/rerun.json"
check "select_rows rerun forces a full run with suffix (2)" 0 $? "$TMP/rerun.json" '"brief_suffix": " \(2\)"'
grep -q '"run_mode": "full"' "$TMP/rerun.json"; check "select_rows rerun stays a full run" 0 $?
python3 "$S/select_rows.py" "$F/calendar.json" --config "$CFG" --as-of 2026-03-02 > "$TMP/month.json"
check "select_rows first full run of the month" 0 $? "$TMP/month.json" '"first_full_run_of_month": true'

# Holds lift: a confirmed milestone of the dependency's type, or CONFIRMED with a date in the row's Notes.
py "
import json; m=json.load(open('$F/milestones.json')); m['values'].append(['Spring webinar','Webinar','2026-03-20','','Yes','Topic agreed',''])
json.dump(m,open('$TMP/ms_web.json','w'))
v=json.load(open('$F/calendar.json')); h=v['values'][0]
for r in v['values'][1:]:
    if r[h.index('Row ID')]=='W12-06': r[h.index('Notes')]+=' Sam, 15 MAR 26: CONFIRMED for 20 MAR 26.'
json.dump(v,open('$TMP/cal_conf.json','w'))"
python3 "$S/select_rows.py" "$F/calendar.json" --config "$CFG" --facts "$F/facts.json" --milestones "$TMP/ms_web.json" --as-of 2026-03-16 > "$TMP/sel_ms.json"
python3 "$S/select_rows.py" "$TMP/cal_conf.json" --config "$CFG" --facts "$F/facts.json" --as-of 2026-03-16 > "$TMP/sel_conf.json"
py "
import json
for f in ('$TMP/sel_ms.json','$TMP/sel_conf.json'):
    a={r['row_id']:r['action'] for r in json.load(open(f))['rows']}; assert a['W12-06']=='draft', (f,a['W12-06'])
"; check "select_rows: a confirmed milestone or CONFIRMED with a date lifts the hold" 0 $?

python3 "$S/select_rows.py" "$F/calendar.json" --config "$CFG" --as-of 2026-03-16 --shadow > "$TMP/shadow_sel.json"
check "select_rows shadow drafts Approved rows" 0 $? "$TMP/shadow_sel.json" '"live_status": "Approved"'
python3 "$S/select_rows.py" "$F/calendar.json" --as-of 2026-03-16 > "$TMP/nocfg.json"
check "select_rows without a config uses defaults" 0 $? "$TMP/nocfg.json" 'The approver to review'
py "
import json; c=json.load(open('$CFG')); c['calendar']['statuses']=['Proposed','Planned','Draft ready','Approved','Posted','Cancelled']
json.dump(c,open('$TMP/ws_v1.json','w'))"
python3 "$S/select_rows.py" "$F/calendar.json" --config "$TMP/ws_v1.json" --as-of 2026-03-16 > "$TMP/v1.json"
check "select_rows reads a six-status list" 0 $? "$TMP/v1.json" '"backlog_skipped": 1'

# ---- plan_check ----
python3 "$S/plan_check.py" "$F/calendar.json" "$F/facts.json" "$F/proof_log.json" --config "$CFG" \
  --milestones "$F/milestones.json" --as-of 2026-03-16 > "$TMP/plan.json"; check "plan_check runs" 0 $?
py "
import json; d=json.load(open('$TMP/plan.json'))
notes=[(n['row_id'],n['kind'],n['body']) for n in d['row_notes']]
txt=' '.join(b for _,_,b in notes); br=' '.join(d['brief_risks'])
assert any(r=='W14-01' and 'Partner Win in even weeks' in b for r,_,b in notes), notes
assert any(r=='W14-05' and 'more than one Poll' in b for r,_,b in notes), notes
assert any(r=='W14-05' and 'Good Friday (UK public holiday)' in b for r,_,b in notes), notes
assert any(r=='W15-01' and 'Easter Monday' in b for r,_,b in notes), notes
assert any(r=='W15-03' and 'Thursday slot rotates' in b for r,_,b in notes), notes
assert any(r=='W12-03' and k=='conditional_swap_date' and '19 MAR 26' in b and '18 MAR 26' in b for r,k,b in notes), notes
assert 'webinar topic (fact E01) is not approved' in br, br
assert 'W15-02 (07 APR 26): no Customer Proof item' in br, br
assert 'Spring Energy Forum' in br and 'W15-04' in br, br
assert 'W12-05' not in txt + br
assert 'Sam Ortega' in txt
assert d['holiday_market']=='UK' and d['notes']==[]
"; check "plan_check cadence, holidays, conditional swap date, dependency, proof, milestone" 0 $?
python3 "$S/plan_check.py" "$F/calendar.json" "$F/facts.json" --config "$CFG" --as-of 2026-03-20 > "$TMP/plan2.json"
check "plan_check dependency past deadline adds a swap note" 0 $? "$TMP/plan2.json" '"kind": "dependency_swap"'
py "
import json; c=json.load(open('$CFG')); c['company']['holiday_market']='DE'; json.dump(c,open('$TMP/ws_de.json','w'))
c2=json.load(open('$CFG')); c2['company'].pop('approver'); c2.pop('plan'); json.dump(c2,open('$TMP/ws_min.json','w'))"
python3 "$S/plan_check.py" "$F/calendar.json" "$F/facts.json" --config "$TMP/ws_de.json" --as-of 2026-03-16 > "$TMP/plan_de.json"
check "plan_check skips holidays for other markets with a note" 0 $? "$TMP/plan_de.json" "Holiday check skipped: no built-in public holidays for market 'DE'"
absent "plan_check DE has no holiday notes" "$TMP/plan_de.json" 'public holiday\)'
python3 "$S/plan_check.py" "$F/calendar.json" "$F/facts.json" --config "$TMP/ws_min.json" --as-of 2026-03-16 > "$TMP/plan_min.json"
check "plan_check with no plan section skips cadence checks" 0 $? "$TMP/plan_min.json" 'The approver'
absent "plan_check minimal config has no cadence notes" "$TMP/plan_min.json" 'odd weeks|rotates'
(cd "$S" && py "
import plan_check as p
from datetime import date
uk, nl, us = p.uk_holidays(2026), p.nl_holidays(2026), p.us_holidays(2026)
assert uk[date(2026,4,3)]=='Good Friday' and uk[date(2026,5,25)]=='Spring bank holiday' and uk[date(2026,12,28)].startswith('Boxing Day')
assert nl[date(2026,4,27)]==\"King's Day\" and nl[date(2026,5,14)]=='Ascension Day' and date(2025,5,5) in p.nl_holidays(2025)
assert us[date(2026,11,26)]=='Thanksgiving Day' and us[date(2026,9,7)]=='Labor Day'
assert p.easter(2027)==date(2027,3,28)
"); check "plan_check built-in US, UK and NL holidays" 0 $?

# plan_check: ISO weeks, alternation over the year end, two proof slots a week, dated events first, holds.
py "
import json; d=json.load(open('$TMP/plan.json'))
assert d['weeks']==[12,13,14,15] and 'precedence_moves' in d and d['precedence_moves']==[]
assert any(b.startswith('Week 14 (30 MAR 26)') for b in d['brief_risks']), d['brief_risks']
assert not any('W13-09' in json.dumps(n) for n in d['row_notes'])
"; check "plan_check labels ISO weeks and skips the Backlog row" 0 $?
py "
import json
c=json.load(open('$CFG')); p=c['plan']; p.pop('proof_slot')
p['proof_slots']=[{'weekday':'Tue','type':'Partner Win'},{'weekday':'Thu','type':'Customer Proof'}]
json.dump(c,open('$TMP/ws_slots.json','w'))
v=json.load(open('$F/calendar.json')); h=v['values'][0]; I=lambda k: h.index(k)
for r in v['values'][1:]:
    if r[I('Row ID')]=='W13-02': r[I('Date')]='Thu 26 MAR 26'
    if r[I('Row ID')]=='W13-04': r[I('Notes')]='Changed from Partner Win to Industry POV, as asked in Notes.'
ev=['Wed 01 APR 26','Planned','Live demo day','Reporting','LinkedIn','Live demo day: one report for every site','=formula','=formula','','','','','W14-07','14','AM','Event announcement','','','','','','']
v['values'].append(ev)
json.dump(v,open('$TMP/cal_slots.json','w'))"
python3 "$S/plan_check.py" "$TMP/cal_slots.json" "$F/facts.json" --config "$TMP/ws_slots.json" --milestones "$TMP/ms_web.json" --as-of 2026-03-16 > "$TMP/plan_slots.json"
check "plan_check with proof_slots runs" 0 $?
py "
import json; d=json.load(open('$TMP/plan_slots.json')); br=' '.join(d['brief_risks']); notes={(n['row_id'],n['body']) for n in d['row_notes']}
assert 'Week 12 (16 MAR 26) has no Customer Proof slot' in br, br
assert 'Week 13 (23 MAR 26) has no Partner Win' not in br, br
assert '26 MAR 26: the Customer Proof slot (W13-02) shares the day with W13-04.' in br, br
assert ('W14-06','The Customer Proof slot is planned for Thursday; this row is on a Monday.') in notes, notes
assert 'webinar topic' not in br, br
m={x['row_id']:x for x in d['precedence_moves']}
assert set(m)=={'W14-02','W14-03'} and m['W14-02']['to']=='2026-04-08' and m['W14-02']['event']=='W14-07', m
assert m['W14-02']['note'].startswith('Moved from 01 APR 26 to 08 APR 26: W14-07'), m
"; check "plan_check proof slots, Advisor fills Customer, converted slot, shared day, precedence, milestone lifts hold" 0 $?
py "
import json
h=json.load(open('$F/calendar.json'))['values'][0]
def row(d, rid, ct, ch='Website'):
    r={k:'' for k in h}; r.update({'Date':d,'Status':'Planned','Channel':ch,'Row ID':rid,'Content type':ct,'Title / angle':ct}); return [r[k] for k in h]
v={'values':[h,row('Wed 30 DEC 26','W53-01','Blog 9 - Publish'),row('Wed 30 DEC 26','W53-02','Blog 9 - LinkedIn teaser','LinkedIn'),
             row('Wed 06 JAN 27','W01-01','Blog 10 - Publish'),row('Wed 06 JAN 27','W01-02','Blog 10 - LinkedIn teaser','LinkedIn')]}
json.dump(v,open('$TMP/cal_ye.json','w'))"
python3 "$S/plan_check.py" "$TMP/cal_ye.json" "$F/facts.json" --config "$CFG" --as-of 2026-12-28 --weeks 2 > "$TMP/plan_ye.json"
py "
import json; d=json.load(open('$TMP/plan_ye.json')); ids={n['row_id'] for n in d['row_notes'] if 'blog pair' in n['body']}
assert d['weeks']==[53,1] and ids=={'W53-01'}, (d['weeks'], ids)
"; check "plan_check alternation runs on across week 53 and week 1" 0 $?
# ---- swap_slots ----
python3 "$S/swap_slots.py" "$F/calendar.json" "$TMP/select.json" "$F/match.json" --config "$CFG" --as-of 2026-03-16 \
  --drafter-blocked W12-03 > "$TMP/swaps.json"
check "swap_slots runs" 0 $?
py "
import json; d=json.load(open('$TMP/swaps.json')); s={x['row_id']:x for x in d['swaps']}
assert set(s)=={'W12-01','W12-03'}, s.keys()
assert s['W12-03']['existing'] and s['W12-03']['type']=='Poll' and s['W12-03']['chapter']=='2'
assert s['W12-03']['conditional'].endswith('by the morning of 18 MAR 26')
n=s['W12-01']; assert not n['existing'] and n['type'] in ('Industry POV','Poll','Guide push')
assert n['chapter']=='3' and '8' not in n['chapters_available'] and '1' not in n['chapters_available']
assert all(x['fallback'] for x in d['swaps'])
st=[(x['row_id'],x['kind'],x['old'],x['new']) for x in d['stale_notes']]
assert st==[('W12-03','teaser_condition','19 MAR 26','18 MAR 26')], st
"; check "swap_slots candidates, existing proposal, chapters, conditional date, stale teaser condition" 0 $?
python3 "$S/swap_slots.py" "$F/calendar.json" "$TMP/select.json" "$F/match.json" --config "$CFG" --as-of 2026-03-16 \
  --drafter-blocked W12-03 --max-fallbacks 1 > "$TMP/swaps1.json"
py "import json; assert json.load(open('$TMP/swaps1.json'))['fallbacks_skipped']==['W12-03']"
check "swap_slots respects the fallback cap" 0 $?
python3 "$S/swap_slots.py" "$F/calendar.json" "$TMP/select.json" "$F/match.json" --config "$CFG" --as-of 2026-03-16 > "$TMP/swaps_bd.json"
py "import json; assert [x['row_id'] for x in json.load(open('$TMP/swaps_bd.json'))['swaps']]==['W12-01']"
check "swap_slots: a base draft with a gap is not a swap candidate" 0 $?
py "
import json; v=json.load(open('$F/calendar.json')); h=v['values'][0]; rows=v['values']
orig=next(r for r in rows if r[h.index('Row ID')]=='W12-01'); fb=list(orig)
fb[h.index('Row ID')]='W12-01-FB'; fb[h.index('Status')]='Fallback post'; fb[h.index('Content type')]='Industry POV'
rows.insert(rows.index(orig)+1, fb)
w=next(r for r in rows if r[h.index('Row ID')]=='W13-02')
w[h.index('Notes')]='Agents 09 MAR 26: Proof intake: no signed-off item yet; if one is logged by 12 MAR 26, the next run drafts it.'
json.dump(v,open('$TMP/cal_fb.json','w'))
bl={'values':[h+['Moved to Backlog','Was dated'],['','Backlog','Energy myths','Reporting','LinkedIn','Five energy reporting myths','','','','','','','W09-04','9','AM','Industry POV','','','','','','','02 MAR 26','Tue 03 MAR 26']]}
json.dump(bl,open('$TMP/backlog.json','w'))"
python3 "$S/select_rows.py" "$TMP/cal_fb.json" --config "$CFG" --as-of 2026-03-16 > "$TMP/sel_fb.json"
python3 "$S/swap_slots.py" "$TMP/cal_fb.json" "$TMP/sel_fb.json" "$F/match.json" --config "$CFG" --as-of 2026-03-16 \
  --backlog "$TMP/backlog.json" > "$TMP/swaps_fb.json"
py "
import json; d=json.load(open('$TMP/swaps_fb.json')); s={x['row_id']:x for x in d['swaps']}
assert s['W12-01']['fallback'] is False and s['W12-01']['fallback_row_exists'] is True, s
assert 'W12-01-FB' not in s
assert s['W12-01']['backlog_options'][0]['row_id']=='W09-04', s['W12-01']
st=[(x['row_id'],x['kind'],x['old'],x['new']) for x in d['stale_notes']]
assert ('W13-02','cutoff_passed','12 MAR 26','22 MAR 26') in st, st
a={r['row_id']:r['action'] for r in json.load(open('$TMP/sel_fb.json'))['rows']}
assert a['W12-01-FB']=='fallback_row'
"; check "swap_slots: a -FB row means no new fallback; Backlog options; passed cut-off" 0 $?

python3 "$S/plan_check.py" "$TMP/cal_fb.json" "$F/facts.json" --config "$CFG" --as-of 2026-03-16 > "$TMP/plan_fb.json"
absent "plan_check ignores Fallback post rows" "$TMP/plan_fb.json" 'W12-01-FB'

# ---- visuals ----
python3 "$S/visuals.py" "$F/calendar.json" "$F/assets.txt" "$F/return_W13-01.json" "$F/return_W13-04.json" "$F/return_W13-02.json" \
  --config "$CFG" > "$TMP/vis.json"; check "visuals reports the real-photo clash (exit 1)" 1 $?
py "
import json; d=json.load(open('$TMP/vis.json')); r={x['row_id']:x for x in d['resolved']}
assert r['W13-01']['changed'] and 'dashboard-hero.png' in r['W13-01']['visual'], r
assert r['W13-01']['visual_alternatives']==[]
assert r['W13-04']['visual'].startswith('Needed: ImageGen image of') and not r['W13-04']['changed']
assert [u['row_id'] for u in d['unresolved']]==['W13-02'] and 'Real photo' in d['unresolved'][0]['reason']
"; check "visuals skips the Cancelled row's file, keeps the AI image, flags real-photo rows" 0 $?
py "
import json; c=json.load(open('$CFG')); c['visuals']['ai_image_tool']=None; json.dump(c,open('$TMP/ws_noai.json','w'))
r=json.load(open('$F/return_W13-01.json')); r['visual_alternatives']=[]; r['row_id']='W13-01'; json.dump(r,open('$TMP/W13-01.json','w'))"
python3 "$S/visuals.py" "$F/calendar.json" "$F/assets.txt" "$TMP/W13-01.json" --config "$TMP/ws_noai.json" > "$TMP/vis_noai.json"
check "visuals without an AI image tool asks for a photo or graphic" 0 $? "$TMP/vis_noai.json" 'Needed: photo or graphic'

# ---- make_bundles ----
RUN="$TMP/run"; SH="$RUN/shared"; mkdir -p "$SH"
for f in workspace.json calendar.json proof_log.json facts.json rules.md plan_rules.md voice.md assets.txt long_form.md brightwell-chapter-map.md milestones.json; do cp "$F/$f" "$SH/"; done
python3 "$S/make_bundles.py" "$RUN" "$ROOT" plan > "$TMP/mb_plan.json"; check "make_bundles plan" 0 $?
for f in workspace.json plan_check.py milestones.json calendar.json; do
  [ -f "$RUN/plan/$f" ]; check "plan bundle has $f" 0 $?
done
python3 "$S/make_bundles.py" "$RUN" "$ROOT" draft --rows W13-01 > /dev/null; check "make_bundles draft" 0 $?
for f in workspace.json row.json long_form.md chapter-map.md facts_approved.json recent.txt visuals_recent.txt assets.txt; do
  [ -f "$RUN/draft/W13-01/$f" ]; check "draft bundle has $f" 0 $?
done
[ ! -f "$RUN/draft/W13-01/guide.md" ]; check "draft bundle has no guide.md" 0 $?
grep -q "map for drafters" "$RUN/draft/W13-01/chapter-map.md"; check "chapter map copied from the config-named file" 0 $?
py "
import json; f=json.load(open('$SH/facts_approved.json'))
assert [x['id'] for x in f]==['A01','A04','C02'] and set(f[0])=={'id','claim','comments'}, f
"; check "facts_approved.json has approved facts only" 0 $?
absent "visuals_recent.txt skips the Cancelled row" "$RUN/draft/W13-01/visuals_recent.txt" 'W12-05'
grep -q "W11-01" "$RUN/draft/W13-01/visuals_recent.txt"; check "visuals_recent.txt lists rows in the window" 0 $?
python3 "$S/make_bundles.py" "$RUN" "$ROOT" proof --rows W12-01 --proof-rows 2 > /dev/null; check "make_bundles proof" 0 $?
grep -q "Northgate" "$RUN/proof/W12-01/proof_item.json" && [ -f "$RUN/proof/W12-01/workspace.json" ]; check "proof bundle has proof item and workspace.json" 0 $?
python3 "$S/make_bundles.py" "$RUN" "$ROOT" draft --rows W12-04 --shadow > /dev/null
grep -q '"Live status": "Approved"' "$RUN/draft/W12-04/row.json"; check "make_bundles shadow keeps the live status" 0 $?
py "
import json; d=json.load(open('$TMP/swaps.json'))
for x in d['swaps']: x['angle']=x.get('angle') or 'Why one dashboard beats twelve spreadsheets'
json.dump(d,open('$TMP/swaps_final.json','w'))"
python3 "$S/make_bundles.py" "$RUN" "$ROOT" fallback --rows W12-01 --swaps "$TMP/swaps_final.json" > /dev/null; check "make_bundles fallback" 0 $?
py "
import json; r=json.load(open('$RUN/fallback/W12-01/row.json')); fb=json.load(open('$RUN/fallback/W12-01/fallback.json'))
assert r['Status']=='Planned' and r['Title / angle'].startswith('Why one dashboard') and 'Guide ch3' in r['Spec'], r
assert 'W12-01-FB, Status Fallback post' in fb['note'] and 'Sam Ortega uses it' in fb['note'] and fb['chapter']=='3'
"; check "fallback bundle carries the swap, not the original row" 0 $?
python3 "$S/make_bundles.py" "$RUN" "$ROOT" check --draft "$F/draft_pass.json" > /dev/null; check "make_bundles check (pass draft)" 0 $?
python3 "$S/make_bundles.py" "$RUN" "$ROOT" check --draft "$F/draft_fail.json" > /dev/null; check "make_bundles check (fail draft)" 0 $?
for f in workspace.json draft.json check_compliance.py check_draft.py assets.txt visuals_recent.txt facts.json; do
  [ -f "$RUN/check/W13-01/$f" ]; check "check bundle has $f" 0 $?
done
echo '{"row_id":"W13-01"}' > "$TMP/prev.json"; echo '[{"n":1,"fix":"x"}]' > "$TMP/fixes.json"
python3 "$S/make_bundles.py" "$RUN" "$ROOT" redraft --from draft/W13-01 --previous "$TMP/prev.json" --fixes "$TMP/fixes.json" > /dev/null
[ -f "$RUN/redraft/W13-01-2/fixes.json" ] && [ -f "$RUN/redraft/W13-01-2/workspace.json" ]; check "make_bundles redraft" 0 $?

# make_bundles: person items, milestones notes, the approver's edits, gaps, Advisor proof items.
py "
import json
an={'values':[['Date added','From','For','Fact','Link','Used in','Add to facts sheet?'],
              ['2026-03-12','W13-04 Notes','W13-04','Our pilot ran across 14 sites.','','',''],
              ['','Ideas row 3','','Not dated yet, so not counted.','','','']]}
json.dump(an,open('$SH/approver_notes.json','w'))
ae={'values':[['Date captured','Row ID','Content type','Status','Size of edit','Original draft',\"Approver's text\",'What changed','Draft URL'],
              ['2026-03-09','W10-02','Industry POV','Posted','Light edit','old a','new a','Shorter hook',''],
              ['2026-03-09','W10-03','Poll','Posted','Rewrite','old b','new b','New question',''],
              ['2026-03-10','W10-02','Industry POV','Posted','Light edit','old a2','new a2','Cut the last line',''],
              ['2026-03-10','W10-02','Image prompt','Posted','Light edit','prompt old','prompt new','Wider shot','']]}
json.dump(ae,open('$SH/approver_edits.json','w'))"
cp "$TMP/ms_web.json" "$SH/milestones.json"
python3 "$S/make_bundles.py" "$RUN" "$ROOT" draft --rows W12-03,W14-06,W12-06 --select "$TMP/select.json" --proof-rows 0,2,0 > /dev/null
check "make_bundles draft with --select and --proof-rows" 0 $?
py "
import json, os
B='$RUN/draft'
g=json.load(open(B+'/W12-03/gaps.json')); assert g['placeholders']==['[Blog 2 link]'], g
assert not os.path.exists(B+'/W14-06/gaps.json')
pi=json.load(open(B+'/W12-03/person_items.json')); assert [x['detail'] for x in pi]==['Our pilot ran across 14 sites.'], pi
a=json.load(open(B+'/W14-06/person_items.json')); assert a[0]['organization']=='Northgate Facilities' and a[0]['can_name']=='Yes (proof log)' and len(a)==2, a
assert json.load(open(B+'/W14-06/proof_item.json'))['Organization']=='Northgate Facilities'
w=json.load(open(B+'/W12-06/person_items.json')); assert any('Topic agreed' in x['detail'] and x['from']=='Milestones tab' for x in w), w
assert os.path.exists(B+'/W12-06/milestones.json')
e=json.load(open(B+'/W13-01/approver_edits.json')) if os.path.exists(B+'/W13-01/approver_edits.json') else None
e=json.load(open(B+'/W12-03/approver_edits.json'))
assert [x['row_id'] for x in e]==['W10-02','W10-03'] and e[0]['approvers_text']=='new a2', e
pe=json.load(open(B+'/W12-03/approver_prompt_edits.json')); assert pe[0]['approvers_prompt']=='prompt new', pe
"; check "draft bundles: gaps.json, person_items.json, Advisor item, milestone notes, approver edits, prompt edits" 0 $?
py "
import json; c=json.load(open('$SH/workspace.json')); c['edit_learning']['enabled']=False; json.dump(c,open('$TMP/ws_noedit.json','w'))"
cp "$SH/workspace.json" "$TMP/ws_keep.json"; cp "$TMP/ws_noedit.json" "$SH/workspace.json"
python3 "$S/make_bundles.py" "$RUN" "$ROOT" draft --rows W13-04 > /dev/null
[ ! -f "$RUN/draft/W13-04/approver_edits.json" ]; check "edit_learning.enabled false: no approver_edits.json" 0 $?
cp "$TMP/ws_keep.json" "$SH/workspace.json"
python3 "$S/make_bundles.py" "$RUN" "$ROOT" check --draft "$F/draft_pass.json" --suffix -p > /dev/null
for f in person_items.json milestones.json row.json; do
  [ -f "$RUN/check/W13-01-p/$f" ]; check "check bundle has $f" 0 $?
done

# ---- check_compliance (run from the check bundle, as the checker agent does) ----
B="$RUN/check/W13-01"
python3 "$B/check_compliance.py" "$B/draft.json" "$B/facts.json" --config "$B/workspace.json" > "$TMP/cc_pass.json"
check "check_compliance passes a clean draft" 0 $? "$TMP/cc_pass.json" '"pass": true'
B2="$RUN/check/W13-04"
python3 "$B2/check_compliance.py" "$B2/draft.json" "$B2/facts.json" --config "$B2/workspace.json" > "$TMP/cc_fail.json"
check "check_compliance fails a bad draft" 1 $? "$TMP/cc_fail.json" '"pass": false'
py "
import json; d=json.load(open('$TMP/cc_fail.json')); t=json.dumps(d)
rules=[f['rule'] for f in d['fixes']]
assert 'R-01' in rules, rules
assert 'Competitors' in rules, rules
assert 'Product timing' in rules, rules
assert any('X09' in f['issue'] for f in d['fixes']), t
assert any(\"Figure '75%'\" in f['issue'] for f in d['fixes']), t
assert any('alternate hook' in f['issue'] for f in d['fixes']), t
assert any('meter-room.jpg' in f['issue'] for f in d['fixes']), t
"; check "check_compliance fixes: custom rule, competitor, timing, fact, figure, hook, repeat visual" 0 $?
python3 "$B/check_compliance.py" "$B/draft.json" "$B/facts.json" > "$TMP/cc_auto.json"
check "check_compliance finds workspace.json in its bundle" 0 $? "$TMP/cc_auto.json" '"pass": true'

# check_compliance: bracketed gaps are not figures, "02" and "2" match, person items are figure sources.
B3="$RUN/check/W13-01-p"
py "
import json; d=json.load(open('$B3/draft.json'))
d['post']=d['post'].replace('cut monthly reporting time by 40%.', 'cut monthly reporting time by 40% across 14 sites in [number] regions, with [Advisor 3 full name]. Week 02 of the pilot set the pace.')
json.dump(d,open('$B3/draft.json','w'))"
python3 "$B3/check_compliance.py" "$B3/draft.json" "$B3/facts.json" --config "$B3/workspace.json" > "$TMP/cc_gap.json"
py "
import json; d=json.load(open('$TMP/cc_gap.json')); figs=[f for f in d['fixes'] if f['rule']=='Figures']
assert not figs, figs
"; check "check_compliance: gaps, 02 and person-item figures pass" 0 $?
rm "$B3/person_items.json"
python3 "$B3/check_compliance.py" "$B3/draft.json" "$B3/facts.json" --config "$B3/workspace.json" > "$TMP/cc_gap2.json"
check "check_compliance: without person_items.json the 14 does not trace (exit 1)" 1 $? "$TMP/cc_gap2.json" "Figure '14'"
grep -q "No image_prompt" "$TMP/cc_pass.json"; check "check_compliance warns when a post has no image prompt" 0 $?

# ---- calendar_writes: plan, guard, verify, shadow ----
python3 "$S/calendar_writes.py" plan "$F/calendar.json" "$F/writes.json" --config "$CFG" > "$TMP/cw_plan.json"
check "calendar_writes plan accepts allowed writes" 0 $? "$TMP/cw_plan.json" '"Calendar!B4:B12"'
py "
import json; d=json.load(open('$TMP/cw_plan.json')); a={(x['row_id'],x['col']):x['value'] for x in d['accepted']}
assert a[('W13-01','Status')]=='Draft ready' and a[('W12-01','Title / angle')].startswith('Partner news:')
assert d['guard_ranges']==['Calendar!B4:B12','Calendar!J4:M12'], d['guard_ranges']
"; check "calendar_writes plan values and guard ranges" 0 $?
python3 "$S/calendar_writes.py" plan "$F/calendar.json" "$F/writes_bad.json" --config "$CFG" > "$TMP/cw_bad.json"
check "calendar_writes plan refuses locked writes (exit 1)" 1 $?
py "
import json; d=json.load(open('$TMP/cw_bad.json'))
assert not d['accepted'] and len(d['refused'])==5, d
r=' '.join(x['reason'] for x in d['refused'])
assert 'person' in r and 'request' in r and 'only to Draft ready' in r and 'Cancelled' in r and 'proof placeholder' in r and 'does not exist' in r
"; check "calendar_writes refusal reasons" 0 $?

mkfresh() {  # mkfresh <out prefix> <python edits on rows (list of dicts keyed by header)>
  py "
import json
v=json.load(open('$F/calendar.json'))['values']; h=v[0]; rows=[dict(zip(h,r)) for r in v[1:]]
$2
g=[[r[k] for k in h] for r in rows]
b=[[g[i-2][h.index('Status')]] for i in range(4,13)]
jm=[g[i-2][h.index('Notes'):h.index('Row ID')+1] for i in range(4,13)]
json.dump({'range':'Calendar!B4:B12','values':b},open('$1_b.json','w'))
json.dump({'range':'Calendar!J4:M12','values':jm},open('$1_jm.json','w'))"
}
mkfresh "$TMP/clean" "pass"
python3 "$S/calendar_writes.py" guard "$F/calendar.json" "$F/writes.json" "$TMP/clean_b.json" "$TMP/clean_jm.json" --config "$CFG" > "$TMP/guard.json"
check "guard: clean fresh read accepts every write" 0 $? "$TMP/guard.json" '"refused": \[\]'
mkfresh "$TMP/moved" "rows.pop(7)"   # a person deleted W12-06 (row 9): rows below shift up
python3 "$S/calendar_writes.py" guard "$F/calendar.json" "$F/writes.json" "$TMP/moved_b.json" "$TMP/moved_jm.json" --config "$CFG" > "$TMP/guard_moved.json"
check "guard: row moved is refused (exit 1)" 1 $? "$TMP/guard_moved.json" 'Row ID changed: expected W13-01'
mkfresh "$TMP/status" "rows[2]['Status']='Cancelled'"   # a person cancelled W12-01 (row 4)
python3 "$S/calendar_writes.py" guard "$F/calendar.json" "$F/writes.json" "$TMP/status_b.json" "$TMP/status_jm.json" --config "$CFG" > "$TMP/guard_status.json"
check "guard: status changed is refused (exit 1)" 1 $? "$TMP/guard_status.json" "Status changed during the run \('Planned' to 'Cancelled'\)"
mkfresh "$TMP/note" "rows[10]['Notes']='Sam: keep this one.'"   # a person wrote a note on W13-03 (row 12)
python3 "$S/calendar_writes.py" guard "$F/calendar.json" "$F/writes.json" "$TMP/note_b.json" "$TMP/note_jm.json" --config "$CFG" > "$TMP/guard_note.json"
check "guard: a person's note is kept and the new note appended" 0 $? "$TMP/guard_note.json" 'Sam: keep this one. Orchestrator 16 MAR 26: due 25 MAR 26'

apply() {  # apply <guard.json> <out after.json> [extra python]
  py "
import json
v=json.load(open('$F/calendar.json'))['values']; h=v[0]
for a in json.load(open('$1'))['accepted']:
    v[a['row']-1][h.index(a['col'])]=a['value']
${3:-}
json.dump({'values':v},open('$2','w'))"
}
apply "$TMP/guard.json" "$TMP/after.json"
python3 "$S/calendar_writes.py" verify "$F/calendar.json" "$TMP/after.json" "$F/writes.json" --guard "$TMP/guard.json" --config "$CFG" > "$TMP/verify.json"
check "verify: clean read-back" 0 $? "$TMP/verify.json" '"unexpected_changes": \[\]'
apply "$TMP/guard.json" "$TMP/after_bad.json" "v[14][h.index('Date')]='Wed 25 MAR 26'"
python3 "$S/calendar_writes.py" verify "$F/calendar.json" "$TMP/after_bad.json" "$F/writes.json" --guard "$TMP/guard.json" --config "$CFG" > "$TMP/verify_bad.json"
check "verify: unexpected change is reported (exit 1)" 1 $? "$TMP/verify_bad.json" '"cell": "A15"'
apply "$TMP/guard.json" "$TMP/after_del.json" "v.pop(8)"
python3 "$S/calendar_writes.py" verify "$F/calendar.json" "$TMP/after_del.json" "$F/writes.json" --guard "$TMP/guard.json" --config "$CFG" > "$TMP/verify_del.json"
check "verify: deleted row reported (exit 1)" 1 $?
py "import json; d=json.load(open('$TMP/verify_del.json')); assert d['deleted_row_ids']==['W12-06'] and not d['unexpected_changes'], d"
check "verify: deleted row reported once by Row ID, no shifted cells" 0 $?
python3 "$S/calendar_writes.py" verify "$F/calendar.json" "$F/calendar.json" "$F/writes.json" --config "$CFG" > "$TMP/verify_nw.json"
check "verify: writes missing from the read-back (exit 1)" 1 $?
py "import json; assert len(json.load(open('$TMP/verify_nw.json'))['not_written'])==6"
check "verify: every missing write listed" 0 $?

python3 "$S/calendar_writes.py" shadow "$F/calendar.json" "$F/writes.json" --config "$CFG" > "$TMP/shadow.json"
check "shadow lists would-be writes" 0 $? "$TMP/shadow.json" 'W13-01 Status: Draft ready'
python3 "$S/calendar_writes.py" shadow "$F/calendar.json" "$F/writes_bad.json" --config "$CFG" > "$TMP/shadow_bad.json"
check "shadow lists would-be refusals" 0 $? "$TMP/shadow_bad.json" 'would be refused'
py "
import json; d=json.load(open('$TMP/shadow_bad.json'))
assert not any('W12-05' in l or 'Cancelled' in l for l in d['brief_lines']), d['brief_lines']
"; check "shadow brief lines never mention the Cancelled row" 0 $?
python3 "$S/calendar_writes.py" verify "$F/calendar.json" "$F/calendar.json" --shadow --config "$CFG" > "$TMP/verify_sh.json"
check "verify --shadow: no change" 0 $? "$TMP/verify_sh.json" '"unexpected_changes": \[\]'
python3 "$S/calendar_writes.py" verify "$F/calendar.json" "$TMP/after.json" --shadow --config "$CFG" > "$TMP/verify_sh2.json"
check "verify --shadow: any change is reported (exit 1)" 1 $?

# calendar_writes: requests, Week, weeksync, tidy, v2, Backlog, --log, fallback rows.
cat > "$TMP/w2.json" <<'JSON'
[
 {"row": 13, "col": "Date", "value": "2026-03-31", "request": "W13-04 Notes"},
 {"row": 13, "col": "Title / angle", "value": "What site managers ask for first", "request": "W13-04 Notes"},
 {"row": 13, "col": "Notes", "value": "Agents 16 MAR 26: Moved to 31 MAR 26 and retitled, as asked in Notes."},
 {"row": 12, "col": "Content type", "value": "Industry POV", "request": "Ideas row 4"},
 {"row": 7, "col": "Pillar", "value": "Audits", "request": "W12-04 Notes"},
 {"row": 25, "col": "Date", "value": "2026-03-26", "request": "W13-07 Notes", "series": true},
 {"row": 25, "col": "Pillar", "value": "Audits", "request": "W13-07 Notes", "series": true},
 {"row": 10, "col": "Spec", "value": "Carousel"},
 {"row": 15, "col": "Week", "value": "13"},
 {"row": 27, "col": "Notes", "value": "Agents 16 MAR 26: a note on a Backlog row."},
 {"row": 25, "col": "Original draft", "value": "Audit season is closer than it looks. Read it: https://brightwell.example.com/blog/audit-trail", "v2": true},
 {"row": 25, "col": "Draft URL", "value": "https://docs.example.com/d/TEST-drafts-002?tab=t.w1307v2"},
 {"row": 14, "col": "Date", "value": "Thu 02 APR 26", "request": "W13-05 Notes"}
]
JSON
python3 "$S/calendar_writes.py" plan "$F/calendar.json" "$TMP/w2.json" --config "$CFG" > "$TMP/cw2.json"
check "calendar_writes plan with requests (refusals exit 1)" 1 $?
py "
import json; d=json.load(open('$TMP/cw2.json')); a={(x['row_id'],x['col']):x['value'] for x in d['accepted']}
r={(x['row'],x['col']):x['reason'] for x in d['refused']}
assert a[('W13-04','Date')]=='2026-03-31' and a[('W13-04','Week')]=='14' and a[('W13-04','Title / angle')].startswith('What site')
assert a[('W13-03','Content type')]=='Industry POV'
assert a[('W13-07','Date')]=='2026-03-26' and ('W13-07','Week') not in a
assert a[('W13-07','Original draft')].endswith('audit-trail')
assert 'Planned or Proposed' in r[(7,'Pillar')] and 'series shift changes only' in r[(25,'Pillar')]
assert 'request' in r[(10,'Spec')] and 'ISO week' in r[(15,'Week')] and 'Backlog' in r[(27,'Notes')]
assert 'YYYY-MM-DD' in r[(14,'Date')]
assert len(d['refused'])==6, d['refused']
"; check "calendar_writes requests, series, Week, v2 Original draft, Backlog refusals" 0 $?

py "
import json; v=json.load(open('$F/calendar.json')); h=v['values'][0]
for r in v['values'][1:]:
    if r[h.index('Row ID')]=='W13-01': r[h.index('Date')]='Tue 31 MAR 26'
json.dump(v,open('$TMP/cal_moved.json','w'))"
echo '[{"row": 25, "col": "Original draft", "value": "Overwrite attempt"}]' > "$TMP/w_od.json"
python3 "$S/calendar_writes.py" plan "$F/calendar.json" "$TMP/w_od.json" --config "$CFG" > "$TMP/cw_od.json"
check "Original draft without v2 is never overwritten (exit 1)" 1 $? "$TMP/cw_od.json" 'replaced only by a v2 redraft'
python3 "$S/calendar_writes.py" weeksync "$TMP/cal_moved.json" --config "$CFG" > "$TMP/ws.json"
py "import json; d=json.load(open('$TMP/ws.json')); assert d==[{'row':10,'col':'Week','value':'14','by':'week sync','row_id':'W13-01'}], d"
check "weeksync lists the Week write for a Date a person moved" 0 $?

py "
import json; v=json.load(open('$F/calendar.json')); h=v['values'][0]
for r in v['values'][1:]:
    if r[h.index('Row ID')]=='W13-04':
        r[h.index('Notes')]='Sam, 10 MAR 26: keep this one short. Agents 11 MAR 26: Drafted. Agents 12 MAR 26: Visual changed.'
        r[h.index('Sources')]='Facts A01; Guide ch2; Facts A01'
json.dump(v,open('$TMP/cal_tidy.json','w'))
w=[{'row':13,'col':'Notes','tidy':True,'value':'Sam, 10 MAR 26: keep this one short. Agents 16 MAR 26: Drafted; visual changed.'},
   {'row':13,'col':'Sources','tidy':True,'value':'Facts A01; Guide ch2'}]
json.dump(w,open('$TMP/w_tidy.json','w'))
json.dump([{'row':13,'col':'Notes','tidy':True,'value':'Agents 16 MAR 26: Drafted.'}],open('$TMP/w_tidy_bad.json','w'))
json.dump([{'row':13,'col':'Notes','tidy':True,'value':'Sam, 10 MAR 26: keep this one short. Agents 16 MAR 26: one. Agents 16 MAR 26: two.'}],open('$TMP/w_tidy_two.json','w'))
json.dump({'values':[['Date moved','Row ID','Agent','Text','Reason moved'],['2026-03-16','W13-04','Agents','Agents 11 MAR 26: Drafted.','Tidy']]},open('$TMP/log.json','w'))
json.dump([{'row':13,'col':'Notes','value':'Agents 11 MAR 26: Drafted.'}],open('$TMP/w_relog.json','w'))"
python3 "$S/calendar_writes.py" plan "$TMP/cal_tidy.json" "$TMP/w_tidy.json" --config "$CFG" > "$TMP/cw_tidy.json"
check "tidy keeps the person's words and one agent line" 0 $? "$TMP/cw_tidy.json" '"value": "Facts A01; Guide ch2"'
python3 "$S/calendar_writes.py" plan "$TMP/cal_tidy.json" "$TMP/w_tidy_bad.json" --config "$CFG" > "$TMP/cw_tidy_bad.json"
check "tidy that drops a person's words is refused (exit 1)" 1 $? "$TMP/cw_tidy_bad.json" 'drop or change text a person wrote'
python3 "$S/calendar_writes.py" plan "$TMP/cal_tidy.json" "$TMP/w_tidy_two.json" --config "$CFG" > "$TMP/cw_tidy_two.json"
check "tidy with two agent lines is refused (exit 1)" 1 $? "$TMP/cw_tidy_two.json" 'only 1 agent line'
python3 "$S/calendar_writes.py" plan "$F/calendar.json" "$TMP/w_relog.json" --log "$TMP/log.json" --config "$CFG" > "$TMP/cw_log.json"
check "--log: a line already in the Agent log is not appended again" 0 $? "$TMP/cw_log.json" '"accepted": \[\]'

cat > "$TMP/w_fb.json" <<'JSON'
[
 {"row": 4, "col": "Notes", "value": "Agents 16 MAR 26: Backup post added below (W12-01-FB). To use it, set it to Approved and this row to Cancelled."},
 {"insert_after": "W12-01", "values": {"Date": "2026-03-17", "Status": "Fallback post", "What to post": "Industry POV", "Pillar": "Reporting",
   "Channel": "LinkedIn", "Title / angle": "Backup for W12-01: why one dashboard beats twelve spreadsheets", "Row ID": "W12-01-FB",
   "AM/PM": "AM", "Content type": "Industry POV", "Draft URL": "https://docs.example.com/d/TEST-drafts-001?tab=t.w1201fb",
   "Notes": "Agents 16 MAR 26: Backup post for W12-01 (checker: pass). To use it, set this row to Approved and W12-01 to Cancelled."}},
 {"insert_after": "W12-04", "values": {"Date": "2026-03-18", "Status": "Fallback post", "Row ID": "W12-04-FB", "Content type": "Poll"}},
 {"insert_after": "W12-05", "values": {"Date": "2026-03-19", "Status": "Fallback post", "Row ID": "W12-05-FB"}},
 {"insert_after": "W13-01", "values": {"Date": "2026-03-23", "Status": "Planned", "Row ID": "W13-01-FB"}},
 {"insert_after": "W13-02", "values": {"Date": "2026-03-24", "Status": "Fallback post", "Row ID": "W13-02-B"}}
]
JSON
python3 "$S/calendar_writes.py" plan "$F/calendar.json" "$TMP/w_fb.json" --config "$CFG" > "$TMP/cw_fb.json"
check "insert_after: invalid fallback rows refused (exit 1)" 1 $?
py "
import json; d=json.load(open('$TMP/cw_fb.json')); i=d['inserts']
assert [x['row_id'] for x in i]==['W12-04-FB','W12-01-FB'], i
x=i[1]; h=json.load(open('$F/calendar.json'))['values'][0]
assert x['after_row']==4 and x['range']=='Calendar!A5:V5' and x['insert_request']['insertDimension']['range']['startIndex']==4
assert x['values'][h.index('Week')]=='12' and x['values'][h.index('Action needed')] is None
r=' '.join(y['reason'] for y in d['refused']); assert 'Cancelled' in r and 'Status Fallback post' in r and 'must be W13-02-FB' in r, r
assert d['guard_ranges']==['Calendar!B4:B7','Calendar!J4:M7'], d['guard_ranges']
"; check "insert_after: bottom-up inserts with Week, null formulas and guard ranges" 0 $?
python3 -c "
import json; w=json.load(open('$TMP/w_fb.json')); json.dump(w[:2],open('$TMP/w_fb_ok.json','w'))"
py "
import json; v=json.load(open('$F/calendar.json'))['values']
json.dump({'range':'Calendar!B4:B4','values':[[v[3][1]]]},open('$TMP/fb_b.json','w'))
json.dump({'range':'Calendar!J4:M4','values':[v[3][9:13]]},open('$TMP/fb_jm.json','w'))"
python3 "$S/calendar_writes.py" guard "$F/calendar.json" "$TMP/w_fb_ok.json" "$TMP/fb_b.json" "$TMP/fb_jm.json" --config "$CFG" > "$TMP/g_fb.json"
check "guard accepts the fallback insert" 0 $? "$TMP/g_fb.json" '"row_id": "W12-01-FB"'
py "
import json; v=json.load(open('$F/calendar.json'))['values']
json.dump({'range':'Calendar!B4:B4','values':[['Cancelled']]},open('$TMP/fb_b2.json','w'))"
python3 "$S/calendar_writes.py" guard "$F/calendar.json" "$TMP/w_fb_ok.json" "$TMP/fb_b2.json" "$TMP/fb_jm.json" --config "$CFG" > "$TMP/g_fb2.json"
check "guard refuses the insert when the original was cancelled during the run (exit 1)" 1 $? "$TMP/g_fb2.json" 'Fallback row not added'
py "
import json; v=json.load(open('$F/calendar.json'))['values']; g=json.load(open('$TMP/g_fb.json')); h=v[0]
for a in g['accepted']: v[a['row']-1][h.index(a['col'])]=a['value']
for i in g['inserts']:
    row=['=formula' if x is None else x for x in i['values']]; row[h.index('Date')]='Tue 17 MAR 26'
    v.insert(i['after_row'], row)
json.dump({'values':v},open('$TMP/after_fb.json','w'))
v2=[list(r) for r in v]; v2.insert(len(v2), v2.pop(4)); json.dump({'values':v2},open('$TMP/after_fb_bad.json','w'))"
python3 "$S/calendar_writes.py" verify "$F/calendar.json" "$TMP/after_fb.json" "$TMP/w_fb_ok.json" --guard "$TMP/g_fb.json" --config "$CFG" > "$TMP/v_fb.json"
check "verify: fallback row in place, no moved rows" 0 $? "$TMP/v_fb.json" '"moved_rows": 0'
py "import json; d=json.load(open('$TMP/v_fb.json')); assert d['fallback_rows_added']==['W12-01-FB'] and not d['fallback_row_problems'] and not d['added_row_ids'], d"
check "verify: fallback row counted as expected, not as a person's insert" 0 $?
python3 "$S/calendar_writes.py" verify "$F/calendar.json" "$TMP/after_fb_bad.json" "$TMP/w_fb_ok.json" --guard "$TMP/g_fb.json" --config "$CFG" > "$TMP/v_fb_bad.json"
check "verify: fallback row not under its original is reported (exit 1)" 1 $? "$TMP/v_fb_bad.json" 'not directly under'
python3 "$S/calendar_writes.py" shadow "$F/calendar.json" "$TMP/w_fb.json" --config "$CFG" > "$TMP/sh_fb.json"
check "shadow lists the would-be fallback row" 0 $? "$TMP/sh_fb.json" 'W12-01-FB: fallback row would be added under W12-01'
py "import json; json.dump(json.load(open('$TMP/sh_fb.json'))['brief_lines'],open('$TMP/sh_fb_lines.json','w'))"
absent "shadow brief lines never name the Cancelled row" "$TMP/sh_fb_lines.json" 'W12-05'

# ---- doc_text and extract_final ----
python3 "$S/doc_text.py" "$F/docs.json" "$TMP/doc.md" --expect "End of draft" > "$TMP/dt.json"
check "doc_text extracts tabs and tables" 0 $? "$TMP/doc.md" 'Fact \| A01'
python3 "$S/doc_text.py" "$F/docs.json" "$TMP/doc2.md" --expect "Pre-publish checklist" > "$TMP/dt2.json"
check "doc_text flags a cut-off doc (exit 1)" 1 $? "$TMP/dt2.json" 'MISSING'
python3 "$S/extract_final.py" "$F/docs.json" "https://docs.example.com/d/TEST-drafts-002?tab=t.w1301" > "$TMP/ef.json"
check "extract_final returns the text above the dashed line" 0 $? "$TMP/ef.json" '"final_text": "Final post text line one.\\nLine two."'
python3 "$S/extract_final.py" "$F/docs.json" "t.nope" > "$TMP/ef2.json"
check "extract_final reports a missing tab (exit 1)" 1 $? "$TMP/ef2.json" 'not found'
py "
import json; d=json.load(open('$F/docs.json')); c=d['content']['tabs'][0]['documentTab']['body']['content']
p=lambda t: {'paragraph': {'elements': [{'textRun': {'content': t}}]}}
c.insert(-1, p('Image prompt (edit this, then paste into ImageGen): A wide shot of a plant room, morning light. No text.\\n'))
c.insert(-1, p('Image prompt as drafted (do not edit): A plant room. No text.\\n'))
json.dump(d,open('$TMP/docs_p.json','w'))"
python3 "$S/extract_final.py" "$TMP/docs_p.json" "t.w1301" > "$TMP/ef3.json"
py "
import json; d=json.load(open('$TMP/ef3.json'))
assert d['image_prompt'].startswith('A wide shot') and d['image_prompt_original']=='A plant room. No text.', d
"; check "extract_final returns both image prompt lines" 0 $?

echo
if [ "$fails" -eq 0 ]; then echo "All orchestrator tests passed."; else echo "$fails orchestrator test(s) failed."; fi
[ "$fails" -eq 0 ]
