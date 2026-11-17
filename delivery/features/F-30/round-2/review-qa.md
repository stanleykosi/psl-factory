VERDICT: CHANGES
REVIEWER: qa
COMMIT: 48ba8f7a6f3cf40c6e185d87dfe9ff4fbabd4c83
AUTHORITY: integrated QA (frontend against the contract mock)

## Summary
- Tested this head (base dlv-00 8524af3c plus the branch) on the coordinator's production build: app http://localhost:4833, contract mock 4832, `FRAME_FIXTURES=1`. Personas pm, finance_lead, ceo and none. The whole flow ran through the real Next proxy and the mock; Playwright scripts are in the scratchpad `qa-f30/qa1.cjs`..`qa7.cjs`. The mock was reset after the run.
- e2e: `MOCK_PORT=4832 npx playwright test -c <scratch>/pw.qa2.config.mjs e2e/issue-detail.spec.ts e2e/workspace.spec.ts e2e/work-item.spec.ts e2e/project-tabs.spec.ts e2e/weekly.spec.ts e2e/minutes.spec.ts` gave **165 passed (4.1 m)**, so the shared-file regressions are green. Unit: `npx vitest run tests/issue-detail.test.tsx tests/issue-assign-mock.test.ts` gave 41/41. The spec greps for criteria 1, 3, 16 and 21 found nothing.
- An earlier run on 4834/4835 failed 24 tests. That was my harness, not the product: `next start` serves the API origin baked into `.next/routes-manifest.json` (4832), so the 4835 app wrote to 4832 while the tests read the log on 4834. Anyone who runs e2e on separate ports needs their own build.
- Everything works except one failure. The four states, the controls per persona, the three writes, the escalation hand-off, the failure paths, access, the register row and the phone Drawers all match the spec. The failure is criterion 12 for the shared step forms: an empty "Post update" leaves focus on the submit button, and neither step form shows a top summary.
- Not proved:
  - Real backend authority. The mock's E-WORK-ASSIGN accepts persona `none` with its own CSRF token, and it has no tenant concept, so "wrong tenant" was tested only as a 403/404 on the read and on the write.
  - The step `uncertain` result and its reconcile panel. No step script reaches it; it is covered by unit tests only.
  - The 60 s fake-time 409 rule. Unit tests only.
  - Real escalation creation. The mock's E-WORK-START answered with W-1407.

## Findings
- QA-2-1 | blocking | medium | frontend | Criterion 12 is not met for the step forms ("Post update", "Record a reply").
  - Expected: submitting empty shows the message under each field, a top summary, and focus on the first invalid field.
  - Actual on W-2411, 1440 and 390, by click and by Enter: the messages under "Update type" and "Update" appear, but focus stays on `<button type="submit">Post update</button>` (a focusin trace shows nothing else got focus) and no summary is drawn.
  - Cause: `focusFirst` in `frontend/src/features/workspace/StepForm.tsx:227-236` matches the first `[data-field] [aria-invalid="true"]` element. For a choice field that is the wrapper `<div aria-invalid="true">`, which cannot take focus, so `.focus()` does nothing and the loop returns early.
  - On W-2412 "Record a reply", focus does reach the textarea, but there is still no summary.
  - "Set an owner" (AssignForm) is correct: it shows "1 thing to fix" and focuses the Owner combobox.
  - Tests: `tests/issue-detail.test.tsx` checks summary and focus only for Owner (line 392); nothing covers the step forms.
  - Fix: focus the first focusable control inside the invalid field, add the same summary the assign form has (or have the spec's owner amend criterion 12 for the shared StepForm), and add a component test for both step forms.
- QA-2-2 | non-blocking | low | frontend | The candidate option for a team reads "Engineering / Team · recorded by PM · Team" and the outside party reads "Client · recorded by PM · Outside party". When the fixture's `role` is already "Team", the page's own kind word repeats it. Spec item 11 says kind should appear "as the backend words it", and BACKEND-HANDOFF lists these words as frontend wording. Either drop the kind word when it equals `role`, or let the backend word it. `frontend/src/features/workspace/AssignForm.tsx:58-59`.
- QA-2-3 | non-blocking | low | frontend | The e2e test "an unknown issue is the same not-open view with no name" (`e2e/issue-detail.spec.ts:143`) passes without testing anything. The mock serves W-1001 for any unknown id (`GET /api/v1/work/W-2499` returned "Lagoon Health · Milestone 2 invoice", which the page draws as an h1). The test only checks that the issue title is absent. Criterion 15 does hold: I injected `x-mock-scenario` 403 and 404 on the item read only, and both showed the same "NO ACCESS · You can't open this work item" view with no title, owner or ISS id. The e2e should use the scenario header on the item read instead.

## Verified
- UI-1-1 | verified | In the browser, W-2411 draws the waiting tone and W-2412 the stopped (red) tone. Statuses come from the response and are the same for pm, finance_lead and ceo.
- UI-1-2 | verified | W-2413 at 1440 has no "See all exceptions" button. The F-22 workspace e2e (W-2001..W-2008) is green.
- UI-1-3 | verified | W-2413 at 390: "Set an owner" is pinned and 44 px high, and it opens a full-height (844/844) Drawer.
- UI-1-4 | verified | Not re-scored. The e2e and axe runs on the four states at 1440 and 390 pass with the facts strip.
- UI-1-5 | verified | Not re-scored. The layout passes e2e and axe; placement is the UI reviewer's check.
- UX-1-1 | verified | e2e at 390 asserts the "Project" link goes to `/projects/P-0101`. It passed.

## Evidence (exact requests and results)
- **Controls per persona (criterion 4)** (`qa1.cjs`):
  - For pm, finance_lead and ceo alike: W-2411 shows ["Post update"]; W-2412 shows ["Record a reply","Raise an escalation"]; W-2413 shows ["Set an owner"]; W-2414 shows []. The only API calls are `GET /api/v1/me`, `GET /api/v1/work/<id>` and the bell feed.
  - Persona `none`: no h1, no buttons, and only `GET /api/v1/me` is called.
- **Post update (criterion 8)** (`qa2.cjs`):
  - The three Update types (Acknowledge, Started, Progress update) start unselected.
  - A double click sent one `POST /api/v1/work/W-2411/steps {"expected_revision":3,"step":"post_owner_update","idempotency_key":"<uuid>","inputs":{"update_type":"progress","update":"Fix verified on 2 of 3 models."}}` with the CSRF header. The input was padded with spaces and arrived trimmed.
  - The page showed "Done: update posted." and the re-read "Owner update · recorded by PM". The mock log shows `sends` = 1 for that key.
- **Step failures (criterion 13)** (`qa2b.cjs`, `qa5.cjs`):
  - 422: "Check the highlighted fields…", entries kept.
  - 409: "changed while you were working", entries kept.
  - 500 (fulfilled) and network reset: "couldn't confirm this step", "Try again" offered, and Try again sent the same idempotency key.
  - None of them showed "Done".
- **Record a reply (criterion 9)**:
  - Empty submit sends nothing and shows "Add reply to continue."
  - Valid submit sends one POST `{"expected_revision":3,"step":"record_reply",...,"inputs":{"reply":"Engineering is on it."}}`. The page showed "Done: reply recorded." and the re-read "Owner reply · recorded by PM".
- **Raise an escalation (criterion 10)** (`qa5.cjs`, `qa7.cjs`):
  - Opens "START WORK · Escalate and communicate" prefilled with "Project Lagoon Health · patient app" and "From issue ISS-0233 · Login fails on older Android phones". No POST is sent, and the page says nothing was started.
  - Only the drawer's own "Raise escalation" posts `POST /api/v1/work {"line":"escalation",...,"intake":{"project":"P-0101","from_issue":"ISS-0233","escalate_to":"internal"}}` and moves to W-1407.
  - Existing Start work behaviour: a first press without "Escalate to" goes to the server and comes back as a 422. That is not this feature's code.
- **Set an owner (criteria 11 and 14)**:
  - The options are exactly Tunde Bello, Engineering and Lagoon Health support, with none preselected.
  - A double click sent one `POST /api/v1/work/W-2413/assignment {"expected_revision":2,"person_id":"T-ENG","note":"Engineering takes it"}`. The page showed "Owner set: Engineering", the re-read status "FOLLOW-UP STARTED", and no "Set an owner". The log has one written assignment.
  - `psl_mock_assign=invalid`: 422 under Owner, entries kept.
  - `stale`: 409, stale sentence, entries kept.
  - 500 and network: "Not recorded…", Try again offered after the re-read, nothing written.
  - 403 on the write: the not-open view. 401: signed out.
- **Direct API checks on the mock** (`qa-f30/api.sh`):
  - E-WORK-ASSIGN: no CSRF → 403; another persona's CSRF → 403; unlisted person_id → 422 person_id; extra key → 422; 2001-character note → 422 note; non-JSON → 422 body; stale revision → 409; W-2499 → 404; scenario 401/403/404 → as declared.
  - The same body sent again after success → 422, so no second assignment.
  - Mock assign cookies: `uncertain` gives 500 and logs written=false; `uncertain_written` gives 500 and logs written=true.
  - E-WORK-STEP: a repeated key replays the first answer (`replay: true`); an unoffered step gets 404 "That step is not offered on this item."
- **Access (criterion 15)**:
  - Item-read 401 → "You're signed out" with link `/accounts/login/?next=%2Fwork%2FW-2411`.
  - 403 and 404 → identical "NO ACCESS" text, with no title, owner or reference.
- **Phone at 390 (criterion 18)** (`qa6.cjs`):
  - "Record a reply", "Set an owner" and "Post update" each open the full-height Drawer with labelled fields.
  - Escape and Cancel close it and return focus to the opener. Every target is at least 44 px and there is no sideways scroll.
  - Each submit closes the Drawer and shows its notice.
- **Register row (criterion 6)**: e2e passed. `/projects/P-0101/registers`, then the title, leads to `/work/W-2411` showing "Engineering (recorded by PM)", with 6 tab links and none marked current.

## Notes
- The fix for QA-2-1 touches the shared F-17 `StepForm`. Re-run `e2e/workspace.spec.ts`, `weekly.spec.ts` and `minutes.spec.ts` after it. All three were green at this head.
