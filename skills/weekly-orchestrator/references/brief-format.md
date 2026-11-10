# Weekly brief and update

One doc per run in the briefs folder of the mode in use (`references/locations.md`). The approver (`company.approver.name`) reads it early in the week. One page: short lines, no padding, nothing the approver has to decode.

## Name

- Full run: `Weekly brief - DD MMM YY` (the run date).
- Requests run, or a second run on a day that already has a brief: `Update - DD MMM YY`, written only if the run changed something. A second update on the same day adds ` (2)`, then ` (3)`.
- On TEST, prefix `TEST - `. Simulated test runs (`--as-of`) add ` (simulated)`, for example `TEST - Weekly brief - 16 MAR 26 (simulated)`.

## Create

- **Google Drive:** Drive `create_file` with the title, parentId (the briefs folder) and contentMimeType `text/plain`, textContent = the brief below. It converts to a Google Doc. Then make the section headings bold with Docs `update_doc` (optional).
- **Other platforms** (Notion page, Word Online, local folder): create one page or file with the same title and text, then read it back.

## Text

`<approver>` is `company.approver.name`. `<image tool>` is `visuals.ai_image_tool`.

```
Weekly brief: <run day DD MMM YY>, covering <first date> to <last date>
<one line: N drafts ready for review, N with gaps to finish, N need <approver>'s decision>

Missed runs
<only if missed_runs is not empty: "No run on <DDD> DD MMM YY. This run covers those rows.">

To finish drafts: what to send
<one line per item, grouped by person: "<Row ID>, <DDD DD MMM YY>: <item> (needed | optional)". Only items from What's missing on Draft ready rows, including "Log this in the proof log with sign-off" items>

Ready for review
<Row ID>, <DDD DD MMM YY>, <what to post>: <draft tab link>. <flag for the approver, if any>. <"Has gaps: see To finish" when the draft has bracketed gaps>

Backup posts (fallback rows)
<Row ID>-FB, <DDD DD MMM YY>, <swap type> as a backup for <original content type>: <tab link>. <checker result>. To use it, set <Row ID>-FB to Approved and <Row ID> to Cancelled.

Changes made from your notes and ideas
<one line per ask or hand edit handled: "<Row ID>: <what changed> (from <Notes | Ideas row N | your edit to <column>>)">
<one line per fact filed: "Filed from <where>: <fact, short> (<approver's notes row N | proof log row N>)">
<series_shift.py and Milestones change lines>

Voice guide changes to approve
<monthly run, edit_learning.enabled only: "<voice guide section>: <proposed change> (from your edits on <Row IDs>)". <approver> edits the voice guide if they agree.>

New post types to approve
<content type: one-line playbook entry the drafter proposed>

Needs <approver>
<one line per decision: Proposed rows due soon, swap proposals, facts to add to the facts sheet, asks the run could not read one way, drafts that failed the check twice, Approved rows that need approving again after a change, rows of a cancelled milestone (one line per milestone)>
<Approved rows due within 2 days with What's missing still listing something other than images: "<Row ID>, <DDD DD MMM YY>: Approved, but What's missing still says '<text>'. Clear it or move the row.">

Images to make (<image tool>)
<Row ID>, <DDD DD MMM YY>, <subject from the Visual column>: <draft tab link>. <if visuals.product_reference_photo is set and the prompt shows the product: "Attach the product reference photo.">

Blocked
<Row ID>, <date>: <the hard rule or hold, in plain words, and who lifts it>

Proof slots
<Row ID>, <date>: <drafted from proof log row N | base draft, no proof item yet | flagged: reason | backup row added>

Risks (planner)
<one sentence each, from the planner's brief_risks, only for risks not already listed under another heading. Leave the section out when nothing is left>

Calendar changes proposed
<from the calendar builder: new Proposed rows, ideas scheduled or parked>

Team-owned this period
<rows matching calendar.team_owned_regex in the window, with date: the team writes these>

Overdue
<rows dated before the run date and not Posted, Cancelled or Backlog: Row ID, date, Status. "Set Posted if it went out, move it, or set Backlog.">

Backlog
<backlog.py brief_lines: rows moved to or back from the Backlog tab this run, then one line: "<N> posts on the Backlog tab. To use one, set its Status there to Planned (add a date in Notes if you want one).">

Run details
Checker: <N passed, N after one redraft, N failed twice>. Calendar writes: <N cells>; guard and verify: <clean | see top>.
Files: <TEST or live>; config <workspace.json updated date>; <title of each doc source read, as in sources.*.title>.
<one line: anything the person running the system must know about the run itself, or "Full details in the Agent log (RUN row).">
```

## Rules

- Leave out a section when it has nothing in it, except Ready for review and Run details.
- Leave out "Voice guide changes to approve" unless this is the monthly run and `edit_learning.enabled` is true.
- Leave out "Images to make" when `visuals.ai_image_tool` is null; list the photos or graphics needed under "To finish drafts: what to send" instead.
- Cancelled rows appear nowhere: no section, no count, no line. A cancelled milestone's remaining rows that are not yet Cancelled are listed once under Needs the approver so the approver can cancel them in one go.
- Every swap proposed this run also gets a line under Needs the approver. When the Backlog tab holds a fitting post, offer it in the same line.
- A risk already listed in the last brief, and still the same, is not repeated.
- A proof slot waiting for sign-off whose cut-off date has passed says so: "the sign-off cut-off of DD MMM YY has passed".
- In Run details, the Checker line counts backup rows separately: "Checker: drafts <...>; backups <...>".
- The full run details go to the Agent log tab as one row (Row ID `RUN`, Agent `Orchestrator`, Reason `Run details`), never into the brief.
- A Row ID guard refusal, a Backlog `refused` item or a verify problem goes at the very top of the brief, above the first line.
- Never paste a draft into the brief; link the tab.
- Dates DD MMM YY with an uppercase month, spelling per `writing.spelling`, no em dashes.

## Update (requests mode)

Name as above. First line: `Update: <run day DD MMM YY>`. Then only the sections with content, in the same order, usually "To finish drafts: what to send", "Ready for review", "Changes made from your notes and ideas", "Needs <approver>" and "Backlog". Run details is one line: `Checker: <...>. Calendar writes: <N cells>; guard and verify: <clean | see top>.` A requests run that changed nothing writes no update.

## Shadow brief

Name: `SHADOW - Weekly brief - DD MMM YY`; on TEST, `TEST - SHADOW - Weekly brief - DD MMM YY` (add ` (simulated)` for `--as-of` runs). Folder: `sources.shadow.briefs_folder` for the mode in use. The person testing the system reads it, not the approver.

Same text as above, with these changes:

- First line: `Shadow run: nothing was written to the live calendar, proof log, drafts folder or briefs folder.` On TEST, say TEST instead of live.
- Ready for review: add the live status to each line: `<Row ID>, <DDD DD MMM YY>, <what to post> (live: <status>): <draft tab link>. <flag>`.
- Rename "Needs <approver>" to "Would need <approver>", "Changes made from your notes and ideas" to "Changes that would be made (not written)" and "Calendar changes proposed" to "Calendar changes proposed (not written)".
- Add a section after Backlog:

```
Calendar writes not made
<one line per brief_lines entry from calendar_writes.py shadow, then the Backlog moves, series shifts, Notes tidies, tab rows and proof log writes a live run would make; "None" if empty>
```

- Run details: `Files: shadow (live reads) | test shadow (TEST reads).` and `Verify: calendar <clean | list>; proof log <clean | list>; live drafts and briefs folders <unchanged | list>.` Add `Review rows added: N (shadow review sheet).` and `Final text: not copied in shadow (<Row IDs>).`
