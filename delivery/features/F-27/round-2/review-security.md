VERDICT: PASS
COMMIT: 43a3d5fcad8e0072a85bcab2625a446b88d037e6
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- SEC-1-1 is fixed. Whenever the From shown on screen comes from `from_options[]` (one option or a chosen one), the request now names that person as `from_person_id`. The mock records a request without `from_person_id` as the caller.
- SEC-1-2 is fixed. When the backend pairs delegates with a From, To lists only the delegates paired with the From shown. When there is no From list (the caller), it lists only the unpaired ones. The mock applies the same rule.
- No security control was weakened. The round-2 diff (`ab5a4f0f..34c38e4e`, frontend) moves the phone actions into the Drawer footer, closes the sheet when the list moved, rewrites 422 labels and adds a 409 message for a failed re-read. The submit still checks every value against the lists, one write still runs at a time, and the add controls still depend on `can_add` and `revision`.

## Findings
None.

## Verified
- SEC-1-1 | verified | **Form.** `frontend/src/features/setup/DelegationForm.tsx:124` now reads `if (fromPerson) body.from_person_id = fromPerson.person_id`. `fromPerson` exists only when it comes from `from_options[]` (a single option, or the chosen one, line 81), so the "You" case still sends nothing. **Mock.** `frontend/mock/delegations.mjs:130-135` no longer falls back to the single option: a missing `from_person_id` is the caller, and the new row's From is `{name: <persona name>, is_you: true}`. **Tests.** The component test for the `authority` scenario expects `from_person_id: 'P-KEMI'`. A new mock test shows that a request without From is recorded as `{name:'Ada Okafor', is_you:true}`, and the Kemi→Chika combination is refused. The round-2 build.md says these tests fail on the round-1 code.
- SEC-1-2 | verified | **Form.** `DelegationForm.tsx:84-86` sets `paired` from the presence of any `for_person_id`. If there are two or more From options and none is chosen, To has no options and waits. Otherwise To keeps only the options whose `for_person_id` equals the shown From's `person_id`. With no From list that value is `undefined`, so only unpaired options remain. **Mock.** `delegatesFor` (`frontend/mock/delegations.mjs:97-102`) uses the same exact match. **Tests.** New component test "pairing keys without a From list (SEC-1-2)": To lists only the unpaired option, and the PUT carries no `from_person_id`. In the `authority` scenario, with Kemi shown, only Femi is listed.

## Notes
- Re-checked after the round-2 refactor:
  - The Drawer footer `actions` call the same `submit`, which still returns early on `busy` or `blocked`.
  - The `useDelegationAdd` ref still serialises the desktop panel and the phone sheet.
  - Values are still taken only from the current lists, so a planted option sends no PUT.
  - `invalidMessage` builds its text only from the form's own field labels, or shows the backend's message as plain text.
  - `STALE_UNREAD` and the notice when the list moved claim no effect beyond what was returned.
- The round-1 notes still stand. The backend message on a 403/404 PUT is shown as is. D05, D-ADMIN-AUTHORITY and G-SCR13A-1/-5 are backend or PSL decisions. This screen is not a security control.
- Evidence: I read the code and did not run anything. The tests cited are the builder's runs (322 vitest, 26 e2e).
- Merged head 43a3d5fc, checked on 17 Nov. `git diff 34c38e4e..43a3d5fc` changes no delegation file: there is no diff under `features/setup/**`, `useDelegation*`, `mock/delegations.mjs` or the delegation fixtures, and none under `src/api/**`, `src/components/**`, `src/shell/**` or the package files. The only shared file touched is `frontend/mock/server.mjs`. There F-26 adds `isMoneyRequest`, which routes only the money tab of E-PROJECT-TAB and E-REPORT, before the M-1 list. E-DELEGATIONS and E-DELEGATION still go through the persona choice and the CSRF check (`server.mjs:265-270`) before `delegations.mjs`. `mock-contract.test.ts` only swaps its 501 example to E-PAYROLL-MATCH. The verdict stands. I did not open the coordinator's merge-checks.log or merge-e2e.log.
