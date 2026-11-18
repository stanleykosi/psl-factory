DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging, product-decision
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-28 is the second half of FE-LINE-MINUTES (SCR-28): the two end states, `internal` (minutes filed at once) and `published` (client minutes approved and sent), each on desktop and phone. That is 4 boards, well inside the D-64 cap of about 8. One outcome, one PR.
- Gates are met. FE-LINE-MINUTES is in architecture v7 with no unresolved gates (see F-23 readiness, architecture/packages/v7/delivery.md:2046-2076). SCR-28 is in the client approval of 13 Nov 2026 (design/review.json). Its dependency F-23 (default, suggesting, drafted, review) is merged (PR #54), and F-23's spec deliberately left these 4 boards to this feature (F-23 spec.md:71, 131, 230).
- The one soft gate is D-LINE-WORKSPACE, still `proposed`. It counts only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g) and (i)): contract mock only, the backend developer may change or refuse any field, nothing released. Same terms as F-17, F-21 and F-23.
- The rule "which audiences skip review" has no decision id (gaps-c-client-lines.md SCR-28). The frontend decides nothing: it renders whatever the reloaded work item returns. Decisions D-98, D-104, D-105 and D-106 (F-23 conflicts and waivers) carry over; no new question reaches the client.
- I did not run `design.py check` (no shell in this role). The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** after the PM confirms internal minutes, or the PMO Lead approves client minutes, the work item (`/work/{work_id}`, line key `minutes`) shows the finished result on the F-17 workspace frame. Internal: the minutes are filed and the actions created, listed with owner and due date, with "OWNER NEEDED" where an action has none. Published: the approved version, the recipients each with their own delivery receipt, the actions created, and "Open actions". All on the contract mock.

**Boards (4):** SCR-28-desktop-internal, SCR-28-mobile-internal, SCR-28-desktop-published, SCR-28-mobile-published (design/canvas/project/). Combined with F-23's 8, SCR-28 is complete at 12 of 12.

**Task ID and endpoints:** FE-LINE-MINUTES (R-WORKITEM), second part. Read-mostly: E-WORK-ITEM (`workspace`), E-DOCUMENT for opening the minutes, and the existing reconcile path on E-WORK-ACTION. Owner assignment on an "OWNER NEEDED" action reuses the F-23 per-item step form (E-WORK-STEP with the F-17 idempotency key, `expected_revision`, 409 reload; E-LINE-OPTIONS scoped by `work_id`) only if the data offers that step. No new route and no new endpoint. Acceptance: A-WORKSPACE (frontend half), with A-WORKITEM, A-DECIDE and the F-17, F-21 and F-23 tests staying green.

**Reuse, not rebuild:** `frontend/src/features/workspace/**` and `features/work-item/**` (sections `table`, `recipients`, `facts`, `timeline`; `link.action_id`), the shared component library (D-91..D-96; no local copies), tokens only. Extend the frame only with small general changes. Add v7-typed mock fixtures for `internal` and `published` and make the F-23 mock handler return them after confirm (internal) and after approve (published). F-23's seam stays: Approve and Return still produce the generic outcomes, and the reloaded item now renders as these boards.

**Tests and fidelity (D-64, D-83, item (h)):** unit tests for the fixtures and any new frame change; Playwright with axe at 390 and 1440. The UI review passes only on the design-fidelity check of the 4 boards with every element present (after approved exceptions) and a score of at least 90. Run fidelity once per round. Sonnet builder unless the spec rates the work high risk.

**Out:** the F-23 boards and their steps (do not reopen them), every other line, backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `src/shell/**`, `my-work/**`. Real sends and real filing: nothing leaves the mock. If a board needs something the contract lacks, record it as a contract proposal in build.md and do not extend the contract locally.

## Binding rules for the spec
- The frontend shows only what the backend returns. Filed status, action counts, owners, due dates, recipient names and receipt states all come from the data. Nothing is derived from `/me` roles or from the notes text (INV-ACCESS, INV-AGENT).
- Receipts are per person (`receipt` on each `recipients` item). Never show one aggregate "Delivered". Show "Sent" or "Delivered" only when a recipient's receipt says so. Where it is `not_yet` or absent, say so. A send in `effect_uncertain` keeps the F-17 rule: the only action is reconcile; no resend, no new key (INV-RESEND).
- Unknown values show "Unknown", never 0 or blank (INV-UNKNOWN). An action without an owner shows "OWNER NEEDED" as the board draws it, and no owner is guessed or inferred from the notes.
- The frontend does not decide which audience skips review, where internal minutes are filed, or whether actions are created at confirm or at approval (G-SCR28-5, G-SCR28-7). It shows the data and the `consequence` text as returned and adds no wording of its own.
- "Open actions" and "Open the minutes" render only when the data supplies the link (`workspace.links[]` / `version.document_id`, G-SCR28-3). Otherwise they do not appear.
- Template label stays "TEST TEMPLATE" until PSL supplies the real one (product decisions, Nov 2026). Alerts and the real client send are D-ALERT-PROVIDERS and do not gate the mock.
- No wrapping button labels, tags on one line, 44px phone targets (D-92c), prefers-reduced-motion respected, labels and focus order right.
- Any board difference (for example how a phone lays out the recipient list) goes in the exceptions file for the design engineer to sign, as in D-105.

## Contract proposals the spec must carry
From gaps-c-client-lines.md, SCR-28 section. Additive, mock overlay only, for the backend developer to confirm. Build.md records each.
1. G-SCR28-3 links: `workspace.links[]` {key, label, target kind} and `link.action_id`, now including "Open actions".
2. G-SCR28-7 order of creation, and the audience-skips-review rule (no decision id): backend questions. The mock fixtures encode no rule beyond what each fixture returns.
3. G-SCR28-8 recipients: exact recipients from the data with a per-person `receipt`.
4. G-SCR28-6 records: there is no REC-ACTION, REC-DECISION or REC-MEETING in model.json. A backend item, not a frontend change.
5. Backend items, not blocking: the `workspace` block and E-WORK-STEP are unimplemented, and idempotency is a backend promise not yet built. "No duplicate send" is verified only on the mock.

## Risk
Medium. The work sits on the shared F-17 renderer (`features/workspace/**`, `features/work-item/**`) and a proposed v7 contract (D-LINE-WORKSPACE), and the published board shows per-recipient delivery of client minutes (external-messaging, INV-RESEND, uncertain effect). It stays at medium because it is 4 read-mostly boards, everything is on the mock, the backend send and filing are unimplemented and nothing is released. SURFACES match F-23: ui, api, contract-change, external-messaging, product-decision (the audience rule and order of creation belong to the backend and PSL, not this build). PRODUCT-ACCEPTANCE is not-required: the work conforms to the client-approved boards and adds no flow, copy or rule the boards do not already draw.

## Questions
None. Open items (audience-skips-review rule, order of creation, D-LINE-WORKSPACE confirmation) hold the real backend transition, not this mock build.
