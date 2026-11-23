DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Frontend-only connection of the built SCR-15 default (bell drawer F-15, /notifications F-12) and settings (/settings/alerts) to live API 1.22.0. Task FE-ALERTS.
- SCR-15 is in the approved design scope (design/review.json). The live API exists, so no backend work is needed.
- A-42 to A-45 are open. They do not block the work. Build on the best reading of the contract and flag each gap.
- The live API is thinner than the board, so the screen visibly changes. The client must see the result.
- The account tab, the account-menu items and any change to "My roles", "Delegate while away" or the phone entry are out. They wait on the open part of D-ALERTS-ENTRY.

## Scope
Outcome: a signed-in person reads alerts grouped into "Needs you" and "For information", marks them read, opens the related work, and sets how they are alerted. Alert settings are email and WhatsApp switches with delivery receipts.

In:
- `GET /notifications` feeds the drawer and /notifications.
  - Use `items[{id, title, subject, detail, group, read, django_url}]` and `as_of`.
  - `group: action` is "Needs you". `group: update` is "For information".
  - Show "as of" coverage from `as_of`.
- `POST /notifications/{id}/read` with body `{}` and CSRF.
  - Apply the read state locally. The response has no unread count, so derive the badge and unread count from the loaded list.
- `GET /me/alert-preferences` and `POST /me/alert-preferences`.
  - Settings: `email_requested` and `whatsapp_requested` switches, with `email_ready` and `whatsapp_ready` shown.
  - Save with `{revision, email_requested, whatsapp_requested}` and handle a stale revision.
  - Show `recent_deliveries` receipts with states queued, uncertain, delivered and held. Show "uncertain" honestly and do not call it delivered.
- Loading, empty, error and signed-out states per the existing board states.

Out:
- The account tab and password change (`/me/account`, `/me/account/password`).
- Account-menu items.
- Backend changes.
- Any per-event switch, digest time or quiet hours control. The live API has none. Hide these or show them as unavailable, and do not fake them or keep v7 mock behaviour.

Handling the gaps (flag each in the build notes):
- A-42: the live items carry no time, agent or work id. Omit time and avatar, or use a neutral avatar. Open the work only if the work id can be parsed from `django_url`. Otherwise show no open link, and do not link to the retired Django page.
- A-43: no paging and no server counts. Do not show search, agent filter or unread filter that the server cannot answer.
  - Client-side filtering of the loaded list is allowed, with the coverage stated.
  - Unread counts derive from the loaded list.
- A-44: settings reduce to two switches plus receipts.
- A-45: send `{}` and do not expect an unread count.

Keep it to about 8 boards. Reuse `frontend/src/features/alerts/*` and branch from origin/main.

## Risk
Medium. The change spans a cross-layer contract (the v7 mock to live reshape: PUT becomes POST, and the settings and list shapes change). It also changes what the client sees where the board promised more than the API serves. It touches the WhatsApp and email channel switches and receipt states (external-messaging), but nothing is sent from this screen. It handles no money, identity or migration. Write requests need CSRF and revision handling. Cite `frontend/src/features/alerts/model.ts` and `types.ts` as the main adaptation points.
