VERDICT: PASS
COMMIT: 3df5462d49c464d12d789486760215fb1df62304
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer (lighter panel, D-180)

## Summary
- Walked the Money and Milestones tabs on head 3df5462d at 1440 and 390 against the shared dev server (Next 4970, mock 4971), as the default finance lead, `none`, and the scripted projects: P-0101 (full, plus the `changed` cookie), P-0102 (limited, 2 completion pages), P-0106 (empty), P-0107 (money 403), P-0108 (money 404, completions present), P-0105 (milestones 404, money ok), P-0099 (no access), a forced 500 and a forced body with no `items`.
- Unknown money is never 0 and never summed. Null amount shows the Unknown tag with the reason, null paid/owed show Unknown each, a Delivered invoice with null paid reads "Delivered" with Paid Unknown, a USD item reads "USD 1,000.00", and no total appears anywhere. The page issues only GETs (no non-GET request seen).
- Journeys match the spec and the accepted D-182/D-185 hides. Position numbers, source references (for example "SOW-0198 v2"), the Proof press (one `GET .../milestones/3101`, "Proof version 2"), "Show more" (`?page=2`), the CHANGES column only in the `changed` state, the refusal states and the error card with Try again all behave as specified. The row with a null `stage_position` shows no number.
- Phone width works: cards in returned order, no horizontal overflow on either tab, the drill-down opens as a bottom sheet with a close button. Console errors seen were only the expected 403/404/500 from scripted refusals.
- Two small accessibility gaps are non-blocking. Screenshots (fresh, this head) are in /private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/ux/ (for example 101-money-1440.png, 101-ms-changed-1440.png, m101-sheet-390.png, m101-ms-changed-390.png, m108-ms-390.png).

## Findings
- UX-1-1 | non-blocking | medium | frontend | Escape does not close the phone bottom sheet. It is `role="dialog" aria-modal="true"` and the close X works, but pressing Escape leaves `?figure=` in the URL and the dialog open (checked at 390 on /projects/P-0101/money?figure=kickoff). Keyboard users on a modal expect Escape. Likely in the shared sheet component, so route to whoever owns it.
- UX-1-2 | non-blocking | low | frontend | The tabs have no section headings: the only heading on the page is the project h1. "Billing by contract stage" and "Recorded completions" are plain text, and the data table has no caption. Screen-reader users cannot jump to the completions list. Make them h2 and caption the table.
- UX-1-3 | non-blocking | low | frontend | The Proof buttons carry no `aria-expanded` and rely on a hidden "for <name>" label to tell them apart, which is fine; the expanded state is not announced. Add `aria-expanded` to match the inline reveal.

## Verified
- TECH-1-1 | verified | UX lens: a body with an invoice missing id or currency, or a body with no `items`, shows the "We couldn't load this project's money" card with Try again and nothing partial drawn (checked the no-`items` body at 1440 and 390).
- TECH-1-2 | verified | The Money lead reads "Each figure shows where it comes from when a source is recorded. Unknown amounts are shown as Unknown, never as 0." and an item with no sources reads "No source recorded" in the panel (Go-live and Hypercare checked).
- TECH-1-3 | verified | P-0102 (`limited: true`) shows "Some figures may be incomplete." above the table on both tabs. P-0106 (`items: []`) shows "No contract stages yet / Stages appear here once the SOW is signed." on the Money tab and "No milestones on this project yet." plus "No completions recorded yet." on the Milestones tab.
