VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: 8779c5f30c05ed760fc1cbfe3a2dddf790daca1e
AUTHORITY: delivery security review

## Summary
- The fix round adds no write path, endpoint, dependency, HTML sink or permission change. The changes are one display condition (it hides the "See all exceptions" link on `fixed_assets`), scoped CSS, fixture wording and facts, and tests.
- Decide still runs only through F-33's `InlineDecide`/`useDecision`, with `you_can_act`, the claim, CSRF and `expected_revision` unchanged. The claim is sent on load, only while `you_can_act` is true, as F-33 spec.md:96 and F-42 spec.md:145 require. No claim is sent where you cannot act (W-3905, W-3906, W-3912 and the holds, as before).
- No money rule changed. There is no arithmetic, and Unknown is not shown as 0.
- Vitest at 8779c5f30c05ed760fc1cbfe3a2dddf790daca1e, run one file at a time: asset-schedule 37, asset-schedule-mock 11, income-schedule 44, income-schedule-mock 8, work-item 46, work-item-board 81, workspace 37, workspace-step 47, workspace-mock 7, all passed. A first combined run under load average 30 to 150 timed out in work-item-board and the *-mock files failed to start; each of those passed when run alone, and none of them is touched by this diff.

## Findings
None.

## Verified
- Round-1 security PASS carried forward. The diff does not touch any surface that review covered: auth, CSRF, the claim, decide or the API client.
