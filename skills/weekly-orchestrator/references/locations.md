# Locations used by the weekly run

Locations come from `workspace.json` (`sources.<key>`), live or test. This file names the keys, never IDs or URLs. Each source's `platform` says how to read it (`docs/workspace-config.md`, "Adapter rules"). The person running the skill, or the scheduled task prompt, says `test`, `live`, `shadow` or `test shadow`. If it is not stated, ask.

For each key, `live` is the client's working file and `test` is its TEST copy. A read-only source with `test: null` uses the `live` location in every mode.

## Read only (every mode)

| Key | Saved as | Used by |
| --- | --- | --- |
| `sources.rules` | `rules.md` | Everyone. Wins over every other file |
| `sources.plan_rules` | `plan_rules.md` | Planner, calendar builder |
| `sources.voice_guide` | `voice.md` | Drafters, checker, monthly voice guide proposals |
| `sources.facts_sheet` (`tab`, `range`) | `facts.json`, `facts_approved.json` | Drafters (approved rows only), checker, planner |
| `sources.long_form` | `long_form.md` | Drafters read one chapter only. Read only when something is drafted |
| `sources.long_form.chapter_map` | `chapter-map.md` | Drafters, swap angles |
| `sources.assets` | `assets.txt` | Drafters, checker, `visuals.py`. List every subfolder once per run |
| `sources.other[]` | as the step needs | For example, published blog text for a teaser (`blog.txt`) |
| `sources.agent_register` | not saved | Confirms a passing TEST run before a `live` run |

## Calendar tabs

All in `sources.calendar`, live or test. Tab names come from `calendar.tabs` (defaults below). Look up each tab's sheetId with `get_spreadsheet` once per run.

| Key in `calendar.tabs` | Default name | Range | Saved as | Agents write |
| --- | --- | --- | --- | --- |
| `calendar` | Calendar | A1:V | `before.json`, `after.json` | Cells allowed by the column lock, fallback rows (`insert_after`), rows back from the Backlog, sort and hide |
| `backlog` | Backlog | A1:X | `backlog.json` | Rows moved from the Calendar (`backlog.py`); rows removed only after their copy is read back |
| `ideas` | Ideas | A1:H | `ideas.json` | Through `tab_guard.py` only (calendar builder) |
| `milestones` | Milestones | A1:G | `shared/milestones.json` | Through `tab_guard.py` only (calendar builder) |
| `approver_notes` | From the approver's notes | A1:G | `shared/approver_notes.json` | New rows, one per fact, through `tab_guard.py`; Used in |
| `agent_log` | Agent log | A1:E | `agent_log.json` | New rows only: moved Notes lines, one RUN row per run |
| `approver_edits` | Approver edits | A1:I | `shared/approver_edits.json` | New rows only (`edit_capture.py`), only when `edit_learning.enabled` is true |
| `agent_snapshot` | Agent snapshot (hidden) | A1:L | `shared/snapshot.json` | The whole tab, once, as the last calendar write of every run (`snapshot.py save`) |
| `this_week`, `how_to_use` | This Week, How to use | | not read | Never |

## Read and write by mode

| Key | `test` | `live` | `shadow` | `test shadow` |
| --- | --- | --- | --- | --- |
| `sources.calendar` (every tab above) | `test`: read, write | `live`: read, write | `live`: read only | `test`: read only |
| `sources.proof_log` (`tab`, `range` A1:J) | `test`: read, write column J; new rows only when `proof.approver_word_is_signoff` is true | `live`: as `test` | `live`: read only | `test`: read only |
| `sources.drafts_folder` | `test`: write; list for edits | `live`: write; list for edits | never written | never written |
| `sources.briefs_folder` | `test`: read titles, write | `live`: read titles, write | `live`: list only (verify) | `test`: list only (verify) |
| `sources.shadow.drafts_folder` | not used | not used | `live`: write | `test`: write |
| `sources.shadow.briefs_folder` | not used | not used | `live`: read titles, write | `test`: read titles, write |
| `sources.shadow.review_sheet` (`tab`) | not used | not used | `live`: append A to H | `test`: append A to H |

The orchestrator is the only writer to these locations during a run. Subagents get local copies and write nothing.

Never write to the calendar (any tab), proof log, drafts folder or briefs folder (live or TEST) in a shadow run. If a shadow key is missing from the config, a shadow run cannot start: say so and offer `/setup-workspace update`. If a calendar tab in `calendar.tabs` is missing, stop, name the missing tab and offer to add it with the calendar builder (`calendar-builder/references/calendar-schema.md`), on TEST first.
