VERDICT: PASS
REVIEWER: qa
COMMIT: bb47233b740f50132102bbe88167479f9645553f
AUTHORITY: delivery integrated QA

## Summary
- Ran the live demo (app :4975, mock :4974, reset before each journey, persona cookie `psl_mock_persona`) with Playwright at 1440 and 390. Contract mock only: nothing is sent to Support. No file in the worktree was changed.
- Handover states W-3701..3705, 3709, 3710, 3711 render from data. Publish writes once on a double press and shows "published" only after the re-read. Publish also survives reload.
- Recording Support's reply sends upload, then one POST with `gaps[]` and the PM's name. Received sends no `gaps`. The gaps or acknowledged state and "Recorded under your name" show only after the re-read, and survive reload.
- Failure paths hold at both widths: 409, 500 and 403 on write; 403, 404 and 500 on read; uncertain W-3706 and W-3707; stale W-3708; ceo refused on W-3701 and W-3704.
- Not exercised: the axe and fidelity runs (other reviewers), a real Support send, and a real backend. The `record-then-fail` scenario was not run (the 500 on the write was injected with `page.route`).

## Findings
None.

## Verified
- UI-2-1 | verified | the "When they replied" date-time field accepts `2026-04-10T11:00` and the body carries `responded_at` `2026-04-10T11:00:00+01:00`, matching the spec. That body carries WAT, not a UTC conversion, as specified.
- UI-1-3 | verified | same field; "Support replied" is one fixed row, "Femi Ojo · Support lead", beside "When they replied".
- Delivery back link (round 2) | verified | 390: "← Delivery" (aria "Back to Delivery") goes to /projects/P-0101/delivery. 1440: the crumb "Delivery" does the same and the phone-only back link is hidden by design. The row "Handover to Support" links to /work/W-3704 at both widths.
- Shared `workspace.css` from the dlv-00 merge (F-43 and F-45) | verified | the diff adds only `.ws[data-line="ledger_sources"]` and `.ws[data-line="cash_forecast"]` rules plus the new `.ws-figstrip` and `.ws-caption` classes. The handover is line `delivery_handover`, so it is unaffected. No sideways scroll on any handover page at 1440 or 390.

## Evidence
- States: W-3701 shows the Publish button only (no form). W-3702 shows "Review needed?" Unknown, with no Publish button and no form. W-3703 shows the in-place form, "Support replied | Femi Ojo · Support lead" and "When they replied". W-3704 shows GAPS · 2 with two OPEN gaps. W-3705 shows a closure link to /work/W-3720. W-3709 shows no form (not your role); its text was not read into this report.
- Publish: double-click on W-3701 gave one POST /api/v1/work/W-3701/steps, then the record form, which was still there after reload with no Publish button.
- W-3706 (200 `effect_uncertain`): the "Confirm what happened" reconcile panel with "It arrived / It didn't arrive / I can't tell yet", Publish gone, one POST, banner "Handover · delivery unconfirmed". W-3707 had the same one POST and Publish gone. W-3708 (409): "This changed while you were working. Showing version 2." with the re-read's "Published 08 Apr", no publish step.
- Publish 500 (injected): "We couldn't confirm this step. Check the page before trying again." The status shows no "published", and Publish is locked.
- Record:
  - Record is disabled until proof and the tick are given. The footer says "Add the proof and confirm it's genuine to record this."
  - The remove chip measures 24x24 at 1440 and 48x48 at 390.
  - POST to /api/v1/tasks/T-3701/response with `{expected_revision:1, who:"R-3701", action:"changes_requested", responded_at, evidence_id, attested:true, gaps:[the two lines], case_revision, version_id:"V-3701"}`. From W-3703 the call goes to T-3703.
  - After the record, the GAPS · 2 state shows "Recorded under your name" and the page survives reload.
  - Received sent no `gaps`.
- Record failures (injected with `page.route`): 500 gave "We couldn't confirm the reply was recorded. We've reloaded this item so you can see whether it was." with the entries kept and no success claim. 409 gave "This changed while you were recording. We've reloaded it. Check the details and record again." with the entries kept. 403 gave the no-access view with no recorded text.
- Reads: W-3703 with 403 and with 404 gave identical no-access views (no title, project, reference or gap text). A 500 gave "couldn't load" with a Try again button. ceo got no-access on W-3701 and W-3704 with no leak. A 401 route redirected to the sign-in flow with next=/work/W-3703.
- Notes, not blocking:
  - On the `pm` persona with the mock cookie scenarios 403 and 404, `/me` fails first ("Your account can't use PSL Factory", and a "couldn't load your account" error). That is the shared shell, not F-40.
  - Unknown id W-9999 serves a different mock fixture (INV-0412). This is the mock fallback, not an F-40 issue.
