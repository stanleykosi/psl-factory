VERDICT: CHANGES
COMMIT: 15c8e6bd1aa8c17eefc1f3365473714f6700eb3f
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer

## Summary
- Fidelity tool (run once on this head, not re-run): coverage 100% after approved exceptions on all four boards. Visual scores are below the 90 gate: desktop 86.9, desktop-error 81.9, mobile 65.1, mobile-error 59.3.
- Much of the visual gap comes from approved exceptions (removed subtitle and footer, filled sample values on the board), which pull the fields up on the page. Three real, non-exception differences remain (below).
- Reports and side-by-side images: delivery/features/F-58/round-1/fidelity/<board>-<width>/.
- Side-by-side reading was done on the saved images only; no new browser session was run.

## Findings
- UI-1-1 | blocking | medium | frontend | Error state: the board's Password field takes a red-orange border after a failed sign-in (SCR-17-desktop-error, SCR-17-mobile-error). The built Password field keeps the normal dark border. Expected the error border token on the field the callout refers to.
- UI-1-2 | blocking | low | frontend | Phone: board inputs are 52px high (Password box 350x52); built inputs are 48px (350x48), so every control below shifts. Match the board height at 390.
- UI-1-3 | blocking | low | frontend | Field labels render bold in the build; the board's labels are a lighter (medium) weight, on both desktop and phone. Use the board's label weight and the existing label token.

## Notes
- The tool's "different place" flags (3 on desktop, 1-2 on phone) follow from the exceptions D-177 to D-179 and are not raised.
- Phone Password text colour is #1F2427 against the board's #000000 (the tool marks it); the page value is the project ink token, so it is acceptable.
- Once UI-1-1 to UI-1-3 are fixed, a fresh tool run is needed to show visual >= 90; if it still falls short only because of the exceptions, the design engineer should decide whether to accept that.

## Verified
None (round 1).
