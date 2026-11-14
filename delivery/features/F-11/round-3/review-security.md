VERDICT: PASS
COMMIT: 604e1b0a0f8fb3ac2cee49124f70370b1343e6de
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Reviewed the round-3 diff edc4763..604e1b0 (PhoneBar.tsx, AppShell.tsx, SetRulePanel.tsx, the setup views, shell.css). No blocking issues.
- The back link `label`, `href` and `note` all render as React text children and an `aria-label` string. There is no `dangerouslySetInnerHTML`. Every caller passes a constant: `'Setup'`, `/setup/roles` and `'RULES'` (SetupFrame.tsx:74), and `'Queue'` and `/my-work` in the fixture. No URL, query or API data reaches the link. The href is a `next/link` app path.
- The browser derives no authority from the back link. It is navigation only, and the destination route still runs its own gate. `staysOpen(page)` in RulesView and FinanceRulesView is the same `isEditable` check on the API re-read as before. It only decides where a message appears and never enables an action.
- "Nothing you entered was saved." is still added only when `rejected` is true. That value comes only from the 409, 403 and 404 outcomes, so the `saved` and `unconfirmed` outcomes never get it. The `staysOpen` change did not touch `rejected`. Request, CSRF and retry code are unchanged. No new packages and no secrets.

## Findings
- None blocking.

## Verified
- SEC-2-1 | reopen | Non-blocking, low. The code is correct, but I did not confirm in this round that the 5xx-then-withdrawn case is tested for "no NOT_SAVED". Keep it as a test gap.
- SEC-1-1 | reopen | Non-blocking, low. Unchanged: Save ignores an upload in progress.
- SEC-1-2 | reopen | Non-blocking, backend proposal, for T-SETUP. The mock does not check `evidence_id`.
- SEC-1-3 | reopen | Non-blocking, backend proposal, for T-SETUP. Readonly mock rows still carry `proof_case`.

## Notes
- The `note` field is not sanitised. The type allows any string, so a future caller who passes API-derived text still gets React escaping, but it would be shown in the bar. Pass only constants.
- A page that fails to unmount leaves its back link set until `setBack(null)` runs in the layout-effect cleanup. The bar is also re-keyed on the path, so this cannot carry a stale link to another user's session.
