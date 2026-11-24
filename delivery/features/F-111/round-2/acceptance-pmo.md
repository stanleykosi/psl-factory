VERDICT: PASS
COMMIT: 8a5c09fe624b12c209c2a70cb1f75c8a38238586
REVIEWER: pmo-acceptance
AUTHORITY: PMO delivery acceptance, round 2 (delivery acceptance only; client/product acceptance, merge and release keep their own authorities)

## Summary
- Scope held: the nine changed files (e2e, mock, adapter, model, `LiveWorkItemView.tsx` one-line import, three test files) are all issue-followup read work for FE-CONNECT-1 (SCR-30). No write, no `workspace` change, no other feature's files. The feature has no operation IDs.
- No blocking finding is open. Round 1's blocking findings are VERIFIED (TECH-1-1, UI-1-1, UI-1-2) or ACCEPTED_RISK under named authority (TECH-1-2, UX-1-1, UI-1-3, UI-1-4 under D-202, which is in `delivery/OVERNIGHT-DECISIONS.md` at line 550). UI-1-5 and UI-1-6 are accepted under D-203 (line 561), and `fidelity-exceptions.json` holds the 57 exceptions and eight D-83 waivers.
- Gate PASS on 8a5c09fe (round 2 attempt 1). Technical, UX, UI and QA passed on the same head. Product acceptance is recorded in `round-2/acceptance-product.md` under D-184, with the stated limit that it is a batch acceptance and not a fresh screen review.
- QA-2-4, the missing live issue journey, is acceptable for this read-only line before the demo. It is not acceptable to leave it unnoticed. See PMO-2-1.
- Parent status: nothing in the round files claims more than this slice. Writes stay with F-111B and the per-section Try again, banner tone, link-capable fact and next-step fixes stay with F-95.

## Judgement on QA-2-4 (live proof)
- Read-only, no money, no identity data, no messages sent. A wrong page here misleads a reader but cannot change a record.
- The mock fixtures are Ajv-checked against the 1.26.0 contract (`tests/mock-issues-live.test.ts`, 12 of 12). Live sign-in, `/me`, `/projects` and `/work` return 200 on the live Django. Only the issue follow-up, detail and messages shapes are unproved against real data.
- The demo risk is the first real issue showing a field or state the mock does not (for example a null timeline kind or a live-only field). The page degrades to the generic error box. It does not give wrong data silently, because unknown values map to "Not recorded" and no write path exists.
- The fix is cheap. Seed one project issue on the demo database, start a follow-up with `POST /work` on `pmo-issues/v1`, and open the page. A run-through of the seed is a demo-readiness step for the integration owner. It does not need another build round.

## Criteria against evidence
- AC1 to AC8, AC10 to AC14, AC16, AC18: passing on the mock per `review-qa.md` (5101 to 5108, scenario cookies, both widths, only GET requests). AC1 differs in one place: Go-live is plain text, not a link (TECH-1-3, accepted under D-202).
- AC9 and AC11: partial by design. Nothing is drawn for write controls, and the failure copy is a reload message with no per-section Try again (accepted under D-202; UX-2-1 asks for the spec text to be corrected).
- AC15 (polling with fake timers): not covered here. Polling belongs to F-85's `PanelView`; TECH-1-6 stays open and is non-blocking.
- AC17 (live comparison): not proved. See PMO-2-1.

## Findings
- PMO-2-1 | non-blocking | medium | integration | AC17 and the live journey are unproved (QA-2-4): the local database has no project issue and no seed was run. The authority is D-203 and the product acceptance's "Not covered" note. Before the demo, seed one issue, start its follow-up work item and compare the page with the three live reads for reference, severity, status, age, owner, timeline row count and message count. Record the result in `BUILD-TESTS.md` or the merge batch. If the live page disagrees, raise it as a fix and do not hide it.
- PMO-2-2 | non-blocking | low | frontend | Open non-blocking findings travel with the merge and need an owner so they are not lost: TECH-1-6, TECH-2-1, UX-1-6, UX-2-1 (spec text for AC9), UX-2-2, UI-2-1 (exception name "" for the side panel), UI-2-2 (add a "NEXT" exception), UI-2-3, QA-2-1 to QA-2-3. UI-2-1 and UI-2-2 are changes to `fidelity-exceptions.json` for the design engineer. QA-2-1 (a 404 on only the detail or messages read replaces the whole panel) is the most visible and belongs with F-95.

## Verified
- TECH-1-1 | verified | per technical round 2: `issues.mjs` serves `django_url`, the Ajv contract test passes.
- UI-1-1, UI-1-2, UX-1-2, UX-1-4, UX-1-5, TECH-1-4, TECH-1-5 | verified | per the round-2 technical, UI and QA files.
- TECH-1-2, TECH-1-3, UX-1-1, UX-1-3, UI-1-3, UI-1-4 | accepted risk | D-202 names the authority (design engineer), and its text is a real decision in `OVERNIGHT-DECISIONS.md`.
- UI-1-5, UI-1-6 | accepted risk | D-203 ("Sign all", LD-Q7), signed in `fidelity-exceptions.json`.
