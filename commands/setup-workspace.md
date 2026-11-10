---
description: Point the Social Draft Desk agents at your calendar, rules, voice guide, facts, proof log, assets and folders (Drive, Notion, GitHub, SharePoint, local or URL). Run this first.
argument-hint: "[new|update|check] [--config <location>]"
---

Run the workspace-setup skill from this plugin now.

Arguments: $ARGUMENTS

- `new` (default when no config exists): start with the skill's opening prompt, then the questions, source checks and save. The questions include the run schedule (full run day and time, requests run days and time), how typed dates are read (day first or month first), who may write asks, whether the approver's word counts as proof sign-off (explain the trade-off; default off) and whether edit learning is on.
- `update`: read the config at `--config` and change only what the person names.
- `check`: read the config at `--config`, run `check_workspace.py` and test every source. Change nothing.

Ask before assuming anything. Never publish, post or send anything.
