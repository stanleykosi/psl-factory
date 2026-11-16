STATUS: READY
COMMIT: 7202d804508b579e6a819427e85fc6684bc413ee
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the two blocking UI findings: the "Next" panel is now plain at every width, and "Edit your update" is blue (action), not green.
- Also fixed the non-blocking findings inside this feature's files: panel/landmark name, access tests, whole-run request check, hairline above the untitled sentence row, 403 test, form-open check.
- Still contract mock only (D-LINE-WORKSPACE proposed): no real send, delivery, template, recipient or idempotency claim; D-RETURN and D-ALERT-PROVIDERS open.

## Changes
- `frontend/src/features/workspace/Workspace.tsx`: when `workspace.next` has lines the panel uses `ws-decide--next` and drops `psl-panel--decide` / `psl-panel__head--decide` (plain ink-ruled panel, plain head). Without `next` it is the Decide panel exactly as before. The `<aside>` is named by the panel head ("Next") when it holds only that panel, else keeps "Review and decide".
- `workspace.css`: the green button fill is scoped `.ws-decide:not(.ws-decide--next)`, so the Next panel's primary button keeps the default blue; untitled sections draw no hairline above the first row.
- `Sections.tsx`: `ws-section--untitled` class for sections without a title.
- Tests: `tests/weekly-returned-received.test.tsx` (21 tests), `e2e/weekly-returned-received.spec.ts`.
- `fidelity-exceptions.json` waiver scores updated; `round-2/fidelity/**`.

## Fixes
- UI-1-1 | 7202d804508b579e6a819427e85fc6684bc413ee | plain Next panel at 1440 and 390; Decide unchanged without `next`
- UI-1-2 | 7202d804508b579e6a819427e85fc6684bc413ee | green fill no longer applies in the Next panel; blue action
- UI-1-3 | 7202d804508b579e6a819427e85fc6684bc413ee | aside labelled by the "Next" heading when it holds only that panel
- SEC-1-1 | 7202d804508b579e6a819427e85fc6684bc413ee | 404 and 403 tests wait for the no-access text, then check no title/client/id; 401 test checks the signed-out callout and `next=/work/W-2299`
- SEC-1-2 | 7202d804508b579e6a819427e85fc6684bc413ee | request URLs collected across the whole run; hostname check in `afterEach`
- TECH-1-1 | 7202d804508b579e6a819427e85fc6684bc413ee | test: the `next` line stays visible with the form open (desktop; on a phone the form carries the same consequence)
- TECH-1-3 | 7202d804508b579e6a819427e85fc6684bc413ee | added a 403-on-Edit component test for W-2209
- UX-1-2 | 7202d804508b579e6a819427e85fc6684bc413ee | no top rule above the first row of an untitled section

Skipped: TECH-1-2 (already listed as a frame change in round 1; kept). UX-1-1 (backend should carry a `next` line for failed/unknown delivery; frame needs no change). UX-1-3 (mock `overview.mjs` read-only here; component test covers the 404 state). UX-1-4 (shared reconcile panel's pinned bar, `features/response/**` read-only; not reproduced as a blocker). Left by instruction: UI-1-4, SEC-1-3 (follow-ups in older shared code).

## Acceptance criteria
Unchanged from round 1 (all met); the changed ones re-verified:
1. [x] Four boards at 100% coverage after exceptions (below); visual waivers re-scored in `fidelity-exceptions.json`, pending design engineer.
15. [x] axe, one h1, no sideways scroll, 44px, focus: e2e passed.
19. [x] Every request in the whole e2e run goes to localhost/mock (`afterEach`).
20. [x] checks.sh and existing specs pass.

Fidelity (one run, production build, 4750/4751):
| board | width | coverage | with exceptions | visual |
|---|---|---|---|---|
| desktop-returned | 1440 | 70.4 | 100 | 78 |
| desktop-received | 1440 | 65.4 | 100 | 78.3 |
| mobile-returned | 390 | 66.7 | 100 | 83.3 |
| mobile-received | 390 | 40 | 100 | 86.3 |
Side-by-side on desktop-returned: plain Next panel and blue button now match the board. The tool's pass is false only for visual < 90, as in F-21.

## Validation
- `bash delivery/checks.sh`: exit 0; 79 files, 1674 tests passed.
- `E2E_PORT=4750 MOCK_PORT=4751 npx playwright test e2e/weekly.spec.ts e2e/weekly-returned-received.spec.ts e2e/workspace.spec.ts`: 79 passed. The new e2e test checks the button's computed background equals `--action` and the Next head is transparent.
- Servers stopped by PID; test-results deleted; ports 4750-4759 clear.

## Verified
- UI-1-1 | fixed | component test (no `psl-panel--decide` or head modifier on the Next panel; Decide keeps them without `next`); e2e computed head background transparent; fidelity side-by-side
- UI-1-2 | fixed | e2e: button background equals `--action`
- UI-1-3 | fixed | component test: `complementary` named "Next"; "Review and decide" kept otherwise
- SEC-1-1 | fixed | component tests for 404, 403 and 401 (wait for the state first)
- SEC-1-2 | fixed | `afterEach` over a never-reset request list
- TECH-1-1 | fixed | component test with the form open
- TECH-1-3 | fixed | 403-on-Edit component test
- UX-1-2 | fixed | CSS `.ws-section--untitled .ws-row:first-child { border-top: none }`

## Blocked
Not blocked.
