STATUS: READY
COMMIT: 570b3e2f4b1529212a6299158cdbb81c3c467d61
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the round-1 review findings the adapter can fix; the rest are named lane C or F-87 dependencies below.
- The mock again carries `django_url` and is checked against the live contract; Blocks is back in the facts; Chasing no longer prints "Time unknown".
- `fidelity-exceptions.json` is written (57 items, each "builder proposal, pending design engineer").

## Changes
- `frontend/mock/issues.mjs`: `django_url` restored; the no-owner fixture's team label is "No owner" (the contract requires a label of at least one character).
- `frontend/tests/next-config.test.ts`: `issues.mjs` added to the guard allowlist with the same reason as `work-live.mjs` (test data mirroring the contract; no check weakened).
- `frontend/tests/mock-issues-live.test.ts` (new): Ajv check of the work item, follow-up, detail and messages for every fixture against `contracts/psl-factory.openapi.json`, as `mock-live-projects.test.ts` does. It caught the empty-label difference above.
- `frontend/src/features/issue-followup/model.ts`: Blocks is a fact in the one facts block; Chasing is a text section (no right-hand "Time unknown"); no-owner text shown once (the Next section skips `next_action` when the banner has it); Owner fact is not drawn when `assignment_id` is null; "Owner acknowledged" no longer repeats "Acknowledged"; the acknowledgement line shows only when it adds the time-less or basis information; planned milestone reads "UAT (planned)"; `allowedActions()` removed; `sections()` no longer takes a case id.
- Tests and e2e updated to match. `delivery/features/F-111/fidelity-exceptions.json` new.

## Fixes
- TECH-1-1 | mock django_url restored, allowlist entry, contract check | 570b3e2f4b1529212a6299158cdbb81c3c467d61
- UI-1-1 | Blocks moved into the facts | 570b3e2f4b1529212a6299158cdbb81c3c467d61
- UI-1-2 | "Time unknown" gone from Chasing | 570b3e2f4b1529212a6299158cdbb81c3c467d61
- UX-1-2 | same as UI-1-2 | 570b3e2f4b1529212a6299158cdbb81c3c467d61
- UX-1-4 | no-owner sentence shown once on the page's sections | 570b3e2f4b1529212a6299158cdbb81c3c467d61
- UX-1-5 | repeated status word and acknowledgement line dropped | 570b3e2f4b1529212a6299158cdbb81c3c467d61
- TECH-1-4 | planned wording | 570b3e2f4b1529212a6299158cdbb81c3c467d61
- TECH-1-5 | `allowedActions()` removed | 570b3e2f4b1529212a6299158cdbb81c3c467d61
- UI-1-5 and UI-1-6 | fidelity-exceptions.json written | 570b3e2f4b1529212a6299158cdbb81c3c467d61

## Left for lane C or F-87 (for the coordinator)
- TECH-1-2 / UX-1-1 (Try again): the frame's `PanelView` retries only when `read()` rejects, and then it replaces the whole panel with its generic "couldn't load this part" box. The spec wants the facts to stay when only the detail or messages read fails, so I did not reject. A per-section Try again needs F-87's `reload` (the Actions slot). I removed the false promise: the error text now reads "This is not available right now. Reload the page to try again." Hold for F-87, or accept the reload wording.
- AC9 (controls drawn disabled when `can_request_update` or `team.can_record` is true): these are writes. Spec Summary: "Read only. Owner update, reply, set owner, message owner, refresh and restart, and raise escalation are F-111B or other features. Their buttons render hidden or disabled and send nothing." Lanes: "No write forms (F-111B, on F-87's Actions slot)". They belong to F-111B on F-87's Actions slot. Nothing dead is drawn; the flags stay in the readback.
- UI-1-3 (banner tone): `PanelView` calls `SectionView` without the `banner` prop, so every adapter banner draws the warning (amber) tone. Red needs lane C to let a section carry a tone, or the design engineer to accept amber.
- UI-1-4 (frame "Next step" line contradicting the banner): the frame prints the work item's `next_step` ("Wait for the owner to update the issue.") above the adapter's sections. Fix in lane C: show the follow-up's `next_action` there, or let a line adapter replace the frame's next step.
- TECH-1-3 / UX-1-3 (Blocks link, issue register link): `SectionView` facts draw text only and `refPath` links only to a project or work item. Blocks is now plain text in the facts (no link); the register link is not drawn. Lane C change: a link-capable fact.
- TECH-1-6: the adapter has no timers; polling is `PanelView`'s. No fake-timer test here; belongs with F-85.
- UX-1-6: accepted reading of Question 2 (nothing drawn); the spec should say so.

## Acceptance criteria
Unchanged from round 1 except AC1 (Go-live is text in the facts, not a link: see above), AC9 and AC11 (F-87, see above).

## Validation
- `npx vitest run tests/issue-followup.test.tsx tests/mock-issues-live.test.ts`: 30 passed. `tests/next-config.test.ts` and `tests/cash-forecast.test.tsx`: passed (50 tests) before the last model edit, which only removed an unused parameter.
- `npx tsc --noEmit` and eslint on the changed files: clean.
- Not run per your instructions: full gate, production build, the e2e spec (e2e text assertions updated; unrun this round), a new fidelity run.

## Coordinator note (24 Nov)
Round 2 isn't gated yet. The blocking TECH-1-2 / UX-1-1 (Try again) needs F-87's `reload`, so F-111 holds for F-87 on main, like F-103. On 24 Nov lane C was asked for the four frame needs above: section reload, banner tone, an adapter-supplied next step, and a link-capable fact. If lane C declines 2 to 4, the design engineer decides whether to accept amber and the current next-step line. After F-87 lands: merge main, add a per-section Try again through `Actions`, move the adapter import into `workspace/lines/index.ts`, then gate.
