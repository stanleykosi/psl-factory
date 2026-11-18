VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: c5d2515627c96736a1d8884183eb630e29617a0e
AUTHORITY: delivery technical review

## Summary
- The four writes follow the spec. PM confirm reuses F-30's `useWorkspaceAssign` (CSRF, `expected_revision`, no key, one press sends once). Register and uncertain handling stay on F-17's step hook. Record input reuses F-18's `useResponse` unchanged apart from one field. No new write path is added.
- The additive `Notice.problem.forbidden?` is safe for F-18. It is optional and set only when the refusal was a 403. The F-18 page reads `message` only, and the F-18 tests are unchanged.
- Edits to AssignForm, Sections, Workspace and WorkItemView leave every non-preset path as before. `preset` is undefined without a valid `default_person_id`, so F-30's closed "Set an owner" form renders exactly as it did. `CellValue` changes only cells that previously rendered blank (empty text, or a missing tag cell), which now read Unknown. Unknown is never turned into 0.
- Nothing comes from `/me`. The only grep hit is an old "reads /me" comment in `Workspace.tsx`, which is not a read. The two `mock-contract.test.ts` edits do not loosen the schema check. The three builder deviations (the "Created" `text` section, sidecars without "Ask Tola", persona `none` not enforced) are acceptable mock-only limits.
- Two non-blocking points: the "Recorded under your name" notice appears before the re-read, and the mock-contract comment overstates what the overlay checks.

## Findings
1. TECH-1-1 | non-blocking | medium | frontend | `frontend/src/features/workspace/Workspace.tsx` (`afterRecorded`, around line 300): `setRecorded(RESPONSE_TEXT.done(...))` runs before `await page.reload()`. Expected: spec line 7 and AC 10 say the page never says "recorded" until the re-read says so. Actual: the polite notice is built from the 200 and shown while the re-read is still in flight. If the re-read fails (`refreshFailed`), "Recorded under your name…" stands without the re-read. Spec line 109 does say to build the notice from the 200's `recorded`, so the spec contradicts itself. Suggested fix: call `setRecorded` after `await page.reload()` returns an item. F-30's assign flow has the same order, so this may be left as is.
2. TECH-1-2 | non-blocking | low | frontend | `frontend/tests/mock-contract.test.ts` (new strip block, `disabled_reason` / `asked_at` loop): the comment says each overlay key "is checked on its own, then removed", but `teams[].disabled_reason` and `asked_at` are only deleted, never checked. Expected: type-check them as the other three keys are. Actual: any value passes after the strip. `engagement-planning-mock.test.ts` may cover this. It is not a loosening of an existing check, since these keys are new.
3. TECH-1-3 | non-blocking | low | frontend | `frontend/src/features/workspace/useWorkspaceAssign.ts:66`: the notice text switches on the literal `assign.role === 'PM'`. This is a hard-coded role word, but the spec (line 95) says to do exactly this.
4. TECH-1-4 | non-blocking | low | frontend | `frontend/src/features/workspace/ResponseDrawer.tsx` (403 effect): any 403 on claim or record closes the Drawer onto the page-level not-open view, even when the re-read still shows the task actionable (for example a policy refusal with a message). This matches AC 13, but the server's message is lost. Note for the backend: a 403 means no access, and a business refusal should be 422.

## Verified
None (round 1).
