VERDICT: PASS
COMMIT: 3c93fe030ff5ac81da343dc7a0917820c8803d7b
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- SEC-1-1 is fixed. When a decide's effect is uncertain and the reload after it also fails, the new `unconfirmed` view keeps Approve, Return and Reject disabled. `decide()` still refuses anything except the `item` view, and Try again sends only a GET.
- SEC-1-2 is fixed. The done view checks the echoed verdict with `Object.hasOwn`. Any value other than the three shows a neutral "Decision recorded" and never "approved".
- Round 2 did not weaken CSRF. `src/api/` and the shared client are unchanged since round 1, and every write still carries `expected_revision`.
- The no-resend rule still holds. No code path sends a second decision without a new tap on an enabled button. The cannot-act, 403 and stale views still have no controls, and a 401, 403 or 404 on the reconcile read now replaces the whole page.
- No new packages, secrets or raw HTML. The only fixture change is a display name added to W-1206.

## Findings
None.

## Verified
- SEC-1-1 | verified | useDecision.ts:126-141: `reconcile()` catches a failed read. A 401, 403 or 404 goes to the `error` view (signed-out or no-access, no controls). Any other failure goes to `unconfirmed`. The controls come back only when the reloaded task is actionable at `claim.revision`; a different revision shows the stale view. useDecision.ts:186: `decide()` returns early unless `view.kind === 'item'`. DecidePanel.tsx:32: `locked` disables all three buttons. useDecision.ts:172: the claim effect runs only in the `item` view, so the unconfirmed view sends no claim. useDecision.ts:144-148: `recheck()` calls `reconcile()` only, which is one GET. The UnconfirmedNotice (DecideView.tsx:31-44) no longer says the item was reloaded. Unit test "decide network error and a failed reload keep every control off; Try again only reads the item" asserts the disabled buttons and that the only POSTs were claim and decide. The builder also reports an e2e test with the same POST-count check. When the reconcile read succeeds after the claim moved the revision (for example 2 to 3), the page claims again at revision 3 before the buttons come back. A claim records no decision, so this is safe.
- SEC-1-2 | verified | DecideStates.tsx:219-225: `Object.hasOwn(VERDICT_WORDS, result.verdict)` gates the words. An unknown or inherited key falls back to `RECORDED`, and `approved` requires a known `approve`. A unit test echoes `constructor` and asserts the neutral wording, and that the page does not say "approved".

## Notes
- Unchanged from round 1 and still non-blocking: the mock's `/__mock/reset` has no CSRF or Origin check, and might be reachable through a `%2e%2e` path on the dev proxy. It affects local mock state only and never a production build pointed at Django.
- Real Django session, CSRF, grant enforcement and the backend's revision and eligibility order are still unproved by this frontend-against-mock round. They belong to T-DECIDE and FE-CONNECT-1.
- I reviewed the code only. I did not call the shared app or mock, and did not run the test suites. The test results above are from the builder's report and the test source.
