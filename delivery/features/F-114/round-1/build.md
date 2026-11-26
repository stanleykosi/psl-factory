STATUS: READY
COMMIT: 9e15c21cd4952e84443aba228897fcf9d1f80485
BUILDER: builder
LANE: full

## Summary
- Go-live acceptance (SCR-45) now lives on the live work item for line `delivery-go-live/v1`, drawn by one adapter registered on the `go-live-signoff` panel (same plug-in as F-113B). The `go-live-replies` and `go-live-milestone` panels have no adapter, so nothing is drawn twice. This replaces the spec's separate `/work/{id}/go-live` route (lead's instruction).
- Writes built: upload and keep a signed copy per signer (`.../go-live-signoff/proofs`), record "Signed" (`.../go-live-signoff`), Prepare v2 (`.../go-live-replies/successor`), link a decline issue and prepare a new release candidate (`.../go-live-replies`).
- Every write goes through `useWorkCommand`: one request per press, no automatic retry, a lost answer locks with "We couldn't confirm that this happened. Check the page before trying again.", and nothing says "recorded" except the re-read.
- Mock ids differ from the spec: 4411 to 4422 and 4429 (4401 to 4410 are taken on main). 4411 ready to sign, 4412 accepted, 4413 changes, 4414 declined, 4415 not the appointed PM, 4416 earlier acceptance, 4417 conflict once, 4418 hidden source, 4419 withdrawn, 4420 nothing delivered, 4421 capture entry, 4422 declined with no options, 4429 not found.

## Changes
- `frontend/src/features/go-live/goLiveModel.ts`: reads' types, sections (sent block, accepted or earlier acceptance, latest reply, history, "What this unlocks", response rules), the pure rules (`signoffHeld`, `signoffInputs`, issue and candidate helpers) and the command descriptors.
- `goLiveAdapter.ts`: reads sign-off, replies and (only when a reply is declined) decline; 403 or 404 on the sign-off read means "Only the appointed PM records the signatures." and the replies still draw. If both reads fail, the panel's own Try again shows.
- `GoLiveActions.tsx`, `SignoffForm.tsx`, `DeclinePanel.tsx`, `Press.tsx`: the forms and one press button (disabled with a visible reason).
- `frontend/src/features/workspace/lines/index.ts`: one import line (separate commit).
- `frontend/mock/go-live.mjs` and its registration in `frontend/mock/server.mjs`; `frontend/tests/next-config.test.ts`: allow-list entry `go-live.mjs`.
- Tests: `tests/go-live-model.test.ts`, `tests/go-live-live.test.tsx`, `e2e/go-live.spec.ts`.
- `makeCommand` bug (`action: null` deletes an `action` placed in `fixed`): worked around, nothing is put in `fixed` that needs `action`. Shared-code note for the coordinator: the helper should be fixed once.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] 4411 shows the sent block, PM and Client blocks, six fields each, "Record signatures" off: live test and e2e at 1440 and 390.
2. [x] Client copy: picker upload, then one proofs call `{case_revision, receipt_id, upload_id, role:"Client", checked:true}`, only after the box is ticked; the new record is listed from the re-read and chosen for that signer (only if exactly one new row appears).
3. [x] Same record for both signers: "Choose a different signature record for each signer", nothing sent (also "61" vs "061").
4. [x] Sign-off body has both revisions, `version_id`, `receipt_id`, both signers, `mode:"fresh_signatures"`, `prior_acceptance_id:null`, `note`; sections re-read after.
5. [x] Any empty or blank field of either signer: "Needs reconciliation ...", button off, nothing prefilled (every field and blank form tested).
6. [x] 4416 offers "Use the earlier acceptance (#6990)" and sends 6990; 4411 has no such option.
7. [x] 409 (4417): changed notice, re-read, not shown as recorded; second press sends revisions 7 and 42.
8. [x] Double press and double click in one tick: one POST.
9. [x] 4415: no form, "Only the appointed PM records the signatures.", replies and unlock list still drawn.
10. [x] 404 shows "This record is unavailable." (4429). There is no separate "not on this line" case: the adapter is bound to the line's panels.
11. [x] 4420: "The go-live document hasn't been sent to the client yet." and no form.
12. [x] 4412: banner and unlock rows from the reads only; no "Mark milestone", Hypercare or Archive rows.
13. [x] 4416: "An earlier acceptance is on file (#6990)", no accepted banner.
14. [ ] Record a reply: HELD (see Held).
15. [x] With `capture[]` empty (4413) the read's `finding` is shown as the reason and no reply form is drawn.
16. [x] Prepare v2 body: revisions, four null `inputs`, `reason`.
17. [x] Decline: link existing (null title, owner, next action), create new (title, owner from `owners[]`, next action), new candidate with `requirements_id` from the read. `review_remediation` is HELD.
18. [x] A reply with no entry in the lists draws no decline control (4422).
19. [x] 4419: withdrawn reply is a read-only row; no form offers withdrawn.
20. [x] 4418: "Details not available to you"; no null, 0 or blank.
21. [x] A grep test lists only the three GETs and the five write urls; a full run touches no other route.
22. [x] PDF accepted, `.exe` and over-size refused before any request; `// @ts-expect-error` for UploadId vs EvidenceId.
23. [ ] Not run against live Django (no signed-in PM session used; read-only checks on psl_demo5 were not needed to build). The read shapes come from the contract types; the coordinator should compare once against a go-live work item.
24. [x] 403 `csrf_failed`: one session refresh, "Press the button again.", no second POST.
25. [x] e2e at 1440 and 390 (no side scroll). The fidelity tool was NOT run (no board reference was available to the tool for the live page); visual check is left to the design engineer.
26. [x] lint, typecheck, tests pass.

## Held and why
- Record the client's reply (`record_reply`) and `review_remediation`: both need an integer `evidence_id` and no read lists one; the only path (`fileToEvidence`) is an unconfirmed proposal that needs a file-agent role nobody has chosen (backend question 1). The page says so in plain words and sends nothing.
- Not drawn, as the spec says: Tola's card and steps, the single Signed/Changes/Declined form, names and titles of signers, "Delivery confirmed" and channel of the sent document, "v1 not accepted", hypercare and archive rows, "Mark milestone complete" (F-114B).

## Decisions I made (flag if wrong)
- The sign-off form is hidden once the milestone read shows an acceptance or once any non-withdrawn client reply exists (the boards show the changes and declined states without it). The server stays the rule.
- Success text: the shared sender's "Done. This item is now ..." is not drawn; the page shows only the re-read (accepted banner, new history row). The spec's inline "Recorded." with `record_id` is not drawn.
- The shared 409 and 503 words are useWorkCommand's ("This changed while you were working. Showing the latest version.", "Try again shortly."), not the spec's longer wording.
- Issue ids in the unlock list are plain text (no issue page link).
- Receipt used for the signing and proofs calls is the one with the latest `recorded_at`.
- A blank "next action" for a new issue is sent as null.

## Validation
- `npx tsc --noEmit`: clean. `npx eslint . --max-warnings 0`: clean.
- `npx vitest run`: 204 files, 4692 tests passed (includes go-live-model 22 and go-live-live 35, next-config, demo-mock, mock-contract, line-adapter, live-work-item, api-live-schema-drift).
- `node --check` on `mock/server.mjs` and `mock/go-live.mjs`: ok.
- `E2E_PORT=4910 MOCK_PORT=4911 npx playwright test e2e/go-live.spec.ts`: 12 passed (6 at 1440, 6 at 390); Playwright started and stopped both servers, nothing left listening.
- `delivery/checks.sh` in its CI mode was not run here; the coordinator waits for GitHub's checks.
