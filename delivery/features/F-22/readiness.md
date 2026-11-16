DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-22 is the second half of FE-LINE-WEEKLY (SCR-25): the two outcomes of the PMO Lead's review decision. `returned` is the PM's "RETURNED TO YOU" page with the return note and "Edit your update". `received` is "RECEIVED BY CLIENT" with the per-recipient delivery confirmations. It is 4 boards (desktop and phone x returned and received), well under the D-64 cap of about 8. This is the "F-21b" that F-21's readiness.md and spec.md name.
- Gates are met. FE-LINE-WEEKLY is in architecture v7 with `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2014-2044). SCR-25 is in the 13 Nov client approval (design/review.json:38), and that covers all 12 SCR-25 boards, because the approval is by screen and screens.md:48 lists all 12 artboards. The dependency F-21 is merged (D-87, D-88, PR #39). F-17 (the frame) is merged.
- D-LINE-WORKSPACE is still `proposed` (architecture/build_model.py:826) and counts only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g) and (i)), on F-17 and F-21's terms. The limits are: contract mock only, the backend developer may change or refuse any field, nothing released.
- D-RETURN (open, r2) and D-ALERT-PROVIDERS (open, r2) do not block this feature. Neither is in FE-LINE-WEEKLY's `gate_ids`. Both are carried as working assumptions "the frontend builds against" (design engineer, 13 Nov 2026). D-RETURN holds only the runtime transition (what a return creates for the preparer). D-ALERT-PROVIDERS holds only real delivery (there is no chosen email provider, so no real confirmation exists). Details are under Risk.
- No business rule is open, so there are no questions. Both pages only show what the backend returns. The one thing to watch is truthfulness: "Verified" and "both deliveries confirmed" must come only from confirmation data, never from the page being reached.
- I did not run `design.py check` because my role has no shell. The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** after the review decision, the work item page shows its result. The PM sees a returned report with the PMO Lead's note and a way back to the editor. Everyone sees a received report with who it went to and whether each delivery is confirmed. This is on the contract mock, mounted on the F-17 renderer and the F-21 weekly work. It adds no route and no weekly-specific page.

**Boards (4):**
- SCR-25-desktop-returned and SCR-25-mobile-returned (`view: returned`). Desktop: the "RETURNED TO YOU" tag, a warning callout ("Kemi Adebayo returned v1 on 12 Nov: ..." with the note), "Your update" (the four parts, each with its cite chip such as "2 RECORDS", "ISS-0233", "MIN-0141", "2 ACTIONS"), and a "Next" panel ("Edit your part, then Tola reassembles v2 and it goes back for review." plus the primary "Edit your update"). Phone: "RETURNED", "Report returned", the quoted note, "Edit your update".
- SCR-25-desktop-received and SCR-25-mobile-received (`view: received`). Desktop: the "RECEIVED BY CLIENT" tag, a green callout ("Lagoon Health received v2: emailed 12 Nov 15:10 to 2 contacts, both deliveries confirmed. Verified."), "What happened" rows (Approved by <name> 12 NOV 14:58; Emailed to <recipient> DELIVERED 15:10; Emailed to <recipient> DELIVERED 15:11) and a "Next" panel ("Next week's report opens on 19 Nov, after the week ends."). Phone: "Report received", "Delivered to 2 client contacts. Verified."

**Reuse, not rebuild:**
- Build on the shared component library (`frontend/src/components`, D-91) from the start: `Callout`, `Panel`, `Tag`, `Button`/`Link`, `PageTitle`, `Breadcrumb`, `Tabs`, `FactsStrip`, `PhoneActionBar`. Do not add new local copies of callouts, tags or panels.
- Mount on the F-17 renderer (`features/work-item/**`) and the F-21 weekly work (tests/weekly.test.tsx, e2e/weekly.spec.ts, mock/fixtures W-2201 to W-2208). The sections map to existing kinds: `text` with `cites` for "Your update", `recipients` or `checklist` rows with tag and tone for "What happened", and the section `note` / header callout for the banner. Where a board region has no place in the frame, make a small general frame change, as F-21 did. The D-81 line frame (project tab bar, ~35px title) and the D-83 line-board rules apply as for F-21.
- "Edit your update" opens the F-21 default editor (the D-69 press-to-open form) for the same work item. It does not add a new write path. Saving and re-sending use E-WORK-STEP (`save_draft`, `send_to_tola`) with the F-17 idempotency and 409 handling already built in F-21. Tola reassembling v2 and the return to review are the existing assembling and review states from F-21.
- Return and Reject on the review board (F-21) already go through E-TASK-CLAIM/E-TASK-DECIDE. F-22 builds no new decision UI; it only renders the result.

**Task ID and endpoints:** FE-LINE-WEEKLY (R-WORKITEM, R-DECIDE), second part. E-WORK-ITEM (read, `workspace`; `view` is a free string in the v7 contract, so `returned` and `received` need no schema change). E-WORK-STEP (write, from the returned page's editor), E-WORK-ACTION (reconcile, reuse), E-LINE-OPTIONS (reuse for the record pick lists). All on the contract mock. Acceptance: A-WORKSPACE (frontend half), with A-WORKITEM, A-DECIDE, the F-17 tests and all F-21 tests staying green.

**Tests and fidelity (D-64, D-83):**
- New v7-typed fixtures for `returned` and `received` on the weekly line, schema-validated. The F-21 mock test currently asserts no served fixture contains `"returned"` or `"received"` (frontend/tests/weekly-mock.test.ts:54). F-22 must replace that guard with positive checks for the new fixtures and keep it for W-2201 to W-2208, so the F-21 IDs stay unchanged.
- Fixtures needed: returned (note, returner, date, version), received with two confirmed deliveries, and the edge cases below: received with an unknown confirmation, a delivery that is `uncertain` or `failed`, and no recipients.
- Unit tests plus Playwright with axe at 390 and 1440. Tokens only, no hard-coded colour. Reduced motion respected.
- Per D-64: one fidelity run per round. Per D-83: the four boards pass on 100% element coverage after approved exceptions, the UI reviewer's side-by-side reading finding no fixable gap, and visual >= 70, with a visual waiver signed per board in the feature's `fidelity-exceptions.json` citing D-83. Sonnet builders (medium risk). Only affected reviews re-run after a fix round.
- `design.py check` must pass first.

**Binding rules for the spec:**
- The frontend shows only what the backend returns. The return note, the returner's name, the version number, the dates and times, the recipient names and addresses, the "N contacts" count, the "Next week's report opens on 19 Nov" sentence and every tag come from the data. The page computes none of them, including the next-week date and the count of contacts. Nothing is derived from `/me` roles (not "RETURNED TO YOU", not who may edit): whether the viewer can edit comes from the item's `allowed_actions` / step data, and a viewer who cannot edit sees no "Edit your update" button.
- Unknown is not zero (INV-UNKNOWN). A missing confirmation time, count or recipient shows "Unknown", never 0, blank or "Delivered".
- Delivery confirmations are shown only from data. "DELIVERED hh:mm" appears only for a recipient whose confirmation says delivered, with its returned time. The green "Verified" callout and the phone "Delivered to 2 client contacts. Verified." appear only when the data says every recipient is confirmed. Reaching the `received` view is not itself proof. A recipient whose status is not confirmed (`uncertain`, `failed`, `not_yet`, `unknown`) shows its own tag and tone as returned (the contract's `tag.tone` is the backend's, never derived from the state name) and the callout does not claim "Verified" or "both deliveries confirmed". Partial confirmation is shown as partial.
- No resend while uncertain (INV-RESEND, the F-17 round-6 and QA-5-5 fix). The page offers no "Send again" or "Resend", and no new key. After an `effect_uncertain` send the only action is reconcile on E-WORK-ACTION, locked from the item's own reconcile state so a reload does not unlock it. The `received` page offers no action that sends a report. If the backend returns `received` with an uncertain recipient, only reconcile is offered. The reconcile reply is still undefined (BACKEND-HANDOFF.md, "Added during F-21"), so this is verified on the mock only.
- Tola assembles but does not write the client text. "Edit your update" opens the PM's own text. Nothing offers to generate or rewrite it.
- Test-template and sample labels show when the data says so. Do not claim a real client template or a real delivery.
- Unknown work id gives the 404 state with no client, title or id (F-21 QA-3-2). Nothing from another item's fixture shows.

**Out:**
- Backend, OpenAPI, `schema.d.ts` regeneration and `architecture/**`. Contract gaps go in build.md as proposals. The ones already known: how the delivery confirmations are carried per recipient (an item `tag` plus `value`, or a proper receipt field), where the return note and returner live, and the reconcile reply.
- Real sends and real delivery confirmation. Nothing leaves the mock.
- The return-and-edit loop beyond what F-21 built, a "returned" counter or history view, and the PMO Lead's own view of a returned report (not drawn).
- FE-LINE-MINUTES (F-23), the assistant (F-24) and every other line.
- Changes to `src/shell/**`, `my-work/**` and the existing work item boards.
- Board-vs-data differences to list as exceptions rather than invent fields: the desktop boards select the "Documents" project tab while the project's Journey tab would be the usual one (frame, D-81); the desktop returned and phone returned notes differ in length (the phone quote is shorter), so the page shows the single note the data carries; the sentence "emailed ... to 2 contacts" is data text, not computed.

## Risk
Medium. The work is on the shared renderer and a proposed v7 contract (D-LINE-WORKSPACE, `proposed`, so the backend may change any field) and it renders delivery confirmations for a client-bound send (INV-RESEND, effect_uncertain). It stays at medium rather than high because both new states are read views plus a link into the F-21 editor. All of it is on the mock, no send is made here, and nothing is released. SURFACES: ui (4 boards), api (E-WORK-ITEM `workspace` views, E-WORK-STEP via the editor), contract-change (proposed block and the receipt shape), external-messaging (client report delivery truthfulness). PRODUCT-ACCEPTANCE is not-required because both pages conform to the client-approved boards (design/review.json:38) and the rules (return needs a note, exact version sent, four cited parts) are on the boards and in screens.md:116.

D-RETURN (model.json, `open`, owner "business owner with the backend developer"): the proposal is that every return creates a "correct and resubmit" task for the preparer, and the returned board matches it ("Edit your part, then Tola reassembles v2"). It is not in this task's gates and the frontend builds against it as a working assumption. It holds only the runtime behaviour: what the real backend creates on Return and how it numbers v2. Until it is decided, nothing derives that from the frontend. It does not block the build.

D-ALERT-PROVIDERS (model.json, `open`): no WhatsApp or email provider is chosen and the accounts belong to PSL (I-03), so no real delivery confirmation exists. It holds only the real confirmation transition. It does not block the build, because the page renders confirmations from mock data and claims nothing the data does not say. Delivery confirmations and the "Verified" claim must not appear from anything but confirmation data.

Backend items to record (not blocking): E-WORK-STEP, the `workspace` block and the reconcile reply are unimplemented; idempotency, the resend refusal and cite scoping are backend promises (BACKEND-HANDOFF.md priority 1 and "Added during F-21"); the client template is a test template until PSL supplies the real one.

**Size:** one PR on the existing frame, 4 boards, two states on the same route, roughly 600 to 1,000 lines with fixtures and tests. If the spec shows more, drop the two phone boards to a follow-on first.

## Questions
None.
