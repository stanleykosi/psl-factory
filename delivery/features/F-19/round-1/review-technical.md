VERDICT: PASS
COMMIT: effdc3f55c827a61a258ee44f6904654cbd6eaee
REVIEWER: reviewer-technical
AUTHORITY: delegated technical review

## Summary
- Code matches the contract: three typed calls only, exact PUT body `{expected_revision, name, email}`, a synchronous ref guard against double press, no resend, and one reload after a 200, 409, 403 or unclear failure. 422 maps `fields[]` to the inputs. No `/me` use.
- Mock follows the spec's check order (403, 404, shape 422, field 422, 409, success). Replies are validated against v7. `server.mjs` shows only the import, the operation IDs, the reset call and one dispatch line.
- `tests/mock-contract.test.ts` edit is additive only (a path value, a body, three `{none: 403}` rows). No `expect` was removed or loosened. Needed because the generic test calls every M1 operation, and persona none must get 403 for these. Accepted.
- The three extra `E-CLIENT*.json` fixtures are needed because `server.mjs` reads `fixtures/<operationId>.json` for each M1 operation. The alternative was a `server.mjs` edit. Accepted.
- checks.sh passed on this head. Visual scores under 90 on three boards are the design engineer's call, not a technical defect.

## Findings
- TECH-1-1 | non-blocking | low | frontend | Tamarind Loans is `billing_contact_set: true`. The spec's fixture row says false, but acceptance 5 ("2 missing") needs true. The spec contradicts itself and the builder followed the acceptance criteria, so this is fine. The coordinator should correct the spec row. `frontend/mock/fixtures/clients/list.json`.
- TECH-1-2 | non-blocking | low | frontend | The clients-specific `ClientNoAccess` replaces the shared `NoAccessState` (which says "work item"). This is a reasonable deviation, and it follows the F-07 `ProjectNoAccess` precedent. Nothing about the record is shown. `frontend/src/features/clients/ClientStates.tsx`.
- TECH-1-3 | non-blocking | low | frontend | The saved state and the CL-3508 first-409 are kept per persona and client in module memory. That is a sensible adaptation to the five-persona generic test, and `resetClients()` clears both. Test-only coupling. `frontend/mock/clients.mjs:60-63`.
- TECH-1-4 | non-blocking | low | frontend | The CL-3507 "money absent" variant is not built, and CL-3509 covers an absent `money`. The list table also shows "Set" twice per row (STATE and BILLING CONTACT columns). Both are recorded in build.md. No action needed beyond the design engineer's attention.

## Verified
None (round 1).
