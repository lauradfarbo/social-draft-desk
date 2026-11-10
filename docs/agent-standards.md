# Agent standards

Every skill and agent in this repo meets these standards before it runs against a client's live workspace.

## 1. Document the agent

Each `SKILL.md` and agent file states:

- **Purpose:** the job, in one sentence.
- **Assumptions:** what must already be true (a valid `workspace.json`, an approved plan, a voice guide).
- **Inputs:** every source it reads, by its `sources.*` key in the config.
- **Outputs:** every file, cell or row it writes, and the Status it sets.
- **Access:** the connectors it needs and the narrowest scope that works. Read-only wherever writing is not required. Subagents get Read, Bash and Glob on a local bundle and no connectors.
- **Hard rules:** what it must never do.

The client keeps an agent register (a sheet) with each agent's purpose, inputs, outputs, assumptions, access and test results.

## 2. Keep a person in the loop

- Agents draft, propose and flag. They never publish, post, send email or submit forms.
- The rules file wins over every other file, including the skills.

### The approver's direction comes first

- People direct the calendar in plain words: in a row's Notes, on the Ideas tab, or by editing a row's cells directly. Only people in `requests.from` (default: the approver) are acted on. No set phrase is ever needed.
- On a Planned or Proposed row, agents make the change asked for in the `calendar.request_columns` cells (Date, What to post, Pillar, Channel, Title / angle, Content type, Spec), then draft, and say what changed in one Notes line. They never tell a person to edit a column themselves.
- If part of an ask breaks a hard rule, agents do the rest and say in the same line what was left out and why.
- When an ask is clear, agents act on it, even in an unattended run, and say in Notes what they took it to mean. When two readings cannot both be right, they do not draft, and name both readings in Notes and the brief.
- Typed dates are read per `dates.typed_order`. Agents write every date as DD MMM YY.

### Hand edits count

- Every run ends by saving the Calendar and Milestones to the hidden Agent snapshot tab, and the next run starts by comparing against it. A person's direct edit to a request column is an ask, handled like one in Notes.
- A changed row that already has a draft is redrafted into a v2 tab, and the v2 text replaces Original draft.
- A second run on the same day handles only what changed since the first (requests mode).
- Edits a person makes in the draft doc are logged on the Approver edits tab (when `edit_learning.enabled`). Drafters copy the approver's style from them, never their claims. Monthly voice guide changes are proposals in the brief; agents never edit the voice guide.

### Always draft, with gaps

- A missing fact, link, name or photo is a gap, not a blocker. The drafter writes a base draft with the gap in [square brackets], What's missing lists exactly what would finish it, and Status goes to Draft ready.
- Only hard rules and holds stop a draft. A hold lifts on plain words: a dated "CONFIRMED" in Notes, a Milestones row of the dependency's type with Confirmed Yes, or the dependency fact turning Approved.
- Numbers inside [brackets] are gaps, not figures.

### Statuses

| Set by | Statuses |
| --- | --- |
| Agents | Proposed (new rows), Draft ready (a checked draft), Fallback post (a backup row agents add) |
| People | Planned, Approved, Posted, Cancelled, Backlog |

- Agents never set a people status, never draft a Proposed row, and never edit or delete a row a person approved.
- A person drops a post by setting Cancelled, never by deleting the row. Every run hides Cancelled rows on the Calendar. Agents skip them everywhere, never write to them, and never mention them in a brief, update, run summary or notification.
- A person keeps a post for later by setting Backlog. The run moves the whole row to the Backlog tab, writing and reading back the copy before it removes the original. A row set to Planned on the Backlog tab moves back to the Calendar.
- Agents never write formula columns (`calendar.formula_columns`), the This Week tab or summary tabs.

### Backup rows

- A row near its date that cannot run (a hold, or a proof slot with no usable proof) gets a backup post as a full new row directly under it: Row ID `<original>-FB`, Status Fallback post, its own draft tab.
- A person uses it by setting the backup to Approved and the original to Cancelled. Agents never make the swap.

### Short Notes and the Agent log

- Notes hold a person's text word for word plus one current agent line, "<`notes.agent_prefix`> DD MMM YY: <where the row stands>". A tidy never drops or changes a person's words.
- Older agent lines move word for word to the Agent log tab. Each run also writes one RUN row there with the full run details, so the brief keeps run details to three lines.
- What's missing is rewritten as the current list. Sources lose duplicates.

## 3. One writer, guarded writes

- Only the main session writes. Subagents work on local copies and return JSON.
- Every calendar write passes three checks: the column lock (`calendar_writes.py plan`), the Row ID and Status guard on a fresh read just before writing (`calendar_writes.py guard`), and a read-back (`calendar_writes.py verify`). Inserted backup rows and Backlog moves are guarded and verified the same way. Ideas and Milestones writes pass `tab_guard.py`. A refused write is reported, never retried around.
- People may sort or reorder the Calendar at any time. Runs match rows by Row ID, never by position, and every run ends by sorting by Date, AM/PM and Row ID.
- Append-only cells (Notes, Sources) are re-appended to the current value, so a person's edit during a run is kept. Original draft is written once, and replaced only by a v2 redraft.
- Connector results and subagent returns are saved exactly as returned. A person's cell text is never retyped into a write.

## 4. Claims and proof

- Drafts state only claims from approved facts sheet rows, the proof log, or facts the approver gave in Notes or on Ideas (filed by agents on the From the approver's notes tab). Anything else becomes a [bracketed] gap.
- A fact on the From the approver's notes tab counts as approved for drafting but never authorizes a name. Facts that keep coming up are flagged in the brief for the facts sheet, which only the approver edits.
- Outside people and companies are named only from the proof log. The company's own team (`company.people`) may always be named.
- Customer, partner and advisor posts use only signed-off proof log items, with organization names and quotes exactly as logged. What counts as signed off depends on `proof.approver_word_is_signoff`:
  - Off (default): only Sign-off status Yes counts, and agents never add proof log rows. News the approver mentions becomes "Log this in the proof log with sign-off" in What's missing.
  - On: agents log news the approver gives in the proof log themselves, entries count unless their Sign-off status is in `proof.not_signed_off_values`, and implied sign-offs carry a note asking the approver to confirm the organization is happy to be named.
- Agents never invent a customer, partner, quote, figure or result.
- Every draft is checked by a separate compliance checker that never sees the drafter's reasoning. One redraft, then the draft is flagged and Status stays as it was.

## 5. Test before going live

1. Run `/setup-workspace check`: the config must pass `check_workspace.py`.
2. Run on TEST copies (prefix `TEST - `) or in shadow mode.
3. Compare the output with the source, field by field, and report every mismatch rather than fixing it silently.
4. Record the result (date, mode, pass or fail, notes) in the agent register.
5. Switch to the live files only once the mode in use has a passing test with the current config. Any config or plugin change needs a fresh TEST run.

## 6. Writing standards for agent output

Defaults. The client's rules file and `writing.*` in the config override them.

- Professional tone, short sentences, no filler.
- No em dashes.
- Metric units.
- Dates in prose as `DD MMM YY` with a leading zero and an uppercase month (03 NOV 26).
- Week numbers are ISO weeks, and Row IDs use the same number (W11-02).
- One spelling variety per client, set in the config.
- Every statistic carries its source.

This repo itself is written in US English.

## 7. Keep client material out of the repo

- Skills are generic. Client names, products, people, competitors, colors, document IDs and reference files live in the client's workspace and `workspace.json`, never here.
- Worked examples and test fixtures use fictional companies.
- Before every commit, search the repo for client names, product names, people, document IDs and brand color codes. The `.gitignore` excludes `clients/`, `workspace.json` and `weekly/` run folders at the repo root.
