# Learning from the approver's edits

Applies only when `edit_learning.enabled` is true (the default). When it is false, skip the edit capture (SKILL step 10) and the monthly proposals (step 23), and bundles get no `approver_edits.json` or `approver_prompt_edits.json`.

The approver edits drafts in the draft doc, sometimes rewriting them fully. The agents learn from this in two ways.

## Every full run: examples (step 10)

`edit_capture.py` compares each Draft ready, Fallback post, Approved or Posted tab with Original draft and logs every new version on the Approver edits tab (`calendar.tabs.approver_edits`): Date captured, Row ID, Content type, Status, Size of edit (Light edit, or Rewrite when under half the draft's words survive), Original draft, Approver's text, What changed, Draft URL. With `--prompts`, an edited image prompt is logged as its own row with Content type "Image prompt: <content type>". The main session writes What changed in one or two plain sentences, for example "Rewrote the call to action: dropped the email address and added a two-point benefit list."

An edit already logged with the same text is skipped; a later change logs a new row. Only docs changed since the previous brief are read.

Draft, proof and fallback bundles get up to `edit_learning.examples_per_draft` (default 3) of the approver's latest edited posts, same content type first, as `approver_edits.json` (`row_id`, `content_type`, `size`, `what_changed`, `original_draft`, `approvers_text`), and the latest three prompt edits as `approver_prompt_edits.json` (`row_id`, `original_prompt`, `approvers_prompt`, `what_changed`). The shared inputs are `shared/approver_notes.json` and `shared/approver_edits.json` (the tabs as read). Drafters copy the approver's choices (structure, hooks, calls to action, tone, what is cut), never the claims: a claim in the approver's text still needs a fact ID or `person_items.json`.

## Monthly: voice guide proposals (step 23)

On the monthly run only. Bundle `voice/`: the Approver edits rows captured since the last proposals (as `edits.json`), `voice.md`, `rules.md`, `workspace.json`. Agent: a general-purpose subagent with Read only. Prompt:

```
You review how <approver> edits <company>'s post drafts. Read workspace.json, voice.md and rules.md, then each edit in edits.json (Original draft and Approver's text). Find patterns that repeat in at least <min_supporting_edits> edits: structure, hooks, calls to action, tone, words added or cut, length. Ignore one-off fact changes. Return only JSON: {"proposals": [{"voice_guide_section", "change": "one sentence, written as a rule", "evidence": ["<Row ID>: <what the approver did>", ...]}], "notes": "anything that conflicts with rules.md"}. At most <monthly_proposals_max> proposals. A proposal never relaxes a rule in rules.md. Use <spelling> spelling, no em dashes.
```

`<approver>` is `company.approver.name`, `<company>` is `company.name`, and the numbers come from `edit_learning.*` (defaults 2 and 5). The orchestrator lists the proposals in the brief under "Voice guide changes to approve". The approver edits the voice guide; agents never change it.

## Limits

- An edit made on the channel after posting is not seen. Edits belong in the draft doc.
- A Draft ready tab still being edited may be captured mid-edit; the next run captures the newer version as another row, and drafters use the latest.
