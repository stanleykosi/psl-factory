VERDICT: PASS
COMMIT: df180ca0716d9a70e19bc82f5df57cce37e99aeb
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Fix-round check at 1440 and 390 on the shared build: UX-1-1 and UX-1-2 are fixed.
- After Approve by keyboard (Enter on the focused button) on W-1901, focus lands on the done h1 ("Invoice v2 for Lagoon Health is approved") and a status line reads "Your decision was recorded."
- On the stale case (W-1902) focus lands on the "A newer version arrived while you were reading." heading inside the alert, which announces the change.
- The 5xx card and the 401 view each now have one h1 ("Decision"); no sideways scroll at either width. Mock reset before and after.
- UX-1-3 stays as the design engineer chose (D-55). Rest of round 1 carried forward: this round changes only focus, one status line, two headings and one removed duplicate line, with no effect on the walked journeys.

## Findings
None.

## Verified
- UX-1-1 | verified | Done: focus on H1 and role=status "Your decision was recorded." at 1440 and 390. Stale: focus on the alert's H2 with role=alert text, at both widths.
- UX-1-2 | verified | 500 and 401 (intercepted item request) each render one h1 "Decision" at 1440 and 390; the 500 card keeps its alert.
- UX-1-3 | carried | Left as is by design choice; non-blocking.

## Notes
- The 401 view has no live region; it is a full view with a heading, which is enough.
