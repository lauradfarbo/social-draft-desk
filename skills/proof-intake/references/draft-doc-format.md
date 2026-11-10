# Weekly draft doc

One doc per plan week in the drafts folder (`sources.drafts_folder`), one tab per post. The approver reviews a whole week in one doc, edits in the tab, then copies the post text into LinkedIn. The steps below are for Google Docs; on another platform follow the adapter rules in `docs/workspace-config.md` and keep the same names and text.

## Names

- Doc: `Drafts - Week NN (DD MMM YY)`, where NN is the ISO week of the post's date (two digits, the same number as the row's Week column and Row ID) and the date is the Monday of that week. Example: `Drafts - Week 11 (09 MAR 26)`. Find an existing week's doc by the `Drafts - Week NN` prefix and the Monday date: week numbers repeat every year, so the date tells two years' docs apart. Also accept a doc whose week number has no leading zero, rather than making a second doc for the same week.
- Tab: `DDD DD MMM YY - <short type> (<Row ID>)`. Examples: `TUE 10 MAR 26 - Poll (W11-01)`, `THU 12 MAR 26 - POV (W11-02)`. Days 1 to 9 always have a leading zero. Docs tab titles are limited to 50 characters; shorten the type if needed.
- First tab (the default "Tab 1"): rename to `Week overview`.
- Backup tab: `DDD DD MMM YY - BACKUP <short swap type> (<Row ID>-FB)`. Example: `THU 12 MAR 26 - BACKUP Poll (W11-02-FB)`. Its reviewer notes start with one extra line, above "First comment": `Backup for <Row ID> (<original content type>). It is its own calendar row, <Row ID>-FB, directly under <Row ID>. To use it, set <Row ID>-FB to Approved and <Row ID> to Cancelled.`
- v2 tab: the same title with " v2" at the end (" v3" and so on after that). Used for a refresh (a teaser whose link arrived), a redraft after the row was changed by hand, and any other redraft of a drafted row. The v2 tab's link replaces Draft URL and its post text replaces Original draft, so edit learning compares the approver's edits with the latest draft.
- Base drafts with gaps: the post keeps each gap as [square-bracket text]. Under "Flags for the approver", list "To finish:" items first, then "To strengthen:", then any "New type:" line. The approver replaces the brackets in the tab before setting Approved.

## Find or create the doc

1. Drive `search_files`: `parentId = '<drafts folder>' and title contains 'Drafts - Week NN'`.
2. If none: Drive `create_file` with title, parentId and contentMimeType `text/plain`, textContent = the overview text below (it becomes Tab 1). Then rename Tab 1: Docs `update_doc` with `updateDocumentTabProperties` {tabProperties: {tabId: "t.0", title: "Week overview"}, fields: "title"}.
3. If a tab for the same Row ID already exists, do not overwrite it: the approver may have edited it. Add a v2 tab (above) and say so in the Notes line.

## Add the post tab

1. Docs `update_doc`: `addDocumentTab` {tabProperties: {title: <tab name>}}. Keep the returned tabId.
2. Docs `update_doc`: `insertText` with `endOfSegmentLocation: {tabId}` and the tab text below.
3. Make the line "Notes for the reviewer (do not post)" bold. Nothing else: keep formatting plain so the post copies cleanly.
4. Tab link for the calendar: `https://docs.google.com/document/d/<docId>/edit?tab=<tabId>`.

## Tab text

```
<post text exactly as it should appear on LinkedIn, hashtags included>

----------
Notes for the reviewer (do not post)

First comment: <text with link, or "None">
Alternate hook: <one line>
Poll question and options: <poll only>
Visual: <Use: ..., Needed: <AI image tool> image of ... Prompt in draft tab., Needed: <real photo>, or None needed>
Image prompt (edit this, then paste into the AI image tool): <image_prompt. Attach the product reference photo first when the prompt names it>
Image prompt as drafted (do not edit): <the same text; the run compares the two lines to learn from the approver's prompt edits>
Alternative prompt: <only when the Visual is an AI image>
Other visual options: <visual_alternatives, or "None">
Word count: <n>
Facts used: <fact IDs, comma separated; "From the approver's notes row N" for person items>
Sources: <documents with version, chapter>
Flags for the approver: <anything omitted or uncertain, one sentence each, or "None">
Checker: <pass, or the warnings confirmed>
```

Proof intake adds lines after Sources: "Proof item: ...", "Sign-off: ..." when the sign-off was implied, and "Do not post before DD MMM YY." when needed (see proof intake's `proof-rules.md`).

Leave out the two image prompt lines when no image prompt was returned (no AI image tool set, or a real-photo-only type), and the Alternative prompt line when the visual is not an AI image. Column I on the calendar gets only the Visual line; the prompts stay in the tab.

The approver copies everything above the dashed line. Edits go in the tab, not in LinkedIn, so Final text stays accurate.

## Week overview text

```
Drafts for Week NN, <Monday DD MMM YY> to <Sunday DD MMM YY>.
One tab per post. Edit in the tab, then set Status to Approved on the calendar.
Copy only the text above the dashed line into LinkedIn.
```
