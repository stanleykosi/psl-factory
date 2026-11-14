VERDICT: PASS
COMMIT: ab641e93900ddddcaeaa19d323f33fa9045ef9d0
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- Against the real v6 contract the rebuilt pages degrade gracefully. Every PROPOSAL field is optional. A missing value shows "—" (list) or "Not known" (facts) and is never shown as 0. Tab counts, the total and Tola's summary simply don't appear, and the list total falls back to "N shown".
- Core contract reads are unchanged from round 1: the generated operation types, the 401/403/404 mapping, server row order, the no-request guard when `projects` is missing, and a static page title. The no-access state names nothing. The route segment is decoded once.
- The `server.mjs` edit is still minimal. The one changed assertion in `mock-contract.test.ts` strips the PROPOSAL fields with `contractBody()` and still validates the rest against the schema. That is spec-sanctioned and does not weaken the test.
- One non-blocking concern: the mock's proposal shapes differ from the shapes now drafted in architecture v7 (details in TECH-2-1). I did not re-run tests; checks.md shows 17 files / 415 tests green on this head.

## Findings
- TECH-2-1 | non-blocking | medium | frontend | The proposal shapes the client reads are not type-guarded and differ from the v7 draft. Today they only reach the page from the mock, so nothing breaks. Once a backend serves v7, `ProjectsList.tsx:97` (`item.next_milestone ?? '—'`) would render an object `{name, due}` as a React child and throw. `ProjectJourney.tsx:117` would print "PM [object Object]" because v7 `pm` is `{name, role, is_you}`. v7 `facts` is an array of `{label, value, money, unknown}`, but the client reads an object, so the strip shows "Not known". v7 `summary` is `agent_summary` `{agent, text}`, and the line `tone` and `station` are new. The client should check `typeof` before rendering each proposal field (string for `next_milestone`, `pm` and the line text), so that an unexpected shape degrades to "—" or "Not known" instead of throwing. When v7 is frozen, align `model.ts` and the mock fixtures to it. Under the standing rule this does not block the round.
- TECH-2-2 | non-blocking | low | frontend | The Active tab sends `status=active` by default (`model.ts` `buildProjectsQuery`). A v6 backend does not know this parameter. If it ignores it, the "Active" tab shows every project, closed ones included, with no marker. If it rejects unknown query parameters, the list shows the error card. The client does not filter and shows no status, so it cannot tell. Please record this as a coordination point with the backend developer, or send `status` only when the page has seen `counts` (which the list cannot know before the first read).

## Verified
- TECH-1-1 | verified | Round 1 had no findings. I re-checked its notes: `isJourney` still requires a non-empty `next` (unchanged), and the contract-only parts of both reads are still validated by `mock-contract.test.ts`.
