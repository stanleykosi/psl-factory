VERDICT: CHANGES
COMMIT: f2a1ebfd541d2a248f6e0ef7985b31b561ca7582
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (D-180 lighter panel; builder's fidelity run read, not re-run)

## Summary
- Read round-1/fidelity side-by-side and report.json for SCR-17 set-up at 1440 (coverage 60%, visual 90.1) and 390 (coverage 60%, visual 55.6). The tool was not re-run, as instructed.
- The 4 unmatched board items are not defects: the email and masked-password values are sample values the tool cannot read from live inputs, and the WhatsApp value and sentence are the approved D-182 Q2 removal. They need extra exception entries (design engineer), not a build change.
- One real defect: at 390 the board has a full-width dark "PSL FACTORY" band across the top; the page has no band (brand text on the light background). This is the main cause of phone visual 55.6.
- Desktop passes visually (90.1). Smaller deviations are listed under Notes.

## Findings
- UI-1-1 | blocking | medium | frontend | Phone brand band missing. Board SCR-17-mobile-setup draws a full-width #1F2427 band (390x51) holding "PSL FACTORY" at the top; the built page at 390 shows the wordmark on the light background with no band (report.json: "background #1F2427 on the board, none on the page"). Visual 55.6 vs required 90. Expected: dark band as the board. Actual: no band. Path: frontend/src/features/sign-in/BrandColumn.tsx (and join.css / sign-in phone styles). Check against the F-58 sign-in phone board before changing the shared component so sign-in does not regress.
- UI-1-2 | non-blocking | low | frontend | Desktop brand column carries three illustrations and the tagline "Work you can see moving, from first draft to verified."; the SCR-17-desktop-setup board shows only the wordmark on an empty dark column. The other SCR-17 boards (sign-in, error) do carry the tagline, and the column is the shared F-58 component, so this is treated as settled. Design engineer to confirm or add an exception.
- UI-1-3 | non-blocking | low | frontend | Work email renders as a grey read-only field (tinted fill, no heavy border); the board draws it as a white bordered input like the others. Reasonable for read-only, but it is a visible difference. Design engineer to confirm.

## Unmatched items
- `sola.martins@psl.example` (board value in the email box): sample value, the page does show it in the field (see side-by-side). Not a defect; propose exception "input value the tool cannot read".
- `••••••••••••` (board masked password): sample value, the page field is empty by design. Not a defect; same proposed exception.
- `+234 802 *** 1190` and "We'll send a code to check it. You can change this later.": approved removal (D-182 Q2 a); the spec exception names the textbox label, the tool lists the value and sentence as Text. Approved in substance; design engineer to add the two Text entries so the tool reaches 100%.
- Extra on page, approved: "This invitation works until 26 Nov 2026, 15:00." and "Confirm new password" (spec exceptions).

## Notes
- The tool will not pass until the design engineer adds the four Text exceptions (coverage then 10/10 with exceptions) and UI-1-1 is fixed (phone visual >= 90).
- Heading 32 vs 30px (desktop) and 26 vs 24 (phone), small text 14 vs 12px: shared sign-in tokens settled in F-58; welcome text colour #1F2427 vs board #4A5357. Taste-level, not blocking.
- Page positions are shifted down about 8 to 50px because of the added validity line and confirm field (approved additions).
- The app was not started for this review; findings rest on the builder's captured screenshots.

## Verified
