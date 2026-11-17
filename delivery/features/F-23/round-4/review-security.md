VERDICT: PASS
COMMIT: 81e06419df1929371e460af6cd2f2adb13192903
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- QA-3-1 is fixed in the shared decision page. When the decide answer says `work_state: "effect_uncertain"`, or the reloaded item is `effect_uncertain` or carries `reconcile`, the done view shows no green approved banner. It also drops the "Your decision was recorded." status, the next-step card and the Paid line. Instead it shows the shared uncertain notice and a neutral "NOT CONFIRMED" header.
- Nothing offers a resend. The only control on the uncertain done view is "Open the work item". The network and server-error path in `useDecision.decide` is unchanged: it reloads once, never resends, and keeps its own notice.
- The work-page lock (AC 19) is unchanged, because this round's diff does not touch `features/workspace`. On W-2305 the decision links stay `aria-disabled` with no `href`, and ReconcilePanel is still the only action. The e2e now also checks the uncertain wording on the decision page at 1440, 390 and 320.
- The second dlv-00 merge (F-27 delegation, head 81e06419) leaves every minutes guard intact (checked below). The first merge (F-26) also left the F-23 guards intact. `server.mjs` keeps `E-DOCUMENT` and the D-2304-only 501, and `minutesProposalsStripped` keeps all of its proposal checks.

## Findings
None.

## Verified
- QA-3-1 (security reading: no path shows success for an unconfirmed send) | verified | `DecideStates.tsx:414-417` sets `uncertain` from the answer's `work_state`, from the reloaded `state` or from `reconcile`, and `approved` now requires `!uncertain`. The status line (`:441-445`) and the next-step callout (`:455`) are gated on `!uncertain`. Two new tests in `decide.test.tsx` cover the uncertain `work_state` and a reloaded item with `reconcile`. They check that the success banner, "is approved", "Next step." and "Paid is tracked" are all absent, and that `counts().decides` stays at 1. The e2e in `e2e/minutes.spec.ts:142-144` repeats the check on W-2305.
- SEC-2-1 and SEC-3-1 (both non-blocking) carry forward unchanged, since neither `WorkItemOverview.tsx` nor `AgentNote` was touched.

## Impact assessment
- **No duplicate or missing notice.** On the 200-with-uncertain answer, `useDecision` does not set its own `uncertain` flag, so only `DoneView` shows the notice. On a thrown or uncertain error, the page goes through `reconcile` instead of the done view, as before.
- **Brief "recorded" before the reload.** A plain 200 answer with no uncertain `work_state` shows the recorded state until the reload arrives. If the reload then reports `effect_uncertain` or `reconcile`, the view switches to NOT CONFIRMED. That first state reflects what the server actually answered, so it is not a false success claim.
- **Fixtures.** W-2304 and W-2305 `.approve` now mark reviewed and approved as earned. W-2305 marks sent as `unknown`, not `not_yet` or `earned`. That is the honest state for an uncertain send: the human decision was recorded, and delivery is unknown. Receipt stays unknown. No fact claims a confirmed send.
- **Merged F-26 code** (`money.mjs` routing in `server.mjs`, the 501 test moved to `E-PAYROLL-MATCH`) is outside this feature and was reviewed in F-26. It does not affect the minutes routes.
- No new dependencies, secrets or `/me` reads.

## Second merge check (778e8681..81e06419, F-27 delegation)
- The merge does not touch `frontend/src/features/workspace`, `features/decide`, `features/work-item`, `fixtures/work/**` or `mock/workspace.mjs`, so the confirm set, the decision-link lock, the prefill, the restricted handling and the uncertain done view are byte-for-byte the same as at 778e8681.
- `frontend/mock/server.mjs`: the conflict was resolved as a union. `M1_OPERATIONS` (line 45) still lists `'E-DOCUMENT'` and `...ASSISTANT_OPERATIONS`, with `'E-DELEGATIONS'` and `'E-DELEGATION'` appended. The D-2304-only guard is still at line 301 and answers 501 for any other document. The new delegation branch is its own `operationId` check and comes before the generic fixture send, so it cannot answer a minutes or document route.
- `frontend/tests/mock-contract.test.ts`: only additions (delegation imports, a request body, PM and none mapped to 403, contract bodies). `minutesProposalsStripped` and its `links`, `items_default`, `values`, `date_format` and `warn_lines` checks are unchanged (lines 84-115).
- The other merged files belong to F-27 (setup delegation pages, mock, tests) and were reviewed in F-27. `round-4/merge2-e2e.log` ends with 122 passed, including the minutes and workspace specs.
