VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 9f594712fb1c9a7ac4283d41d121707c4f96d45f
AUTHORITY: delivery UX review

## Summary
- Walked /projects/P-0101/delivery, /work/W-2501, W-2502, W-2503 as persona pm at 1440 and 390 (read only; also W-2504 for the unavailable controls; followed "Approve for release" to the decide route only, no decision submitted, no writes).
- Journeys match spec.md and the D-113-approved conflicts: six rows in order with tags, dates, links only for Release gates and Go-live; sub-nav at 1440 only; Tola card, Next; waiting, decision and ready states read in plain business language.
- Authority is clear without being implied: W-2501 shows no controls and says "Only a PMO Lead can decide."; W-2502 shows Approve and Return as links to the decide page only because the fixture says you_can_act; W-2504 shows both unavailable (aria-disabled, no href, reason in aria-describedby: "This decision needs a PMO Lead."). Ready page says "This isn't a deployment" and "Open go-live" appears only on W-2503.
- No sideways scroll at 390 (scrollWidth 390 on all four pages); decision controls and tabs are 44px tall. Only small targets: "History" (24px) and skip link, both in the shared frame, not this feature.
- Sample-data wording ("Planning decision" gate beside "Approve for release") is as approved in D-113; visual waivers are the UI reviewer's call.

## Findings
1. UX-1-1 | non-blocking | low | frontend | /work/W-2501 at 1440: the "Planning decision" task panel sits right-aligned with a large empty area to its left and its bottom edge touches the "Release gates" card below. Expected a tidy block; actual a floating panel (shared TaskPanels placement, Conflicts 4, an approved extra). Consider a margin below it or full-width placement.
2. UX-1-2 | non-blocking | low | frontend | /work/W-2501, W-2502, W-2503 at 390: the shared "History" link is 24px tall, under the 44px target of D-92c. Pre-existing shared frame (LineHeader), not introduced here; fix when the frame is next touched.
3. UX-1-3 | non-blocking | low | frontend | W-2502 at both widths: "Claim it first" appears as a small grey line under "Approve for release" without saying that the claim happens on the next page. Expected a clearer hint (e.g. "You claim it on the next page"); actual terse copy. Shared frame wording from the fixture's claim_required.

## Verified
None (round 1).
