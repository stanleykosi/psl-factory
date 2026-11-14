VERDICT: PASS
COMMIT: 3c93fe030ff5ac81da343dc7a0917820c8803d7b
REVIEWER: reviewer-qa
AUTHORITY: integrated QA reviewer

## Summary
- Exercised on the shared production build of this head: app http://localhost:3401, which proxies `/api/v1` to the contract mock on http://127.0.0.1:3402. The mock was reset (`POST /__mock/reset` → 204) before every state-changing journey and again at the end. The full browser run made 73 checks. J1, J6 and J7 were rerun (33 checks) after I fixed my script's curly-apostrophe matching. Separate browser retests covered the fixes, and 30 direct API calls were made. Everything passed apart from the three non-blocking findings below.
- Cross-feature journey works. My work → W-1001 → "Open the decision" leads to "This decision isn't open here", as the spec intends, because T-2001 has no `decision`. Work item W-1201 → "Open the decision" → claim → Approve → done → "Open the work item" shows revision 3, APPROVED earned and no "Open the decision" → "Back to my work". Return, reject, stale (409, with "Review version 3" → approve v3 at revision 5), not-yours, own work, already-decided, not-your-turn, a decide that is retried after a double failure ("couldn't confirm"), and 401/403/404/422/500 on the item, claim and decide all behave as specified, at 1440 and 390.
- All round-2 fixes were retested in the browser: SEC-1-1/TECH-1-1, SEC-1-2/TECH-1-2, TECH-1-3, TECH-1-4 and UI-1-1 to UI-1-5 are verified.
- Unproved, because this is a UI and contract-mock run only: real Django session auth and its 401 redirect, real CSRF token issue and rotation, server-side grants and per-record access (wrong user or tenant is simulated by mock 403/404 and the fixtures' `you_can_act`), approval order and the claimed-role rule (D-APPROVAL-ORDER, T-DECIDE), real revision bumps on claim, idempotency of the real decide, and WhatsApp/email alerts behind `asked[]`. No PostgreSQL or backend service was in the path.

## Findings
- QA-2-1 | non-blocking | medium | frontend | A session that has already expired when someone opens a decision link loses the task. When `/me` answers 401, the shell (F-01) renders `SignedOutState` with `usePathname()` only (`frontend/src/shell/AppShell.tsx:27,56`), so the sign-in link is `/accounts/login/?next=%2Fwork%2FW-1201%2Fdecide`, without `?task=T-1201`. After signing in, the person lands on "This decision isn't open here". This is the likely path from an alert link. Repro: cookie `psl_mock_scenario=401`, open `/work/W-1201/decide?task=T-1201`. F-04's own 401 handling is correct: a 401 on the item alone, on the claim and on the decide each gives `next=%2Fwork%2FW-1201%2Fdecide%3Ftask%3DT-1201`. Expected: the shell keeps the query string. The fix belongs to the shell lane (read-only for F-04).
- QA-2-2 | non-blocking | low | frontend | After a keyboard decision (focus on "Approve v2", Enter), the done view replaces the panel and focus falls to `<body>`. No focus move or live announcement tells a screen-reader user "Invoice v2 is approved". The done view has no `role="status"` or `role="alert"` and no heading focus (`frontend/src/features/decide/DecideStates.tsx` DoneView). Expected: move focus to the done heading, or announce it. The spec does not require this, so it is not blocking.
- QA-2-3 | non-blocking | low | integration | In mock data, no My work row leads to an actionable decision. Every My work row links to W-1001 to W-11xx, and the only one with a decide task, W-1001/T-2001, has no `decision`, so it lands on "isn't open here" as specified. As a result, the full My work → decision → result journey cannot be demonstrated end to end from My work. It was exercised from the work item page instead. A W-12xx row in `E-WORK-LIST.rows.json` (F-02's file) would close the demo gap.

## Verified
- SEC-1-1 | verified | Decide aborted (`route.abort('failed')`), then every W-1201 GET answers 503. "We couldn't confirm whether your decision was recorded…" appears, and Approve, Return and Reject are all `disabled` at 1440 and 390. Try again while the item is still down stays unconfirmed. Once reads succeed, Try again brings the item back, with "We couldn't confirm your decision. We've reloaded this item…" and the controls enabled. Exactly 2 POSTs were sent (claim, decide), with no resend. axe is clean at both widths and there is no sideways scroll.
- TECH-1-1 | verified | Same run as SEC-1-1. In addition: when the decide reaches the mock (the effect is recorded) and the browser sees an aborted response, the reconcile shows "This decision has already been made." with no controls and one decide POST.
- SEC-1-2 | verified | Decide stubbed to 200 with `verdict:"constructor"`. The page shows "DECISION RECORDED · 03:00" and "Decision recorded on Invoice v2", and the header area has no "approved".
- TECH-1-2 | verified | Same as SEC-1-2.
- TECH-1-3 | verified | Claim stubbed to return revision 3, decide aborted once, and the reloaded item set to revision 3. No stale view appears. The POSTs were: claim `{"expected_revision":2}`, decide `{"expected_revision":3,…}`, re-claim `{"expected_revision":3}`, then decide `{"expected_revision":3,"verdict":"approve"}`.
- TECH-1-4 | verified | curl to the mock: revoke with no note → 422 "Check these fields: note.". Revoke with note "x" → 501 `not_mocked`.
- UI-1-1 | verified | Approve has class `psl-btn psl-btn--lg psl-btn--block decide-approve` and background rgb(36, 89, 214) at 1440 and 390, read after the 0.12s transition.
- UI-1-2 | verified | The approve done banner `.decide-banner--success` has background rgb(221, 239, 227) and a 2px rgb(34, 118, 74) border at 1440 and 390.
- UI-1-3 | verified | W-1203 reads "1 step" and never "1 steps".
- UI-1-4 | verified | At 390, Approve is 54px, and Return and Reject are 50px, inside a `psl-actionbar` that is fully within the viewport.
- UI-1-5 | verified | W-1206 chain reads "CEO · Ada Okafor (you)".

## Evidence
Commands: the app is the shared `next start` build of 3c93fe0 on 3401, and the mock on 3402 (neither was started or stopped by QA). The browser runs used `playwright` and `@axe-core/playwright` from `/Users/Hunchoo/psl-factory-worktrees/f-04/frontend/node_modules`, with a headless Chromium and `reducedMotion: 'reduce'`, WCAG 2.0/2.1/2.2 A and AA tags.

API, direct to the mock (`-H 'X-CSRFToken: mock-csrf-finance_lead'`):
- Claim T-1201:
  - `{}` → 422 "Check these fields: expected_revision."
  - `{"expected_revision":2,"x":1}` → 422 naming `x`.
  - rev 1 → 409 `stale_revision`.
  - rev 2 → 200 `{"task_id":"T-1201","revision":2,"claimed_by":"Ada Okafor"}`. Repeated → 200 (idempotent).
  - No CSRF → 403 `csrf_failed`. PM token with the finance cookie → 403 `csrf_failed`.
  - `{bad` → 422 naming `body`.
- Claim other tasks: T-1203 (not your role) → 403. T-1204 (own) → 403. T-9999 → 404.
- Decide T-1201:
  - `maybe` → 422 naming `verdict`.
  - Return with no note → 422 naming `note`. Reject with a whitespace note → 422 naming `note`. A 2001-character note → 422.
  - Revoke with a note → 501.
  - `X-Mock-Scenario: 401` → 401. Cookie scenario 409 → 409.
  - Approve rev 2 through the app proxy (http://localhost:3401/api/v1) → 200 with `work_state:"ready"`. GET W-1201 then returns rev 3, `ready`, task `already_decided`, and next_step "Chidi issues invoice v2…".
  - Replay at rev 2 → 409. Rev 3 → 403.
- Stale: T-1207 decide at rev 4 → 409, then GET W-1207 returns rev 5 with Invoice v3 and `billing@lagoonhealth.example`. Claim and decide at rev 5 → 200.
- Other GETs: `ANY-OTHER` returns the base W-1001. W-1099 → 404.
- Reset → 204. W-1201 is back at rev 2 and W-1207 at rev 4.

Browser journeys (session `F-04-qa`). The A/B/C/D checks are recorded per journey:
- J1, My work → W-1001 → "Open the decision" (`/work/W-1001/decide?task=T-2001`): "isn't open here", no controls, no POST, and "Open the work item" returns.
- J2, W-1201 work item → "Open the decision":
  - One claim with `{"expected_revision":2}` and `X-CSRFToken: mock-csrf-finance_lead`.
  - All the AC2 values are shown, including "Step 1 of 1" and the title "Decision · PSL Factory".
  - A double-click on Approve sends exactly one decide, `{"expected_revision":2,"verdict":"approve"}`.
  - Done view: "YOU APPROVED · HH:mm", "Decided by Ada Okafor", APPROVED earned, the next step and the Paid line, with no controls.
  - The work item then shows revision 3 and no "Open the decision". Browser back shows "already decided" with no new POST. "Back to my work" leads to /my-work.
  - axe is clean on the default and done views at 1440.
- J3, return and reject:
  - A blank note is blocked with "Add a note to return or reject.", `aria-invalid="true"`, focus on the note and no POST.
  - `maxlength=2000` and the "n / 2000" counter are present.
  - "Wrong PO" sends the exact body. The done view reads "YOU RETURNED" or "YOU REJECTED", with no Paid line.
- J4, stale W-1207 at 1440 and 390:
  - 409 after one decide.
  - All the AC9 copy is shown, with Amount "unchanged" and Send to "changed".
  - Review version 3 → claim `{"expected_revision":5}` → Approve v3 → decide at rev 5 → "Invoice v3 is approved".
  - Claim 409 (route stub) gives the stale view with no decide.
  - axe is clean, with no sideways scroll at 390.
- J5, W-1203, W-1204, W-1205 and W-1206 at 1440 and 390: every AC12 string is present, there are zero textareas and zero approve/return/reject buttons, and no POST is sent. axe is clean on W-1203 and W-1204 at both widths.
- J6, uncertain effect:
  - The double failure is as described under Verified.
  - Decide 500 with a good reload gives the warning, exactly one reload GET and no resend.
- J7, errors:
  - 401 on the item alone, on the claim and on the decide → signed-out, with `next` keeping `?task=T-1201`. A 401 on `/me` drops it (QA-2-1).
  - Item 403, and W-1099 (404) → no-access view, with no id, title or amount.
  - Item 500 → "ERROR · COULDN'T LOAD" card, and Try again re-fetches and recovers.
  - A missing `task`, or `task=T-NOPE` → "isn't open here".
  - Decide 422 → message shown, note kept, one POST.
  - Decide 403 and claim 403 → generic "NOT YOUR DECISION" with no controls.
  - Claim 422 → message shown, with all three buttons disabled.
  - Claim network failure → disabled buttons, and Try again re-claims.
  - Decide with the CSRF header stripped → mock 403. The page shows cannot-act, not approved, and the item stays at rev 2.
- J8:
  - The `pm` persona sees enabled controls on W-1201, and `finance_lead` sees none on W-1203, so eligibility does not come from `/me`.
  - Persona `none` gets the shell's no-sections state and no claim.
  - W-1202 shows "Unknown", with no "0.00" or "₦0".
  - W-1208 has no To or "Changed since" row, shows "Step 3 of 3" and two Approved steps.
- J9, keyboard and phone:
  - At 1440, Tab order is Note → Approve v2 → Return → Reject, each with a visible outline. Enter on Approve decides (focus is then lost; see QA-2-2).
  - At 390:
    - The action bar is in the viewport, with button heights 54, 50 and 50.
    - `scrollWidth` is 390.
    - The mini line reads "Station 4 of 7 · Finance review · only a Finance Lead can decide".
    - The focused note is not covered by the action bar.
    - Approve leads to the done view, with no sideways scroll.
    - axe is clean on the default and done views.

## Notes
- The AC2 "SAMPLE DATA" label is not visible on this build. `frontend/src/shell/sample.ts` gates it on `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1` under a recorded design decision of 14 Nov 2026, and the fixtures still carry `sample: true`. This was not raised as a finding; spec.md predates the decision.
- Mock ordering: a replayed decide at the old revision after the approve answers 409, not 403, although the task is now `you_can_act: false`. This matches AC16 but not the numbered check order (7 before 8) in spec.md. It is mock-only and has no UI impact.
- UX-2-1 and UX-2-2 (the note stays editable, and the heading still reads "Approve invoice v2" while unconfirmed) were observed in this run too. They are not re-raised.
