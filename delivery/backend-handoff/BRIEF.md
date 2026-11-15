# Brief: board-vs-contract gap check for the backend handoff (15 Nov 2026)

Goal: by tonight the backend developer must know, for every screen, what he is building, how
(endpoints, fields, writes, guards) and where the current v7 contract has to change. You check a
group of screens that have NOT been built yet. Read-only work: do not edit code, architecture or
boards. Write only your one output file.

## Sources
- Approved boards (the spec): `design/canvas/project/SCR-*.dc.html` (main canvas) and
  `design/canvas/finance/project/SCR-*.dc.html` (Finance and Payroll canvas). Open every board of
  your screens, desktop and mobile, every state.
- Screen list and states: `design/screens.md`; task per screen: `delivery/screen-coverage.md`.
- Contract v7 (proposal, additive over v6): `architecture/packages/v7/openapi.json` (schemas and
  operations), `endpoints.csv` (operation id → method, path), `model.json` (records, decisions,
  their status), `delivery.md` (per task: refs, fields, acceptance), `handoff.md`.
- Line screens render through the shared workspace block on the work item (built in F-17):
  read `delivery/features/F-17/spec.md` (Contract section) and `frontend/src/features/workspace/`
  for the section kinds and step field kinds that already exist. A line board's needs are a gap
  only when no existing section kind / step field kind / operation can carry them.
- Examples of how gaps were found and written: the "Conflicts" sections of
  `delivery/features/F-19/spec.md` and `delivery/features/F-21/spec.md`.

## Rules
- Business rules, approvers, money values and thresholds are never invented. If a board needs a
  rule PSL hasn't decided, name the open decision id (D-COSTING-RULE, D-CHANGE-DECIDERS,
  D-RECEIPT-ALLOCATION, D-DECISION-VARIANTS, D-ADMIN-AUTHORITY, D-PAYROLL-VISIBILITY, D-SIGNIN,
  D-SPEECH-INPUT, or another from model.json) instead of proposing one.
- Unknown values are not zero; payment exceptions don't erase debt; access is per record and action;
  model output never grants authority; uncertain external effects are reconciled before any retry.
  Flag every board element that touches these.
- Prefer additive changes. Say "additive" or "breaking" for each proposal.
- Be concrete: name the operation id, schema and field path; quote the board text that needs it.
- Plain business language in the "What the screen does" line; precise technical detail elsewhere.

## Output format (Markdown, exactly this shape per screen)

```
## SCR-xx · <screen name> (<states>)
Task: <FE task id> · Boards: <n> · Canvas: main|finance · Gated by: <decision ids or none>
What the screen does: <one or two plain sentences: who uses it, what they see, what they decide or do>
Proposed route: </path> (or "work item line workspace: line key <key>")
Reads: <op id> <METHOD path> — fields used: <a, b.c, …>
Writes: <op id> <METHOD path> — body: <…>; guards: expected_revision | idempotency_key | CSRF | claim
Agent work shown: <what the agent drafts/checks/assembles on this screen, and which human decision follows>
Covered by v7 as is: <list of board elements fully covered>
Gaps:
- G-<SCR>-<n> | <board element, quoted> | v7 today: <what exists or "nothing"> | change: <proposal> | additive|breaking | blocking|nice-to-have
Questions for the backend developer:
- <question>
```

End the file with a `## Summary` table: screen, boards, gaps (blocking / nice-to-have), gated by.
