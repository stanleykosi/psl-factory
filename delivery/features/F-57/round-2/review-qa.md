VERDICT: PASS
COMMIT: 5262fbd45ea1743f1bbde3e0c5fc07eaa992e732
REVIEWER: qa
AUTHORITY: integrated QA on the current head

## Summary
- Mock (own mock on 4981, production build of this head on 4980): all 8 personas drawn at 1440 and 390 with the expected menus, role words and Start work; five long role names clip with an ellipsis at 1440, 1280 and 1100 with no sideways scroll; POST /__mock/reset gives 204; the csrf_failed notice shows, the second press saves, one PUT per press.
- Live (Django 8002 on Postgres 55433, `next start` 4980 rebuilt with API_ORIGIN=http://127.0.0.1:8002): signed-out state with no anchor in main, one GET /session 200 with the token; sign-in rotates the token; live-lead and live-multi show "Name · role words" matching the same session's role-dashboard; live-none shows the name alone; phone menu matches. No retired/accounts/admin href anywhere in the frame.
- Live csrf_failed (token rotated behind the app, live-lead, alert settings Save with the page's GET served from a fixture because the live page is an accepted error card): one PUT answered 403 csrf_failed, one GET /session, "Press the action again" shown, no automatic repeat; the second press used the new token (the live PUT then gives 405 because the endpoint is not connected, not csrf).
- Six download routes with a valid id reach Django through the proxy (302 to /accounts/login/, the accepted A-55 behaviour) with the exact trailing-slash path; a non-matching path or bad id gives the Next 404 page. TECH-1-2 exact destinations: confirmed in `tests/next-config.test.ts` (45 tests in client and next-config pass) and in the built routes-manifest (7 rewrites, all to 127.0.0.1:8002).
- Not proved: a signed-in download returning a file; the signed-in `/me` 401 then `signed_in:true` reload path against live (unit-tested only); an Administrator account on live (see QA-2-1); no real WhatsApp or email provider involved.

## Findings
- QA-2-1 | non-blocking | medium | backend | Live account `live-admin` (superuser): `POST /api/v1/session` signs in but answers 422 `action_unavailable` "'invite_minutes' is a required property", and `GET /api/v1/role-dashboard` answers 422 the same way (Django log). Expected 200 matching the contract. Effect on F-57: the frame degrades as designed to the name alone, so the "Admin" role word the spec expects for administrators is not shown and that path is unproved live. Reproduce: `POST /api/v1/session {"username":"live-admin",...}` with a token from GET /session.
- QA-2-2 | non-blocking | low | frontend | At 800px wide the top bar no longer clips the role line (`scrollWidth` equals `clientWidth` with five long names) and the page does not scroll sideways; Start work stays inside the viewport. Noted only as evidence, no change asked. (Informational; remove if not wanted.)

## Verified
- UI-1-1 | verified | Mock with role-dashboard routed to five long names: 1440, 1280 and 1100 show clip true, document scrollWidth equals viewport, Start work right edge 1312, 1212 and 1032, and the who title holds the full "name · roles" text.
- TECH-1-1 | verified | `npx vitest run tests/client.test.ts` passes including the GET /session 403 csrf_failed case (one session call, kind csrf); live and mock runs showed exactly one GET /session after a csrf_failed write and no loop.
- TECH-1-2 | verified | Six download paths curled through 4980 reach Django (302 with Django's trailing-slash `next=` path, same as direct to 8002); `/cases/x/files/1` gives the Next 404; `tests/next-config.test.ts` passes.
