VERDICT: CHANGES
COMMIT: 9ee65d4d689c0101591a3f94a5146c72db9545bc
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Walked pm, finance_lead, none (desktop 1440 and phone 390) and the chooser/validation/picker journeys on the shared build with the contract mock. Behaviour matches the spec: pm opens the invoice directly, chooser lists 8 grouped lines, milestone is blocked until a project is chosen, the disabled Milestone 4 shows its reason, a missing milestone returns an inline 422 with focus on the callout, Harmattan lists the billing-contact message. No dead ends. `none` sees no Start control.
- One board deviation is blocking: the primary start button in the drawer and sheet is action blue; both SCR-04 boards (desktop, mobile) draw it in the Start orange used by the top-bar button.
- Other differences from the boards are the ones the spec records (grouped radio list, textarea, "What happens next" card, Cancel when opened directly, billing contact in the callout, 8 lines vs the board's 6) and are listed as non-blocking notes only.
- Not walked: ceo-only paging, the uncertain-result and 409 states (covered by the builder's tests, not by me in the browser). Boards compared: desktop, desktop-lines, desktop-validation, mobile, mobile-validation. The other 7 line boards were not compared pixel by pixel.

## Findings
- UX-1-1 | blocking | high | frontend | The primary start button in the line drawer and phone sheet ("Start the invoice") is action blue (#2459D6 family) when enabled. Boards SCR-04-desktop and SCR-04-mobile draw it in the Start orange (#C8401C), the same colour as the top-bar and phone-bar Start button. Expected the same orange on every enabled primary start button in the drawer footer; actual blue at 1440 and 390 (see the validation state, where it is enabled). Spec does not record this as an approved exception. Likely in `frontend/src/features/start-work/LineForm.tsx` / `DrawerFrame.tsx` footer button class (use `psl-btn--start`).
- UX-1-2 | non-blocking | low | frontend | "1 things to fix" (eyebrow and callout "1 things to fix before Chidi can start.") reads wrongly for one item. The spec fixed this copy, but a singular form ("1 thing to fix") would be plain and consistent with the board's "2 things to fix". Ask product if the spec text may be changed.
- UX-1-3 | non-blocking | low | frontend | After a 422 the footer primary stays enabled, where the board validation state shows it greyed until the problem is fixed. The spec does not say; keeping it enabled lets the person retry, which is reasonable. Note for the design engineer.
- UX-1-4 | non-blocking | low | frontend | The top-bar label shows a wider gap in "Start  work" (visually hidden " work" span plus the space) at 1440; the board shows a single space.
- UX-1-5 | non-blocking | low | frontend | Phone sheet stacks Back under the primary button; the mobile boards show only the full-width primary. Costs vertical space on 390px (the "What happens next" card is cut by the sticky footer and needs a scroll). Spec says a footer with Back/Cancel, so no change required unless the design engineer wants the board layout.

## Notes (differences from the boards that the spec covers, for the design engineer)
- Chooser: board draws each line as a bordered card with no group headings and a blue Tola callout box; build has a grouped radio list and a plain Tola link row (spec: grouped radio list). Board lists 6 lines incl. "Planning and delivery handoff"; spec/fixtures list 8.
- Drawer: board has "Line chosen from the Start work menu · change line" and Back even when opened directly; the build hides both unless opened from the chooser (spec). Board's note is a single-line input; the build uses a textarea (spec). "What happens next" is a grey card with Chidi avatar rather than a divider and inline red "a Finance Lead decides" (spec).
- Phone: board header shows "Step 2 of 2 · change line" with the title "Invoice preparation"; build shows eyebrow "START WORK", the full title and the subline (spec).
- Accessibility seen: dialog focus lands on the first control (search in the chooser), validation moves focus to the alert callout, Esc in an open listbox leaves the dialog open, controls are real buttons with labels. Phone "+ Start" is 44px.

## Verified
None (round 1).
