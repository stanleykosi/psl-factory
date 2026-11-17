VERDICT: PASS
REVIEWER: qa
COMMIT: cc694876c715f0c927f3879491eb9ede706c4f31
AUTHORITY: integrated QA

## Summary
- Tested the head on the running stack: app on :4794 (production build, FRAME_FIXTURES=1) with the contract mock on :4793 as user `pm` (personas `ceo` and `finance_lead` used for the persona check). I drove pages in a Playwright Chromium session (f-28-qa) and called the mock endpoints with curl.
- e2e: `e2e/minutes-end.spec.ts` and `e2e/minutes.spec.ts` (the F-23 regression check) gave **44 passed, 0 failed**. Component and mock tests: `tests/minutes-end.test.tsx`, `tests/minutes-end-mock.test.ts`, `tests/mock-contract.test.ts` and `tests/minutes*` gave **404 passed**.
- Both journeys reach their end views. W-2301 with Internal and confirm ends on "Filed · Internal"; with Client it ends on the drafted view. Approving W-2309 on the decide page ends on "Published · Received" with "Sent to". Receipts are shown per person. After an uncertain send, reconcile is the only action: one POST to `/actions`, nothing to `/steps`, `/claim` or `/decision`, and Record stays disabled after the uncertain result. Signed-out, forbidden and wrong-tenant states show no item data.
- **Not proved: this is a contract mock only.** No backend, PostgreSQL, real send, email or WhatsApp provider, filing or action records exist for this line. Every "emailed", "delivery confirmed" and "Received" is fixture text. Duplicate-send protection is proved only on the mock's idempotency map. "Integrated" here means frontend plus contract mock, not frontend plus Django, so this pass is not INTEGRATED_QA_PASSED evidence for a backend.

## Findings
- QA-2-1 | non-blocking | low | integration | The W-2313 mock accepts an assign-owner step with no owner and reports success. The `assign_owner` field is `required: false`, and `W-2313.steps.json` answers every call with 200 "Done: owner assigned.". Pressing Assign owner with no owner chosen sent `{"step":"assign_owner","item_ids":["A-2"],...}` with no `inputs`, and the mock reported success. Expected per criterion 13: the backend refuses a blank owner with a 422. The frontend side is correct: the blank owner is left out, and the 422 path works (forced with `X-Mock-Scenario: 422` at 390: form kept open, "Tunde Bello" kept, alert shown). This is a fixture gap, and the step is already flagged keep-or-drop (TECH-1-2). `frontend/mock/fixtures/work/W-2313.steps.json:1`, `frontend/mock/fixtures/work/W-2313.json` (workspace.steps[0].fields[0].required).

## Verified
- UI-1-1 | verified | On :4794, "Open actions" on W-2310, W-2311 and W-2312 is an `<a>` with href `/projects/C-0211/actions` and the button-link class. The e2e test "Open actions goes to the project Actions tab" passed.
- UI-1-2 | verified | At 390, the e2e checks passed on W-2310 to W-2314: the table frame does not scroll sideways (scrollWidth <= clientWidth) and cells are labelled Action, Owner, Due and State. The F-23 tables (W-2301 to W-2308) have no tag column, so they are not stacked, and all of `e2e/minutes.spec.ts` passed.
- UI-1-3 | verified | This is a factory file, not code. `fidelity-exceptions.json` carries the added entries. There is no behaviour to test; the waivers are still pending the design engineer.

## Journeys exercised (commands and results)
- **Load, no writes.** Opened `/work/W-2310`, `W-2311`, `W-2312` and `W-2314` at 1440. Status tags: "Filed · Internal", "Published · Received", "Published · Delivery unconfirmed" and "Published". Each page made 0 non-GET requests, all to host `localhost`, and 0 requests in 5 s idle.
- **Per-person receipts.**
  - W-2311: Ada Okoye email RECEIVED 10 Nov 17:31; projects inbox email RECEIVED 17:32.
  - W-2312: Ada Okoye RECEIVED; projects inbox UNCERTAIN 17:32; Femi Daniel whatsapp NOT YET (no time).
  - "Delivered" and "delivery confirmed" appear only in the returned sentence and tag of W-2311.
  - `grep -rnE "Delivered|delivery confirmed" frontend/src/features/workspace` found nothing.
- **OWNER NEEDED and Unknown.** W-2311, W-2312 and W-2314 show the ownerless row as "No owner yet · Unknown · OWNER NEEDED". W-2314 has no links and no buttons.
- **Reconcile lock (INV-RESEND), W-2312.**
  - Chose "I can't tell yet" and pressed "Record and continue". This sent exactly one POST: `/api/v1/work/W-2312/actions` with `{"expected_revision":9,"action":"reconcile","outcome":"unknown"}`.
  - The mock answered 501 (no sidecar). The page shows "We couldn't confirm your answer. Reload the work item…", and the Record button becomes disabled. Total POSTs stayed at 1.
  - After a reload, reconcile is still the only panel and 0 POSTs went to steps, claim or decision.
  - Direct calls:
    - `POST /api/v1/work/W-2312/steps {"step":"send",...}`: 404 "That step is not offered".
    - Reconcile with `expected_revision:3`: 409 stale_revision.
    - Bogus outcome: 422.
    - Reconcile on W-2311 (not allowed): 422.
    - The item stays `effect_uncertain` rev 9.
- **Open the minutes.** The e2e run showed one GET `/api/v1/documents/D-2304/versions/1` and the "Test template" tag. curl of the same document returned 200.
- **Signed out, forbidden and wrong tenant.** Forced the scenario on the W-2311 GET only (page.route adding `X-Mock-Scenario`), at 1440 and 390:
  - 401 shows "You're signed out. Sign in" with `/accounts/login/?next=%2Fwork%2FW-2311`.
  - 403 and 404 show "NO ACCESS · You can't open this work item".
  - Visible text contains none of W-2311, Lagoon, C-0211, Kemi or Minutes. The id appears only in the RSC route payload of the URL the user typed.
  - With the scenario cookie set on every call, the shell shows its own signed-out, no-role or load-error state.
- **CSRF.** A POST to steps without the token returned 403 csrf_failed.
- **Personas.** `pm`, `ceo` and `finance_lead` see identical controls on W-2311 (`Open actions`) and on W-2312 (`Open actions`, `Open the minutes`). The diff adds no `/me` read under `features/workspace`.
- **Owner assignment, W-2313.**
  - Assigning Tunde sends one POST with `expected_revision` 8, a UUID key, `item_ids ["A-2"]` and `inputs.owner "U-TUNDE"`.
  - 409 shows "This changed while you were working. Showing version 8." and reloads the item.
  - 422 keeps the form and its input.
  - Sending the same key twice to the mock gives 200 and 200, with `sends` = 1 and the second entry marked `replay`.
- **Reaching the end views (e2e, 1440 and 390).**
  - Internal: one `/steps` POST with `{step:"confirm_minutes", inputs:{audience:"internal"}}`, 0 to `/decision`, ending on "Filed · Internal".
  - Client: ends on the drafted view.
  - W-2309: approve sends one `/decision` and at most one `/claim`, 0 to `/steps`, then shows "Published · Received" and "Sent to" with no writes on the work page.
- **Accessibility (e2e).** No axe violations (wcag2a/aa, 21a/aa, 22aa) on W-2310 to W-2314 at 1440 and 390. Also checked there: one h1, no sideways scroll, visible focus, phone controls at least 44 px, no wrapped labels, no animation with reduced motion.
- **Scope checks.** No change under `frontend/src/api`, `apps`, `architecture`, `design` or `src/shell`. No raw colour in the CSS diff. No new "resend" or "send again" text.

## Notes
- My first e2e run had 5 failures, and they came from my setup, not from the head. The production build fixes the API rewrite to mock :4793 at build time (`.next/routes-manifest.json`), so `API_ORIGIN`/`MOCK_PORT=4795` did not take effect, and my manual journeys reset the same mock at the same time. I reran with the spec's `MOCK_PORT=4793` and nothing else running: 44 passed. Anyone reusing a prebuilt `.next` should point the spec at the mock port the build was made with.
- Commands:
  - e2e: `cd frontend && MOCK_PORT=4793 E2E_PORT=4796 npx playwright test -c <scratch>/qa/pw.config.ts minutes-end.spec.ts minutes.spec.ts` (`next start` only, no rebuild).
  - Unit and mock tests: `npx vitest run tests/minutes-end.test.tsx tests/minutes-end-mock.test.ts tests/mock-contract.test.ts tests/minutes`.
- I reset the :4793 mock state afterwards (`POST /__mock/reset`: 204). The :4794 and :4793 servers are still running, and the helpers I started on :4795 and :4796 are stopped. The worktree is clean.
