# Shadow mode

Shadow mode lets the system draft real weeks without touching anything live. Use it to try the system on live data before the first `live` run, or to test a change to the config or the plugin.

## What it reads and writes

| | `shadow` | `test shadow` |
| --- | --- | --- |
| Reads calendar (all tabs) and proof log | `live` | `test` |
| Reads rules, plan rules, voice guide, facts, long-form source, assets | Same as every run | Same as every run |
| Draft docs go to | `sources.shadow.drafts_folder.live` | `sources.shadow.drafts_folder.test` |
| Brief goes to | `sources.shadow.briefs_folder.live` | `sources.shadow.briefs_folder.test` |
| Review rows go to | `sources.shadow.review_sheet.live` | `sources.shadow.review_sheet.test` |
| Writes to the calendar or any of its tabs (Backlog, Ideas, Milestones, approver's notes, Agent log, Approver edits, Agent snapshot), proof log, drafts or briefs folders | Never | Never |

The only writes in a shadow run are new draft docs and tabs in the shadow drafts folder, the shadow brief, and new rows on the review sheet's tab (`sources.shadow.review_sheet.tab`). See `locations.md`. Only the full run has a shadow mode; `requests` with `shadow` is refused.

## How each step changes

Step numbers are those of the full run in SKILL.md.

1. **Load the config.** As normal. Stop if any `sources.shadow` key is missing.
2. **Same-day check.** List the shadow briefs folder (not the briefs folder) and collect the dates from titles that contain `Weekly brief` only. The folder may also hold draft docs; ignore them. A shadow brief for the same date already exists: say so and stop (there is no shadow requests mode).
3. **Calendar builder: dry run.** Work out the rows each due run (monthly, ideas, milestone) would propose, using the calendar builder's own rules, and keep them as a list. Write nothing to the Calendar, Ideas or Milestones tabs. The list goes in the brief under "Calendar changes proposed (not written)".
4. **Requests.** Run `request_scan.py` as normal and work out each change, but write nothing: no row edits, no approver's notes rows, no proof log rows. Drafts use the rows as they are. List every change under "Changes that would be made (not written)".
5. **Backlog moves.** Run `backlog.py plan` and list its `out` and `in` rows under "Calendar writes not made". No `deletes`.
6. **Hand edits and series.** Run `snapshot.py compare` and `series_shift.py` as normal (they only read). List their writes under "Calendar writes not made"; draft rows a live run would redraft.
7. **Snapshot.** As normal. Also save the proof log as `proof_before.json`, and list the drafts and briefs folders of the mode read (live for `shadow`, TEST for `test shadow`) so step 22 can confirm nothing new appeared.
8. **Select.** Add `--shadow` to `select_rows.py`. Planned, Draft ready, Approved and Posted rows in the window are all drafted, because live rows may already be produced by hand. Proposed, team-owned, Cancelled and Backlog rows are never drafted. Every item carries `live_status`.
9. **Final text.** Do not read draft tabs or copy anything. List the `final_text` rows in the brief only.
10. **The approver's edits.** When `edit_learning.enabled` is true, read the Approver edits tab as normal so drafters learn from it, but run no capture and write nothing.
11. **Planner and proof match.** Planner as normal. Add `--shadow` to `match_proof.py`: a proof row a person already filled is drafted from the proof item they chose, if it still counts as signed off and is public by the slot date. Otherwise the slot comes back as `flag` with `chosen_item_unusable`: list it in the brief under Proof slots and draft nothing for it.
12. to 17. **Draft, swaps, visuals, check, redraft.** Swaps (step 13) are worked out and listed under "Calendar writes not made"; no backup drafts are made in shadow runs. Otherwise as normal, but build draft and proof bundles with `--shadow` (`make_bundles.py ... draft --rows ... --shadow`), so the drafting skill sees Status Planned and the real one under Live status. Proof drafters run `check_proof_post.py --live` in a `shadow` run (it reads live data); `test shadow` runs leave `--live` out.
18. **Write the drafts** to the shadow drafts folder. Doc name `SHADOW - Drafts - Week NN (DD MMM YY)`; on TEST, `TEST - SHADOW - Drafts - Week NN (DD MMM YY)`. Tabs and tab layout as in draft-doc-format.md. Add one line under the reviewer notes: "Shadow draft. Live status at run time: <status>."
19. and 20. **Collect writes and tidy.** Build `writes.json` exactly as a live run would, but only for rows whose `live_status` is Planned or Proposed, including Planned rows the selection marked blocked (these are the writes a live run would really make). Drafts of rows already Draft ready, Approved or Posted produce no calendar writes. Run `notes_tidy.py` to count the tidies; write no Agent log rows.
21. **No writes.** Run `python3 scripts/calendar_writes.py shadow before.json writes.json --config shared/workspace.json`. Put its `brief_lines` in the brief under "Calendar writes not made". Write nothing to the calendar. Proof log writes are listed the same way ("Proof log row N, Used in calendar row: ..."), never written.
22. **Verify nothing changed.** Read the calendar and proof log again, save as `after.json` and `proof_after.json`, then run `python3 scripts/calendar_writes.py verify before.json after.json --shadow --config shared/workspace.json` and the same for the proof log files. Any change is reported at the top of the brief as "Changed during the run, not by the agents" with the cells. List the drafts and briefs folders again and confirm nothing new appeared since step 7; report anything that did.
23. to 26. **Skipped.** No voice guide proposals, no sort, no hide, no Agent log RUN row and no Agent snapshot save: the next live run must still see every change people made.
27. **Brief.** Shadow brief (brief-format.md, Shadow brief section) in the shadow briefs folder.
28. **Review rows.** Append one row per shadow draft to the review sheet's tab, below the last filled row in column C, columns A to H only: run date (DD MMM YY), Week (`Week NN`, ISO week), Row ID, post date (`DDD DD MMM YY`), What to post, live status, `=HYPERLINK("<tab URL>","Open draft")`, checker result (`Passed`, `Passed after redraft` or `Failed twice`). Never write columns after H and never change an existing row. Read the new rows back.

## Output to the person

As normal, plus: "Shadow run: nothing written to the calendar, proof log, drafts or briefs folders (verify: clean | list)." and the review sheet link.
