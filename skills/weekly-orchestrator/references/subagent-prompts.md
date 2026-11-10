# Subagents: bundles and prompts

Each subagent gets a folder with only what it needs, and a short prompt. Subagents write nothing to any platform. They return JSON; the main session saves each return with `save_result.py report` and writes.

Run folder: `weekly/<run date YYYY-MM-DD>/` in the session workspace. Shared files, saved once per run in `shared/` (read rules in SKILL.md, "Saving source data for the scripts"):

| File | From |
| --- | --- |
| `workspace.json` | The config, as loaded in step 1. Copied into every bundle |
| `calendar.json` | `sources.calendar` A1:V (also kept as `before.json`) |
| `proof_log.json` | `sources.proof_log` A1:J |
| `facts.json` | `sources.facts_sheet` (`tab`, `range`) |
| `facts_approved.json` | Rows of facts.json whose Status is in `facts.approved_values`, as `[{"id","claim","comments"}]` (`comments` from `facts.comments_col`). `make_bundles.py` writes it |
| `rules.md`, `plan_rules.md`, `voice.md` | `sources.rules`, `sources.plan_rules`, `sources.voice_guide`, each checked for its `expect_phrase`. Google Docs: Docs `read_doc`, saved as returned, then `python3 scripts/doc_text.py <saved>.json <name>.md --expect "<expect_phrase>"`. Never Drive `read_file_content` for a Doc. Other platforms: the text as returned. Stop the run if a check fails |
| `assets.txt` | `sources.assets` listing: one line per file, `<subfolder>/<file name>` |
| `milestones.json` | Milestones tab, A1:G (the planner lists rows of cancelled milestones; Milestones Notes go to linked rows' `person_items.json`) |
| `approver_notes.json` | The approver's notes tab (`calendar.tabs.approver_notes`), A1:G. `make_bundles.py` writes `person_items.json` into every draft, proof, fallback and check bundle |
| `approver_edits.json` | The Approver edits tab (`calendar.tabs.approver_edits`), A1:I, after step 10. Only when `edit_learning.enabled` is true. `make_bundles.py` writes `approver_edits.json` and `approver_prompt_edits.json` into every draft, proof and fallback bundle |
| `snapshot.json` | The hidden Agent snapshot tab, A1:L (main session only, never bundled) |
| `long_form.md` | Text of `sources.long_form`, once per run and only when something is drafted, so drafters need no connector |
| `chapter-map.md` | The client's chapter map (`sources.long_form.chapter_map`; template in `templates/chapter-map.md`) |

Build every bundle with `python3 scripts/make_bundles.py <run dir> <plugin root> plan|draft|proof|fallback|redraft|check ...` (`references/scripts.md`). It copies shared files, `workspace.json` included, and never retypes them.

Every subagent is a plugin agent with Read, Bash and Glob only, so none can reach a connector: `planner`, `compliance-checker`, `drafter` and `proof-drafter`. If a plugin agent type is not listed (for example before the plugin is reinstalled), stop and tell the person. On TEST only, a general-purpose subagent with the agent file's body pasted at the top of its prompt may stand in, and the brief says so.

Skill-only install (the package has a top-level `SKILL.md` and an `agents/` folder but no plugin agent types): this is a supported mode, live included. Start a general-purpose subagent for each role with the agent file's body pasted at the top of its prompt, followed by the bundle prompt below. Tell it to use only Read, Bash and Glob on its bundle folder and to call no connector. The brief's Run details say "Subagents: skill-only mode".

In every prompt, `<spelling>` is `writing.spelling` from `workspace.json` (US or UK).

## Planner

Bundle `plan/`: workspace.json, calendar.json, facts.json, proof_log.json, milestones.json, plan_rules.md, rules.md, `scripts/plan_check.py`.
Agent: `planner`.
Prompt: `Plan bundle: <abs path>/plan. Run date: <YYYY-MM-DD>. Follow your instructions and return only the JSON. Use <spelling> spelling as set in workspace.json.`

## Short-form drafter (one per `draft`, `refresh` or v2 row)

Bundle `draft/<Row ID>/`, built with `make_bundles.py ... draft --rows <ids> --select select.json` (add `--proof-rows` for an advisory row matched to an Advisor proof item; 0 for rows with none): workspace.json, `row.json` (the row as an object with the calendar headers as keys, plus `_row`), rules.md, voice.md, facts_approved.json, `person_items.json`, assets.txt, long_form.md, chapter-map.md, `recent.txt` (Row ID, Content type and Sources of rows of the same content type, and of long-form source rows, from `visuals.no_repeat_weeks` weeks before to 14 days after the row), `visuals_recent.txt` (Row ID, date and Visual of every other row within `visuals.no_repeat_weeks` either side), `gaps.json` for rows with gaps (`{"gaps", "placeholders"}`), `approver_edits.json` and `approver_prompt_edits.json` when edit learning is on, `proof_item.json` for an advisory row with a matched item, and copies of the short-form-drafter skill's `SKILL.md` (as `drafter_skill.md`), its `references/` files and `scripts/check_draft.py`. Teasers add `blog.txt` (the published blog text, read by the main session from the link in `blog_link`, or from a `sources.other` repo).
Agent: `drafter`.
Prompt:

```
You are the short-form drafter, called by the weekly orchestrator. Draft one post for row <Row ID>.
Bundle: <abs path>/draft/<Row ID>. Read workspace.json, then rules.md and voice.md; rules.md wins. Follow steps 1 to 8 of drafter_skill.md, using post-types.md and chapter-map.md from the bundle. Use <spelling> spelling as set in workspace.json.
Read one chapter of long_form.md only. Write nothing outside the bundle.
State only claims from facts_approved.json, plus person_items.json (facts the approver gave, approved as written). Name an outside person or company only from proof_item.json (the proof log); the people in company.people may always be named.
If approver_edits.json is in the bundle, read it before writing: each item is a post the approver edited (row_id, content_type, size, what_changed, original_draft, approvers_text). Write the way they edit: structure, hooks, calls to action, tone and what they cut. For the same content type, treat their text as the model. Style only: a claim in their text still needs a fact ID or person_items.json. If approver_prompt_edits.json is in the bundle (row_id, original_prompt, approvers_prompt, what_changed), write the image prompt the way they edit prompts.
Always draft: if gaps.json is in the bundle or something is missing, write the full post with each gap as [square-bracket text] and list each as a flag starting "To finish:" or "To strengthen:". Return blocked only for a hard rule or a hold. If post-types.md has no entry for the content type, use the nearest type and add a flag starting "New type:" with a one-line playbook entry.
Run check_draft.py with --config workspace.json --facts facts_approved.json on your draft and fix every fail.
Return only this JSON:
{"row_id","type":"post|founder|poll|video","post","first_comment","alternate_hook","poll_question","poll_options","visual","visual_alternatives":[],"image_prompt","image_alt_prompt","image_alt_subject","fact_ids":[],"sources":"<documents with version and long-form chapter>","flags":["one sentence each, or empty"],"word_count","script":"video rows only: shot list and script","blocked":"empty, or the hard rule or hold that stops the draft"}
```

Image prompt fields, when `visuals.ai_image_tool` is set: `image_prompt` is the ready-to-paste prompt for every post except real-photo-only rows (`visuals.real_photo_only_regex`), whatever the Visual line says. `image_alt_prompt` and `image_alt_subject` are filled only when the Visual is "Needed: <AI image tool> image of <subject>". When `visuals.ai_image_tool` is null, all three stay empty and the visual is a `Use:` file or `Needed: <photo or graphic>`.

## Fallback drafter (one per swap with `fallback: true`)

Bundle `fallback/<Row ID>/`: built with `make_bundles.py ... fallback --rows <ids> --swaps swaps_final.json`. As for the drafter, but row.json carries the swap (a Content type from `swaps.types`; the angle as Title / angle) and `fallback.json` holds the original row and the long-form chapter.
Agent: `drafter`.
Prompt: the drafter prompt, with "Draft one post for row <Row ID>" replaced by:

```
Draft one backup post for row <Row ID>: the proposed swap in fallback.json, not the original row. Use the content type and angle in row.json and read long_form.md chapter <N> only. The post must stand on its own: never mention the original topic, the swap or why it was made.
```

Save the return as `returns/<Row ID>-fb.json`. The checker and any redraft work as for any draft (check bundle `--suffix -fb --content-type "<swap type>"`; redraft `--from fallback/<Row ID>`). The main session writes it as a new `<Row ID>-FB` row (SKILL step 19).

## Proof drafter (one per `draft` slot in the match plan)

Bundle `proof/<Row ID>/` (`make_bundles.py ... proof --rows <ids> --proof-rows <N,...>`): as for the drafter, but with proof intake's `SKILL.md` (as `proof_skill.md`), `proof_item.json` (the proof log row as an object), `references/proof-rules.md` and `scripts/check_proof_post.py`.
Agent: `proof-drafter`.
Prompt: as for the drafter, but start with "You are proof intake, called by the weekly orchestrator. Follow step 3 of proof_skill.md and proof-rules.md. Use only proof_item.json for the organization, what happened and the quote." Add `"proof_row": <N>` to the returned JSON. No image prompt fields. Run `check_proof_post.py draft.json proof_item.json --config workspace.json --facts facts_approved.json` (add `--live` whenever the run reads the live calendar, shadow runs included).

## Compliance checker (one per draft)

Bundle `check/<Row ID>/` (or `check/<Row ID>-2/` for a redraft): `draft.json` built from the drafter's JSON with only row_id, content_type, type, post, first_comment, alternate_hook, visual, visual_alternatives, image_prompt, image_alt_prompt, image_alt_subject, poll_question, poll_options, fact_ids. Never include flags, sources or any note from the drafter. Add workspace.json, facts.json, `person_items.json`, rules.md, voice.md, assets.txt, visuals_recent.txt, `proof_item.json` for proof posts and matched advisory rows, and copies of `scripts/check_compliance.py` and `scripts/check_draft.py`.
Agent: `compliance-checker`.
Prompt: `Check bundle: <abs path>/check/<Row ID>. Follow your instructions and return only the JSON. Use <spelling> spelling as set in workspace.json.` Add one line for a new content type (what it is and its limits), and one line naming any hold lifted this run and how ("hold on the webinar topic lifted: CONFIRMED with a date in W12-03 Notes").

## Redraft (one per failed draft, once)

Bundle `redraft/<Row ID>-2/`: `make_bundles.py ... redraft --from draft/<Row ID> --previous <failed draft JSON> --fixes <checker fixes JSON>` (use `--from proof/<Row ID>` for a proof post, `--from fallback/<Row ID>` for a backup). It copies the original bundle, workspace.json included, and adds `previous.json` and `fixes.json`.
Agent: a fresh `drafter` or `proof-drafter`.
Prompt: the drafter prompt plus: `A compliance check failed. Apply every fix in fixes.json to previous.json. Keep everything else unless a fix requires a change. Return the same JSON.`

## Voice guide proposals (monthly)

See `references/edit-learning.md`.
