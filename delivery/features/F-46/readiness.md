DECISION: NOT-READY
RISK: low
SURFACES: none
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-46 duplicates work that is already merged. F-12 delivered FE-ALERTS (the v7 "F-12A" task): `/notifications` and `/settings/alerts`, with fidelity 97.8 / 92.9 / 96.4 / 95.8 on SCR-15 desktop, mobile, desktop-settings and mobile-settings. It is DONE and merged as PR #18 (merge 537607ea). The routes are in `frontend/src/app/notifications/page.tsx` and `frontend/src/app/settings/alerts/page.tsx`.
- FE-ALERTS looked as if it had no feature because F-12's record still names the retired task `FE-M4` (`delivery/features/F-12/feature.json` `git.task_id`, already raised there as an open low finding). That record gap, not missing work, is why the night-log sweep created F-46.
- The other 6 SCR-15 boards are not FE-ALERTS frontend work. SCR-15-desktop-account and SCR-15-mobile-account are FE-ALERTS-MENU part 2 (account menu and sign-out, gated on D-SIGNIN). The 4 WhatsApp and email boards are T-ALERTS message content (backend, held by D-ALERT-PROVIDERS). F-15 built the bell and drawer.
- F-12's one real follow-up, QA-1-1 (the phone save callout sitting under the footer, D-27), was fixed in `delivery/followups-01/build-note.md` item 6. No first outcome of 8 boards or fewer remains to scope.
- Recommendation: close F-46 as a duplicate. Spending a spec, a build and reviews on it would rebuild merged screens.

## Scope
**Outcome:** none. Do not write a spec or create a worktree for F-46.

**What the coordinator should do (record changes only, no code):**
1. Mark F-46 closed as a duplicate of F-12, or delete `delivery/features/F-46/` (the night-log undo).
2. Correct F-12's `git.task_id` from `FE-M4` to `FE-ALERTS` and fill in its `operation_ids` (E-NOTIFICATIONS, E-NOTIFICATION-READ, E-ALERT-PREFS-READ, E-ALERT-PREFS). Both are open low findings in `delivery/features/F-12/feature.json`. Then mark FE-ALERTS done in the backlog so later sweeps skip it.
3. Close QA-1-1 on F-12 with a pointer to followups-01 item 6.
4. Still with the design engineer, not with readiness: F-12's PMO-1-1. D-24 must be confirmed for the provisionally approved fidelity exceptions E-1 to E-6, and the proposal fields D-NOTIFY-MODEL r3 and D-ALERT-PREFS-VIEW r1 must be accepted (F-12 `decision.md` "For the human").

**Where each of the 10 SCR-15 boards belongs:**
| Board | Owner | State |
|---|---|---|
| SCR-15-desktop, SCR-15-mobile | F-12 (FE-ALERTS) | merged |
| SCR-15-desktop-settings, SCR-15-mobile-settings | F-12 (FE-ALERTS) | merged; saves preferences only, sends nothing |
| SCR-15-desktop-account, SCR-15-mobile-account | FE-ALERTS-MENU part 2 | gated on D-SIGNIN (sign-out); the bell and drawer part is F-15, merged |
| SCR-15-desktop-whatsapp, SCR-15-mobile-whatsapp, SCR-15-desktop-email, SCR-15-mobile-email | T-ALERTS / JOB-ALERTS (backend message templates) | held by D-ALERT-PROVIDERS; F-12 already owns their in-app link targets |

**Out of scope here:** any channel setting that sends or tests a message, such as a "send test WhatsApp" or verifying the number. None is drawn on the settings boards. Any such feature waits on D-ALERT-PROVIDERS and is T-ALERTS work, not FE-ALERTS.

## Risk
Low, and SURFACES is none, because this readiness proposes no code change. The settings page that is already merged (`frontend/src/features/alerts/AlertSettingsPage.tsx`) writes only E-ALERT-PREFS and triggers no WhatsApp or email send, so the open D-ALERT-PROVIDERS does not affect merged behaviour. Gates for FE-ALERTS are clear: `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:3004-3035), SCR-15 is in the client approval (design/review.json:28), and the endpoints exist in frontend/src/api/schema.d.ts:516, 537 and 757. The verdict is NOT-READY only because no unbuilt work remains.

## Questions
None.
