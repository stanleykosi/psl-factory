VERDICT: PASS
COMMIT: f39d6dda8b095d99f19a3f9c809a2c97b71eba27
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- TECH-1-1 fixed: a 422 the page cannot place now shows as a Callout in both forms; the misleading "Check the highlighted fields." is gone. Owner has its own error on the action form.
- TECH-1-2, 1-3 and 1-4 fixed in code. A failure after the 201 is "not confirmed" with a re-read. An unconfirmed create re-reads the list and detail. A 401 shows the sign-in link.
- Merge f421b8e6 is clean. Against main 8692cf87, `mock/server.mjs` (+12) and `src/api/types.ts` (+9) have additions only and no removed main lines, so F-85, F-86 and F-72 are intact and the F-119 routes and aliases are kept.
- TECH-1-5 is left as a question for the design engineer ("saved" or "held"); it does not block.

## Findings
None.

## Verified
- TECH-1-1 | verified | `failure.ts` keeps unmapped fields under `other`. `generalMessage(failure, drawn)` returns the loose messages, or the API message when no field is named. `FailureNotice` draws it in `RetroForm` (DRAWN: reference, occurredAt, boxes, evidence) and `ActionForm` (DRAWN includes ownerId, dueAt). `tests/retrospective-failure.test.ts` covers the empty-fields, unmapped-field and owner cases. The builder reports two e2e tests as well.
- TECH-1-2 | verified | `useRetrospective.ts:save` sets `posted` after the 201. A later failure maps to `failureOf(networkError())`, which is unconfirmed, and re-reads the list. Save stays off until the read shows the result. It never says "Try again shortly".
- TECH-1-3 | verified | `createAction` re-reads the list and detail on `unconfirmed` and `stale`, with a "check the follow-up actions below" message.
- TECH-1-4 | verified | `FailureNotice` renders `SignedOutState` for `signed_out` in both forms.
- TECH-1-5 | open question | The date shown is the meeting's `occurred_at`. The spec says "saved" and the e2e asserts it. The design engineer decides; not blocking.
- TECH-1-6 | verified | The builder reports `e2e/retrospective.spec.ts` at 24 of 24 after the toast change. I did not re-run it. Criterion 21 (live Django) is still unchecked; QA on 55433 should cover it.
- Not run by me: no tests. I read the code and the diff against main. The GitHub gate passed on f39d6dda (D-199).
