VERDICT: PASS
COMMIT: 14d6953dd4a39c4ceed7f77dba5a77fb2ecf65cb
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (frontend + contract mock)

## Summary
- **What was tested.** The shared production build of head 14d6953 ran on http://localhost:4911 (`next start`, cwd `f-09/frontend`, `.next/BUILD_ID` dated after the head commit). It proxies `/api/v1` to the contract mock on http://127.0.0.1:4912. I did not start or stop either server. I reset the mock (`POST /__mock/reset` → 204) before and after every journey.
- **How.** One headless Chromium run made 187 checks; 186 passed. I also made 41 direct API calls and ran a separate retest of the fixes. Recording a client response (W-1601) and a SOW signature (W-1602) with proof works at 1440 and 390: validation, success, reopen, the claim-first path (W-1605), the fallbacks when fields are absent (W-1606), and the no-case item (W-1609). So do the work item entry link, the reconcile panel (W-1603/1604/1607) and every specified negative.
- **409 then press again.** All entries and the file are kept, and the item is reloaded once. The second deliberate press records, and the run sent exactly two E-RESPONSE POSTs. The second POST carries the reloaded `case_revision`: when I forced the reload to return 7, the second press sent 7. This holds after 409, 403 and an uncertain result, so TECH-1-1 is fixed on the real build.
- **Uncertain results are never resent.** This was checked for record-then-fail, 500, 503 and network loss on E-RESPONSE, E-WORK-ACTION and the upload. Each time one POST went out and nothing was resent automatically. When the reload also failed, the warning said "Record stays off", and Try again sent only a GET.
- **Not proved (contract-mock run only).** These were not exercised: real Django session auth and CSRF issue, server-side grants per record (wrong user or tenant was simulated with mock 403/404 and the fixture `you_can_act`/`allowed_actions` flags, and the mock grants finance_lead the W-1601 record), real revision bumps on claim (the mock claim returns the same revision 3), real evidence storage and hashing, the backend T-RESPONSE/T-EXCEPTIONS, any receipt check for delivery, and PostgreSQL. D-32 (the phone When/Note/attestation fields that the boards don't draw) is held for the design engineer and is not judged here.

## Findings
- QA-2-1 | non-blocking | low | frontend | Pre-existing shell issue, not caused by F-09; the same as F-04 QA-2-1 and still open. **Problem:** when the whole session is already signed out (`/me` answers 401), the frame renders `SignedOutState` with `usePathname()` only (`frontend/src/shell/AppShell.tsx:44,74`). The sign-in link becomes `/accounts/login/?next=%2Fwork%2FW-1601%2Frespond`, which drops `?task=T-1601`. After sign-in the person lands on "This response isn't open here" and must go through the work item. **Repro:** cookie `psl_mock_scenario=401`, then open `/work/W-1601/respond?task=T-1601` (evidence `qa-evidence/j15-401-1440.png`). **Expected:** the sign-in link keeps the query string. **Actual:** the query is dropped. F-09's own 401 handling is correct: a 401 on the item GET alone and a 401 on the Record press both give `next=%2Fwork%2FW-1601%2Frespond%3Ftask%3DT-1601`. The fix belongs to the shell lane, which is read-only for F-09.

## Verified
- TECH-1-1 | verified | `fix.cjs` filled W-1601 with one upload (case_revision 5 returned), then forced the first E-RESPONSE to 409, 403 or 503 and rewrote the reload GET to `case_revision: 7`. The second press sent `case_revision` 7 in all three cases (`qa-evidence/fixes-retest.log`). In an unaltered run, 409 then press again recorded with two POSTs in total (`qa-evidence/j10-409-1440.png`).
- TECH-1-2 | verified | Comment-only change, no runtime behaviour. The entry link and the reconcile panel on WorkItemOverview behave as specified (journeys `entry` and `reconcile` in `qa-run.log`).
- TECH-1-3 | verified | After recording, a page reload of `/work/W-1601/respond?task=T-1601` shows the eyebrow "REL-0077 · LAGOON HEALTH" and the h1 "Client UAT response" (36px), with no form controls and no POST.
- UX-1-2 | verified | The same reopen at 390 keeps the h1 "Client UAT response" and "REL-0077" in the bar note.
- UX-1-1 | verified | The untouched form at 1440 and at 390 shows "Choose when and what they did to record this." with no `role="alert"` in main; the only alert node is Next's route announcer. After the first change, the alert "Add the proof and confirm it's genuine to record this." appears.
- UX-1-3 | verified | W-1603 at 390 as finance_lead: "Record and continue" is enabled before a choice (358x50 at y776, inside the viewport). Pressing it shows the alert "Choose what happened to continue.", focus moves to the first radio in the group, and no POST is sent. Choosing "It didn't arrive" clears the alert, and the press sends one POST with `outcome:"not_delivered"` (`qa-evidence/j19-reconcile-phone-nochoice-390.png`). At 1440 the button stays disabled until a choice is made.
- UI-1-1 | verified | Phone success: `.psl-phonebar .shell-phonenote` reads "REL-0077" at x316 y19 (`qa-evidence/j20-phone-success-390.png`). The SOW form at 390 shows "← SOW" and "SOW-0207".

## Notes
**Commands.** Browser runs used `playwright` 1.65.0 and `@axe-core/playwright` from `/Users/Hunchoo/psl-factory-worktrees/f-09/frontend/node_modules`, with scratch scripts and no webServer. Personas were set with the `psl_mock_persona` cookie. Targeted failures came from `page.route` and took three forms: `continue` with an added `X-Mock-Scenario` header, so the real mock answers; `fulfill` with 500/503; or `abort('internetdisconnected')`. The full log is `qa-evidence/qa-run.log`. I rewrote three script-side mismatches before the final run: the fixtures use straight apostrophes, the panel head is uppercased by CSS, and one upload retry check raced the chip. The behaviour behind each was rechecked and is correct.

**Journeys (browser), all PASS except QA-2-1:**
- **Entry.**
  - W-1601 links "Record the client's response" to `/work/W-1601/respond?task=T-1601`, with no "Open the decision".
  - W-1608 shows neither link.
  - W-1602 links "Record the client's signature".
  - W-1201 still shows "Open the decision".
  - The click-through lands on the form.
  - At 390 the link is 326x44 and `scrollWidth` is at most 390.
- **Default and validation (W-1601).**
  - Title "Record a response · PSL Factory". Crumb "QUEUE / PREPARE FOR RELEASE / REL-0077 · STATION 3 OF 5".
  - The responder is preselected. The three actions show and none is checked. The version option shows. There is no channel control. The Tola aside is present.
  - Record is disabled. A forced click sends nothing.
  - One upload is sent with `kind:"client_response_proof"`, `case_revision` 4 and `X-CSRFToken: mock-csrf-pm`.
  - With proof but no tick, the same alert shows. With the tick, Record is enabled. Unticking disables it again.
  - The note is capped at 2000 with the counter "2000 / 2000". Removing a file sends no request.
- **Success.**
  - The two uploads carry case_revision 4 then 5.
  - Exactly one E-RESPONSE is sent, with no claim. Its body is `{"expected_revision":2,"who":"P-AO","action":"approved","responded_at":"2026-11-11T16:20:00+01:00","evidence_id":"EV-C-1601-1","attested":true,"evidence_ids":["EV-C-1601-2"],"case_revision":6,"version_id":"V-240","received_via":"email","note":"Signed on paper"}` (trimmed, and no team, what or estimate keys).
  - The success view reads "Response recorded. Client UAT sign-off for Lagoon Health, received by email on 11 Nov, recorded by Tunde Bello at 09:53 with 2 proof files." It also shows both next lines, the correction line and "Back to the work item", with no controls. The item is reloaded once with a GET.
  - Afterwards the work item has no entry link.
- **Phone W-1601.**
  - "← Queue", the summary line "Lagoon Health · Patient app · build 2.4.0 · Dr Amaka Obi", the short attestation, no aside, and "Take a photo or choose a file".
  - Record is pinned 358x50 inside the viewport and `scrollWidth` is at most 390.
  - Success shows "← Work item", "REL-0077" and "Back to my queue".
- **SOW W-1602 at 1440 and 390.**
  - The crumb shows, with only PROJECTS as a link. The document line reads "sent 18 Dec 10:30". The signer line and the next line show.
  - "Declined" sends `action:"rejected"`. The upload kind is `sow_signed_copy`.
  - At 390 the h1 is "SOW signature".
- **Claim (W-1605).**
  - Who and Version start on "Choose…". The channel select offers Email, Letter and In person.
  - The missing-fields alert names who, version and channel.
  - The order is upload → claim `{"expected_revision":3}` → E-RESPONSE, with `expected_revision` set to the claim's 200 revision and `received_via:"letter"`.
  - A claim 409 sends no E-RESPONSE and shows the stale warning.
  - A claim network failure shows "We couldn't get this ready. Try again." and sends no E-RESPONSE.
- **Absent fields and no case.**
  - W-1606 has no aside, intro or board sentences. Its success reads "Response recorded. Recorded by Tunde Bello at 09:48.", with no next lines, no "received by" and no proof count.
  - W-1609 shows "Proof can't be uploaded for this item.", the file input is disabled, and Record never enables. No POST is sent.
- **409, 422, 403 and 404.**
  - 409: as in Summary.
  - 422 (scenario): the server message shows, entries are kept, and one POST is sent.
  - Real mock 422 (evidence_id tampered in flight): "Check these fields: evidence_id." shows.
  - 403: one reload GET, a problem callout with "Your role does not allow this.", and the controls are kept. When the reload makes the task not actionable, the page shows "This response isn't open here".
  - W-1608 opened directly, an unknown task and a missing `?task=` all show the not-open state with "Open the work item".
  - 404 on Record: the no-access state, with no resend.
- **Load errors.**
  - Item 404 and 403 show "You can't open this work item" with no id, reference or name.
  - Item 500 and network loss show "We couldn't load this response form. Your work is safe; nothing was changed." Try again then loads the form.
  - 401 on the item alone and 401 on Record both show sign-in with `next` keeping `?task=`. A 401 on `/me` is QA-2-1.
- **Uncertain results.**
  - record-then-fail: the warning and the success view show, with one POST, still one after 2s.
  - 500 and network loss: the warning shows, Record comes back, entries are kept, and nothing is resent. A deliberate second press records.
  - Reload also failing: the "…couldn't reload to check. Record stays off…" warning shows, Record is disabled, and Try again sends one GET and no POST (`qa-evidence/j12-uncertain-reloadfail-1440.png`).
- **Double press.** A double click while the request was held showed "Recording…", disabled, with `form[aria-busy="true"]`. One E-RESPONSE was sent.
- **Proof upload errors.**
  - Mock 403: "You can't add proof to this item." (`qa-evidence/j17-upload-403-1440.png`).
  - 409: "This item changed. Add the file again.", plus one reload GET.
  - 422: the server message. An empty file gets the real mock 422 "Check these fields: content_base64.".
  - None of these is re-sent, and Record stays disabled.
  - 500 and network loss: "Couldn't upload. Try again." with the button. There is no automatic retry. Try again sends GET W-1601, then one POST, and the chip recovers.
- **Wrong persona.**
  - Persona `none` gets the frame's "No sections are open to your role yet." with no form.
  - finance_lead can record W-1601, and pm sees the W-1603 panel. This is because the mock decides grants from fixture flags, not from personas (spec assumption). Grants per persona are unproved until the backend exists.
- **Reconcile (W-1603, finance_lead, 1440).**
  - The head, the body "Chidi checked 6 times over 2 hours…", the three options with board wording and the footer all show. The panel is the right-hand aside at x1028.
  - The button is disabled before a choice. "It arrived" shows the proof field and the button stays disabled until the `delivery_receipt` upload completes.
  - Then exactly one POST is sent: `{"expected_revision":6,"action":"reconcile","outcome":"delivered","evidence_id":"EV-C-1603-1","case_revision":6}` with CSRF. The page reloads and the panel is gone. Only two POSTs were sent in total.
  - "It didn't arrive" sends no evidence or case_revision.
  - 409 shows "This item changed. Reload it to see the latest." and network loss or record-then-fail shows "We couldn't confirm your answer…", each with "Reload the work item". 403 and 422 show the server message. Each case sent one POST and no resend.
  - After record-then-fail, the item is at the `unknown` sidecar (revision 7) and was written once.
  - W-1604 shows no panel. W-1607 shows two options with no "Allow", no delivered option and no resend_note.
- **axe (WCAG 2.0, 2.1 and 2.2 A/AA).** No violations at 1440 or 390 for the default form, validation, success, SOW, reconcile and the W-1601 entry.

**Direct API (curl through the 4911 proxy; mock reset before and after):**
- **Upload:**
  - wrong kind → 422 `kind`; zero bytes → 422 `content_base64`; stale case_revision → 409;
  - no CSRF → 403 `csrf_failed`; persona none → 403; unknown case → 404;
  - ok → 200 with a 64-hex sha256 and case_revision 5, after which the GET shows 5.
- **E-RESPONSE:**
  - attested missing or false → 422 `attested`; unknown evidence → 422 `evidence_id`; who not offered → 422 `who`; action not offered → 422 `action`; 2001-character note → 422 `note`; extra key `foo` → 422 `foo`;
  - stale expected_revision → 409; T-1608 with a valid body → 403;
  - persona none → 403; no CSRF, or another persona's token → 403 `csrf_failed`; unknown task → 404; `X-Mock-Scenario: 422` → the scenario body;
  - ok → 200 with `recorded.by.name` "Tunde Bello", then a repeat → 409, and the GET shows `you_can_act:false` with `already_decided`.
- **E-WORK-ACTION:**
  - W-1604 with the correct revision → 403; no outcome → 422; delivered with no evidence → 422 `evidence_id`; resume → 501; stale → 409; persona none → 403;
  - not_delivered → 200 `{state:"processing", revision:7}`, and the GET then has no reconcile.
- **Observation, not a finding:** the mock accepts `team` on a client_response E-RESPONSE because v7 declares it for the RFP variant. The frontend never sends it, as the success body above shows.

**Scratch.** Scripts and screenshots stayed in the session scratchpad and were deleted. I kept 6 screenshots and 2 logs (about 0.5 MB) in `round-2/qa-evidence/`. I never read `.runtime/demo-access.txt`.
