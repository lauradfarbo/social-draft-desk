# Content calendar schema

The calendar is used by people who are not marketers. People change Status and Notes, and may edit a row's Date, What to post, Pillar, Channel, Title / angle, Content type or Spec directly (the run treats such an edit as an ask). Everything else is filled by agents or formulas.

Where a value below comes from `workspace.json`, the key is named in backticks. A missing optional key falls back to the default shown.

## Tabs (in order)

Tab names come from `calendar.tabs` (keys in brackets); the defaults are shown.

1. **This Week** (`this_week`): formula view of the next 14 days plus anything overdue. Draft links open the post's tab in the weekly draft doc. Row 1 links to the Calendar filter view where Status is changed. Never write to it.
2. **Calendar** (`calendar`): one row per line item.
3. **Backlog** (`backlog`): posts kept for later. See "Backlog tab".
4. **Ideas** (`ideas`): post ideas from the approver and the team.
5. **Milestones** (`milestones`): trade shows, launches, webinars, funding dates.
6. **From the approver's notes** (`approver_notes`): facts the approver gave in Notes or on the Ideas tab, filled by agents. See "Agent tabs".
7. **Agent log** (`agent_log`): older agent Notes lines and one RUN row per run. See "Agent tabs".
8. **Approver edits** (`approver_edits`): every edited version of a draft, for edit learning. See "Agent tabs".
9. **Agent snapshot** (`agent_snapshot`, hidden): what the last run saw, so hand edits are found. See "Agent tabs".
10. **How to use** (`how_to_use`): plain-language instructions for people.

## Calendar columns (fixed order, A to V)

Visible (A to L, dark header):

| Col | Column | Filled by | Rule |
| --- | --- | --- | --- |
| A | Date | Builder | Real date, written as `YYYY-MM-DD`, displayed `ddd d mmm yy` |
| B | Status | Agents and people | Dropdown, values below |
| C | What to post | Builder | Plain-language format from the mapping below |
| D | Pillar | Builder | From the pillar mapping; the approver may override |
| E | Channel | Builder | Verbatim from the plan |
| F | Title / angle | Builder | Clean title: no quote marks. Proof slots show the placeholder from `calendar.proof_placeholders` until proof intake links approved proof |
| G | Action needed | Formula | Single ARRAYFORMULA in G2. Team-owned rows (content type matches `calendar.team_owned_regex`) show "Team writes this: set Posted when live". Never write to G |
| H | Draft | Formula | Single ARRAYFORMULA in H2: a link to U (Draft URL), showing the first line of V (Original draft, up to 80 characters) or "Open draft". Never write to H |
| I | Visual | Drafting agent | "Use: <file name> (<`visuals.asset_prefix`>/<subfolder>)", "Needed: <`visuals.ai_image_tool`> image of <subject>. Prompt in draft tab." (only when an AI image tool is set), "Needed: <photo, video or graphic>" or "None needed (LinkedIn renders the poll)". No file or AI image subject is reused within `visuals.no_repeat_weeks` weeks either side (default 8) |
| J | Notes | People, agents | A person's text, word for word, plus one current "<`notes.agent_prefix`> DD MMM YY:" line (default "Agents"; `notes.agent_lines_kept`, default 1). Older agent lines move word for word to the Agent log tab (`notes_tidy.py`). A tidy never drops a person's words. A person's plain-words ask here is a request |
| K | What's missing | Planner, proof intake, drafters | Exactly what a person must provide to finish the post (proof log sign-off, blog link, photos, a decision). Cleared by the agent once provided. Drives "Waiting on" in Action needed |
| L | Sources | Builder, drafters | Every document the row draws on, with version, plus facts sheet IDs once drafted (for example "Energy Reporting Without the Spreadsheet ch3; Plan Rules 1.0; Facts C02, M05"). Lets the team see when a source is out of date |

Agent columns (M to V, gray header, collapsed column group, warning-only protection):

| Col | Column | Filled by | Rule |
| --- | --- | --- | --- |
| M | Row ID | Builder | `W{iso week:02d}-{seq:02d}` from the row's Date, for example `W11-02`. seq counts up within the week in Date and AM/PM order. Backup rows: `<Row ID>-FB`. An ID is never reused: when the same week number from an earlier year is still on the Calendar or Backlog tab, seq continues after the highest one already used. Set once: a row that later moves week keeps its ID |
| N | Week | Builder, orchestrator | The calendar (ISO) week of the Date, as a number (`calendar.week_numbering`: `iso`). Kept in step with the Date by `calendar_writes.py weeksync` when a person moves a Date, and written with the Date when a request moves a row |
| O | AM/PM | Builder | `AM`, `PM` or blank |
| P | Content type | Builder | Verbatim from the plan; the key drafting agents use |
| Q | Spec | Builder | Verbatim "What to create" text from the plan. Word counts here are replaced by the voice guide's |
| R | Proof item | Proof intake | Link to the proof log row (proof slots only) |
| S | Published link | Agent, optional | Live post URL if the agent can find it |
| T | Final text | Agent | Copied from the draft tab (text above the dashed line) when Status becomes Posted |
| U | Draft URL | Drafting agent | Link to the post's tab in the weekly draft doc, for example `https://docs.google.com/document/d/<docId>/edit?tab=<tabId>` |
| V | Original draft | Drafting agent | The post text as first drafted. Written once, never overwritten. The learning agent compares it with Final text |

## Status values

The list comes from `calendar.statuses`. Defaults:

| Value | Set by | Meaning |
| --- | --- | --- |
| Proposed | Calendar builder | New row awaiting approval. Drafters ignore it |
| Planned | Approver | Approved slot, ready to draft |
| Draft ready | Drafting agent | Draft linked, awaiting review (What's missing lists any [bracketed] gaps to fill) |
| Fallback post | Orchestrator | Backup row directly under its original, Row ID `<original>-FB`. To use it: Approved here, Cancelled on the original |
| Approved | Approver | Ready to post on the date |
| Posted | Approver | Live |
| Cancelled | Approver | Dropped. The row stays as history and is hidden on the Calendar at the end of every run (`backlog.py hide`). Agents never draft, flag, write to or mention it. Use this instead of deleting a row |
| Backlog | Approver | Keep for later, on any row not yet Posted. The next run moves the whole row to the Backlog tab (`backlog.py`). On the Backlog tab, setting Planned brings it back to the Calendar (on the date in its Notes, or the best free slot) |

Agents set only the statuses in `calendar.agent_statuses` (default Proposed, Draft ready, Fallback post). People set Planned, Approved, Posted, Cancelled and Backlog. A swap is proposed in Notes, never by changing Status. If the client uses other Status words, replace them in the formulas below as well.

## Pillar mapping (by content type)

Defaults, checked in this order. A client can replace them with `calendar.pillar_map`, a list of `[regex, pillar]` pairs checked in order (case-insensitive). Proof types come from `calendar.proof_types` (default Partner: Partner Win, Customer: Customer Proof, Advisor: Advisory board announcement). A content type with no mapping is drafted from the nearest pattern and listed in the brief for approval.

| Content type contains | Pillar |
| --- | --- |
| Advisory board announcement | PR & Press |
| Partner recruitment | Partner & Customer Proof |
| Partner Win, Customer Proof (the Partner and Customer values of `calendar.proof_types`) | Partner & Customer Proof |
| Press Release, Trade show | PR & Press |
| Blog, video, Gratitude, Year-in-review | Product & Brand Education |
| The long-form label (`swaps.source_label`), Newsletter, Event, Live event | Lead Generation |
| Poll | Engagement |
| POV | Thought Leadership |

## "What to post" mapping

Defaults. A client can replace them with `calendar.what_to_post_map`, a list of `[regex, text]` pairs checked in order.

| Content type | What to post |
| --- | --- |
| Press Release - Distribute | Press release: wires, trade press and website (post first) |
| Press Release - LinkedIn announcement | LinkedIn post: press release announcement (later the same day) |
| Advisory board announcement | LinkedIn post: advisory board announcement |
| Partner recruitment | LinkedIn post: partner recruitment |
| Partner Win | LinkedIn post: partner news |
| Customer Proof | LinkedIn post: customer story |
| Any video | LinkedIn video |
| Blog N - Publish | Blog article on website (post first) |
| Blog N - LinkedIn teaser | LinkedIn post: blog teaser (2 to 4 hours after the blog) |
| Trade show teaser, live, recap | LinkedIn post: <show> trade show |
| Long-form launch or push (contains `swaps.source_label`) | LinkedIn post: <label> promotion |
| Newsletter (any) | LinkedIn newsletter |
| Event announcement | LinkedIn post and LinkedIn Event listing |
| Event reminder | LinkedIn post: webinar reminder |
| Live event | Live webinar and LinkedIn post |
| Poll | LinkedIn poll |
| Industry POV | LinkedIn post: opinion |
| Gratitude post | LinkedIn post: thank you |
| Year-in-review | LinkedIn post: year in review |

## Formulas (write once, on build only)

Replace `<team_owned_regex>` with `calendar.team_owned_regex` (default `Publish|Newsletter|Distribute`).

Calendar!G2:
```
=ARRAYFORMULA(IF(A2:A="","",IF(B2:B="Posted","Done",IF(B2:B="Cancelled","Cancelled: no action",IF(B2:B="Backlog","Moves to the Backlog tab on the next run",IF(B2:B="Fallback post","Backup post: to use it, set this row to Approved and the row above to Cancelled",IF(A2:A<TODAY(),"Overdue: post it or update the status",IF(B2:B="Proposed","New slot: review, then set Planned",IF(REGEXMATCH(P2:P&"","<team_owned_regex>"),IF(A2:A=TODAY(),"Team: publish today, then set Posted","Team writes this: set Posted when live"),IF(B2:B="Approved",IF(A2:A=TODAY(),"Post today","Ready: post on the date"),IF(B2:B="Draft ready",IF(K2:K<>"","Review the draft; to finish it, see What's missing","Review the draft, then set Approved"),IF(K2:K<>"","Waiting on: see What's missing",IF(A2:A-TODAY()<=7,"Draft due","")))))))))))))
```

Calendar!H2:
```
=ARRAYFORMULA(IF(U2:U="","",HYPERLINK(U2:U,IF(V2:V="","Open draft",IF(LEN(REGEXEXTRACT(V2:V&"","^[^\n]*"))>80,LEFT(REGEXEXTRACT(V2:V&"","^[^\n]*"),77)&"...",REGEXEXTRACT(V2:V&"","^[^\n]*"))))))
```

A HYPERLINK built inside LET, HSTACK or MAP shows the text but is not clickable, so the Draft links use the plain ARRAYFORMULA pattern above.

### This Week tab

Layout: A1:J1 merged, light fill, bold, holding the filter view link (below). Headers in row 2, A2:L2: Date, Status, What to post, Channel, Title / angle, Action needed, What's missing, Draft, Visual, Notes, Draft URL, Original draft. Columns K and L are hidden helpers. Freeze rows 1 and 2. A3 and I3 use the same filter and sort, so their rows line up. The tab stays read-only because any typed value breaks its formulas.

This Week!A1 (replace `<sheetId>`, `<calendarGid>` and `<filterViewId>`):
```
=HYPERLINK("https://docs.google.com/spreadsheets/d/<sheetId>/edit#gid=<calendarGid>&fvid=<filterViewId>","To change a Status, click here. It opens the Calendar showing only these posts. Click a Draft link to open the post.")
```

This Week!A3 (columns A to G):
```
=IFERROR(CHOOSECOLS(SORT(FILTER({Calendar!A2:A,Calendar!B2:B,Calendar!C2:C,Calendar!E2:E,Calendar!F2:F,Calendar!G2:G,Calendar!K2:K},Calendar!A2:A<>"",Calendar!A2:A<=TODAY()+13,Calendar!B2:B<>"Cancelled",(Calendar!A2:A>=TODAY())+(Calendar!B2:B<>"Posted")),1,TRUE),1,2,3,4,5,6,7),"Nothing due in the next 14 days")
```

This Week!I3 (columns I to L: Visual, Notes, Draft URL, Original draft):
```
=IFERROR(CHOOSECOLS(SORT(FILTER({Calendar!I2:I,Calendar!J2:J,Calendar!U2:U,Calendar!V2:V,Calendar!A2:A},Calendar!A2:A<>"",Calendar!A2:A<=TODAY()+13,Calendar!B2:B<>"Cancelled",(Calendar!A2:A>=TODAY())+(Calendar!B2:B<>"Posted")),5,TRUE),1,2,3,4),"")
```

This Week!H3 (the clickable Draft link, same pattern as Calendar!H2):
```
=ARRAYFORMULA(IF(K3:K="","",HYPERLINK(K3:K,IF(L3:L="","Open draft",IF(LEN(REGEXEXTRACT(L3:L&"","^[^\n]*"))>80,LEFT(REGEXEXTRACT(L3:L&"","^[^\n]*"),77)&"...",REGEXEXTRACT(L3:L&"","^[^\n]*"))))))
```

### Filter view

Calendar filter view "This Week: update Status here" (`addFilterView`): range Calendar A:V, sort by column A ascending, filter on column A with CUSTOM_FORMULA:

```
=AND($A2<>"",$A2<=TODAY()+13,$B2<>"Cancelled",OR($A2>=TODAY(),$B2<>"Posted"))
```

It shows the same rows as This Week and only changes what the person who opens it sees.

When adding rows, write `null` to G and H: the formulas fill them. See "Writing new rows" in SKILL.md.

## Formatting

Neutral defaults. Replace them with the client's palette in their sheet, not in this repo.

| Element | Format |
| --- | --- |
| Visible header (A to L) | `#1F2933`, white bold text |
| Agent header (M to V) | `#6B7280`, white bold text |
| Fallback post | `#FBF3E0`, italic gray text on A:L (first conditional format rule), never marked overdue |
| Proposed | `#FFF4CC` |
| Planned | White |
| Draft ready | `#E3EEF7` |
| Approved | `#1E6B52`, white bold text |
| Posted | `#E5E7EB` |
| Cancelled | `#E5E7EB`, gray strikethrough text |
| Overdue (date past, not Posted, Cancelled, Fallback post or Backlog) | `#F8D7D3`, bold |
| Today's rows | Bold |
| Even calendar weeks | Banded `#F5F7F9`: `=AND(ISNUMBER($A2),ISEVEN(WEEKNUM($A2,21)))` (21 is ISO numbering) |
| Agent tabs (header) | `#6B7280`, white bold text, wrap on |

- Freeze row 1 and columns A to B. Filter on A1:V.
- Action needed in bold. Wrap What to post, Title, Action needed, Visual, Notes, What's missing, Sources. What's missing in dark red text.
- Columns M to V in one collapsed column group with warning-only protection. G and H and the whole This Week tab are also warning-only protected.
- Dropdowns: Status (B) from `calendar.statuses`, AM/PM (O).
- Spreadsheet locale set so typed dates read per `dates.typed_order` (day first: for example English (United Kingdom); month first: English (United States)). Column A keeps its `ddd d mmm yy` format.

## Backlog tab (A to X)

Columns A to V exactly as the Calendar (same headers, same order), then W Moved to Backlog and X Was dated (both dates, displayed DD MMM YY). Header row as on the Calendar, freeze row 1, wrap on, Status dropdown in B with the Calendar's values. No formulas. People change only Status (Planned to bring a post back) and Notes (an optional date, read per `dates.typed_order`). Agents write rows only through the orchestrator's `backlog.py`: a row is moved, never deleted, and the copy is written and read back before the source row is removed. Row IDs on this tab still count as used.

## Agent tabs

Filled by agents only, gray header, wrap on, warning-only protection. People read them.

| Tab | Columns | Rule |
| --- | --- | --- |
| From the approver's notes | Date added, From, For, Fact, Link, Used in, Add to facts sheet? | One row per fact the approver gave in Notes or on the Ideas tab that is not proof news. From says where it was written, For a Row ID or topic, Fact is the approver's words, word for word. Each row counts as approved for drafting and never authorizes naming a person or company. Writes go through `tab_guard.py --key "Date added"` |
| Agent log | Date moved, Row ID, Agent, Text, Reason moved | Older agent Notes lines, word for word, moved by `notes_tidy.py`, plus one RUN row per run with the full run details |
| Approver edits | Date captured, Row ID, Content type, Status, Size of edit, Original draft, Approver's text, What changed, Draft URL | Every new version of a drafted post (Light edit or Rewrite), from `edit_capture.py`. Drafters learn the approver's style from it |
| Agent snapshot (hidden) | Kind, Key, Date, Status, What to post, Pillar, Channel, Title / angle, Content type, Spec, Confirmed, Saved | Kind is row or milestone, Key the Row ID or milestone name. Written only by `snapshot.py save`, the last write of every run, and compared at the start of the next (`snapshot.py compare`) to find hand edits and milestone changes. People never edit it |

## Ideas tab columns (A to H)

Idea (one line), Added by, Date added, Wanted by, Link or source, Status, Calendar row, Agent note.

People fill Idea, Added by, Date added, Wanted by (optional) and Link or source (optional). The agent fills Status (`Scheduled` or `Parked`; people may set `Declined`; blank or `New` means new), Calendar row and Agent note. Columns G and H have warning-only protection. An idea may ask to change, convert or move existing rows; the builder does it. Only an idea that wholly breaks a hard rule is Parked.

## Milestones tab columns (A to G)

Milestone, Type (Trade show, Launch, Webinar, Funding, Partner, Product), Start date, End date, Confirmed (Yes, No, Cancelled), Notes, Rows proposed (Yes or blank).

A person sets Confirmed to Cancelled instead of deleting a milestone. The builder proposes no rows for it, and the planner handles its remaining rows. A change to Start date or Confirmed starts the builder's milestone change run (SKILL.md, Mode 3b). Notes on a milestone go to the drafter of every linked row.

## How to use tab

Plain lines for people, in this order (`scripts/build_calendar.py` writes the same text). Lines 6 and 7 are left out when `requests.enabled` is false. Line 8 follows `dates.typed_order` (month first: "Type dates month first: 12/2/26 is 02 DEC 26."). Line 12 uses `requests.series_drop_word`.

1. This Week shows what is due in the next 14 days and anything overdue. Start there.
2. Rows marked Proposed are new slots from the agents. Read the title and Notes, then set Planned to approve or Cancelled to drop.
3. Agents draft Planned rows and set Draft ready. Click the Draft link to read the post. If What's missing is filled, the draft has [bracketed] gaps: send what it lists and the agents finish the draft.
4. To change a Status, use the link at the top of This Week. It opens the Calendar showing only this week's posts.
5. Set Approved when a draft is ready to post, and Posted once it is live.
6. To ask for a change, write it in plain words in the row's Notes or on the Ideas tab, for example "move this to Thursday" or "make this a poll". The agents make the change at the next run and say what they changed in Notes.
7. You can also change a post by editing its cells directly (Date, What to post, Title and so on). The agents pick up either at the next run.
8. Type dates day first: 2/12/26 is 02 DEC 26.
9. A row marked Fallback post is a backup for the post above it. To use it, set it to Approved and the post above to Cancelled.
10. To drop a post, set its Status to Cancelled. Do not delete the row. Cancelled rows are hidden on the next run.
11. To keep a post for later, set its Status to Backlog. The next run moves it to the Backlog tab. To use it again, set its Status on the Backlog tab to Planned, and add a date in Notes if you want one.
12. Posts in a series ("2 of 5") stay in order. If you move one later, the later posts move with it. If you cancel one, the series moves back one slot; write "drop" in its Notes first if you want it gone instead. Cancel a blog and its teaser together.
13. You can sort or reorder the Calendar at any time, for example by Date after moving posts. Ignore the protection warning and go ahead: every row carries its own Row ID, and the agents find rows by Row ID, not by position.
14. Add post ideas on the Ideas tab. Set Declined on an idea instead of deleting it.
15. Add trade shows, launches and other dates on the Milestones tab. To cancel a milestone, set Confirmed to Cancelled. Do not delete the row.
16. Leave Action needed, Draft and the gray agent columns to the agents and formulas. The agents keep their own tabs (From the approver's notes, Agent log, Approver edits) up to date.
