VERDICT: PASS
REVIEWER: qa
COMMIT: 971bf73adfb922d5edd856bb0ce5f051b5b91f1e
AUTHORITY: delivery integrated QA

## Summary
- Stack: the running demo. The app on http://localhost:4987 is a production build of head 971bf73. Its served chunks contain the round-3 `noteNotSent` text and all 14 return 200. It proxies to the contract mock on http://127.0.0.1:4986. I restarted neither. Every journey began with `POST /__mock/reset` (204). I drove Chromium through Playwright from `f-35/frontend/node_modules` in Africa/Lagos as personas `ceo`, `pm` and `none`, at 1440x900 and at 390x844 (touch). Script: `node qa.cjs 1440|390` in the session scratchpad `f35r3/`. Logs are `r1440.log` and `r390.log`, and screenshots are in `shots/`. Results: 1440 passed 162 of 163, and the single failure was a key-order bug in my own script (the body was correct; fixed and confirmed at 390). 390 passed 165 of 165. The mock was reset at the end.
- QA-2-1 is fixed with a real two-reviewer race: separate browser contexts, A = `ceo`, B = `pm`, both on `/work/W-3202`. A approves. B, on the older copy, returns with a note, and gets one decision 409, no resend and an honest current state. The stale notice is lasting and has no decide buttons. I also tested B pressing "Approve and send" on the stale copy: the stale sentence shows with no note line.
- No regressions across the round-2 journeys. Covered:
  - All 12 states W-3201 to W-3212, for `ceo` and `pm`.
  - W-3210 shows 3 OF 5, Unknown and no hidden names.
  - Approve and send with a double press. Return: blank and 2001-character notes refused, a valid note trimmed.
  - The phone Drawer and the pinned bar.
  - W-3209 uncertain approve. Decide 500 and abort.
  - Scenarios 403, 409 and 422. On 409 the note is kept and only a new press resends.
  - W-3205: a 500, then Try again with the same key; it survives reload. W-3212 uncertain.
  - W-3206, W-3207 and W-3208 send zero task POSTs. W-3203 and W-3211 show amber CHECKING with no resend and no `/actions`.
  - Access: 401, 403 and 404 on read, 401 on decide, and persona `none`.
- Unproved: the contract mock only. There is no real backend, delivery provider or receipt source, and the reviewer and audience Setup values are held. In the mock, B's claim on the stale copy answers 200 because B claimed on load, before A decided. How a real backend refuses a claim after another reviewer has decided is not exercised. The SAMPLE DATA tag is hidden by build design. Axe and fidelity were not re-run (the builder's e2e and checks.sh cover them).
- Known non-blocking items, unchanged: UX-2-3 / QA-2-4 (the green banner on partial delivery), QA-2-2 (the shared History link is 42x24 at 390), and UX-3-1 to UX-3-3 and TECH-3-1.

## Findings
None.

## Verified
- QA-2-1 | verified | Two contexts, `ceo` (A) and `pm` (B), at 1440 and 390. A presses "Approve and send" and gets "SENT · CHECKING DELIVERIES" plus "Monthly report v1 is approved". B, still showing "YOUR REVIEW", opens "Return with a note" (the Drawer at 390), types "  Stale tab note  " and presses it. B's log: `POST /api/v1/tasks/T-3202/claim {"expected_revision":1}` 200, then `POST /api/v1/tasks/T-3202/decision {"expected_revision":1,"verdict":"return","note":"Stale tab note"}` with CSRF, 409, and no second decision. B's page:
  - Status "SENT · CHECKING DELIVERIES" with the four recipients "NOT YET", which is the true current state.
  - A single `role="alert"` warning: "This review changed while you were reading it, so nothing was recorded." and "Your note wasn’t sent: “Stale tab note”".
  - No Approve or Return button, no dialog left open, no "is approved", "is returned", "DRAFTING · RETURNED" or "Decision recorded", and no sideways scroll.
  - The notice is still there after 6 s idle, still with exactly one decision. After a reload the page shows the sent state with no buttons and the notice is gone (UX-3-2, non-blocking).
  - Approve variant: B's approve gets 409, and the page shows the same stale sentence, no note line and no buttons.
  - Screenshots: `shots/1440-race-return.png` and `shots/390-race-return.png`.
  - Control check: the scenario-cookie 409 on a still-actionable task shows the stale sentence exactly once, so the page notice and the panel's view never double up.
