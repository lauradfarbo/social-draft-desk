# Proof rules

The client's rules file states what counts as proof; it wins over this file. Type names, placeholders, the swap window, the approver and the sign-off rule come from `workspace.json`.

## Sign-off

| `proof.approver_word_is_signoff` | Counts as signed off | Agents add proof log rows |
| --- | --- | --- |
| false (default) | Sign-off status `Yes`, with Sign-off from and Can go public from filled | Never. Proof news in Notes or Ideas becomes "To finish: Log this in the proof log with sign-off" in What's missing |
| true | Any entry whose Sign-off status is not in `proof.not_signed_off_values` (default `No`, `Pending`). Blank Sign-off from counts as Logged by; blank Can go public from counts as Date logged | Yes, with `proof_log_add.py`: Sign-off status Yes, Sign-off from "<who> (<where>)", Can go public from the date the news was added unless one was given, Logged by "Agents, from <who>'s <where>". Duplicates (same Type and Organization) are skipped |

With the true setting, an implied sign-off (blank status, blank Sign-off from or blank public date, or a row agents logged) adds a reviewer note asking the approver to confirm the organization is happy to be named before posting. The approver's word never covers a quote. In both settings, outside people and companies are named only from the proof log; the company's own team may always be named.

## Proof log columns

| Col | Column | Filled by | Notes |
| --- | --- | --- | --- |
| A | Date logged | Person (or agent, when allowed) | Date (agents: the date the approver's news was added) |
| B | Type | Person (or agent) | A key of `calendar.proof_types`: `Partner`, `Customer` or `Advisor` by default. For `Advisor`, Organization reads "<person>, <organization>" |
| C | Organization | Person | Exact public name |
| D | What happened | Person | Plain facts the organization agreed can be public |
| E | Approved quote (verbatim) | Person | `"Quote text" (Name, Role, Organization)` or blank |
| F | Sign-off from (name) | Person | Who signed off at the organization |
| G | Sign-off status | Person (or agent) | `Yes`, `No` or `Pending`; what a blank means depends on the sign-off rule |
| H | Can go public from | Person | Date |
| I | Logged by | Person (or agent) | A name in `company.people`, or "Agents, from <who>'s <where>" |
| J | Used in calendar row (agent fills) | Proof intake | Row ID and date drafted, or "Not used: sign-off No" |

## Matching (match_proof.py does this)

- Each proof log Type fills the content type it maps to in `calendar.proof_types` (Partner to Partner Win, Customer to Customer Proof, Advisor to Advisory board announcement).
- Slots: Status `Planned`, Proof item empty, dated in the next 14 days. Advisory board announcement rows are matched up to `proof.advisor_horizon_days` (default 91) ahead, in date order, so a series gets its people in order. They are drafted by the short-form drafter (`drafter` in the plan). An advisory row with no item is `no_item`: a base draft with the advisor's details as [bracketed] gaps, never a flag or a swap.
- Cancelled and Backlog rows are never slots.
- Earliest slot first, filled with the earliest-logged usable item whose go-public date is on or before the slot date.
- A note from the approver on a slot (a sentence in Notes starting "<approver first name>," or containing "(<approver first name>,", returned as `person_note`) is a condition, for example "the first partner at the partner's own event". Use an item there only if it meets the condition.
- A signed-off item that cannot be used yet waits for a later slot. Report it; write nothing in the proof log.

## Flags and swaps

Write one sentence per issue in Notes, prefixed "Proof intake DD MMM YY:". N is the proof log row. The swap window is `run.swap_days` (5 if not set).

| Situation | Notes | Swap |
| --- | --- | --- |
| No proof item for the type | "No signed-off <partner/customer> proof in the proof log for this slot." | Only if the slot is within the swap window |
| An item has Sign-off status No | "Proof log row N (<organization>) has sign-off No, so it is not used." | Yes, now |
| An item is waiting for sign-off (Pending, or blank under the default rule), cut-off ahead | "Proof log row N (<organization>) is waiting for sign-off; it can fill this slot if signed off by <signoff_cutoff>." | Only if within the swap window |
| An item is waiting for sign-off, cut-off passed (`cutoff_passed` true) | "Proof log row N (<organization>) is waiting for sign-off; the sign-off cut-off of <signoff_cutoff> has passed. If it is signed off by <late_cutoff>, the next run drafts it; otherwise use the backup row." This replaces the earlier waiting line: a passed date never stays in the current line | Backup row as usual within the swap window |
| Signed off, but public after the slot | "Proof log row N (<organization>) can go public from DD MMM YY, after this slot." | Only if within the swap window |

The sign-off cut-off is the slot date minus the swap window. Swap proposal, added as one more sentence: "Proposed swap: <a type from `swaps.types`> on <one-line angle> (<`swaps.source_label`> ch N). <Approver> to approve by changing the row." Pick the type the nearby rows use least (check the same and the next week), and an angle from a chapter in `swaps.chapters`, not in `swaps.excluded_chapters`, and not used in Sources on the last 8 weeks of rows. When the weekly orchestrator runs, take the type and chapter from its swap output so swaps in one run never repeat; the orchestrator drafts the swap onto a backup row, `<Row ID>-FB` with Status `Fallback post`, directly under the slot. The approver uses it by setting the backup row to Approved and the slot to Cancelled. Never change Status, Date, Content type or Title on the slot to make the swap. Never propose an anonymous customer or partner story.

## The post

- Advisory board announcement (drafted by the short-form drafter): the advisor's name, role on the board and organization exactly as in the proof log, and what they will help with, in its words.
- Partner Win: what the partnership is, in the proof log's words; why it matters to the partner's customers, using approved fact IDs; one call to action. Customer Proof: the use case or result exactly as stated; the problem it addresses for the audience in the voice guide; one call to action, usually a question.
- Name the organization once in full, exactly as in the proof log, early in the post. Suggest in the reviewer notes that the approver tags its company page.
- Approved quote: if used, on its own lines, in straight double quotation marks, word for word, followed by the attribution as written. At most one quote.
- Word count, opening, hashtags and links as in `writing.*` (the same rules as the short-form drafter). Add any hashtag a `writing.hashtags.conditional` rule asks for.
- No figures unless they are in What happened or on an approved fact.
- Visual: `Use: <file> (<visuals.asset_prefix>/<subfolder>)` only if a file for this organization exists, else `Needed: <organization> logo or photo, with their permission`.

## Title / angle (F)

Replace the placeholder only (`calendar.proof_placeholders` for the content type; `match_proof.py` returns `title_placeholder: true`): "<Short type>: <organization> <what, in 3 to 6 words>", for example "Partner news: Northgate Facilities joins as a reseller" or "Customer story: Harlow Council monthly energy reports". Never overwrite a title a person wrote.

## Proof item link (R)

For a Google Sheet: `https://docs.google.com/spreadsheets/d/<proof log>/edit#gid=<sources.proof_log.sheet_gid>&range=A<row>`. On another platform, the link to the record.

## Reviewer notes additions

Add under the standard reviewer notes: "Proof item: proof log row N, signed off by <name>, public from DD MMM YY.", "Sign-off: <name>'s word (proof log row N). Confirm <organization> is happy to be named before posting." when the plan has `implied_signoff` true, and "Do not post before DD MMM YY." when the public date is after the run date.
