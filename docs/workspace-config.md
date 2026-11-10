# Workspace config (`workspace.json`)

Every skill, agent and script in this plugin reads one file, `workspace.json`, to learn where the client's material lives and which rules apply. Nothing client-specific is written into the plugin itself. The `workspace-setup` skill (`/setup-workspace`) builds this file by interview; you can also copy `templates/workspace.example.json` and fill it in by hand.

The file lives in the client's own workspace (a Drive folder, a Notion page, a private repo or a connected local folder), never in this repo. Each run is told where it is: `/weekly-run test --config <location>`, or the location saved in the scheduled task prompt that setup writes.

## Sections

### `company`

| Key | Meaning |
| --- | --- |
| `name` | Company name as it appears in posts |
| `hashtag` | The brand hashtag, if any |
| `approver.name`, `approver.role` | The one person who approves rows and drafts. Agents write "<approver> to approve" in Notes and the brief |
| `people` | Team names that may appear in posts. Names outside this list and the proof item raise a warning |
| `people_first_mention` | Optional. First-mention forms, for example `{"Priya": "Priya Nair, co-founder"}` |
| `timezone`, `holiday_market` | Run timezone, and the market whose public holidays shift posting dates (US, UK, NL and so on) |

### `run`

How far ahead to draft (`horizon_days`, 13 = the next two weeks), how many weeks the planner checks, how close a blocked row must be before a backup post is added (`swap_days`), the fallback cap, and the default mode. The default is always `test` until the agent register records a passing test.

The schedule has two parts. Setup writes one scheduled task prompt for each (`skills/weekly-orchestrator/references/scheduled-prompts.md`).

| Key | Default | Meaning |
| --- | --- | --- |
| `run.full_run.weekday`, `run.full_run.time` | `Monday`, `12:30` | The weekly full run: plan check, drafts for the next two weeks, backup posts, the weekly brief. The first full run of the month is also the monthly run. Time is 24-hour in `company.timezone` |
| `run.requests_runs.weekdays`, `run.requests_runs.time` | Tuesday to Friday, `06:00` | Light weekday runs (`/weekly-run <test|live> requests`) that act only on asks, hand edits, new ideas, Backlog moves and series shifts, and write a short update only if they changed something. An empty list means no requests runs |
| `run.weekday` | `Monday` | Single-day form. When both are set, `run.full_run.weekday` wins |

A second run on the same day as a full run handles only what changed since (requests mode), unless the person asks for `rerun`.

### `dates`

| Key | Default | Meaning |
| --- | --- | --- |
| `dates.typed_order` | `day_first` | How agents read a date a person types in Notes, on the Ideas tab or in a cell: `day_first` (2/12/26 is 02 DEC 26) or `month_first` (2/12/26 is 12 FEB 26). Set it to match the sheet's locale. Agents always write dates as DD MMM YY |

### `sources`

One entry per file the agents use. Every entry has:

| Key | Meaning |
| --- | --- |
| `kind` | `doc` (read as text), `table` (rows with a header), `file` (PDF or long-form), `folder` (listing), `repo` |
| `platform` | `google_drive`, `notion`, `github`, `sharepoint`, `local` (a connected folder) or `url` |
| `live`, `test` | The ID, URL, repo path or local path. `test` is the TEST copy; `null` means the same file is used in test runs (read-only sources only) |
| `title` | Human name with version, quoted in Sources and the brief |
| `expect_phrase` | Words near the end of a doc. A read that does not contain them is treated as cut off and the run stops |
| `tab`, `range` | Tables only |
| `sheet_gid` | Google Sheets tables only, optional: the tab's gid, used to build row links (for example the Proof item link) |

Required: `rules`, `voice_guide`, `facts_sheet`, `calendar`, `drafts_folder`, `briefs_folder`. Recommended: `plan_rules`, `proof_log`, `long_form`, `assets`, `agent_register`. Optional: `shadow`, `other` (any further reference: a website repo, a Notion wiki, a product sheet).

#### Where each source can live

| Source | Read from | Write to |
| --- | --- | --- |
| Rules, plan rules, voice guide | Google Docs, Notion page, GitHub file, SharePoint or OneDrive file, local Markdown, public URL | Never written |
| Facts sheet | Google Sheet, Notion database, Excel file, CSV in a repo | Never written |
| Long-form source and chapter map | PDF or doc anywhere a connector can read | Never written |
| Assets | Google Drive folder, SharePoint folder, local folder, repo folder | Never written |
| Calendar, proof log | Google Sheet (tested). Notion database or Excel Online (adapter, see below) | Agents write only the cells in `calendar-schema.md` |
| Drafts, briefs | Google Docs (tested). Notion pages or Word Online (adapter) | One doc per week, one brief per run |

The calendar, proof log, drafts and briefs path is built and tested on Google Workspace. The other platforms are supported through the adapter rules below and must pass the TEST run before going live.

#### Adapter rules (any platform)

Scripts never talk to a platform. They read local JSON in one shape, so any source can feed them:

- **Tables** are saved as `{"values": [["Header A", "Header B"], ["row 2 a", "row 2 b"]]}`, header row first, row 2 is the first data row. This is the Google Sheets `get_values` shape. For a Notion database, Excel file or CSV, convert to this shape with the columns in the schema order, and keep a `_source_row` key map (Row ID to page ID or row number) in the run folder so writes go back to the right record.
- **Docs** are saved as plain text or Markdown. For Google Docs use Docs `read_doc` and `doc_text.py` (Drive text export can cut long docs off). For Notion, GitHub, SharePoint and local files, save the text as returned. Always check `expect_phrase`.
- **Folders** are saved as `assets.txt`, one `<subfolder>/<file name>` per line.
- **Writes** always pass the same three checks whatever the platform: `calendar_writes.py plan` (column lock), `calendar_writes.py guard` on a fresh read just before writing (Row ID and Status unchanged), then `calendar_writes.py verify` on a read-back.

### `writing`

Machine-readable rules for `check_draft.py` and `check_compliance.py`. The client's rules doc still wins; this section is the part a script can test.

| Key | Meaning |
| --- | --- |
| `spelling` | `US` or `UK`. The scripts fail the other variety |
| `units` | `metric` or `imperial`. The scripts fail the other system |
| `date_format`, `no_em_dash`, `emoji` | Output conventions |
| `word_count` | `[min, max]` per draft type (`post`, `founder`, `poll`) |
| `opening_max_words` | The first sentence must be shorter than this |
| `hashtags` | `min`, `max`, `required` tags, and `conditional` tags (`if_regex` in the post means `tag` should be added: a warning) |
| `link_in_first_comment` | Links go in the first comment, never the post body |
| `competitors` | Company and brand names that must never appear. Lower case |
| `avoid_terms` | Voice guide avoid list. Lower case |
| `date_words_warn` | Words that suggest a launch, availability or delivery date. Warning only |
| `custom_rules` | Client claim rules: `id`, `level` (`fail` or `warn`), `regex` (case-insensitive), optional `unless_regex`, and the `message` the drafter sees, which should name the approved wording |
| `on_hold_topics` | Topics not to mention while a fact (`fact_id`) is not Approved: `regex`, `fact_id`, optional `milestone_type` (a Milestones row of that Type with Confirmed Yes lifts the hold; when it is missing, the `milestone_type` of the `plan.dependencies` entry with the same `fact_id` is used) |

### `facts`

Column names on the facts sheet and the Status values that count as approved. Agents state only claims from approved rows.

### `calendar`

Content type patterns: team-owned rows (never drafted), proof types and their title placeholders, teaser rows (need the published blog link), event live and recap rows (need real photos), and the Status lists.

| Key | Default | Meaning |
| --- | --- | --- |
| `calendar.week_numbering` | `iso` | The Week column holds the ISO week of the Date, and Row IDs start with it: `W{iso week:02d}-{seq:02d}` (W11-02). A Row ID is never reused across years: seq continues after the highest one used. `iso` is the only value supported |
| `calendar.alternation_anchor_week` | `{"year": 2026, "week": 1}` | The week counted as odd for every odd and even week rule (proof slot, blog pair). Weeks are counted from it, so week 53 and week 1 still alternate. Pick a week at or before the first calendar row and do not change it once rows exist |
| `calendar.statuses` | Proposed, Planned, Draft ready, Fallback post, Approved, Posted, Cancelled, Backlog | The Status dropdown. Cancelled is required |
| `calendar.agent_statuses` | Proposed, Draft ready, Fallback post | The only statuses agents may set. People set Planned, Approved, Posted, Cancelled and Backlog. `check_workspace.py` refuses any other value here |
| `calendar.request_columns` | Date, What to post, Pillar, Channel, Title / angle, Content type, Spec | The cells agents may change on a Planned or Proposed row when a person asks. A subset of the default list |
| `calendar.tabs` | See below | Tab names, if the client renamed them. Each value is a tab name (`"ideas": "Post ideas"`) or, for the guarded tabs (`ideas`, `milestones`, `approver_notes`), an object `{"tab": "Post ideas", "key": "<key column>", "status": "<status column>"}` |
| `calendar.proof_types` | Partner: Partner Win, Customer: Customer Proof, Advisor: Advisory board announcement | Proof log Type to the content type that proof fills. Advisor items fill Advisory board announcement rows in date order |

Default `calendar.tabs`: `calendar` Calendar, `backlog` Backlog, `ideas` Ideas, `milestones` Milestones, `approver_notes` From the approver's notes, `agent_log` Agent log, `approver_edits` Approver edits, `agent_snapshot` Agent snapshot (hidden), `this_week` This Week, `how_to_use` How to use.

### `requests`

The approver's direction comes first. A person writes what they want in plain words in a row's Notes, on the Ideas tab, or by editing a row's cells directly, and the next run makes the change.

| Key | Default | Meaning |
| --- | --- | --- |
| `requests.enabled` | `true` | `false` turns off acting on asks and hand edits. Notes are still read for facts |
| `requests.from` | `["approver"]` | Whose words count as asks: `approver`, `team` (anyone in `company.people`), or named people. Text from anyone else is listed in the brief, not acted on |
| `requests.series_drop_word` | `drop` | A word in a series post's Notes that removes it when it is cancelled, instead of moving the rest of the series back one slot |
| `requests.hold_lift_word` | `CONFIRMED` | A word that, with a date, lifts a hold. Plain words also count: no set phrase is ever required |

### `notes`

| Key | Default | Meaning |
| --- | --- | --- |
| `notes.agent_prefix` | `Agents` | Agent lines in Notes start "<prefix> DD MMM YY:" |
| `notes.agent_lines_kept` | `1` | Current agent lines kept in Notes. Older agent lines move word for word to the Agent log tab. A person's text is never moved or changed |

### `proof`

| Key | Default | Meaning |
| --- | --- | --- |
| `proof.approver_word_is_signoff` | `false` | Whether news the approver gives counts as proof sign-off. See below |
| `proof.not_signed_off_values` | `["No", "Pending"]` | Sign-off status values that never count. Used only when the option above is on |
| `proof.advisor_horizon_days` | `91` | How far ahead Advisor proof items are matched to Advisory board announcement rows |

**Off (default).** Agents never write new proof log rows. When the approver mentions news about a named partner, customer or advisor, the row gets "Log this in the proof log with sign-off" in What's missing, and only entries with Sign-off status `Yes` count. Slower, but a second step always confirms that an outside organization agreed to be named.

**On.** News about a named partner, customer or advisor that the approver gives in Notes or on the Ideas tab is logged in the proof log by the agents (`proof_log_add.py`: Sign-off Yes, dated when added, public from that date unless the approver gave one, duplicates skipped, a person's row never edited). Every entry counts as signed off unless its Sign-off status is in `proof.not_signed_off_values`. Implied sign-offs carry a reviewer note asking the approver to confirm the organization is happy to be named. Faster, but the approver's word is then the only check that the organization agreed. Turn it on only when the approver may sign off for the company and accepts that.

In both cases outside people and companies are named only from the proof log, and the company's own team (`company.people`) may always be named.

### `edit_learning`

| Key | Default | Meaning |
| --- | --- | --- |
| `edit_learning.enabled` | `true` | Log every new version of a draft the approver edited on the Approver edits tab, and give drafters examples |
| `edit_learning.examples_per_draft` | `3` | The approver's latest edited posts each drafter sees, same content type first. Style only: claims still need a source |
| `edit_learning.monthly_proposals_max` | `5` | Voice guide changes proposed in the monthly brief for the approver to approve. Agents never edit the voice guide |
| `edit_learning.min_supporting_edits` | `2` | Edits each proposal must rest on |

### `series`

| Key | Default | Meaning |
| --- | --- | --- |
| `series.draft_within_days` | `14` | Series posts ("post N of M" in Notes) are drafted only within this many days, or as soon as their details arrive |

### `plan`

Cadence rules `plan_check.py` can test: intentional deviations by Row ID, posts per week, the weekly proof slot, the blog pair, the rotation slot, types not to repeat in one week, and dated dependencies (a fact that must be Approved by a deadline). Odd and even weeks count from `calendar.alternation_anchor_week`. Leave a key out to skip that check. Anything a script cannot test stays in the plan rules doc for the planner agent to judge.

| Key | Default | Meaning |
| --- | --- | --- |
| `plan.precedence` | `dated_events_first` | When an evergreen row sits on a dated event's slot, the planner proposes moving the evergreen row. `off` turns the check off |
| `plan.dated_event_regex` | `\bevent\b\|\bwebinar\b` | Content types that count as dated events for `plan.precedence` |
| `plan.proof_slots` | None | `[{"weekday": "Tue", "type": "<proof type>"}, ...]`: one proof slot a week per entry. Used instead of `plan.proof_slot` when set |
| `plan.dependencies[].milestone_type` | None | The Milestones Type that lifts this hold. A Milestones row of that type with Confirmed Yes lifts it, as does the dependency fact turning Approved or a dated "CONFIRMED" in the row's Notes |
| `plan.week1_monday` | None | Optional. The Monday of plan week 1, used only when `calendar.alternation_anchor_week` is not set and by `verify_calendar.py` to map a plan's own week numbers. Week and Row IDs always use ISO weeks |

### `swaps`

The evergreen post types used when a slot cannot run, the long-form source chapters a swap may draw on, and chapters never used for a swap (for example one that gives launch dates).

### `visuals`

How many weeks either side a file or AI image subject may not repeat, the assets folder label, the AI image tool (or `null` for none), an optional product reference photo note, the content types that need a real photo, aspect ratios, and brand colors for abstract images.

### Optional keys

Leave any of these out to use the default.

| Key | Default | Meaning |
| --- | --- | --- |
| `calendar.pillar_map` | Table in `calendar-schema.md` | `[[regex, pillar], ...]`, checked in order |
| `calendar.what_to_post_map` | Table in `calendar-schema.md` | `[[regex, text], ...]`, checked in order |
| `calendar.content_type_aliases` | None | `{"<client type name>": "<generic type in post-types.md>"}` |
| `calendar.blog_id_regex` | `^(Blog \d+)` | Pulls the blog ID out of a content type, to pair a teaser with its blog |
| `calendar.formula_columns` | Action needed, Draft | Columns agents never write |
| `writing.spelling_allow` | None | Words exempt from the spelling check (brand names, quoted titles) |
| `writing.product_timing` | `{"level": "fail"}` | Launch, availability and delivery timing: `level` fail, warn or off, optional `regex` and `message` |
| `plan.dependencies[].row_regex` | Label or fact ID | Which rows a dependency holds, matched on Content type, Title / angle or Notes |
| `plan.pdf` | Default layout | How `verify_calendar.py` reads the plan PDF: `row_regex`, `stop_regex`, `content_type_field`, `title_field` |
| `visuals.product_regex` | None | Words that mean an image prompt shows the product, so it must start from `product_reference_photo` |

### Defaults for every key a script reads

Keys not in the tables above. A missing key uses this default; a missing optional check is skipped.

| Key | Default |
| --- | --- |
| `company.name`, `company.approver.name` | Empty: scripts write "the company" and "the approver" |
| `company.people` | `[]` |
| `company.holiday_market` | Empty: the holiday check is skipped. `US`, `UK` and `NL` have holiday tables |
| `channels` | `["LinkedIn"]` |
| `run.horizon_days` | `13` |
| `run.plan_check_weeks` | `4` |
| `run.swap_days` | `5` |
| `run.max_fallbacks` | `4` |
| `run.default_mode` | `test` |
| `facts.id_col`, `facts.claim_col`, `facts.status_col`, `facts.comments_col` | `ID`, `Claim`, `Status`, `Approver comments` |
| `facts.approved_values` | `["Approved", "Approved with edits"]` |
| `calendar.team_owned_regex` | `Publish\|Newsletter\|Distribute` |
| `calendar.teaser_regex` | `LinkedIn teaser` |
| `calendar.event_live_regex` | None: only `visuals.real_photo_only_regex` marks real-photo rows |
| `calendar.proof_placeholders` | Partner Win: "Partner news (to confirm)", Customer Proof: "Customer story (to confirm)" |
| `sources.calendar.tab` | `calendar.tabs.calendar` (Calendar) |
| `sources.long_form.chapter_map` | `chapter-map.md` |
| `writing.spelling`, `writing.units` | Empty: that check is skipped (`check_workspace.py` asks for a value) |
| `writing.word_count`, `writing.opening_max_words`, `writing.hashtags` | None: that check is skipped |
| `writing.no_em_dash`, `writing.link_in_first_comment` | `true` |
| `writing.emoji` | Allowed unless `false` |
| `writing.competitors`, `writing.avoid_terms`, `writing.custom_rules`, `writing.on_hold_topics` | `[]` |
| `writing.date_words_warn` | A built-in list of launch and availability words |
| `plan.known_deviations`, `plan.dependencies`, `plan.no_repeat_in_week` | `[]` |
| `plan.posts_per_week`, `plan.proof_slot`, `plan.blog_pair`, `plan.rotation_slot` | None: that check is skipped |
| `swaps.types` | `["Industry POV", "Poll", "<source label> push"]` |
| `swaps.source_label` | `Long-form` |
| `swaps.chapters`, `swaps.excluded_chapters` | `[]` |
| `visuals.no_repeat_weeks` | `8` |
| `visuals.asset_prefix` | `Assets` |
| `visuals.ai_image_tool`, `visuals.product_reference_photo`, `visuals.real_photo_only_regex` | None |
| `visuals.aspect_ratios` | `["1.91:1 (1200 x 627)", "1:1 (1080 x 1080)"]` |

## Changing the config

Re-run `/setup-workspace` and choose "update", or edit the file and run `/setup-workspace check`. Either way, record the change and a fresh TEST run in the agent register before the next live run. What a client can change in the config, and what needs a plugin change, is in `docs/change-guide.md`.
