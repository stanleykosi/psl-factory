VERDICT: PASS
COMMIT: f29087ed4c453d75e2766dfa992956fcc94d9aab
REVIEWER: ui-reviewer
AUTHORITY: UI design reviewer

## D-193 pre-merge re-check of the main sync
This is a D-193 pre-merge re-check of the merge of origin/main 4a88c26b into the branch (cfc3c462 to f29087ed). Diff-only; no server, no new screenshots or fidelity runs. The evidence and findings below are from cfc3c462 and are kept.
- `frontend/mock/server.mjs`: the diff adds imports, F-62 live work-list/item routes, and F-113's `deliveryRead` route. F-71's milestone-completion route line is unchanged and still comes first; the delivery route follows it on a different path. Nothing there touches the Money or Milestones reads.
- F-71's own files are unchanged: no diff in the money and milestones components, `money.test.tsx` or `milestones.test.tsx`. The path-wide `projects/` diff is not empty, but only F-113's files (DeliveryTab, deliveryModel, useDeliveryOverview, dlvov.css) plus two small shared edits.
- Shared edit that touches my lens: `model.ts` `visibleTabs` now adds a Delivery tab after Journey in the project tab bar for every project, so it shows above the Money and Milestones tabs too. `ProjectJourney.tsx` passes `caseId` to DeliveryTab. Money and Milestones bodies, tables, cards and css are untouched. The bar is the F-70/F-113 shell, which the exceptions file already treats as shell-owned (tab counts, breadcrumb); I have not re-measured it at 1440 or 390. The tab bar already scrolls on the phone width screenshots, so one more label is a low risk. Offered as a note, not blocking.
- Other incoming files (verified list, work list, my-work css) are on other screens.
- ci-mode checks passed on f29087ed (GitHub Actions run, success).
- The signed 46-entry exceptions and D-202 visual waivers are unaffected. Verdict stays PASS.

## Summary
- No frontend change is needed. UI-1-2, UI-1-3 and UI-1-4 are fixed and retested at 1440 and 390 with fresh screenshots. No sideways scroll on either tab in any state checked.
- The fidelity tool still reports FAIL on all six runs, with the exceptions file applied (coverage 11.9% to 83.3% with exceptions, visual 80.8 to 82.7; table below). No element is missing because of a build gap (class c). Every remaining miss is a board sample value live data cannot carry (a), UI-1-5 (b), or a copy difference the spec already records (a). Each of these is the design engineer's to except or waive (UI-2-1 to UI-2-3).
- The visual score stays under 90 because of accepted hides and spec-approved additions: Milestones adds INVOICE and PAID columns and a Recorded completions section, Money adds a non-stage row and a Due line, and live data replaces the board's sample rows. Cause is exceptions and waivers, not styling.
- The verdict is PASS for the frontend. The design-fidelity gate stays open until the design engineer approves the exceptions or waives the score (UI-2-1 to UI-2-3).
- Evidence is in the scratchpad `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/`: `fid2/<board>-<width>/` (report.json, side-by-side.png), `fid2/scores.txt` and `fid2/run.sh`, and `shots2/` (money and milestones states at 1440 and 390). The `/Users/Hunchoo/psl-factory-main/design/canvas/project` boards were used.

Fidelity runs (finance_lead cookie, P-0101; Milestones "changed" runs also set `psl_mock_milestones=changed`). The Money run at 1440 used `?figure=kickoff`. Each run waited 12 s for the page, because the shared dev server compiled slowly and the first two attempts caught the "Loading" skeleton (discarded).

| Board | Width | Coverage (raw) | Coverage with exceptions | Visual | Result |
|---|---|---|---|---|---|
| SCR-12-desktop | 1440 | 55.1% (27/49) | 63.3% | 80.8 | FAIL |
| SCR-12-mobile | 390 | 36.4% | 36.4% | 82.0 | FAIL |
| SCR-38-desktop | 1440 | 65.1% | 74.4% | 81.4 | FAIL |
| SCR-38-desktop-changed | 1440 | 78.6% | 83.3% | 82.7 | FAIL |
| SCR-38-mobile | 390 | 59.1% | 68.2% | 79.2 | FAIL |
| SCR-38-mobile-changed | 390 | 75.0% | 75.0% | 81.4 | FAIL |

Raw coverage matches round 1 to the decimal; the exceptions file lifts it only by the 10 entries that match by name. The visual score moved by 1 to 3 points either way (80.8 to 82.7 against 78 to 84 in round 1), which the fixes in UI-1-2 to UI-1-4 do not change.

Still missing after exceptions, by class:
- (a) board sample values and wording live data cannot carry: Money desktop and phone: "Verified 03 Nov", "Finance tracks", "Awaiting Finance decision", "Held · owner needed", "Not yet due · amount set at go-live", "Stage 2 · UAT" style stage names, the "—" cells, "Where ₦4,250,000 comes from" head, the three source rows (Signed SOW v2, Stage terms v1, "Milestone 2 completion, recorded by Tunde Bello HB-M2"), and the lead sentence "Every figure links to the record it came from" (live says "Each figure shows where it comes from when a source is recorded", spec Conflicts 3). Milestones: "Tunde Bello · PMO" (the board's user chip; live shows the signed-in persona), "Done 27 Oct · proof" and "Done 11 Nov · client UAT sign-off" (live shows "Done <date>", Due and a Proof button, spec 21), "Not yet" (live "Not completed", spec line 197), the "Not yet · amount set at go-live" and "Unknown" hypercare row (live data gives NGN 500,000.00), "CR-0031 added work to milestone 3 ..." callout (live shows "CHG-0007 · Extra reporting scope" in the CHANGES column), the "INV-0398 · verified" phone lines (live "Delivered"), and the "—" cells.
- (b) UI-1-5: "₦3,000,000", "₦4,250,000", "₦3,000,000.00", "₦4,250,000.00" against "NGN ..." (6 element entries across the runs).
- (c) real build gap: none.
- Shell-owned (F-70, not this feature): "← Project" and "← Projects" back links (live "Back to Projects"), breadcrumb, tab counts, Alerts button, user chip.

## Findings
- UI-2-1 | non-blocking | medium | design engineer (exception or waiver) | Board sample values and wording that live data cannot carry are still counted missing: the (a) list above, 15 to 20 elements per run. Approve them as exceptions in `delivery/features/F-71/fidelity-exceptions.json` (the file matches by role and name, so each exact board text needs its own entry), or accept them as sample content. Coverage is 100% only once they are listed. Spec-recorded copy differences that are not in the file yet: "Not yet" against "Not completed" (spec line 197), "Done 27 Oct · proof" as "Done <date>" plus Proof button (spec 21, D-185), and the lead sentence (spec Conflicts 3). Reports: `fid2/*/report.json` under `coverage.missing`.
- UI-2-2 | non-blocking | low | design engineer (exception or waiver) | UI-1-5, carried over: amounts read "NGN 3,000,000.00" where the boards draw "₦3,000,000". The spec requires the currency code from the item, so this is intended. It needs an approved exception; there is no way to match the board without dropping the code. Raising it again in the exceptions file closes the 6 elements.
- UI-2-3 | non-blocking | medium | design engineer (exception or waiver) | Visual score is 79.2 to 82.7 on all six runs (needs 90). It stays under 90 because of accepted hides (Chidi card, report title, "Mark milestone N complete") and spec-approved additions the boards do not draw: INVOICE and PAID columns, Recorded completions and Proof buttons, non-stage rows, Due lines, the limited callout, plus live rows in place of the sample ones. My side-by-side reading found no remaining styling difference of the build's own (type, colour, borders, table and card surfaces, header all match). Waive the 90 for this feature, or redraw the boards to the live shape.

## Re-score with the signed exceptions (D-202)
Re-run once on the same head and server, with the 46-entry `fidelity-exceptions.json` (output in scratchpad `fid3/<board>-<width>/`, `fid3/scores.txt` not written; table from `fid3/out.txt`). Coverage with exceptions is 100% on all six runs and nothing is unexcepted. The tool still prints FAIL because it does not read `visual_waivers`; visual is waived in the signed file for each run.

| Board | Width | Coverage with exceptions | Visual | Visual waived |
|---|---|---|---|---|
| SCR-12-desktop | 1440 | 100% | 80.8 | yes (D-202) |
| SCR-12-mobile | 390 | 100% | 82.0 | yes |
| SCR-38-desktop | 1440 | 100% | 81.4 | yes |
| SCR-38-desktop-changed | 1440 | 100% | 82.7 | yes |
| SCR-38-mobile | 390 | 100% | 79.2 | yes |
| SCR-38-mobile-changed | 390 | 100% | 81.4 | yes |

UI-2-1, UI-2-2 and UI-2-3 are settled by the design engineer's signature and are closed. The Notes above stand.

## Notes
- Phone Money cards show "Unknown" in the monospace face and larger than on desktop (bold sans). It is still the same brown and is the only Unknown style on that screen; the Milestones phone cards use bold sans. Taste, not blocking; worth aligning if the design engineer cares.
- Phone Money "Tap an amount to see where it comes from" is plain text where the board draws a link. It does nothing as a link on the board either way (the sheet opens from the amounts). Offered for the exceptions file with UI-2-1.
- Kick-off row Paid cell (desktop) reads "Paid NGN 2,000,000.00 · / Owed NGN 500,000.00" over two lines, one pair per two lines. Each figure is intact, so UI-1-2 is met; the trailing dot at the end of the Paid line is a small oddity that reads fine.
- Mock demo controls ("Demo") and the Next dev badge appear in the screenshots only because of the shared dev build.

## Verified
- UI-1-2 | verified | money-ok-1440.png and ms-ok-1440.png: "NGN 2,000,000.00", "NGN 500,000.00" and "NGN 250,000.00" each stay whole; Paid and Owed break only between the two. Same at 390 (money-ok-390.png, ms-ok-390.png).
- UI-1-3 | verified | money-ok-1440.png: the panel shows the header "Where a figure comes from" and "Choose an amount to see where it comes from." as its body, with no empty box. With a figure chosen (money-figure-1440.png) the panel shows the source list.
- UI-1-4 | verified | ms-ok-1440.png and the phone cards (fid2/SCR-38-mobile/side-by-side.png): "Unknown" is bold brown text, no yellow tag, same as Money; Paid Unknown, Owed Unknown and "+ the change · change amount Unknown" all match.
- UI-1-1 | verified | fid3 re-run on cfc3c462 with the signed 46-entry exceptions file: coverage with exceptions 100% on all six runs, 0 unexcepted; visual 79.2 to 82.7 waived per run under D-202 (`visual_waivers`). Side-by-side reading found no difference of the build's own.
