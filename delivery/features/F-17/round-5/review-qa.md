VERDICT: PASS
COMMIT: ff48d19d80a904de760cf524166ad820107267dd
REVIEWER: qa
AUTHORITY: integrated QA

## Summary
- I ran the real stack at head ff48d19 myself: a fresh production `next build` and `next start` on 4801 (FRAME_FIXTURES=1, API_ORIGIN pointing to the contract mock), with the contract mock on 4802. I stopped both by their own PIDs and ports. Browser session `f-17-qa` used touch taps (hasTouch and isMobile) at 390x844 and 320x640, and pointer clicks at 1440. Every tap landed on the button's on-screen centre and was hit-tested with `elementFromPoint`. The script reported 0 failures.
- **QA-5-1 and QA-5-5 are verified.** On W-2008, "Record and continue" is reachable by tap in every case I tried: right after the press, scrolled to the bottom, after a reload and in a new tab, at both 390 and 320. Each tap sends one `/actions` request (200) and nothing to `/steps`. After a reload while delivery is uncertain, both steps are `aria-disabled` and the hint reads "Confirm what happened first." I tried a tap, focus with Enter and Space, a double click and a double tap. The mock log still shows only the first `approve_send`.
- (c) A person without reconcile permission: I simulated this by removing `reconcile` from `allowed_actions` in the reloaded read. They get no reconcile button, every step is off, and a tap, keyboard press or double click sends no second `approve_send`. (d) Once the item is reconciled ("It didn't arrive", 200), the steps unlock straight away in the same session and after a reload. The Decide bar pins to the bottom again (fixed at 747-844 on a 390 screen, 522-640 on 320), and the single allowed resend goes out once with a new key at revision 5. (e) On W-2001, W-2006, W-2007 and W-2009 the Decide bar is still pinned at 390 and 320, the last section clears it and nothing scrolls sideways. Desktop is unchanged: the panel is static, there is no padding and labels don't wrap. (f) The F-18 "Record the outcome" link shows and can be tapped on W-2111 and W-2114 at all three widths. Neither item draws a workspace. Tapping it at 390 opens `/work/W-2111/outcome`. I put W-2111's `rfp_outcome` onto W-2001 so the link and a workspace appear together. The link sits above the workspace with no overlap, it is clear of the pinned bar (link 627-671, bar from 672 at 390) and nothing scrolls sideways.
- Regression: Playwright `workspace`, `work-item`, `decide`, `response` and `rfp` specs passed 126 of 126 (exit 0). The second fix only touches the lock input and the CSS rules for the flowing Decide panel. The base merge only touches WorkItemOverview (the RFP link and the order of note and links in the state panel) and F-18 files. So I did not redo the direct mock calls I ran at af3b958 (CSRF, 422, 404, 409, replaying a key). Those results stand.
- **Not proved:** a real backend (E-WORK-STEP, the workspace read and the server-side refusal of a resend while uncertain are all unimplemented; the mock accepts any `approve_send` it is given, so only the frontend lock is proven), real per-record or per-tenant permission (I could only simulate a person without reconcile by changing the read), backend idempotency, real sends or providers, and real evidence upload.

## Findings
- QA-5-3 | non-blocking | low | frontend | Carried forward, unchanged. On a phone, the uncertain callout "Delivery to Lagoon Health couldn't be confirmed." sits below the fold after the press (y 938 on an 844-high screen at 390). The diff does not touch it.
- QA-5-4 | non-blocking | low | frontend | Carried forward, unchanged. A 2001-character note in "Return with a note" on W-2001 shows "Keep the note to 2000 characters." twice. It is still refused before any request is sent. The diff does not touch it.

## Verified
- QA-5-1 | verified | Touch tap on W-2008, persona finance_lead. 390x844 (button at 776-826):
  - Same session right after the press (scrollY 123): the Decide panel flows (`ws-decide--flow`, static), the hit is the button and `/actions` returns 200.
  - Scrolled to the bottom (scrollY 679): the Decide panel is at 605-748, above the button, which gets the hit and a 200.
  - After a reload: at scrollY 0 the button is already visible and gets the hit. After picking an answer (scrollY 394) and at the bottom (624), the tap is answered with 200.
  - In a new tab: same as after a reload, 200 at both positions.
  - 320x640 (button at 572-622): every one of the same six cases gets the hit and a 200. At the bottom the Decide panel is at 401-544.
  - Every case sends exactly one `/actions` POST and nothing to `/steps`.
  - At 1440, Record and continue is answered with 200, and `.ws` padding and `scroll-padding-bottom` are 0/auto.
  - Screenshots: `a-390-*-bottom-before.png`, `a-320-*-bottom-before.png`.
- QA-5-2 | verified | Not touched by the second fix or the merge, so the af3b958 retest stands: long labels wrap inside 320 and 390 and stay `nowrap` at 1440. (e) also confirms that pinned items still have no sideways scroll at 390 and 320.
- QA-5-5 | verified | Press "Approve and send" on W-2008, then reload, at 390, 320 and 1440. Both steps are `aria-disabled="true"` and the hint reads "Confirm what happened first." I then tried, in order: a touch tap or forced click on "Approve and send", focus with Enter and Space, a forced double click, two more touch taps, and a forced click on "Return with a note". No form opened. The mock log at each width shows one entry, for example `[["approve_send",200,"6df20b2b",3]]`, so there was no second key and no resend. The no-reconcile variant (c) at 390 and 1440 also shows one entry. Screenshots: `b-390-reload.png`, `c-390-noreconcile.png`.

## Evidence (commands)
- `cd frontend && FRAME_FIXTURES=1 API_ORIGIN=http://127.0.0.1:4802 npx next build` (exit 0). `MOCK_PORT=4802 node mock/server.mjs` and `API_ORIGIN=http://127.0.0.1:4802 FRAME_FIXTURES=1 npx next start -p 4801` were started by me and stopped by their own PIDs and ports before the e2e run. Afterwards both ports were free and the worktree was clean. The `.next` and `test-results` folders were already there before my run.
- `NODE_PATH=frontend/node_modules node qa.cjs`: cases (a) to (f) plus (d2), the same-session press then reconcile. The output is in `qa.log` and `qa2.log` (0 failures). On the first run the desktop pass of (d) stopped on a tap without touch support. I fixed the script and re-ran the rest with `SKIP=1`.
- `E2E_PORT=4801 MOCK_PORT=4802 FRAME_FIXTURES=1 npx playwright test e2e/workspace.spec.ts e2e/work-item.spec.ts e2e/decide.spec.ts e2e/response.spec.ts e2e/rfp.spec.ts`: 126 passed, exit 0 (`e2e.log`).
- Scripts, logs and screenshots are in `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/e200da9c-af6a-499f-b21a-ccf36964230e/scratchpad/qa-f17-r5c/`.
