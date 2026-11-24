VERDICT: CHANGES
COMMIT: d9f900c2122f048e73d85ec1b4e3daac63125900
REVIEWER: qa-reviewer
AUTHORITY: integrated QA

## Summary
- Mock journeys all pass in a browser against the production build (`next start` on 4971, contract mock on 4972): choose a proof, upload a PDF, the check-file tick, "Recorded" only after the re-read, every hold line, 409, uncertain, re-read failure, paging, no name, 403/404.
- One blocking finding: `e2e/project-tabs.spec.ts:82` (milestones, desktop and phone) still asserts no link matching /complete/i. F-78 adds "Mark complete" links, so the committed spec fails at this head (2 failed, 45 passed across money.spec.ts and project-tabs.spec.ts).
- QA-2-1 (`money.spec.ts` idle aside) and TECH-2-1 (Proof toggle) are verified.
- Live: hidden for every staff role until LB-2 is fixed. The Milestones tab shows no "Mark complete" for live-lead, live-multi or live-none. This is the backend issue LB-2 (no role carries `milestone.complete`), not a frontend failure.
- Not proved: a real completion, the real PDF upload and the real re-read against Django. The local database has no project with milestones, and LB-2 blocks the write. This is the integration-QA gap.

## Findings
- QA-3-1 | blocking | medium | frontend | A committed e2e spec fails at this head. `frontend/e2e/project-tabs.spec.ts:82` (`milestones: stages from /money, Proof on a linked completion... no completion control`) asserts `getByRole('link', { name: /complete/i })` has count 0. F-78 now shows a "Mark complete" link per open stage when `can_complete` is true, so the mock gives 2 links on desktop and phone. Command: `E2E_PORT=4971 MOCK_PORT=4972 npx playwright test e2e/money.spec.ts e2e/project-tabs.spec.ts`. Result: 2 failed (desktop 1440, phone 390), 45 passed. Expected: the spec asserts the F-78 behaviour (links present when allowed, absent under a hold or `norole`). The build.md for round 3 does not mention e2e.
- QA-3-2 | non-blocking | low | integration | Live, as `live-multi`, the Milestones tab on project 0d790a54 shows "We couldn't load the recorded completions" (`unexpected_response`). `GET /projects/{id}/milestones` returns `sections: []` and `isCompletions` requires exactly one section (`milestonesModel.ts:23`). This is F-71 code. The backend sends no completions section for that role. Decide which side changes. No effect on F-78 behaviour.

## Verified
- QA-2-1 | verified | `money.spec.ts` passed (desktop and phone) in the run above. The aside is found by its head "Where a figure comes from".
- TECH-2-1 | verified | `npx vitest run tests/milestones.test.tsx`: 36 passed, including "TECH-2-1: Proof is a toggle; aria-expanded is true from the press, through the read, until the second press". QA-2-2 is the same behaviour.
- UI-2-1 | verified (static only) | `npx vitest run tests/milestone-complete.test.tsx`: 45 passed, including the panel-head colour rule test. The rendered contrast was not measured here.

## Journey results
Run: vitest `tests/milestone-complete.test.tsx` 45, `tests/milestones.test.tsx` 36, `tests/mock-live-milestone-complete.test.ts` 17 (Ajv against the live contract), `tests/milestones-model.test.ts` 14, all passed. Browser: Playwright driving `/projects/P-0101/milestones/complete?name=UAT sign-off`, mock reset before each case.

Mock (cookie `psl_mock_complete`):
- ok, existing proof: button disabled with nothing chosen. Still disabled with the proof only. Enabled once the tick is added. One POST `{revision:5,name,evidence_id:31}`, then the page showed "Milestone recorded", "Completed 23 Nov 11:15", "Proof version 2", the Finance text and no button. The text comes from the re-read.
- ok, PDF upload: the file route got one POST and the write sent `{revision:5,name,upload_id:8001,checked:true}`. One tick leaves the button disabled. Both ticks enable it. The result was "recorded".
- baseline, proofreq, inuse, norole: the hold text matches the spec table, no button, no POST. On the tab, the baseline hold line shows above the table and there are no links.
- forbidden (403) and notfound (404): "This project or milestone isn't available to you."
- conflict: after the 409 the page says "This project changed while you were confirming. We reloaded it...". The proof and the tick were kept. The second press sent revision 6 and recorded. 2 POSTs.
- uncertain (503): "We couldn't tell whether this was recorded." with Check again, and 1 POST only. Check again then gave "It wasn't recorded. Your choices are kept", and the form returned.
- uncertain-saved: Check again gave "A completion with this name is now recorded. Open the Milestones tab to see it." 1 POST.
- reread-fail (201 then 503): "We saved your completion but couldn't confirm it yet. Check again." No Mark complete button. Check again sent only the GET and the page then showed "Milestone recorded".
- paged: 2 proofs, then 3 after "Show more" (de-duplicated).
- no name: "Choose a milestone from the Milestones tab.", no read or write. The Milestones tab shows 2 "Mark complete" links in the default case.

Live (Django 8010, Postgres 55433, Next dev 4970), accounts live-lead, live-multi, live-none, API calls by curl:
- live: hidden for every staff role until LB-2 is fixed. The tab has no "Mark complete" link for any of the three. The options read returns 404 for all three roles on both local sample cases.
- POST without CSRF gives 403 `csrf_failed`. An empty name gives 422 `invalid_input` with a field message. A write on the sample case gives 404. An unknown case and a missing milestone id give 404. The deep link in the browser shows "This project or milestone isn't available to you." with no button.
- live-none: the tab shows "You can't open this project".
- No database writes were made. No live POST created a record.

## Notes
- Stack and cleanup: I started mock (PID 36127), next start 4971 (37175/37176), Django (runserver, 8010) and next dev (38236, 4970). All were stopped, and no listener remains on 4970, 4971, 4972 or 8010. Disk was 21 GiB free at the start. `npm run build` ran in the worktree through Playwright.
- Unproved: real PDF upload with its server checks, a real 409, and a real recorded completion with the Finance handoff queued. These need LB-2 fixed and a project with a signed baseline and proof.
