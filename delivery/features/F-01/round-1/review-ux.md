VERDICT: PASS
COMMIT: f6e9a9ecdc299700381927a13d66386138d83e5c
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- I walked the frame in Chrome against the mock (app on 3111, mock on 3112) at 1440, 768 and 390 px, as finance_lead, pm and the persona with no sections. I also forced the 401, 403 and 404 scenarios. Servers are stopped.
- The top bar matches SCR-01-desktop (ink bar, orange underline on the current link, SAMPLE DATA label, "Ada Okafor · Finance Lead"). The phone bar and its menu work. The omitted "+ Start" is recorded in the spec as out of scope (FE-M2), so it is not a deviation.
- Every state in the spec's C5 table shows the specified copy, and the signed-out, forbidden and error states each give a next step (Sign in, a reason, Try again). SAMPLE DATA appears in all of them. No horizontal scroll at 390, 768 or 1440.
- Three non-blocking polish items are listed below.

## Findings
- UX-1-1 | non-blocking | low | frontend | At 768 to about 900 px, finance_lead's name and role are not visible in the top bar. The who-line is squeezed to nothing by the spec's rule (f), so the person can't see who they are signed in as on a tablet. The builder reported this too. Ask the design owner for a wrap or a shorter who-line. Where: `frontend/src/styles/shell.css`, `.psl-nav__who`.
- UX-1-2 | non-blocking | low | frontend | An unknown URL such as `/nonexistent` shows Next's default "404 This page could not be found." inside the full bar, with no link back to a destination. Add a short, plain not-found page with a link to the first destination. `frontend/src/app/` has no `not-found.tsx`.
- UX-1-3 | non-blocking | low | product | A placeholder page shows the same word twice: the h1 "My work" and the card's h3 "My work". The spec's C5 table asks for both, so the builder is not at fault. The design owner could drop the h3 once real pages arrive.

## Notes
- The 404 error state shows the raw code ("Reference not_found for support."), as the spec's C5 table asks. That is fine for now, and the copy can be revisited when real error codes arrive.
- The menu's person line (name over role) works well on the phone, and Esc and link selection close it. The e2e suite also checks both, and I did not re-run it.
- I did not exercise the keyboard focus ring or reduced motion by hand. I relied on the builder's Playwright run for those.
