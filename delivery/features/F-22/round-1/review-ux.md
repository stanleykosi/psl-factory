VERDICT: PASS
COMMIT: 6d857c318ffb4d772126d9e236e9dba90f0625ba
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Walked W-2209 to W-2214 on the production build (mock 4754, app 4755, FRAME_FIXTURES=1) at 1440 and 390 as the PM persona; no sideways scroll, one title, no dead end on the returned and received-confirmed paths.
- Returned: amber note above "Your update", cite chips, "Next" panel with a single primary "Edit your update"; the editor opens with the saved words, focus lands on its heading and Escape returns focus to the button. No button on W-2210.
- Received: "Verified" and DELIVERED appear only on W-2211. W-2212 shows the reconcile panel with no resend, W-2213 shows UNKNOWN with no time and the backend's BOUNCED, W-2214 shows "Nothing here yet.".
- Matches D-97 (note as amber callout, sentence plus green tag, backend tag on rows, "12 Nov 15:10" times). Copy and states follow the spec; the listed differences (Next head colour, single data sentence on phone) are accepted exceptions.
- Mock only; no real send or delivery is claimed.

## Findings
- UX-1-1 | non-blocking | low | frontend | W-2213 (failed or unknown delivery): Verify is "Needs a person" but the page offers no action and no words on what to do, only a full-width "See all exceptions" bar; expected a plain next step from the data (the backend's `next` line). Fix: backend to carry a `next` line for failed and unknown deliveries; frame needs no change.
- UX-1-2 | non-blocking | low | frontend | W-2211 and W-2213 text-only delivery row (`Sections.tsx` text rows): the sentence panel draws a stray hairline above the row because it has no title, so it reads as an empty heading line. Fix: drop the top rule for an untitled panel.
- UX-1-3 | non-blocking | low | backend | Unknown id `/work/W-9999` on the mock returns 200 with another item's fixture (INV-0412, Lagoon Health) so the 404 state cannot be seen in a browser; the spec expects 404 with nothing from another item. This is existing mock behaviour (`frontend/mock/overview.mjs`, read-only here) and the component test covers the state. Fix: mock to return 404 for ids it does not serve.
- UX-1-4 | non-blocking | low | frontend | Phone W-2212: the sticky "Record and continue" bar overlaps the "What happened" rows on a full-page capture; in a normal viewport it follows scroll, so check that the last rows stay reachable above the bar (bottom padding). Not reproduced as a blocker.

## Verified
None (round 1).
