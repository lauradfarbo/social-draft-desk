# Weekly runbook

For the person who approves and posts (the approver). It assumes the plugin is installed, `/setup-workspace` has passed, and both scheduled tasks are on (`docs/go-live-checklist.md`).

## What the system does

Each week the agents read the content calendar, draft the posts due in the next one to two weeks, check every draft against the rules, voice guide and facts sheet, and write a one-page brief. They never publish, post, send email or submit anything. You review, approve and post.

It runs as two scheduled tasks on your account:

- **Full run**, once a week at `run.full_run` (default Monday 12:30). Plan check, drafts, backup posts, the weekly brief.
- **Requests runs**, on `run.requests_runs` days (default Tuesday to Friday 06:00). They act only on what you asked or changed since the last run, and write a short update only if they changed something.

Times are in `company.timezone`. The tasks run in the cloud, so your computer can be off.

## Time it takes

About 60 to 90 minutes of review a week, plus 2 minutes per post on posting day. The first full run of each month adds about 15 minutes to review new proposed rows.

## Your week

| When | What you do |
| --- | --- |
| Any time | Add post ideas on the Ideas tab. Write news or facts (a partner signed, an event date) in the row's Notes. Add approved photos to the assets folder. Change events on the Milestones tab |
| Before the full run (at least 15 minutes before) | Make the week's changes so the run picks them up. Set Proposed rows to Planned, or write in Notes what to change. Edit a row's cells directly if that is easier: Date, What to post, Pillar, Channel, Title / angle, Content type, Spec. Plain words are enough. Type dates the way the sheet reads them (`dates.typed_order`) |
| Full run (automatic) | Drafts the Planned rows due in the next 7 to 14 days, checks them, updates the Calendar and writes `Weekly brief - DD MMM YY` in the briefs folder. You get a notification |
| After the full run (60 to 90 minutes) | Open the brief. Do what "To finish drafts: what to send" asks by writing it in the row's Notes. Open the This Week tab, click each Draft link and edit the post in the draft doc, never on the channel itself: the agents learn from your edits there. Set Status to Approved |
| Image prompts | When Visual says "Needed: <AI image tool> image", open the post's tab, edit the prompt if you like, and paste it into the AI image tool. Attach the product reference photo if the prompt shows the product. Check the image is accurate, then save it to the assets folder. Partner, customer and live event posts use real photos only |
| Requests run days (automatic) | Acts on Notes, cell edits and ideas from the day before. Writes `Update - DD MMM YY` only if it changed something |
| Posting day | Copy the text from the draft doc into the channel. Put links in the first comment if your rules say so. Post. Set Status to Posted: the next run saves the final text |
| First full run of the month | The calendar is extended to 13 weeks ahead and the brief may propose voice guide changes from your edits. Review the new Proposed rows and set them to Planned, or comment in Notes. Approve or reject each voice guide proposal and edit the voice guide yourself |

## Statuses

| You set | Agents set |
| --- | --- |
| Planned: draft this row | Proposed: a new row for you to review |
| Approved: the draft is ready to post | Draft ready: a checked draft is in the draft doc |
| Posted: it is live | Fallback post: a backup for the row above |
| Cancelled: drop the post | |
| Backlog: keep it for later | |

Only Planned rows are drafted. A row with gaps is still drafted: the gaps are in [square brackets] and What's missing says what to send.

## Common actions

| To | Do this |
| --- | --- |
| Change a post | Write what you want in its Notes, or edit the cell. The next run makes the change, says what it did in one Notes line, and redrafts into a v2 tab if the row was already drafted |
| Keep a post for later | Set Status to Backlog. The next run moves the row, draft included, to the Backlog tab. To bring it back, set its Status there to Planned, with a date in Notes if you want one |
| Drop a post | Set Status to Cancelled. Never delete a row. The run hides it. Cancel a blog and its teaser together |
| Use a backup row | A pale gold row with Status Fallback post is a backup for the row above. Set it to Approved and the row above to Cancelled |
| Run a series | Write "post 1 of 5" and so on in Notes. Move a post later and the later posts move with it. Cancel one and the series moves back one slot; write "`requests.series_drop_word`" (default "drop") in its Notes first if you want it gone instead |
| Lift a hold | Write "CONFIRMED" and the date in the row's Notes, set the matching Milestones row's Confirmed to Yes, or approve the fact on the facts sheet |
| Give proof news | Write who, what, from when it can be named, and any event and date in the row's Notes. What happens next depends on `proof.approver_word_is_signoff`: off, the row asks you to log it in the proof log with sign-off; on, the agents log it for you |
| Run by hand | Start a new task in Claude and type `/weekly-run live --config <location>` (full run) or `/weekly-run live requests --config <location>`. A second run on the same day handles only what changed since the first; to redo the full run, type `/weekly-run live rerun --config <location>` |

## What you never need to do

- Edit the gray agent columns, the This Week tab or any hidden tab.
- Use a set phrase. Plain words count.
- Tell the agents twice. If an ask was handled, the Notes line says so. If it could not be, the brief says why.
