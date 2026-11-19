VERDICT: PASS
REVIEWER: qa
COMMIT: af1d1c8d3629b577c4baeebb4eae025c6a511397
AUTHORITY: delivery integrated QA

## Summary
- Ran the real stack (app 4955, mock 4954, head 4dba97ab) in Chromium at 1440 and 390 with Playwright, resetting the mock before each journey. Scripts: scratchpad `qa.mjs`, `q2.mjs`, `q3.mjs`, `q4.mjs` (not committed). Nothing in the worktree changed.
- Everything the UX review did not exercise passed: the real two-reviewer stale 409, W-4213 uncertain observation, W-4208 Unknown to CHECK HELD, reject with a note, and "approved" only after the re-read.
- Main paths passed: record Found with proof, observer copy, independent approve to VERIFIED, holds, read-only fixtures with zero writes, and access refusals. No amount, currency sign or digit-group figure appeared on any page.
- Not proved: real QuickBooks or backend (mock only), real two-person separation (the backend decides), and axe or fidelity (covered by the builder's e2e and the UI review).

## Findings
- QA-1-1 | non-blocking | low | backend | The mock still accepts an upload to C-LED-0052 for the capturer on W-4210, because the F-31 grant ignores the step's `disabled_reason`. The page sends nothing (0 POSTs on W-4210 at both widths). The builder already put this in BACKEND-HANDOFF; a real backend must refuse it.
- QA-1-2 | non-blocking | low | frontend | After the W-4213 500 the page re-reads and shows "We couldn't confirm this step. Check the page before trying again." with status "AWAITING FINANCE DECISION". No Try again is offered (the spec allows this: "if still offered"). The mock log has one 500, no replay and no second step. The observer sees the review state and the `prepared_by_you` copy.

## Verified
- Stale 409, run at 1440 and 390 with two tabs: A approved (VERIFIED). B pressed Reject with the note "Stale note QA". B's POSTs were claim and decision with `expected_revision: 1`, and the decision was not repeated. B then showed VERIFIED, "This review changed while you were reading it, so nothing was recorded." and "Your note wasn't sent: “Stale note QA”". Both still showed 3 s later, and no "rejected" wording appeared. On the phone the Reject Drawer held the note.
- W-4213: upload and one step POST, then a 500 recorded once in the mock log (replay false). The page re-read and showed the failed wording, never "Observation recorded.". No automatic resend.
- W-4208: empty submit showed "Add what you found to continue." and "Add proof to continue." with no request. Unknown with proof sent one step with `inputs.found: "unknown"`. The page then showed CHECK HELD, UNKNOWN and Verification rules, with 0 buttons and no Decide panel.
- Reject: an empty note sent nothing and showed "Add a note to reject it.". With "  Wrong journal  " the POSTs were one claim and one decision `{reject, expected_revision:1, note:"Wrong journal"}` (trimmed). The page showed REJECTED with 0 controls and no "Correct". "Decide · Ledger reviewer" and "Note (needed to reject)" appear at 1440 and 390; there is no Return.
- Approve: with the re-read held for 3 s, the status stayed AWAITING FINANCE DECISION and no "is approved" or "Verified" notice showed. After the re-read: VERIFIED, "LED-0052 v1 is approved", and Posting, Authenticity and Completeness all NO. Writes were one claim and one decision with no note.
- Record Found on W-4202: a double-click sent one upload and one step (five keys, UUID key, `evidence_ids`). The re-read showed "You prepared LED-0052 v1, so someone else must review it." with 0 buttons. The chip "×" is 48x48 at 390. No horizontal scroll.
- W-4212: approve gave CHECKING and "LED-0052 v1: result not confirmed", never approved. A routed abort on the decision gave the "couldn't confirm your decision" notice with a re-read and one decision POST. A 403 on the decision gave the read-only view with no "approved".
- Read-only and holds (W-4201, W-4204, W-4205, W-4206, W-4207, W-4209, W-4210, W-4211): no Decide control, and every button pressed produced 0 POSTs. W-4205 names no reviewer. W-4206 shows the prepared-by copy. W-4207 shows "Ledger reviewer" only as its own required role. W-4210 is inert with its reason.
- Access: persona none got the not-open page with no title and 0 writes. A 403 and a 404 on the work read give identical text and no title at both widths. (The mock serves a fallback INV-0412 for an unknown work id, so the 404 was forced with the scenario header. This is not F-45 code.)
