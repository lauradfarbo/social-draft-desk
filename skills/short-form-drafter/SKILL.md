---
name: short-form-drafter
description: Drafts LinkedIn posts from content calendar rows into the weekly draft doc, one tab per post. Use when asked to "draft row W06-01", "draft this week's posts", "draft the long-form push", "redraft W11-02", "write the LinkedIn post for this row", or when the weekly orchestrator calls the drafter for a Planned LinkedIn row. Covers teasers, press release announcements, long-form source pushes, industry POV, polls, event posts, partner recruitment, advisory board announcements, gratitude, year-in-review and short video scripts, and drafts any new content type from the nearest pattern. Not for Partner Win or Customer Proof (proof intake) or team-owned rows such as blogs, newsletters and press release distribution.
---

# Short-form drafter

Turn one Planned LinkedIn row on the content calendar into a review-ready draft: the post, one alternate hook, a visual, an image prompt, the facts used and the sources. The draft goes into the week's draft doc as its own tab. The approver (`company.approver.name`) reviews, edits in the tab and posts. This skill never publishes.

Read `workspace.json` first. If there is none, run the `workspace-setup` skill and stop.

## Purpose, inputs, outputs, access

- **Purpose:** one review-ready LinkedIn draft per Planned row, built only from approved facts and the approver's own facts. Always a full base draft: what is missing becomes a [bracketed] gap, not a blocker.
- **Assumptions:** the calendar exists with the A to V schema, the rules file and voice guide exist, and the facts sheet has a Status column.
- **Inputs:** `workspace.json`, the rules file, the voice guide, approved facts, the approver's facts (`person_items.json`), the approver's recent edits, the assets folder listing, one chapter of the long-form source (through the client's chapter map, read only when something is drafted), the calendar row and, for teasers, the published blog. See `references/locations.md`.
- **Outputs:** one tab in the week's draft doc (a v2 tab for a redraft); on the calendar row, the cells listed under "Calendar writes".
- **Access:** read-only on every reference source; write on the calendar (listed cells only) and the drafts folder.

## Hard rules

- Never publish, post, send email or submit anything.
- Read the rules file and the voice guide before writing. The rules file wins over every other file, including this skill.
- **Always draft.** When a fact, name, link or photo is missing, write the best full post you can from approved facts, put each missing item in the post as [square-bracket text] (for example `[Blog 2 link]` or `[Advisor's organization]`), and list each one as a flag starting "To finish:" (needed before posting) or "To strengthen:" (optional). Write the "To finish:" items in What's missing. Return `blocked` only for a hard rule or a hold (below). Numbers inside [brackets] are gaps, not figures.
- **Holds.** A row on a topic in `writing.on_hold_topics`, or held by an entry in `plan.dependencies`, is not drafted while the hold stands. A hold is lifted when its fact is approved, when a Milestones row of the dependency's `milestone_type` has Confirmed `Yes`, or when the row's Notes hold the hold-lift word (`requests.hold_lift_word`, default `CONFIRMED`) with a date. Read the approver's plain words in Notes; there are no other set phrases.
- State only claims from facts sheet rows whose Status is in `facts.approved_values`, or from `person_items.json`. Anything else is omitted, left as a gap or written under "Flags for the approver". The long-form source supplies angles, not approved claims.
- **The approver's facts.** `person_items.json` holds rows from the "From the approver's notes" tab (`calendar.tabs.approver_notes`): facts the approver gave in Notes or on the Ideas tab, word for word, plus the Notes of any Milestones row linked to this row. Each counts as approved for drafting. Cite it in Sources as "From the approver's notes row N". It never authorizes a name.
- **Names.** Name an outside person or company only from the proof log (`proof_item.json` in a bundle). The company's own team (`company.people`) may always be named. When the approver's note names someone new and the proof log does not have them, leave the name as a gap and add a "To finish:" flag: "Log this in the proof log with sign-off" (or, when `proof.approver_word_is_signoff` is true, proof intake logs it on the next run).
- Never name a company in `writing.competitors`, or any consumer brand. Compare categories, not companies.
- Never invent customers, partners, quotes, results, attendees, conversations or figures.
- No launch, availability or delivery dates unless the rules file allows them. Words in `writing.date_words_warn` are checked.
- Apply every client claim rule in `writing.custom_rules`. Use the approved wording each rule's message names.
- **New content types.** If `references/post-types.md` has no entry for the row's content type, draft it in the pattern of the nearest type (say which in a flag), and add a flag starting "New type:" with a one-line playbook entry for the approver to approve. Never stop on an unknown type.
- **Learn from the approver's edits.** When the bundle holds `approver_edits.json` (posts the approver edited, with the original draft and their text), read it before writing and write the way they edit: structure, hook, call to action, tone and what they cut. For the same content type, treat their text as the model. Style only: a claim in their text still needs a fact ID or a person item. `approver_prompt_edits.json` does the same for image prompts.
- Agents never generate images or video. Visuals come from the assets folder; when no unused file fits and `visuals.ai_image_tool` is set, the visual is an AI image the approver makes from the draft's prompt (`references/post-types.md`). Never reuse an assets file or an AI image subject used on another row within `visuals.no_repeat_weeks` weeks either side.
- **Image prompt on every draft.** When `visuals.ai_image_tool` is set, every draft except real-photo-only types (`visuals.real_photo_only_regex`) carries one ready-to-paste `image_prompt`, whatever the Visual line says, plus an identical as-drafted copy so the run can learn from the approver's prompt edits.
- **Series.** A row whose Notes say "post N of M" is part of a series. Draft it only within `series.draft_within_days` days (default 14) of its date, or once its details have arrived. Keep the series' order and voice.
- Spelling variety and units follow `writing.spelling` and `writing.units`.
- Draft only rows with Status `Planned` (and the orchestrator's refresh and v2 redrafts of `Draft ready` rows). Ignore `Proposed`, `Cancelled` and `Backlog`, and never mention a Cancelled row in any output. Never draft Partner Win or Customer Proof rows, or team-owned rows (`calendar.team_owned_regex`). Advisory board announcement rows are drafted here, with the matched Advisor proof item when there is one.
- Use the TEST calendar and TEST drafts folder until the agent register records a passing test for this skill.

## Calendar writes

Only these cells on the row being drafted: Status (B, to `Draft ready` only), Visual (I), Notes (J), What's missing (K, this row only), Sources (L, append only), Draft URL (U) and Original draft (V). Notes keep a person's text word for word plus one current agent line, "<`notes.agent_prefix`> DD MMM YY: ..."; append that line, or replace the cell only through the orchestrator's tidy, which moves older agent lines word for word to the Agent log tab. Original draft is written once; only a v2 redraft replaces it (with the new Draft URL). Never write G, H, formula columns, the Date or any other tab. Backup rows (`<Row ID>-FB`, Status `Fallback post`) are inserted by the weekly orchestrator, not by this skill. Before writing, re-read the row and confirm its Row ID and Status are unchanged; after writing, read it back and confirm each cell. Never retype a person's cell text into a write: copy it exactly as read.

## Files

Read `references/locations.md` for the `sources.*` keys this skill uses, `references/post-types.md` for what each content type needs, and `references/draft-doc-format.md` before creating docs or tabs. Read the client's chapter map (named in `sources.long_form.chapter_map`; template at `templates/chapter-map.md`) before using the long-form source.

## Steps for one row

**Fallback drafts.** When the bundle holds `fallback.json`, the orchestrator has proposed an evergreen swap for a row that cannot run. Draft the swap in `row.json` (a type from `swaps.types`, on its angle, from the long-form chapter in `fallback.json`), never the original row. The post stands on its own: no mention of the original topic, the swap or the reason. The orchestrator puts it on its own backup row, `<Row ID>-FB`, directly under the original.

**Refresh and v2 redrafts.** A row marked `refresh` (a teaser whose blog link has now arrived) or changed by hand after drafting (Date, What to post, Pillar, Channel, Title / angle, Content type or Spec) is redrafted from the current row into a v2 tab. `previous.json` holds the earlier draft: keep what still fits, fill the gaps that are now answered, and change what the edit changed.

1. **Read the row** (Calendar A to V) and confirm: Status is `Planned` (or a refresh or v2 redraft), Channel is LinkedIn, and the content type is not a proof or team-owned type. If not, stop and report why.
2. **Check holds** (Hard rules, "Holds"). A held row is not drafted: write "<topic> on hold: not drafted" as the Notes line and stop. Anything else that is missing (a teaser's blog link, event facts or photos, an advisor's details, a speaker or a registration link) becomes a gap: draft anyway. `gaps.json` in a bundle lists the gaps the orchestrator already knows.
3. **Load context** (keep it lean): the rules file, the voice guide, the approved facts, `person_items.json`, `approver_edits.json`, the assets listing (all subfolders), the relevant long-form chapter only, and for teasers the published blog. Read Sources on earlier rows of the same type (`recent.txt` in a bundle) to avoid repeating an angle, and the Visual column of rows within the no-repeat window (`visuals_recent.txt`) to avoid repeating an image.
4. **Plan the post** before writing: the one idea, the hook, the fact IDs or person items each claim will use, the gaps, the call to action, the visual (post-types.md, "Visual line") and the image prompt. A claim with no source does not go in.
5. **Write** the post, the alternate hook, the first comment (only if there is a link, or a `[link]` gap) and, for polls, the question and 2 to 4 options. For video types, write the shot list and script under the reviewer notes, and the caption post as the post.
6. **Check mechanically**: save the draft as JSON and run `python3 scripts/check_draft.py draft.json --config workspace.json --facts facts.json` (add `--person-items`, `--milestones` and `--row` when the files are not in the draft's folder; see the script header). Type is `post`, `founder`, `poll` or `video`. Fix every fail. Resolve every warning: change the text, or confirm it under "Checker" in the reviewer notes (for example "figure confirmed: fact C04 with source named"). The gaps warning is expected on a base draft: confirm every gap is in the flags.
7. **Check claims**: go sentence by sentence and confirm each factual statement maps to a fact ID or a person item. Remove, bracket or flag any that do not. Work through the voice guide's pre-publish checklist.
8. **Repeat 6 and 7** once if anything changed. If it still fails, do not set Draft ready: write the tab with the failures under "Flags for the approver", write the Notes line, and leave Status as is.
9. **Write the doc tab** as set out in draft-doc-format.md and get the tab link.
10. **Write the calendar row**: U = tab link; V = post text exactly as in the tab (only if V is empty, or on a v2 redraft); I = the visual line (for an AI image, only "Needed: <AI image tool> image of <subject>. Prompt in draft tab."; the prompts stay in the tab); L = append "; Drafter: <documents and versions>; Facts <IDs>; From the approver's notes row N"; J = the agent line "<prefix> DD MMM YY: ..." with one sentence per flag; K = the "To finish:" items, cleared of what this draft resolved; B = `Draft ready` if steps 6 to 8 passed.

## Running for several rows

Draft each row in its own subagent with only that row and the files in step 3, so drafts do not borrow each other's angles. Subagents get a local bundle (`workspace.json`, `row.json`, rules, voice guide, `facts_approved.json`, `person_items.json`, `gaps.json`, `approver_edits.json`, `approver_prompt_edits.json`, `milestones.json`, `proof_item.json` for an advisory row, `previous.json` for a redraft, assets and visuals listings, the long-form chapter), use only Read, Bash and Glob, and return JSON: the post, hook, first comment, visual, visual alternatives, image prompts, fact IDs, person items used, sources, flags ("To finish:", "To strengthen:", "New type:") and checker result. The main session alone writes the doc tabs and the calendar, one row at a time. When the weekly orchestrator calls this skill, the drafter runs steps 1 to 8 only, writes nothing to any platform, and returns the JSON set out in the orchestrator's subagent prompts. The orchestrator's independent compliance checker then checks the draft before Status changes.

## Output to the person

One line per row: Row ID, date, result (Draft ready, Draft ready with gaps, on hold, or failed checks), the tab link, what to send to finish it, and any new type to approve. Brief. Dates in DD MMM YY with an uppercase month.
