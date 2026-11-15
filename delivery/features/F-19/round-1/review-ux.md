VERDICT: PASS
COMMIT: effdc3f55c827a61a258ee44f6904654cbd6eaee
REVIEWER: reviewer-ux
AUTHORITY: delegated UX review

Scope: spec (D-70, D-71 approved), build.md, checks.md (gate PASS), side-by-side images for the detail boards at both widths. I did not start the app; the build's e2e (axe at 390 and 1440, focus, 44px targets, reduced motion) and component tests are taken as evidence and were not re-run.

Journey check: list to detail to project link, set billing contact, and the 401/403/404/409/422/network states all follow the spec. Unknown and "Not given" are words, never 0. No dead ends were found in the described flows. There is no Clients entry link, which is approved by D-70.

- UX-1-1 | non-blocking | low | design engineer | Fidelity gate: 3 of 4 boards score visual under 90 (desktop 85.9, desktop-detail 79.3, mobile-detail 76.7), so spec acceptance 1 and 2 are not met. The side-by-side images show the gaps come from board elements D-71 approved as not built (Legal name, address, Tax ID, Contacts, "Save client details", the phone sticky Save bar) and from the extra Money and Projects panels. The layout, order and tokens are otherwise faithful. The design engineer should accept these scores in writing or decide on the contract proposals. This is not a UX defect.
- UX-1-2 | non-blocking | low | builder | The board draws empty required inputs with an orange border and a blue Save button. Ours has plain inputs and a grey disabled Save until both are filled. Optional: use the board's required-field border and a blue enabled Save. Keep Save disabled until both are filled, since the spec requires that.
- UX-1-3 | non-blocking | low | builder | On the list table, "Set" appears twice per set row (STATE tag and BILLING CONTACT). It is clear but redundant, and a screen reader hears it twice. Consider hiding one visually, or making the tag the only text.
- UX-1-4 | non-blocking | low | builder | Phone detail: the helper "Needed before any invoice can start" is red under the name input, while the email input has no helper. This matches the board, so it is only a note. Make sure the helper is linked to the name input by `aria-describedby`.
