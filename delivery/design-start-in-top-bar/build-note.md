# Build note: "+ Start" in the top bar on every board (D-89)

Branch design-start-in-top-bar, commit 2aabb63d78e422787ffe2689b3f06c1fdf579bfa (pushed, no PR). Worktree /Users/Hunchoo/psl-factory-worktrees/design-start.

## Finding
All 259 desktop boards with the "Main" top bar already drew "+ Start work" and its chevron, so no desktop board needed a change. The gap was the phone boards: only 6 main-canvas phone boards (wordmark bar) had Start. 253 phone boards had a back-link bar with no Start; those were changed.

## Boards changed (253)
| Canvas | Variant | Changed |
|---|---|---|
| main | phone back-link bar + page word (e.g. INV-0412, 1 OF 3) | 184 |
| main | phone back-link bar, no page word (SCR-10-mobile, SCR-16-mobile-validation) | 2 |
| Finance and Payroll | phone back-link bar + page word | 67 |
| both | desktop top bar | 0 (already had it) |
| main | phone wordmark bar | 0 (6 already had it) |

## Skipped and why (not changed)
- Concepts (24 main): *-concepts, a-/b-/c-/d-* (queue/item/phone/assistant variants), mascot-*.
- Reference line flows (19 main LINE-*, LINES-desktop; 7 Finance LINE-finance-*): marked "NOT A PLATFORM SCREEN".
- Flow overviews (4 main, 1 Finance): *-flow-desktop, FINANCE-moved-desktop.
- Pointers: Main.dc.html on each canvas.
- Signed-out pages (8 main, SCR-17 desktop and mobile: sign in, reset, setup, error): no session so the app draws no Start (the app mounts it only when the user has startable lines). Flag for the design engineer if D-89 should cover these.
- WhatsApp message mocks (2 main, SCR-15-*-whatsapp): not app screens.
Full per-board list: survey.csv (board, canvas, width, variant, had_start, changed).

## Markup inserted (copied from SCR-01-mobile, the existing phone Start)
Start link, main canvas:
```
<a href="SCR-04-mobile.dc.html" data-cmp="CMP-23" style="min-height: 44px; display: inline-flex; align-items: center; gap: 6px; padding: 0 14px; background: #C8401C; color: #FFFFFF; font-weight: 600; text-decoration: none; white-space: nowrap;"><svg aria-hidden="true" width="12" height="12" viewBox="0 0 14 14"><path d="M7 1v12M1 7h12" stroke="currentColor" stroke-width="2.4"/></svg>Start</a>
```
Finance canvas: same, but `href="https://claude.ai/artifact/THB9steET1h8qCmZp9jdD2" target="_blank"` (the link the Finance desktop Start already uses; SCR-04-mobile is not on that canvas).

Variant 1, back link + page word: the page word span is wrapped with Start so Start sits at the bar's right end and the word stays beside it (the bar is space-between):
`<a>← Back</a><span style="display: inline-flex; align-items: center; gap: 12px;"><span mono>WORD</span>[Start link]</span>`
Variant 2, back link, no page word: Start link appended after the back link; the two bars lacking space-between (SCR-10-mobile, SCR-16-mobile-validation) get `display: flex; justify-content: space-between; align-items: center;` on the bar div. Nothing else on any board changed (253 files, one line each).
No phone board draws a bell in its bar, so Start is the last item everywhere.

## Render check (Playwright, from /Users/Hunchoo/psl-factory/frontend/node_modules)
- Phone 390: all 253 changed boards rendered. Per board: Start inside bar, no overlap with back link or page word, no bar overflow, bar height 56 (unchanged), Start right edge 374 (16px gutter), no horizontal page scroll. Result: 253 of 253 pass, 0 bad.
- Content not pushed down: h1 top identical before and after on the 6 before/after boards (70/70, 99/99, 70/70, 72/72, 70/70, 70/70).
- Desktop 1440: unchanged boards, spot-checked 4 (main SCR-01, SCR-06, SCR-02; Finance SCR-02-desktop-returned): Start present, bar 56 high, Start 40 high, no wrap.
- Before/after PNGs (top 300px) in shots/: main-J04-mobile, main-SCR-03-mobile, main-SCR-10-mobile, main-SCR-16-mobile-validation, main-SCR-26-mobile-accepted, fin-SCR-02-mobile-evidence-asked.

## Lint
`python3 /Users/Hunchoo/software-factory/packages/design/design.py lint --project /Users/Hunchoo/psl-factory-worktrees/design-start` -> "ready for client approval", exit 0.

## Scripts
start.py (survey plus insert; --apply writes), lib.py, render.js are copied here; originals in /private/tmp/claude-501/design-start/.

## Changed files for republishing (relative to each canvas's project folder)
### main: design/canvas/project/ (186)
J04-mobile.dc.html
SCR-02-mobile-awaiting-reconciliation.dc.html
SCR-02-mobile-cancelled.dc.html
SCR-02-mobile-effect-uncertain.dc.html
SCR-02-mobile-history.dc.html
SCR-02-mobile-issue.dc.html
SCR-02-mobile-owner-needed.dc.html
SCR-02-mobile-permission.dc.html
SCR-02-mobile-processing.dc.html
SCR-02-mobile-ready.dc.html
SCR-02-mobile-setup-needed.dc.html
SCR-02-mobile-verified.dc.html
SCR-02-mobile-waiting.dc.html
SCR-02-mobile.dc.html
SCR-03-mobile-ceo-costing.dc.html
SCR-03-mobile-cto-emergency.dc.html
SCR-03-mobile-done.dc.html
SCR-03-mobile-not-yours.dc.html
SCR-03-mobile-payment-exception.dc.html
SCR-03-mobile-stale.dc.html
SCR-03-mobile.dc.html
SCR-04-mobile-accounts.dc.html
SCR-04-mobile-bu.dc.html
SCR-04-mobile-change.dc.html
SCR-04-mobile-escalation.dc.html
SCR-04-mobile-forecast.dc.html
SCR-04-mobile-incident.dc.html
SCR-04-mobile-issue.dc.html
SCR-04-mobile-leadership.dc.html
SCR-04-mobile-ledger.dc.html
SCR-04-mobile-lines.dc.html
SCR-04-mobile-minutes.dc.html
SCR-04-mobile-payroll.dc.html
SCR-04-mobile-ppe.dc.html
SCR-04-mobile-schedules.dc.html
SCR-04-mobile-validation.dc.html
SCR-04-mobile-weekly.dc.html
SCR-04-mobile.dc.html
SCR-05-mobile-cant.dc.html
SCR-05-mobile-draft-started.dc.html
SCR-05-mobile-thread.dc.html
SCR-05-mobile-working.dc.html
SCR-05-mobile.dc.html
SCR-06-mobile.dc.html
SCR-07-mobile.dc.html
SCR-08-mobile-returned.dc.html
SCR-08-mobile.dc.html
SCR-10-mobile.dc.html
SCR-11-mobile.dc.html
SCR-12-mobile.dc.html
SCR-13-mobile-delegation.dc.html
SCR-13-mobile-delivery-rules.dc.html
SCR-13-mobile-fields.dc.html
SCR-13-mobile-finance-rules.dc.html
SCR-13-mobile-permission.dc.html
SCR-13-mobile-rules.dc.html
SCR-13-mobile-validation.dc.html
SCR-13-mobile.dc.html
SCR-15-mobile-account.dc.html
SCR-15-mobile-email.dc.html
SCR-15-mobile-settings.dc.html
SCR-15-mobile.dc.html
SCR-16-mobile-rfp-lost.dc.html
SCR-16-mobile-rfp-outcome-lost.dc.html
SCR-16-mobile-rfp-outcome-pending.dc.html
SCR-16-mobile-rfp-outcome-unknown.dc.html
SCR-16-mobile-rfp-outcome.dc.html
SCR-16-mobile-rfp-pending.dc.html
SCR-16-mobile-rfp-unknown.dc.html
SCR-16-mobile-rfp-won.dc.html
SCR-16-mobile-sow-signed.dc.html
SCR-16-mobile-success.dc.html
SCR-16-mobile-team-input.dc.html
SCR-16-mobile-validation.dc.html
SCR-16-mobile.dc.html
SCR-19-mobile.dc.html
SCR-21-mobile-deactivate.dc.html
SCR-21-mobile-invite.dc.html
SCR-21-mobile.dc.html
SCR-22-mobile.dc.html
SCR-23-mobile.dc.html
SCR-24-mobile.dc.html
SCR-25-mobile-assembling.dc.html
SCR-25-mobile-invalid.dc.html
SCR-25-mobile-received.dc.html
SCR-25-mobile-returned.dc.html
SCR-25-mobile-review.dc.html
SCR-25-mobile.dc.html
SCR-26-mobile-accepted.dc.html
SCR-26-mobile-edit.dc.html
SCR-26-mobile-reject.dc.html
SCR-26-mobile-response-review.dc.html
SCR-26-mobile-review.dc.html
SCR-26-mobile.dc.html
SCR-27-mobile-adjust.dc.html
SCR-27-mobile-approvals.dc.html
SCR-27-mobile-ask.dc.html
SCR-27-mobile.dc.html
SCR-28-mobile-drafted.dc.html
SCR-28-mobile-internal.dc.html
SCR-28-mobile-published.dc.html
SCR-28-mobile-review.dc.html
SCR-28-mobile-suggesting.dc.html
SCR-28-mobile.dc.html
SCR-29-mobile.dc.html
SCR-30-mobile-no-owner.dc.html
SCR-30-mobile-overdue.dc.html
SCR-30-mobile-verified.dc.html
SCR-30-mobile.dc.html
SCR-31-mobile-authorise.dc.html
SCR-31-mobile-closed.dc.html
SCR-31-mobile-decision.dc.html
SCR-31-mobile-execution.dc.html
SCR-31-mobile-go-live-note.dc.html
SCR-31-mobile-impact.dc.html
SCR-31-mobile-notice.dc.html
SCR-31-mobile-rejected.dc.html
SCR-31-mobile.dc.html
SCR-33-mobile.dc.html
SCR-34-mobile.dc.html
SCR-35-mobile-detail.dc.html
SCR-35-mobile.dc.html
SCR-38-mobile-changed.dc.html
SCR-38-mobile.dc.html
SCR-39-mobile-example.dc.html
SCR-39-mobile-review-own.dc.html
SCR-39-mobile-review.dc.html
SCR-39-mobile.dc.html
SCR-40-mobile-draft.dc.html
SCR-40-mobile-review.dc.html
SCR-40-mobile-submitted-portal.dc.html
SCR-40-mobile-submitted.dc.html
SCR-41-mobile-register.dc.html
SCR-41-mobile.dc.html
SCR-42-mobile-held.dc.html
SCR-42-mobile-readiness.dc.html
SCR-42-mobile-ready.dc.html
SCR-42-mobile-record.dc.html
SCR-42-mobile.dc.html
SCR-43-mobile.dc.html
SCR-44-mobile-decision.dc.html
SCR-44-mobile-owner-needed.dc.html
SCR-44-mobile-readiness.dc.html
SCR-44-mobile-ready.dc.html
SCR-44-mobile-returned.dc.html
SCR-44-mobile.dc.html
SCR-45-mobile-accepted.dc.html
SCR-45-mobile-changes.dc.html
SCR-45-mobile-declined.dc.html
SCR-45-mobile-signatures.dc.html
SCR-45-mobile.dc.html
SCR-46-mobile-evaluating.dc.html
SCR-46-mobile-not-met.dc.html
SCR-46-mobile-qualified.dc.html
SCR-46-mobile-record.dc.html
SCR-46-mobile-setup-needed.dc.html
SCR-46-mobile.dc.html
SCR-47-mobile-uncertain.dc.html
SCR-47-mobile-working.dc.html
SCR-47-mobile.dc.html
SCR-48-mobile-gaps.dc.html
SCR-48-mobile-received.dc.html
SCR-48-mobile-record.dc.html
SCR-48-mobile.dc.html
SCR-49-mobile-blocked.dc.html
SCR-49-mobile-closed.dc.html
SCR-49-mobile-decision.dc.html
SCR-49-mobile-returned.dc.html
SCR-49-mobile.dc.html
SCR-50-mobile-record.dc.html
SCR-50-mobile-refused.dc.html
SCR-50-mobile-report.dc.html
SCR-50-mobile-retro.dc.html
SCR-50-mobile-review.dc.html
SCR-51-mobile-decide.dc.html
SCR-51-mobile-draft.dc.html
SCR-51-mobile-investigating.dc.html
SCR-51-mobile-not-escalated.dc.html
SCR-51-mobile-received.dc.html
SCR-51-mobile-review.dc.html
SCR-52-mobile-drafting.dc.html
SCR-52-mobile-received.dc.html
SCR-52-mobile-review.dc.html
SCR-52-mobile-setup.dc.html
SCR-52-mobile-tuesday.dc.html
STATES-mobile.dc.html

### Finance and Payroll: design/canvas/finance/project/ (67)
SCR-02-mobile-evidence-asked.dc.html
SCR-02-mobile-evidence-supplied.dc.html
SCR-02-mobile-returned.dc.html
SCR-03-mobile-own.dc.html
SCR-09-mobile-error.dc.html
SCR-09-mobile.dc.html
SCR-18-mobile-permission.dc.html
SCR-18-mobile.dc.html
SCR-20-mobile-record.dc.html
SCR-20-mobile.dc.html
SCR-32-mobile.dc.html
SCR-36-mobile.dc.html
SCR-37-mobile.dc.html
SCR-53-mobile-drafting.dc.html
SCR-53-mobile-investigating.dc.html
SCR-53-mobile-owner-needed.dc.html
SCR-53-mobile-publishing.dc.html
SCR-53-mobile-quarantined.dc.html
SCR-53-mobile-returned.dc.html
SCR-53-mobile-reviews.dc.html
SCR-53-mobile-setup-needed.dc.html
SCR-53-mobile-uncertain.dc.html
SCR-53-mobile-units.dc.html
SCR-53-mobile-verified.dc.html
SCR-54-mobile-export.dc.html
SCR-54-mobile-held.dc.html
SCR-54-mobile-investigating.dc.html
SCR-54-mobile-returned.dc.html
SCR-54-mobile-review.dc.html
SCR-54-mobile-verified.dc.html
SCR-54-mobile-withdrawn.dc.html
SCR-55-mobile-calculating.dc.html
SCR-55-mobile-date-review.dc.html
SCR-55-mobile-investigating.dc.html
SCR-55-mobile-register-review.dc.html
SCR-55-mobile-returned.dc.html
SCR-55-mobile-schedule-review.dc.html
SCR-55-mobile-verified.dc.html
SCR-56-mobile-actuals.dc.html
SCR-56-mobile-group-review.dc.html
SCR-56-mobile-group-rows.dc.html
SCR-56-mobile-investigating.dc.html
SCR-56-mobile-review.dc.html
SCR-56-mobile-uncertain.dc.html
SCR-56-mobile-verified.dc.html
SCR-57-mobile-held.dc.html
SCR-57-mobile-investigating.dc.html
SCR-57-mobile-publish.dc.html
SCR-57-mobile-receipts.dc.html
SCR-57-mobile-result-review.dc.html
SCR-57-mobile-source-review.dc.html
SCR-57-mobile-verified.dc.html
SCR-58-mobile-duplicate.dc.html
SCR-58-mobile-investigating.dc.html
SCR-58-mobile-observe.dc.html
SCR-58-mobile-rejected.dc.html
SCR-58-mobile-review.dc.html
SCR-58-mobile-verified.dc.html
SCR-59-mobile-combine-review.dc.html
SCR-59-mobile-followup.dc.html
SCR-59-mobile-input-review.dc.html
SCR-59-mobile-match-held.dc.html
SCR-59-mobile-match-review.dc.html
SCR-59-mobile-publish.dc.html
SCR-59-mobile-receipts.dc.html
SCR-59-mobile-totals-review.dc.html
SCR-59-mobile-verified.dc.html
