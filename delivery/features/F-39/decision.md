RECOMMENDATION: ESCALATE
COMMIT: 45ae7b660519ea32d5a7d5f08eff2817230ec33a
APPROVER: approver

## Summary
- F-39 is part 1 of the escalation (SCR-51, 8 boards, W-3601 to W-3609): Tola's check, the PMO Lead's "Escalate to the client" / "Don't escalate" decision, and Message v1 sent for internal review. Contract mock only; nothing reaches the client.
- Round 4 gate, technical, UX and integrated QA are PASS on this head. UI is carried forward from c706d6a7 with an impact note. PMO acceptance is PASS. No blocking finding is open.
- Fidelity is 76.8 to 87.1, all above the D-83 floor of 70. All 8 visual waivers and 44 exceptions are still "builder proposal, pending design engineer".
- Risk is medium with contract-change as a surface (X-VERDICTS, escalations enum, cites, links). The diff has 25 files (cap 15). Product acceptance is required and pending.
- The shared InlineDecide and Workspace change (stale notice) also reaches F-33's income line, which has no two-reviewer test of its own.

## Why
Merge policy keeps this with a human: contract-change is an always-human surface, the diff exceeds 15 files, and product acceptance and every waiver are unsigned. The code looks sound, stays inside the workspace features, fixtures and tests, and the 409 two-reviewer race (QA-3-1) is fixed and tested on this head.

## Acceptance criteria
1. Four states from data (W-3601 to W-3604): met. Component tests and QA at 1440 and 390.
2. Tola's work shown, never a decision: met.
3. Unknown is never 0 (W-3606): met.
4. The page counts and dates nothing: met.
5. Sample-marked: met.
6. Controls only from you_can_act and required_role: met.
7. Escalate: one claim, one decision, double press sends one: met.
8. Don't escalate needs a note: met.
9. No success before the re-read: met.
10. Uncertain decide never reads as success: met.
11. Backend refusals shown (403, 409, 422): met. The real two-reviewer 409 is fixed in round 4 (QA-3-1 verified).
12. Send for review: met on W-3604. On the mock, W-3602 has no after-step fixture (QA-4-1, non-blocking).
13. Missing reviewer is a hold (W-3608): met.
14. Nothing says sent to the client: met, enforced by a test over all fixtures and sidecars.
15. Access 401, 403, 404: met. The live 404 journey cannot run because the mock serves W-1001 (QA-3-2, non-blocking).
16. Frame: met.
17. Phone: met.
18. Fidelity (D-64, D-83): not met until the 8 waivers are signed. All scores are at or above the floor.
19. Accessibility: met per QA and review.
20. Tokens and components only: met.
21. Mock matches the contract: met.
22. Contract not extended: deviation. InlineDecide.tsx changed twice (see below). Accepted by PMO-4-2, pending the human's sign-off.
23. Existing tests green: met. checks.sh exit 0, 76/76 tests, e2e 60 passed.
24. build.md evidence: met.

## For the human
Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-39/fidelity-exceptions.json
- /Users/Hunchoo/psl-factory/delivery/features/F-39/round-2/fidelity/scores.txt
- /Users/Hunchoo/psl-factory/delivery/features/F-39/round-4/build.md
- /Users/Hunchoo/psl-factory/delivery/features/F-39/round-4/acceptance-pmo.md
- /Users/Hunchoo/psl-factory/delivery/NIGHT-LOG-2026-11-18.md

Please sign:
1. The visual waivers and exceptions. The 8 D-83 waivers are desktop investigating (87.1) and the other seven boards (76.8 to 86.1). The 44 entries include the Message v1 box styling (UI-2-2), "Back to the issue" position, the "15 DAYS LATE" tag, the time-only footer, the AgentCard head and footer (Conflicts 7), the crumbs, tab bar and phone bar (Conflicts 9), the frame items (Conflicts 12) and SAMPLE DATA. The mobile-draft waiver text needs the UI-3-1 correction (it mentions a box the phone board does not draw, and says "not pinned" when the button is pinned). The DONE tag colour (green on the page, blue on the board) is not named in the draft waivers yet.
2. The shared InlineDecide change. This is the AC 22 deviation (PMO-4-2). Round 1 added `task.asked` in the cannot-act branch. Round 4 added `onStale` and `DECIDE_TEXT.noteNotSent`, plus a Workspace alert, byte-identical to F-35's 971bf73a. The stale-notice fix also changes F-33's income line, which gets the new alert without a two-reviewer test (TECH-4-2). Decide whether to accept that or add the test first.
3. The round-1 coordinator decisions. InlineDecide draws the backend's `asked`. There is no `inputs: {}` on Send for review (a spec deviation; the schema allows it). The time-only card footer is an exception. The grep criterion allows F-16's "NOT YOUR DECISION" eyebrow.
4. Product acceptance (required). Open questions for PSL:
   - Does "Don't escalate" notify the person who raised it?
   - May the PMO Lead edit Message v1?
   - Which internal notes skip review (G-SCR51-1)?
   - Who reviews client messages (no policy slot)?
   - Should the notice after Don't escalate still read "was rejected" (UX-1-3, QA-3-3)?

Before the PR, the coordinator should:
- Resolve the Workspace.tsx import conflict with F-35 (TECH-4-1).
- Set `operation_ids` to the four operations (PMO-4-1).
- Add the stale-decide behaviour to the handoff text on the branch (PMO-4-3).
