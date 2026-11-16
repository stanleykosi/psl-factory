VERDICT: PASS
COMMIT: de541608e755eb9de9b2625187c08abc297a3fb1
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- Round 3 changes three things in the frontend:
  - W-2209's four cite fields carry their saved records (fixture data only).
  - The step form pre-fills a `records` field from that list.
  - An uncertain item with no reconcile shows a warning callout with a Reload button.
- None of the three draws anything new on the closed W-2209 or W-2211 page that the four SCR-25 boards score. The builder's no-re-run argument holds, and the round-2 scores and the D-99-signed waivers stand.
- The new callout uses the shared warning `Callout` (amber, which D-92b assigns to "effect uncertain") and the shared secondary `Button`. It adds no CSS and no hard-coded colours or sizes.
- This was a read-only review of `git diff 0cc0a73b..de541608`. I started no server and ran no fidelity check.

## Does the no-re-run argument hold?
Yes. I checked each change against the four boards:
- **W-2209.json cite values:** they are new `value` lists on the step's `*_cites` fields. Only the Edit form (StepForm) reads them, and the form opens only when someone presses "Edit your update". The closed page's "Your update" rows and their chips ("2 RECORDS", "ISS-0233", "MIN-0141", "2 ACTIONS") come from the section items, which this round did not change. No fidelity run opens the form, so the scored pages for SCR-25-desktop-returned and SCR-25-mobile-returned are unchanged.
- **StepForm.tsx:** only the form's starting values change. There is no markup or class change, so it has no effect until the form is open, and the boards do not draw the form.
- **Workspace.tsx:** the new callout appears only when `item.state === 'effect_uncertain'` and there is no `reconcile`. The scored fixtures are W-2209 (`state: action_needed`) and W-2211 (`state: verified`), so it does not show on any scored board.
- **Earlier boards:** no CSS, token or shared-component file changed, so nothing on the earlier F-17 and F-21 boards can move either.

## Findings
None.

## Design-system check of the new callout (Workspace.tsx:272-282)
- It uses `Callout kind="warning"` with the existing `ws-notice` class. It has the same structure as the stale and uncertain notices next to it (a `role="alert"` wrapper, a sentence, then a secondary Button).
- Its colour meaning is right: amber means waiting, which matches D-92b for "effect uncertain". It shows no green and no verified wording, and the sentence makes no delivery claim.
- The sentence comes from `STEP_TEXT.uncertainNoReconcile`. The visible "Reload" label is an inline literal, which is the pattern the neighbouring stale notice already uses (Workspace.tsx:266). There is no board for this state, so this is a frame state rather than a board difference.

## Verified
- UI-1-1, UI-1-2, UI-1-3 (verified in round 2) | still verified | the round-3 diff does not touch `workspace.css`, the Next panel markup (Workspace.tsx:315-321) or the aside's label.

## Board waivers (D-83)
- SCR-25-desktop-returned (78): justified, signed D-99. Not affected this round.
- SCR-25-desktop-received (78.3): justified, signed D-99. Not affected this round.
- SCR-25-mobile-returned (83.3): justified, signed D-99. Not affected this round.
- SCR-25-mobile-received (86.3): justified, signed D-99. Not affected this round.

## Notes
- `role="alert"` on a callout that renders on page load is announced as soon as the page opens. The neighbouring notices do the same, and for an uncertain effect it is acceptable.
