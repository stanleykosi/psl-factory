STATUS: READY
COMMIT: 273d81b5b7cb2d146cd010383cb6f5a40e9e6b96
BUILDER: builder
LANE: full

## Summary
- Round 2 closes the blocking round-1 findings that can be fixed in this line: the Decide panel names the pack version, fixture facts and times are true, the green band, info note, outcome button, phone bar tags and Tola's Drafted time are drawn, the title is board-sized, the pack link is a link, Reject is neutral and Submitted is amber.
- Some style findings sit in shared code (shell nav colours, agent card DONE tag, F-33 decide panel caption, section-header bar, note label) and stay as honest pending exceptions or waivers; see Blocked-by-shared below.
- Checks pass; the rfp e2e passes (125); one fidelity run: coverage with exceptions 100 on all 8 boards, visual 76.7 to 89 (waivers proposed, unsigned).

## Changes
- `frontend/src/features/workspace/Workspace.tsx`: submission title gets `ws-title--submission`; document links pass `plain` on the submission line only.
- `frontend/src/features/workspace/workspace.css`: `.ws-title--submission` 24px, 112% stretch (20px on phone).
- `frontend/src/features/workspace/Links.tsx`: `plain` prop draws a document link as a plain link (`cmp-linkbutton`); default unchanged.
- Fixtures: W-3502 Reject emphasis `secondary` (board neutral); W-3502.approve, W-3503, W-3504, W-3505.delivered RFP status kind `pending` (amber, result awaited), label unchanged.
- Earlier this round (58ef982f, 6c2a7215, 322f0d91, 03e5959f): InlineDecide version label (only when `decision.recipient` is returned), Sections `lead` band, Workspace outcome button/phone bar, WorkItemView phone bar tags, LineAgent "Drafted" time, fixtures and tests.
- Shared-file changes, all scoped to line key `rfp_submission` or an opt-in prop: Workspace, Sections (`lead`), InlineDecide (recipient-gated), WorkItemView (submission line only), WorkItemOverview, Links (`plain`).

## Fixes
- TECH-1-1 | Decide panel names the returned version label; AC 8 test asserts "Submission pack v1" | 58ef982f
- UX-1-1 | uncertain and not-delivered fixtures no longer say a decision is pending | 58ef982f
- UX-1-2 | submitted fixture facts carry the true timeline times | 58ef982f
- UI-1-1 | Record the outcome is the primary button in the Next card (phone: own bottom section) | 03e5959f
- UI-1-2 | success banner is the green band with icon | 03e5959f
- UI-1-3 | receipt ref sentences and phone bar tags/status drawn from returned data | 03e5959f
- UI-1-9 | Tola "Drafted <time>" drawn from agent.started_at | 03e5959f
- UI-1-10 | info note drawn from fixture text | 03e5959f
- UI-1-5 | submission title 24px wide-set (20px phone); still h2 under the frame's h1 | a1f2c7c1
- UI-1-6 | Submitted tag amber via status kind in fixtures | a1f2c7c1
- UI-1-7 | Open the full pack is a plain link; Reject neutral | a1f2c7c1

## Left (shared code or contested, not fixed)
- UI-1-4: tab nav role/extra text copies are the F-18 frame (exceptions stay); the dark "Submission" chip is the frame's current-tab style, shared with F-18/F-37.
- UI-1-5 heading level (h1 vs h2) kept: the frame already has the page h1.
- UI-1-6: nav colours/underline, "More ways to start", agent DONE tag colour are shared shell/agent card.
- UI-1-7: decide caption colour, header orange bar, note label ("needed to return or reject", F-33) are shared.
- UI-1-8: History link size is the shared line header; the phone bar is a pinned section.
- Kemi/Overview/Setup need a PMO Lead mock persona; run used persona pm.

## Acceptance criteria
1. [x] AC 1 to 20 unchanged from round 1 except AC 8 (version in Decide panel, now asserted in `tests/rfp-submission.test.tsx:272`) and AC 18 fidelity: see Fidelity.

## Validation
- `bash delivery/checks.sh` under the shared lock, on the head: 132 files, 3241 tests passed, lint/typecheck/build exit 0. Lock released by the run's own rmdir.
- e2e `E2E_PORT=4951 MOCK_PORT=4952 npx playwright test e2e/rfp-submission.spec.ts e2e/rfp.spec.ts e2e/response.spec.ts e2e/workspace.spec.ts`: 125 passed (5.2m).
- Fidelity, one run, production build (app 4985, `API_ORIGIN=http://127.0.0.1:4984`, mock 4984, persona pm), `round-2/fidelity/run.sh`, scores in `round-2/fidelity/scores.txt`:
  coverage with exceptions 100 on all 8. Visual: desktop draft 89, review 76.7, submitted 84.7, submitted-portal 79.5; phone draft 78.4, review 79.3, submitted 83.6, submitted-portal 81.3. All under 90 and at or above 70: 8 waivers in `fidelity-exceptions.json`, unsigned. Raw coverage 66.7 to 85.7.
- `fidelity-exceptions.json`: no exception removed (every missing-type one is still hit in the run); the 8 waivers re-measured with new reasons.
- Demo left running: app 4985, mock 4984. Worktree clean and pushed.
- Coordinator: merged dlv-00 (273d81b5b7cb2d146cd010383cb6f5a40e9e6b96) to take test-reliability fix #80; base_sha 26d06343cbf753403427f76b492a592f01ea9fb2.
