---
description: Run the weekly content run, or the light weekday requests run (drafts, checks, calendar updates and the brief). Never publishes.
argument-hint: "<test|live> [requests|rerun] | <shadow|test shadow> [--as-of YYYY-MM-DD] [--config <location>]"
---

Run the weekly-orchestrator skill from this plugin now.

Arguments: $ARGUMENTS

- `--config <location>` is where `workspace.json` lives (a Drive file, Notion page, repo path or local path). If it is not given, ask the person. If no config exists, run the workspace-setup skill first, then start this run.
- `test` uses the `test` location of every write source in `workspace.json`: calendar (with its tabs), proof log, drafts folder and briefs folder. `live` uses the `live` locations. If neither is given, ask which.
- `live` runs only when the agent register records a passing TEST run with the current config. If it does not, say so and offer a `test` run.
- `requests` (written `/weekly-run <test|live> requests`; the words may come in either order) runs requests mode: a light weekday run that acts only on new asks in Notes, new ideas, hand edits since the last run, Backlog moves and series shifts, drafts the rows they touch, and writes `Update - DD MMM YY` only if it changed something. The full run happens once a week (`run.full_run`).
- A second run on a day that already has a weekly brief switches to requests mode by itself and handles only what changed since.
- `rerun` (with `test` or `live`, in either order) forces a full rerun on a day that already has a weekly brief: the skill passes `--rerun` to `select_rows.py` and the brief name gets " (2)" (or the next number). Use it only when the person asks for it.
- `shadow` reads the live calendar and proof log and writes drafts, the brief and review rows to `sources.shadow.*` only (weekly-orchestrator `references/shadow-mode.md`). Nothing is written to the calendar, proof log, drafts folder or briefs folder. Shadow applies to the full run only.
- `test shadow` runs shadow mode on the TEST calendar and proof log, writing to the TEST shadow locations.
- `--as-of YYYY-MM-DD` simulates the run date. Use it only with `test` or `test shadow`.

Follow the skill's steps in order and finish with its short output to the person and the brief or update link. Do what people ask in Notes, on the Ideas tab and by editing cells, and always produce a base draft. Never publish, post or send anything. Spelling, units and dates follow `writing.*` in `workspace.json`.
