VERDICT: PASS
COMMIT: 3c93fe030ff5ac81da343dc7a0917820c8803d7b
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- All four round-1 findings are fixed. If a decide fails with a network or server error and the reload after it also fails, the decision buttons now stay off. Try again only re-reads the item and never sends the decision again.
- When the reload after an uncertain decide answers 401, 403 or 404, the page is replaced (signed-out or no-access view). It no longer leaves the old version open for a decision.
- The done view no longer turns an unexpected verdict into "approved". The stale check after an uncertain decide now compares against the claimed revision.
- This round changes only the decide feature, its tests, the e2e suite and the W-1206 fixture. No existing assertion was removed or weakened: the one changed return-view assertion is now stricter.
- I found no new problems. Two small points are under Notes: a spec line the coordinator should update, and new copy for product to confirm.

## Findings
None.

## Verified
- TECH-1-1 | verified | `useDecision.ts:126-141` `reconcile()`. A failed reload after an uncertain decide gives `unconfirmed` for network/5xx errors, and the error view for the `NO_ACCESS` kinds (unauthenticated, forbidden, not_found). The view renders SignedOut or NoAccess (`DecideView.tsx:51-54`). `decide()` (line 186) still requires `view.kind === 'item'`, and `DecidePanel` gets `locked` (`DecideView.tsx:121`, `DecidePanel.tsx:32`), so all three buttons stay off. `recheck()` (144-148) only calls `reconcile`, which is one GET. The controls come back only through `reconcile`'s success path. "We've reloaded this item" is replaced by `UnconfirmedNotice` in this state. Tests: decide.test.tsx "decide network error and a failed reload keep every control off; Try again only reads the item". It asserts the buttons are disabled, the second GET fails, and the only POSTs are one claim and one decide. There are also "Try again leading to a recorded decision shows the already-decided view" and the 403/404/401 `it.each`. The e2e double-failure test uses `page.route`. All are in the passing gate (checks.md: 319 unit tests).
- TECH-1-2 | verified | `DecideStates.tsx:222-224`. `Object.hasOwn(VERDICT_WORDS, result.verdict)` decides whether the verdict is known. Unknown echoes get "DECISION RECORDED" / "Decision recorded on <label>", the neutral banner and an info callout, with no Paid line. The test uses the inherited key `constructor` and asserts no "approved" wording.
- TECH-1-3 | verified | `useDecision.ts:137` compares `now.revision !== revision`, and `decide()` passes `claim.revision` (line 217). Test "after an uncertain decide, the stale check compares with the claimed revision": the claim returns rev 3, the reload shows rev 3, no stale view appears, and the next decide body is `expected_revision: 3`.
- TECH-1-4 | verified | round-2 build.md "Not built" now says 422 for a missing or blank note and 501 `not_mocked` for a valid note. This matches `frontend/mock/server.mjs` and `mock-decide.test.ts` as checked in round 1. The mock is unchanged this round.

## Notes
- spec.md:143 still says Approve uses `psl-btn--confirm`. This head uses the default `psl-btn` (UI-1-1, the SCR-03 boards). The builder flagged this. The coordinator should update the spec line so that the spec and the code agree.
- The unconfirmed copy ("We couldn't confirm whether your decision was recorded. We also couldn't reload this item…") is new and goes beyond the uncertain-effect sentence in spec.md:106. So does the neutral banner for return, reject and unknown verdicts. Both are safe, and they are for product or UX to confirm.
- When the backend moves the revision on claim, the reconciled item view has a new claim key (`task:3`), so one more claim is sent at that revision. This follows "claim once per task id + revision" and is not a resend of the decision.
- The `architecture/` and `delivery/` changes in base..HEAD came from the merged delivery-setup branch (12897aa, c877daa), not from this round's builder commit.
