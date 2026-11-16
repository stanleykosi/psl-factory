VERDICT: PASS
COMMIT: 6d857c318ffb4d772126d9e236e9dba90f0625ba
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- Every delivery claim comes from the data: "Verified", "Delivered" and "Bounced" are the item's own `tag`, the status tag is `workspace.status`, and the sentences are fixture strings. The frame works out no count, date, "v2" or tone. A recipient marked `unknown` or `uncertain` never reads Received or Delivered.
- The uncertain fixture (W-2212) has no `steps`. Reconcile is its only action (one POST to `/actions`, none to `/steps`). The lock comes from the item's own `reconcile`/`allowed_actions`, so a reload keeps it. No resend control exists.
- Access: whether "Edit your update" shows depends only on `workspace.steps` (W-2210 has none, and a mock step POST on it gets 404). Nothing new reads `/me`. The 404 and wrong-tenant handling are the unchanged F-17/F-21 paths.
- No secrets, tokens or real contact addresses in the diff. Names are sample names from the boards. No new dependency. No change under `src/api`, `apps`, mock handlers or existing fixtures. The build.md limits (contract mock only, D-RETURN, D-ALERT-PROVIDERS) are stated and nothing beyond them is claimed.
- Three non-blocking test and copy gaps are listed below.

## Findings
- SEC-1-1 | non-blocking | medium | frontend | The access test proves nothing. Expected (AC12): the 404 read draws `NoAccessState` with no client, title or id, and the 401 draws the signed-out callout with `next`. Actual: the test named "a 404 on the read shows no title, client or id; a 401 shows the signed-out callout" `waitFor`s on `not.toContain('Lagoon Health')`, which passes at once before the fetch settles. It never checks that the no-access state appeared, and it has no 401 case at all. Fix: wait for the no-access state's heading or text, then check for no title, client or id; add a 401 case that checks the signed-out callout and `next=/work/W-2299`; or rename the test to what it covers. Path: frontend/tests/weekly-returned-received.test.tsx:247-258.
- SEC-1-2 | non-blocking | low | frontend | The e2e "every request in this run went to the local mock" only checks its own page load. `beforeEach` empties `requests` (e2e/weekly-returned-received.spec.ts:17), so the test at :84 sees only W-2211's requests, not the run's. Expected (AC19): every request in the run is checked. Fix: run the hostname check in an `afterEach`, or collect requests in a list that is never reset. Path: frontend/e2e/weekly-returned-received.spec.ts:84-87.
- SEC-1-3 | non-blocking | low | frontend | This feature now shows the shared reconcile panel on a weekly client report. On desktop that panel says "The factory won't resend until a person confirms what happened, so the client is never invoiced twice." That is invoice wording on a report, and it is a no-duplicate promise, which the spec (D-LINE-WORKSPACE limits) says not to claim on the mock. The text is older and lives in a read-only lane (`features/response/**`), so it is not blocking here. Fix (follow-up): make the sentence neutral or data-driven (for example "Nothing is resent until a person confirms what happened."), or take the reason from `reconcile`. Path: frontend/src/features/response/ReconcilePanel.tsx:136.

## Verified
- None (round 1).

## Notes
- The tag replaces the receipt word on a recipient row (Sections.tsx:344). If a future backend sends a "Delivered" tag on a row whose `receipt` is `uncertain`, the row will read Delivered. This is the approved D-97 rule (the backend owns the label). The real per-recipient receipt record (Conflicts 3 proposal) should make tag and receipt consistent on the server side.
- The `text` rows that now draw `item.tag` change no earlier fixture: a scan of `mock/fixtures/**` finds tags on text or recipients items only in W-2211 to W-2213.
- W-2212's reconcile option "It didn't arrive. Allow one resend of the same version." records an answer through E-WORK-ACTION; it is not a send from the client. The mock still answers 501 for `/actions`, so the reply and the next state are unverified (mock evidence only, as the spec says).
- Everything is React text rendering: there is no `dangerouslySetInnerHTML`, no URL built from data and no new header in the diff.
