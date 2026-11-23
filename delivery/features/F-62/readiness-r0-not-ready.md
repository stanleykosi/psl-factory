DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- The three screens are 13 boards (SCR-01: 9, SCR-10: 2, SCR-14: 2), over the 8-board limit. SCR-01 alone is rated L (screens-a-frame-core.md line 96).
- All three read one endpoint, GET /work, with a different queue. That makes a clean split possible.
- Live API 1.22.0 cannot fill several design parts: tab counts, station bar, Decide/Do/Fix tag, reference, state filters, rows per page, exception kind, month filter and totals. Backend questions A-6 to A-10 and A-37 to A-41 are open.
- Each of those parts needs a recorded rule: hide it, or show the live substitute. That is a visible change to the approved boards.
- I did not re-run design.py check or re-verify architecture approval for this note. The builder must confirm both before the spec starts.

## Scope
Split into two features. Each connects to live GET /work and keeps the unknown-is-not-zero rule.

F-62a (task FE-CONNECT-1, part 1), 6 boards:
- Shared work-list adapter: `?queue`, `page`/`next_page`, the `lines[]` title lookup, `limited`/`evaluated`/`deferred` coverage, `as_of`, and "show more" that keeps asking past empty pages.
- SCR-14 Verified outputs (`queue=verified`, `output_url`) and SCR-10 All exceptions (`queue=exceptions`, `state` and `status_label`, `owner`, `updated_at`).
- Their desktop and phone boards, plus empty states.
- Out: Facts earned and Proof columns, month filter and counts. These are hidden or replaced with the live substitute until A-37 to A-41 are answered.

F-62b (task FE-CONNECT-1, part 2), 9 boards, after F-62a merges:
- SCR-01 My work: the 8 tabs, tab renames, search, line and project filters, and the lead view.
- Role heading and decisions from `/role-dashboard`.
- If 9 boards is too many, defer the `/role-dashboard` section. It is new in live and not on the current boards.
- Out: per-tab counts, station bar, kind tag, state and waiting-on filters, rows-per-page, "While you're free" suggestions, and the assign-PM write. Treat each as hidden or substituted per the backend answers.

Both parts open an item's work at `/work/{id}` with the integer `id`. Neither adds backend or contract changes.

## Risk
Medium: a cross-layer contract change (v7 to live row shape, paging and queue renames) shared by three screens, with read-only access and no money or data writes. Product acceptance is required because dropping or substituting design parts (counts, filters, reference) changes what the client approved. Source: delivery/connect/screens-a-frame-core.md, SCR-01, SCR-10 and SCR-14.
