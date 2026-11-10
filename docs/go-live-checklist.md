# Go-live checklist

For a buyer who sets this up and runs it alone. Allow about 90 minutes for setup and the TEST run, then one supervised live week.

## 1. Install and connect

- [ ] Use a Claude plan that includes plugins, connectors and scheduled tasks, on the company's own account. Nothing should depend on a personal or contractor account.
- [ ] Install the plugin (README, Quick start) and ask Claude "which version of social-draft-desk is installed?". Note the version for the task prompts.
- [ ] Connect only the connectors your sources need (for Google Workspace: Drive, Docs and Sheets) with the company account. Turn off connectors the run does not use.
- [ ] Confirm the approver can edit every file and folder the run uses: calendar, proof log, facts sheet, drafts folder, briefs folder, assets folder and the TEST copies.

## 2. Set up the workspace

- [ ] Run `/setup-workspace`. Answer every question, including the run schedule, typed date order, who may write asks, the proof sign-off option (default off) and edit learning.
- [ ] No voice guide yet: run the `brand-voice-guide` skill. No calendar yet: ask the `calendar-builder` skill to convert your approved plan. Build it on the TEST copy first.
- [ ] Check the calendar has every tab in `calendar.tabs`, including the hidden Agent snapshot, and the Status dropdown has all eight statuses.
- [ ] Set the sheet's locale to match `dates.typed_order`.
- [ ] `/setup-workspace check` passes with no errors. Read every warning.

## 3. TEST run

- [ ] Run `/weekly-run test --config <location>` and open the brief in the TEST briefs folder.
- [ ] Open the TEST draft doc. Check each draft against its row: right type, right date, claims only from approved facts, gaps in [brackets] listed in What's missing.
- [ ] Try one of each on the TEST calendar, then run `/weekly-run test requests --config <location>` and check the result: an ask in Notes, a direct cell edit, Backlog, Cancelled, a backup row used.
- [ ] Record the result (date, mode, pass or fail, notes) in the agent register.

## 4. Schedule the two runs

Create two scheduled tasks on the company account, named as you like (for example "Weekly content run (full)" and "Weekday requests run"). Two tasks, never one. Set each:

| Setting | Full run | Requests run |
| --- | --- | --- |
| Schedule | `run.full_run` weekday and time | `run.requests_runs` weekdays and time |
| Approval | Automatic, if your organization allows it; otherwise the run stops at each approval | Same |
| Notifications | Push and email | Push and email |
| Connectors | Only those the run needs | Same |

Pick a time a few minutes off the hour or half hour; scheduled runs at :00 and :30 can be delayed. Leave at least 15 minutes between your weekly edits and the full run.

Copy both task prompts from `skills/weekly-orchestrator/references/scheduled-prompts.md` (one place, so they never drift) and fill each `<...>` from `workspace.json`.

- [ ] Both tasks created, settings checked in the Scheduled tasks list, next run times as expected.
- [ ] Until the first live week, keep both tasks off, or use `test` in place of `live` in both prompts.

## 5. First live week

- [ ] Make your weekly edits before the full run.
- [ ] After the full run, open the brief in the live briefs folder and confirm it is there.
- [ ] Work through the brief and drafts as in `docs/runbook.md`. Edit drafts in the draft doc, not on the channel.
- [ ] On a requests run day, make one small ask in Notes the day before and check the update.

## 6. What to check in the first two weeks

- [ ] Every Planned row due in the window was drafted or has a reason in the brief.
- [ ] No draft states a claim that is not on the facts sheet, the proof log or the From the approver's notes tab.
- [ ] No outside person or company is named who is not in the proof log.
- [ ] The verify result in each summary is clean, with no unexpected changes at the top of the brief.
- [ ] Cancelled rows are hidden and appear nowhere in the brief or updates.
- [ ] Backup rows sit directly under their originals.
- [ ] Notes on each row hold your text plus one agent line.
- [ ] Two weekly runs completed with no help: record this in the agent register as the go-live date.
