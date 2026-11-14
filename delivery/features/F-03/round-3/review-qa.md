VERDICT: PASS
COMMIT: 3f684410f771cf53c1103d40aaa7977b09c084b3
REVIEWER: qa
AUTHORITY: integrated QA (UI against the contract mock only)

## Summary
- Built `frontend/` and `architecture/` from `git archive` of this head into a scratchpad copy (`npm ci`, `next build`, `next start -p 3241`) with the contract mock on 3242. Drove the pages with Playwright/Chromium and called the mock endpoints with curl. Stopped only those two processes; 3301/3302 were not touched.
- Passed: spec criteria 1-17 on the pages (six facts, state tags, station track at 390/760/900/1079/1080/1280, agent card, decision link by persona, W-1005 warning callout with no buttons, 401/403/404/500/network states, history WAT times, restricted rows, filter/paging requests, polling). Criterion 18 (fixture schema validation) and the vitest suites were not re-run; I relied on checks.md GATE: PASS.
- Not proved: nothing was tested against Django, PostgreSQL or real permissions. The mock does not vary `you_can_act` or the history by persona or by the user's real access, so "wrong user" and "wrong tenant" were exercised only through the fixtures (W-1002) and forced 403/404 responses. Real access control, real revision changes and real agent progress are unproved. `/work/[id]/decide` (F-04) was not opened. It is a link only.
- No blocking findings.

## Findings
- QA-3-1 | non-blocking | low | frontend | The mock persona cookie does not change the item payload. `pm` on W-1001 still shows "You are Finance Lead." and "Open the decision", because the mock fixture returns `you_can_act: true`. The page is right to render what the API says. This is a mock limit, so real wrong-user behaviour must be retested against the backend (W-1002 covers the `you_can_act: false` rendering).
- QA-3-2 | non-blocking | low | frontend | The history fallback is generic. `/work/W-1002|W-1003|W-1005/history` all show the default invoice history ("Drafted invoice", "Started the line"), which does not match a weekly client update (W-1003). The spec allows this fallback. Add per-id history fixtures before anyone demos those pages.

## Verified
- UI-2-1 | verified | Station track on /work/W-1001. scrollWidth equals the viewport at 390, 760, 900, 1079, 1080 and 1280, with no sideways scroll. The 7 stations sit in a single column (same x) at 390/760/900/1079 and in one row (same y, 7 boxes) at 1080 and 1280. Exactly one `aria-current="step"` at every width.
- UI-2 note (effect-uncertain station) | verified | /work/W-1005 at 1280: the Deliver box is solid amber with white text. Below 1080 I did not screenshot W-1005, so the pale amber row there is unproved by me (unit/e2e claimed by build.md).

## Evidence
- API (curl to 3242): `/api/v1/work/W-1001..W-1006` return 200. `W-1099` returns 404 `not_found`. `ANY-OTHER` returns the W-1001 default. History `W-1004`: `kind=decisions` gives 4 rows; `limit=10` gives 10 rows and `next_cursor=o:10`; `limit=10&cursor=o:10` gives 2 rows and no cursor; `limit=7` gives 12 rows, so it behaves as 20; `kind=evidence` gives 3 rows. `X-Mock-Scenario` 401/403/404 return those codes on item and history. No response has a `_kind` key (`grep -c '"_kind"'` returns 0).
- Page W-1004: Drafted/Reviewed/Approved Earned with 10:58/16:12/16:40 times. Sent "Not yet", Receipt recorded "Unknown", Verified "Not yet", Paid note present. W-1005: Sent and Receipt recorded "Unknown", warning callout, 0 buttons on the page. W-1001 has the "Open the decision" link to `/work/W-1001/decide?task=T-2001` and "You are Finance Lead." W-1002 reads "Only a Finance Officer can decide." with no link. W-1003 reads "step 3 of 4" and "Cannot approve, send or pay.", with no buttons.
- Errors (the route intercepts hit only the work endpoint): 403 and 404 both show "You can't open this work item" with "Back to my queue" to /my-work, and neither the id nor the title appears. 401 shows "You're signed out. Sign in" with `next=%2Fwork%2FW-1001`. A first-call 500 shows an error card, and Try again shows the item (2 fetches). A network abort shows the error card. A persona `none` user sees the shell's "No sections are open" page. A /me scenario 403 shows the shell's forbidden page, which is correct for /me.
- Note: the error card reads "Reference server_error for support." and "Reference network_error for support." That is a code, not a support reference. The mock supplied no reference.
- History W-1004: 12 rows by default, in fixture order, newest first. "12 Nov 16:40" is the WAT form of 15:40Z. Includes a Returned v1 and Approved v2. The restricted row shows only time, actor and "Restricted". The controls are the filter buttons, the rows-per-page select and links only. Request URLs: `kind=all&limit=20`, `kind=decisions&limit=20` (4 rows), `kind=all&limit=10` (10 rows), then `limit=10&cursor=o%3A10` (12 rows, and Show more gone). A first-call 500 on history shows an error card, and Try again gives 12 rows. At 390px there is no sideways scroll.
- Polling: W-1003 fetched 3 times in about 11 s (an initial fetch plus polls at 5 s intervals). A forced 500 poll left the item on screen and showed the refresh message. W-1001 fetched once in 12 s.
- Reduced motion: computed animation names are `[]` with reduce and `["psl-pulse"]` without.
- Hidden-tab polling and the history reload when the revision changes were not exercised in the browser. Only unit tests claim them.
- Scratchpad scripts: `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad/qa/frontend/qa-run.mjs` and `qa2.mjs`, with screenshots next to them.
