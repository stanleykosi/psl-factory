VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: a6c95d30225f2a01c632cda4dd65c23d4144f726
AUTHORITY: delivery technical review

## Summary
- This is a verification review of the fix round. I read `git diff ea9718cd..2e9e42e3` (one commit, 25 files). It changes payments and workspace styling, `Attachment` in `Sections.tsx`, adds `stepSubmitLabel` in `proposals.ts`, makes one change to the `StepForm.tsx` submit label, and edits the W-38xx fixtures and tests.
- `submit_label` is optional. `stepSubmitLabel` returns `undefined` unless the value is non-empty text, so `submitLabel ?? stepSubmitLabel(step) ?? step.label` gives every step without the field the same label as before. Only the W-38xx `edit_draft` fixtures carry it. The busy label still uses `step.label`.
- The money rules are untouched. No money, amount, Unknown or send-lock code is in the diff; the only payments source change is one CSS rule.
- No assertion was loosened. The test edits change the clicked button from "Edit" to "Save draft" and add assertions (icon, no link, old subtitle gone, no "Edit" button in the form, 44px on phone). `mock-contract` and `payments-mock` now check `submit_label` is a string before they strip it.
- Ran `npx vitest run` on 13 files (payment-reminder, payments, payments-mock, workspace-step, weekly, weekly-mock, weekly-returned-received, minutes, minutes-mock, minutes-end, minutes-end-mock, issue-detail, mock-contract): **641 passed**.

## Findings
None.

## Verified
- Round 1 had no technical findings. The round-1 conclusions about the TECH-1-1 hook order and the reminder lock still hold, because this diff does not touch `useWorkspaceStep.ts`, `Workspace.tsx` or the mock server.

## Update for head a6c95d30 (diff 85d04ad7..a6c95d30)

- The head moved by merging dlv-00 (F-47 Start work proof upload, #65 test settings). No payments, reminder, phone drawer or attachment file is in the frontend diff.
- F-47 additions in mock/server.mjs (a third E-EVIDENCE-UPLOAD owner, gated to start-work lines) and me.finance_lead.json (more startable lines) sit beside F-41 code without changing it. mock-contract.test.ts is not in this diff.
- No money rule changed. Vitest on payments, start-work, mock-contract and workspace tests: 12 files, 621 tests passed. checks.sh 2606 and e2e 98 passed.

Verdict unchanged.
