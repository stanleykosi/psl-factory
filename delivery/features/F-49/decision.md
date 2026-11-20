RECOMMENDATION: ESCALATE
COMMIT: 139eceeb05c331741f89d45b9b995c5175ca1fa0
APPROVER: approver

## Summary
- F-49 adds the "Log a received RFP" line to the Start work drawer (SCR-23, desktop and phone) on the contract mock. The person uploads the RFP document, submits once, and lands on the new RFP in Unassigned for F-36's assign panel.
- Gate, technical, UX, UI (under D-131), QA and PMO acceptance all PASS on this head, with no blocking finding open. The diff is 19 files, all inside readiness Scope and the spec's lanes.
- Risk is medium (client-bid work item, append-only evidence to a shared case, contract-change overlays), and product acceptance is required by readiness. Nothing real is written; the backend gaps G-23-1 to G-23-6 are in the handoff.
- Open items are the design engineer's: 24 unsigned fidelity exceptions, confirmation of the D-131 waiver and phone floor exception, QA-2-1, and product acceptance.
- Before the PR: set `operation_ids` (PMO-2-1).

## Why
The work is sound and evidenced, but fidelity is not at the gate on either board and the exceptions are builder proposals. Product acceptance is a person's call. A merge by the factory would skip both.

## Acceptance criteria
1. Line drawn from data (AC 1): met, component test and QA at both widths; the new code adds no board strings (three old comments in other features contain "Tamarind").
2. Nobody but the grant sees it (AC 2): met, mock test; no persona or roles read in start-work.
3. Clients from the backend only, New client only under the overlay (AC 3, 4): met; QA saw three clients and no New client row.
4. Deadline three values, `show_when` (AC 5, 6): met; QA saw Unknown send no `deadline_at`.
5. Phone matches desktop, 44px targets (AC 7, 17): met per UX and UI reviews, e2e 10 of 10.
6. Upload when chosen, one start, Unassigned count (AC 8, 9, 10): met; QA saw 1 upload, 1 start despite a double click, count 6 to 7.
7. No browser rules, stale, uncertain, access, plain text, unknown never 0 (AC 11 to 16): met in tests; QA exercised 403, 409, 500, uncertain with Check again.
8. Fidelity (AC 18): not met until signed. Desktop 86.5 coverage and visual 74.2; phone 78.3 and visual 59. The waiver and floor exception are accepted under D-131; the 24 exceptions are not signed.
9. Accessibility, tokens, mock matches contract, contract not extended, existing tests green (AC 19 to 23): met; I spot-checked the diff for hex, rgb( and `accept=` and found none; gate PASS on this head.

## For the human
Please decide:
1. Sign the 24 exceptions in fidelity-exceptions.json (9 frame, 8 sample data, 5 claim, 1 component, 1 words), all "builder proposal, pending design engineer". The UI reviewer asks that the phone exception name the Deadline versus Submit-by order swap and the wording differences (conflicts 5, 7).
2. Confirm at sign-off the desktop D-83 waiver (visual 74.2) and the phone floor exception (visual 59), both already accepted under D-131.
3. QA-2-1: an empty "Log RFP" press sends one start with `intake: {}` and the mock's 422 shows the required messages. The spec says nothing is sent. The cause is F-05's shared behaviour, and it is harmless on the mock. Accept it as a follow-up (the PMO pass leans this way), or have it fixed first, which touches every line and needs a new round.
4. Product acceptance (required): logging an RFP as a new client flow, and the held items: no new-client write, no claim of a separate case, deadline kept as Unknown, Stated and Not stated.
5. Set `operation_ids` to E-LINES, E-LINE-OPTIONS, E-EVIDENCE-UPLOAD, E-WORK-START, E-ME, E-WORK-ITEM before the PR.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-49/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-49/round-2/acceptance-pmo.md
- /Users/Hunchoo/psl-factory/delivery/features/F-49/round-2/review-qa.md
- /Users/Hunchoo/psl-factory/delivery/features/F-49/round-2/review-ui.md
- /Users/Hunchoo/psl-factory/frontend/src/features/start-work/useStartWork.ts (submit, around line 337, in the F-49 worktree)
