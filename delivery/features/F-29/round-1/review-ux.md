VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 9a6dd8ea67a79b6f699f55bdbe4ed24c873baeeb
AUTHORITY: reviewer-ux

## Summary
- Walked /projects/P-0102/documents/D-2901 at 1440 and 390 as persona pm on the shared mock (4853): default, returned, returned-hidden, cannot-act, no-review, no-sections, amount-unknown, v1, missing v, Documents tab; personas ceo and none; drawer and Escape focus return on the phone.
- Journey matches the approved boards and the D-111 decisions: crumb, title, tags, five sections, section 4 tint with the agent note, Checks, Audience, one phone amounts tag, "Tola flagged section 4", pinned Return/Approve, drawer with a focused, labelled note field.
- States say something useful: not-open-to-you (same for missing v, ceo, none), read-only "This review isn't open to you here.", prepared_by_you sentence, "The text isn't available here." plus Download, "The note isn't shown to you.", amount unknown reads Unknown.
- Write path not exercised by me: the mock keeps decision state server-wide (overrides map on W-2901), which would change what the UI reviewer scores. I made no approve or return calls; I relied on the builder's e2e request-log evidence for claim/decide/409/422. No scenario cookies that write were used.
- Only non-blocking polish found.

## Findings
- UX-1-1 | non-blocking | low | frontend | Returned state, desktop: "Ask Tola to draft v3" renders as plain bold text with "Not available yet" beside it, while "Edit as v3" is a grey block button with the note underneath. The two held actions look different and the first does not read as a disabled button (board draws two buttons). Expected the same disabled-button treatment for both. See the returned desktop view, Tola panel in `frontend/src/features/documents/DocumentParts.tsx`.
- UX-1-2 | non-blocking | low | frontend | Version 1 (status "Replaced by v2") shows "This review isn't open to you here." That is true but unhelpful; a superseded version would be clearer as "Replaced by v2. Review v2." (only if the backend sends it; do not build it in the browser). Taste, no spec breach.
- UX-1-3 | non-blocking | low | frontend | Phone, amount-unknown: the single tag reads just "UNKNOWN" with no word saying what is unknown (default reads "MATCHES COST-0140 V2"). Consider "AMOUNTS: UNKNOWN". The detail is available in the Checks list lower down, so no one is misled.
- UX-1-4 | non-blocking | low | product | Fixture inconsistency: crumb and page say "Lagoon Health" while the Documents tab and project page for P-0102 title it "Harmattan Bank · mobile onboarding" (builder noted this; the spec asks for Lagoon Health). Mock-only; settle the fixture name before the backend contract.

## Verified
None (round 1).
