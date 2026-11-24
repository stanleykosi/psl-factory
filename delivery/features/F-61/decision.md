RECOMMENDATION: ESCALATE
COMMIT: dab5f01825066cb85627bf0f427f27ef29e7d3ef
APPROVER: approver

## Summary
- Frontend-only move of the alerts bell drawer, /notifications and /settings/alerts from the v7 mock to the live API. 42 files changed, with the v7 alert operations removed.
- Gate, technical, security, UX, UI, QA and PMO all pass on this head (re-confirmed after the D-193 sync). Product acceptance was carried over under D-188.
- Readiness rates it medium, with surfaces contract-change and external-messaging. Both are on the merge policy's always-human list. The policy allows auto-merge for low risk only, and a change of more than 15 files also goes to a human.
- Open non-blocking gaps: alert creation is not proven live (seeded by ORM); a stale preferences save returns 422, not 409, so the page shows no Reload (TECH-1-1, QA-1-1, LA-4); the alerts-bell e2e failure (QA-1-2) also fails on main.

## Why
The code looks sound and the reviews pass, but the diff changes an API contract shape (PUT to POST, new list and settings shapes). It also changes the WhatsApp and email switches and receipt states. The policy puts both surfaces with a human whatever the review result. The stale-save path also leaves a person stuck until they reload by hand. Someone should accept that, or have it fixed, on purpose.

## Acceptance criteria
1. Bell drawer groups alerts by `group` with as-of: met per QA and UX reviews. I did not re-run it myself.
2. /notifications has no search, agent filter or unread filter: met per UI and QA reviews.
3. Badge counts unread items in the loaded list: met per the unit tests the technical review cites.
4. Mark-read sends `{}` with CSRF: met per the e2e and unit evidence.
5. Failed mark-read keeps the row unread: met per the component tests.
6. `workHrefFromUrl` link rules: met per the unit tests.
7. Agent and time wording removed: met per QA.
8. Settings show exactly two switches and receipts: met per UI fidelity.
9. Save body is `{revision, email_requested, whatsapp_requested}`: met per Playwright.
10. A 409 shows the stale notice: met in the component test. The live API returns 422 instead, so this path does not work live (LA-4).
11. Receipt states, with `uncertain` not worded as delivered: met.
12. A 401 shows the signed-out state: met.
13. Per-account lists: met per live-lead and live-none.
14. A response with no `items` shows the error state: met.
15. v7 operations removed: met per the gate grep.
16. Tests rewritten, not deleted: met.

## For the human
Decide whether to merge PR #112 with these gaps accepted:
- A stale preferences save returns 422, and the page has no Reload for it (TECH-1-1, QA-1-1, LA-4). Merge as is, or fix it first? The fix is to treat code `action_unavailable` like `stale`, or to have the backend return 409.
- Alert creation was not proven live (ORM-seeded), and the e2e failure QA-1-2 also fails on main.

Files to look at:
- /Users/Hunchoo/psl-factory-main/delivery/features/F-61/round-1/review-qa.md
- /Users/Hunchoo/psl-factory-main/delivery/features/F-61/round-1/review-technical.md
- frontend/src/features/alerts/AlertSettingsPage.tsx
- frontend/src/api/alerts.ts
