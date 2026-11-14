VERDICT: PASS
COMMIT: edc476370a1b20444d9807811a9d7b0a6ed2f503
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Reviewed the round-2 diff 06b4c0e..edc4763 (9f91efe QA-1-1, edc4763 QA-1-2). The diff touches only display and mock code. Save, CSRF, the request body and the retry rules are unchanged.
- The browser does not decide anyone's authority. Whether the panel closes depends only on the API's re-read run through the existing `isEditable` (`can_change === true` and so on). This choice only moves where the message appears. It never enables an action. If the re-read fails, the message stays in the panel.
- The new page-level callout leaks nothing new. It shows the same text the panel showed before: the API's `{code,message}` message or fixed text. To that it adds two fixed sentences, with no rule names, ids or values. It is plain React text, not HTML.
- "Nothing you entered was saved." is added only for the `rejected` outcome, which `useRuleSave` sets only for 409, 403 and 404. These are definite non-saves. It is not added for `saved` or `unconfirmed` (5xx or network error, re-read done). The `unchecked` outcome never calls `announce`.
- The mock evidence counter now lives in `setup.mjs` and is reset by `resetSetup()`. This is mock-only and has no security effect.

## Findings
- SEC-2-1 | non-blocking | low | frontend | The rule that "the not-saved claim never appears on an uncertain result" has no test. Expected: a unit test where a 5xx is followed by a re-read with every row's `can_change` false. It should check that the page callout contains EDITOR_GONE but not NOT_SAVED. Today only the 403 path is tested. Actual: the code is correct (frontend/src/features/setup/SetRulePanel.tsx:77-84, `rejected` is true only from line 164), but nothing stops a regression. Path: frontend/tests/setup-rules.test.tsx.

## Verified
- SEC-1-1 | reopen | Not in this round's brief (build.md defers it). Save is still `disabled={busy || locked}` and ignores an upload in progress (frontend/src/features/setup/SetRulePanel.tsx:257). Still non-blocking and low. The round-2 change neither worsens nor fixes it.
- SEC-1-2 | reopen | Backend proposal, unchanged. The mock still does not check `evidence_id`. Still non-blocking, for T-SETUP.
- SEC-1-3 | reopen | Backend proposal, unchanged. The readonly mock rows still carry `proof_case`. The frontend still uses only editable rows. Still non-blocking, for T-SETUP.

## Notes
- Impact on round-1 conclusions: none weakened. The CSRF path, the 401/403/404/409/422/5xx handling, the single-flight save, the fixed-route links and the absence of raw HTML are all untouched. No new packages and no secrets.
- `closedNotice` in RulesView is never cleared after it is shown, though the Finance disclosures clear it. It holds only fixed or API message text for the same signed-in person, so this is not an exposure. If the wording needs to change, that is a UX point.
- On a `saved` outcome where the right is then withdrawn, the callout says "Saved as version N. You can no longer change these rules…" and correctly does not claim a non-save.
