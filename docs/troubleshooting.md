# Troubleshooting

To run by hand at any time, start a new task in Claude and type `/weekly-run live --config <location>` (full run) or `/weekly-run live requests --config <location>` (requests run). A second run on the same day handles only what changed since the first; `/weekly-run live rerun --config <location>` redoes the full run. To try something safely, use `test` instead of `live`.

## Problems and fixes

| Problem | How you notice | Fix |
| --- | --- | --- |
| Missed run | No brief in the briefs folder about an hour after the full run time, and no notification | Open Scheduled tasks in Claude and check the full run task is on and what its last run says. Then run `/weekly-run live` by hand. The run recovers what was missed and names the missed run date in the brief. Overdue rows are listed, not drafted |
| Connector signed out | The run ends with a connector or sign-in error, or the notification says it could not read a file | In Claude settings, open Connectors and reconnect the ones your sources use (for Google Workspace: Drive, Docs and Sheets) with the company account. Check both scheduled tasks still list them. Run by hand |
| Plugin version stop | Notification: "the plugin must be updated to <version>". Nothing was read or written | The installed plugin is older than the scheduled task requires. Install the required version, ask Claude "which version of social-draft-desk is installed?", then run by hand. The check exists because an older version may not save the Agent snapshot, so the next run would read its own writes as your hand edits |
| Draft off-tone | The post reads wrong for the company | For one post, write what you want in Notes ("shorter, more practical, lead with the cost point"). The next run redrafts it into a v2 tab. For a lasting fix, edit the voice guide. Your edits in the draft doc also teach the agents, and monthly voice guide proposals appear in the brief |
| Wrong status | A row is not drafted, or shows a status you did not expect | Only Planned rows are drafted: set Proposed rows to Planned. Agents only ever set Proposed, Draft ready and Fallback post; set any other status yourself. A Cancelled row is hidden, not lost: unhide the rows (the arrows in the row numbers) or set its Status back. A Backlog row has moved to the Backlog tab. If a row was deleted by mistake, restore it from the sheet's version history |
| Missing proof | The brief says a proof slot is not drafted; Notes propose a swap and a backup row may appear | Write the news in the row's Notes (who, what, from when it can be named, event and date). If `proof.approver_word_is_signoff` is on, the agents log it in the proof log. If it is off, log it yourself (or ask whoever keeps the proof log) with Sign-off status Yes. Otherwise use the backup row or the swap, or set the slot to Backlog. Agents never invent a customer, partner or quote |
| Guard refusal | The brief or summary lists a refused or guarded write, or cells "changed by a person during the run" | The row moved, was deleted, or had its Row ID or Status changed between the agent's read and its write, so the agent did not write. Nothing is lost: the next run starts from a fresh read and tries again. Avoid editing in the minutes the run is working. If the same row is refused two runs in a row, check its Row ID in column M was not typed over |
| Cut-off doc read | The run stops before drafting and says a source was cut off or did not contain its expected phrase | Each doc in `workspace.json` has an `expect_phrase` near its end. Either the read was cut off (very long doc, connector limit) or someone removed or reworded that phrase. Open the doc and check the phrase is still near the end. If you changed it, update `sources.<key>.expect_phrase` with `/setup-workspace update`. Then run by hand |
| Ask not acted on | Your Notes text is still there with no agent line after it | Check the row is Planned or Proposed (agents never change Approved, Posted or Cancelled rows) and that you are in `requests.from`. If part of the ask broke a hard rule, the agent line says what was left out and why |
| Config error | The run stops at the start with a config error | Run `/setup-workspace check`. It lists every error and how to fix it |

## Where the hidden tabs are

In Google Sheets, click the All sheets button (four lines, bottom left). Hidden tabs are listed there; click one to open it. To hide it again, right-click its tab and choose Hide sheet. Other platforms keep these as separate tables or pages under the names in `calendar.tabs`.

| Tab | What it holds | Edit it? |
| --- | --- | --- |
| Agent log | Older agent Notes lines, moved word for word, and one RUN row per run with full run details | No |
| From the approver's notes | Each fact you gave in Notes or on Ideas, word for word, with where and when | No. Say corrections in Notes |
| Approver edits | Your edits to drafts and image prompts, used to learn your style | No |
| Agent snapshot | The Calendar as the last run left it, used to spot your hand edits | Never. Editing it makes the next run miss or invent hand edits |

The gray agent columns on the Calendar (Row ID onward, M to V) are collapsed: click + above column M to open them. Do not edit them. Never type in the Action needed or Draft columns or on the This Week tab: they are formulas.

## When to ask for help

If the same problem comes back after a fix, or a run reports an unexpected change at the top of the brief, stop the scheduled tasks, run `/weekly-run test` and use `docs/change-guide.md` to ask Claude for a fix on the TEST files.
