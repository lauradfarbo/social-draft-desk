---
name: calendar-builder
description: Builds and extends the company's rolling 13-week content calendar from an approved content plan. Use when asked to "build the content calendar", "convert the content plan to a calendar", "extend the calendar", "run the monthly calendar update", "add a milestone", "propose rows for a trade show, launch, webinar or funding date", "a milestone date changed", or "process new post ideas" from the Ideas tab, including ideas that ask to change, convert or move existing rows.
---

# Calendar builder

**Purpose:** keep the company's content calendar as the single source of truth, always 13 weeks ahead. Convert the approved plan into rows once, then add new rows only as proposals for a person to approve. The calendar is kept by people who are not marketers, so keep everything a person sees plain and short.

Read `workspace.json` first. If there is none, run the `workspace-setup` skill. Every location, name, list and rule this skill uses comes from that file. Locations come from `sources.<key>`, live or test.

## Assumptions

- The company has an approved content plan (often a PDF) with a dated, week-by-week schedule.
- A plan rules doc (`sources.plan_rules`) sets the cadence, the playbook specs and the holiday shifts. The `plan` section of the config holds the part a script can test.
- One named person approves rows: `company.approver.name`, called the approver below.

## Inputs

| Input | Config key | Used for |
| --- | --- | --- |
| Approved content plan | Named by the person on the first run | First run only |
| Plan rules doc | `sources.plan_rules`, `plan` | Cadence, playbook specs, holiday shifts |
| Rules doc | `sources.rules`, `writing` | Writing and brand rules, competitor names |
| Facts sheet | `sources.facts_sheet`, `facts` | Checking ideas against approved claims |
| Calendar (Calendar, Backlog, Ideas, Milestones, From the approver's notes tabs) | `sources.calendar`, `calendar.tabs` | Existing rows and Row IDs, last date covered, ideas, milestones, facts the approver gave |
| Milestone changes | The orchestrator's `snapshot.py compare` (`milestone_changes`) | Mode 3b |
| Long-form source and chapter map | `sources.long_form`, `swaps.source_label` | Chapters used recently |
| Published archive, performance report (optional) | `sources.other` | Pillars and chapters used recently, pillar weighting |

## Outputs

- New Calendar rows with Status `Proposed` (first run: `Planned` or `Posted`).
- Changes a person asked for on existing Planned or Proposed rows (request writes), each with one Notes line.
- Empty agent cells filled on rows a person added.
- Ideas rows set to `Scheduled` or `Parked`, Milestones rows set to Rows proposed `Yes`.
- Milestone change run: linked rows moved, retitled or given reminders when a milestone's Start date or Confirmed changes.
- A short summary for the weekly brief.

## Access

- Calendar: read and write cell ranges on the Calendar, Ideas and Milestones tabs; read the Backlog and From the approver's notes tabs (for Row IDs in use and the approver's facts). On the first run, create the calendar file and all its tabs in the folder the person names.
- Every other source: read only.

## Hard rules

- Never publish, post, send email or submit anything.
- Never delete a row. On monthly and milestone runs, only add new rows below the last row (see "Writing new rows").
- The approver's direction comes first. When a person in `requests.from` (default the approver) asks, on the Ideas tab, in a row's Notes or by editing a row's cells, change, convert or move existing `Planned` and `Proposed` rows to do what they asked. Write only the columns in `calendar.request_columns` (default Date, What to post, Pillar, Channel, Title / angle, Content type, Spec) through the orchestrator's `calendar_writes.py`, with `"request": "<where they asked, for example 'W11-02 Notes' or 'Ideas row 4'>"` on each write, and add one Notes sentence saying what changed, ending "as asked on the Ideas tab" or "as asked in Notes". If part of an ask breaks a hard rule, do the rest and say in that sentence what was left out and why. With `requests.enabled` false, propose the change in Notes instead.
- On a row a person added directly to the Calendar, fill the empty agent cells (What to post, Pillar, Channel, Row ID, Week, Content type, Spec, Sources, What's missing). Never change anything the person entered.
- Every row the builder adds after the first run has Status `Proposed`. Agents set only the statuses in `calendar.agent_statuses` (default Proposed, Draft ready, Fallback post; the orchestrator sets the last two). People set `Planned`, `Approved`, `Posted`, `Cancelled` and `Backlog`. The only exception is the first run, where the person running it states which rows are already posted.
- Skip `Cancelled` rows everywhere: never write to them, count them as free slots or mention them in any summary, brief or notification. Treat `Backlog` rows the same until the orchestrator's `backlog.py` moves them to the Backlog tab.
- Never retype a person's cell text into a write. Notes are append-only through `calendar_writes.py`.
- Never write to the Action needed (G) or Draft (H) columns, or to the This Week tab. They are formulas.
- Every row has Sources filled. What's missing names exactly what a person must provide, in plain words.
- Never name or cite a company in `writing.competitors` in any title, angle or note.
- Never invent customers, partners, quotes or results. Proof rows (content types in `calendar.proof_types`) keep the title from `calendar.proof_placeholders` until proof intake links an approved proof log item.
- Work on the TEST calendar (`sources.calendar.test`) until the agent register records a passing test for the run mode in use.
- Writing standards for anything written into the calendar: `docs/agent-standards.md` and `writing.*` (spelling, units). No em dashes. Dates in prose as DD MMM YY with an uppercase month (13 OCT 26).

## Calendar schema

Read `references/calendar-schema.md` before writing anything. It defines the tabs, column order (A to V), Status values, pillar and "What to post" mappings, formulas, filter view and formatting. Do not add, remove or reorder columns.

## Row IDs and weeks

- Week (column N) is the calendar (ISO) week of the Date, as a number (`calendar.week_numbering`, `iso`). Every "Week N" in titles, Notes and the brief is the calendar week.
- Row ID is `W{iso week:02d}-{seq:02d}`, for example `W11-02`. seq counts up within the week in Date and AM/PM order and continues after the highest seq already used for that week number on the Calendar and the Backlog tab, so an ID from an earlier year is never reused (W02 in 2027 and again in 2028). A backup row is `<Row ID>-FB`.
- A Row ID is set once. A row that later moves week keeps its ID; the orchestrator's `calendar_writes.py weeksync` keeps Week in step with the Date.
- People may sort or reorder the Calendar at any time. Find rows by Row ID, never by position.
- Alternating cadence (odd and even weeks) counts weeks from `calendar.alternation_anchor_week` (default year 2026, week 1), so the pattern still alternates across week 53 and week 1.
- Dates a person types are read per `dates.typed_order` (`day_first` by default: 2/12/26 is 02 DEC 26).

## Platforms

The tested path is Google Sheets. For a Notion database or Excel Online, follow the adapter rules in `docs/workspace-config.md`: the same columns in the same order, the same never-overwrite rules, and the same guard and read-back checks. Formulas (Action needed, Draft, This Week) are replaced by the platform's equivalent (a Notion formula property or view, an Excel formula) or, where the platform has none, left to the agent to fill on each run. Run the TEST calendar on that platform before going live.

## Dry run (shadow mode)

When the weekly orchestrator runs in shadow mode, run the monthly, ideas and milestone modes as a dry run: read as normal, work out every new row, request change, cell and Ideas or Milestones update the run would write, and return them as a list (Row ID, date, What to post, title, What's missing, the change asked for and where, or the idea and Parked reason). Write nothing to any tab. The orchestrator puts the list in the shadow brief under "Calendar changes proposed (not written)".

## Writing new rows

Never append to the Calendar (Sheets `append_values`). The formulas in G2 and H2 return values down to the last row of the grid, so an append can land below them, hundreds of rows down.

1. Read Calendar column A and find the last row with a Date. The first new row is the one below it.
2. Write the new rows with Sheets `update_values` to an explicit range, for example `Calendar!A48:Q59`. Dates as `YYYY-MM-DD` so they are stored as real dates. Row ID and Week as in "Row IDs and weeks". New rows need not be in date order: the orchestrator sorts the Calendar by Date, AM/PM and Row ID at the end of every run.
3. Put `null` in G, H and I (and any other cell to leave alone) so the formulas and empty cells are not overwritten. Never write an empty string to G or H: it breaks the formula.
4. Read back the new rows and the row above them. Confirm the row above is unchanged, Action needed shows "New slot: review, then set Planned" and Dates display as dates.
5. To fill empty cells on a person's row, write only those cells (for example `Calendar!C48:D48` and `Calendar!L48:Q48`). Never write a range that includes a cell the person filled. Read the row again just before writing and skip it if its Date, Status or the target cells changed.

## Mode 1: First run (convert the plan)

1. Read the plan in full. Locate the week-by-week schedule.
2. Extract one row per dated line item. Copy Content type, Channel(s), What to create (into Spec) and Draft title / angle verbatim, joining wrapped lines with a single space.
3. Split the date into Date (real date, year inferred from the plan's date range) and AM/PM (only where the plan marks AM or PM). Week is the ISO week of the Date and Row IDs follow "Row IDs and weeks". The plan's own week numbers (1, 2, 3) only order the rows; plan week 1 starts on `plan.week1_monday`.
4. Fill Pillar and What to post from the mappings. Set Status: rows the person names as already posted get `Posted`; all others `Planned`.
5. Build the calendar natively with the connectors. Do not upload an .xlsx: the Drive connector does not convert .xlsx to a Google Sheet reliably.
   - Drive `create_file` with contentMimeType `application/vnd.google-apps.spreadsheet`, the exact name given (for testing: `TEST - <company.name> Content Calendar`) and the folder named.
   - Sheets `update_spreadsheet`: create the tabs in the order the schema gives (names from `calendar.tabs`), and hide the Agent snapshot tab.
   - Sheets `update_formulas`: write the Calendar tab in one call with verbatim titles, the G2 and H2 formulas, and `null` in G and H below row 2. Write the This Week link row, headers and formulas, the headers of Backlog, Ideas, From the approver's notes, Agent log, Approver edits and Agent snapshot, the Milestones rows (dated milestones stated in the plan only) and the How to use text.
   - Sheets `update_spreadsheet`: apply formatting, dropdowns, filter, the filter view, freeze, conditional formats, the collapsed column group and warning-only protection.
   - `scripts/build_calendar.py` produces the same layout as an .xlsx, for an offline copy only.
6. Verify: export the calendar (Calendar tab as `calendar.json` in the `{"values": [...]}` shape, or the file as .xlsx), save the plan text with `pdftotext -layout`, and run:
   `python3 scripts/verify_calendar.py plan_layout.txt calendar.json --config workspace.json [--expect <row count stated in the plan>]`
   It compares every row's week (plan order against the ISO week of the Date, the Week column and the Row ID prefix), weekday, date, AM/PM, content type and title. Report each mismatch. Never fix a mismatch silently. If the plan's table layout differs from the default, set `plan.pdf` in the config (see the script's usage text).
7. Only after verification passes, clean the titles in column F: remove quote marks and replace proof titles with the placeholder from `calendar.proof_placeholders`. Column P keeps the verbatim content type for traceability.

## Mode 2: Monthly run (first full run of each month)

1. Read the Calendar and Backlog tabs. Find the last dated row and, for each week number, the highest seq used.
2. Work out the weeks needed to restore a 13-week horizon from today.
3. For each new week, apply the cadence in the plan rules doc and the `plan` section of the config: `plan.posts_per_week`, the weekly proof slot (`plan.proof_slot`: weekday, and which proof type runs in odd and even weeks, counted from `calendar.alternation_anchor_week`), the blog Publish and LinkedIn teaser pair (`plan.blog_pair`), the rotation slot and its types (`plan.rotation_slot`), types not repeated in one week (`plan.no_repeat_in_week`), the newsletter frequency, and anything else the plan rules doc sets. A missing key means the plan rules doc decides.
4. Shift any row that lands on a public holiday in `company.holiday_market` as the plan rules doc says (default: to the next working day that has no row of the same type). Say so in Notes.
5. Respect `plan.dependencies`: a row that needs a fact that is not yet Approved is still proposed, with What's missing naming the fact and its deadline. Dated events come first (`plan.precedence`, default `dated_events_first`): never put an evergreen row on a dated event's slot.
6. Propose a clean title and angle for each row that continues the story arc and covers pillars and long-form chapters not used in the last 8 weeks.
7. Fill Pillar, What to post, Channel, Content type and Spec from the mappings and the plan rules playbook. Set Status `Proposed`. Leave G and H empty. For team-owned rows (content type matches `calendar.team_owned_regex`), write in Notes that the team writes it and agents do not draft it. For a teaser (`calendar.teaser_regex`), write in Notes that the agent drafts it once the published blog link is in Notes on the blog row. Fill Sources with the documents the row is based on (plan rules doc and version, long-form chapter, other reference). Fill What's missing with anything a person must provide before the post can be finished, such as proof log sign-off for proof slots.
8. Write the rows as set out in "Writing new rows". Do not touch existing rows.
9. Write a summary of proposed rows (dates, types, titles, rules applied, anything uncertain) for the next weekly brief.

## Guarding Ideas and Milestones writes

Someone may delete, insert or sort rows on the Ideas, Milestones or From the approver's notes tab while a run is in progress. Before writing any cell on those tabs:

1. Keep the tab as first read, saved exactly as returned (`ideas_before.json` or `milestones_before.json`).
2. Just before writing, read the same range again and save it (`ideas_fresh.json`). Put the planned writes in `tab_writes.json` (`[{"row": 5, "col": "Status", "value": "Scheduled"}]`).
3. Run `python3 scripts/tab_guard.py ideas_before.json ideas_fresh.json tab_writes.json --key "Idea (one line)" --config workspace.json` (Milestones: `--key "Milestone"`; From the approver's notes: `--key "Date added"`).
4. Write only the `accepted` ranges. For an idea or milestone whose write is skipped, do not add its Calendar rows either (run the guard before adding Calendar rows), so the next run picks it up cleanly. Pass `brief_lines` to the orchestrator for the brief.

## Mode 3: Milestone run

1. Read new rows on the Milestones tab where Rows proposed is blank. Skip any milestone whose Confirmed is `Cancelled`.
2. Propose supporting rows: a teaser before, a live post on the day, a recap after, and a press release Distribute (AM) and LinkedIn announcement (PM) pair only for genuine news (launch, funding, major partner).
3. Check each proposed date against existing rows and the cadence. Where a slot is taken, propose the nearest free slot and say so in Notes.
4. Start each new row's Notes with "Milestone: <milestone name exactly as on the Milestones tab>." so the planner can find the rows if the milestone is cancelled later.
5. Write the rows as `Proposed` (see "Writing new rows"), then set Rows proposed on the milestone to `Yes` (through the tab guard).

## Mode 3b: Milestone change run

When the orchestrator's `snapshot.py compare` reports a milestone change (someone changed Start date or Confirmed on the Milestones tab), run this before drafting. A milestone's rows are those whose Notes say "Milestone: <name>.", whose Title / angle names it, or, for a Webinar, every Event announcement, Event reminder and Live event row. The orchestrator gives the milestone's Notes to every linked row's drafter (`person_items.json`).

1. Confirmed changed to Yes, a `requests.hold_lift_word` line with a date in Notes (default "CONFIRMED"), or the dependency fact Approved: lift the hold on the milestone's rows (a `plan.dependencies` entry whose `milestone_type` matches the milestone's Type). Its announcement is drafted now if it is due within 14 days. Unpark any Ideas row whose Agent note says it was parked because of that hold: set its Status to `New` so the ideas run schedules it in the same run.
2. Start date changed: move the milestone's rows with it. The live post goes on the new date; a recap stays the week after; the announcement keeps its date unless it now falls after the event.
3. Reminders: make sure there is at least one reminder post a week from the announcement to the event, and two in the final week, as `Proposed` rows whose Notes start "Milestone: <name>.". Holiday weeks follow the plan rules doc and are flagged for the approver.
4. Retitle any row whose title or spec names the old date or an old working title.
5. Confirmed changed to `Cancelled`: move nothing. The planner lists the remaining rows once in the brief.
6. Every change to an existing row is a request write (`"request": "Milestones row N"`, Planned and Proposed rows only) with one Notes line ending "as changed on the Milestones tab". New rows follow "Writing new rows".

## Mode 4: Ideas run (every run, full or requests mode, before drafting)

1. Read the Ideas tab. Process rows where Idea is filled and Status is blank or `New`. Ignore `Declined` (people set Declined instead of deleting an idea).
2. For each idea, find the best slot: the Wanted by date if given, otherwise the nearest suitable slot in the next 13 weeks that fits the cadence and pillar balance. Prefer replacing nothing: use a free rotation slot, or propose in Notes a swap for a proof slot that has no approved proof.
3. Do what the idea asks. If it asks to change existing rows ("make the next 3 customer stories advisory board posts", "move the poll to Friday"), change, convert or move those Planned and Proposed rows in place as request writes (see the hard rules), keeping each date unless the idea gives one and the holiday rules allow it; say in Notes why a date was kept. Then set the Ideas row to `Scheduled` with the changed Row IDs in Calendar row.
4. Check the idea against the rules doc, `writing.*` and the facts sheet. If it needs a fact that is not yet approved, schedule it anyway: the drafter writes a base draft with the gap in [brackets] and What's missing says what to add. A fact the approver gave in Notes or on the Ideas tab counts as approved once it is on the From the approver's notes tab. Park an idea only when the whole of it breaks a hard rule (a competitor name, an invented customer, partner or quote, a launch, availability or delivery date, a topic in `writing.on_hold_topics` while its hold stands), and say so in Agent note in one plain sentence. If only part of it breaks a rule, schedule the rest and say what was left out.
5. A series ("one a week for 5 weeks") becomes one row per post, each with "post N of M" in Notes. The drafter writes base drafts as each comes within `series.draft_within_days` (default 14) or once its details arrive.
6. For each new post, add a Calendar row (see "Writing new rows") with Status `Proposed`, a clean title and angle, Pillar, What to post, Channel, Content type, Sources (the idea's link plus reference files) and What's missing. In Notes write "From Ideas tab: <added by>, <date added>".
7. On the Ideas row set Status `Scheduled`, write the new Row ID in Calendar row and a one-line Agent note naming the proposed date. Check the row with the tab guard first.
8. Also check for rows a person added straight to the Calendar (Date filled, Row ID empty) and fill their empty agent cells as described in the hard rules, including What to post.

## Scripts

| Script | Use |
| --- | --- |
| `scripts/tab_guard.py` | Row guard for Ideas, Milestones and From the approver's notes writes. Exit 1 if any write was skipped |
| `scripts/verify_calendar.py` | First-run check: plan text against the calendar export, row by row, including ISO Week and Row ID. Exit 1 on any mismatch |
| `scripts/build_calendar.py` | Offline .xlsx copy of the calendar from a rows JSON file (see `examples/sample-rows.json`). Needs openpyxl. Never uploaded as the live calendar |

Run any script with no arguments to see its usage.

## Output to the person

End every run with: rows added (count and Row IDs), rows changed on request (Row ID and what changed), any mismatch or rule conflict found, and what needs a person's decision. Keep it brief.
