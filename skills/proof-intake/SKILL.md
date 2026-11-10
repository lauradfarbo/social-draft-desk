---
name: proof-intake
description: Fills the Partner Win and Customer Proof calendar slots (and matches Advisory board announcement rows) from signed-off proof log items only, drafting the LinkedIn post into the weekly draft doc. When the workspace allows it, also logs proof news the approver gives in Notes or on the Ideas tab. Use when asked to "run proof intake", "check the proof log", "draft the partner post", "draft the customer story", "fill the proof slots", "process new proof", or when the weekly orchestrator calls proof intake. Flags empty slots and proposes swaps; never invents a customer, partner or quote.
---

# Proof intake

Match items in the proof log to the proof slots on the content calendar (the content types in `calendar.proof_types`: Partner Win, Customer Proof and Advisory board announcement by default). Draft a post only from a signed-off item. With no usable proof, flag the slot and propose a swap. This skill never publishes, and never writes a quote, name or result that is not in the proof log.

Read `workspace.json` first. If there is none, run the `workspace-setup` skill and stop.

## Purpose, inputs, outputs, access

- **Purpose:** turn signed-off proof into review-ready posts, and flag proof slots that cannot run.
- **Assumptions:** the calendar has the A to V schema and the proof log has the A to J columns in `references/proof-rules.md`.
- **Inputs:** `workspace.json`, the calendar (Notes), the Ideas tab, the proof log, the rules file, the voice guide, approved facts, the approver's facts (`person_items.json`), the approver's recent edits and the assets listing. See `references/locations.md`.
- **Outputs:** one tab per drafted slot in the week's draft doc; on the calendar, the cells listed under "Writes"; on the proof log, column J, plus new rows for the approver's news only when `proof.approver_word_is_signoff` is true.
- **Access:** read-only on reference sources; write on the calendar (listed cells), the proof log (as above) and the drafts folder.

## Sign-off rule (config)

`proof.approver_word_is_signoff` sets what counts as signed off. It is false unless the client chose otherwise in `workspace.json`.

- **false (default):** only Sign-off status `Yes` counts, with Organization, What happened, Sign-off from and Can go public from filled. Agents never write new proof log rows. When the approver's note gives proof news (a partner came on board, a customer signed, an advisor joined), add "To finish: Log this in the proof log with sign-off" to What's missing on the row it is for, and say so in the brief.
- **true:** the approver's word is the sign-off. News the approver gives in Notes or on the Ideas tab is logged by agents with `scripts/proof_log_add.py` (step 1a). An entry counts as signed off unless Sign-off status is in `proof.not_signed_off_values` (default `No`, `Pending`). A blank Sign-off from counts as Logged by; a blank Can go public from counts as Date logged. An implied sign-off adds a reviewer note asking the approver to confirm the organization is happy to be named.

In both cases, outside people and companies are named only from the proof log. The company's own team (`company.people`) may always be named. The approver's word never covers a quote: a quote is used only when it is in the log word for word with who said it.

## Hard rules

- Never publish, post, send email or submit anything.
- Read the rules file and the voice guide before writing. The rules file wins over every other file, including this skill.
- Draft only from an item that is signed off under the sign-off rule above, with Organization and What happened filled and public on or before the slot date. Anything else is not proof.
- Use the organization's name exactly as in the proof log. Name no other customer, partner, person or company.
- Use the approved quote word for word, with its attribution exactly as written, or not at all. Never shorten, tidy or paraphrase it into quotation marks. Never write a quote.
- State what happened only as the proof log states it. No added figures, results, scope, dates or adjectives the item does not give. Claims about the company need a fact ID whose Status is in `facts.approved_values`, or a person item, as in the short-form drafter. Numbers inside [brackets] are gaps, not figures.
- Every other content rule applies: `writing.competitors`, `writing.custom_rules`, `writing.on_hold_topics` (with the same hold lifts as the drafter), no launch, availability or delivery dates, and the spelling and units in the config.
- If the go-public date is after the run date, the draft is allowed, but the reviewer notes and Notes say "Do not post before DD MMM YY".
- Never generate images or video, and never use an AI image prompt for a proof post: it shows a real organization. The visual is an assets file for that organization (not used on another row within `visuals.no_repeat_weeks` weeks) or `Needed: <organization> logo or photo, with their permission`.
- Learn from the approver's edits: when the bundle holds `approver_edits.json`, write the way the approver edits (structure, hook, call to action, tone). Style only: claims still come from the proof item or a fact ID.
- Skip `Cancelled` and `Backlog` rows. Never mention a Cancelled row in any output.
- Use TEST files until the agent register records a passing test for this skill.

## Writes

- **Calendar**, on the slot row only: Status (B, `Draft ready` only), Title / angle (F, only while it reads the placeholder in `calendar.proof_placeholders`), Visual (I), Notes (J: a person's text word for word plus one current "<`notes.agent_prefix`> DD MMM YY:" line; older agent lines move to the Agent log through the orchestrator's tidy), What's missing (K, this row only), Sources (L, append only), Proof item (R), Draft URL (U) and Original draft (V, write once; a v2 redraft replaces it). Never write G, H, formula columns or any other tab. Never change Status to anything else, and never change Content type or Date to make a swap: the swap goes on a backup row the orchestrator inserts.
- **Proof log**: column J ("Used in calendar row (agent fills)") on any item. New rows only when `proof.approver_word_is_signoff` is true, through `proof_log_add.py`. Never edit a row a person wrote.
- Before each write, re-read the row and confirm its Row ID and Status are unchanged; after it, read back and confirm. Never retype a person's cell text into a write.

## Files

Read `references/locations.md` for the `sources.*` keys, `references/proof-rules.md` for sign-off, matching, flags, swaps and the post shape, and `references/draft-doc-format.md` before creating docs or tabs.

## Steps

1. **Read** the calendar (A1:V), the Ideas tab and the proof log (A1:J). Save each as JSON in the `{"values": [...]}` shape, exactly as returned.
1a. **The approver's proof news.** When a person's text in Notes or an Ideas row says a partner came on board, a customer signed, an advisor joined the board or similar, that is proof news. A plan or a hope ("we expect to sign X") is not: leave it.
   - If `proof.approver_word_is_signoff` is true: write each piece of news as an item in `new_items.json` (type, organization exactly as written, what happened in their words, a quote only if given word for word with who said it, source, the date it was added: the date in the note, else Date added on Ideas, else the run date) and run `python3 scripts/proof_log_add.py proof_log.json new_items.json --config workspace.json`. Write its `rows` to its `range`, read them back, then reread the proof log before step 2. News already in the log is skipped. Put its `brief_lines` in the output.
   - If it is false: write nothing to the proof log. Add "To finish: Log this in the proof log with sign-off (<organization>)" to What's missing on the row the news is for. The script refuses to run (exit 3) in this setting.
2. **Match**: run `python3 scripts/match_proof.py calendar.json proof_log.json --config workspace.json` (add `--as-of YYYY-MM-DD` only for tests). The plan lists, for each proof slot in the next 14 days and each Planned Advisory board announcement row within `proof.advisor_horizon_days` (default 91), `draft` with a proof row, `flag` with the reasons, or `no_item` (advisory rows only), plus items to mark as not used and proof log problems. Follow the plan. If a slot's `person_note` sets a condition (for example a specific partner or event), check the item meets it; if not, treat the slot as `flag` and say why.
3. **For each `draft` slot with `drafter` "proof-intake"**, in its own subagent when there are several (one row, one proof item, the rules, voice guide, approved facts, `person_items.json` and `approver_edits.json` only):
   1. Write the post as set out in proof-rules.md, plus one alternate hook, the first comment (only if the item gives a public link) and the visual line.
   2. Save the draft and the proof item as JSON. Run `python3 scripts/check_draft.py draft.json --config workspace.json --facts facts.json`, then `python3 scripts/check_proof_post.py draft.json proof_item.json --config workspace.json` (add `--live` on the live calendar). Fix every fail and resolve every warning, as in the drafter.
   3. Check each sentence: it maps to the proof item, a fact ID or a person item. Remove anything that does not.
   4. Repeat the checks once if anything changed. If still failing, do not set Draft ready: write the tab with the failures under "Flags for the approver", add the Notes line and stop for this row.
3a. **Advisory board rows** (`drafter` "short-form-drafter"): the short-form drafter drafts them, with the matched Advisor item as `proof_item.json` and first in `person_items.json`. A `no_item` row gets a base draft with the advisor's details as [bracketed] gaps; no flag, no swap.
4. **Write the doc tab** in the week's draft doc (draft-doc-format.md). Short type in the tab name: `Partner news`, `Customer story` or `Advisor`, or the client's equivalent.
5. **Write the calendar row**: U tab link; V post text (only if empty); I visual; R the proof log row link; F the new title (only when `title_placeholder` is true; proof-rules.md); L append "; Proof intake: Proof log row N, <rules title>, <voice guide title>; Facts <IDs>"; J the agent line "<prefix> DD MMM YY: drafted from proof log row N." plus "Do not post before DD MMM YY." if needed; K clear the proof request; B `Draft ready`.
6. **Write the proof log**: J on the used item = "<Row ID> (drafted DD MMM YY)".
7. **For each `flag` slot**: write one agent line in Notes per proof-rules.md, with the swap proposal when `propose_swap` is true. Skip if `already_flagged` is true. Leave K as it is (it already names what a person must provide); add to K only if it is empty.
8. **For each item in `mark_not_used_signoff_no`**: J = "Not used: sign-off No (DD MMM YY)".
9. **For `proof_log_problems`**: do not edit the item. Report each in the output so a person fixes it.

## Called by the weekly orchestrator

The weekly orchestrator runs steps 1a and 2 in the main session and step 3 in a subagent per slot. The subagent gets a local bundle (`workspace.json`, `row.json`, `proof_item.json`, `person_items.json`, `approver_edits.json`, rules, voice guide, approved facts, assets listing), uses only Read, Bash and Glob, writes nothing and returns JSON as set out in the orchestrator's subagent prompts. The orchestrator runs the independent compliance checker, then does steps 4 to 9 as the only writer.

## Output to the person

One line per proof slot: Row ID, date, result (Draft ready, flagged, swap proposed, base draft for an advisory row), the tab link or the reason, and the proof log row used. Then one line per proof log row added, per proof log problem, per news item waiting to be logged, and per signed-off item waiting for a later slot. Brief. Dates in DD MMM YY with an uppercase month.
