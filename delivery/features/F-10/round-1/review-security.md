VERDICT: PASS
COMMIT: 02db3e841a47c4d83ed907c5bba467ef3a05a164
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Access is decided only by the API: the page never reads `/me` roles or destinations, and 403 and 404 render the same `MonthEndNoAccess` view, which shows no amounts, counts or task names.
- Restricted rows never link. `taskEnd` checks `restricted === true` before `work_id`, phone cards have no links, and the fixtures carry no payroll values or `work_id` on the Payroll row.
- `period` is checked on the server (`parsePeriod`, exactly one `YYYY-MM` string, month 01-12). Missing, repeated or malformed values call `notFound()` and send no request. Only the validated value reaches the API query and the sign-in `next`, which `SignedOutState` encodes.
- No money is derived client-side. Cash comes from the returned decimal string, using BigInt and no float. Unknown stays "Unknown" and is never 0. Counts are shown as returned and never counted from `tasks`.
- No new dependencies and no secrets in commits, fixtures or tests. Error handling reuses `WorkErrorCard`, which shows the contract's error code only, never the message or internals.

## Findings
- SEC-1-1 | non-blocking | low | frontend | Enum values from the response are used as lookup keys without a guard. If a backend sends an `agent_note.agent` outside tola/chidi/zainab, `AGENT_NAMES[note.agent]` is undefined and `agent.name` throws, so the whole page falls to the error boundary. That is also where the agent string is put into the `/agents/{agent}.png` src. In the same way, an unknown `state` makes `STATE_TAGS[task.state].text` throw, and an unknown `tone` gives the class `psl-tag--undefined`. All of these fail closed: no data is exposed, and the image path stays same-origin. Expected: skip the note, or fall back to a neutral tag, when a value is not in the known set. Paths: frontend/src/features/finance/month-end/MonthEndView.tsx:153-156, frontend/src/features/finance/month-end/model.ts:110-114.

## Verified
None (round 1).

## Notes
- Live probes against the shared mock (127.0.0.1:4012):
  - finance_lead with `2026-10` gives 200. `2026-09`, a missing period and a repeated period give 404.
  - Persona pm gives 403 `{code:"forbidden", message:"Month-end is for Finance."}`.
  - `psl_mock_month_end=__proto__` falls back to the default fixture because of the `Object.hasOwn` guard.
- On the shared build (localhost:4011), `?period=2026-13` and a `<script>` payload both reach the not-found fallback (`NEXT_HTTP_ERROR_FALLBACK;404`). The payload appears only escaped inside Next's RSC flight JSON, and nothing is rendered as HTML. The HTTP status is 200 because the response is streamed in dev. That is framework behaviour, and nothing in this change causes it.
- Restriction is enforced by the backend, and that is how it should be. On a pure v4 body there is no `restricted` flag, so a row that has a `work_id` would link. The real E-MONTH-END (T-FINANCE) must leave out `work_id`, or set `restricted: true`, on any row the caller may not open. E-WORK-ITEM must still enforce its own 403/404. This is a note for the backend lane, not a frontend defect.
- `workHref` uses `encodeURIComponent`. A `work_id` of `..` would still resolve to `/`, and that value comes from the trusted API. This is not a concern now.
- Pre-existing behaviour: `WorkErrorCard` shows the server's `code` string. The pattern is shared with other features and has not changed here.
- Text in evidence and comments tried to direct nothing. No prompt-injection content was found.
