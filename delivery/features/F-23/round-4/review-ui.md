VERDICT: PASS
COMMIT: 81e06419df1929371e460af6cd2f2adb13192903
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- The decide done view no longer shows an outcome after an uncertain approve. It shows the amber warning notice and a neutral grey header "NOT CONFIRMED · <time>" / "<label>: result not confirmed". The green banner, the Next step card and the "recorded" status line are gone, and the facts strip keeps its paid note off.
- **Design system:**
  - The amber is the shared `Callout kind="warning"` (`.psl-callout--warning`, `--waiting-tint`/`--waiting-ink`, D-92b), with its warning icon and full sentence.
  - The header uses the existing `decide-banner--neutral` (`--neutral-tint`/`--neutral-ink`).
  - No new CSS and no hard-coded colour.
  - Colour never carries the meaning alone: "NOT CONFIRMED", "result not confirmed" and the notice sentence say it in words.
- No scored board moves, including after the F-27 delegation merge at 81e06419 (see Verified).

## Findings
- UI-4-1 | non-blocking | low | frontend | (no board) | `DecideStates.tsx` `DoneView` can show two amber alerts that contradict each other. When the decide answers `work_state: "effect_uncertain"` and the reload then fails (`useDecision.ts:197-202` sets `refreshFailed`), the page shows the uncertain notice ("…We've reloaded this item so you can see whether it was recorded.") and directly under it "We couldn't refresh this item. Open the work item to see the latest." The same first sentence also shows in the moment before the reload returns, while `reloaded` is still null. Suggestion: when `refreshFailed` and `uncertain`, show one notice. Or reuse `DecideView`'s `UnconfirmedNotice` wording, which already covers "uncertain and the reload failed". Wording is the UX lens's call, so not blocking here.

## Verified
- QA-3-1 (UI side) | verified | Code `DecideStates.tsx` (eb6ddf08):
  - **When it triggers:** `uncertain` = answer `work_state === "effect_uncertain"`, or the reloaded item is `effect_uncertain`, or it carries `reconcile`.
  - **What it changes:** `approved` is forced false, so the banner is `neutral`, not `success`. The `cmp-sr` "Your decision was recorded." status is dropped, and so is the `decide-next` callout (green or info, with the Next step and the agent image). `UncertainNotice` is drawn in `role="alert"`.
  - **No duplicate:** `UncertainNotice` moved, unchanged, from `DecideView.tsx` and is shared, so there is one wording. `DecideView` returns `DoneView` early (`DecideView.tsx:99-110`), so the done view never shows a second copy of the notice.
  - **Other lines:** the change is general for every line. The ready-answer approve path is untouched (`approved` and the banner are as before).
- No scored board moves | verified |
  - **Decide boards:** the F-16 decide boards are scored on fixtures whose decide answers ready, so their done view is unchanged.
  - **SCR-28 boards:** all eight are work pages, not the decide page.
  - **Changed fixtures:** the only fixtures changed this round are `W-2304.approve.json` and `W-2305.approve.json`, decide sidecars that no board scores.
  - **dlv-00 (F-26) merge:** changes nothing under `features/work-item`, `features/workspace`, `components`, `styles` or `shell` (`git diff --stat d5f10f5a 778e8681` on those paths is empty). Its only shared touch is `ProjectJourney.tsx` mounting `MoneyTab`, which no SCR-28 page renders; the work page draws its own `ProjectBar`.
  - **Result:** the signed D-105/D-106 scores stand.
- dlv-00 (F-27 delegation) merge, 778e8681..81e06419 | verified | no SCR-28 board can move.
  - **What the merge touches:** the frontend diff is only F-27 code. That is `src/app/setup/delegation/page.tsx`, `src/features/setup/*` (Delegation view, form and hooks, `api.ts`, `format.ts`, `contract-proposal.ts`, and `setup.css` rules scoped to `.setup-deleg*`, `.setup-table--deleg` and `.setup-phone`, imported only by `SetupFrame.tsx`). It also adds `mock/delegations.mjs` and its fixtures, `mock/proposals/setup.json`, the setup e2e and tests, and the `mock-contract.test.ts` delegation entries.
  - **The one `server.mjs` list:** `M1_OPERATIONS` gains `'E-DELEGATIONS', 'E-DELEGATION'`. It keeps `'E-DOCUMENT'` and `...ASSISTANT_OPERATIONS`, plus one reset and one route line for delegations.
  - **What it leaves alone:** `git diff --stat 778e8681 81e06419` is empty for `features/work-item`, `features/workspace`, `features/decide`, `components`, `styles`, `shell`, `mock/fixtures/work`, `mock/workspace.mjs` and `mock/start-work.mjs`.
  - **Result:** the eight SCR-28 work pages and their fixtures render exactly as at 778e8681, and the signed scores stand.
- UI-3-1, UI-3-2 | carried | non-blocking, unchanged by this round.

## Waivers (unchanged, signed)
- SCR-28-desktop 1440: 65.3, D-106.
- SCR-28-desktop-suggesting 1440: 81.3, D-105.
- SCR-28-desktop-drafted 1440: 85.4, D-105.
- SCR-28-desktop-review 1440: 78.7, D-105.
- SCR-28-mobile 390: 70.2, D-106.
- SCR-28-mobile-suggesting 390: 82, D-105.
- SCR-28-mobile-drafted 390: 82.5, D-105.
- SCR-28-mobile-review 390: 78.7, D-105.

## Notes
- Read-only: no servers started and no code changed. The uncertain done view has no board, so I judged it on the code and on the design-system rules above rather than a fidelity run.
