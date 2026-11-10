# Scheduled task prompts

Two scheduled tasks run the system, both on the client's own account and in `company.timezone`. Create them only after the agent register records a passing TEST run, and keep them off until the go-live date. Fill each `<...>` from `workspace.json` when you create the task; change the schedule in the task settings, not here. Never put a file ID in a prompt: locations come from the config.

| Task | Schedule | Argument |
| --- | --- | --- |
| Full run | `run.full_run.weekday` at `run.full_run.time` (default Monday 12:30) | `live --config <location>` |
| Requests run | `run.requests_runs.weekdays` at `run.requests_runs.time` (default Tuesday to Friday 06:00) | `live requests --config <location>` |

Pick a full run time after the approver usually reviews and edits, so the run sees those edits. Avoid exactly on the hour; a few minutes before or after is less likely to be delayed.

## Full run

```
Run the weekly content run with the social-draft-desk plugin: use the /weekly-run command, or the weekly-orchestrator skill, with the arguments "live --config <workspace.json location>". Requests runs are a separate scheduled task.
First confirm the loaded plugin version (.claude-plugin/plugin.json) is <current version> or later. If it is lower, stop before reading or writing anything, send a notification saying the plugin must be updated, and end with one line saying why.
The agent register records a passing TEST run with the current config, so treat this as the go-ahead for a live run; do not stop to ask. Use only the live locations in workspace.json, never the TEST or shadow ones.
Spelling, units and dates follow writing.* in workspace.json. Use them in drafts, draft tabs, Notes and the brief, and tell every drafter and checker subagent the same.
People may sort or reorder Calendar rows at any time: never rely on row positions from an earlier read; always use a fresh read and the Row ID guard before writing.
Plain words count: when what a person wrote or changed is clear, act on it and say in the Notes line what you took it to mean. Read typed dates per dates.typed_order.
This run is unattended. Do not stop to ask questions. When a choice is truly unclear (two readings that cannot both be right), take the safe option: do not change or draft the row, and flag both readings in Notes and in the brief.
Never publish, post, send email or submit anything.
Follow the skill's steps in order, including asks, Backlog moves, hand edits and series shifts, the column lock, the Row ID guard just before any calendar write, the tab guard for Ideas, Milestones and approver's notes writes, the read-back verify, the sort and hide of Cancelled rows and the Agent snapshot save as the last calendar write. Finish by writing the weekly brief. Skip every Cancelled row and never mention one.
End with the skill's short output, the verify result and the brief link. Send a notification only when something was drafted or changed, or something needs the approver.
```

## Requests run

```
Run the weekday requests run with the social-draft-desk plugin: use the /weekly-run command, or the weekly-orchestrator skill, with the arguments "live requests --config <workspace.json location>". It handles only what changed since the last run: open asks in Notes, new ideas, hand edits found by the Agent snapshot, Backlog moves and series shifts, for rows within series.draft_within_days days or in a series. The full run is a separate scheduled task.
First confirm the loaded plugin version (.claude-plugin/plugin.json) is <current version> or later. If it is lower, stop before reading or writing anything, send a notification saying the plugin must be updated, and end with one line saying why.
The agent register records a passing TEST run with the current config, so treat this as the go-ahead for a live run; do not stop to ask. Use only the live locations in workspace.json, never the TEST or shadow ones.
Spelling, units and dates follow writing.* in workspace.json, in drafts, draft tabs, Notes and the update, and in every subagent prompt.
People may sort or reorder Calendar rows at any time: always use a fresh read and the Row ID guard before writing.
Plain words count: when what a person wrote or changed is clear, act on it and say in the Notes line what you took it to mean. Read typed dates per dates.typed_order.
This run is unattended. Do not stop to ask questions. When a choice is truly unclear, take the safe option: do not change or draft the row, and flag both readings in Notes and in the update.
Never publish, post, send email or submit anything.
Follow the skill's requests mode, including the column lock, the Row ID guard, the tab guard, the read-back verify, the sort and hide of Cancelled rows and the Agent snapshot save. If nothing is open, write nothing but the sort, hide and snapshot, and end with "Nothing open." Write "Update - DD MMM YY" only if something was done. Skip every Cancelled row and never mention one.
End with the skill's short output, the verify result and the update link. Send a notification only when something was drafted or changed, or something needs the approver.
```

## Why the version check

The Agent snapshot is saved at the end of every run. A run on an older plugin that does not save it would make the next run read the agents' own writes as a person's hand edits. Update `<current version>` in both prompts after installing a new required version, never before.
