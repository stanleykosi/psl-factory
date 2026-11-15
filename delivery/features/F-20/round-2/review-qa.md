VERDICT: PASS
COMMIT: 1bf933da30fd5e895b5b35f48e89149984c4a305
REVIEWER: qa
AUTHORITY: integrated QA

## Re-confirmed on the synced head
- Head 1bf933da30fd5e895b5b35f48e89149984c4a305 (worktree confirmed with `git rev-parse HEAD`). The only change since 777d9a3f is the merge of origin/dlv-00-delivery-setup, and the only F-20 file it touched is `frontend/src/features/setup/SetupFrame.tsx`.
- Ran `cd /Users/Hunchoo/psl-factory-worktrees/f-20/frontend && E2E_PORT=4671 MOCK_PORT=4672 npx playwright test e2e/setup-templates.spec.ts --reporter=line`: 11 passed (49.2s) in real Chromium against the contract mock. That includes phone test 9 (one h1 "Templates", the "← Setup" bar link named "Back to Setup", no link inside `main`, no side scroll, axe clean) and phone test 10 (upload works inside the card, axe clean). Desktop test 2 covers the upload 200: one POST, the new version, focus and the announcement.
- "← Setup" destination: `useSetupPhoneBack` now sets `href: '/setup/rules'` (SetupFrame.tsx line 75), replacing `/setup/roles`. The e2e asserts the link label and role but not its href, so the destination is confirmed from the source, not by a click-through. The earlier "goes to /setup/roles" line below is superseded by this.
- Cleanup: `test-results` deleted, worktree has no changes, and ports 4671 and 4672 are free.
- Findings QA-2-1 to QA-2-3 are unchanged and non-blocking. The merge touched nothing they depend on.

## Summary
- **What ran.** I made a production build in the worktree (`next build` with `FRAME_FIXTURES=1` and `API_ORIGIN=http://127.0.0.1:4672`) and served it with `next start -p 4671`. It ran against the contract mock (`MOCK_PORT=4672 node mock/server.mjs`). I drove 27 journeys in headless Chromium session `f-20-qa` (timezone Africa/Lagos) at 1440 and 390. All 27 passed. Script: `/private/tmp/claude-501/f20-qa/qa.mjs`. Output: `/private/tmp/claude-501/f20-qa/qa.out`. I also called the mock directly with `curl`: no-CSRF 403, unknown-id 404, empty-file 422 naming `filename` and `content_base64`, pm 403, wrong-revision 409, 200, a repeat 409, the list showing the bump, readonly 403, the cursor page and reset 204. `npx vitest run tests/setup-templates-mock.test.ts tests/setup-templates.test.tsx`: 54 passed. Disk had 5.2 GB free. I stopped my servers by PID (70476, 70401, 70057). The worktree is clean.
- **Proved on the mock:**
  - The list shows the 8 rows in the order returned, 8 TEST TEMPLATE tags, the banner, "8 TEMPLATES · 8 TEST AS OF 12 NOV, 10:40", one h1, and the tab title.
  - Search filters the loaded rows only and sends 0 requests. "No templates match" shows when nothing matches.
  - Show more sends `cursor=o:50` and appends rows (50 to 60). "SHOWN" and "Searching the 50 shown" appear while more rows exist. A failed page keeps the 50 rows and offers Show more again.
  - Upload 200 sends one POST with exactly `expected_revision, filename, content_base64, note`. The bytes decode to the multi-byte file. One reload follows, the panel closes, the row shows "Version 2" from the reload, focus lands on the row name, and the polite status announces "Version 2 uploaded for Invoice".
  - A double click in one tick sends 1 POST and shows "Uploading…".
  - A zero-byte file and a 2001-character note are refused with 0 POSTs, `aria-invalid` and a described message.
  - 409 shows the API message in `role="alert"`, reloads, closes the panel and clears the file and note. The next press needs a new file and carries the reloaded `expected_revision: 2`.
  - 422 marks the file and the note (`aria-invalid` and `aria-describedby` with the server text). The message sits in a `role="alert"` callout, the entries are kept and nothing reloads.
  - A 500, a 503 or an aborted request sends 1 POST, reloads once and shows a `role="alert"` that takes focus.
  - When the effect landed but the response was lost (`route.fetch` and then abort), the page shows "The upload went through." (`role="status"`) and focus goes to the row.
  - When the write and the reload both fail, Upload version is locked. Try again only reads (0 POSTs) and then unlocks.
  - 403 on the write after the rights were removed shows "Your role does not allow this." as an alert. After the reload there are 0 Upload controls.
  - 403 on both the write and the read gives the not-open view, with one h1 "Setup" and no template name.
  - 401 shows "Sign in" with `next=%2Fsetup%2Ftemplates`.
  - Read-only data shows no Upload control and no disabled button. The empty list shows the empty state with no table or count. Persona pm sees the not-open view with 0 template calls.
  - Keyboard order in the panel is File, Note, Upload version, Cancel. Escape closes the panel and returns focus to its button.
  - On the phone: one h1 "Templates", 8 cards, the note, then "AS OF" under the note, and no sideways scroll. The bar link "← Setup" (aria-label "Back to Setup") goes to `/setup/roles`, and `main` has no back link of its own. Upload 200, 409, 422 and 503 behave as on desktop.
  - axe found 0 violations on the list, the open panel, 409, 422, empty, read-only, not-open and the phone views.
- **Screen-reader announcement of save results (the F-19 gap).** Every save outcome is announced:
  - 200 uses the polite `role="status"` and focus moves to the row.
  - 409, 403, uncertain and unchecked use `role="alert"` (`OutcomeNotice`, which takes focus).
  - "went through" uses `role="status"`.
  - 422 uses an inline `role="alert"`.
  - Two non-blocking gaps remain: focus after a 422 (QA-2-1) and the empty-list case (QA-2-2).
- **Not proved without a real backend.** D-TEMPLATES-VIEW is still `proposed`. These are mock behaviour only:
  - every field shape, the undeclared `cursor` query, the 422 field names and the 409 rule;
  - file storage, file-type and size policy, virus scanning and 413 handling;
  - whether `expected_revision: 0` is valid (the mock refuses it, per TECH-1-1);
  - a real CSRF or session flow.

  The `test_template: false` path is covered only by component stubs, because the mock never returns false, by design. I created the 500, 503, abort, 401 and lost-response cases with Playwright `route` at the browser boundary. They are not real network failures.

## Findings
- QA-2-1 | non-blocking | low | frontend | **After a 422, keyboard focus drops to `<body>`.** "Upload version" gets `disabled={busy}` (`frontend/src/features/setup/TemplateUploadPanel.tsx:113`), so Chromium drops focus during the request. The 422 path does not move focus back (`TemplatesView.tsx:132-133`). This happened at 1440 and 390. The `role="alert"` callout is still announced, so the result is not silent. A keyboard user must still Tab back into the panel. Expected: focus goes to the first invalid field or to the callout. Every other outcome moves focus. This is the same pattern as F-19 QA-2-2.
- QA-2-2 | non-blocking | low | frontend | **A 403 or 404 on the write that empties the list shows no message.** The `rejected` notice is rendered inside `notices`, and `notices` exists only in the non-empty branch (`TemplatesView.tsx:223-238`, `308-322`). In the browser I pressed Upload and the mock answered 404. The reload returned `items: []`, and the page silently became "No templates to show.". No alert appeared and focus went nowhere. This is an edge case, because the person's only template has to disappear. Expected: render `notices` in the empty branch too.
- QA-2-3 | non-blocking | low | frontend | **The mock counts an unknown `versions` as zero.** `store()` uses `(row.versions ?? 0) + 1` (`frontend/mock/templates.mjs`, the `store` function). Only Closure report carries `versions` in `desktop.json`. After the first upload, Invoice reads "Version 2 · PDF 1 version · Changed by Ada Okafor, 15 Nov", which is wrong sample data. AGENTS.md says unknown values are not zero. Expected: leave `versions` out when it was unknown. The UI is correct, because it shows exactly what it is given. This affects mock data only.

## Verified
- UI-1-2 | verified | In the browser at 1440, after an upload the Invoice row reads "Invoice · Version 2 · PDF · 1 version · Changed by Ada Okafor, 15 Nov" inside the Document cell. The action cell holds only the Upload control. Read-only rows have no Upload control and no disabled button.
- UI-1-3 | verified | At 390 the phone reads, in order: "Templates", "All 8 are test templates until PSL supplies its own.", "AS OF 12 NOV, 10:40", then the first card (Invoice).
- UI-1-4 | verified | `tests/setup-templates.test.tsx` passes (54 tests across the two template suites), including the history-on-every-row test.
