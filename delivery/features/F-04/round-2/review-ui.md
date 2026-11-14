VERDICT: PASS
COMMIT: 3c93fe030ff5ac81da343dc7a0917820c8803d7b
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer, round 2 (visual review against the approved SCR-03 boards and the design system)

## Summary
- Both round 1 blocking items are fixed: Approve is action blue (rgb 36, 89, 214) at 50px on desktop and 54px on the phone, and the approve done view has the verified-tint success banner with a 2px verified border, matching both done boards.
- Return and reject done views use a neutral grey banner (7.46:1 contrast). No board exists for them, so this is recorded under Notes.
- The unconfirmed state keeps Approve, Return and Reject disabled, with a warning callout and Try again. The layout holds at 390 and 1440.
- The stale view (W-1207, "Review version 3") and the cannot-act views (W-1203, W-1206) match the spec. No sideways scroll at 390 in any state checked.
- One non-blocking finding: the unconfirmed Try again button is 40px, below the 44px default control size.

## Findings
- UI-2-1 | non-blocking | low | frontend | The Try again button in the unconfirmed state uses `psl-btn--sm` (40px) at `frontend/src/features/decide/DecideView.tsx:39`. The Button README reserves control-sm for the top bar and dense toolbars; the default content control is control-md (44px). Expected 44px, actual 40px at 390 and 1440. Visible only in that state.

None blocking.

## Verified
- UI-1-1 | verified | Default W-1201 Approve computes to rgb(36, 89, 214) (#2459D6, action blue) at 1440 (50px) and 390 (54px, full width). This matches "Approve v2" on SCR-03-desktop.dc.html and SCR-03-mobile.dc.html. While unconfirmed it is disabled and grey, as intended.
- UI-1-2 | verified | Approve done (W-1201, approve answered by a local route stub): banner background rgb(221, 239, 227) (verified-tint), border rgb(34, 118, 74) (verified), eyebrow "YOU APPROVED · HH:mm" and heading in rgb(22, 80, 47) (verified-ink). This matches SCR-03-desktop-done.dc.html and SCR-03-mobile-done.dc.html for the banner and eyebrow. The heading colour is noted below.
- UI-1-3 | verified | W-1203 reads "Approval chain 1 step" at both widths. W-1208 reads "Step 3 of 3".
- UI-1-4 | verified | Phone Approve is 54px with 17px text, full width, as on SCR-03-mobile.
- UI-1-5 | verified | W-1206 step 3 reads "CEO · Ada Okafor (you)".

## Notes
- Taste: the done heading is verified-ink at both widths. The desktop board's heading sets no colour and inherits ink; the mobile board sets #16502F. The build follows mobile. Round 1 recorded the heading as verified-ink without checking the desktop markup, so that was loose. Either colour is acceptable; the design owner decides.
- Taste: the mobile done banner uses 16px 18px padding and a 26px heading. The mobile board uses 14px padding and a 24px heading. The desktop board matches the build.
- Return and reject done views (no board) use the neutral banner (`--neutral-tint` background, `--neutral-ink` border and text). This is for the design owner to confirm.
- Spec line 143 still names `psl-btn--confirm` for Approve. The boards and the Button README say action blue. The spec should be updated so the record matches the build.
- Method, round 2: the app was checked on the shared build (3401) with the mock on 3402, at 1440x900 and 390x844. States: W-1201 default, W-1203, W-1206, W-1208, done approve and return, unconfirmed, and stale W-1207. Done, unconfirmed and stale were produced by local route stubs in the browser: the decision was never sent to the mock, the item read was answered locally, and `/__mock/reset` was not called. The claim on open is the app's normal call. Screenshots were deleted after this review was written.
- Contrast (WCAG ratios, token pairs): neutral-ink on neutral-tint 7.46, verified-ink on verified-tint 7.89, white on action 6.04. All pass AA.
- Sideways scroll: scrollWidth equals clientWidth at 390 and 1440 in every state checked.
