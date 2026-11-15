VERDICT: PASS
COMMIT: a5e803ab09ccd3122a4c252be8658a9138314be0
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- TECH-1-1, TECH-1-2 and TECH-1-3 are fixed, and each has a test that fails on the round-1 source. UX-1-1 is fixed (unmatched 422 messages join the top alert) with a test.
- The D-62 layout changes write nothing new. Sections are split into main and side, and the Decide panel wraps the same `StepRow` and `control(...)` calls. Step forms render once each, as before, outside the pinned panel. The submit, key, in-flight, reload and lock logic in `useWorkspaceStep` is unchanged apart from notice text and a `label` field.
- Layout is chosen by section kind and step scope only, never by line or work id. The read-only branch moves `suggestions` aside and adds no controls.
- Fidelity gaps (criterion 25) are the design reviewer's. They are recorded honestly in the build and are not claimed as passing.

## Findings
- TECH-2-1 | non-blocking | low | frontend | `useWorkspacePage` resets on an id change by setting state during render (usePageReload.ts:27-34). An older in-flight `reload()` for the previous id can still land and set `fresh` after the reset. WorkItemView's newer-read rule limits the harm. Guard the late write by id if it ever shows.
- TECH-2-2 | non-blocking | low | frontend | TECH-1-4 is still open: a manual retry sends the reloaded revision. This needs a backend answer on the idempotency promise before a real-API cutover. The build records it.

## Verified
- TECH-1-1 | verified | reset on id change at usePageReload.ts:27-34. The test "access lost on one item is not carried to the next id" renders W-2001, loses access, rerenders W-2002, and expects `lost` and `fresh` null. It fails on the old code, which had no reset.
- TECH-1-2 | verified | `stale(undefined)` no longer names a version (useWorkspaceStep.ts:41). The test "a 409 whose re-read fails does not name a version" covers it.
- TECH-1-3 | verified | `hasValue` treats empty and blank as Unknown in facts and figures (Sections.tsx:47, :155, :343). The test uses '' and '   '.
- UX-1-1 | verified | StepForm collects unmatched 422 field messages with the top message into the alert (StepForm.tsx:244-249). A matched field stays under its input only, and a test shows it is not repeated at the top.
