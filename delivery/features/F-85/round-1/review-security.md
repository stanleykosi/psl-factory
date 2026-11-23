VERDICT: PASS
COMMIT: 1817c34ee2d7bf6386c9ade3231304b9dbe3a7e4
REVIEWER: reviewer-security
AUTHORITY: reviewer-security (lighter panel, D-180)

## Summary
- The only write is the evidence upload (POST /cases/{case_id}/files). It goes through lane A's live client with the CSRF header slot, and the caseId comes only from the loaded item. The client checks type and size first; the service stays the final rule.
- 403 and 404 render fixed words ("This record is unavailable." or no-access); no ids or server text are echoed. A 403 caused by a stale CSRF token is told apart from no access.
- Decision links are built locally (/work/{id}/decide?task={id}) from numeric ids, and only when can_decide or can_claim is true. tasks[].url is never followed. Panel urls are limited to /api/v1/ paths by an allow-list regex, with no "..", "//" or query. Adapter commands are described and never sent.
- fileToEvidence is a proposal with no caller. Evidence ids are branded apart from upload ids, and a null id stays null.
- Merge delta (35189b45 to 1817c34e): only frontend/mock/server.mjs and frontend/src/api/client.ts changed in scope; nothing under features/workspace or features/work-item. The signed-out guard (psl_mock_session=out gives 401 on every /api/ path except session and logout) now runs before the live work and upload routes, so it only adds a refusal. The work-live upload, its CSRF check and its 403/404 handling are untouched. Sign-in and sign-out check X-CSRFToken. client.ts adds an empty csrfHeader type placeholder; the middleware still sets the real token. The project-path normaliser touches only project routes. No weakening found.
- Not exercised: the live upload (file storage is not running locally). I judged it from the code and the unit tests.

## Findings
- SEC-1-1 | non-blocking | low | frontend | item.output_url is put straight into an anchor href with no scheme check (LiveWorkItemView.tsx:229-233). The value comes from the backend, so it is trusted today. A javascript: or data: value would still run on click. Suggest allowing only a same-origin path or https, and adding rel="noopener" if the link can leave the site.

## Notes
- Upload errors map to fixed phrases, except that the `invalid` and default cases show the server field message or message text. This is acceptable, but the backend must keep those texts free of internals.
- UploadedFile.download_url is kept in state but never rendered or followed in this change. F-87 must apply the same scheme rule when it uses it.
- Panel url validation is a path-shape check, not an allow-list of routes. The server decides access per route, which is consistent with the backend-owned access model.
