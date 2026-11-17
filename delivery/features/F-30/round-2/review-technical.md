VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 48ba8f7a6f3cf40c6e185d87dfe9ff4fbabd4c83

Scope: diff 0b69974d..48ba8f7a only.

No findings.

Impact assessment:
- Exceptions bar: the added condition `&& line_key !== 'issue_followup'` is an AND on the existing hasExceptionsLink check, so owner_needed items on every other line still show "See all exceptions". Only the issue line loses it.
- Back link: usePhoneBack changes only when line_key is issue_followup and a project case_id exists. Otherwise it falls back to the old Queue (or history) target, so other lines are unchanged.
- Severity tag: drawn only when a facts item carries severity. Other lines have none, so they are unaffected. Restricted sections are skipped.
- Strip, side note and `ws-fact--blocked`: the strip and sideNote paths are gated by issueLine. The blocked class applies only when status is 'blocked'. The ws-decide--info change now also requires no assign candidates; this is minor and covered by the tests.
- Tests: issue-detail.test.tsx passes (31/31), including the new negative and positive cases. No existing test was weakened. The old facts expectation changed to match the board (severity moved to the header).
