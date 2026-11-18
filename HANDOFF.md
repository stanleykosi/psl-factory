# PSL Operations Factory handoff

## Current checkpoint · 18 November 2026

Continue the user's Railway consolidation and262-state acceptance task after this checkpoint. Keep HOD values/owners deferred, preserve all122 IDs/13families and the108-process PMO/Finance release. Use the in-app browser and synthetic data. Do not merge main, reset/clean, connect real accounts or create paid services.

Branch `build/design-consolidation`. Prior pushed checkpoint `38ad2f8c` contains the verified won-proposal→Planning increment. This checkpoint adds verified staff account/action handover. Inspect git status/fetch before further work; preserve local changes. Last fetched main `8f347a0a32a24ad3b48fbc6ab2ea351613e1dfa6`, unmerged. [Main source reconciliation](docs/design/2026-11-18-main-reconciliation.md) distinguishes frontend/mock notes from native proof.

## Hosted and tested

- [Railway application](https://psl-design-web-design-acceptance.up.railway.app), project `f957481b-c6f7-43af-bc66-449a330a9d53`, environment `design-acceptance`.
- Current152 source: web `d9174754-fbb0-4cdd-8525-3be408c18aa4`, worker `da101d9c-7623-4612-8a8f-2adf57cebb4f`, both SUCCESS. Service IDs web `ac6b2ef8-4bd1-4dcf-9c28-5ef5b0de0de3`, worker `9959671c-482b-4384-9164-13b532b6dc83`, checks `00c14ca1-5361-4bee-97a5-2ec7aba6ef18`.
-148 `d3bda776-509f-49ec-8a0c-39fc5e480a7a`:48 PostgreSQL tests PASS/92.407s, checks/drift/fixture/final0. Applied additive identity0006/0007 to preview only after pass; source-only native staff fixture succeeded.
-150 `8b887bde-b790-4cb8-9e9f-1b2e2b36eda0`:57 PASS/178.208s, checks/drift/final0, no migration/fixture. Includes current roles/source permissions, native delegation, concurrent departure/decision revocation, sessions and queued delivery.
-152 `23e2ff09-ed32-40f5-8e33-52b81d9b0bef`:18 PASS/26.056s, checks/drift/final0, no migration/fixture. Covers actual account HTTP→unassigned history,23-revision bounded pagination/current permission denial, design/shell.
- Failed runs remain failed:1470tests/1setup error/0.265s (old SQL rejectedv3);14939PASS/1obsolete-labelFAIL/17notrun/156.960s;1510PASS/1null-ownerERROR/17notrun/3.045s. Corrections and exact evidence are in BUILD-TESTS.md; overlapping cohorts are not unique totals.
- All1,716 service runtimepaths match passing152; root1,715 excluding acceptance settings. Stages `.runtime/design-states-152-checks` and `.runtime/design-states-151-{web,worker}` carry the same source (stage names differ only). Worker script SHA256 `540f735cd6a2f42fccbf9aad5c044fd7594e1506ea07f79251224968aae06d6e` unchanged.
- Retained PostgreSQL testDB `test_design_archive_20261117`: never drop/reset. Preserve applied identity0006/0007 and pmo0064–0069 bytes. Use new additive migrations for subsequent changes.

## Actual browser results

Staff source-only fixture: synthetic person120, successor121, technical authority2; projectone `f01c74c2-81f7-4be8-b9a5-6aae4c71a243`/proof2032/action11 and projecttwo `9ca06486-7269-4c04-8310-da8f27205abe`/proof2033/action12. Browser used Setup→Staff/search/Active→both-scope departure review→Cancel (account retained), then actual departure at21:24:45WAT under150. **Do not repeat/reset/reseed person120.** It is now inactive with zero access. Action11 remains Owner needed;12 belongs to121. Both remain Open/revision2.152 modern histories show prior120, both unchanged20Nov21:04:24WAT deadlines, recorder/reason/proof. Both project role policies remain Active/rev1 with121Current; inactive120 cannot act. No prior approval was transferred or action completed.

Desktop1280/body-client1265 and phone390/body-client375 passed. Saved/inspected `.runtime/design-acceptance-staff152-{unassigned-phone,reassigned-desktop,inactive-desktop,inactive-phone}.jpg`; earlier roster148 phone also retained. Default viewport restored. Browser2/tab4 is the filtered inactive roster, no edits, handoff marked; staff CUA part summarised once. Reuse `pslBrowserAPI`, `pslStateTab`, `evidenceFs`; after compaction call `cua.rewriteDocumentation()` before browser actions.

Previous accepted won-source journey remains: case `6cb3da61-9922-49e3-9e32-37803cc45be6`, work115 Verified/Planning116/packet2031; exact requirements2011/plan2014/Engineering2012/Security2013, quoteNGN100.00/whole contract, unknown date/contact and fresh Planning decisions retained.146 passed58PGtests/657.028s and native fixture. No registration or Planning protocol change. Direct source-bound registration/date/contact113 remains accepted too.

## Continue implementation

Inventory remains262 states/59screen IDs. Current ledger **207 observed /186 with open checks /55 unseen /21 completed scoped journeys**. New SCR21 anddeactivate observations remain partial because the actual started-work handover/profile branches still need work. Do not declare262 complete or turn optional extra examples into requirements. [Acceptance ledger](docs/design/screen-state-acceptance.md) records exact criteria/proof.

1. Finish/push this reviewable checkpoint, then continue named access profiles, current role/scope labels and pending invitation rows. Replace the main raw-action grant UI with configured profile controls; retain the exact legacy interface as secondary. Keep technical access separate from D05 business nominations/approvals. Real profile values remain deferred.
2. Finish the design's actual started factory work/recording-responsibility handover. Current global departure correctly holds on current worker/decision claims and reuses native recovery, but the connected UI/browser journey is not yet proved. Preserve starter/approvals; use reviewed current execution binding, original-operation reconciliation and exact source permissions.
3. Add controlled reactivation with fresh roles/access, never resurrecting old grants or sessions. Proposed design: require all-scope current authority and removal/review of old D05 nominations before enabling; fresh allocation follows its native human review. This is a proposal, not implemented functionality. Current session fence is already built/tested.
4. Build the inspected payroll row-level continuation gap: SCR09/18 let good rows continue while specific rows remain held. Existing configured CSV/Excel intake, provider review, matching, HR corrections and aggregates exist, but native parent-held gates stop that progression. Preserve hashes/forbidden-field rejection, unknown held totals, current HR-only details, source-control and final-publication safeguards. See backlog `payroll_row_progress_20261118`.
5. Authorised past-winning answer reuse, ordinary client acceptance/workaround, remaining Finance/Setup/project states and role/device/recovery checks remain. Inspect native code first. Railway reproducible deployment/IaC migration before1December also remains; review official docs, no new services/charges.

HOD work is actual people/admin scope, login profiles, audiences, calendars/financial oracles/thresholds/requiredness. Live providers/destinations are separate external evidence. Missing values hold dependent actions; missing interfaces remain engineering work.

## Working commands and history

Use `cmd.exe`, `login:false`, `.venv\Scripts\python.exe -X utf8`. Local Django/compile checks work; PostgreSQL tests run on Railway. `git -c core.whitespace=cr-at-eol diff --check`. Git/Railway network may need approved escalation. Write commit text to `.runtime/<name>.txt`, then `git commit -F`; verify commit before push. Never print secrets. No new subagents delegated.

Compare frozen stages with `.runtime/compare_design_runtime.py`; root mode `--root`. Await robocopy completion before overlays. Read final `PSL_ACCEPTANCE_EXIT` before replacing checks. Current152 final0, no running test. Historical conflicting restart notes are preserved in [archived handoff](docs/build-history/HANDOFF-2026-11-18-before-146-reconciliation.md) and [archived state](docs/build-history/BUILD-STATE-2026-11-18-before-146-reconciliation.md); their pending instructions are superseded. BUILD-TESTS/LOG and backlog retain subsequent actual failures and passes.
