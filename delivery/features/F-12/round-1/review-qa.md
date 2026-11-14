VERDICT: PASS
COMMIT: 831b17164ca8b1200e9ff84d2d486ea0d7dc7dc5
REVIEWER: reviewer-qa
AUTHORITY: integrated QA reviewer (F-12 round 1)

## Summary
- Exercised: the shared production build of this head (`next start -p 4211`, cwd the f-12 worktree, `.next/BUILD_ID` written 08:27, after the head commit at 08:23) against the f-12 contract mock on :4212 (pid cwd f-12/frontend). I drove it with headless Playwright from the worktree's node_modules (1440x900 and 390x844 touch, timezone Africa/Lagos) and also called the mock directly with curl. I reset the mock (`POST /__mock/reset` → 204) before each stateful journey and once at the end. Script: `round-1/qa-evidence/qa-journeys.mjs` (24 journeys, all PASS).
- Every success and failure journey in spec criteria 4-7 and 9-22 passed end to end: the list, search, filter, open-to-work with mark-read, empty, error, Show more, the bare (v4) backend, 401, settings save with the exact body, 409 stale, 422 invalid, locked, 500/network/403 save failures, the double press, and the phone at 390. axe (wcag2a/2aa/21a/21aa/22aa) found 0 violations in 19 states at 1440 and 390.
- Wrong user: the pm persona sees only N-0101/N-0102 and their own masked number. pm marking finance_lead's N-0002 gets 404, and N-0002 is unchanged. Another persona's CSRF token, or none, gets 403 csrf_failed on both writes. Wrong tenant does not apply: the spec has no tenant dimension.
- One non-blocking finding: at 390 the focused stale (409) and save-problem callouts are partly hidden under the pinned Save footer (QA-1-1).
- Not proved: the real backend (T-ALERTS is not built). Own-record filtering, the 404 on another person's id, server-side masking, CSRF, revision checks and real WhatsApp/email delivery are mock-simulated only, so this is contract-mock integration, not live API evidence. Provider failure does not apply: no provider call is made from this UI. Proposal fields (D-NOTIFY-MODEL r3, D-ALERT-PREFS-VIEW r1) are still `proposed`.

## Findings
- QA-1-1 | non-blocking | low | frontend | Phone 390, `/settings/alerts`: after a 409 (scenario `stale`) or a 500 on Save, the callout ("Someone changed these settings since you opened them. This is the latest version; make your changes again.") is focused but its last line sits under the fixed Save footer. Measured: callout y 696-779, footer y 758-844 (position fixed), scrollY 0 with 49px still scrollable. `elementFromPoint` at y=775 hits the footer, not the callout. Repro: cookie `psl_mock_alerts=stale`, 390x844 touch, tap "WhatsApp, A decision is waiting for me", tap Save settings. Expected: the whole focused callout shows above the footer. Actual: "again." is hidden until the person scrolls. Evidence: `round-1/qa-evidence/stale-callout-under-footer-390.png`. The 422 callout is shorter (696-758) and just clears the footer. This passes WCAG 2.4.11 because the callout is only partly hidden, so it is not blocking. Suggested fix: add `scroll-margin-bottom`/`scroll-padding-bottom` equal to the footer height (86px, matching `.alerts-footspace`) and scroll the callout into view on focus. `frontend/src/features/alerts/AlertSettingsPage.tsx:72`, `alerts.css:73`.

## Verified
- Not applicable (round 1).

## Notes
Journeys run (browser unless marked curl). Each one passed, with the observed result:
- L1 board 1440: four rows in order, the meta lines exactly as spec, "4 ALERTS", one NEW, hrefs /work/W-1001, W-1002, W-1099, W-1006, no horizontal scroll, title "Notifications · PSL Factory".
- L2 search "payroll" → 1 row, "1 ALERT", URL q=payroll. Filter Chidi → 2 rows and "Filter · 1". The hint reads "1 unread". Unread only → 1 row, URL agent=chidi&unread=1. Esc discards the draft and focus returns to "Filter · 2". "nothing like this" → "No alerts match"; Clear restores 4 rows and the bare URL. Query keys sent: only q, agent and unread; unread is always `true`, and q is never empty. localStorage and sessionStorage stay empty.
- L3 a direct load with `?q=lagoon&agent=chidi` gives 1 row with the search prefilled. `?agent=bogus&unread=yes` is ignored and sends a plain request with 4 rows.
- L4 one POST `/api/v1/notifications/N-0001/read` with `X-CSRFToken: mock-csrf-finance_lead` → /work/W-1001. Back shows no NEW and "0 unread". Read row 4 sends no POST → /work/W-1006. Restricted row 3 → /work/W-1099 "You can’t open this work item", with no payroll text.
- L5 a mark-read answered with 500, or aborted: navigation still happens, exactly 1 POST is sent, and NEW stays on return.
- L6 Cmd-click opens /work/W-1001 in a new tab with 0 POSTs, and the list stays put.
- L8 `empty`: "No alerts yet.", "Alert settings" and "0 ALERTS" (desktop). At 390 there is no count line and no horizontal scroll.
- L9 the list with X-Mock-Scenario 404 → "ERROR · COULDN’T LOAD / … / Reference not_found for support. / Try again". 403 → Reference forbidden. A 503 HTML body → Reference unexpected_response. Try again recovers all 4 rows. A network abort after success → "Last loaded 11:00. Reference network_error for support."
- L10 a 401 on the list → Sign in href `/accounts/login/?next=%2Fnotifications%3Fq%3Dlagoon`.
- L11 `many`: 20 rows. A failed Show more keeps the 20 and shows "We couldn’t load more. Nothing was changed."; Try again → 25 rows, and Show more and the callout go away.
- L12 `bare`: a URL with q/agent is replaced by /notifications and re-read. There is no search, Filter, count or "unread". Meta lines read "Chidi · 10:42 / Tola · 08:30 / Zainab · 08:10 / Chidi · yesterday". Opening row 1 → /work/W-1001, and NEW is still there on return. `/settings/alerts` → error card with Reference not_found, no switches and no Save.
- L13 phone list: "← Home" to /, no eyebrow and no count, "Alert settings" below the list, Filter button 44x44. The Filter sheet is a bottom sheet (y 374 to 844); Zainab → 1 row. Tapping a row → /work/W-1001.
- S1 settings 1440: a double-click on Save sends one PUT with CSRF and the body deep-equal to `{channel:"both",frequency:"immediate",expected_revision:3,events:[5 in order, work_stuck email false],digest_at:"09:00",quiet_hours:"none"}`, with no label, timing or number. Enter toggles a switch. The saved notice clears on the next edit. A reload shows the saved values. Later saves send expected_revision 4, then 5, without a reload, so state is replaced from the PUT body.
- S2 `stale`: the focused warning callout shows. The edited WhatsApp switch and the digest revert to the server's values, and the other person's "Email, Work I started is stuck" shows off. The next save sends revision 4 and is saved.
- S3 a 409 whose re-read fails → settings error card (Reference network_error) with no Save.
- S4 `invalid`: the PUT sends `channel:"sms"` unchanged. The focused callout reads "We couldn’t save your settings. Check these fields: channel." and the edit is kept.
- S5 `locked`: both "Payroll problems" switches are aria-disabled and stay off on click, Space and Enter. The PUT sends `{key:"payroll_problems",whatsapp:false,email:false}` and is saved.
- S6 a PUT answered with 500, aborted, or rewritten to another persona's token (real mock 403 csrf_failed): each shows "We couldn’t save your settings. Nothing was changed." with the message and reference, sends 1 PUT and no retry within 1.2s, keeps the edit, and leaves Save enabled. A manual retry then saves, and the reload shows the value.
- S7 a 401 on the settings read and on the save → `next=%2Fsettings%2Falerts`.
- S8 a 200 without events → Reference missing_events with no Save. Try again recovers once the route is removed.
- S9 `phone` at 390: "← Notifications", 4 cards, "Quiet hours 20:00 to 07:00 and weekends", no digest select and no number card. The pinned Save is at y 772-826. The switch is 44x26 visually, with a 44px tall hit area (`alerts.css:84`). The phone PUT body keys are only channel, frequency, expected_revision and events.
- S10 `board` at 390 shows the 5th card "Everything else". The stale and invalid states at 390 pass axe (see QA-1-1).
- S11 signed out on /work/W-1001 → Sign in href contains `next=%2Fwork%2FW-1001`.
- curl :4212: a repeat mark-read on N-0001 gives 200 twice (idempotent). An empty q or unknown agent → 404 invalid_query. digest_at "23:00" → 422 "Check these fields: digest_at.". expected_revision 99 → 409 stale_revision. A PUT without CSRF → 403.
- The mock's alert state was reset at the end. I started and stopped no servers.
