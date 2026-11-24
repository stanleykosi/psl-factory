VERDICT: PASS
COMMIT: 98eb07bbb7c5fe76f5f13423947995eb4942e520
REVIEWER: qa
AUTHORITY: integrated QA (lighter D-180 panel)

## Summary
- Merge-delta re-confirmation on 98eb07bb (origin/main 811465d8 merged into the round-2 head eacdc704; the only conflict was a test allow-list; CI passed per premerge-checks-98eb07bb.log). From frontend/ in the worktree I ran the F-88 test files: received-bid, weekly-returned-received, rfp-assign-mock, issue-assign-mock, assign-pm, my-work, my-work-model, start-work-live, next-config. Result: 245 tests, all passing. One combined 9-file run (9 workers, 591 s) showed 2 failures, both `findBy...` timeouts under load, one in weekly-returned-received; the files rerun separately passed (weekly-returned-received 24/24; the other 8 files 221/221). I did not identify the second failing file from the first run, so a timeout in a different file is possible, but the separate reruns cover all nine files. I treat this as machine load, not a regression.
- No mock browser walk and no live run this time (the design engineer's answer "Mock-only, like F-60", and the earlier live 403 proof stands). The findings and journeys below were observed on eacdc704; the merge brought in no F-88 file change I could see tested differently, so they carry forward on that assessment. Nothing was started, so there is nothing to stop.
- Mock, both drawers, at 1440 and 390: every success and failure journey in the brief behaved as the spec says (list below). Run in a real browser (Playwright, Chromium) against `next dev` on 4982 and the contract mock on 4983, from the worktree at this head. Each journey was driven in the page; the mock's request log was read back for the form-data keys and the assign bodies.
- Live: only the 403 refusal was run, as the design engineer's answer "Mock-only, like F-60" allows. As `qa-seed` on Django 8021 / Postgres 55433, `GET /received-bids/organisations` returned `{"items": []}`, `POST /received-bids` (multipart, authority 1, a valid pdf, session CSRF) returned 403 `forbidden`, and `GET /received-bids/assignments` was still `{"items": [], "cursor": null, "checked": 0}` afterwards. An unauthenticated POST was refused 403 `csrf_failed`. No organisations, grants, seed or migration were touched.
- Unproved live, per the answer "Mock-only, like F-60": the RFP log success path (a 200 with a real receipt and the receipt read), replay by `start_key`, the 422 duplicate, the real 5 MiB upload limit and the 413/415 answers from Django, the assignments list, the assign POST and `POST /cases/{case_id}/files` for a received bid. All of those were proved on the mock only; the mock's answers are the contract's shapes, not Django's.
- Round-2 fixes verified (TECH-1-1, TECH-1-2, UX-1-1); UI-1-1 to UI-1-3 were verified by the UI reviewer and I saw the same wording in the running build. No blocking finding. Three non-blocking notes follow.

## Findings
- QA-2-1 | non-blocking | low | frontend | The mock's Unassigned badge on My work reads 6 (v7 `/work` counts) while the list below serves 13 RFPs over two pages. Already known and left by the builder (UX-1-2, build.md); live `/work` has no counts. Check the badge once the live counts exist. `frontend/mock/received-bids.mjs`, `MyWork`.
- QA-2-2 | non-blocking | low | frontend | The persona with no organisations (mock `none`) cannot reach Start work in the browser (My work never loads for it), so the empty client list ("You can't log a received RFP for any organisation yet." with a disabled submit) was not seen in the page. The `rb_orgs_denied` 403 variant was seen (see below). The empty state is covered only by the unit tests. `frontend/tests/received-bid.test.tsx`.
- QA-2-3 | non-blocking | low | frontend | The Start work chooser has the visible heading "Lines you can start" once, but two visually hidden legends repeat "Lines you can start" for screen readers (one per group). Not a visual repeat, so UX-1-1 stands as fixed; a screen-reader user hears the phrase three times. `frontend/src/features/start-work/LineChooser.tsx`.

## Verified
- TECH-1-1 | verified | The mock `/lines` lists `received-bid` with `can_submit_via_api: false`, and the chooser shows "Log a received RFP / Record an RFP a client sent, with its file" and opens the form (1440 and 390). The line appears only because `/lines` lists it; the negative case (live `/lines` without it) was not run in the browser and rests on the unit tests.
- TECH-1-2 | verified | My work loads at both widths, the Unassigned tab and drawer open and close with no notice callout or console failure; "PM assigned" and "RFP logged" appear only inside the drawers.
- UX-1-1 | verified | Chooser at 1440 shows one visible "LINES YOU CAN START · 2" heading with one list; the two further "Lines you can start" strings are zero-height legends (QA-2-3).
- UI-1-1 | verified | SCR-24 drawer shows the info callout "Only people allowed to prepare RFPs for this workspace are listed. Who may assign is set by PSL in Setup." and "2 people can prepare RFPs here" under Accountable PM, at both widths.
- UI-1-2 | verified | "One of the roles PSL allows to assign RFPs" shows under "You are assigning as", for several roles and for the single-role case (`rb_one_role`, role shown as plain "Head of PMO").
- UI-1-3 | verified | SCR-23 shows eyebrow "START WORK · PRE-SALE" (desktop), the callout "Logging an RFP opens a new pre-engagement workspace for it. The RFP reference can't be changed later.", the labels Received / Submit to / Submission deadline (Unknown, Stated, Not stated) / Deadline, and the four-way submission control (Email, Client portal, By hand, Not stated).

### SCR-23 Log RFP journeys (each at 1440 and 390 unless noted)
- Empty submit: "5 things to fix" (client, reference, document, received, deadline); no POST sent.
- Success (client Northwind Bank, reference RFP-2026-041, rfp.pdf, received via "Use now", deadline Unknown, method Email, target, client name, Note, tick-box ticked): one `POST /api/v1/received-bids`; the mock saw multipart fields `authority, start_key, reference, received_at, deadline_status, note, prospect_name, submission_method, submission_target, context_attested=true` plus file `document`; no `definition`, no `POST /work`. Result "RFP logged." with reference, received time, file name and size, the Note, and the link "Open Unassigned" (`/my-work?queue=unassigned`); focus lands on the status message.
- Confirm tick-box: absent until a client name or submission detail is filled, present after.
- Validation: a 4001-character Note refused ("Use 4000 characters or fewer.") and "Stated" with no date refused ("Choose the deadline date and time."), no POST for either.
- File refusals in the page: `pic.png` "Use a Word or PDF file."; a 6 MiB pdf "The file is larger than 5 MB."; a pdf of exactly 5 MiB accepted and logged. Server 413 (`rb_too_large`) shows "The file is larger than 5 MB."; 415 (`rb_unsupported`) shows "Use a Word or PDF file.".
- Duplicate (`rb_duplicate`, 422): callout shows the API's own message "This reference has already been logged for this organisation."; nothing new recorded.
- start_key replay (`rb_uncertain`): first send 503, callout "Not confirmed. Check before trying again."; "Check again" resent; the mock log shows two requests with the same `start_key` (503 then 200) and the success read back. Same at both widths.
- 403 on the POST (`rb_denied`): "You can't log RFPs for this organisation."; 403 on the client list (`rb_orgs_denied`): the same words, "The client list could not be loaded." and a disabled "Log RFP".
- 422 with a field (`rb_invalid`): summary "1 thing to fix" with the API's message.
- Receipt read down after a 200 (`rb_receipt_down`): "RFP logged. We couldn't read the receipt back." with "Read the receipt again" and "Open Unassigned", no second POST.
- Not run: the 429 scenario (the mock answers every route with the status, so the chooser itself fails to open); it rests on the unit tests.

### SCR-24 Assign PM journeys (persona `pmo_lead`; `pm` gets the mock's 403 on the Unassigned list by design; each at 1440 and 390)
- List: 12 RFPs with "Assign PM" links and "Load more"; the restricted row shows "You need access to this RFP's owner first" with no link.
- Empty submit: "4 things to fix" (PM, role, proof, reason); no POST.
- Success with a recorded proof: one POST, 201, body `{intake:77, revision:3, candidate:301, role:"Head of PMO", reason, evidence:901}`; drawer shows "PM assigned: Amara Okoye." and "What happens next: The PM prepares the RFP response"; focus on the status.
- Success with an upload: `POST /cases/{case}/files` 200 on picking the file; submit without the tick-box refused ("Confirm you checked the file.", no assign POST); after ticking, body has `upload_id:8001, checked:true` and no `evidence`.
- Reason/PM/proof mapping: 422 (`assign_invalid`) shows "Say why this person was chosen." and "This proof is not available." against their fields.
- 409 (`assign_stale`): "This changed while you were working."; form kept for the new revision.
- 503 with the assignment stored (`assign_lost_reply`): the drawer re-reads and shows "Already assigned: Amara Okoye" with the steps; no second POST. 503 with nothing stored (`assign_uncertain`): "We couldn't confirm the PM was assigned. Check before trying again." and the form is offered again; no automatic resend.
- 403 "You can't assign a PM for this RFP."; 404 "This RFP isn't available.".
- Read states: setup required "Nobody is set up to assign yet. Ask a PSL admin to finish setup." (no form); no nominees "No one can be chosen for this RFP yet."; already assigned (`rb_assigned`) "Already assigned: Amara Okoye" with steps and no form; no listed proofs offers only the upload picker; no `next_steps` hides the block; one role shown as plain text.
- Not run: wrong tenant beyond the mock's 403/404 answers; any real PM name list from Django.

## Notes
- Servers started by this run (mock 46308, Next 46310 and its child 46352, Django 64696) were stopped by recorded PID; ports 4982, 4983 and 8021 are free. Scripts and screenshots are in the session scratchpad only. The qa-seed password was read from the local file by a script and not copied or printed.
