STATUS: READY
COMMIT: b051cfa790dc4984060e6e236649aefb5c83e764
BUILDER: builder
LANE: full

## What is sent, and what stays held
- Contract mock only. Nothing is sent to Support and nobody at Support receives, replies to or acknowledges anything. "Publish to Support" is a mock step (G-48-2: no Support recipient or channel exists). Every "published", "received", "acknowledged", "Femi Ojo" and "verified" is fixture text returned after the write and re-read.
- The Setup rule `delivery.handover_review` is Not set. W-3702 shows "Review needed?" as Unknown with no controls. No review decision, approver or recipient is built.
- Open for the backend: G-48-1 (gaps field and the Received / Gaps found mapping), G-48-2 (Support recipient, channel, receipt word), and the three questions at `gaps-d-delivery.md:147-150` (what closes a gap, and the two others there). G-48-3 needs no field (covered by `unknown`). G-F40-1 (`<id>.recorded.<action>` fixtures) is mock only.
- Closure is parts 2 and 3: "See what closure needs" goes to the plain item W-3720.

## Summary
- The Handover row on `/projects/P-0101/delivery` (and the sub-nav's Handover) now links to `/work/W-3704` through one added `work_id` line in `P-0101.json`.
- The handover item draws four states from the response alone: ready to publish (W-3701), reply form in place (W-3703), gaps (W-3704), acknowledged (W-3705). W-3702 is the hold; W-3706 to W-3711 are the negative fixtures.
- New `SupportHandoverForm` built from F-18's parts, hosted in a Panel by a split-out `ResponseFlow` (F-31's Drawer is unchanged). One guarded write after the proof upload; no success text before the re-read; 409 or an unclear result re-reads the page and says so in "reply" wording.
- Publish is one key per attempt; after an uncertain result only reconcile; "acknowledged" and the green banner come only from `status.tone: verified`.
- Mock: `gaps` rule (422 `gaps`) and the state per action on `response.mjs`.

## Changes
- `src/features/response/`: `SupportHandoverForm.tsx` (new); `ResponseForm.tsx` (export `Actions` with a label prop, `Attest`, `Fixed`); `useResponse.ts` (`gaps` entry, `gapLines`, `handoverOpen`, missing-line branch, body); `contract.ts` (`gaps?` marked PROPOSAL); `labels.ts` (`Record reply`, name · role for the handover responder).
- `src/features/workspace/`: `ResponseDrawer.tsx` (`ResponseFlow` split out; `ResponsePanel`; `REPLY_TEXT`; `responseTaskFor` also returns `support_handover`); `Workspace.tsx` (reply panel in the main column, `afterReplyRecorded`, `afterReplyMoved`); `Steps.tsx` (shared file, listed: a task with no `decision` block still gets the "This decision needs a PM." sentence when `cannot_act_reason` is `not_your_role`, as the spec needs for W-3709); `workspace.css` (additive).
- `mock/`: `response.mjs` (two additive rules); fixtures W-3701 to W-3711, W-3720 with `.steps`/`.next`; `response/` sidecars; `P-0101.json` one line (`"work_id": "W-3704"`).
- Tests: `support-handover.test.tsx` (40), `support-handover-mock.test.ts` (44), `e2e/support-handover.spec.ts`; edits to `delivery-overview.test.tsx`, `delivery-release-mock.test.ts` (the Handover expectations), `mock-contract.test.ts` (links allow-list adds W-37), `response-mock.test.ts` (checks the proposed `assistant`/`work` link kinds on their own, then strips links before the schema check, as the other mock tests do), `e2e/delivery-release.spec.ts` (sub-nav now lists Handover).
- Factory: `fidelity-exceptions.json`, `round-1/fidelity/**` (run.sh, drive-states.mjs, serve-frozen.mjs, scores.txt, reports).

## Spec versus the merged code (re-verified)
- F-34 is merged: Hypercare's `work_id` W-3101 was already in the fixture; only Handover's was added (diff is exactly one line). Both unit tests and the `delivery-release` e2e expected "Handover has no link" and now expect W-3704.
- Delivery tab paths (`DeliveryTab.tsx`, `PROJECT_TABS`, `work` link kind in `proposals.ts`) are as the spec names them; no `src/features/projects/**` change. On a phone the sub-nav is hidden (F-32), so the sub-nav link check runs at 1440 only.
- `Steps.tsx` unavailable-step sentence needed the small change above: it only used `cannotActCopy` when the task had a `decision` block.
- `case_revision` is 2 in the fixtures (not 1): the mock checks an upload against the first P-0101 item (2), so 1 would 409 forever.
- `W-3701.next` and `W-3706.delivered` carry T-3701 and T-3706, not T-3703: the mock finds a task by id across items, so a duplicate id would record against the wrong item. Matching `W-3701.recorded.*` and `W-3706.recorded.*` sidecars were added.
- W-3701 also returns `next` (the consequence sentence) so the panel is headed "Next" as the board draws it; the step text is not repeated.
- The mock 200 for a handover record is the bare form (the sidecars list no task), so the notice reads "Recorded under your name" with no summary.
- A `ceo` persona can open the work item (fixtures are static); the no-access check for a persona not on P-0101's list is on the Delivery tab (`/projects/P-0101/delivery`), where the mock denies it.
- `design.py check` was not re-run in this round (the spec's 18 Nov run stands).
- Shared InlineDecide is not used by this line; F-35's stale-409 fix (971bf73a) is not duplicated and nothing here touches it.
- No `/me` read added under `features/workspace` or `features/response`.

## Acceptance criteria
1. [~] Fidelity: all 8 boards 100% coverage after exceptions; visual 74.2 to 87.7, all below 90. Each carries a proposed D-83 waiver (floor 70 met), unsigned. See Fidelity.
2. [x] Exceptions limited: 23 entries plus 8 waivers, each tied to a Conflicts number, none covers data the response supplies. All marked "builder proposal, pending design engineer".
3. [x] Row opens W-3704, one-line P-0101 diff: unit tests, e2e, `git diff`.
4. [x] Four states: `support-handover.test.tsx` (1440 and 390), e2e at both widths; grep for the board strings in `src` is empty.
5. [x] Hold has no controls, no POST: component test, e2e.
6. [x] Publish once, claims nothing before the re-read: component test with a held re-read; e2e with the mock log (one send).
7. [x] Uncertain paths W-3706, W-3707, W-3708, network failure, reconcile outcomes: component tests, e2e, mock test.
8. [x] Draft v2 is queued then "Drafting v2", gaps stay OPEN: component and e2e.
9. [x] Form from the response only; W-3709 unavailable; unlabelled actions offer nothing: component tests (pm and finance_lead).
10. [x] Upload then one POST with the body, no claim unless asked, double press once, Record off without proof, tick or gap: component and e2e.
11. [x] No success before the re-read on 200, record-then-fail, 500, network, 409, 422: component tests; e2e for record-then-fail, 409, 403.
12. [x] Recorded under the PM's name; grep for "logged in / signed in as / Support sent" is empty.
13. [x] Verified only from `status.tone`: W-3711 and a tone-changed W-3705 copy.
14. [x] Unknown, not zero; "Gaps · 2" only from the label.
15. [x] Links only from data (`../x` and no link).
16. [x] 401, 403, 404 on the read, 403 on the write, ceo on the Delivery tab.
17. [x] Phone: e2e measures 44px targets including `.resp-chip__remove`; Record reply pinned.
18. [x] Axe at 1440 and 390 on W-3701 to W-3705, W-3702, W-3709, the 422 form, W-3706 after Publish, no-access; remove button named; focus returns to the page heading.
19. [x] `@/components` and F-18 parts only; the CSS diff has no colour literals.
20. [x] Mock test: all fixtures and sidecars validate once `links` is removed; 422 `gaps` both ways; T-3709 is 403; repeat key replays.
21. [x] No change in `src/api`, `apps`, `architecture`, `design`, `src/shell`, `src/features/decide`, `src/features/projects` or protected paths. `gaps` exists only as the PROPOSAL field.
22. [x] Existing tests green; the only assertion edits are the Handover expectations (plus the two list/validation edits above, which add and loosen nothing a fixture could hide).
23. [x] This file carries the held section.

## Fidelity
App 4975 on a production build (built with `API_ORIGIN` set to the mock on 4974), mock 4974, persona pm. Record boards scored from the driver-frozen pages (`drive-states.mjs`).

| Board | Width | Coverage | With exceptions | Visual |
|---|---|---|---|---|
| SCR-48-desktop | 1440 | 59.5 | 100 | 78.1 |
| SCR-48-desktop-gaps | 1440 | 64.9 | 100 | 83.0 |
| SCR-48-desktop-received | 1440 | 63.9 | 100 | 77.8 |
| SCR-48-desktop-record | 1440 | 63.6 | 100 | 74.2 |
| SCR-48-mobile | 390 | 55.6 | 100 | 82.4 |
| SCR-48-mobile-gaps | 390 | 80 | 100 | 87.7 |
| SCR-48-mobile-received | 390 | 40 | 100 | 74.8 |
| SCR-48-mobile-record | 390 | 75 | 100 | 82.2 |

Pending (design engineer): sign or refuse the 23 exceptions and 8 D-83 waivers in `delivery/features/F-40/fidelity-exceptions.json` (all "builder proposal, pending design engineer"); decide Conflicts 1 to 5 (the board's "No · below the rule's threshold" is only a sample fixture; Gaps is one line-per-gap box; the "genuine" tick is added). Servers on 4974 and 4975 are stopped.

## Validation
- `bash delivery/checks.sh` under the shared lock: exit 0 (lint, typecheck, 2909 unit tests, build) at 534a0269 plus later commits that changed only e2e files (eslint and tsc rerun clean).
- `npx playwright test e2e/support-handover.spec.ts e2e/delivery-release.spec.ts` (ports 4976/4977, Africa/Lagos): 57 passed. Earlier full run of support-handover, delivery-release, delivery-hypercare, engagement-planning, workspace and response specs: 150 passed, 3 failed (the Handover sub-nav expectation, a strict-mode locator, and the ceo check); all three fixed and the two affected specs rerun green. `frontend/test-results` deleted.
- `df -h /` 4.0 GB free at the end.

## Blocked
Not blocked.
