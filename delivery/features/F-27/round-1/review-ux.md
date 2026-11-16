VERDICT: PASS
COMMIT: ab5a4f0f8046ab431cd183345b6e98f8012369ca
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Walked /setup/delegation on the contract mock (production build, ports 4803/4804) at 1440 and 390: default, empty, readonly, forbidden, many, authority; then add, 422 (invalid), 409 (stale), uncertain, uncertain_written at both widths (phone through the sheet). SEC-1-1 not repeated.
- List, states and copy match spec and boards: Unknown end date, UPCOMING/ENDED/ACTIVE tags, empty message, view-only shows no panel or button, forbidden shows "This section isn't open to your role." No sideways scroll anywhere.
- Add works: success announces "Delegation added: ..." and focuses the new row/card (phone sheet closes); 422 shows messages beside To and Ends with focus on To and entries kept; 409 shows the stale sentence, entries kept; uncertain gives "It was not added..." and uncertain_written disables Add with "Start again".
- Visual score (desktop 84.0 waiver) is the UI reviewer's and design engineer's call, not judged here.

## Findings
- UX-1-1 | non-blocking | low | frontend | 422 top message reads "Check these fields: delegate, ends." using the backend's raw field keys (lowercase, "delegate" is not the label "To"). Expected the visible labels ("To, Ends"). Seen at 1440 panel and 390 sheet. Map field names to the labels in DelegationForm.
- UX-1-2 | non-blocking | low | frontend | On phone, after uncertain_written the sheet stays open over the list and says "Check the list for your delegation", but the list is hidden behind the sheet; the person must press Cancel to look. Suggest "Close this to check the list, or start again." on phones.

## Verified
None (round 1).
