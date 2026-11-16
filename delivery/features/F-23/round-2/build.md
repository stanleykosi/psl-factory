STATUS: READY
COMMIT: 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the blocking UX-1-1, UI-1-1, UI-1-2, UI-1-3 and UI-1-4, SEC-1-1 and the in-scope non-blocking items. Contract mock only; nothing is released (D-LINE-WORKSPACE limits as in round 1; test template; no real send).
- One fidelity run of 8 boards (plus one single-board probe of the desktop default while testing a due-date format, not scored): coverage 100 after exceptions on all; desktop default is 69.2, under the D-83 floor of 70 (open design-engineer decision).

## Changes
- UX-1-1: item-scope forms open with the row's current values. New PROPOSAL `items[].values` (text string, record {value,label}, date ISO) read by `proposals.ts` `itemValues`; `StepForm` takes `initial` (wins over descriptor `value`). Untouched values are sent as they were; a field the PM clears is left out, as the spec says. Fixture rows carry `values`; the contract test checks them on their own and strips them.
- UI-1-1: dropped `context.project` from W-2301 and W-2306..W-2308 (crumbs kept).
- UI-1-2: general CSS grid for side-column rows with a tick, as the review gave.
- UI-1-3: `WorkItemOverview` draws no task card for a task that a workspace step's `task_id` already links to (general rule). F-17/F-21/F-22 line boards have no such pair; the weekly, workspace, decide and decide-board suites and e2e pass unchanged.
- UI-1-4: drafted and review fixtures follow the boards: no extra heading or version line; one panel "Minutes" / "Minutes v1 · for Lagoon Health" whose first row is "Minutes v1 · client version" with a DRAFTED tag; IN tags neutral.
- SEC-1-1: a restricted section adds nothing to ticks, the confirm set or the cross-section count; component test added.
- UX-1-4: tables with step buttons stack their rows on a phone (Edit and Remove on screen). UX-1-6: "Done:" messages are not prefixed with the step label; the W-2301 sidecar messages read "Done: action added." etc. UX-1-7: W-2302's agent block has the four steps (3 of 4). UI-1-5: the Due column is text as the board draws it ("13 Nov", "Unknown"). Cost: Unknown is plain text, not the Unknown pill.
- Exceptions 5-8 (Conflicts 6 entries) reworded per UI Q2: words present, the tool does not read text inside a list row, placement and style differ. Waiver texts carry the measured scores.

## Fixes
- UX-1-1 | 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772 | Edit forms prefill text, owner and due from the row
- UI-1-1 | 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772 | context.project dropped from the default fixtures
- UI-1-2 | 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772 | tick beside the words in side-column rows
- UI-1-3 | 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772 | no task card for a task a workspace step links to
- UI-1-4 | 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772 | drafted and review rows as the boards draw them, IN neutral
- SEC-1-1 | 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772 | restricted sections excluded from the confirm set and count
- UX-1-4, UX-1-6, UX-1-7, UI-1-5, TECH-1-2 | 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772 | as above

## Left, and why
- UX-1-2 (invoice/Finance wording on the minutes decision result and reconcile panel): shared F-16 and response copy, not minutes fixtures. Needs a shared-copy change by its owner.
- UX-1-3 (work page "Approve and send, sends this exact version" against the decision page "Approve v1 … Send is the next station"): the decision page text is shared F-16 copy (X-VERDICTS); the work-page sentence is the spec's. Needs a coordinator or design-engineer choice.
- UX-1-5 (Conflicts 6 signature), UX-1-8 (disabled-button contrast and the empty area, shared with F-21), UI-1-6 (Tola's note third-sentence colour): for the design engineer or the frame backlog. The "Add action to continue." sentence is the frame's shared required-field wording.
- TECH-1-1: item-scope steps now send `item_ids: [id]` on every line, not only minutes; the backend handler for each line must accept or ignore it.
- Round-1 open items unchanged: the changed F-17 assertion, the three deviations, desktop default visual under 70.

## Acceptance criteria
Round-1 evidence stands; tests added for prefill, restricted sections, task-card suppression, "Done:" wording and the board rows (minutes.test.tsx, 42 tests). Fidelity (round-2/fidelity/scores.txt):
desktop 1440: default 69.2, suggesting 81.3, drafted 85.4, review 78.7; phone 390: default 74.2, suggesting 82, drafted 82.5, review 78.7. Coverage with exceptions 100 on all.

## Validation
- bash delivery/checks.sh: exit 0.
- Playwright (4761/4762): minutes, weekly, weekly-returned-received, workspace, decide, decide-board, assistant: 170 passed.
- Servers stopped by PID; test-results deleted.

## Verified
- UX-1-1 | verified | component tests: Edit opens with the row's values (text, Lagoon Health owner, due), and an untouched save sends them; an action with no owner or due sends text only.
- UI-1-1 | verified | fixture and test: W-2301 has no context.project; W-2302 keeps it.
- UI-1-3 | verified | W-2304 test: no Open the decision, no task card; the two workspace links remain.
- SEC-1-1 | verified | restricted decisions section: its rows are not drawn, not counted, not sent (item_ids A-1..A-3).
- UI-1-2, UI-1-4 | verified | fidelity side-by-side shows the tick inline; drafted 85.4 and review 78.7, phone review 78.7.
