VERDICT: PASS
REVIEWER: qa
COMMIT: 62ed73aa419d1e6a2bc990125bfd517422a778d3
AUTHORITY: delivery integrated QA

## Summary
- I ran a production build of this head (`API_ORIGIN=http://127.0.0.1:4876 FRAME_FIXTURES=1 npm run build && npx next start -p 4877`) against my own contract mock (`MOCK_PORT=4876 node mock/server.mjs`). I drove pages in Chromium (session `f-32-qa`, scripts `qa.cjs` and `qa2.cjs` in the QA scratch folder) and called the API directly with curl through the app's `/api/v1` proxy.
- Every journey in spec.md passed at 1440 and 390, both success and failure paths. I found no blocking defect. The Delivery tab, the waiting, decision and ready release states, and the PMO decision through the F-16 page (claim, then approve, or return with a note) all come from the data. "Release ready" appears only after the re-read item says so.
- Targeted vitest: 18 files and 874 tests passed. The spec's e2e set (`E2E_PORT=4878 MOCK_PORT=4879 npx playwright test` on delivery-release, workspace, work-item, decide, minutes, issue-detail, weekly, project-tabs and projects): 238 passed and 0 failed.
- Not proved: this is the contract mock only. No backend, real PMO Lead authority, real release check or deploy exists. The "PMO Lead", "Kemi Adebayo", "approved" and "Release ready" are fixture text, and the build.md "What is released" section says so. The tenant check is simulated by the mock's no-access ids (P-0099, W-1099), the `ceo` persona and `X-Mock-Scenario`. "Uncertain" was simulated by routing a decide response with `work_state: effect_uncertain`.
- Housekeeping: I stopped only my own PIDs (mock 92910, app 93156 and 93185). Both my build and the Playwright webServer rebuilt `frontend/.next` in the worktree. The shared 4872/4873 servers had already stopped when I finished, so whoever restarts them should rebuild with `API_ORIGIN=http://127.0.0.1:4872`.

## Journeys
1. **PM on the Delivery tab (SCR-43), 1440 and 390: pass.**
   - `/projects/P-0101/delivery` shows the tabs Journey, Delivery, Milestones 4, Documents 6, Money, Registers 6, Actions 9 (no counts at 390). Delivery is `aria-selected=true`.
   - Six rows appear, numbered 01 to 06. Release gates links to `/work/W-2503` and Go-live acceptance to `/work/W-2510`. The tags read Release ready (done), Accepted (done), Running (`psl-tag--waiting`, amber; UI-1-4), Archived and verified, Support listed 2 gaps (person), Not yet (neutral).
   - No "N of M" text appears. Ask Tola goes to `/assistant` and nothing is POSTed.
   - The sub-nav is shown at 1440 and hidden at 390.
   - axe found no violations, there is no sideways scroll, and every target is at least 44px at 390. `/projects/P-0101/planning` is still the 404 page.
2. **Release gate, default / decision / ready: pass.**
   - W-2501 (default) has no decision link. It shows "Waiting for PMO Lead" and "Only a PMO Lead can decide.".
   - W-2502 (decision) has "Approve for release" linking to `/work/W-2502/decide?task=T-2502`. Neither "Release ready" nor "Open go-live" appears.
   - W-2503 (ready) shows the status "Release ready", the green banner, the readiness note, Next and "Open go-live" (`/work/W-2510`).
   - W-2507 shows "Unknown" 3 times (Open issues value "Unknown"). No value is blank or "0".
   - W-2508 has no "Release ready", no green banner and no Open go-live (INV-AGENT).
   - No "Claim it first" text on any release item (UI-1-7d/UX-1-3). The line tab bar on W-2501 has 7 links with none current.
   - Each page was axe-clean, with no sideways scroll and 44px controls at 390, and sent no write.
3. **PMO Lead decides through the F-16 page, claim then approve: pass.**
   - Pressing "Approve for release" on W-2502 navigates only. The work page sent no write.
   - The F-16 page sent `POST /api/v1/tasks/T-2502/claim {"expected_revision":1}`. After "Approve v1" it sent `POST /api/v1/tasks/T-2502/decision {"expected_revision":1,"verdict":"approve"}`. Both carried `X-CSRFToken: mock-csrf-pm`, and there were exactly 2 writes.
   - The h1 then read "Release gates · build 1.0.0 is approved", and the decide page was axe-clean. Reloading `/work/W-2502` showed RELEASE READY, the banner "Release ready and verified on 25 Mar. This isn't a deployment…", the readiness note, Next and Open go-live → `/work/W-2510`.
   - Re-opening the decide page afterwards offers no enabled control and sends nothing.
   - On the API, a repeat decide answers 409 `stale_revision`, and the re-read item is `state: verified` with T-2502 `you_can_act: false`.
4. **Return with a note: pass.**
   - With an empty note, Return sent nothing (the claim was the only write) and the note message showed.
   - With a note, exactly one decide was sent: `{"expected_revision":1,"verdict":"return","note":"Rollback plan is missing from the release note."}`. The h1 read "…was returned".
   - `/work/W-2502` then shows no "Release ready". As the spec says, the mock leaves the item as it was, because the returned board is part 2.
5. **A person whose task has `you_can_act: false` sees no control: pass.**
   - W-2504, W-2505 and W-2506 as `pm`, `finance_lead` and `ceo` show no decide link. "Approve for release" and "Return with a note" are `aria-disabled` buttons with `aria-describedby`.
   - The reasons read "This decision needs a PMO Lead." (W-2504), "You prepared Release gates · build 1.0.0, so someone else must review it." (W-2505) and "This decision isn't open to you here." (W-2506). They are the same for every persona.
   - Opening `/work/W-2504/decide?task=T-2504` directly shows "NOT YOUR DECISION · This decision needs a PMO Lead.", no enabled Approve, Return or Reject, and sends no claim.
   - API: claim and decide on T-2504 answer 403 `forbidden`, and a claim without CSRF answers 403 `csrf_failed`.
6. **401, 403 and 404 with no leak: pass.** The scenario header was injected on the record read only, on `/work/W-2502`, `/projects/P-0101/delivery` and `/work/W-2502/decide?task=T-2502`, at both widths.
   - 401 shows "You're signed out" with `/accounts/login/?next=<route>`.
   - 403 and 404 render the same `main` text ("You can't open this work item" / "…this project").
   - `document.body.textContent` contains none of Lagoon, REL-0091, Release gates, patient app, Hypercare, Approve for release or Planning decision. axe was clean on all of them.
   - The `ceo` persona on P-0101, `/projects/P-0099/delivery` and `/work/W-1099` get the no-access view after one record read, with no further call.
   - Curl confirmed the API side: 401/403/404 on `GET /work/W-2502` and `GET /projects/P-0101`, and 404 on P-0099, W-1099 and ceo P-0101.
7. **409, 422, 5xx and uncertain on the decide: pass.** Each case sent exactly one decide and no automatic resend. In every case the work page afterwards shows YOUR DECISION and no "Release ready".
   - 409: shows the F-16 stale view ("A newer version arrived while you were reading").
   - 422: keeps the decision form, not approved.
   - 500, 503 (HTML body), network abort and timeout: show "We couldn't confirm your decision. We've reloaded…", with h1 "Planning decision", not approved.
   - Uncertain (`work_state: effect_uncertain`): shows "NOT CONFIRMED" and "…: result not confirmed".
   - API: a blank return note answers 422 `note`, a bad verdict 422 `verdict`, and `expected_revision: 0` 422.
8. **Phone 390, 44px targets, no sideways scroll: pass.**
   - Delivery tab, W-2501, W-2502, W-2503, W-2504 and W-2507: `scrollWidth <= innerWidth`, and every visible button, tab and `a.psl-btn` in main is at least 44px. The e2e checks the same.
   - The known 24px History link on the shared F-30 frame (UI-1-10, UX-1-2) is carried and is not this feature's code.
9. **axe at both widths: pass.** No violations (wcag2a/2aa/21a/21aa/22aa) on:
   - the Delivery tab, and its empty state (e2e);
   - W-2501, W-2502, W-2503, W-2504 and W-2507;
   - the decide page;
   - the no-access, 401, 403 and 404 views;
   - W-2901, W-2411 and W-2201.
10. **Other lines unchanged: pass.**
    - W-2901 (minutes) keeps `work-columns` (no `--lone`) and its "Open the decision" link to `/work/W-2901/decide?task=T-2901`.
    - W-2411 (issue) and W-2201 (weekly) keep their layout, gain only the Delivery tab in the line tab bar, and show no new disabled control or "isn't open to you here" sentence.
    - axe was clean at both widths with no sideways scroll.
    - The minutes, issue-detail, weekly and workspace e2e specs are in the 238 passing.
11. **Nothing claims a release happened unless the response says so: pass.** "Release ready" appeared only on W-2503 and on W-2502 after the mock answered `work_state: verified`. It never appeared after a failed, stale, uncertain or returned decide, nor on W-2508.

## Findings
1. QA-2-1 | non-blocking | low | frontend | After the approve, the re-read W-2502 (`W-2502.approve.json`, T-2502 `cannot_act_reason: "already_decided"`) still shows the "Planning decision" panel reading "Only a PMO Lead can decide.". That reads as if the decision is still open. The cause is the shared `TaskPanels` (`frontend/src/features/work-item/WorkItemOverview.tsx:497`, unchanged from base), which ignores `cannot_act_reason`. The F-16 page already has the "This decision has already been made." copy (`decide/DecideStates.tsx:41`). This is a frame follow-up and does not affect this feature's acceptance criteria.
2. QA-2-2 | non-blocking | low | integration | The spec lists `src/features/work-item/**` as shared read only, but round 2 edits `WorkItemOverview.tsx` and `work-item.css` (`work-columns--lone`, scoped to `line_key === 'delivery_release'`). This is not in AC-22's forbidden list, and I confirmed W-2901, W-2411 and W-2201 unchanged. It should still be noted for the merge with F-31 and F-33, which render through the same frame.
3. QA-2-3 | non-blocking | info | backend | On the mock, a return on T-2502 leaves the item unchanged: `you_can_act: true`, revision 1, and Approve for release is offered again. A second decide would therefore be accepted. This is expected under the spec (the returned board is part 2). A real backend must close or advance the task on return.

## Verified
No QA findings were open from round 1. I checked these round-2 fixes for their behaviour:
- UI-1-4 | verified | The Hypercare tag renders `psl-tag--waiting` ("Running") at 1440 and 390.
- UI-1-5 / UX-1-1 | verified | W-2501 is the only one of the tested items with `work-columns--lone`. W-2901, W-2411 and W-2201 keep `work-columns`.
- UI-1-6 | verified | W-2501 shows "Waiting for PMO Lead" and "Only a PMO Lead can decide.", with no decision control.
- UI-1-7(d) / UX-1-3 | verified | No "Claim it first" on W-2501 to W-2507. The F-16 page still claims once on open, before the decide (the request log above).

## Update for head 62ed73aa (diff 5bab76ae..62ed73aa)
- Read the diff 5bab76ae..62ed73aa on the shared files (Steps, Workspace, Sections, WorkItemView, AssignForm, workspace.mjs, mock-contract test): F-31 additions sit beside the F-32 release-gate paths without changing them.
- Orphan-step rule checked: a step whose task is in tasks[] with you_can_act true still links to the decision page; only a missing task or you_can_act false is unavailable.
- Ran engagement-planning, release-gates, delivery-*, workspace* and issue-detail tests in the worktree: 8 files, 230 tests passed.
- Verdict unchanged.
