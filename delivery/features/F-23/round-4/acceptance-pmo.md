VERDICT: CHANGES
COMMIT: 778e868137d79b0b808b55c5c994c7345613d586
REVIEWER: pmo-acceptance
AUTHORITY: delivery PMO acceptance

## Summary
- Delivery evidence on this head is complete: round-4 gate PASS (checks.sh exit 0), merged-head `merge-checks.log` (1952 tests) and `merge-e2e.log` (116 passed), and PASS from technical, security, UX, UI and QA on 778e8681.
- Scope holds. Task FE-LINE-MINUTES is covered by the 8 boards in readiness (default, suggesting, drafted, review, each at 1440 and 390). The internal and published boards stay out (F-23b). The feature has no operation IDs. The endpoints in readiness (E-WORK-ITEM, E-WORK-STEP, E-LINE-OPTIONS, E-TASK-CLAIM, E-TASK-DECIDE, E-WORK-ACTION, E-DOCUMENT) were exercised on the contract mock by QA.
- All blocking findings are VERIFIED: UX-1-1, UI-1-1..1-4, UI-2-1, QA-3-1. The other findings are non-blocking and OPEN, or VERIFIED. None is an accepted risk.
- Design-engineer sign-offs match `fidelity-exceptions.json`: 36 exceptions cite D-98 or D-105, and 8 visual waivers cite D-105 or D-106 at the measured scores (65.3, 81.3, 85.4, 78.7; phone 70.2, 82, 82.5, 78.7). Nothing is pending.
- One blocking gap: `delivery/BACKEND-HANDOFF.md` has no F-23 section (PMO-4-1). Delivery acceptance only; client acceptance, merge and release keep their own authorities. Everything stays on the contract mock under the D-LINE-WORKSPACE limits (proposed, nothing released, test template, no real send).

## Checks
- **Criteria evidence.** `review-qa.md` shows live evidence on this head for default, pre-ticked, exact confirm set, edit/remove/add, stale 409, 500 retry, suggesting, drafted, open-the-minutes, review, return-note at 1440 and 390, uncertain lock at 1440, 390 and 320, 401/403/404, personas, unknown and restricted, and notes-grant-nothing. Component and e2e runs are in the merge logs.
- **Fidelity.** Round-3 `scores.txt` lists only 69.1 and 74.2 for the two default boards. The signed scores (65.3, 70.2) are in the `-signoff` report.json files and in `fidelity-exceptions.json`. The other six boards stand on round-2 scores. Round 4 made no fidelity run, which the builder justified: no scored board shows the uncertain done view. This is acceptable under D-64.
- **D-98 / D-104 / D-105 / D-106 against the file.** D-98 covers Conflicts 1 to 5 and 3 (the Note box and the "Keep this decision" name). D-105 covers the frame and phone-rendering entries and the visual waivers. D-106 covers the 65.3 and 70.2 default waivers. D-104's 69.2 exception was superseded by D-106, which the file reflects. No exception covers a value the data can supply.
- **Contract-mock limits.** build.md states the D-LINE-WORKSPACE limits, calls the template a test template and claims no real backend, idempotency or working line. QA states what is not proved (no real backend, send or recipients; no PMO Lead persona, decisions taken as `pm`).
- **QA-3-1 shared decide change.** It was authorised by the coordinator as a general correctness fix. TECH-4 checked it: `UncertainNotice` was moved, not copied; F-16 tests were only added to, and none was weakened or edited. Two new component tests and the e2e W-2305 at 3 widths cover it. QA re-ran `decide`, `minutes`, `minutes-mock` and `mock-contract` (369/369). A normal approve (W-2304) is unchanged. In scope as a bounded exception to the "no shared change" rule.
- **Parent package.** build.md claims no more than the mock slice. Nothing in the F-23 record marks FE-LINE-MINUTES, the minutes line or the A-WORKSPACE backend half as done.

## Findings
- PMO-4-1 | blocking | medium | pmo | `/Users/Hunchoo/psl-factory/delivery/BACKEND-HANDOFF.md` has no F-23 section. A search for `items_default`, `G-SCR28`, `warn_lines`, `date_format` and `test_template` finds nothing in it. Only the priority list mentions SCR-28 in passing (lines 60, 70, 76). Without it the backend developer does not receive the F-23 contract proposals. Fix: add an "Added during F-23: the minutes line (17 Nov)" section in the style of the F-22 and F-26 sections. It names SCR-28 default, suggesting, drafted and review (W-2301 to W-2308 on the mock), says it is contract mock only and every item is additive and may be renamed or refused, and lists the items below.
  - **Contract proposals**
    - `steps[].items_default: "checked"`, with `item_ids` covering the kept decisions and all remaining actions (G-SCR28-1).
    - `items[].values`, the per-item prefill for Edit forms (TECH-1-2, UX-1-1), with the list-of-values shape for owner.
    - `columns[].date_format`, so the table can draw "13 Nov" instead of "13 Nov 2026" (UI-1-5).
    - `agent_note.warn_lines`, so the amber "needs you" sentence is data and not the third sentence of the note (UI-1-6, D-105, D-106).
    - `workspace.links[]` `{key, label, target kind}` and `link.action_id` in cells and cites (G-SCR28-3). "Open the minutes" works today through `version.document_id`. "Ask Tola" and "Open actions" are not provided.
    - E-DOCUMENT `test_template`, which the minutes view and the "Test template" tag read.
    - Meeting, action and decision records: REC-MEETING, REC-ACTION and REC-DECISION are not in model.json, and where meetings come from is open (G-SCR28-6). They are in the priority-list line 76 but need their own entry.
  - **Owner options**
    - Owner options per work item: E-LINE-OPTIONS takes `work_id` (G-SCR28-4).
    - Option `hint` ("client", "recorded by PM") with `recorded_by_pm` and `outside_party` stored by the backend from the chosen option (G-SCR28-2).
  - **Item steps**
    - Item-scope steps send `item_ids: [id]` for every line (TECH-1-1). The backend handler for each line must accept or ignore it.
    - The confirm step sends the exact `item_ids` shown with `expected_revision` and a UUID key.
  - **Open questions, one line each**
    - G-SCR28-5: whether audience may change and whether client minutes need review. The step should return the new `steps` and `consequence`.
    - G-SCR28-7: whether actions are created at confirm or at approval.
    - G-SCR28-8: recipients come from client contact records, never from the notes.
    - G-SCR28-9: notes are untrusted. `cites` carries `evidence_id`.
    - D-RETURN: whether a return keeps or reopens the confirmed decisions and actions, and a required note.
    - The uncertain-send reconcile reply (already listed under F-21 and F-22) also covers W-2305.
    - `effect_uncertain` and the refusal to resend are verified on the mock only. Idempotency is a backend promise not yet built. D-ALERT-PROVIDERS gates a real client send.
    - The client template is a test template until PSL supplies the real one.
  - **Frame/UX asks**
    - Shared decide page: "Paid is tracked separately by Finance…" shows on a minutes approve (QA-3-2). Approve v1 / "Approve and send" wording (UX-1-3).
    - A phone note box on the review board (the design engineer signed that the note is entered on the F-16 page, D-98).
- PMO-4-2 | non-blocking | low | pmo | `delivery/features/F-23/round-3/fidelity/scores.txt` still lists 69.1 and 74.2 (UI-3-2, still OPEN). The signed 65.3 and 70.2 are only in the `-signoff` report.json files and in `fidelity-exceptions.json`. Fix: add the two rows to the file. The six other boards have rows only in round 2.
- PMO-4-3 | non-blocking | low | pmo | The OPEN non-blocking findings travel with the feature as follow-ups: QA-3-2 and QA-4-1 (wording on the decide pages), TECH-1-1, TECH-1-2, TECH-4-1, TECH-2-2, UX-1-2..UX-1-8, UX-2-1, UI-1-5, UI-1-6, UI-2-3, UI-3-1, UI-3-2, SEC-2-1, SEC-3-1, UX-4-1, UI-4-1. None is an accepted risk and none needs one. Fix: the coordinator keeps them in the follow-up list, and the findings that are really frame or backend asks go to the handoff in PMO-4-1.
- PMO-4-4 | non-blocking | low | pmo | The drafted and review boards were last scored in round 2. The round-3 DRAFTED tone change and the amber line could move them slightly (round-3 build.md says so). The signed waivers cite the round-2 scores. Fix: none required for delivery acceptance. Re-score once if the design engineer asks at product review.

## Verified
- UX-1-1 | verified | state VERIFIED in feature.json, retested live by UX in round 2 and passing again in round 4.
- UI-1-1 | verified | state VERIFIED in feature.json.
- UI-1-2 | verified | state VERIFIED in feature.json.
- UI-1-3 | verified | state VERIFIED in feature.json.
- UI-1-4 | verified | state VERIFIED in feature.json.
- UI-2-1 | verified | state VERIFIED in feature.json.
- QA-3-1 | verified | state VERIFIED in feature.json; QA round 4 re-ran it live at 1440, 390 and 320.
- PMO scope | verified | scope, task coverage and the shared decide change checked as above; nothing outside readiness landed.
