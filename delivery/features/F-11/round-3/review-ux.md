VERDICT: PASS
COMMIT: 604e1b0a0f8fb3ac2cee49124f70370b1343e6de
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked the shared build (4111, mock 4112, reset before and after) as admin and finance_lead at 390 and 1440, in a headless browser session.
- Phone back link: on Rules, Finance rules and Delivery rules the frame bar shows "← Setup" (accessible name "Back to Setup", href /setup/roles), with no Menu and no second Setup link in the page. Finance and Delivery show the mono "RULES" note beside it. The link takes the 2px focus ring and goes to the Roles page. scrollWidth is 390 on all three. This closes UX-2-1 (back-link slot now exists).
- Outcome callout after a withdrawn right: on Rules (admin, finance_lead) and Finance (both) one alert shows with the same wording as round 2, focus is on it, the Set a rule panel is gone and no Save buttons remain.
- Outcome callout after Show more: with the first page read-only and a later page holding an editable rule (list responses altered in the browser, since the mock's "many" scenario has no editable row), Show more brings the panel back and the "panel has closed" text is gone from the page. Same for both personas.
- Earlier results carry forward by impact: the change touches the phone bar and the closed-panel notice only, so the desktop list, save, stale/invalid, empty, forbidden and pm/none paths are unaffected. Not re-walked.

## Findings
- UX-3-1 | non-blocking | low | frontend | Carried from UX-1-2: phone "← Setup" goes to the reserved Roles page, the nearest Setup home until the phone Setup home is built. Unchanged.

## Verified
- UX-2-1 | verified | Phone back link is now in the frame bar with the RULES note where the boards draw it (see Summary); the fidelity exception is no longer needed for visuals.
- UX-2-2 | reopen | Still open, unchanged, non-blocking (see UX-3-1).
- TECH-2-1 | verified | UX view: withdrawn right shows one focused callout and the panel closes; Show more that restores an editable row removes the stale callout and shows the panel.
