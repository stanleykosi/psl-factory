VERDICT: CHANGES
COMMIT: 0c081045fa29ad5d62d5ffed92916e21dbc68f13
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- D-193 sync-only re-check of head 0c081045 (from 6636f0eb, the head I passed). The merges brought F-85 (live work item), F-86 (live Start work) and F-72 (live document review) into the branch. None of their files is on the Delivery tab, and the Delivery tab's styles are unchanged, so no browser run was needed. One change does reach the Delivery journey: the Delivery row titles now open a route that the merged mock no longer serves (finding UX-2-4). Verdict moves to CHANGES on that finding alone.
- Delivery tab files unchanged in the diff: `DeliveryTab.tsx`, `deliveryModel.ts`, `useDeliveryOverview.ts`, `dlvov.css`, `ProjectJourney.tsx`, `projects/model.ts`, `project-tabs.css`, `mock/delivery-overview.mjs`. `projects/DocumentsTab.tsx` changed, but it is the Documents tab, not F-113.
- Mock routing: the new route matchers (`WORK_LIVE_PATH`, `CASE_FILES_PATH`, `START_LIVE_PATH`, `isLiveDocumentPath`) do not match F-113's three reads (`/projects/{id}/delivery-overview`, `/work/{id}/release-register`, `/projects/{id}/delivery/{n}/closure-checklist`), so those reads still answer from `deliveryRead`. Checked by pattern, not by running the mock.
- Work item route changed: `app/work/[id]/(item)/layout.tsx` and `page.tsx` now send any integer id to the live work item view (F-85). The Delivery row titles link to `/work/2501` to `/work/2505`, which are integer ids, so they now reach the live view. `mock/work-live.mjs` serves only 4101 to 4108, and returns 404 "This record is unavailable." for everything else. Before the merge those links reached the v7 item that round 2 walked.
- Also changed, not Delivery: `work-item.css` (F-85 history list), `types.ts`, `next-config.test.ts` allow-list, and the F-86 Start work and F-72 document review files. None changes a Delivery surface.
- The D-199 CI workflow and `delivery/checks.sh` change how gates run. They do not change the app's UI.

## Findings
- UX-2-4 | blocking | The Delivery tab's row titles (`/work/2501` to `/work/2505`) now open the live work item view, and the mock answers those ids with a 404 "This record is unavailable." That is a dead end on the Delivery journey, and it breaks the spec's rule that the row title opens the work item. Fix in the mock or the route, not on the Delivery tab: for example add live fixtures for 2501 to 2505 in `mock/work-live.mjs`, or make the layout fall back to the v7 frame for ids the live mock does not know. The Delivery tab itself needs no change. Re-walk the link at 1280px and 390px after the fix.

## Verified
- UX-1-1 | verified | No overlap at 1280px or 390px. Rows are padded inside the panel. Tag and date sit right-aligned, stacked. Screenshots: /private/tmp/claude-501/ux/r2-d.png and /private/tmp/claude-501/ux/r2-m.png. Carried forward: the Delivery tab files and styles are unchanged since 6636f0eb.
- UX-1-2 | verified | The closure reason reads "Handover to Support – Support listed 2 gaps." Carried forward: `delivery-overview.mjs` and `deliveryModel.ts` are unchanged.
- UX-1-3 | verified | Phone rows are about 90px, from over 190px before. Title and tag share one line, with reference and date beneath. This matches SCR-43-mobile. Carried forward: `dlvov.css` is unchanged.

## Notes
- Spec AC3 and the line near it still say "click Open". build.md already asks the coordinator to reword them to "click the row title".
- Not retested: the 403 and 500 states. Round 2 did not touch that code, and round 1 verified 403.
- The 2501 to 2505 destinations were not walked after the merge. This review did not start a server or run a browser, as the sync-only rule asks. UX-2-4 is from the diff and the mock source.
- Process slip (round 2): when cleaning up I killed PID 82822 by mistake. It was a mock server running from /Users/Hunchoo/psl-factory/frontend, not one I started. My own three processes were already stopped. If someone was using that mock, restart it.
