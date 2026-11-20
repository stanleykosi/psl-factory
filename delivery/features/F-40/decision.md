RECOMMENDATION: ESCALATE
COMMIT: 60ff597c130fee6aa063eeafe8b11cb3bd6e900b
APPROVER: approver

## Summary
- F-40 draws the Handover to Support item (SCR-48) in four states from the contract mock: Tola's draft, Publish, the PM records Support's reply with proof, gaps go back for v2, acknowledged only after the re-read. Nothing is sent to Support.
- Gate (attempt 4, D-127), technical, security, UX, UI, QA and PMO acceptance all PASS on this head, with no blocking finding.
- Risk is medium, but surfaces include contract-change, external-messaging and product-decision, which are always-human in the merge policy.
- Open items are the design engineer's: 8 waivers, 26 exceptions, Conflicts 1 to 5 and product acceptance.
- Before the PR: set `operation_ids` and add the F-40 section to BACKEND-HANDOFF.md (PMO-3-1, PMO-3-2).

## Why
The work is sound and evidenced, but the always-human surfaces and the unsigned visual and product decisions need a person. Publish is a send with no defined channel (G-48-2), and the fidelity waivers go as low as 73.8.

## Acceptance criteria
1. Fidelity scores (AC 1): not met until the waivers are signed. Eight boards score 73.8 to 88.2, below 90, so each needs a D-83 waiver.
2. Exceptions limited (AC 2): met in content, none covers data; unsigned.
3. Row opens the item (AC 3): met; Handover row and sub-nav link to W-3704, and P-0101.json differs by one `work_id` line (checked in the diff).
4. Four states from data, authority from `you_can_act`, hold has no controls: met, per technical review and QA at 1440 and 390.
5. Verified only after the re-read, uncertain recovery, no resend: met, QA exercised 409, 500, 403, 404, W-3706, W-3707, W-3708.
6. Proof upload then one POST, gaps sent only with Gaps found: met, QA.
7. Access, phone, accessibility: met; the shared History link size is a follow-up (UX-2-1).
8. Existing tests green, evidence: met; checks.sh passed on this head and e2e 152/152 after the merge.

## For the human
Please sign or refuse:
1. The 8 D-83 visual waivers (73.8 to 88.2) in fidelity-exceptions.json `visual_waivers`: desktop 79.4, gaps 83.4, received 77.8, record 73.8; mobile 86.8, gaps 88.2, received 75.3, record 82.5.
2. The 26 exceptions (all "builder proposal, pending design engineer"), including the separate Support replied date-time picker (UI-2-1; the contract needs a structured date-time) and the shared Proof card's Remove button (UI-2-2).
3. Spec Conflicts 1 to 5 (round-1/build.md, spec.md lines 22 to 36):
   - 1: "Review needed? NO" is a sample fixture only; the real page shows Unknown (rule Not set) with no Publish.
   - 2: Publish is a mock step; the real send waits for a Support channel (G-48-2).
   - 3: the reply form draws in place on the work item, not in a Drawer.
   - 4: Gaps is one box, one gap per line, sent as `gaps[]` (G-48-1).
   - 5: the "I confirm this response is genuine" tick is added to the form.
4. Product acceptance (required): when a handover needs review (`delivery.handover_review`, Not set), the Support recipient and channel, and the `gaps` field proposal.

Follow-ups, not blocking: shared History link height (24px at 390), mock-only `gaps` field (G-48-1), Parts 2 and 3 of FE-DELIVERY-CLOSURE.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-40/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-40/spec.md
- /Users/Hunchoo/psl-factory/delivery/features/F-40/round-1/build.md
- /Users/Hunchoo/psl-factory/delivery/features/F-40/round-3/review-ui.md
- /Users/Hunchoo/psl-factory/delivery/features/F-40/round-3/acceptance-pmo.md
