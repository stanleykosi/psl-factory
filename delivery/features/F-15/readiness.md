DECISION: READY
RISK: medium
SURFACES: ui, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- FE-ALERTS-MENU is ready for the bell and drawer only. D-ALERTS-ENTRY is decided (15 Nov, design engineer) and is listed in the v7 manifest decisions. Dependencies FE-ALERTS (F-12) and FE-M2A (F-05) are merged.
- One outcome: a signed-in person sees an alert bell in the top bar and opens a drawer of their alerts, grouped "Needs you" and "For your information", with an Open action on each row.
- Sign-out and the account menu links are out of scope. D-SIGNIN is still open and is the only part of the v7 task that it gates.
- "Needs you" depends on a `needs_you` field that v7 does not have. This is a contract proposal. Without it, every alert shows under "For your information", so the build is not blocked.
- The bell sits in the shared shell that every page uses, so a regression would show everywhere. That is why risk is medium and the client must see the result.

## Scope
Task: FE-ALERTS-MENU, split. The bell and drawer are in. The account menu, sign-out and account links are deferred until D-SIGNIN is decided. Record that deferral in the spec and the PR.

Endpoints: E-NOTIFICATIONS (list, `unread_count`, `as_of`) and E-NOTIFICATION-READ. No new endpoints. Reuse the alerts data layer and the SCR-15 row styling in `frontend/src/features/alerts/` (`model.ts`, `types.ts`, `alerts.css`, `useIsPhone.ts`). Do not duplicate it.

Design source: `design/concepts/alerts-bell-concepts.html`, concepts 1 and 3 per its "My recommendation" section. For alert rows, use the SCR-15 boards (`design/canvas/project/SCR-15-*.dc.html`).

In:
- Bell in the desktop top bar (`frontend/src/shell/AppShell.tsx`, `shell-topbar`/`TopNav`), beside the person's name. It shows an unread count.
- A "N need you" chip beside the bell on wide screens (concept 3).
- A full-height right-side drawer on desktop (concept 1).
- On phone, a full-height sheet. The two groups are tabs. The bell must also be reachable from `PhoneBar`.
- Groups "Needs you" and "For your information". Each row has an Open action that goes to the related work (`work_id`/`reference`) and marks the alert read through E-NOTIFICATION-READ.
- Loading, empty, error, signed-out and forbidden states, using the existing alerts and shell state patterns. Keyboard and focus handling: Escape closes the drawer, focus is trapped while it is open and returns to the bell on close.
- A link from the drawer to the full notification centre (`/notifications`).
- Keep the bell hidden or inert when `/me` is not ready, as the shell already does for the nav.

Contract proposal (not in v7, label it as a PROPOSAL in the spec): an optional boolean `needs_you` on each notification item. The frontend must work when it is absent, and every alert then shows under "For your information". The "N need you" chip is hidden when the count is 0 or unknown. Unknown is not zero. The backend developer owns adding it. Do not edit `schema.d.ts` by hand to invent the field. Read it defensively and add it to the generated contract only through the normal contract change route.

Out:
- Sign-out, the account menu and the account links (D-SIGNIN open, PSL).
- Changes to the alert settings and preferences screens, WhatsApp and email message content, and the assistant.
- Any new backend work.

## Risk
Medium. The change is in the shared shell (`AppShell.tsx`, `TopNav` and `PhoneBar`), which wraps every page. It adds a cross-layer contract proposal (`needs_you`) and a new responsive interaction (drawer and sheet, with focus management). It reads and marks alerts as read through existing endpoints. It moves no money, identity or data migrations, and the optional field makes it safe to ship before the backend. SURFACES are ui and contract-change.

Note for the reviewers: `design/review.json` records client approval of the canvas (SCR-15 among its screens). The bell concepts page is outside that approval and rests on the design engineer's decision. Product acceptance is therefore required so the client sees the bell and drawer.
