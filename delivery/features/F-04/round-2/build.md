STATUS: READY
COMMIT: 3c93fe030ff5ac81da343dc7a0917820c8803d7b
BUILDER: builder
LANE: full

## Summary
- `/work/[id]/decide?task=<id>` still claims on open and decides one exact version. Round 1's stale, cannot-act and error views are unchanged.
- New: when a decide gets a network or 5xx error and the reload after it also fails, the page says "We couldn't confirm whether your decision was recorded." Approve, Return and Reject stay disabled, and Try again only re-reads the item; it never resends the decision. If that reload answers 403 or 404, the no-access view shows. A 401 shows the signed-out view.
- After an uncertain decide, the stale check now compares against the claimed revision.
- Approve is now the default action-blue `psl-btn`, at the same size and full width. On the phone it is 54px (control-xl). The approve done view has the green success banner from SCR-03-desktop-done / mobile-done.
- Return and reject use the same banner layout in a neutral grey. If the response echoes a verdict other than the three, the page shows a neutral "Decision recorded" and never says "approved". The chain reads "1 step" for a single step, and W-1206's "(you)" now follows a name.

## Changes
- `frontend/src/features/decide/useDecision.ts`: new `unconfirmed` view (item, replaced decision, claimed revision, checking). `reconcile()` reads the item after an uncertain decide. A 401, 403 or 404 there replaces the page. A network or 5xx failure gives `unconfirmed`. A task still actionable at the claimed revision brings back the item view. A different revision gives the stale view. `recheck()` is the GET-only Try again. The claim stays on screen in the unconfirmed view, but `decide()` still requires the `item` view.
- `frontend/src/features/decide/DecideView.tsx`: `UnconfirmedNotice` is a warning callout with Try again, which reads "Checking…" while the read is in flight. It replaces the "We've reloaded this item" notice in that state.
- `frontend/src/features/decide/DecidePanel.tsx`: a `locked` prop disables all three buttons. Approve's class is now `psl-btn psl-btn--lg psl-btn--block decide-approve`; the `psl-btn--confirm` class is gone.
- `frontend/src/features/decide/DecideStates.tsx`: DoneView checks the verdict with `Object.hasOwn`. Unknown verdicts get "DECISION RECORDED · HH:mm" and "Decision recorded on <label>", with no Paid line and an info callout. It passes `banner` to the header: `success` for approve, `neutral` otherwise.
- `frontend/src/features/decide/DecisionContent.tsx`: DecideHeader takes an optional `banner` and wraps the eyebrow and h1 in it. "1 step" vs "n steps".
- `frontend/src/features/decide/decide.css`: `.decide-banner--success` (2px border in `--verified`, `--verified-tint` background, `--verified-ink` text, matching the board) and `.decide-banner--neutral` (`--neutral-tint` / `--neutral-ink`). Below 720px, `.decide-approve` uses `--control-xl` at 17px.
- `frontend/mock/fixtures/work/W-1206.json`: the CEO step (`is_you: true`) now has `person: "Ada Okafor"` (the mock viewer).
- `frontend/tests/decide.test.tsx`: tests for Approve's class, the success and neutral banners, the unexpected verdict (`constructor`), decide and reload both failing (controls off, Try again fails then succeeds, POSTs are exactly claim and decide), Try again leading to the already-decided view, a 401, 403 or 404 on the reload after an uncertain decide, the stale check at the claimed revision (claim moves to rev 3, so no stale view, next decide at 3), and "1 step".
- `frontend/e2e/decide.spec.ts`: the unconfirmed state was added to the axe and no-sideways-scroll set at 390 and 1440. New tests: the double failure on the mock (decide aborted, item 503 via `page.route`, Try again GET only, controls back once reads succeed, POSTs exactly claim and decide), the phone Approve at 54px in action blue, and the approve banner colours and the return neutral banner.

## Fixes
- SEC-1-1 | 3c93fe0 | When the decide and the reload after it both fail, the page shows the unconfirmed state with every control disabled and a GET-only Try again. A 403 or 404 on that reload shows no access and a 401 shows signed out. Unit and e2e tests added.
- TECH-1-1 | 3c93fe0 | Same fix as SEC-1-1.
- SEC-1-2 | 3c93fe0 | Unknown verdicts show a neutral "Decision recorded". The check uses `Object.hasOwn`, and the test uses the inherited key `constructor`.
- TECH-1-2 | 3c93fe0 | Same as SEC-1-2.
- TECH-1-3 | 3c93fe0 | `reconcile()` compares the reloaded revision with `claim.revision`. Unit test added.
- TECH-1-4 | n/a (report only) | Corrected below: the mock answers `revoke` with 422 only when the note is missing or blank. With a valid note it answers 501 `not_mocked`, as spec.md requires (`mock-decide.test.ts` "revoke with a note is not mocked").
- UI-1-1 | 3c93fe0 | Approve uses the default action-blue `psl-btn`, at `--lg` and full width. Unit and e2e tests assert the class and rgb(36, 89, 214).
- UI-1-2 | 3c93fe0 | The approve done view has the success banner: `--verified-tint` background, a 2px `--verified` border, and the eyebrow and h1 in `--verified-ink`, as on SCR-03-desktop-done. The e2e test checks the computed colours.
- UI-1-3 | 3c93fe0 | "1 step" when `step_count` is 1.
- UI-1-4 | 3c93fe0 | The phone Approve is 54px (`--control-xl`, 17px text, as on SCR-03-mobile). Tested in e2e.
- UI-1-5 | 3c93fe0 | W-1206's CEO step names Ada Okafor, so "(you)" follows a name.

## For the design engineer (product check)
- No board exists for the return and reject done views. They use the approve banner layout in neutral grey (`--neutral-tint` background, a 2px `--neutral-ink` border and text): not green and not an alarm colour. Their next-step callout stays info blue, as the spec says.
- An unknown verdict echo uses the same neutral banner, with "DECISION RECORDED · HH:mm" and "Decision recorded on <label>".
- The unconfirmed state keeps the board on screen with the three buttons disabled. Its message reads: "We couldn't confirm whether your decision was recorded. We also couldn't reload this item to check, so the decision buttons stay off. Try again reloads the item; it doesn't send your decision again."
- The spec text (line 143) still names `psl-btn--confirm` for Approve. This round follows the boards and the coordinator's instruction; the spec line is the coordinator's to update.

## Not built
Unchanged from round 1, with one correction: `revoke` is not sent by the client. The mock answers it with 422 when the note is missing or blank, and with 501 `not_mocked` when the note is valid.

## Acceptance criteria
1. [x] Contract v4: unchanged since round 1, and `architecture/` is untouched this round.
2. [x] Default view: unit "W-1201 shows only the decision values…" passes and now also asserts the blue Approve class. In e2e, the default view at 390 and 1440 passes axe.
3. [x] Unknown is never shown as zero: unchanged tests pass.
4. [x] W-1208 omissions and the earlier approvals in WAT: the test passes.
5. [x] Claim once with the revision and CSRF, also under StrictMode: the test passes.
6. [x] Approve and done view: the unit test passes, with the success banner and the h1 inside it. The e2e done state passes axe at both widths, and the banner colours are checked.
7. [x] Note rules: the tests pass, and the return banner is neutral.
8. [x] One write at a time: the test passes.
9. [x] Stale: the unit and e2e stale flows pass.
10. [x] 409 on claim: the test passes.
11. [x] Controls absent for W-1203 to W-1206 (GET only): the table test passes with the W-1206 fixture change.
12. [x] Cannot-act copy: the test passes, and W-1206 still shows "Step 3 of 3".
13. [x] Eligibility not taken from /me: the test passes.
14. [x] Errors: the round-1 tests pass. New: decide and reload both fail, Try again leads to already-decided, and a 401, 403 or 404 on the reload.
15. [x] Mock validation: `mock-decide.test.ts` passes.
16. [x] Mock stale and done flows: pass.
17. [x] Fixtures: strict Ajv against v4 passes over all W-12xx files, including the edited W-1206.
18. [x] Layout and a11y: the e2e decide suite passes, including the unconfirmed state at 390 and 1440 (axe-clean, no sideways scroll), the 44px phone action bar and the 54px phone Approve. I checked screenshots of the 1440 approve done view and the 390 unconfirmed view.
19. [x] Gate: `bash delivery/checks.sh` exit 0.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-04 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0. eslint has 0 warnings, typecheck is clean, vitest gives 13 files and 319 tests passed, and `next build` passes.
- `cd frontend && E2E_PORT=3401 MOCK_PORT=3402 npm run test:e2e`: 83 passed (1.3m), up from 78; the 5 new tests are all in decide.spec.ts.
- `git push origin refs/heads/fe-decide-decide-one-exact-version-approve-return:…`: 86aefc6..3c93fe0, and `git ls-remote` shows 3c93fe0. `git status --porcelain` is empty, `frontend/test-results` was removed, and 15 GB was free afterwards.

## Blocked
None.
