STATUS: READY
COMMIT: eacdc7045a458039ad42eb19ea5852cc411578df
BUILDER: builder
LANE: full

## Summary
- Round 2 restores the board's wording, hints, callouts and the submission control on SCR-23 and SCR-24 wherever the contract allows (UI-1-1 to UI-1-3).
- The Log RFP line now appears in Start work only when `GET /lines` lists it (key `received-bid`); it is no longer added for everyone (TECH-1-1). This also removes the repeated "Lines you can start" heading (UX-1-1). The mock `/lines` now lists it with `can_submit_via_api: false`; `ownsSubmit` still makes it startable.
- The dead `notice` state and callout in MyWork are removed (TECH-1-2).

## Changes
- `src/features/start-work/lines/receivedBid.tsx`: eyebrow "START WORK · PRE-SALE"; info callout "Logging an RFP opens a new pre-engagement workspace for it. The RFP reference can’t be changed later."; labels "Received", "Submit to", "Submission deadline" (options Unknown / Stated / Not stated), date label "Deadline"; "How the client wants it submitted (optional)" is a four-way segmented control (Email, Client portal, By hand, Not stated); hints under RFP reference, Received and Submit to as on the board.
- `src/features/rfp/AssignPmDrawer.tsx`: info callout at the top, "N people can prepare RFPs here" under Accountable PM (from `nominees.length`), and "One of the roles PSL allows to assign RFPs" under the role.
- `LineChooser.tsx`, `StartWorkDrawer.tsx`, `lines/index.ts`: `withOwnLines` and the own-line description removed. `MyWork.tsx`: `notice` removed. `mock/start-live.mjs`: lists `received-bid`.
- Tests updated to the board labels; new assertions for the callouts, hints, eyebrow and no repeated heading.

## Fixes
- UI-1-1 | 506935c4 | SCR-24 callout and helper count built.
- UI-1-2 | 506935c4 | Role helper line built (static copy, shown for one or several roles).
- UI-1-3 | 506935c4 | SCR-23 callout, PRE-SALE eyebrow, labels, segmented submission control and hints restored.
- TECH-1-1 | 506935c4 | own line only when `/lines` lists it.
- TECH-1-2 | 506935c4 | dead notice removed.
- UX-1-1 | 506935c4 | one chooser list, one heading.

## Board differences kept, for the UI reviewer
Batch-accepted (LC-Q7, LC-Q8, LC-Q9, LC-Q17; D-182, D-187): Note replaced by required Reason and Proof required (not "(optional)") on SCR-24; no nominee role or hint and no "alerted" sentence (the "What happens next" block lists served `next_steps`); the client is an organisation picker with an optional "Client name as written in the RFP" and a confirmation tick-box (SCR-23); success shows the receipt and a link, not a work item.
Kept because the contract forces it, not answered in a batch (new board questions):
- NQ-1: SCR-23 client label is "Client" (an organisation picker, existing organisations only). The board says "Client or prospect" with "New client · they'll be added to the client register", which C-9 says the API does not do. I did not draw the new-client hint.
- NQ-2: SCR-23 board shows the Note as "Received from their procurement lead by email." and the deadline hint "Taken from page 2 of the RFP (proof attached)". The contract has no source or proof for the deadline; not drawn.
- NQ-3: SCR-24 gets states no board draws (setup required, no nominees, already assigned, unconfirmed, the upload-or-recorded proof choice with a "checked" tick-box) and the list behind the drawer is the received-RFP list, not the work table. Needs a board.
- NQ-4: the board's submission-method segment cannot be cleared once chosen (optional field); an unchosen method is simply not sent.
- The board's sample values (Tamarind, Tunde Bello) are data, not differences.

## Acceptance criteria
Unchanged from round 1 (all [x]); criterion 20 now reads: Start work lists the received RFP through the registry when `/lines` lists it.

## Validation
- Full `npm test` through the lock on cbccc7a3: 158 files, 3772 tests passed.
- `tsc --noEmit` and eslint clean on changed paths. No new fidelity run (the reviewer asked for one after fixes; I did not run it because the tool needs a rebuild through the lock; SCR-23 still has no URL).
- Live proof stays mock-only (no organisations or grants set up). UX-1-2 (mock Unassigned badge says 2, list serves 13) is left: the badge comes from the v7 `/work` counts and tests expect 2; live `/work` has no counts.

## Coordinator note (lane C, 24 Nov)
Head moved from the builder's cbccc7a3 to eacdc704 only by the coordinator merging origin/main 8692cf87 (D-199 CI gates and other lanes' merges). One allow-list conflict in tests/next-config.test.ts: main's entries kept, received-bids.mjs added. Gated on GitHub Actions under D-199.
