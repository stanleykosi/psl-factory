VERDICT: PASS
COMMIT: 831b17164ca8b1200e9ff84d2d486ea0d7dc7dc5
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- Both pages match the spec contract. The save body is built from the read record (channel and frequency as read, expected_revision omitted when absent, events in order, digest and quiet hours desktop only). 409 re-reads and drops edits, 422 shows the message, 401 shows the signed-out state, and nothing retries.
- Proposal fields are typed locally in `contract-proposal.ts` and tolerated when absent. Search and Filter hang on `total`, and the count and unread text are never computed from rows.
- No external connections and no browser storage. The client is the shared same-origin one with its CSRF middleware. `masked_number` is read in one place and never sent.
- Mock and test edits are minimal. The `server.mjs` diff is exactly seam items 1-7. The `mock-contract.test.ts` diff is exactly edits (a)-(c). No existing test was weakened. Nothing outside the lanes changed (src/api, shell, package.json untouched).
- The gate passed on this head. I read the code and did not re-run the tests.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `AlertSettingsPage.tsx:34,90-91`: a 200 save response without `events` goes to the "missing_events" error card, and the "saved" notice is then not shown. The spec says to replace state with the PUT body, so this is consistent. Consider keeping the previous prefs and revision if a v7 PUT ever returns no events.
- TECH-1-2 | non-blocking | low | frontend | Phone back links "← Home" and "← Notifications" sit level with the heading, not on their own line (build.md E-4). The builder discloses it. It needs the design engineer's approval and is not a code defect.

## Notes
- The `bare` mock scenario answers 404 to PUT-less v7 reads and ignores q/agent/unread, as a v4 backend would. That is faithful to PMO-0-2.
- `mock/alerts.mjs` validates the PUT body with Ajv against the overlay and applies the 409 check only when `expected_revision` is present, as spec'd.
