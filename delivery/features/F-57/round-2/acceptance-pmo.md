VERDICT: PASS
COMMIT: 5262fbd45ea1743f1bbde3e0c5fc07eaa992e732
REVIEWER: pmo-acceptance
AUTHORITY: PMO delivery acceptance for F-57 (FE-CONNECT-1 part b). Not client or product acceptance, merge or release.

## Summary
- Delivery accepted on head 5262fbd4: the gate passed (round 2, attempt 1), and technical, security, UX, UI and integrated QA all PASS on this same commit. The task is FE-CONNECT-1 part b only; no operation IDs were in scope.
- Both blocking findings from round 1 (UI-1-1 long role words overflow the top bar, TECH-1-1 session refresh loop) are VERIFIED by named reviewers with retest evidence. No blocking finding is open. No accepted risk is in play.
- Product acceptance is required (readiness) and is still pending. It belongs to the design engineer. What is being asked is set out below.
- The 8 non-blocking follow-ups are listed with owners. Several parts of the live scope are unproved (see the end of Findings).
- This acceptance covers the frame slice only. Wave 1 (sign-in) and later waves, and any screen's own live data, are not claimed.

## Acceptance check
- Criteria: QA ran the mock and live checks on this head (criteria 12 to 16: mock personas, csrf notice, six download routes, live signed-out, sign-in, role words, csrf_failed). Criteria 1 to 11 and 17 are covered by the gate (lint, typecheck, full test run, design check) and the technical review. Build round 2 reports lint and typecheck clean, 156 files and 3706 tests passing, frame e2e 27 passing.
- Scope: changed paths are frontend only (api client and errors, live schema, shell, mock, tests, e2e, styles, a few frame callers). No backend or contract file changed and protected paths are untouched. Nothing outside FE-CONNECT-1 part b landed.
- Decisions: D-172 and D-174 cover the role-words fallback, the sign-in gap, the unfiltered menu, the signed-out line and the csrf wording. The built behaviour matches them.
- Docs and handoff: readiness, spec, build notes for both rounds, checks and all reviews exist. The spec's live-run evidence is in review-qa.md.
- Parent package: nothing in this round claims more than the frame. The parent task FE-CONNECT-1 is complete only for part a (F-56) plus this part b. Wave 1 and later waves stay open.

## What product acceptance is asked to accept
For the design engineer, in plain terms. The frame (top bar, phone menu, signed-out and error states) now loads from the live API. On the mock the app should look and behave as it did, except for these visible changes against the boards:
1. Role words. The top bar shows "Name · role words". The words are the person's distinct role names from the live role list, joined with commas, where the boards draw one role. If that list cannot be read, or the person has none, the bar shows the name alone. Mock persona "none" now shows only "Sample Person" instead of "Sample Person · Staff". Role words may appear a moment after the name on first load. When the words are too long for the bar they are cut with an ellipsis, and the full text is in the bar's hover title. In the phone menu the full roles wrap under the name. (D-174.)
2. Menu. Live, everyone gets the same five links: My work, Projects, Overview, Assistant, Setup. Clients stays under Projects. Setup therefore shows for everyone live, although the board says Leads only. The mock keeps hiding Setup for personas that lack it. "No sections are open" can occur only in the mock. (D-174.)
3. Signed out. The callout reads "You're signed out." plus "Sign-in opens in a later release. Ask your administrator if you need access now." with no link. Live, a signed-out person has no sign-in page until wave 1. (D-172, D-174.)
4. Session expired on a write. A refused write shows "Your session was refreshed. Press the action again. Nothing was changed." in that screen's own error spot, and the write is never repeated automatically. (D-174.)
5. Error cards for too-many-requests (429), read limit (503), bad request, too large and unsupported use the existing "Reference <code> for support" card with Try again, with no retry timing shown.

Not shown to PSL before: all of the above. Product acceptance should be recorded against this head by the design engineer, and the dev server must be restarted first (UX-1-1) or the app on port 3000 will show "No sections are open" for every persona.

## Findings
- PMO-2-1 | non-blocking | low | pmo | Product acceptance is pending. Delivery is accepted here; it does not stand in for the design engineer's acceptance, the merge or the release decision.
- Carried non-blocking follow-ups (all OPEN in feature.json; none blocks delivery):
  - TECH-1-2 | owner frontend | The mock `startable_lines` in `frontend/mock/fixtures/me.*.json` keep the v7 keys instead of live keys such as `pmo-weekly-report/v1`. The frame only tests that the list is not empty. Next: the per-line adapter work (wave 3) or the next wave that connects Start work, whichever comes first.
  - TECH-1-3 | owner frontend | Role words are read once per page load (`src/shell/useRoleWords.ts`). Try again after an error and a sign-in on the same page will not re-read them. Next: wave 1 (SCR-17 sign-in) must re-trigger the read.
  - UX-1-1 | owner integration | The design engineer's mock on port 3001 (started 22 Nov) still serves the old `/me` shape. Next: restart `node mock/server.mjs` from this head before the design engineer reviews, as part of putting acceptance to them.
  - UX-1-2 | owner frontend | When `/me` answers csrf_failed twice (or 404), the card says "Reference csrf_failed for support." Wording only. Next: a later wording pass, no deadline.
  - UX-2-1 | owner frontend | The cut-off role words are visible only in a mouse-hover title. Keyboard and touch users with several long role names cannot read the rest in the bar (the phone menu shows them in full). Next: a later release could show the list in a menu or profile page; design engineer to decide if it matters.
  - QA-2-1 | owner backend | Live superuser account: `POST /api/v1/session` signs in but gives 422 `action_unavailable` ("'invite_minutes' is a required property") and `GET /role-dashboard` gives the same 422. The frame degrades to the name alone, so the "Admin" word is not shown. Next: put this to the backend as question A-56 (a backend fix or a contract answer); the frontend needs no change.
  - QA-2-2 | owner frontend | Informational. At 800px the role line is not clipped and nothing scrolls sideways. No change asked; may be closed.
- Unproved scope, so nobody reads this PASS as proving it:
  - A signed-in download returning a file. Live downloads proved only the 302 to the login page (A-55) and the exact paths.
  - The live path where `/me` answers 401, `/session` then says `signed_in:true`, and the frame reloads. Unit-tested only.
  - An Administrator account live, because of QA-2-1.
  - Live alert-settings Save succeeding: the endpoint answers 405 live (not connected), so the csrf retry path was proved only up to "second press uses the new token".
  - Sign-in, sign-out, recovery and invitation pages (wave 1), every screen's own live data (wave 2 onward), the per-line workspace adapter and evidence picker (wave 3).
  - Per-role hiding of menu entries (backend question A-2 open), and any real WhatsApp or email provider. Not in scope.
  - The mock results are mock evidence; the live results were run against a local Django on a local Postgres with test accounts, not production.

## Verified
- UI-1-1 | verified | Verified by reviewer-ui and re-run by qa on this head: five long role names clip with an ellipsis at 1440, 1280 and 1100 with no sideways scroll, Start work stays inside the viewport and the title holds the full text. feature.json state VERIFIED.
- TECH-1-1 | verified | Verified by reviewer-technical and qa: one session request on a csrf_failed answer from GET /session, no loop; unit test present. feature.json state VERIFIED.
