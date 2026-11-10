# Change guide

Most changes are made in your own files or in `workspace.json`, and take effect at the next run. A few need a change to the plugin itself.

## What you change in your own files

The agents read these at the start of every run.

| File | Change freely | Instead needs a config or plugin change |
| --- | --- | --- |
| Rules | Content rules, wording, who may be named, holds. Add a version line at the top (version, date, what changed) | A rule a script must enforce: add it to `writing.custom_rules` (config) |
| Plan rules | Themes, story arc, special initiatives, dependencies, playbook text | Cadence a script checks: `plan.*` (config) |
| Voice guide | Tone, examples, words to use and avoid, post mechanics | Word counts and the avoid list a script checks: `writing.word_count`, `writing.avoid_terms` (config) |
| Facts sheet | Add a claim with a new ID and an approved Status; withdraw one by changing its Status. Only approved claims are ever stated | Nothing |
| Milestones tab | Add, move or cancel events (Confirmed Yes, No or Cancelled). Notes there count as your words | Nothing |
| Ideas, Notes, proof log, How to use tab | Anything | Nothing |
| Assets folder | Add, rename or remove files | Nothing |

## What you change in `workspace.json`

Use `/setup-workspace update` (it asks what to change and checks the result) or edit the file and run `/setup-workspace check`. Every key is in `docs/workspace-config.md`. Run `/weekly-run test` after any config change before the next live run, and record it in the agent register.

| To change | Key |
| --- | --- |
| Spelling, units, word counts, hashtags, emoji | `writing.spelling`, `writing.units`, `writing.word_count`, `writing.hashtags`, `writing.emoji` |
| Competitor names, avoid list, claim rules, topics on hold | `writing.competitors`, `writing.avoid_terms`, `writing.custom_rules`, `writing.on_hold_topics` |
| Cadence: posts per week, proof slot, blog pair, rotation slot | `plan.posts_per_week`, `plan.proof_slot`, `plan.blog_pair`, `plan.rotation_slot` |
| Dated dependencies and what lifts them | `plan.dependencies` (with `milestone_type`) |
| Who may name people, who may write asks | `company.people`, `requests.from` |
| Whether the approver's word is proof sign-off | `proof.approver_word_is_signoff` (read the trade-off first) |
| Edit learning on or off, examples per draft | `edit_learning.*` |
| How typed dates are read | `dates.typed_order` (also set the sheet's locale to match) |
| Swap types and long-form chapters | `swaps.*` |
| Visual rules, AI image tool, product reference photo | `visuals.*` |
| A source moved or replaced | `sources.<key>`. Moving a file usually keeps its ID; copying or recreating it makes a new one the config does not know |
| Run day or time | `run.full_run`, `run.requests_runs`, and the schedule of both scheduled tasks. Change the tasks; no plugin change |

## What needs a plugin change

- A new, renamed or moved column on the Calendar, Backlog or proof log. Tab names can be changed in `calendar.tabs` instead.
- A new status, or a change to which statuses agents may set.
- A check a regex cannot express (for example a rule that compares two rows).
- A new post type you want treated as standard. Until then, new types are drafted from the nearest pattern and listed in the brief for your approval.
- A new platform for the calendar, proof log, drafts or briefs beyond the adapter rules.
- A new channel with its own post format.

## How to ask Claude for a plugin change

1. Start a new task in Claude with the installed plugin available.
2. Describe the change and why, and paste the request below.
3. Claude changes a copy of the plugin, raises the version, adds a changelog entry, tests it on your TEST files and records the result in the agent register.
4. Install the new version in place of the old one and confirm the version.
5. If Claude says the new version must be required, update the version line in both scheduled task prompts after installing, never before, or the next run stops.
6. Check the next brief, or run `/weekly-run test` first.

Request to paste:

```
Update the installed social-draft-desk plugin (currently <version>). Change: <what you want and why>. Read the plugin README, docs/workspace-config.md, our workspace.json, our rules and our plan rules first. If the change can be made in workspace.json or our own files instead, say so and do that rather than changing the plugin. Otherwise make the change, raise the version, add a changelog entry, and test it on the TEST calendar and TEST proof log only. Record the tests in our agent register. Then package the plugin for me to install, and tell me if the scheduled task prompts need a new version line. Do not touch the live calendar until I confirm.
```

For a config change only:

```
Update our workspace.json at <location>. Change: <what you want and why>. Use /setup-workspace update, run /setup-workspace check, then run /weekly-run test and record the result in our agent register. Do not touch the live calendar.
```
