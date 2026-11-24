VERDICT: PASS
COMMIT: 6636f0eb7b4ae40ec93e12d35c6e3a8b7b2d9753
REVIEWER: qa
AUTHORITY: integrated QA, round 2

## Summary
- Mock journeys pass at 1440 and 390 on the production build at this head. The build's rewrites point at 127.0.0.1:4010, so I ran the mock there (PID 9644) and `next start` on 4990 (PID 9645), with persona `pm`. Six rows in order with shuffled input, one overview GET, the closure reasons, the title link and the no-access, error and recovery states all behave as the spec says, with no horizontal scroll.
- The 403, 404, 500 and network failures were injected with browser-level routing on the delivery-overview call only. The mock's scenario cookie fails every call, including the account read, so it cannot isolate one endpoint. P-0099 gives 403 natively. 403 and 404 both show the same no-access panel with no server text. 500 and network show the error panel, and "Try again" makes exactly one new request and recovers.
- Live (Django 8030 on 55433, PID 18326, signed in as qa-seed): sign-in, project list, and delivery-overview (200, six lines, all not_started) work. The write-free list and the 401, 404 and bad-id cases behave. A real started line could not be made: POST /work for `delivery-release/v1` returns 422 `action_unavailable` "Select this case delivery dossier". The project has no delivery dossier, so the live started-row, closure-reason and work-link journeys are unproved (see QA-2-1).
- The UI was not run against live Django. The build bakes its API origin into the rewrites, and a second `next dev` would overwrite `.next`. I replayed the real live overview JSON through the production page on 4990, at 1440 and 390: six rows, NOT STARTED, no links, no overflow.
- All processes I started are stopped (4010, 4990 and 8030 are no longer listening).

## Findings
- QA-2-1 | non-blocking | medium | integration | Evidence missing for the live started-row journey (AC1 on Django, AC3, AC7, AC8). The qa-seed project `4a228bcb-f762-4bc6-858e-74e9ab11ebd3` ("Project delivery") has no delivery dossier: `GET /projects/{id}/delivery/1/closure-checklist` and `/2/` return 404, and `POST /work` with `delivery-release/v1`, `dossier_id: 1` returns 422 `action_unavailable`. Seed command not run, for the merge batch: `manage.py seed_delivery_demo --username <qa-seed account>` (PGPORT=55433, PSL_ENV=development; `local-dev-environment` memory says it was refused before for want of delivered receipts, so it may need a prior seed such as `seed_demo`, `seed_standard_demo` or `seed_rfp_demo`). After it, start the lines through `POST /work` and open `/projects/{id}/delivery` on Next pointed at 8030 (build with `API_ORIGIN=http://127.0.0.1:8030`).
- QA-2-2 | non-blocking | low | frontend | The live line titles differ from the mock and the spec's table. Live `title` values are "Delivery gates and release evidence", "Release observations and hypercare", "Support and Operations handover", "Project artifact archive" and "Project closure" (Go-live acceptance matches). The page prints the API title as sent, which follows the spec ("from title"). The wording is longer than the board's "Release gates", "Hypercare", "Handover to Support" and so on. At 390 the longer titles still do not overflow. Confirm whether to show API titles or fixed board words. Not a regression.
- QA-2-3 | non-blocking | low | frontend | Carried from round 1 and unchanged: `effect_uncertain` uses the amber waiting tone (TECH-1-1). Accepted under D-195, so this is for the record only. I did not exercise it on screen because neither the mock nor the live data has that state.

## Verified
- UX-1-1 | verified | P-0101 at 1440 and 390: tag and date are in separate cells, no overlap, no horizontal scroll (screenshots in the scratchpad `shots/d-p0101.png`, `shots/m-p0101.png`).
- UI-1-1 | verified | same run.
- UI-1-2 | verified | rows sit inside the panel at 1440 (screenshot above).
- UI-1-3 | verified | 390: title and tag share one line, reference and date beneath, number box hidden.
- UI-1-4 | verified | `main a[href^="/work/"]` returns five links named by the row titles (`/work/2501` to `/work/2505`), none named "Open"; clicking "Release gates" lands on `/work/2501`. The panel head reads "The six delivery lines, in order".
- UX-1-2 | verified | the closure row reads "Closure waits on: Handover to Support – Support listed 2 gaps. / Retrospective", and the current check (Hypercare) is not listed.
- UX-1-3 | verified | same as UI-1-3.
- UI-1-5 | verified (out of my lens) | the exceptions file exists and is pending the design engineer. I did not judge it.

## Journeys run (command or page, result)
Mock (Next 4990 production build, mock 4010, cookie `psl_mock_persona=pm`):
- `/projects/…0101/delivery`, 1440 and 390: requests `GET delivery-overview`, `GET work/2501/release-register`, `GET …/delivery/52/closure-checklist`, one each, no non-GET request. Rows 01 to 06 (release, go-live, hypercare, handover, archive, closure) although the fixture is shuffled. The tag texts are VERIFIED, VERIFIED, VERIFIED, ACTION NEEDED, READY and NOT STARTED, with "Updated 25 Mar", "02 Apr", "18 Nov", "20 Nov" and "19 Nov". "Checked 23 Nov 2026 · 10:00 WAT" at 1440. The 390 view hides the number box and the rule sentence, as the spec says. No "of 6 done", DLV number, gate wording or Tola text.
- `/projects/…9999/delivery` (not in the list, so six lines all not_started): six NOT STARTED rows, zero `/work/` links, no reference, no date, and no release-register or checklist request.
- `/projects/…0099/delivery` (the mock's no-access id): "You can't open this project … not even its name", with no project name in the header.
- Injected on `**/delivery-overview` for P-0101: 403 and 404 show the no-access panel at both widths. The panel head still carries the project name here, but only because the separate journey read succeeded. Native P-0099 shows no name. 500 and network abort show "Delivery can't be shown right now" with the server message text absent ("SECRET SERVER TEXT" was not printed). "Try again" sent one more request and recovered to six rows, at both widths.
- Observation: on the first desktop run, the 404 and 500 cases were still on the loading skeleton when read at 600ms, and they settled after a longer wait. That is slow first paint on a cold production server, not a failure.
Live (Django 8030, db 55433, qa-seed, stdlib client with session cookie and CSRF):
- `GET /api/v1/session` 200 signed_in. `GET /api/v1/projects` 200, one project. `GET …/delivery-overview` 200, six lines in key order, all `not_started` with null ids. Unknown project uuid 404, malformed id 404, anonymous 401.
- `POST /api/v1/work` `delivery-release/v1` with `dossier_id: 1`: 422 `action_unavailable` (no dossier). This is the correct refusal, and it is the evidence for QA-2-1.
- Live overview JSON replayed through the page at 1440 and 390: renders six NOT STARTED rows, no links, no overflow.

## Not proved
- Started rows, closure reasons, work links and the 403 for a wrong user or tenant on real Django (needs a dossier and a second account; the 403 and 404 cases are indistinguishable by design).
- The UI served from the real backend. The UI-to-8030 path was proxied only as a replayed payload.
- The `effect_uncertain` and other rarer states on screen. They are covered by the unit tests only.
- The flow with a real work item behind `/work/{id}`: I only confirmed the navigation to `/work/2501` on the mock.
