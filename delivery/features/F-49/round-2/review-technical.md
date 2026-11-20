VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 139eceeb05c331741f89d45b9b995c5175ca1fa0
AUTHORITY: delivery technical review

## Summary
- Feature commit 3bedb875 matches the spec and D-130 as accepted. The change is mock-only and sends no real write.
- Authority comes only from the E-LINES grant. The line is absent for other personas, and `src` reads no `/me`, roles or persona.
- The shared start-work changes are additive and keyed to `rfp_intake` or to optional overlay keys. Other lines' forms are unchanged.
- The start sends an idempotency key made when the drawer opens, and the mock replays it correctly. Only non-blocking items remain.

## Findings
- TECH-1-1 | non-blocking | low | frontend | The tighter grep in `tests/rfp-intake-mock.test.ts:293` (`\buseMe\b|/api/v1/me|useRoles|\.roles\b`) is reasonable, since the spec's pattern matches `useMemo` and an old LineChooser comment. But it would miss a new bare `roles` identifier, and build.md says `roles:` while the test does not include it. Add `roles:` or `\broles\b` with the LineChooser comment excluded.
- TECH-1-2 | non-blocking | low | frontend | `useStartWork.ts` submit: the empty-name check calls `setFieldErrors({ [nameless.name]: ... })`. That replaces every other field error rather than merging. It only matters when a 422 is still showing. Merge it to keep the others.
- TECH-1-3 | non-blocking | low | frontend | `rfp-intake-mock.test.ts` fails with ECONNRESET in `beforeEach` (`/__mock/reset`) when run in parallel with other files. It was 1 failed of 180 in my 6-file run, and 18/18 on two solo runs. This is the flake build.md already reports and the gate's F-38 flake note matches. Not caused by the feature logic.
- TECH-1-4 | non-blocking | low | integration | The spec allowed a row in `tests/mock-contract.test.ts` for the new line. None was added. Coverage is in `rfp-intake-mock.test.ts` instead.

## Verified
- Contract: the start body is `{line, case_id: C-RFP-INTAKE, case_revision, intake, idempotency_key}`. `client` is an option value or `{new:{name}}`. `deadline_at` is sent only when the status is `stated`. A field hidden by `show_when` loses its value and is not sent (`useStartWork.ts` setValue and `drawn`). The 201 state is `owner_needed`. W-3351 and the Unassigned row are added in `work-list.mjs`. The mock refuses `{new}` unless `allow_new` and the cookie are present, so no `{new}` is sent without the overlay.
- New client (G-23-1): the row exists only when the line carries `allow_new` (cookie `psl_mock_rfp=new_client`). The sentence "client register" is not in `src`. It sends only `{new:{name}}`, to the mock, and no client record is created. An empty name is stopped in the browser with the required message and is not sent.
- Holds and claims: no browser rules on Received, duplicates or file. There is no "Tola", "workspace" or "its own case" text. The duplicate-reference and future-time 422s come from the mock's samples (`rfpProblems`).
- Idempotency: the key is made at drawer open (`useState(newIdempotencyKey)`). A double press is guarded by `writing.current`. The new key after a 409 and the Check again replay (`previous` lookup before validation) are F-05's and are unchanged. The mock stores the response only after validation passes.
- Shared changes are additive:
  - `showWhen.ts` returns shown for fields with no condition or a malformed one.
  - `intake.ts` adds only the `NewValue` branch.
  - The eyebrow group, four-segment choice and help placement are gated by `rfp_intake` sets in `labels.ts`.
  - The `sw-seg--four` class is reached only when `fourSegments` allows 4 options (others use Select above 3).
  - The CSS adds one media rule and no hex, rgb or hsl.
  - No change in `src/api`, `components`, `shell`, `response` or `rfp`, and no existing test was edited.
- Tests: I ran `rfp-intake.test.tsx`, `rfp-intake-mock.test.ts`, `start-work.test.tsx`, `start-work-intake.test.ts`, `start-work-mock.test.ts` and `rfp-assign.test.tsx`. 179 passed, 1 failed (the ECONNRESET flake, TECH-1-3). The mock file passed 18/18 twice alone. The worktree is unchanged by my run. checks.md is GATE: PASS on this head.
- Docs: BACKEND-HANDOFF.md has an "Added during F-49" section with the overlays and gap ids. The proposals file lists the overlay schemas.
- Out of my lens, left to other reviewers: fidelity criterion 18 (the builder reports it unmet; exceptions are pending the design engineer), and e2e and accessibility, which I did not re-run.

## Carried forward to round 2 (coordinator, D-123)
Round 2 drew the phone submission method as one row of four (CSS, scoped), removed six exceptions, fixed the fidelity driver, and merged test-only fixes from dlv-00 (#80, #81). No write, authority or journey path changed. Carried forward; the UI re-review covers the changes.
