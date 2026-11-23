VERDICT: PASS
COMMIT: cdea4f987fb2e1d59cf051a8bdf96dd7197cf6e9
REVIEWER: reviewer-security
AUTHORITY: reviewer-security (lighter panel, D-180)

## Summary
- Delta 1817c34e to cdea4f98 in scope: only frontend/mock/work-live.mjs (30 lines) and the generated frontend/src/api/live-schema.d.ts (API 1.26.0 types). Nothing changed under features/workspace or features/work-item, so the upload, 403/404 states and link building are the code I passed in round 1.
- Case file upload: the live upload route and its CSRF check in the mock are untouched. The 1.26.0 schema still types the upload with an X-CSRFToken header and an upload_id response. No new upload field is read by the page.
- CSRF and session handling: no src change. The schema keeps X-CSRFToken on every write.
- 403/404: unchanged. The mock edits add only fields (history actor_kind and entry_id, next_before, panel contract_path) and add no new refusal path.
- Links from server data: the new 1.24.0 to 1.26.0 url fields (tracking_url, proofs_url, queue_output_url, download_url) have no consumer in the page; the only server-supplied href is still item.output_url (SEC-1-1). History actor_kind is looked up in a fixed tag table and draws plain text only.
- Not exercised: I ran no tests and no server. I judged this from the diff and a grep of the source.

## Findings
- SEC-1-1 | non-blocking | low | frontend | Carried into F-87. item.output_url is put straight into an anchor href with no scheme check (LiveWorkItemView.tsx:229-233). The backend supplies the value, so it is trusted today. Allow only a same-origin path or https. Apply the same rule to the new tracking_url, proofs_url, queue_output_url and download_url when F-87 renders them.

## Verified
- SEC-1-1 | verified | still open as a non-blocking carry. The code at LiveWorkItemView.tsx:229 is unchanged. It is not a regression.

## Notes
- The mock's new fields come from API 1.24.0 and 1.26.0. The page draws none of them yet, so there is no new exposure. F-87 must review each one as it is rendered.
