VERDICT: CHANGES
COMMIT: 86aefc6d97a27dcb0f7c0801c9edce099038752d
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- The contract now points to v4 in all four places. The types derive from the regenerated schema, `architecture/**` is untouched and no `v2-reviewed` reference remains.
- Claim and decide match spec.md: claim once per task id + revision, decide with the claim's revision, CSRF from the shared middleware, a note only when it has text, and never `revoke` or `evidence_id`. A 409 never resends; it reloads once and compares. Eligibility comes only from `you_can_act` and `cannot_act_reason`.
- Amounts are formatted from the decimal string. Unknown is never 0, and the amount pattern matches the v4 schema exactly. The client never builds an approver, a chain or an amount itself.
- One blocking problem. When a decide fails with a network or server error and the reload that follows also fails, the old version's controls come back without anyone checking whether the decision was recorded.
- The mock's checks follow the spec order, apart from one documented change (revision is checked before eligibility). The tests are thorough and include negative cases; no existing test was weakened.

## Findings
- TECH-1-1 | blocking | medium | frontend | Uncertain effect left unreconciled when the reload fails. Expected (spec "Network or 5xx is an uncertain effect", AGENTS.md "reconcile uncertain effects before retrying"): the controls come back only when the reloaded task is still actionable at the same revision. Actual: `frontend/src/features/decide/useDecision.ts:184-186` sets `submit` to idle and then returns early when `reload()` gives a non-access `ApiError` (network, 5xx or 403). The view stays `{kind:'item'}` on the pre-decide item, and the claim stays `ready` under the same key. So Approve/Return/Reject are enabled again on a version whose decision may already be recorded. The notice beside them also says "We've reloaded this item", which is not true here. A 403 on that GET is not treated as lost access either (`ACCESS_LOST` holds only unauthenticated and not_found). Fix: when the reload fails, do not re-enable the controls. For example, show the load error card, or the no-access view for 403/404 (as `toStale` already does at lines 78-81), so that Try again re-reads the item first. Add a test in which the decide and the reload both fail, asserting that no enabled decision control remains.
- TECH-1-2 | non-blocking | low | frontend | The done view turns an unexpected verdict into "approved". `frontend/src/features/decide/DecideStates.tsx:221`: `result.verdict in VERDICT_WORDS ? result.verdict : 'approve'`. If the response echoes anything other than the three verdicts (the contract types `verdict` as a plain string), the page shows "<label> is approved", the success callout and the Paid line. Use the verdict the client sent, which `decide()` already knows, rather than defaulting to approve.
- TECH-1-3 | non-blocking | low | frontend | After an uncertain effect, the stale check compares against the item's revision, not the claim's. `useDecision.ts:188` tests `now.revision !== task.revision`. Under the spec's assumption that the backend may bump the revision on claim, an undecided task reloads at the claim revision and is shown as "A newer version arrived" with the same version number on both sides. It is safe, but it is the wrong view. Compare with `claim.revision` instead.
- TECH-1-4 | non-blocking | low | frontend | build.md "Not built" says "`revoke` … The mock returns 422 for it". The mock (`frontend/mock/server.mjs`, `taskResponse`) returns 422 only when the note is missing or blank. With a valid note it returns 501 `not_mocked`, as spec.md requires and `mock-decide.test.ts` "revoke with a note is not mocked" asserts. Correct the report.

## Notes
- The departure that puts revision before eligibility (`server.mjs`, the 409 before the 403) is needed for criterion 16 and is documented for T-DECIDE. I accept it.
- `compareRows` adds a third mark, "still unknown", when both amounts are unknown. The spec names only unchanged and changed. It keeps INV-UNKNOWN, which I prefer, but it is a copy change for product or UX to confirm.
- The coordinator's integration commit renumbers F-02's PM sample rows in `E-WORK-LIST.rows.json` to W-1301..W-1305. It is an integration-owner edit to an F-02 fixture, it is recorded in build.md, and PR #8's row-to-item guard still passes.
- Work-item imports (`FactsStrip`, `NoAccessState`, `WorkErrorCard`, `labels`) are read-only. The only edit to F-03's mock handler is the one-line override hook.

## Verified
None (round 1).
