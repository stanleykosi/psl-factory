VERDICT: PASS
COMMIT: 9ee65d4d689c0101591a3f94a5146c72db9545bc
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- The v4 to v6 repoint is complete and in one commit. 856daff touches exactly the 5 named files, and running `openapi-typescript` on v6 again gives a `schema.d.ts` byte-identical to the committed one. The mock, `gen:api`, the drift test and the client header all say v6.
- Start safety holds. The key is made when the line drawer mounts and dropped when it unmounts. A synchronous `writing` ref stops a double press from sending twice. A network error, timeout or 5xx locks the form, and "Check again" resends the stored `sent.current` body with the same key. Nothing is resent automatically, and only a 409 or 422 makes a new key.
- Nothing is invented. Lines come only from E-LINES and options only from E-LINE-OPTIONS. The case comes only from the chosen option or the fixed line, otherwise start is disabled. Money and evidence are never rendered or sent. The body is exactly `{line, case_id, case_revision, intake, idempotency_key}`, and CSRF is added by the existing middleware.
- The mock runs its checks in the order the spec gives, uses Ajv 2020 against the v6 request schema, and strips its mock-only keys. The tests cover the negative cases: 403, 404, both 409s, 422, CSRF and an extra property.
- The findings below don't block. They are one key-policy gap, two contract points for the backend, and some stale version text in tests.

## Findings
- TECH-1-1 | non-blocking | medium | frontend | After a definitive 403 or 404 the form unlocks but keeps the same idempotency key. If the person then changes the project or a field and presses start, the same key goes out with a different body. That is the opposite of what the spec's assumption promises ("the same key is only ever resent with the same body"). On a backend that records keys before its permission or case check, it would also give a confusing 409 `idempotency_key_reused`. The spec only requires a new key after a 409 or 422, so this is a gap, not a contract break. Expected: a new key after any definitive 4xx, because nothing was written. Actual: `useStartWork.ts:186-208` makes a new key only in the 422 and 409 branches.
- TECH-1-2 | non-blocking | medium | backend | Whether a retry is safe depends on the order of the backend's checks, and the contract doesn't fix that order. Suppose the first POST did start and its answer was lost. "Check again" then only works if the backend looks up the idempotency key before it checks `case_revision` and the line grant. If it checks the revision first, a start that already happened, and moved the revision on, answers 409 `stale_revision`. The drawer would then unlock with a new key, and the next press would start the same work twice. The mock checks the key first (`mock/start-work.mjs:184-199`, though the line grant comes before the key). Also, any replay answer other than 201, for example a 200, shows as "uncertain" for good (`useStartWork.ts:181`). Please add both points to the PMO-0-1 question in build.md: look up the key first, then answer with the stored 201.
- TECH-1-3 | non-blocking | low | integration | Some tests still name old contract versions. `tests/mock-work-list.test.ts:15` still reads `architecture/packages/v3/openapi.json` for E-WORK-LIST. The test name at `tests/mock-decide.test.ts:206` still says "v4" but validates through `OPENAPI_PATH`, which is now v6. Neither file is in F-05's lane, and the spec's 5-file repoint list doesn't cover them. Still, after the repoint there should be one contract version. Fix this in whichever lane owns those tests, or when rebasing onto F-06, F-07 or F-08.
- TECH-1-4 | non-blocking | low | frontend | A 201 is trusted without checking its body. `useStartWork.ts:180` casts `data` and reads `work_id`. With an empty 201 body (`data` undefined), it throws a TypeError out of `submit`: the error isn't caught and the drawer shows nothing. With no `work_id`, the browser goes to `/work/undefined`. Expected: a 201 without a string `work_id` is treated as uncertain.
- TECH-1-5 | non-blocking | low | integration | The rebase isn't done yet. Base 2443664 isn't on `main`, and F-06, F-07 and F-08 haven't merged yet (their feature.json state is not merged). So the spec's rule that "every fixture, theirs included, must pass mock-contract against v6" can only be checked after the rebase. Re-run `tests/mock-contract.test.ts` and `tests/api-schema-drift.test.ts` after the rebase, before merging.

## Verified
- None (round 1).

## Notes
- The first-field search in `DrawerFrame.tsx:50` builds its selector by splitting a string. It works but is fragile; `panel.querySelector('.sw-body')?.querySelector(FIRST_FIELD)` would be simpler.
- Closing the drawer while a POST is in flight leaves the request running. A 201 still moves the person to the new work item. That is acceptable, and it matches "If it started, it will appear in My work".
- Keys in the mock's `started` map are shared across personas: a replay by a different persona with the same key and body gets the stored 201. This affects the mock only. The real backend should tie keys to the caller.
- The `server.mjs` fixtures-loader change, which skips `START_OPERATIONS`, goes beyond the spec's "one line each" list. It is needed, and build.md declares it.
