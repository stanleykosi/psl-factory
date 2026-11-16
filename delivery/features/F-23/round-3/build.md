STATUS: READY
COMMIT: 2e5eab9e7453da8eae518308537eb91140cef6ee
BUILDER: builder
LANE: full

## Summary
- Round 3 fixes blocking UI-2-1 and the listed non-blocking items. Contract mock only; nothing is released (D-LINE-WORKSPACE limits as before; test template; no real send).
- The Due column is a date column again; "13 Nov" comes from a general column option, not from text.

## Changes
- UI-2-1: W-2301 and W-2306..W-2308 (and their sidecars) have Due cells as `date` again, A-3 `{unknown: true}` (the frame's amber Unknown, INV-UNKNOWN). New fixtures-only PROPOSAL `columns[].date_format: "day_month"`, read by `columnDayMonth` in `proposals.ts`; the frame's date cell then uses the shared `formatDayMonth` from `@/components` ("13 Nov"). Without the option the full date shows, as before. Stripped and checked on its own in `mock-contract.test.ts`.
- DRAFTED tags: the README says a blue tag always means agent or processing work, and Tola produced the draft, so the DRAFTED row tag and the "Drafted" status are tone `agent` (blue), as the boards draw them.
- TECH-2-1: the fixtures-only guard now also covers `items[].values` and `columns[].date_format`: they may appear only in W-23xx fixtures.
- Correction to the round-2 note on the task card: the rule also removes the card from W-2009 (F-17) and W-2208 (F-21), which are behaviour fixtures and not board pages. Both keep their decision link (step with `task_id`) and their suites pass.

## Fixes
- UI-2-1 | 7abfbcb94384c4380adf6bb289961f547c735e98 | date cells with amber Unknown restored; "13 Nov" through a frame column option
- UI-2-2 | 7abfbcb94384c4380adf6bb289961f547c735e98 | DRAFTED tags in the agent (blue) tone
- TECH-2-1 | 7abfbcb94384c4380adf6bb289961f547c735e98 | guard covers items[].values and columns[].date_format

## Validation
- bash delivery/checks.sh: exit 0.
- Playwright (4761/4762): minutes, workspace, weekly, weekly-returned-received: 105 passed.
- vitest: minutes.test.tsx 43 tests; mock-contract and minutes-mock pass.
- Single-board fidelity run (round-3/fidelity/scores.txt): SCR-28-desktop 1440 coverage 100 after exceptions, visual 69.1 (the D-104 one-board exception, no fixable gap known); SCR-28-mobile 390 coverage 100, visual 74.2. The other six boards were not re-run; round-2 scores stand (81.3, 85.4, 78.7, 82, 82.5, 78.7). The DRAFTED tone change could move the two drafted and two review boards slightly.
- Servers stopped by PID; test-results deleted.

## Verified
- UI-2-1 | verified | test: Due is a date column; A-3 is `date: {unknown: true}` and draws the Unknown value (class psl-unknown); "13 Nov" with the option, "13 Nov 2026" without it. Fidelity desktop 69.1, phone 74.2.
- UI-2-2 | verified | fixtures: DRAFTED tags are `agent` tone.
- TECH-2-1 | verified | mock-contract test "items[].values and columns[].date_format appear only in W-23xx fixtures".

## Base merge
The coordinator merged dlv-00 into the branch (head a3f43067bf20e8474e3a6bb54d273597154d6f28); I checked that `git diff --stat 7abfbcb9 a3f43067 -- frontend` is empty, so no frontend change and the round-3 evidence stands. My last own commit was 7abfbcb94384c4380adf6bb289961f547c735e98.

## Sign-off and note tone
- Merged origin/dlv-00-delivery-setup (delivery records only), then committed 2e5eab9e7453da8eae518308537eb91140cef6ee.
- D-105: every entry and visual waiver in `fidelity-exceptions.json` that said "builder proposal, pending design engineer" now reads "design engineer, 16 Nov 2026 — D-105" (no pending entries remain). The waiver text no longer calls the desktop default an open decision.
- Tola's third sentence (the part asking the PM to act) is amber, chosen by data. The frame had no way to tone one line of the agent note (its only amber line is a separate untitled section note, which sits in the main column). Smallest general addition: fixtures-only PROPOSAL `agent_note.warn_lines: [indexes]`, read by `warnLines` in `proposals.ts`; `AgentNote` draws those lines in a warning Callout under the info note. Nothing matches on the words. Without the key every line is drawn in the info note as before. Fixtures W-2301, W-2306 (+ .next), W-2307, W-2308 carry `warn_lines: [2]`; the contract test validates and strips it, and the "only in W-23xx" guard covers it. Component test covers flagged and unflagged.
- Fidelity, single board SCR-28-desktop default (1440, round-3/fidelity/SCR-28-desktop-1440-signoff): coverage 100 after exceptions, visual 65.3, down from 69.1. It does drop. Cause: the amber line now is a full-width band under Tola's note, where the board puts it in the right column under Tola's card (a frame layout item, Conflicts 6); a first try as a section note in the main column scored 62.8 and 65.5, so I used the note band. The other seven boards were not re-run; only the four default-view fixtures changed, and the phone default may move too.
- Validation: checks.sh exit 0; Playwright minutes, workspace, weekly 88 passed (an earlier run had one W-2006 390 timing flake under load that passed on re-run); servers stopped by PID; test-results deleted.
