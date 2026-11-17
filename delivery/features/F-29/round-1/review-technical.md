VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 9a6dd8ea67a79b6f699f55bdbe4ed24c873baeeb
AUTHORITY: technical reviewer (lead), TECH

## Summary
- Approve and Return reuse useDecision (claim, expected_revision, one write at a time, uncertain and stale states). Controls show only when the task says you_can_act is true and the document is not returned. The note rule is checked before any request.
- Section text, notes, checks and the returned note all render as React text (paragraphs split on blank lines). Nothing uses dangerouslySetInnerHTML. A hostile mock variant exists. body_url is a link only, never fetched.
- The shared-file edits are narrow and correct: the ComingNext removal in ProjectJourney.tsx is dead-code cleanup (documents now goes through hasTabContent), tabsModel.ts adds one tab, and server.mjs adds one hook that falls through to F-23's rule for other documents.
- Access: 403 and 404 look the same. A case_id, version or document_id that differs from the address shows the no-access panel. A missing or invalid ?v= makes no request. Mock visibility follows list.json.
- The handoff note is added to BACKEND-HANDOFF.md. checks.md passed. No tests were weakened. The edits to existing tests only adjust the "documents is 501" and "coming next" expectations.

## Findings
- TECH-1-1 | non-blocking | low | frontend | NoText renders `<a href={doc.body_url}>` with no scheme check (DocumentParts.tsx NoText). The value comes from the server, and a javascript: URL would be an injection route if it were ever sent. Expected: only render the link for http(s) or same-origin relative URLs.
- TECH-1-2 | non-blocking | low | frontend | After a return, if the re-read document never shows `returned` (for example the backend keeps the old state), ReviewNotice shows "Recording the return…" indefinitely with no retry (DocumentReview.tsx, the view.kind === 'done' return branch). Expected: a "could not confirm" fallback like the approve path has. The mock flips the state, so this is unreachable in e2e.
- TECH-1-3 | non-blocking | low | frontend | DocumentsTab passes `VIEW = { register: 'issues' }`, a leftover from the registers tab. It is harmless because buildTabQuery sends register only for the registers tab.

## Verified
None (round 1).
