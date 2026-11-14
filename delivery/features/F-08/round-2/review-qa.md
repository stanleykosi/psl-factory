VERDICT: PASS
COMMIT: 568c0a407f78b39a3cb7cf33f0030cc3b0a6028c
REVIEWER: qa
AUTHORITY: integrated QA (UI-only, against the contract mock; no backend for E-OVERVIEW in this lane)

## Summary
- I ran `e2e/overview.spec.ts` against the shared build (http://localhost:3811, built 07:16 from head 568c0a4, mock 127.0.0.1:3812). I used a temporary scratchpad config with base URL :3811 and no webServer, so the shared `.next` was not rebuilt. Result: 12 passed (49.4s), with axe WCAG 2.2 AA at 1440 and 390, 3D render-on-demand, no-WebGL, reduced motion, the three.js bundle split, the status-cookie tones and the 3D board readout and reset. I deleted the config and its output afterwards.
- I also ran my own Playwright probes (session f-08-qa, chromium, Africa/Lagos) against the same build. They covered personas, the status cookie, 15 s polling (no overlap, visibility, late response dropped, 500 and network error cards, recovery), 401/403/404, flat and 3D (switch, canvas and chip hover, chip focus, drag, reset, rAF idle, dispose with the context lost), live reduced motion, narrowing to under 720px, context-lost and chunk-failure fallbacks, no WebGL, phone and keyboard. Everything matched the spec and this round's build.md.
- "See all exceptions" opens the app's "This page doesn't exist" page on this branch. This is expected because F-06 is not merged. Loading the page itself produces no 4xx responses and no console errors.
- Not proved here: this is UI-only against the mock. There is no real backend (T-FLOOR) and no real grant or tenant filtering, because the mock serves every persona 200 and the frontend `/me` gate is the only wrong-user check. 3D ran on headless Chromium with software GL, not a real GPU. `lines[].status` is a proposed field and is only served under the `psl_mock_overview=status` cookie.

## Findings
None.

## Verified
- FID-1 | verified | I checked behaviour only; fidelity scoring is the UI lens. The default page shows totals 18/5/3/28 and the eyebrow "FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT", with tags verbatim and the round-1 tone fallback (WAITING/STOPPED/UNCERTAIN/PROBLEMS `psl-tag--person`, ON TRACK `psl-tag--neutral`). With `psl_mock_overview=status`, WAITING is `psl-tag--waiting`, ON TRACK is `psl-tag--done` and STOPPED/UNCERTAIN/PROBLEMS are `psl-tag--person`. The phone at 390 shows "18 in progress · 5 need a person", 8 rows, no View switch, no hint and no sideways scroll.
- Coordinator: mascot avatars | verified | All 8 row images load at naturalWidth 192 with alt "Tola · PMO agent" ×4, "Chidi · Finance agent" ×3 and "Zainab · HR agent", in both the default and status variants.
- Coordinator: 3D detection | verified | A normal headless Chromium shows the View switch with Flat checked and no "can't show" hint. With `getContext` returning null for webgl/webgl2, there is no switch, the hint "This device can't show the 3D floor, so it's shown flat." is visible, and all 40 station screen-reader counts are present.
- Coordinator: production 404 | verified | Loading /overview as finance_lead, pm and none produced no response ≥ 400 and no console errors. A 404 appears only after clicking "See all exceptions" (expected, F-06 not merged).
- Coordinator update D-01: 3D concept 3 | verified | The canvas has role=img and the label "3D factory floor: 8 lines. The same figures are listed in the flat view below.", with 8 flat rows kept for screen readers, 40 chips and 8 line labels.
  - Hovering a chip gives a readout such as "Release · Gates · 0 items · no person needed", and a raycast hover on the canvas gives "Cash and BU · Allocate · 0 items · no person needed". When the pointer leaves, the readout goes back to the hint.
  - Tab from "3D floor" reaches the first chip ("1 Brief", 2px solid outline, readout "Pre-sale · Brief · 1 item · no person needed"), then 40 chips, then Reset view (2px solid).
  - A drag moved the chips; for example, the first chip went from (420,367) to (330,464). Reset view put all three sampled chips back at their exact page coordinates and cleared the readout. rAF calls grew by 0 over 1.5 s after the drag settled.
  - Returning to Flat removes the canvas and chips, and the captured WebGL context reports `isContextLost() === true`. This gives runtime evidence for disposal, which TECH-2-2 notes has no automated test.
- TECH-1-1, UI-1-1 | not in the QA lens | Not re-judged. Nothing I ran contradicts the verdicts in the technical and UI reviews.

## Evidence (exact probes, base http://localhost:3811, timezone Africa/Lagos)
- e2e: `cd /Users/Hunchoo/psl-factory-worktrees/f-08/frontend && npx playwright test --config <scratchpad>/pw-qa.config.mjs e2e/overview.spec.ts`. The config had testDir set to the worktree `e2e`, outputDir in the scratchpad, baseURL :3811, chromium and no webServer. Result: 12 passed.
- Personas (cookie `psl_mock_persona`):
  - finance_lead: 1 overview request and the full floor.
  - pm: "This section isn't open to your role. Go to My work" and 0 overview requests.
  - none: "No sections are open to your role yet." and 0 overview requests.
  - The title is "Overview · PSL Factory" in all three.
- Polling (`page.clock`, plus a `page.route` on `**/api/v1/overview` that counts calls and holds some of them open):
  - 1 call before 14 s, and the 2nd call at 15 s.
  - With call 2 held for 45 s of ticks, the total stayed at 2 and at most 1 was in flight.
  - The 500 on call 4 showed `.shell-errorcard[role=alert]`: "ERROR · COULDN'T LOAD / We couldn't load the factory floor. Your work is safe; nothing was changed. Last loaded 14 Nov 16:40 WAT. Reference server_error for support. Try again". While the card was up there were 0 `dl`, 0 Lines section and 0 canvas.
  - Late response: call 5 was held (as_of 15:41, value 33) and Try again sent call 6 (as_of 15:42, value 44). After call 5 was released, the page still showed 44 and "16:42".
  - Aborted fetch: the error card showed "Reference network_error", and the next poll restored the figures with the card gone.
  - Visibility: with `visibilityState` stubbed to hidden, there were 0 requests over 60 s. Back to visible gave 1 immediate request.
- Errors (the overview request is re-sent with `x-mock-scenario`, and `/me` is untouched):
  - 401: "You're signed out." with a Sign in link to `/accounts/login/?next=%2Foverview`.
  - 403: "The factory floor isn't open to your role. Your role does not allow this."
  - 404: the same heading with "We could not find that record."
  - Each showed 0 `dl` and made 0 further overview requests over 30 s.
- Live changes while in 3D:
  - Reduced motion turned on: the canvas went at once, the switch was gone and the motion hint showed. Turned off: the switch came back.
  - Narrowing to 600px: canvas and switch gone. Back at 1440: the switch returned with Flat checked.
  - Dispatching `webglcontextlost` on the canvas, or aborting the JS chunk containing `__THREE__`: flat view, `psl-callout psl-callout--warning` "We couldn't show the 3D floor, so it's shown flat.", no switch, 8 rows and 40 screen-reader counts.
  - Reduced motion at load: the hint is visible and there is no 3D radio.
- Keyboard on the View switch: with Flat focused, ArrowRight checks 3D floor (focus stays on it) and mounts the canvas. ArrowLeft goes back to Flat and removes the canvas.

## Notes
- **Shared mock went down mid-run, then restored.** During my first probe pass the shared mock on 127.0.0.1:3812 (the coordinator's process, pid 62730) stopped listening. Curl to it returned 000, and :3811 answered 500 on `/api/v1/overview`.
  - My requests did not cause this. On my own mock instance (:3899), the 401/403/404 scenarios each answered normally and that instance kept running. Around the same time (07:31), another feature's mock (f-10, pid 69899) was started.
  - I stopped my :3899 instance and started `node mock/server.mjs` with `MOCK_PORT=3812` from the f-08 worktree (pid 70124), so the shared build works again. I left it running in place of the original. The coordinator may want to restart it under their own control.
  - I re-ran every probe after the restore. The e2e run had finished before the outage.
- Try again is a direct call, not a tick, so it can be in flight at the same time as a slow poll (calls 5 and 6 above). The newer response wins, and the older one is dropped, as the spec requires. Ticks never overlap.
- The UI copy uses typographic apostrophes (’). The spec writes them as straight apostrophes. Tests and screen text agree with each other.
- Screenshots and probe scripts were kept in the scratchpad and have been deleted. The worktree is clean, and `frontend/test-results` was not created.
