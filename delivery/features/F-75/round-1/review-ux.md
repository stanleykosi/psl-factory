VERDICT: CHANGES
COMMIT: bfcad616bcb0a7d43a339ba6f4ba1ba67681eeb9
REVIEWER: ux-reviewer
AUTHORITY: UX reviewer

## Summary
- Both tabs match the approved SCR-11 and SCR-29 boards at 1440 and 390 on the shared mock: register switch with count badges, AGE column, "From <meeting> · <date>", amber Unknown, "Owner needed" in signal ink, no horizontal scroll, no console errors apart from the expected 4xx.
- Unknown is never 0: null age reads "—", null due reads the amber Unknown tag, null owner on Issues reads "Owner needed". P-0102 badge stays 30 with 25 then 30 rows loaded. Escalations (ISS-0240) never drawn.
- Refusal states all read well: P-0099 (project no access), P-0103 (tab no access, no row text), 401 ("You're signed out. Sign in"), persona `none` ("No sections are open to your role yet"). Empty (P-0106) and no-match search ("No issues match “zzz”." with Clear search) are right. `pmo_lead` sees Changes, Emergencies, RFPs only, and `?register=issues` falls back to Changes.
- One blocking accessibility gap: after "Show more" removes its button, focus is lost on the phone card list (it falls to BODY), and on desktop it lands on the table frame, not the first new row as spec criterion 21 says.
- Screenshots (fresh, this head) are in /private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/s/ (reg101, reg102, reg106, regpmo2, regq, act101, act106, actq, act103, act401 and others, each at -1440 and -390).

## Findings
- UX-1-1 | blocking | medium | frontend | Focus after "Show more" (spec acceptance 21: focus moves to the first new row). Observed on P-0102 Issues with `psl_mock_persona=pm`: at 390 the button disappears and `document.activeElement` is BODY, so a keyboard or screen-reader user loses their place in the list; at 1440 focus lands on a DIV (the table frame), not the first new row. The builder disclosed this in build.md (`useFocusAfterMore`, rows have no links, phone cards get no focus move), but it is not a recorded spec deviation. Expected: focus on the first newly added row/card (make it focusable with tabindex -1, or keep focus on a stable element), at both widths. Actual: focus lost (phone) or on the frame (desktop). Path: `frontend/src/features/projects/RegistersTab.tsx` and `ActionsTab.tsx` via `useFocusAfterMore`.
- UX-1-2 | non-blocking | low | frontend | The note "Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval." shows under Changes, Emergencies and RFPs too (seen for `pmo_lead` on Changes), where it does not apply. The spec keeps the note as drawn, so this is polish: show it only under Issues.
- UX-1-3 | non-blocking | low | frontend | A closed issue (ISS-0221, "Closed by QA and PM") shows "Owner needed" in signal ink, which reads as an open task on finished work. It follows the spec rule (null owner on Issues reads "Owner needed"); consider plain "—" when the state is closed. Product call, not a spec break.

## Verified
- None. Round 1: no earlier findings to verify.

## Notes
- Accepted per spec, not findings: rows as plain text, no owner role/"recorded by PM" marks, no Overdue row tag, no page-size choice, Critical as a neutral tag, "ISSUE/WHAT/SEVERITY" columns on Changes with "—" where live has no value, badges following the search (all 0 for `?q=zzz`).
- Keyboard: arrow keys on the register tabs move Issues to Changes. Show more requested `?page=2` once, appended 5 rows (30), badge stayed 30, and Changes then showed 1 row (not twice).
- Not covered: axe run, a forced 503 on Show more, and live backend criterion 20 (build.md says not run). Design-fidelity tool not run by the builder; I compared by eye only.
- One first load for `pmo_lead` at 1440 showed "We couldn’t load your account … unexpected_response" while the dev server was compiling; it did not reproduce on the next load. Likely the shared slow dev server, but worth a glance if it recurs.
