# Script command lines

Every script is Python 3 standard library, reads local files saved exactly as returned, writes nothing to any platform, and prints JSON. Run with no arguments to see its usage. Every script that applies client rules takes `--config workspace.json`; a missing optional key uses the default in `docs/workspace-config.md`, and a missing optional check is skipped. Paths are relative to `skills/weekly-orchestrator/` unless named otherwise. Table files have the shape `{"values": [[headers], [row 2], ...]}`.

## Saving

| Command | What it does |
| --- | --- |
| `save_result.py tool <out.json> <tool name part> <input part> [n] [--transcript <file.jsonl>]` | Saves the n-th latest (default 1) connector result whose tool name contains the first part and whose input contains the second, byte for byte, including results the app saved to a file. Example: `save_result.py tool before.json get_values "Calendar!A1:V"` |
| `save_result.py report <out.json> <text part> [--transcript <file.jsonl>]` | Saves the latest JSON object in a subagent's final report that contains the text part (spacing ignored). Example: `save_result.py report returns/W11-02.json '"row_id": "W11-02"'`. Exit 1 if nothing matches |
| `doc_text.py read_doc.json out.md [--expect "<phrase>"]` | Doc text from a Docs read; fails when the phrase is missing |
| `extract_final.py doc.json <tab URL or tab ID>` | The tab text above the dashed line, exactly; also `image_prompt` and `image_prompt_original` when the tab has both prompt lines. Exit 1 if the tab or the dashed line is missing |

`save_result.py` reads only one transcript: the `--transcript` file, or else the newest `*.jsonl` directly in `~/.claude/projects/<working directory, each character other than a letter or digit as "->/` (the current session). It never reads other projects or older sessions. It also reads a file the app saved a large result to, only when that transcript names it. `SAVE_RESULT_TRANSCRIPTS` (a glob) is a test override only. Exit 2 when no transcript is found: pass `--transcript`.

## Asks, hand edits and series

| Command | What it does |
| --- | --- |
| `request_scan.py calendar.json [--ideas ideas.json] [--as-of YYYY-MM-DD] [--days 91] --config workspace.json` | Prints `{"notes_asks", "open_asks", "ideas"}`. `notes_asks`: per row from 14 days ago to `--days` ahead (not Posted, Cancelled or Backlog), the Notes text no agent wrote (agent lines start with `notes.agent_prefix` or another agent prefix and a date), with `kind` (`ask`, `standing`, `info`) and `handled` (an agent line after it says "as asked"). `ideas`: Ideas rows with Idea filled and Status blank or New |
| `snapshot.py compare calendar.json milestones.json snapshot.json --config workspace.json` | Prints `{"first_run", "row_changes", "milestone_changes", "brief_lines"}`. `row_changes`: `{"row", "row_id", "status", "drafted", "changed": {col: [before, now]}}` for rows in the snapshot, not Posted, Cancelled or Backlog, that differ in a `calendar.request_columns` column. `milestone_changes`: Start date or Confirmed changes, with `confirmed_now`. An empty snapshot reports nothing |
| `snapshot.py save calendar.json milestones.json [old_snapshot.json] --config workspace.json` | Prints `{"range": "<Agent snapshot tab>!A1:L<n>", "values"}`: the whole tab (Kind, Key, Date, Status, What to post, Pillar, Channel, Title / angle, Content type, Spec, Confirmed, Saved), padded with blank rows so a longer old snapshot is cleared. Run from `after.json` as the last calendar write |
| `series_shift.py calendar.json snapshot.json [--as-of YYYY-MM-DD] --config workspace.json` | Prints `{"writes", "new_rows", "notes", "notes_meta", "brief_lines"}`. Moved post: later posts move to the next date on their own weekday. Cancelled post: the series is pushed back one slot (the last post's content goes to a new Proposed row in `new_rows`), unless its Notes contain `requests.series_drop_word`. Writes carry `"request": "series shift"` and `"series": true`; `notes_meta` marks rows with `"redraft": true` |
| `proof-intake/scripts/proof_log_add.py proof_log.json new_items.json [--as-of YYYY-MM-DD] --config workspace.json` | Only when `proof.approver_word_is_signoff` is true. Prints `{"rows", "range", "skipped", "brief_lines"}`: new proof log rows with Sign-off status Yes; duplicates (same Type and Organization) skipped; never edits a person's row |

## Backlog, sort and hide

| Command | What it does |
| --- | --- |
| `backlog.py plan calendar.json backlog.json [--as-of YYYY-MM-DD] --config workspace.json` | Prints `{"out", "in", "brief_lines"}`. `out`: Calendar rows with Status Backlog, as 24 Backlog cells (A:V, W Moved to Backlog, X Was dated). `in`: Backlog rows set to Planned, as 22 Calendar cells on the date in Notes (read per `dates.typed_order`) or the best free slot, Week of the new date, null in the formula columns |
| `backlog.py deletes plan.json cal_b.json cal_m.json bl_b.json bl_m.json --cal-sheet <id> --bl-sheet <id>` | From fresh reads of Status and Row ID on both tabs, prints `{"requests", "refused"}`: delete requests, bottom-up, only for rows whose Row ID is found once, whose Status is unchanged and whose copy exists on the other tab |
| `backlog.py sort calendar.json --sheet <id> --config workspace.json` | Prints `{"requests": [sortRange]}`: Date, then AM/PM, then Row ID, so `<id>-FB` sits under its original. Header and formula rows stay in place. Run hide straight after |
| `backlog.py hide calendar.json --sheet <id> [--hidden 13,19] --config workspace.json` | Prints `{"requests", "hidden_count", "shown_count"}`: hides every Cancelled row and shows a hidden row that is no longer Cancelled. Changes no cell value |

## Notes

| Command | What it does |
| --- | --- |
| `notes_tidy.py calendar.json --report --config workspace.json` | Rows whose Notes hold agent lines, with counts |
| `notes_tidy.py calendar.json current.json [--log agent_log.json] --as-of YYYY-MM-DD --config workspace.json` | `current.json`: `[{"row_id", "current": "<prefix> DD MMM YY: ...", "reason"}]`. Prints `{"writes", "log_rows"}`, plus `log_range` with `--log` (lines already in the log are skipped): each row keeps the person's text word for word and in order, plus the one current line; older agent lines go word for word to `log_rows` (Date moved, Row ID, Agent, Text, Reason). Sources lose duplicates. Writes carry `"tidy": true` |

## Selection, planning and drafting

| Command | What it does |
| --- | --- |
| `select_rows.py calendar.json --config workspace.json [--facts facts.json] [--milestones milestones.json] [--as-of YYYY-MM-DD] [--horizon 13] [--series-days N] [--briefs YYYY-MM-DD,...] [--updates YYYY-MM-DD,...] [--mode full\|requests] [--touched <Row IDs>] [--rerun] [--shadow]` | Row actions: `draft` (with `gaps` and `placeholders`), `proof`, `refresh`, `fallback_row`, `team_owned`, `proposed`, `blocked`, `in_review`, `overdue`, `cancelled`; plus `final_text` and `missed_runs`. Backlog rows are left out. `--series-days` defaults to `series.draft_within_days` |
| `plan_check.py calendar.json facts.json [proof_log.json] --config workspace.json [--milestones milestones.json] [--as-of YYYY-MM-DD] [--weeks 4]` | Planner checks; also `cancelled_milestones` and, with `plan.precedence` `dated_events_first`, `precedence_moves` |
| `proof-intake/scripts/match_proof.py ... --config workspace.json` | Proof slots and advisory rows matched to proof items (proof-intake SKILL) |
| `make_bundles.py <run dir> <plugin root> plan\|draft\|proof\|fallback\|redraft\|check [options]` | Builds bundles (subagent-prompts.md). `draft --rows <ids> [--select select.json] [--proof-rows N,...] [--shadow]`; `proof --rows <ids> --proof-rows <N,...>`; `fallback --rows <ids> --swaps swaps_final.json`; `redraft --from <bundle> --previous <file> --fixes <file>`; `check --draft <file> [--proof-row N] [--suffix -2] [--content-type T]` |
| `swap_slots.py calendar.json select.json match.json --config workspace.json [--drafter-blocked <ids>] [--backlog backlog.json] [--as-of YYYY-MM-DD] [--days N] [--max-fallbacks N]` | Prints `{"swaps", "fallbacks_skipped", "stale_notes"}`. A row that already has a `-FB` row gets no new backup. `stale_notes`: dated conditions that no longer match, or passed cut-offs |
| `visuals.py before.json assets.txt returns/<files...> --config workspace.json [--weeks N]` | Resolves visual clashes across one run's returns |
| `check_compliance.py draft.json facts.json --config workspace.json [--proof proof_item.json]` | The checker's scripted checks (also reads `person_items.json` next to it) |

## Edit learning (only when `edit_learning.enabled` is true)

| Command | What it does |
| --- | --- |
| `edit_capture.py calendar.json tab_texts.json approver_edits.json [--as-of YYYY-MM-DD] [--prompts prompts.json] --config workspace.json` | Prints `{"rows", "range", "brief_lines"}`: one Approver edits row per new version of a Draft ready, Fallback post, Approved or Posted tab that differs from Original draft (Light edit or Rewrite). `prompts.json` `{"<Row ID>": {"now", "original"}}` adds a row per edited image prompt, Content type "Image prompt: <type>". An edit already logged with the same text is skipped |

## Calendar writes

| Command | What it does |
| --- | --- |
| `calendar_writes.py plan before.json writes.json [--log agent_log.json] --config workspace.json` | Column lock. Prints `{"accepted", "refused", "inserts", "guard_ranges"}`; exit 1 if any refused. `--log`: a Notes line already moved to the Agent log is not appended again |
| `calendar_writes.py guard before.json writes.json fresh_b.json fresh_jm.json [--log agent_log.json] --config workspace.json` | Row ID guard on fresh reads just before writing. Prints `{"accepted", "inserts", "refused", "changed_by_person", "plan_refused"}`; exit 1 only when `refused` is not empty. Notes and Sources are re-appended to the current cell; a tidy is refused if the cell changed during the run |
| `calendar_writes.py verify before.json after.json writes.json [--guard guard.json] --config workspace.json` | Read-back check. With `--guard`, rows are matched by Row ID and inserted rows are expected; lists `deleted_row_ids`, `added_row_ids`, `moved_rows` and `changed_by_person_during_run` |
| `calendar_writes.py weeksync before.json --config workspace.json` | Week writes for rows whose Date a person moved by hand (ISO week). Row ID never changes |
| `calendar_writes.py shadow before.json writes.json --config workspace.json` | Same lock check; prints `{"would_write", "would_refuse", "brief_lines"}` and writes nothing |
| `calendar_writes.py verify before.json after.json --shadow --config workspace.json` | Shadow runs: every changed cell is reported. Works on any table saved the same way |

Write kinds in `writes.json` (format in the script header): `[{"row", "col", "value", "by"}]`, with these extras.

| Kind | Shape | Allowed |
| --- | --- | --- |
| Plain | `{"row", "col", "value"}` | Status only to Draft ready from Planned (with `"check": "pass"` and a Draft URL write); Visual, What's missing, Draft URL set; Notes and Sources append; Original draft only if empty; Final text only if empty and Posted; Proof item on proof and advisory rows; Title / angle while it is a proof placeholder |
| `"request": "<where asked>"` | Plain write plus the field | Date (YYYY-MM-DD), What to post, Pillar, Channel, Title / angle, Content type, Spec on a Planned or Proposed row. A moved Date gets its Week write added; a Week that does not match the Date is refused |
| `"series": true` | From `series_shift.py` | Date, Title / angle, Spec also on Draft ready rows |
| `"v2": true` | On Original draft, with a Draft URL write to the new tab | Replaces Original draft with the v2 redraft |
| `"tidy": true` | `{"row", "col": "Notes" or "Sources", "value": <whole cell>}` from `notes_tidy.py` | Replaces the cell only if every part a person wrote survives word for word and in order, with at most one agent line; Sources may only lose duplicates |
| `"insert_after": "<Row ID>"` | `{"insert_after", "values": {header: value}}` | A full new row under the original: Row ID `<original>-FB`, Status Fallback post; the original must exist, not be Cancelled or Backlog, and have no `-FB` row yet. `plan` prints `inserts` bottom-up with `after_row` and the values; write cells first, then inserts in the order given |

Everything else is refused: Action needed, Draft and other formula columns, Row ID, AM/PM, Published link, Week (except as above), any write to a Cancelled or Backlog row, and any row that does not exist.
