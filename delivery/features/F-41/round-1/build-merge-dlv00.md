STATUS: READY
COMMIT: ea9718cd5eeb3fd267df59ebb13d7373165cd43e
BUILDER: builder
LANE: full

## Summary
- I merged the current `origin/dlv-00-delivery-setup` (F-31, F-32, F-33) into the F-41 branch. F-31, F-32, F-33 and F-41 all keep their behaviour.
- TECH-1-1: a "Done: …" or "Waiting: …" notice now appears only after the re-read lands, never from the 200 alone. An uncertain answer still locks every step at once.
- TECH-1-3: pressing Enter in the payments search follows the same rule as typing: two or more characters, or an empty box. One character sends nothing.
- TECH-1-2: this round does not change what a hung send does; it is described below as a recorded deviation.
- No change to any page layout, so the round-1 fidelity scores and waivers still apply.

## Fixes
- TECH-1-1 | ea9718cd | `useWorkspaceStep.ts`: the done and queued notices are set after `await page.reload()`. The `effect_uncertain` path is unchanged: it locks and notifies at once, then re-reads. New test: `payment-reminder.test.tsx` holds the re-read open, checks that "Done: Send reminder." and SENT are absent while it is pending, then lets the re-read land and checks that SENT and the notice appear. `workspace-step`, `workspace`, `minutes-end`, `response` and the full vitest suite still pass.
- TECH-1-3 | ea9718cd | `PaymentsView.tsx`: the search form's submit applies `SEARCH_MIN_CHARS`. New test in `payments.test.tsx`: Enter on "H" sends no read, Enter on "Ha" sends `q=Ha`.
- TECH-1-2 | ea9718cd | No code change; this is the record. A hung send leaves its one POST pending with the button busy ("Send reminder…"). Every step stays inert while that write is in flight, and nothing is retried or resent. Because the API client has no request timeout, the page never moves to the re-read or the uncertain notice on its own. If the person reloads during the hang, the page draws whatever E-WORK-ITEM then returns, and Send is locked only if the backend has marked the item `effect_uncertain` or given it `reconcile`. The real guard is the backend refusing a second send while delivery is uncertain (BACKEND-HANDOFF priority 1). A frame-level request timeout that maps to the network-failure path is a backlog item for the frame, not for this feature.

## Merge notes
- `frontend/mock/workspace.mjs`: F-31's `servedAs` (a script's `serve`) comes first, then F-28's `audience`, then F-41's `<id>.next.<step>`, then `<id>.next`. The only `.next.<x>` files are `W-2301.next.internal` (an audience; `internal` is not one of W-2301's step keys) and F-41's three W-3801 sidecars, so no F-31 or F-33 sidecar is affected.
- `Workspace.tsx`: kept F-33's `INCOME_LINE` and the merged phone-Drawer list (issue, engagement, income), and added `payment_reminder` to that one condition. Without it, the reminder's Edit would not open in the Drawer.
- `proposals.ts`: kept F-41's `itemAttachment` and F-31/F-33's `assignDefault`, `itemTeamKey`, `teamDisabled` and `stepVerdict`.
- `BACKEND-HANDOFF.md`: kept every section, in this order: F-31, F-32, F-33, F-41.
- `mock-contract.test.ts`, `Sections.tsx`, `workspace.css` and `server.mjs` merged without conflicts. E-INVOICES' persona statuses and `contractBody`, the `attachment` check and the W-3813 sample exemption sit alongside the base's additions.
- Also removed the last board string from new code: a doc comment in `model.ts` that quoted "INV-0398" (TECH note).

## Validation
- `bash delivery/checks.sh` under the shared lock (1-minute load below 14): **exit 0**. Django check clean; lint, typecheck and build OK; vitest 110 files and 2552 tests passed.
- `cd frontend && E2E_PORT=4952 MOCK_PORT=4953 npx playwright test e2e/payments.spec.ts e2e/engagement-planning.spec.ts e2e/delivery-release.spec.ts e2e/income-schedule.spec.ts e2e/workspace.spec.ts`: **140 passed (7.3 min)**.
  - payments: 31
  - engagement-planning: 22
  - delivery-release: 22
  - income-schedule: 28
  - workspace: 37
- `frontend/test-results` was deleted; no server is left on ports 4950 to 4953.
- All evidence is from the contract mock.
- Fidelity was not re-run, because this round changes no layout. Round-1 scores: SCR-20-desktop 84.5, SCR-20-mobile 71.1, SCR-32-desktop 76.9 and SCR-32-mobile 79.2; coverage is 100% after exceptions on all four. The D-83 waivers still stand, pending the design engineer, and the two SCR-20 list boards need the design engineer's own waiver.
