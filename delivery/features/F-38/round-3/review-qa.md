VERDICT: PASS
REVIEWER: qa
COMMIT: 7f943725014bec795853dc55672d700148c062a6
AUTHORITY: delivery integrated QA

## Summary
- Ran the real built demo (app 4985 over the contract mock 4984, POST /__mock/reset before every case, cookie psl_mock_persona) in Chromium with Playwright at 1440 and 390, 56 checks per width. Nothing is a real backend or a real email or portal send: every "Submitted", "Emailed" and "Received" word is mock fixture text.
- Passed at both widths: PM sends for review (one /steps POST, IN REVIEW only after the re-read, kept on reload, no "sent" wording); cover letter edit saves; reviewer approve (one decision, "Submitted" only after the re-read, kept on reload); Return needs a note (no request without it, then RETURNED TO PM); Reject; portal and email submitted pages with receipts.
- Uncertain (W-3505): after Approve the page reads "Submission pack v1 · delivery not confirmed" with EFFECT UNCERTAIN. It has no "Submitted", no IN REVIEW or review-pending text, no Record the outcome and no resend control; it survives a reload. Recording "It didn't arrive" sends one /actions POST and does not read as submitted.
- Holds and refusals passed: W-3508 Approve disabled with its reason; W-3507 "Not available yet"; W-3509 has no verdict buttons; 403 and 404 look the same and show no pack parts; 401 shows signed out; a 500 on the page read shows Retry; a 500 on the decide shows the "couldn't confirm" notice with one decision and no success; a 500 on Send for review shows "Not recorded" and no IN REVIEW; a 409 on the cover letter keeps the typed text and shows the stale sentence; a 409 on the decide (W-3506) shows v2 and the stale sentence and nothing is submitted.
- Not proved: the reconcile "It arrived" path (needs an evidence upload, which my script did not do; the F-18 reconcile e2e covers it); the pinned phone bar was not measured (the Send for review button was reachable and clicked at 390; the committed e2e asserts position); persona-based access (see QA-3-1).

## Findings
- QA-3-1 | non-blocking | low | integration | In the mock, W-3502 shows the pack and a live "Approve and submit" to pm, finance_lead, admin and pmo_lead (only persona "none" is refused), because mock fixtures do not model per-persona roles. "Pack only for personas who can open it" and "wrong user" cannot be proved here; the backend must refuse them per record and the page must draw only what it returns (the page does: W-3509 `you_can_act: false` draws no buttons). Re-prove against the real backend.
- QA-3-2 | non-blocking | low | frontend | After a 409 on a Return with a note (W-3506), the note is kept (it reappears in the textarea after "Review the latest"), but the form is closed and only "Review the latest" is shown, so the kept note is not visible until pressed. Matches the spec ("keep the note"); noted for UX only.

## Verified
- TECH-2-1 | verified | W-3503/W-3504 draw the submitted pages and Record the outcome link; the submitted fixtures return kind submitted (vitest in build.md; not re-run here); no review-pending wording on uncertain or submitted pages.
- UI-1-8 | verified | At 390, Send for review is reachable and works on the draft (clicked, one POST). The fixed bar's position at scroll was not measured here; the e2e asserts it.
