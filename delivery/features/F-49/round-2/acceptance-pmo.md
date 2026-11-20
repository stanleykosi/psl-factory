VERDICT: PASS
REVIEWER: pmo-acceptance
COMMIT: 139eceeb05c331741f89d45b9b995c5175ca1fa0
AUTHORITY: delivery PMO acceptance

## Summary
- F-49 delivers the "Log a received RFP" line in Start work (SCR-23, desktop and phone) against the contract mock only. It lands on /work/W-3351, Unassigned for F-36's assign panel. Nothing is released and no real write exists.
- Gate, technical, UX, UI (under D-131) and QA all name head 139eceeb. The diff against base 4fc80166 is 19 files, all inside readiness Scope and the spec's lanes (start-work feature, mock fixtures and proposals, two test files, one e2e, BACKEND-HANDOFF). No change in api, components, shell, apps or architecture.
- Closed blockers: UI-1-1 and UI-1-2 (verified), UI-1-3 (verified), TECH-1-2 (verified). UI-1-4 and the phone floor are accepted risk under D-131. No blocking finding is open.
- Open and not blocking: QA-2-1, UX-1-1, UX-1-2, UI-1-5, TECH-1-1, TECH-1-3, TECH-1-4.
- Not proved: a real backend (new client, shared-case contention G-23-5, duplicates). These are recorded for the backend developer in BACKEND-HANDOFF.md.

## Findings
- PMO-2-1 | non-blocking | low | coordinator | `operation_ids` in feature.json is empty. Set it to E-LINES, E-LINE-OPTIONS, E-EVIDENCE-UPLOAD, E-WORK-START, E-ME (readiness lists these five) and add E-WORK-ITEM, which the landing page reads. Do this before the PR.
- PMO-2-2 | sign-off | medium | design engineer | Fidelity (criterion 18) is not met as written: desktop coverage with exceptions 86.5 and visual 74.2; phone 78.3 and visual 59. The desktop D-83 waiver (UI-1-4) and the phone floor exception (UI-1-1) are accepted under D-131. Still unsigned: the 24 exceptions in fidelity-exceptions.json, all "builder proposal, pending design engineer" (9 frame, 8 sample data, 5 claim, 1 component, 1 words). The UI reviewer also asks that the phone exception name the order swap (board draws Deadline before Submit by) and the wording differences (conflicts 5, 7).
- PMO-2-3 | non-blocking | low | design engineer | QA-2-1: judgement below.
- PMO-2-4 | non-blocking | low | builder | Criterion 1's grep `Tamarind|TL-RFP|procurement@` over frontend/src is not literally empty: three hits are code comments in features/response and features/rfp. They predate this change and the diff adds none. The new code has no board strings.
- PMO-2-5 | note | low | coordinator | Round-2 build.md reports a start-work.test.tsx focus-test flake and says the gate is not green. checks.md for this head reads GATE PASS, attempt 1. Treat as the known flake, fixed by #81.

## QA-2-1 judgement
An empty "Log RFP" press sends one start with `intake: {}`, and the mock's 422 supplies the required messages. Spec line 101 says the required message shows and nothing is sent. Read strictly, that is a breach of the spec text.

The cause is not F-49's code. It is F-05's shared behaviour (required fields are the backend's call; the browser only blocks the empty "New client" name). The fault is harmless: the mock creates nothing, and a real backend should refuse an empty start. It also fits the product rule that the browser does not decide what the backend decides.

My view: it can be accepted for this merge, and logged as a follow-up. If the design engineer wants the text obeyed, the fix is a small required-field check in useStartWork.ts that affects every line, so it needs F-05's tests rerun and probably a new round. That choice is the design engineer's. I do not recommend blocking on it.

## Evidence on this head
- Criteria 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 16: covered by rfp-intake.test.tsx and rfp-intake-mock.test.ts, and exercised in a browser by QA at 1440 and 390 (picker, upload once, double press one start, key, case_revision 6, 403, 409, 500, uncertain with Check again, Unassigned 6 to 7).
- Criterion 7 and 17: UX and UI reviewers measured one column, no overflow, four methods on one row at 390; e2e 10 of 10.
- Criterion 20: I spot-checked the diff of frontend/src. It adds no hex, rgb(, PROOF_TYPES or accept=.
- Criterion 22: diff stat is inside the lanes. Overlays are listed in BACKEND-HANDOFF.md and mock/proposals/rfp-intake.json.
- Criterion 18: see PMO-2-2.

## Handoff
BACKEND-HANDOFF.md has the F-49 section (order of writes, G-23-1 to G-23-6, the deadline state, duplicates, which case). It says what is mock only. It states that "Taken from page 2" and similar board sentences are not drawn.

## Verified
- UI-1-1 | verified | capture now shows the whole sheet; 59 is a measurement of height, accepted under D-131.
- UI-1-2 | verified | six scroll-capture exceptions removed; 24 remain.
- UI-1-3 | verified | one row of four at 390.
- TECH-1-2 | verified | field errors merge.
- UI-1-4 | accepted risk | D-131.
