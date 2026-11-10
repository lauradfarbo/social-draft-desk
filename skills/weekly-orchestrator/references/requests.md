# Acting on what people ask

The approver and the team should never need to know which columns agents can change. They write what they want, or edit the cell; the run does it. This applies when `requests.enabled` is true (the default). Asks count from the people in `requests.from`: `approver` (`company.approver.name`) and, when listed, `team` (everyone in `company.people`). An ask signed by anyone else is listed under "Needs the approver", not acted on.

## Where asks come from

| Place | What it looks like | Found by |
| --- | --- | --- |
| A row's Notes | Plain text with no agent prefix, for example "Instead of the partner news, make this a call-out to resellers. Draft a post." | `request_scan.py` (`notes_asks`, `kind: ask`, `handled: false`) |
| Ideas tab | A new idea, including ones that change existing rows ("Make the next 3 customer stories advisory board announcements") | `request_scan.py` (`ideas`), then the calendar builder's ideas run |
| A cell the person edited | A changed Date, What to post, Pillar, Channel, Title / angle, Content type or Spec (`calendar.request_columns`), or a Start date or Confirmed change on the Milestones tab | `snapshot.py compare` (`row_changes`, `milestone_changes`) |

A dated decision ("Sam Ortega, 14 MAR 26: ...", "On hold (...)") is `kind: standing`: keep following it, it is not a new ask, until a person says something that ends it. Plain words end it: `requests.hold_lift_word` (default "CONFIRMED") with a new date on a held row, "go ahead", Confirmed set to Yes on a Milestones row of the dependency's type (`plan.dependencies[].milestone_type`), or the dependency's fact set to an approved Status. Never wait for a set phrase such as "hold lifted". `kind: info` is a link a person added (for example a published blog link): use it, no row change needed.

Typed dates are read per `dates.typed_order`: `day_first` reads 2/12/26 as 02 DEC 26, `month_first` as 12 FEB 26. The script cannot see text a person typed straight after an agent line with no prefix, so also read the whole Notes cell of each row in the window and treat any sentence that is not agent wording as the person's.

## What to do with an ask

1. Work out what the person wants the post to be. Change the row to match: Content type, What to post (calendar-schema.md mapping, or a plain new line such as "LinkedIn post: partner recruitment"), Pillar, Channel, Title / angle, Spec, and Date if they asked to move it (keep the holiday rules for `company.holiday_market`; if a date cannot move, say why). Only Planned and Proposed rows take these writes. Every one carries `"request": "<Row ID> Notes"`, `"request": "Ideas row N"` or `"request": "<Row ID> <column>"`. A moved Date carries its new ISO week: `calendar_writes.py plan` adds the Week write itself. The Row ID stays as it is.
2. Clear What's missing items the change makes moot, and add any the new post needs.
3. Add one Notes line: "`<notes.agent_prefix>` DD MMM YY: <what changed>, as asked in Notes." (or "as asked on the Ideas tab", or "as changed on the calendar" for a hand edit). This marks the ask as handled.
4. Draft the row in the same run, even if something is missing (base draft with [bracketed] gaps).
5. If part of the ask breaks a hard rule (a competitor name, an invented customer or quote, a launch date, a name not in the proof log), do the rest and say in the same line what was left out and why.
6. A new content type gets the nearest playbook pattern. List it in the brief under "New post types to approve" with a one-line proposed playbook entry.
7. When the meaning is unclear (two readings that cannot both be right), change nothing on that row, name both readings in Notes and list it under "Needs the approver".

## Hand edits

A person's direct edit to a tracked column stands: never change it back. A changed Date needs nothing more. A changed What to post, Title / angle, Content type or Spec on a Draft ready or Approved row means the draft no longer fits: redraft it into a " v2" tab (Original draft is replaced with `"v2": true`); an Approved row also gets a Notes line asking the approver to approve it again. An instruction typed into a cell instead of a value is copied word for word to the end of Notes as the person's text, the cell gets a clean value with `"request"`, and the instruction is handled as an ask.

## Series

A series is a set of rows whose Notes or Title / angle say "post N of M". When an idea asks for several posts ("one a week for 5 weeks"), convert or add every row now and give each "post N of M" in Notes. Series rows are drafted within `series.draft_within_days` days (default 14), or as soon as their details arrive. Rows without the details yet get a placeholder title ("Advisory board announcement 3 (advisor to confirm)") and a What's missing line naming exactly what to send.

`series_shift.py` keeps the order: when a person moves a post later, later posts that now fall on or before it move to the next free date on their own weekday; when a person cancels a post, the series is pushed back one slot (each later row takes the content of the one before, and the last post's content goes to a new Proposed row), unless the cancelled row's Notes contain `requests.series_drop_word` (default "drop"). The Cancelled row itself is never written. A post moved to the Backlog leaves a gap, noted once in the brief.

## Filing what the approver says

| What was said | Where it goes | How |
| --- | --- | --- |
| News about a named partner, customer or advisor ("Brightwell signed Northgate Facilities", "Dana Lee joined the advisory board") | Proof log, **only when `proof.approver_word_is_signoff` is true** | Proof intake's `proof_log_add.py` |
| The same news when `proof.approver_word_is_signoff` is false (the default) | The row's What's missing: "Log this in the proof log with sign-off: <news, short>" | Listed under "To finish drafts: what to send". Agents never write a new proof log row |
| Any other fact for posts (an event date, a program detail, a figure the approver is happy to use) | The approver's notes tab (`calendar.tabs.approver_notes`) | One row per fact: Date added (the date the person wrote it, else the run date first seen), From ("W11-02 Notes" or "Ideas row 3"), For (Row ID or topic), Fact (word for word), Link, Used in (agents fill), Add to facts sheet? |
| A request to change a row | The row itself | As above |

Mark "Add to facts sheet?" Yes for a fact that will keep coming up and list it under "Needs the approver": the facts sheet belongs to the approver, and agents never edit it. Every draft and check bundle gets the tab's rows as `person_items.json`. They count as approved for drafting, in the approver's words, but never authorize naming a person or company.

## Proof sign-off

| | `proof.approver_word_is_signoff: true` | `false` (default) |
| --- | --- | --- |
| Agents add proof log rows | Yes, with `proof_log_add.py`: Sign-off status Yes, dated when the news was added, public from that date unless a date was given, duplicates skipped, a person's row never edited | Never |
| An entry counts as signed off | Unless its Sign-off status is in `proof.not_signed_off_values` (default No, Pending); a blank status counts | Only when its Sign-off status is "Yes" |
| Reviewer note on the draft tab | For an implied sign-off: ask the approver to confirm the organization is happy to be named | None |

Say what was logged or flagged in the brief under "Changes made from your notes and ideas".

## Naming people

Outside people and companies are named only from the proof log. The company's own people (`company.people`) may always be named. When the approver names someone new in Notes or on the Ideas tab, the name may be used only once the proof log holds it (logged by agents when `proof.approver_word_is_signoff` is true, otherwise by a person). Record the source in Sources. Never add anything about a person that the source does not say.
