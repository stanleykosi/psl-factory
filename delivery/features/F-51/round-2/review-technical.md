VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: b50b0b7ca04b9583c63fbe723de49d90aebbd987
AUTHORITY: delivery technical review

## Summary
- The shared required check reads each field's `required` flag from the line data (emptyRequired in intake.ts); no line key or field name is hard-coded. Hidden (show_when) fields are skipped, evidence counts confirmed ids.
- An empty press sets field errors, focuses the first field and returns before building the body, so nothing is sent. The server 422 path is intact (422 callout, Proof-under-box and unmatched-problem tests remain and use filled forms).
- F-05, F-47 and F-49 tests changed to the new contract; assertions were replaced, not loosened, and each family has a new empty-press test. Two old 422-specific assertions were dropped (see TECH-2-1).
- Layout pair, Optional line, select and Audience default are keyed by line key or field data, so other lines are unchanged.

## Findings
- TECH-2-1 | non-blocking | frontend | The reworked F-05 test no longer asserts "Start greyed after a 422 until a change" or "a new idempotency key after a 422". The awaitingChange code is still there, and the 409 test covers the new key, but the greyed-after-422 case is no longer covered. Add one assertion to the 422 billing_contact test. frontend/tests/start-work.test.tsx:501.
- TECH-2-2 | non-blocking | product | Audience default uses field-level `value` naming an option; the contract has no choice-default field. Builder flagged it; the coordinator should define it. frontend/src/features/start-work/useStartWork.ts:defaultChoices.

## Verified
- TECH-1-1 | verified | Criteria 3 and 6 now met in behaviour: Start stays enabled, the press names each empty required field and sends nothing (tests in start-work, start-work-proof, rfp-intake and ppe-forecast; e2e forecast and invoice). The spec amendment is no longer needed.
- Item 2 (nothing sent) | verified | tests assert starts/posts length 0 after an empty press, and the next press after a change sends exactly one.
- Item 5 (tests fail without the fix) | verified | by reading: the new assertions (posts 0, focus on first field, error text) cannot pass if submit sends, since the old code sent and the mock returned the 422; the "no default names none" and sample-note tests depend on the new code paths. I did not re-run with the fix reverted.
- Checks | verified | round-2/checks.md passed on this head.
