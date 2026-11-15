VERDICT: PASS
COMMIT: 1bf933da30fd5e895b5b35f48e89149984c4a305
REVIEWER: pmo-acceptance
AUTHORITY: PMO acceptance

## Summary
- Delivery acceptance only. FE-SETUP-TEMPLATES is covered: E-TEMPLATES (list) and E-TEMPLATE-VERSION (upload) are built and tested on the contract mock, which is where they stay. D-TEMPLATES-VIEW is still `proposed`, so FE-CONNECT stays gated on the backend developer. Nothing outside scope landed. The shared-file edits (`server.mjs`, `SetupFrame.tsx`, `mock-contract.test.ts`, `e2e/setup.spec.ts`) are listed in round-1 build.md.
- Evidence (first passed at 777d9a3f): the gate passed (round 2, attempt 1, 1443 tests). Technical, UX, UI and integrated QA all PASS. QA drove 27 browser journeys at 1440 and 390, with 0 axe violations, and 54 template vitest tests passed.
- Fidelity: desktop passes (coverage 100% with exceptions, visual 95.9). Phone visual is 78.8, below the 90 threshold. The design engineer waived it under D-78, signed in `fidelity-exceptions.json` `visual_waivers`, with the reason updated to the 78.8 figure. UI-1-1 is ACCEPTED_RISK with the design engineer named as authority. Every exception is recorded under D-71.
- No blocking finding is open. UI-1-2, UI-1-3 and UI-1-4 are VERIFIED. QA-2-1, QA-2-2 and QA-2-3 are low, non-blocking and frontend-owned: focus after a 422, no message when a 403 or 404 on the write empties the list, and the mock counting an unknown `versions` as zero (mock data only). TECH-1-1, TECH-1-2 and UX-1-1 to UX-1-5 stay OPEN as non-blocking notes. Their causes are settled by D-71, D-78 and D-79.
- Product acceptance is required and is PENDING the design engineer. Nothing here counts as client or product acceptance, merge or release. The UI-visible copy and flow are new: the "Upload PSL's version" panel, the "Version N" wording, the "Upload a new version" label on a non-test row, and the uncertain-upload notices.
- Branch note (resolved): the earlier note that the phone "← Setup" pointed at `/setup/roles` is closed. See "Re-confirmed on the synced head".
- Handoff for the backend developer (D-TEMPLATES-VIEW r1, from round-1 build.md; round-2 build.md does not repeat it, so carry this list forward):
  1. `revision` and `expected_revision` are `minimum 1` in the generated schema, but the spec says a revision 0 must be sent as 0. The UI sends the row's revision as read, including 0. The mock refuses `expected_revision < 1` with a 422, so the fixtures use revision >= 1. Revision 0 is covered only by a component stub. Confirm whether 0 is valid, or state that revision starts at 1.
  2. E-TEMPLATES declares no `cursor` query (`query?: never`). The UI sends `cursor` as returned in `next_cursor`, cast in `features/setup/api.ts` only. Declare it, or say how paging works.
  3. The shared client drops the 422 `fields[]`. `uploadTemplateVersion` reads it directly to mark `filename`, `content_base64` and `note`. Confirm the field names and the 422 shape.
  4. `version` is a free string; the mock bumps integers only. `test_template` is read-only for the UI, and the mock never returns `false`.
  5. Not proved without a real backend: file storage, file-type and size policy, virus scanning, 413 handling, whether `can_upload` is decided per row, and a real CSRF/session flow.

## Re-confirmed on the synced head
- Head 1bf933da differs from the passed head 777d9a3f only by a merge of origin/dlv-00-delivery-setup (follow-ups 02, line-layout frame PR #33, main's backend files PR #32).
- Limit of my check: I had no shell in this run, so I could not run `git diff 777d9a3f..1bf933da --stat -- frontend/src/features/setup frontend/src/app/setup` myself. The "no F-20 file changed beyond the merge" point rests on the coordinator's statement and is not independently confirmed here. The coordinator or the merge gate should confirm that stat.
- What I did check: `SetupFrame.tsx` on the worktree now has `usePhoneBack({ label: 'Setup', href: '/setup/rules', ... })`, so the phone "← Setup" goes to `/setup/rules` (D-68(c)). That resolves the branch note.
- Coordinator evidence reported for this head: `delivery/checks.sh` exit 0, e2e setup-templates 11 passed, e2e setup 28 passed. These are reported to me, not re-run by me.
- Scope, findings and fidelity waivers are unchanged. No new blocking finding. Verdict stays PASS.
- Product acceptance stays PENDING the design engineer.

## Findings
- PMO-2-1 | non-blocking | low | pmo | `feature.json` has `operation_ids: []`, so E-TEMPLATES and E-TEMPLATE-VERSION are not recorded on the feature record. The readiness and spec name them, and build.md and QA cover both. Expected: add both IDs to the record so the endpoint mapping can be traced from `feature.json`. This is a record gap, not an evidence gap.
- PMO-2-2 | non-blocking | low | pmo | Two existing tests were edited, and both edits are disclosed in round-1 build.md. `frontend/e2e/setup.spec.ts` lost the `['Templates', '/setup/templates']` line from the reserved-tabs loop. `frontend/tests/mock-contract.test.ts` now uses `E-CONVERSATIONS` as its unmocked-operation example. The spec's "pass unchanged" criterion is met in spirit, because no assertion was removed or loosened, but strictly the files changed. The design engineer or coordinator should note this at merge.
- PMO-2-3 | non-blocking | low | frontend | Round-2 build.md does not repeat the backend-developer notes. They exist only in round-1 build.md. Carry the list in Summary into the PR description or the D-TEMPLATES-VIEW handoff so the backend developer sees all four contract questions (revision 0, undeclared cursor, 422 `fields[]`, free-string `version`).
- PMO-2-4 | non-blocking | low | frontend | QA-2-1, QA-2-2 and QA-2-3 remain OPEN. They are low and non-blocking, so they do not hold acceptance. They should be queued as follow-up (move focus to the first invalid field after a 422; render `notices` in the empty branch; leave `versions` out when unknown in the mock) or recorded as accepted by the design engineer.

## Coordinator check of the merge diff
`git diff --stat 777d9a3f..1bf933da -- frontend/src/features/setup frontend/src/app/setup` shows one file: `frontend/src/features/setup/SetupFrame.tsx` (2 lines, the follow-ups 02 change of the phone back link to `/setup/rules`, D-68(c)). No other F-20 file changed in the merge.
