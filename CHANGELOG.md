# Changelog

## 1.0.0 (10 NOV 26)

First public release.

- `/setup-workspace`: points every agent at the client's calendar, rules, voice guide, facts sheet, proof log, long-form source, assets and folders (Google Drive, Notion, GitHub, SharePoint, a local folder or a URL) and writes `workspace.json`.
- `brand-voice-guide`: builds the voice guide every drafter writes against.
- `calendar-builder`: converts an approved plan into a rolling 13-week calendar; monthly, milestone and idea rows are added as proposals.
- `/weekly-run`: the weekly full run (plan check, one drafter per post, independent compliance check, one redraft, guarded calendar writes, read-back, brief) and a light weekday requests run.
- Plain-word direction: asks in Notes, on the Ideas tab or by editing a row are acted on, with one Notes line saying what changed.
- Always drafts: missing details become [bracketed] gaps listed in What's missing.
- Backup rows (`Fallback post`), a Backlog tab, short Notes with an Agent log, ISO week Row IDs, series posts kept in order.
- Learning from the approver's edits, with monthly voice guide proposals for approval.
- Proof posts only from signed-off proof log items; the approver's word as sign-off is an option, off by default.
- Shadow mode, TEST copies and missed-run recovery.
- Docs: runbook, troubleshooting, change guide, go-live checklist, config reference, agent standards.
- Tests with a fictional company (Brightwell Analytics).
