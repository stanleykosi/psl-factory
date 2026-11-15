VERDICT: CHANGES
COMMIT: 1432023f985798659f2cc4342c3a745936d30324
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked W-2001 to W-2009 on the mock (FRAME_FIXTURES=1, ports 4731/4732) at 1440 and 390 with a Finance Lead test account. Layout gap against the boards is FID-1-1 (D-62) and is not re-raised here.
- Step outcomes read clearly: done (returned message shown), queued ("Waiting: ..."), 409 ("This changed while you were working. Showing version 5." with the typed text kept), 500 on a sending step (no resend), uncertain (callout plus the reconcile panel, buttons off). A decision step is a link with "Claim it first"; the disabled one shows its reason.
- One blocking gap: a 422 message for a field the form does not show is dropped, so the person never sees it.
- Wording is short and plain. A few non-blocking points on disabled buttons without a reason and dead paging controls.

## Findings
- UX-1-1 | blocking | medium | frontend | A 422 reply with a named field that is not on the form loses its message. Spec criterion 21: an unnamed or unmatched message shows at the top. On W-2006 "Check my answer", the server sends `reviewer: "A reviewer must be free."`; the form shows the main message and the two matched field messages, and "A reviewer must be free." appears nowhere on the page (checked the DOM text). The person cannot tell why the step failed. Expected: every returned message is visible (unmatched ones in the top alert). Actual: the top alert lists only `result.fields` entries that match a field. frontend/src/features/workspace/StepForm.tsx:244-250 (`known`/`unnamed`).
- UX-1-2 | non-blocking | low | frontend | After `effect_uncertain` every step button turns grey with no stated reason (W-2008 at 390: "Approve and send", "Return with a note" are disabled; the explanation sits in a callout far below the reconcile panel). Suggest a short line by the buttons, for example "Confirm what happened first." frontend/src/features/workspace/Workspace.tsx.
- UX-1-3 | non-blocking | low | frontend | "Filter", the filter chip and "Show more" are drawn as disabled controls on W-2002 and the same line "More rows aren't available yet." appears twice. It is spec-mandated, but it reads as a dead end to a PMO or Finance person. Consider one line only, once the section-page read exists, or hide the controls until then.
- UX-1-4 | non-blocking | low | frontend | On the 500 path for a non-sending step the "Try again" button sits above all step buttons and away from the form that failed, and the message "We couldn't confirm this step. Check the page before trying again." does not say which step. Name the step label in the message.
- UX-1-5 | non-blocking | low | frontend | After `done` on a fixture with no reload change (W-2001) the same "Approve and send" button stays on the page, so a person sees nothing telling them it was done beyond the returned message. This is fixture content (no `.next.json`), and the real backend decides whether the step is still offered; note for the line task that the "Done: <label>" line is replaced by `message` when one is returned, so a message that does not name the step loses the step name.

## Verified
(Round 1: nothing to verify.)

## Notes
- Accessibility seen in the walk: errors use `role="alert"`, the done/waiting line sits in a live region, focus went to the first invalid field on 422, the form kept typed input on 409. No keyboard trap seen. Phone width has no sideways scroll on the pages walked.
- The page shows the line's own header block (breadcrumb, "Your review" tag) under the standard work item header on W-2001, so the person sees two sets of titles and status. This is Conflicts 3 in the spec (kept on purpose) and part of FID-1-1.
- Fixture W-2001 shows a recorded approval in the timeline while the track says "Approved: not yet". Fixture content only, not a renderer fault.
- Ports 4731/4732 stopped after the walk. No screenshots written into the repo.
