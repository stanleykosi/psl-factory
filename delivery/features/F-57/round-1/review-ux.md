VERDICT: PASS
COMMIT: 84f3a3e9959b9c9cebe0746a9324c3795d5290da
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Frame walked at 1280 and 390 for finance_lead, pmo_lead, pm, ceo, hr and none, plus signed-out (401), forbidden (403), error (404) and csrf_failed scenarios, against a mock started from the head's code on port 4971 (see UX-1-1 for why).
- Top bar and phone bar show name plus role words ("Ada Okafor · Finance Lead", "Folake Bello · CEO"); persona `none` shows the name alone; menu and Start work match each persona's subset (pmo_lead without Setup, pm and hr smaller menus, none has no menu).
- Signed-out reads "You're signed out. Sign-in opens in a later release. Ask your administrator if you need access now." with no link, no menu, no Start work, no bell; it reads well and fits at 390.
- Forbidden and load-error cards say something useful and offer Try again; phone width has no overflow or dead end.

## Findings
- UX-1-1 | non-blocking | low | integration | The design engineer's running app on port 3000 does not serve this head: its mock (pid 89457 on 3001, started Sun 22 Nov 00:12) still answers the old `/me` shape (`roles[]`, string destinations) and has no `/role-dashboard`, so every persona shows only "No sections are open to your role yet." with no menu, name only, until the mock is restarted. Restart `node mock/server.mjs` on 3001 from this head before the design engineer reviews.
- UX-1-2 | non-blocking | low | frontend | When `/me` answers `csrf_failed` twice the card shows "Reference csrf_failed for support." (same for `not_found` on a 404); the csrf wording "press the action again" is not used here. Acceptable (a frame load is not an action), a plainer line could follow later.

## Verified
None (round 1).
