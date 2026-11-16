VERDICT: PASS
COMMIT: 10c7accc2889434032b1addd7d8fad42fe71b9ce
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Walked the production build on the contract mock at 1440 and 390 as PM (three agents), Finance Lead (Chidi only) and Admin (none). No dead ends found.
- Pick agent, ask (new conversation CV-N1), polling of CV-2405 (step 4, step 5, answered, list line updates), answer with steps and sources, restricted source (label absent, "Restricted"), "Unknown" amount, 404 conversation, and send error with "Try again" all behave as specified.
- "Start this invoice" opens the prefilled Start work drawer; the person presses "Start the invoice"; list shows "Started · INV-0415". A second tab's start shows the drawer's "This project changed since you opened the form" notice (409 path). Nothing offers approve, send or pay; the page says agents cannot.
- Admin and no-agent persona get "No agents are available to you." with a next step and no composer. Finance Lead sees only Chidi.
- Only polish items below; not tested in depth: keyboard order and screen reader output (relied on the builder's axe e2e).

## Findings
- UX-1-1 | non-blocking | phone thread top bar | At 390 the "← Assistant" back label and the conversation title sit tight and the label's second line touches the title ("Assistant" next to "Bank M2"). Give the back label and note a gap or keep the label on one line. | frontend
- UX-1-2 | non-blocking | phone CV-2401 | The sticky composer covers the draft card's lower rows in a full-page capture; confirm the thread has bottom padding so "Start this invoice" is never hidden behind the composer at the end of scroll. | frontend
- UX-1-3 | non-blocking | second-start 409 | After the drawer's stale notice the thread still shows "Start this invoice" until the person presses start again. Spec-accepted (Start work's own notice), but a re-read on that notice would show "Started" sooner. | frontend

## Verified
None (round 1).
