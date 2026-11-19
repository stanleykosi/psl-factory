STATUS: READY
COMMIT: a6c95d30225f2a01c632cda4dd65c23d4144f726
BUILDER: builder
LANE: full

## Summary
- **Phone link:** "Open the reminder draft" in Chidi's note is now a 44px tap target on phones; it looks the same as before.
- **Attachment:** the reminder's attachment is now drawn as the board draws it: a neutral box with a dashed border, the paperclip from the icon set, and ink-coloured text. It is still text only, never a link.
- **Edit form:** the submit button reads the step's returned `submit_label` ("Save draft") instead of repeating "Edit".
- **Subtitles:** the uncertain and set-aside items no longer say "Nothing is sent until you press Send."
- **Base:** this round builds on the merge of dlv-00 (F-31, F-32, F-33) and the TECH-1-1 and TECH-1-3 fixes, recorded in round-1/build-merge-dlv00.md.

## Fixes
- **UI-2-1** | 2e9e42e3 | `payments.css` phone block: `.payments__notebody a` is inline-flex with `min-height: var(--control-md)`.
  - Measured on the production build at 390: 151.6×44.
  - The e2e test "the board rows… note opens the reminder" now asserts at least 44px on the phone.
- **UI-2-2** | 2e9e42e3 | `Sections.tsx` `Attachment` draws `<Icon name="clip">` beside the bold name and the "Uploaded · 84 KB" line. In `workspace.css`, `.ws-attachment` is `--surface`, with a `--rule-strong` dashed `--ink` border and `--ink` text; `--action-tint` and `--action-ink` are gone.
  - Scope: the class is drawn only for an item that carries the `attachment` proposal. Only the W-38xx reminder fixtures carry it (grep across `mock/fixtures`).
  - Weekly, minutes and issue items render no attachment, so they are unchanged. The `minutes-end`, `weekly`, `issue-detail`, `workspace` and `workspace-step` tests pass.
  - `payment-reminder.test` asserts the icon and that there is no link.
- **UX-2-1** | 2e9e42e3 | The fixture subtitles changed; the page is unchanged and still draws `workspace.subtitle` as returned.
  - The uncertain items (W-3803.next, W-3804.next, W-3805, W-3806) read "Delivery of this reminder couldn't be confirmed. Nothing is sent again until a person confirms what happened."
  - The set-aside sidecar reads "This draft is set aside."
  - A test asserts that the old sentence is gone after an uncertain send.
  - "This sends to the client." under the disabled Send stays: it is F-17's consequence line for any step that sends.
- **UX-2-3** | 2e9e42e3 | New proposal `steps[].submit_label`, read by `stepSubmitLabel` in `proposals.ts`.
  - `StepForm.tsx` now uses `submitLabel ?? stepSubmitLabel(step) ?? step.label`. Without the field, every other line keeps its step label.
  - The `edit_draft` fixtures send "Save draft".
  - `mock-contract.test` checks the field and strips it; `payments-mock.test` does the same.
  - Tests assert there is no "Edit" button inside the form and that "Save draft" is present.
  - Listed for the backend as a contract proposal.

## Validation
- `bash delivery/checks.sh` under the shared lock (load, 2nd field, below 14):
  - **First run: exit 1.** One failure in `tests/start-work.test.tsx` ("422: the missing milestone…", a focus-timing assertion). This feature does not touch that file or `start-work`. Run alone it passed 61/61.
  - **Second full run: exit 0.** Django check clean; lint, typecheck and build OK; 110 test files and 2552 tests passed.
- `E2E_PORT=4952 MOCK_PORT=4953 npx playwright test e2e/payments.spec.ts e2e/workspace.spec.ts`: **68 passed** (payments 31, workspace 37). `test-results` was deleted, and no server is left on ports 4950 to 4953.
- **Fidelity:** I made one run, with the shared tool unmodified, over the three boards whose layout changed. It ran on a production build (mock on 4950, app on 4951). Output and `run.sh` are in `round-2/fidelity/`.

| board | width | coverage | with exceptions | visual | round 1 |
|---|---|---|---|---|---|
| SCR-20-mobile | 390 | 41.4 | 100 | 71.1 | 71.1 |
| SCR-32-desktop | 1440 | 77.1 | 100 | 76.7 | 76.9 |
| SCR-32-mobile | 390 | 50 | 100 | 79.2 | 79.2 |

- SCR-20-desktop did not change, so its round-1 score stands: 100 with exceptions, visual 84.5.
- I updated the waivers in `delivery/features/F-41/fidelity-exceptions.json`. SCR-32-desktop is now 76.7, with the attachment fix noted. SCR-20-mobile and SCR-32-mobile are unchanged.
- All exceptions and waivers are still "builder proposal, pending design engineer". The two SCR-20 list boards need the design engineer's board-level waiver.

## Not done this round (non-blocking)
- UI-2-3: the "Updated" line still sits beside the title, not beside the count.
- UI-2-4: the table still starts about 10px lower than on the board.
- UI-2-5: the INV-reference link exceptions are still mapped to Conflicts 16; this is for the design engineer.
- UX-2-2: the phone cards still show "Still owed" only, as the board draws them; whether to add invoiced and received is a design decision.

## Merge with dlv-00 (F-47, #65)
- **New head:** a6c95d30225f2a01c632cda4dd65c23d4144f726 ("Merge dlv-00-delivery-setup (F-47, #65) into F-41"), merged onto 85d04ad7.
- **Conflicts:** one, in `delivery/BACKEND-HANDOFF.md`. Both new sections are kept: "Added during F-47: Start work proof upload" first, then "Added during F-41: payments list and reminder".
- **Merged without conflicts:**
  - `frontend/mock/server.mjs`: F-47's upload branch and cookie pass-through sit alongside F-41's E-INVOICES import, `M1_OPERATIONS` entry, fixture-filter exclusion and dispatch line.
  - `frontend/mock/fixtures/me.finance_lead.json`: F-47's change taken as is.
  - `frontend/tests/mock-contract.test.ts`: no conflict; the F-41 lists (E-INVOICES persona statuses and `contractBody`, the `attachment` and `submit_label` checks, the W-3813 sample exemption) still run alongside the base's.
- **`bash delivery/checks.sh`**, run under the shared lock at a 1-minute load below 14: **exit 0**. Django check clean; lint, typecheck and build OK; 112 test files and 2606 tests passed.
- **`E2E_PORT=4952 MOCK_PORT=4953 npx playwright test e2e/payments.spec.ts e2e/start-work-proof.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts`:** **98 passed** in 5.4 min.
  - payments: 31
  - start-work-proof: 14
  - workspace: 37
  - response: 16
- **Clean-up:** `frontend/test-results` was deleted, and no server is left on ports 4950 to 4953.
- **Fidelity:** not re-run. The merge brings no F-41 layout change, so the round-2 scores and the D-119 signed waivers stand.
