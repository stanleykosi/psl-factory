VERDICT: CHANGES
COMMIT: 84f3a3e9959b9c9cebe0746a9324c3795d5290da
REVIEWER: reviewer-ui
AUTHORITY: reviewer-ui

## Summary
- Markup and CSS for the frame are unchanged apart from the role words (data) and one new signed-out line; tokens and existing classes are reused, no one-off CSS or hard-coded colours.
- Name-only, one role, three roles, phone menu and signed-out callout (1440 and 390) all look right and do not overflow.
- A long role line (5 workspace names, about 100 characters) pushes the 1440 top bar past the viewport: Start work is cut off and the page scrolls sideways (scrollWidth 1530 vs 1440). Three roles fit at 1440, 1280 and 1100.
- Fidelity tool not run: no board element, style or position changed, only the text in the existing role span. Not a gate for a data-only frame change.
- Note: the servers on 3000/3001 do not serve this head's mock. Port 3001 is a stale process (its /me still returns `roles`, /role-dashboard 404), so port 3000 shows name alone for everyone. I checked against a fresh mock from the worktree on a private port, routed into the page, and stopped it afterwards.

## Findings
- UI-1-1 | blocking | medium | frontend | Long role words break the desktop top bar. With positions named Finance Lead, PMO Lead, Head of Delivery Operations, Client Services Manager, Administrator the `.shell-who-role` text does not truncate at 1440: Start work is clipped at the right edge and the document is 90px wider than the viewport. The spec allows up to 50 positions, de-duplicated by name, and asks that long role words not overflow. Expected: the name stays whole and the role words shorten with an ellipsis (full text stays in the accessible name or a title), with Start work and the bell always visible. Actual: `.psl-nav__who` only gets `min-width:0; overflow:hidden; text-overflow:ellipsis` below 1080px (frontend/src/styles/shell.css:63); at 1080px and above it has no cap, so the line grows. Fix by capping the role span on the bar (for example `white-space:nowrap; overflow:hidden; text-overflow:ellipsis` with `min-width:0` on `.psl-nav__who` at all widths), not by changing the design.

## Verified
None (round 1).

## Notes
- Phone menu with the same five roles wraps over two lines under the name in `.shell-menuwho small`; readable, no overflow. 390 phone bar: no horizontal overflow in any case (name-only, one role, five roles, signed out).
- Signed-out callout: warning Callout, existing tokens, one line at 1440, wraps cleanly to three lines at 390 with the icon aligned; no sign-in link, matching the spec. No board draws this state, so it cannot be fidelity-checked; wording is for the design engineer to read.
- 720 to 1079px: role is visually hidden (name only), as before.
- Mock has no persona with a multi-role line, so the design engineer's app never shows the long case; worth adding one for design review.
- Evidence screenshots (scratchpad): /private/tmp/claude-501/-Users-Hunchoo-psl-factory/901fd746-f5ef-43b5-af21-3debcffe0aed/scratchpad/ui/long-1440.png, long-390.png, out-1440.png, out-390.png, pmo-1440.png.
