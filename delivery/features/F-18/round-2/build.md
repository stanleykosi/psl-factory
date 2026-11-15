STATUS: READY
COMMIT: 28c13dbcca5af9b6db6f276e2878c43a487a8958
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes UI-1-1 to UI-1-6, TECH-1-2, the security note and UX-1-1, 1-2, 1-3, 1-4, 1-5, 1-6. UI-1-7 is left for the design engineer.
- The team input form no longer depends on CSS load order: the overrides are now more specific than `response.css`, and `ResponseView` imports `response.css` first, as `OutcomeView` does.
- Recorded states follow the boards. Desktop won has no Next panel. On the phone no state has a Next panel; won and pending pin the action; unknown keeps a secondary button; lost gets a quiet link.
- Follow-up: Send is off while the edit box is empty, and "Use the draft" returns to the draft. After sending, focus moves to the status line and the stale line goes. The card says why you cannot send.
- Gate passes; the rfp, response and work-item e2e specs pass (69). Fidelity: 4 of 18 boards at 90 or more, as in round 1 (see below).

## Changes
- `frontend/src/features/rfp/rfp.css`: overrides use `.resp-form.rfp-form`, `.resp-form.resp-form--team`, `.resp-main.resp-main--team` and `.resp-aside.resp-aside--team`. New `.rfp-pin` (phone pinned bar). The phone panel-head style also covers `.rfp-followup`.
- `frontend/src/features/response/ResponseView.tsx`: CSS import order; an h1 on the not-open page.
- `frontend/src/features/rfp/RecordedView.tsx`: the Next block per board (see Summary); the phone archive line is a muted `psl-hint`, not a callout.
- `frontend/src/features/rfp/labels.ts`: lost tag is neutral, unknown is waiting (amber).
- `frontend/src/features/rfp/FollowupCard.tsx`, `useFollowup.ts`: `blank` guard, "Use the draft", focus, a single status element, the stale note only on a draft, the reason line.
- `frontend/src/features/rfp/useOutcome.ts`: the missing-items hint names the proof as well as the choices.
- `frontend/tests/rfp.test.tsx`: new and changed tests (below).

## Fixes
- UI-1-1 | 28c13db | specificity plus import order; fidelity of the frozen form pages unchanged (93.4)
- UI-1-2 | 28c13db | won on desktop: sentence and an outlined "Open engagement EN-0042", no panel
- UI-1-3 | 28c13db | phone: no Next panel anywhere; won and pending pinned; unknown secondary in flow; lost quiet link
- UI-1-4 | 28c13db | phone archive line is muted text
- UI-1-5 | 28c13db | phone follow-up heading uses the phone heading style
- UI-1-6 | 28c13db | lost is grey and unknown amber, using the existing tone tokens. **This departs from the spec's colour table** (lost red, unknown neutral), as the boards decide.
- TECH-1-2 | 28c13db | see below
- Security note 3, UX-1-3 | 28c13db | blank edit box turns Send off and shows "The box is empty. Write the follow-up, or use the draft."; "Use the draft" replaces Edit while editing
- UX-1-1 | 28c13db | focus moves to the status line after Send
- UX-1-2 | 28c13db | "It goes only if you send it" shows only on a draft
- UX-1-4 | 28c13db | "You can't send this follow-up. Only people PSL allows to send follow-ups can." when neither Send nor Edit is offered
- UX-1-5 | 28c13db | hint reads "Choose A and B, and add the proof, to record this."
- UX-1-6 | 28c13db | h1 (the task title) on the not-open page

TECH-1-2: E-RFP-OUTCOME takes one `evidence_id`. On inspection the outcome form uses the card layout, which already hides the file picker once a file is attached, so a second file cannot be added and the later-file drop was not reachable. I made no code change for it. I added a test: after one upload there is no file input, and the request carries that one id. **This test does not fail on the old code**, because the old code behaves the same way; it guards the one-file rule. Contract question for the backend: should the outcome take several proof files?

## Acceptance criteria
1. [ ] Desktop fidelity: coverage after exceptions is 100 on all 9; visual is at least 90 on 4 (below). The rest wait on UI-1-7.
2. [ ] Phone fidelity: coverage after exceptions is 100 on all 9; visual 70.2 to 89, none at 90 (below).
3. [x] Form variants, exceptions, titles and bar, frame, team input, outcome gating and request, recorded and follow-up states: covered by `tests/rfp.test.tsx` (53 tests, including the new ones) and the e2e specs; nothing else changed from round 1.
4. [x] Follow-up sends only on a click; blank text is never sent: test "an empty box keeps Send off".

## Fidelity (production build, mock 4622, cookie pm, `--exceptions --wait-ms 500`, 1440 and 390)
`round-2/fidelity/scores.txt`; each board folder keeps only `report.json` and `side-by-side.png`; the frozen pages and the two helper scripts are kept.

| Board | 1440 | 390 |
|---|---|---|
| team-input | 93.4 | 85.1 |
| rfp-outcome | 90.3 | 88.5 |
| rfp-outcome-lost | 94.6 | 82.4 |
| rfp-outcome-pending | 92.9 | 87.1 |
| rfp-outcome-unknown | 88.6 | 89.0 |
| rfp-won | 76.6 (was 73.2) | 85.7 (was 74.8) |
| rfp-lost | 88.2 | 70.2 (was 77.7) |
| rfp-pending | 74.6 | 87.3 |
| rfp-unknown | 86.7 | 86.1 |

Coverage after exceptions is 100 on all 18. Phone rfp-lost fell: the tool's content-cell count shrank (1138 to 845) while mismatched cells stayed at 252. The quiet link and the "no engagement" line add text the board does not draw, and the panel chrome no longer matches by accident. I kept the link the spec requires.

Remaining gap for each board under 90 (causes: T approved 40px/26px titles; R contract-required fields: note, attestation, record_as select, "Amount not known", "To", 44px segments; D native date text; C D-60 omissions):
- desktop rfp-outcome-unknown 88.6: R, C (proof card kept, no "What happens next")
- desktop rfp-won 76.6: C (the planning-packet card, about 300px, and the intro)
- desktop rfp-lost 88.2: C (one-line archive callout); lesson tags neutral (UI-1-8, backend)
- desktop rfp-pending 74.6: C (intro callout omitted, rows panel 53px higher)
- desktop rfp-unknown 86.7: R ("To" line), C; NOTHING YET tag neutral (UI-1-8)
- mobile team-input 85.1: T, R, D
- mobile rfp-outcome 88.5, -lost 82.4, -pending 87.1, -unknown 89.0: T, R, D (-lost and -unknown also C)
- mobile rfp-won 85.7, rfp-pending 87.3: T, C
- mobile rfp-lost 70.2: T, C (extra required link and next line; board draws only the lessons and the archive line)
- mobile rfp-unknown 86.1: T, R (agent card and "To" line)

## Validation
- `bash delivery/checks.sh`: passed (exit 0; lint, typecheck, tests, production build).
- `npx vitest run tests/rfp.test.tsx tests/response.test.tsx tests/rfp-mock.test.ts` and the work-item tests: all pass (272 tests across the five files).
- `E2E_PORT=4621 MOCK_PORT=4622 npx playwright test e2e/rfp.spec.ts e2e/response.spec.ts e2e/work-item.spec.ts`: 69 passed. `frontend/test-results` removed.
- Fidelity: all 18 boards re-run on the production build. A first run of the recorded boards hit a mock stopped by another agent's `pkill`; I restarted it and re-ran, and those results are the ones recorded. Servers on 4621 to 4623 are stopped.
- UI-1-1 was not compared against `next dev`, because no dev port is in my range. The fix does not depend on load order: the selectors are now more specific, and the production frozen pages score as before (team input 93.4).

## Blocked
Not blocked. UI-1-7 (14 boards under 90) and the 23 provisional exceptions wait for the design engineer.
