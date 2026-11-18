VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 2e9e42e3313d5a5318aa01fc8b585c2d47c5bcb4
AUTHORITY: delivery UX review

## Summary
- I verified the two UX findings that were fixed this round from the diff and the tests. UX-2-2 stays open as a design decision (non-blocking, as raised).
- The uncertain items no longer promise "Nothing is sent until you press Send". They now say that delivery couldn't be confirmed and that nothing is sent again until a person confirms what happened. This matches the locked buttons and the no-resend rule.
- The Edit form's submit button now reads "Save draft", so the action is distinct from the step that opened it.
- Ran 13 related vitest files: 641 passed.

## Findings
None.

## Verified
- UX-2-1 | verified | The subtitles in W-3803.next, W-3804.next, W-3805 and W-3806 now read "Delivery of this reminder couldn't be confirmed. Nothing is sent again until a person confirms what happened." The set-aside sidecar reads "This draft is set aside." `payment-reminder.test.tsx` asserts the old sentence is gone after an uncertain send. "This sends to the client." stays as F-17's shared consequence line, which the builder noted.
- UX-2-3 | verified | `StepForm.tsx` uses `submitLabel ?? stepSubmitLabel(step) ?? step.label`, and the `edit_draft` fixtures send "Save draft". The test asserts there is no "Edit" button inside the form, and "Save draft" both submits the edit and triggers validation. Steps without the field keep their own label: the weekly, minutes, issue and workspace-step tests pass unchanged.
